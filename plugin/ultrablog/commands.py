#!/usr/bin/env python

import vim, xmlrpclib, webbrowser, sys, re, tempfile, os, mimetypes, inspect
from exceptions import *
from db import *
from util import *
from events import *
from eventqueue import UBEventQueue

def __ub_exception_handler(func):
    def __check(*args,**kwargs):
        try:
            return func(*args,**kwargs)
        except UBException, e:
            sys.stderr.write(str(e))
        except xmlrpclib.Fault, e:
            sys.stderr.write("xmlrpc error: %s" % e.faultString.encode("utf-8"))
        except xmlrpclib.ProtocolError, e:
            sys.stderr.write("xmlrpc error: %s %s" % (e.url, e.errmsg))
        except IOError, e:
            sys.stderr.write("network error: %s" % e)
        except Exception, e:
            sys.stderr.write(str(e))
    return __check

def __ub_enc_check(func):
    def __check(*args, **kw):
        orig_enc = vim.eval("&encoding") 
        if orig_enc != "utf-8":
            modified = vim.eval("&modified")
            buf_list = '\n'.join(vim.current.buffer).decode(orig_enc).encode('utf-8').split('\n')
            del vim.current.buffer[:]
            vim.command("setl encoding=utf-8")
            vim.current.buffer[0] = buf_list[0]
            if len(buf_list) > 1:
                vim.current.buffer.append(buf_list[1:])
            if modified == '0':
                vim.command('setl nomodified')
        return func(*args, **kw)
    return __check

@__ub_exception_handler
def ub_list_items(item_type='post', scope='local', page_size=None, page_no=None):
    ''' List items
    '''
    cmd = UBCmdList(item_type, scope, page_size, page_no)
    cmd.execute()

@__ub_exception_handler
def ub_find(page_no, *keywords):
    ''' List posts/pages which match the keywords given
    '''
    cmd = UBCmdFind(page_no, *keywords)
    cmd.execute()

@__ub_exception_handler
def ub_refresh_current_view():
    ''' Refresh current view
    '''
    if ub_is_ubbuf('%'):
        vname = ub_get_viewname('%')
        if vname == 'search_result_list':
            kws = ub_get_bufvar('ub_keywords')
            pno = ub_get_bufvar('page_no')
            ub_find(pno, *kws)
        elif ub_is_view_of_type('list'):
            vinfo = vname.split('_')
            psize = ub_get_bufvar('page_size')
            pno = ub_get_bufvar('page_no')
            ub_list_items(vinfo[1], vinfo[0], psize, pno)
        elif ub_is_view_of_type('edit'):
            id = ub_get_meta('id')
            id = (id is not None and id) or ub_get_meta('name')
            if ub_is_id(id) or not ub_is_emptystr(id):
                modified = '1'==vim.eval('&modified')
                vim.command('setl nomodified')
                vinfo = vname.split('_')
                try:
                    ub_open_item(vinfo[0], id, 'local')
                except Exception, e:
                    if modified is True:
                        vim.command('setl modified')
                    else:
                        vim.command('setl nomodified')
                    sys.stderr.write(str(e))
            else:
                raise UBException('Key of current buffer cannot be found !')
        else:
            sys.stderr.write('Not implemented !')
            return

@__ub_exception_handler
def ub_preview(tmpl=None):
    '''Preview the current buffer in a browser
    '''
    if not ub_is_view('post_edit') and not ub_is_view('page_edit'):
        raise UBException('Invalid view !')

    prv_url = ''
    enc = vim.eval('&encoding')

    if tmpl in ['private', 'publish', 'draft']:
        ub_send_item(tmpl)

        if ub_is_view('page_edit'):
            prv_url = "%s?pageid=%s&preview=true"
        else:
            prv_url = "%s?p=%s&preview=true"

        prv_url = prv_url % (cfg.blogURL, ub_get_meta('post_id'))
    else:
        if tmpl is None:
            tmpl = ub_get_option('ub_default_template')

        sess = Session()
        template = sess.query(Template).filter(Template.name==tmpl.decode(enc)).first()
        sess.close()
        if template is None:
            raise UBException("Template '%s' is not found !" % tmpl)

        tmpl_str = template.content.encode(enc)

        draft = {}
        draft['title'] = ub_get_meta('title')
        draft['content'] = ub_get_html()

        tmpfile = tempfile.mktemp(suffix='.html')
        fp = open(tmpfile, 'w')
        fp.write(tmpl_str % draft)
        fp.close()
        prv_url = "file://%s" % tmpfile

    webbrowser.open(prv_url)

@__ub_exception_handler
def ub_save_item():
    '''Save the current buffer to local database
    '''
    cmd = UBCmdSave()
    cmd.execute()

@__ub_exception_handler
def ub_send_item(status=None):
    '''Send the current item to the blog
    '''
    cmd = UBCmdSend(status)
    cmd.execute()

@__ub_exception_handler
def ub_open_item_x(item_type, key, scope='local'):
    ''' Open item, this function use __ub_exception_handler and so is suitable to be called directly
    '''
    ub_open_item(item_type, key, scope)

def ub_open_item(item_type, key, scope='local'):
    ''' Open item, this function do not use the __ub_exception_handler and so can be used programmatically
    '''
    ub_check_item_type(item_type)
    ub_check_scope(scope)
    eval("ub_open_%s_%s('%s')" % (scope, item_type, key))

def ub_open_local_post(id, view_type=None):
    '''Open local post
    '''
    # Check prerequesites
    __ub_check_prerequesites()

    # Set editor mode if the corresponding option has been set
    ub_set_mode()

    sess = Session()
    post = sess.query(Post).filter(Post.id==id).first()
    if post is None:
        raise UBException('No post found !')

    post_id = post.post_id
    if post_id is None:
        post_id = 0

    enc = vim.eval('&encoding')
    post_meta_data = dict(\
            id = post.id,
            post_id = post_id,
            title = post.title.encode(enc),
            categories = post.categories.encode(enc),
            tags = post.tags.encode(enc),
            slug = post.slug.encode(enc),
            status = post.status.encode(enc))

    ub_wise_open_view('post_edit', view_type)
    ub_fill_meta_data(post_meta_data)
    vim.current.buffer.append(post.content.encode(enc).split("\n"))

    vim.command('setl filetype=%s' % post.syntax)
    vim.command('setl wrap')
    vim.command('call UBClearUndo()')
    vim.command('setl nomodified')
    vim.current.window.cursor = (len(post_meta_data)+3, 0)

def ub_open_local_page(id, view_type=None):
    '''Open local page
    '''
    # Check prerequesites
    __ub_check_prerequesites()

    # Set editor mode if the corresponding option has been set
    ub_set_mode()

    sess = Session()
    page = sess.query(Post).filter(Post.id==id).filter(Post.type=='page').first()
    if page is None:
        raise UBException('No page found !')

    post_id = page.post_id
    if post_id is None:
        post_id = 0

    enc = vim.eval('&encoding')
    page_meta_data = dict(\
            id = page.id,
            post_id = post_id,
            title = page.title.encode(enc),
            slug = page.slug.encode(enc),
            status = page.status.encode(enc))

    ub_wise_open_view('page_edit', view_type)
    ub_fill_meta_data(page_meta_data)
    vim.current.buffer.append(page.content.encode(enc).split("\n"))

    vim.command('setl filetype=%s' % page.syntax)
    vim.command('setl wrap')
    vim.command('call UBClearUndo()')
    vim.command('setl nomodified')
    vim.current.window.cursor = (len(page_meta_data)+3, 0)

def ub_open_remote_post(id, view_type=None):
    '''Open remote post
    '''
    # Check prerequesites
    __ub_check_prerequesites()

    # Set editor mode if the corresponding option has been set
    ub_set_mode()

    global cfg, api

    sess = Session()
    post = sess.query(Post).filter(Post.post_id==id).first()
    saveit = None

    # Fetch the remote post if there is not a local copy
    if post is None:
        remote_post = api.metaWeblog.getPost(id, cfg.loginName, cfg.password)
        post = Post()
        post.post_id = id
        post.title = remote_post['title']
        post.content = remote_post['description']
        post.categories = ', '.join(remote_post['categories'])
        post.tags = remote_post['mt_keywords']
        post.slug = remote_post['wp_slug']
        post.status = remote_post['post_status']
        post.syntax = 'html'

        saveit = ub_get_option('ub_save_after_opened', True)
        if saveit is True:
            sess.add(post)
            sess.commit()

    id = post.id
    if post.id is None:
        id = 0
    enc = vim.eval('&encoding')
    post_meta_data = dict(\
            id = id,
            post_id = post.post_id,
            title = post.title.encode(enc),
            categories = post.categories.encode(enc),
            tags = post.tags.encode(enc),
            slug = post.slug.encode(enc),
            status = post.status.encode(enc))

    ub_wise_open_view('post_edit', view_type)
    ub_fill_meta_data(post_meta_data)
    vim.current.buffer.append(post.content.encode(enc).split("\n"))

    vim.command('setl filetype=%s' % post.syntax)
    vim.command('setl wrap')
    vim.command('call UBClearUndo()')
    if saveit is not False:
        vim.command('setl nomodified')
    vim.current.window.cursor = (len(post_meta_data)+3, 0)

def ub_open_remote_page(id, view_type=None):
    '''Open remote page
    '''
    # Check prerequesites
    __ub_check_prerequesites()

    # Set editor mode if the corresponding option has been set
    ub_set_mode()

    global cfg, api

    sess = Session()
    page = sess.query(Post).filter(Post.post_id==id).filter(Post.type=='page').first()
    saveit = None

    # Fetch the remote page if there is not a local copy
    if page is None:
        remote_page = api.wp.getPage('', id, cfg.loginName, cfg.password)
        page = Post()
        page.type = 'page'
        page.post_id = id
        page.title = remote_page['title']
        page.content = remote_page['description']
        page.slug = remote_page['wp_slug']
        page.status = remote_page['page_status']
        page.syntax = 'html'

        saveit = ub_get_option('ub_save_after_opened', True)
        if saveit is True:
            sess.add(page)
            sess.commit()

    id = page.id
    if page.id is None:
        id = 0
    enc = vim.eval('&encoding')
    page_meta_data = dict(\
            id = id,
            post_id = page.post_id,
            title = page.title.encode(enc),
            slug = page.slug.encode(enc),
            status = page.status.encode(enc))

    ub_wise_open_view('page_edit', view_type)
    ub_fill_meta_data(page_meta_data)
    vim.current.buffer.append(page.content.encode(enc).split("\n"))

    vim.command('setl filetype=%s' % page.syntax)
    vim.command('setl wrap')
    vim.command('call UBClearUndo()')
    if saveit is not False:
        vim.command('setl nomodified')
    vim.current.window.cursor = (len(page_meta_data)+3, 0)

def ub_open_local_tmpl(name, view_type=None):
    '''Open template
    '''
    # Check prerequesites
    __ub_check_prerequesites()

    # Set editor mode if the corresponding option has been set
    ub_set_mode()

    enc = vim.eval('&encoding')
    name = name.decode(enc)

    sess = Session()
    tmpl = sess.query(Template).filter(Template.name==name).first()
    if tmpl is None:
        raise UBException('No template found !')

    meta_data = dict(\
            name = tmpl.name.encode(enc),
            description = tmpl.description.encode(enc))

    ub_wise_open_view('tmpl_edit', view_type)
    ub_fill_meta_data(meta_data)
    vim.current.buffer.append(tmpl.content.encode(enc).split("\n"))

    vim.command('setl filetype=html')
    vim.command('setl nowrap')
    vim.command('call UBClearUndo()')
    vim.command('setl nomodified')
    vim.current.window.cursor = (len(meta_data)+3, 0)

@__ub_exception_handler
def ub_del_item(item_type, key, scope='local'):
    '''Delete an item
    '''
    # Check prerequesites
    __ub_check_prerequesites()

    ub_check_item_type(item_type)
    ub_check_scope(scope)

    # Set editor mode if the corresponding option has been set
    ub_set_mode()

    enc = vim.eval('&encoding')

    choice = vim.eval("confirm('Are you sure to delete %s %s \"%s\" ?', '&Yes\n&No')" % (scope, ub_get_item_type_name(item_type), key))
    if choice != '1':
        return

    sess = Session()

    try:
        if item_type == 'tmpl':
            sess.query(Template).filter(Template.name==key.decode(enc)).delete()
            UBEventQueue.fireEvent(UBTmplDelEvent(key))
        else:
            id = int(key)

            if scope=='remote':
                global cfg, api
                if item_type=='page':
                    api.wp.deletePage('', cfg.loginName, cfg.password, id)
                else:
                    api.metaWeblog.deletePost('', id, cfg.loginName, cfg.password)
                UBEventQueue.fireEvent(UBRemotePostDelEvent(id))
            else:
                sess.query(Post).filter(Post.id==id).delete()
                UBEventQueue.fireEvent(UBLocalPostDelEvent(id))
    except Exception,e:
        sess.rollback()
        raise e
    else:
        sess.commit()
    finally:
        sess.close()

    UBEventQueue.processEvents()

@__ub_exception_handler
def ub_upload_media(file_path):
    '''Upload a file
    '''
    if not ub_is_view('post_edit'):
        raise UBException('Invalid view !')
    if not os.path.exists(file_path):
        raise UBException('File not exists !')

    file_type = mimetypes.guess_type(file_path)[0]
    fp = open(file_path, 'rb')
    bin_data = xmlrpclib.Binary(fp.read())
    fp.close()

    global cfg, api
    result = api.metaWeblog.newMediaObject('', cfg.loginName, cfg.password,
        dict(name=os.path.basename(file_path), type=file_type, bits=bin_data))

    img_tmpl_info = ub_get_option('ub_tmpl_img_url', True)
    img_url = img_tmpl_info['tmpl'] % result
    syntax = vim.eval('&syntax')
    img_url = __ub_convert_str(img_url, img_tmpl_info['syntax'], syntax)
    vim.current.range.append(img_url.split("\n"))

@__ub_exception_handler
def ub_blog_this(type='post', syntax=None):
    '''Create a new post/page with content in the current buffer
    '''
    if syntax is None:
        syntax = vim.eval('&syntax')
    try:
        ub_check_syntax(syntax)
    except:
        syntax = 'markdown'

    bf = vim.current.buffer[:]

    if type == 'post':
        success = ub_new_post(syntax)
    else:
        success = ub_new_page(syntax)

    if success is True:
        regex_meta_end = re.compile('^\s*-->')
        for line_num in range(0, len(vim.current.buffer)):
            line = vim.current.buffer[line_num]
            if regex_meta_end.match(line):
                break
        vim.current.buffer.append(bf, line_num+1)

@__ub_exception_handler
def ub_convert(to_syntax, from_syntax=None, literal=False):
    '''Convert the current buffer from one syntax to another
    '''
    ub_check_syntax(to_syntax)
    if from_syntax is None:
        from_syntax = vim.eval('&syntax')
    ub_check_syntax(from_syntax)

    content = __ub_get_content()
    enc = vim.eval('&encoding')
    new_content = __ub_convert_str(content, from_syntax, to_syntax, enc)

    if literal == True:
        return new_content
    else:
        __ub_set_content(new_content.split("\n"))
        vim.command('setl filetype=%s' % to_syntax)

@__ub_exception_handler
def ub_new_item(item_type='post', mixed='markdown'):
    ''' Create new item: post, page, template
    '''
    ub_check_item_type(item_type)
    
    if item_type=='post' or item_type=='page':
        ub_check_syntax(mixed)

    eval("ub_new_%s('%s')" % (item_type,mixed))

def ub_new_post(syntax='markdown'):
    '''Initialize a buffer for writing a new post
    '''
    ub_check_syntax(syntax)

    post_meta_data = dict(\
            id = str(0),
            post_id = str(0),
            title = '',
            categories = __ub_get_categories(),
            tags = '',
            slug = '',
            status = 'draft')

    ub_wise_open_view('post_edit')
    ub_fill_meta_data(post_meta_data)
    __ub_append_promotion_link(syntax)

    vim.command('setl filetype=%s' % syntax)
    vim.command('setl wrap')
    vim.command('call UBClearUndo()')
    vim.command('setl nomodified')
    vim.current.window.cursor = (4, len(vim.current.buffer[3])-1)

    return True

def ub_new_page(syntax='markdown'):
    '''Initialize a buffer for writing a new page
    '''
    ub_check_syntax(syntax)

    page_meta_data = dict(\
            id = str(0),
            post_id = str(0),
            title = '',
            slug = '',
            status = 'draft')

    ub_wise_open_view('page_edit')
    ub_fill_meta_data(page_meta_data)

    vim.command('setl filetype=%s' % syntax)
    vim.command('setl wrap')
    vim.command('call UBClearUndo()')
    vim.command('setl nomodified')
    vim.current.window.cursor = (4, len(vim.current.buffer[3])-1)

    return True

def ub_new_tmpl(name):
    '''Initialize a buffer for creating a template
    '''
    # Check if the given name is a reserved word
    try:
        ub_check_status(name)
    except UBException:
        pass
    else:
        raise UBException("'%s' is a reserved word !" % name)

    # Check if the given name is already existing
    enc = vim.eval('&encoding')
    sess = Session()
    if sess.query(Template).filter(Template.name==name.decode(enc)).first() is not None:
        sess.close()
        raise UBException('Template "%s" exists !' % name)

    meta_data = dict(\
            name = name,
            description = '')

    ub_wise_open_view('tmpl_edit')
    ub_fill_meta_data(meta_data)
    __ub_append_template_framework()

    vim.command('setl filetype=html')
    vim.command('setl nowrap')
    vim.command('call UBClearUndo()')
    vim.command('setl nomodified')
    vim.current.window.cursor = (3, len(vim.current.buffer[2])-1)

def __ub_append_template_framework():
    fw = \
'''<html>
    <head>
        <meta http-equiv="Content-Type" content="text/html; charset=utf-8">
        <title>%(title)s</title>
        <style>
        </style>
    </head>
    <body>
        %(content)s
    </body>
</html>'''
    lines = fw.split("\n")
    vim.current.buffer.append(lines)

def ub_fill_meta_data(meta_data):
    if ub_is_view('post_edit'):
        __ub_fill_post_meta_data(meta_data)
    elif ub_is_view('page_edit'):
        __ub_fill_page_meta_data(meta_data)
    elif ub_is_view('tmpl_edit'):
        __ub_fill_tmpl_meta_data(meta_data)
    else:
        raise UBException('Unknown view !')

def __ub_fill_post_meta_data(meta_dict):
    '''Fill the current buffer with some lines of meta data for a post
    '''
    meta_text = \
"""<!--
$id:              %(id)s
$post_id:         %(post_id)s
$title:           %(title)s
$categories:      %(categories)s
$tags:            %(tags)s
$slug:            %(slug)s
$status:          %(status)s
-->""" % meta_dict
    
    meta_lines = meta_text.split('\n')
    if len(vim.current.buffer) >= len(meta_lines):
        for i in range(0,len(meta_lines)):
            vim.current.buffer[i] = meta_lines[i]
    else:
        vim.current.buffer[0] = meta_lines[0]
        vim.current.buffer.append(meta_lines[1:])

def __ub_fill_page_meta_data(meta_dict):
    '''Fill the current buffer with some lines of meta data for a page
    '''
    meta_text = \
"""<!--
$id:              %(id)s
$post_id:         %(post_id)s
$title:           %(title)s
$slug:            %(slug)s
$status:          %(status)s
-->""" % meta_dict
    
    meta_lines = meta_text.split('\n')
    if len(vim.current.buffer) >= len(meta_lines):
        for i in range(0,len(meta_lines)):
            vim.current.buffer[i] = meta_lines[i]
    else:
        vim.current.buffer[0] = meta_lines[0]
        vim.current.buffer.append(meta_lines[1:])

def __ub_fill_tmpl_meta_data(meta_dict):
    '''Fill the current buffer with some lines of meta data for a template
    '''
    meta_text = \
"""<!--
$name:            %(name)s
$description:     %(description)s
-->""" % meta_dict
    
    meta_lines = meta_text.split('\n')
    if len(vim.current.buffer) >= len(meta_lines):
        for i in range(0,len(meta_lines)):
            vim.current.buffer[i] = meta_lines[i]
    else:
        vim.current.buffer[0] = meta_lines[0]
        vim.current.buffer.append(meta_lines[1:])

def ub_get_html(body_only=True):
    '''Generate HTML string from the current buffer
    '''
    content = __ub_get_content()
    syntax = vim.eval('&syntax')
    enc = vim.eval('&encoding')
    html = ub_convert('html', syntax, True)

    if not body_only:
        html = \
'''<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN">
<html>
    <head>
       <meta http-equiv="Content-Type" content="text/html; charset=utf-8">
    </head>
    <body>
    %s
    </body>
</html>''' % html

    return html

def __ub_append_promotion_link(syntax='markdown'):
    '''Append a promotion link to the homepage of UltraBlog.vim
    '''
    doit = ub_get_option('ub_append_promotion_link')
    if doit is not None and doit.isdigit() and int(doit) == 1:
        if ub_is_view('post_edit') or ub_is_view('page_edit'):
            if syntax == 'markdown':
                link = 'Posted via [UltraBlog.vim](%s).' % cfg.homepage
            else:
                link = 'Posted via <a href="%s">UltraBlog.vim</a>.' % cfg.homepage
            vim.current.buffer.append(link)
        else:
            raise UBException('Invalid view !')

def __ub_get_categories():
    '''Fetch categories and format them into a string
    '''
    cats = api.metaWeblog.getCategories('', cfg.loginName, cfg.password)
    return ', '.join([cat['description'].encode('utf-8') for cat in cats])

def __ub_check_prerequesites():
    if cfg is None:
        raise UBException('No valid configurations found !')

    if sqlalchemy is None:
        raise UBException('SQLAlchemy v0.7 or newer is required !')

    if markdown is None:
        raise UBException('No module named markdown or markdown2 !')

def ub_get_post_meta_data():
    '''Get all meta data of the post and return a dict
    '''
    id = ub_get_meta('id')
    if id is None:
        id = 0
    post_id = ub_get_meta('post_id')
    if post_id is None:
        post_id = 0

    return dict(\
        id = id,
        post_id = post_id,
        title = ub_get_meta('title'),
        categories = ub_get_meta('categories'),
        tags = ub_get_meta('tags'),
        slug = ub_get_meta('slug'),
        status = ub_get_meta('status')
    )

def ub_get_page_meta_data():
    '''Get all meta data of the page and return a dict
    '''
    id = ub_get_meta('id')
    if id is None:
        id = 0
    post_id = ub_get_meta('post_id')
    if post_id is None:
        post_id = 0

    return dict(\
        id = id,
        post_id = post_id,
        title = ub_get_meta('title'),
        slug = ub_get_meta('slug'),
        status = ub_get_meta('status')
    )

def __ub_get_content():
    '''Generate content from the current buffer
    '''
    if ub_is_view('post_edit'):
        meta_dict = ub_get_post_meta_data()
    elif ub_is_view('page_edit'):
        meta_dict = ub_get_page_meta_data()
    else:
        return None

    content = "\n".join(vim.current.buffer[len(meta_dict)+2:])
    return content

def __ub_set_content(lines):
    '''Set the given lines to the content area of the current buffer
    '''
    if ub_is_view('post_edit'):
        meta_dict = ub_get_post_meta_data()
    elif ub_is_view('page_edit'):
        meta_dict = ub_get_page_meta_data()
    else:
        return False

    del vim.current.buffer[len(meta_dict)+2:]
    vim.current.buffer.append(lines, len(meta_dict)+2)
    return True

def __ub_convert_str(content, from_syntax, to_syntax, encoding=None):
    if from_syntax == to_syntax \
        or not ub_is_valid_syntax(from_syntax) \
        or not ub_is_valid_syntax(to_syntax):
        return content

    if from_syntax == 'markdown' and to_syntax == 'html':
        if encoding is not None:
            new_content = markdown.markdown(content.decode(encoding)).encode(encoding)
        else:
            new_content = markdown.markdown(content)
    else:
        cmd_parts = []
        cmd_parts.append(ub_get_option('ub_converter_command'))
        cmd_parts.extend(ub_get_option('ub_converter_options'))
        try:
            cmd_parts.append(ub_get_option('ub_converter_option_from') % from_syntax)
            cmd_parts.append(ub_get_option('ub_converter_option_to') % to_syntax)
        except TypeError:
            pass
        import subprocess
        p = subprocess.Popen(cmd_parts, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        new_content = p.communicate(content)[0].replace("\r\n", "\n")
    return new_content

class UBCommand(object):
    ''' Abstract parent class for all commands of UB
    '''
    def __init__(self):
        self.checkPrerequisites()
        # Set editor mode if the corresponding option has been set
        ub_set_mode()
        self.scope = 'local'
        self.itemType = None
        self.enc = vim.eval('&encoding')

    def checkPrerequisites(self):
        ''' Check the prerequisites
        '''
        if sqlalchemy is None: raise UBException('SQLAlchemy is missing !')
        if Base is None or Session is None or Post is None or Template is None:
            raise UBException('Cannot create database objects !')
        if cfg is None: raise UBException('Cannot get UB settings !')
        if api is None: raise UBException('Cannot init API !')
        if db is None: raise UBException('Cannot connect to database !')

    def checkItemType(self):
        ''' Check if the item type is among the available ones
        '''
        if not self.itemType in ['post', 'page', 'tmpl', None]:
            raise UBException('Unknow item type, available types are: post, page and tmpl !')

    def checkScope(self):
        '''Check the given scope,
        return True if it is local,
        return False if it is remote,
        raise an exception if it is neither of the upper two
        '''
        if self.scope=='local':
            return True
        elif self.scope=='remote':
            return False
        else:
            raise UBException('Invalid scope !')

    def execute(self):
        ''' The main functional method of this command
        '''
        self._preExec()
        self._exec()
        self._postExec()

    def _preExec(self):
        ''' Do something before self._exec()
        protected method, called by self.execute()
        '''
        self.checkItemType()
        self.checkScope()

    def _exec(self):
        ''' Do the main part of the job
        protected method, called by self.execute()
        '''
        raise UBException('Not implemented yet !')

    def _postExec(self):
        ''' Do something after self._exec()
        protected method, called by self.execute()
        '''
        pass

    @classmethod
    def doDefault(cls, *args, **kwargs):
        frame = inspect.currentframe(1)
        self = frame.f_locals["self"]
        methodName = frame.f_code.co_name
        
        method = getattr(super(cls, self), methodName, None)
        
        if inspect.ismethod(method):
            return method(*args, **kwargs)

class UBCmdList(UBCommand):
    ''' Listing command, implements UBCommand
    '''
    def __init__(self, itemType='post', scope='local', pageSize=None, pageNo=None):
        UBCommand.__init__(self)
        self.itemType = itemType
        self.scope = scope
        self.pageSize = pageSize
        if self.pageSize is None:
            self.pageSize = int(ub_get_option("ub_%s_pagesize" % self.scope))
        self.pageSize = int(self.pageSize)
        self.pageNo = pageNo
        if self.pageNo is None:
            self.pageNo = 1
        self.pageNo = int(self.pageNo)

    def _preExec(self):
        UBCmdList.doDefault()
        # Check self.pageNo
        self.pageNo = int(self.pageNo)
        if self.pageNo<1:
            raise UBException('Page NO. cannot be less than 1 !')
        # Check self.pageSize
        self.pageSize = int(self.pageSize)
        if self.pageSize<1:
            raise UBException('Illegal page size (%s) !' % self.pageSize)

    def _exec(self):
        if self.itemType=='tmpl': self._listTemplates()
        else: eval("self._list%s%ss()" % (self.scope.capitalize(), self.itemType.capitalize()))

    def _listLocalPosts(self):
        '''List local posts stored in database
        '''
        posts = []

        tbl = Post.__table__
        ua = union_all(
            select([select([tbl.c.id,case([(tbl.c.post_id>0, tbl.c.post_id)], else_=0).label('post_id'),tbl.c.status,tbl.c.title])\
                .where(tbl.c.post_id==None).where(tbl.c.type=='post').order_by(tbl.c.id.desc())]),
            select([select([tbl.c.id,case([(tbl.c.post_id>0, tbl.c.post_id)], else_=0).label('post_id'),tbl.c.status,tbl.c.title])\
                .where(tbl.c.post_id!=None).where(tbl.c.type=='post').order_by(tbl.c.post_id.desc())])
        )
        stmt = select([ua]).limit(self.pageSize).offset(self.pageSize*(self.pageNo-1))

        conn = db.connect()
        rslt = conn.execute(stmt)
        while True:
            row = rslt.fetchone()
            if row is not None:
                posts.append(row)
            else:
                break
        conn.close()

        if len(posts)==0: raise UBException('No more posts found !')

        ub_wise_open_view('local_post_list')
        vim.current.buffer[0] = "==================== Posts (Page %d) ====================" % self.pageNo
        tmpl = ub_get_list_template()
        vim.current.buffer.append([(tmpl % (post.id,post.post_id,post.status,post.title)).encode(self.enc) for post in posts])

        vim.command("let b:page_no=%s" % self.pageNo)
        vim.command("let b:page_size=%s" % self.pageSize)
        vim.command("map <buffer> "+ub_get_option('ub_hotkey_open_item_in_current_view')+" :py __ub_list_open_item('cur')<cr>")
        vim.command("map <buffer> "+ub_get_option('ub_hotkey_open_item_in_splitted_view')+" :py __ub_list_open_item('split')<cr>")
        vim.command("map <buffer> "+ub_get_option('ub_hotkey_open_item_in_tabbed_view')+" :py __ub_list_open_item('tab')<cr>")
        vim.command("map <buffer> "+ub_get_option('ub_hotkey_delete_item')+" :py __ub_list_del_item()<cr>")
        vim.command("map <buffer> "+ub_get_option('ub_hotkey_pagedown')+" :py ub_list_items('post', 'local', %d, %d)<cr>" % (self.pageSize, self.pageNo+1))
        vim.command("map <buffer> "+ub_get_option('ub_hotkey_pageup')+" :py ub_list_items('post', 'local', %d, %d)<cr>" % (self.pageSize, self.pageNo-1))
        vim.command('call UBClearUndo()')
        vim.command('setl nomodified')
        vim.command("setl nomodifiable")
        vim.current.window.cursor = (2, 0)

    def _listRemotePosts(self):
        '''List remote posts stored in the blog
        '''
        global cfg, api

        posts = api.metaWeblog.getRecentPosts('', cfg.loginName, cfg.password, self.pageSize)
        sess = Session()
        for post in posts:
            local_post = sess.query(Post).filter(Post.post_id==post['postid']).first()
            if local_post is None:
                post['id'] = 0
            else:
                post['id'] = local_post.id
                post['post_status'] = local_post.status
        sess.close()

        ub_wise_open_view('remote_post_list')
        vim.current.buffer[0] = "==================== Recent Posts ===================="
        tmpl = ub_get_list_template()
        vim.current.buffer.append([(tmpl % (post['id'],post['postid'],post['post_status'],post['title'])).encode(self.enc) for post in posts])

        vim.command("let b:page_size=%s" % self.pageSize)
        vim.command("map <buffer> "+ub_get_option('ub_hotkey_open_item_in_current_view')+" :py __ub_list_open_item('cur')<cr>")
        vim.command("map <buffer> "+ub_get_option('ub_hotkey_open_item_in_splitted_view')+" :py __ub_list_open_item('split')<cr>")
        vim.command("map <buffer> "+ub_get_option('ub_hotkey_open_item_in_tabbed_view')+" :py __ub_list_open_item('tab')<cr>")
        vim.command("map <buffer> "+ub_get_option('ub_hotkey_delete_item')+" :py __ub_list_del_item()<cr>")
        vim.command('call UBClearUndo()')
        vim.command('setl nomodified')
        vim.command("setl nomodifiable")
        vim.current.window.cursor = (2, 0)

    def _listLocalPages(self):
        '''List local pages stored in database
        '''
        pages = []

        tbl = Post.__table__
        ua = union_all(
            select([select([tbl.c.id,case([(tbl.c.post_id>0, tbl.c.post_id)], else_=0).label('post_id'),tbl.c.status,tbl.c.title])\
                .where(tbl.c.post_id==None).where(tbl.c.type=='page').order_by(tbl.c.id.desc())]),
            select([select([tbl.c.id,case([(tbl.c.post_id>0, tbl.c.post_id)], else_=0).label('post_id'),tbl.c.status,tbl.c.title])\
                .where(tbl.c.post_id!=None).where(tbl.c.type=='page').order_by(tbl.c.post_id.desc())])
        )

        conn = db.connect()
        rslt = conn.execute(ua)
        while True:
            row = rslt.fetchone()
            if row is not None:
                pages.append(row)
            else:
                break
        conn.close()

        if len(pages)==0: raise UBException('No more pages found !')

        ub_wise_open_view('local_page_list')
        vim.current.buffer[0] = "==================== Local Pages ===================="
        tmpl = ub_get_list_template()
        vim.current.buffer.append([(tmpl % (page.id,page.post_id,page.status,page.title)).encode(self.enc) for page in pages])

        vim.command("map <buffer> "+ub_get_option('ub_hotkey_open_item_in_current_view')+" :py __ub_list_open_item('cur')<cr>")
        vim.command("map <buffer> "+ub_get_option('ub_hotkey_open_item_in_splitted_view')+" :py __ub_list_open_item('split')<cr>")
        vim.command("map <buffer> "+ub_get_option('ub_hotkey_open_item_in_tabbed_view')+" :py __ub_list_open_item('tab')<cr>")
        vim.command("map <buffer> "+ub_get_option('ub_hotkey_delete_item')+" :py __ub_list_del_item()<cr>")
        vim.command('call UBClearUndo()')
        vim.command('setl nomodified')
        vim.command("setl nomodifiable")
        vim.current.window.cursor = (2, 0)

    def _listRemotePages(self):
        '''List remote pages stored in the blog
        '''
        global cfg, api

        sess = Session()
        pages = api.wp.getPages('', cfg.loginName, cfg.password)
        for page in pages:
            local_page = sess.query(Post).filter(Post.post_id==page['page_id']).filter(Post.type=='page').first()
            if local_page is None:
                page['id'] = 0
            else:
                page['id'] = local_page.id
                page['page_status'] = local_page.status
        sess.close()

        ub_wise_open_view('remote_page_list')
        vim.current.buffer[0] = "==================== Blog Pages ===================="
        tmpl = ub_get_list_template()
        vim.current.buffer.append([(tmpl % (page['id'],page['page_id'],page['page_status'],page['title'])).encode(self.enc) for page in pages])

        vim.command("map <buffer> "+ub_get_option('ub_hotkey_open_item_in_current_view')+" :py __ub_list_open_item('cur')<cr>")
        vim.command("map <buffer> "+ub_get_option('ub_hotkey_open_item_in_splitted_view')+" :py __ub_list_open_item('split')<cr>")
        vim.command("map <buffer> "+ub_get_option('ub_hotkey_open_item_in_tabbed_view')+" :py __ub_list_open_item('tab')<cr>")
        vim.command("map <buffer> "+ub_get_option('ub_hotkey_delete_item')+" :py __ub_list_del_item()<cr>")
        vim.command('call UBClearUndo()')
        vim.command('setl nomodified')
        vim.command("setl nomodifiable")
        vim.current.window.cursor = (2, 0)

    def _listTemplates(self):
        '''List preview templates
        '''
        sess = Session()

        tmpls = sess.query(Template).all()

        if len(tmpls)==0:
            sys.stderr.write('No template found !')
            return

        ub_wise_open_view('local_tmpl_list')
        vim.current.buffer[0] = "==================== Templates ===================="
        line = "%-24s%s"
        vim.current.buffer.append([(line % (tmpl.name,tmpl.description)).encode(self.enc) for tmpl in tmpls])

        vim.command("map <buffer> "+ub_get_option('ub_hotkey_open_item_in_current_view')+" :py __ub_list_open_item('cur')<cr>")
        vim.command("map <buffer> "+ub_get_option('ub_hotkey_open_item_in_splitted_view')+" :py __ub_list_open_item('split')<cr>")
        vim.command("map <buffer> "+ub_get_option('ub_hotkey_open_item_in_tabbed_view')+" :py __ub_list_open_item('tab')<cr>")
        vim.command("map <buffer> "+ub_get_option('ub_hotkey_delete_item')+" :py __ub_list_del_item()<cr>")
        vim.command('call UBClearUndo()')
        vim.command('setl nomodified')
        vim.command("setl nomodifiable")
        vim.current.window.cursor = (2, 0)

class UBCmdFind(UBCommand):
    ''' Context search
    '''
    def __init__(self, pageNo, *keywords):
        UBCommand.__init__(self)
        self.pageSize = int(ub_get_option("ub_%s_pagesize" % self.scope))
        self.pageNo = pageNo
        if self.pageNo is None:
            self.pageNo = 1
        self.pageNo = int(self.pageNo)
        self.keywords = keywords

    def _preExec(self):
        UBCmdFind.doDefault()
        # Check self.pageNo
        self.pageNo = int(self.pageNo)
        if self.pageNo<1:
            raise UBException('Page NO. cannot be less than 1 !')
        # Check self.pageSize
        self.pageSize = int(self.pageSize)
        if self.pageSize<1:
            raise UBException('Illegal page size (%s) !' % self.pageSize)

    def _exec(self):
        posts = []
        tbl = Post.__table__

        conds = []
        for keyword in self.keywords:
            kwcond = []
            kwcond.append(tbl.c.title.like('%%%s%%' % keyword.decode(self.enc)))
            kwcond.append(tbl.c.content.like('%%%s%%' % keyword.decode(self.enc)))
            conds.append(or_(*kwcond))

        stmt = select([tbl.c.id,case([(tbl.c.post_id>0, tbl.c.post_id)], else_=0).label('post_id'),tbl.c.status,tbl.c.title],
            and_(*conds)
        ).limit(self.pageSize).offset(self.pageSize*(self.pageNo-1)).order_by(tbl.c.status.asc(),tbl.c.post_id.desc())

        conn = db.connect()
        rslt = conn.execute(stmt)
        while True:
            row = rslt.fetchone()
            if row is not None:
                posts.append(row)
            else:
                break
        conn.close()

        if len(posts)==0: raise UBException('No more posts found !')

        ub_wise_open_view('search_result_list')
        vim.current.buffer[0] = "==================== Results (Page %d) ====================" % self.pageNo
        tmpl = ub_get_list_template()
        vim.current.buffer.append([(tmpl % (post.id,post.post_id,post.status,post.title)).encode(self.enc) for post in posts])

        vim.command("let b:page_no=%s" % self.pageNo)
        vim.command("let b:page_size=%s" % self.pageSize)
        vim.command("let b:ub_keywords=[%s]" % ','.join(["'%s'" % kw for kw in self.keywords]))
        vim.command("map <buffer> "+ub_get_option('ub_hotkey_open_item_in_current_view')+" :py __ub_list_open_item('cur')<cr>")
        vim.command("map <buffer> "+ub_get_option('ub_hotkey_open_item_in_splitted_view')+" :py __ub_list_open_item('split')<cr>")
        vim.command("map <buffer> "+ub_get_option('ub_hotkey_open_item_in_tabbed_view')+" :py __ub_list_open_item('tab')<cr>")
        vim.command("map <buffer> "+ub_get_option('ub_hotkey_delete_item')+" :py __ub_list_del_item()<cr>")
        vim.command("map <buffer> "+ub_get_option('ub_hotkey_pagedown')+" :py ub_find(%d,%s)<cr>" % (self.pageNo+1, ','.join(["'%s'" % kw for kw in self.keywords])))
        vim.command("map <buffer> "+ub_get_option('ub_hotkey_pageup')+" :py ub_find(%d,%s)<cr>" % (self.pageNo-1, ','.join(["'%s'" % kw for kw in self.keywords])))
        vim.command('call UBClearUndo()')
        vim.command('setl nomodified')
        vim.command("setl nomodifiable")
        vim.current.window.cursor = (2, 0)
        vim.command("let @/='\\(%s\\)'" % '\\|'.join(self.keywords))
        vim.command('setl hls')

class UBCmdSave(UBCommand):
    ''' Save items
    '''
    def __init__(self):
        UBCommand.__init__(self)
        self.syntax = vim.eval('&syntax')
        self.sess = Session()
        self.viewName = ub_get_viewname('%')
        self.item = None
        self.itemKey = None
        self.itemType = self.viewName.split('_')[0]
        if self.itemType in ['post', 'page']: self.metaDict = eval("ub_get_%s_meta_data()" % self.itemType)
        else: self.metaDict = None

    def _preExec(self):
        UBCmdSave.doDefault()
        # Do not bother if the current buffer is not modified
        if vim.eval('&modified')=='0': raise UBException('This buffer has not been modified !')
        if self.viewName not in ['post_edit', 'page_edit', 'tmpl_edit']: raise UBException('Invalid view !')

    def _exec(self):
        if self.itemType=='post': self.__loadPost()
        elif self.itemType=='page': self.__loadPage()
        else: self.__loadTmpl()

    def _postExec(self):
        UBCmdSave.doDefault()

        self.sess.add(self.item)
        self.sess.commit()
        if self.itemType == 'tmpl':
            self.itemKey = name
        else:
            self.itemKey = self.item.id
            self.metaDict['id'] = self.itemKey
            ub_fill_meta_data(self.metaDict)
        self.sess.close()

        vim.command('setl nomodified')
        
        evt = eval("UB%sSaveEvent('%s')" % (self.itemType.capitalize(), self.itemKey));
        UBEventQueue.fireEvent(evt)
        UBEventQueue.processEvents()

    def __loadTmpl(self):
        '''Save the current template to local database
        '''
        name = ub_get_meta('name').decode(self.enc)

        # Check if the given name is a reserved word
        ub_check_reserved_word(name)

        tmpl = self.sess.query(Template).filter(Template.name==name).first()
        if tmpl is None:
            tmpl = Template()
            tmpl.name = name

        tmpl.description = ub_get_meta('description').decode(self.enc)
        tmpl.content = "\n".join(vim.current.buffer[4:]).decode(self.enc)

        self.item = tmpl

    def __loadPost(self):
        '''Save the current buffer to local database
        '''

        id = ub_get_meta('id')
        post_id = ub_get_meta('post_id')
        if id is None:
            post = Post()
        else:
            post = self.sess.query(Post).filter(Post.id==id).first()

        meta_dict = ub_get_post_meta_data()
        post.content = "\n".join(vim.current.buffer[len(meta_dict)+2:]).decode(self.enc)
        post.post_id = post_id
        post.title = ub_get_meta('title').decode(self.enc)
        post.categories = ub_get_meta('categories').decode(self.enc)
        post.tags = ub_get_meta('tags').decode(self.enc)
        post.slug = ub_get_meta('slug').decode(self.enc)
        post.status = ub_get_meta('status').decode(self.enc)
        post.syntax = self.syntax

        self.item = post

    def __loadPage(self):
        '''Save the current page to local database
        '''
        id = ub_get_meta('id')
        post_id = ub_get_meta('post_id')
        if id is None:
            page = Post()
            page.type = 'page'
        else:
            page = self.sess.query(Post).filter(Post.id==id).filter(Post.type=='page').first()

        meta_dict = ub_get_page_meta_data()
        page.content = "\n".join(vim.current.buffer[len(meta_dict)+2:]).decode(self.enc)
        page.post_id = post_id
        page.title = ub_get_meta('title').decode(self.enc)
        page.slug = ub_get_meta('slug').decode(self.enc)
        page.status = ub_get_meta('status').decode(self.enc)
        page.syntax = self.syntax

        self.item = page

class UBCmdSend(UBCommand):
    ''' Send item
    '''
    def __init__(self, status=None):
        UBCommand.__init__(self)
        self.status = status
        if self.status is None:
            self.status = ub_get_meta('status')
        self.publish = ub_check_status(self.status)
        self.viewName = ub_get_viewname('%')
        self.itemType = self.viewName.split('_')[0]
        self.item = None

    def _preExec(self):
        UBCmdSend.doDefault()
        if self.viewName not in ['post_edit', 'page_edit', 'tmpl_edit']: raise UBException('Invalid view !')

    def _exec(self):
        if self.itemType=='post': self.__loadPost()
        else: self.__loadPage()

    def _postExec(self):
        post_id = ub_get_meta('post_id')
        if post_id is None:
            post_id = api.metaWeblog.newPost('', cfg.loginName, cfg.password, self.item, self.publish)
            msg = "%s sent as %s !" % (self.itemType.capitalize(), self.status)
        else:
            api.metaWeblog.editPost(post_id, cfg.loginName, cfg.password, self.item, self.publish)
            msg = "%s sent as %s !" % (self.itemType.capitalize(), self.status)
        sys.stdout.write(msg)

        evt = eval("UB%sSendEvent(%s)" % (self.itemType.capitalize(), post_id))
        UBEventQueue.fireEvent(evt)

        if post_id != ub_get_meta('post_id'):
            ub_set_meta('post_id', post_id)
        if self.status != ub_get_meta('status'):
            ub_set_meta('status', self.status)

        saveit = ub_get_option('ub_save_after_sent')
        if saveit is not None and saveit.isdigit() and int(saveit) == 1:
            ub_save_item()
        
        UBEventQueue.processEvents()

    def __loadPost(self):
        '''Send the current buffer to the blog
        '''
        self.item = dict(\
            title = ub_get_meta('title'),
            description = ub_get_html(),
            categories = [cat.strip() for cat in ub_get_meta('categories').split(',')],
            mt_keywords = ub_get_meta('tags'),
            wp_slug = ub_get_meta('slug'),
            post_type = 'post',
            post_status = self.status
        )

    def __loadPage(self):
        '''Send the current page to the blog
        '''
        self.item = dict(\
            title = ub_get_meta('title'),
            description = ub_get_html(),
            wp_slug = ub_get_meta('slug'),
            post_type = 'page',
            page_status = self.status
        )

def ub_get_templates(name_only=False):
    ''' Fetch and return a list of templates
    '''
    # Check prerequesites
    __ub_check_prerequesites()

    # Set editor mode if the corresponding option has been set
    ub_set_mode()

    enc = vim.eval('&encoding')

    sess = Session()
    tmpls = sess.query(Template).all()
    sess.close()

    if name_only is True:
        tmpls = [tmpl.name.encode(enc) for tmpl in tmpls]

    return tmpls

