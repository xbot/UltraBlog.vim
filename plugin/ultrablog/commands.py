#!/usr/bin/env python

import vim, xmlrpclib, webbrowser, sys, re, tempfile, os, mimetypes
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
def ub_find(page_no, *keywords):
    ''' List posts/pages which match the keywords given
    '''
    # Check prerequesites
    __ub_check_prerequesites()

    # Set editor mode if the corresponding option has been set
    ub_set_mode()

    page_size = int(ub_get_option('ub_search_pagesize'))
    page_no = int(page_no)

    if page_no<1 or page_size<1:
        return

    posts = []
    tbl = Post.__table__
    enc = vim.eval('&encoding')

    conds = []
    for keyword in keywords:
        kwcond = []
        kwcond.append(tbl.c.title.like('%%%s%%' % keyword.decode(enc)))
        kwcond.append(tbl.c.content.like('%%%s%%' % keyword.decode(enc)))
        conds.append(or_(*kwcond))

    stmt = select([tbl.c.id,case([(tbl.c.post_id>0, tbl.c.post_id)], else_=0).label('post_id'),tbl.c.status,tbl.c.title],
        and_(*conds)
    ).limit(page_size).offset(page_size*(page_no-1)).order_by(tbl.c.status.asc(),tbl.c.post_id.desc())

    conn = db.connect()
    rslt = conn.execute(stmt)
    while True:
        row = rslt.fetchone()
        if row is not None:
            posts.append(row)
        else:
            break
    conn.close()

    if len(posts)==0:
        sys.stderr.write('No more posts found !')
        return

    ub_wise_open_view('search_result_list')
    vim.current.buffer[0] = "==================== Results (Page %d) ====================" % page_no
    tmpl = ub_get_list_template()
    vim.current.buffer.append([(tmpl % (post.id,post.post_id,post.status,post.title)).encode(enc) for post in posts])

    vim.command("let b:page_no=%s" % page_no)
    vim.command("let b:page_size=%s" % page_size)
    vim.command("let b:ub_keywords=[%s]" % ','.join(["'%s'" % kw for kw in keywords]))
    vim.command("map <buffer> "+ub_get_option('ub_hotkey_open_item_in_current_view')+" :py __ub_list_open_item('cur')<cr>")
    vim.command("map <buffer> "+ub_get_option('ub_hotkey_open_item_in_splitted_view')+" :py __ub_list_open_item('split')<cr>")
    vim.command("map <buffer> "+ub_get_option('ub_hotkey_open_item_in_tabbed_view')+" :py __ub_list_open_item('tab')<cr>")
    vim.command("map <buffer> "+ub_get_option('ub_hotkey_delete_item')+" :py __ub_list_del_item()<cr>")
    vim.command("map <buffer> "+ub_get_option('ub_hotkey_pagedown')+" :py ub_find(%d,%s)<cr>" % (page_no+1, ','.join(["'%s'" % kw for kw in keywords])))
    vim.command("map <buffer> "+ub_get_option('ub_hotkey_pageup')+" :py ub_find(%d,%s)<cr>" % (page_no-1, ','.join(["'%s'" % kw for kw in keywords])))
    vim.command('call UBClearUndo()')
    vim.command('setl nomodified')
    vim.command("setl nomodifiable")
    vim.current.window.cursor = (2, 0)
    vim.command("let @/='\\(%s\\)'" % '\\|'.join(keywords))
    vim.command('setl hls')

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
        draft['content'] = __ub_get_html()

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
    if ub_is_view('post_edit'):
        ub_save_post()
    elif ub_is_view('page_edit'):
        ub_save_page()
    elif ub_is_view('tmpl_edit'):
        ub_save_template()
    else:
        raise UBException('Invalid view !')

def ub_save_template():
    '''Save the current template to local database
    '''
    # Check prerequesites
    __ub_check_prerequesites()

    # This function is valid only in 'tmpl_edit' buffers
    if not ub_is_view('tmpl_edit'):
        raise UBException('Invalid view !')

    # Do not bother if the current buffer is not modified
    if vim.eval('&modified')=='0':
        return

    # Set editor mode if the corresponding option has been set
    ub_set_mode()

    sess = Session()
    enc = vim.eval('&encoding')
    syntax = vim.eval('&syntax')
    name = ub_get_meta('name').decode(enc)

    # Check if the given name is a reserved word
    ub_check_reserved_word(name)

    tmpl = sess.query(Template).filter(Template.name==name).first()
    if tmpl is None:
        tmpl = Template()
        tmpl.name = name

    tmpl.description = ub_get_meta('description').decode(enc)
    tmpl.content = "\n".join(vim.current.buffer[4:]).decode(enc)

    sess.add(tmpl)
    sess.commit()
    sess.close()

    vim.command('setl nomodified')
    
    UBEventQueue.fireEvent(UBTmplSaveEvent(name))
    UBEventQueue.processEvents()

def ub_save_post():
    '''Save the current buffer to local database
    '''
    # Check prerequesites
    __ub_check_prerequesites()

    # This function is valid only in 'post_edit' buffers
    if not ub_is_view('post_edit'):
        raise UBException('Invalid view !')

    # Do not bother if the current buffer is not modified
    if vim.eval('&modified')=='0':
        return

    # Set editor mode if the corresponding option has been set
    ub_set_mode()

    sess = Session()
    enc = vim.eval('&encoding')
    syntax = vim.eval('&syntax')

    id = ub_get_meta('id')
    post_id = ub_get_meta('post_id')
    if id is None:
        post = Post()
    else:
        post = sess.query(Post).filter(Post.id==id).first()

    meta_dict = __ub_get_post_meta_data()
    post.content = "\n".join(vim.current.buffer[len(meta_dict)+2:]).decode(enc)
    post.post_id = post_id
    post.title = ub_get_meta('title').decode(enc)
    post.categories = ub_get_meta('categories').decode(enc)
    post.tags = ub_get_meta('tags').decode(enc)
    post.slug = ub_get_meta('slug').decode(enc)
    post.status = ub_get_meta('status').decode(enc)
    post.syntax = syntax
    sess.add(post)
    sess.commit()
    meta_dict['id'] = post.id
    sess.close()

    __ub_fill_meta_data(meta_dict)

    vim.command('setl nomodified')
    
    UBEventQueue.fireEvent(UBPostSaveEvent(post.id))
    UBEventQueue.processEvents()

def ub_save_page():
    '''Save the current page to local database
    '''
    # Check prerequesites
    __ub_check_prerequesites()

    # This function is valid only in 'page_edit' buffers
    if not ub_is_view('page_edit'):
        raise UBException('Invalid view !')

    # Do not bother if the current buffer is not modified
    if vim.eval('&modified')=='0':
        return

    # Set editor mode if the corresponding option has been set
    ub_set_mode()

    sess = Session()
    enc = vim.eval('&encoding')
    syntax = vim.eval('&syntax')

    id = ub_get_meta('id')
    post_id = ub_get_meta('post_id')
    if id is None:
        page = Post()
        page.type = 'page'
    else:
        page = sess.query(Post).filter(Post.id==id).filter(Post.type=='page').first()

    meta_dict = __ub_get_page_meta_data()
    page.content = "\n".join(vim.current.buffer[len(meta_dict)+2:]).decode(enc)
    page.post_id = post_id
    page.title = ub_get_meta('title').decode(enc)
    page.slug = ub_get_meta('slug').decode(enc)
    page.status = ub_get_meta('status').decode(enc)
    page.syntax = syntax
    sess.add(page)
    sess.commit()
    meta_dict['id'] = page.id
    sess.close()

    __ub_fill_meta_data(meta_dict)

    vim.command('setl nomodified')
    
    UBEventQueue.fireEvent(UBPostSaveEvent(page.id))
    UBEventQueue.processEvents()

@__ub_exception_handler
def ub_send_item(status=None):
    '''Send the current item to the blog
    '''
    if ub_is_view('post_edit'):
        ub_send_post(status)
    elif ub_is_view('page_edit'):
        ub_send_page(status)
    else:
        raise UBException('Invalid view !')

@__ub_exception_handler
def ub_send_post(status=None):
    '''Send the current buffer to the blog
    '''
    # Check prerequesites
    __ub_check_prerequesites()

    # This function is valid only in 'post_edit' buffers
    if not ub_is_view('post_edit'):
        raise UBException('Invalid view !')

    # Set editor mode if the corresponding option has been set
    ub_set_mode()

    # Check parameter
    if status is None:
        status = ub_get_meta('status')
    publish = ub_check_status(status)

    post = dict(\
        title = ub_get_meta('title'),
        description = __ub_get_html(),
        categories = [cat.strip() for cat in ub_get_meta('categories').split(',')],
        mt_keywords = ub_get_meta('tags'),
        wp_slug = ub_get_meta('slug'),
        post_type = 'post',
        post_status = status
    )

    post_id = ub_get_meta('post_id')
    if post_id is None:
        post_id = api.metaWeblog.newPost('', cfg.loginName, cfg.password, post, publish)
        msg = "Post sent as %s !" % status
    else:
        api.metaWeblog.editPost(post_id, cfg.loginName, cfg.password, post, publish)
        msg = "Post sent as %s !" % status
    sys.stdout.write(msg)

    UBEventQueue.fireEvent(UBPostSendEvent(post_id))

    if post_id != ub_get_meta('post_id'):
        ub_set_meta('post_id', post_id)
    if status != ub_get_meta('status'):
        ub_set_meta('status', status)

    saveit = ub_get_option('ub_save_after_sent')
    if saveit is not None and saveit.isdigit() and int(saveit) == 1:
        ub_save_post()
    
    UBEventQueue.processEvents()

@__ub_exception_handler
def ub_send_page(status=None):
    '''Send the current page to the blog
    '''
    # Check prerequesites
    __ub_check_prerequesites()

    # This function is valid only in 'page_edit' buffers
    if not ub_is_view('page_edit'):
        raise UBException('Invalid view !')

    # Set editor mode if the corresponding option has been set
    ub_set_mode()

    # Check parameter
    if status is None:
        status = ub_get_meta('status')
    publish = ub_check_status(status)

    global cfg, api

    page = dict(\
        title = ub_get_meta('title'),
        description = __ub_get_html(),
        wp_slug = ub_get_meta('slug'),
        post_type = 'page',
        page_status = status
    )

    post_id = ub_get_meta('post_id')
    if post_id is None:
        post_id = api.metaWeblog.newPost('', cfg.loginName, cfg.password, page, publish)
        msg = "Page sent as %s !" % status
    else:
        api.metaWeblog.editPost(post_id, cfg.loginName, cfg.password, page, publish)
        msg = "Page sent as %s !" % status
    sys.stdout.write(msg)

    UBEventQueue.fireEvent(UBPostSendEvent(post_id))

    if post_id != ub_get_meta('post_id'):
        ub_set_meta('post_id', post_id)
    if status != ub_get_meta('status'):
        ub_set_meta('status', status)

    saveit = ub_get_option('ub_save_after_sent')
    if saveit is not None and saveit.isdigit() and int(saveit) == 1:
        ub_save_page()
    
    UBEventQueue.processEvents()

@__ub_exception_handler
def ub_list_items(item_type='post', scope='local', page_size=None, page_no=None):
    ub_check_item_type(item_type)

    if item_type=='tmpl':
        ub_list_templates()
        return

    ub_check_scope(scope)

    if page_size is None:
        page_size = ub_get_option("ub_%s_pagesize" % scope)
    page_size = int(page_size)
    if page_no is None:
        page_no = 1
    page_no = int(page_no)
    if page_no<1 or page_size<1:
        return

    if item_type=='post':
        if scope=='local':
            ub_list_local_posts(page_no, page_size)
        else:
            ub_list_remote_posts(page_size)
    else:
        eval("ub_list_%s_pages()" % scope)

@__ub_exception_handler
def ub_list_local_posts(page_no=1, page_size=None):
    '''List local posts stored in database
    '''
    # Check prerequesites
    __ub_check_prerequesites()

    if page_size is None:
        page_size = ub_get_option('ub_local_pagesize')
    page_size = int(page_size)
    page_no = int(page_no)
    if page_no<1 or page_size<1:
        return

    # Set editor mode if the corresponding option has been set
    ub_set_mode()

    posts = []

    tbl = Post.__table__
    ua = union_all(
        select([select([tbl.c.id,case([(tbl.c.post_id>0, tbl.c.post_id)], else_=0).label('post_id'),tbl.c.status,tbl.c.title])\
            .where(tbl.c.post_id==None).where(tbl.c.type=='post').order_by(tbl.c.id.desc())]),
        select([select([tbl.c.id,case([(tbl.c.post_id>0, tbl.c.post_id)], else_=0).label('post_id'),tbl.c.status,tbl.c.title])\
            .where(tbl.c.post_id!=None).where(tbl.c.type=='post').order_by(tbl.c.post_id.desc())])
    )
    stmt = select([ua]).limit(page_size).offset(page_size*(page_no-1))

    conn = db.connect()
    rslt = conn.execute(stmt)
    while True:
        row = rslt.fetchone()
        if row is not None:
            posts.append(row)
        else:
            break
    conn.close()

    if len(posts)==0:
        sys.stderr.write('No more posts found !')
        return

    ub_wise_open_view('local_post_list')
    enc = vim.eval('&encoding')
    vim.current.buffer[0] = "==================== Posts (Page %d) ====================" % page_no
    tmpl = ub_get_list_template()
    vim.current.buffer.append([(tmpl % (post.id,post.post_id,post.status,post.title)).encode(enc) for post in posts])

    vim.command("let b:page_no=%s" % page_no)
    vim.command("let b:page_size=%s" % page_size)
    vim.command("map <buffer> "+ub_get_option('ub_hotkey_open_item_in_current_view')+" :py __ub_list_open_item('cur')<cr>")
    vim.command("map <buffer> "+ub_get_option('ub_hotkey_open_item_in_splitted_view')+" :py __ub_list_open_item('split')<cr>")
    vim.command("map <buffer> "+ub_get_option('ub_hotkey_open_item_in_tabbed_view')+" :py __ub_list_open_item('tab')<cr>")
    vim.command("map <buffer> "+ub_get_option('ub_hotkey_delete_item')+" :py __ub_list_del_item()<cr>")
    vim.command("map <buffer> "+ub_get_option('ub_hotkey_pagedown')+" :py ub_list_local_posts(%d,%d)<cr>" % (page_no+1,page_size))
    vim.command("map <buffer> "+ub_get_option('ub_hotkey_pageup')+" :py ub_list_local_posts(%d,%d)<cr>" % (page_no-1,page_size))
    vim.command('call UBClearUndo()')
    vim.command('setl nomodified')
    vim.command("setl nomodifiable")
    vim.current.window.cursor = (2, 0)

@__ub_exception_handler
def ub_list_local_pages():
    '''List local pages stored in database
    '''
    # Check prerequesites
    __ub_check_prerequesites()

    # Set editor mode if the corresponding option has been set
    ub_set_mode()

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

    if len(pages)==0:
        sys.stderr.write('No more pages found !')
        return

    ub_wise_open_view('local_page_list')
    enc = vim.eval('&encoding')
    vim.current.buffer[0] = "==================== Local Pages ===================="
    tmpl = ub_get_list_template()
    vim.current.buffer.append([(tmpl % (page.id,page.post_id,page.status,page.title)).encode(enc) for page in pages])

    vim.command("map <buffer> "+ub_get_option('ub_hotkey_open_item_in_current_view')+" :py __ub_list_open_item('cur')<cr>")
    vim.command("map <buffer> "+ub_get_option('ub_hotkey_open_item_in_splitted_view')+" :py __ub_list_open_item('split')<cr>")
    vim.command("map <buffer> "+ub_get_option('ub_hotkey_open_item_in_tabbed_view')+" :py __ub_list_open_item('tab')<cr>")
    vim.command("map <buffer> "+ub_get_option('ub_hotkey_delete_item')+" :py __ub_list_del_item()<cr>")
    vim.command('call UBClearUndo()')
    vim.command('setl nomodified')
    vim.command("setl nomodifiable")
    vim.current.window.cursor = (2, 0)

@__ub_exception_handler
def ub_list_remote_posts(page_size=None):
    '''List remote posts stored in the blog
    '''
    # Check prerequesites
    __ub_check_prerequesites()

    # Set editor mode if the corresponding option has been set
    ub_set_mode()

    if page_size is None:
        page_size = ub_get_option('ub_remote_pagesize')
    page_size = int(page_size)
    if page_size<1:
        return

    global cfg, api

    posts = api.metaWeblog.getRecentPosts('', cfg.loginName, cfg.password, page_size)
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
    enc = vim.eval('&encoding')
    vim.current.buffer[0] = "==================== Recent Posts ===================="
    tmpl = ub_get_list_template()
    vim.current.buffer.append([(tmpl % (post['id'],post['postid'],post['post_status'],post['title'])).encode(enc) for post in posts])

    vim.command("let b:page_size=%s" % page_size)
    vim.command("map <buffer> "+ub_get_option('ub_hotkey_open_item_in_current_view')+" :py __ub_list_open_item('cur')<cr>")
    vim.command("map <buffer> "+ub_get_option('ub_hotkey_open_item_in_splitted_view')+" :py __ub_list_open_item('split')<cr>")
    vim.command("map <buffer> "+ub_get_option('ub_hotkey_open_item_in_tabbed_view')+" :py __ub_list_open_item('tab')<cr>")
    vim.command("map <buffer> "+ub_get_option('ub_hotkey_delete_item')+" :py __ub_list_del_item()<cr>")
    vim.command('call UBClearUndo()')
    vim.command('setl nomodified')
    vim.command("setl nomodifiable")
    vim.current.window.cursor = (2, 0)

@__ub_exception_handler
def ub_list_remote_pages():
    '''List remote pages stored in the blog
    '''
    # Check prerequesites
    __ub_check_prerequesites()

    # Set editor mode if the corresponding option has been set
    ub_set_mode()

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
    enc = vim.eval('&encoding')
    vim.current.buffer[0] = "==================== Blog Pages ===================="
    tmpl = ub_get_list_template()
    vim.current.buffer.append([(tmpl % (page['id'],page['page_id'],page['page_status'],page['title'])).encode(enc) for page in pages])

    vim.command("map <buffer> "+ub_get_option('ub_hotkey_open_item_in_current_view')+" :py __ub_list_open_item('cur')<cr>")
    vim.command("map <buffer> "+ub_get_option('ub_hotkey_open_item_in_splitted_view')+" :py __ub_list_open_item('split')<cr>")
    vim.command("map <buffer> "+ub_get_option('ub_hotkey_open_item_in_tabbed_view')+" :py __ub_list_open_item('tab')<cr>")
    vim.command("map <buffer> "+ub_get_option('ub_hotkey_delete_item')+" :py __ub_list_del_item()<cr>")
    vim.command('call UBClearUndo()')
    vim.command('setl nomodified')
    vim.command("setl nomodifiable")
    vim.current.window.cursor = (2, 0)

def ub_list_templates():
    '''List preview templates
    '''
    __ub_check_prerequesites()

    # Set editor mode if the corresponding option has been set
    ub_set_mode()

    sess = Session()

    tmpls = sess.query(Template).all()

    if len(tmpls)==0:
        sys.stderr.write('No template found !')
        return

    ub_wise_open_view('local_tmpl_list')
    enc = vim.eval('&encoding')
    vim.current.buffer[0] = "==================== Templates ===================="
    line = "%-24s%s"
    vim.current.buffer.append([(line % (tmpl.name,tmpl.description)).encode(enc) for tmpl in tmpls])

    vim.command("map <buffer> "+ub_get_option('ub_hotkey_open_item_in_current_view')+" :py __ub_list_open_item('cur')<cr>")
    vim.command("map <buffer> "+ub_get_option('ub_hotkey_open_item_in_splitted_view')+" :py __ub_list_open_item('split')<cr>")
    vim.command("map <buffer> "+ub_get_option('ub_hotkey_open_item_in_tabbed_view')+" :py __ub_list_open_item('tab')<cr>")
    vim.command("map <buffer> "+ub_get_option('ub_hotkey_delete_item')+" :py __ub_list_del_item()<cr>")
    vim.command('call UBClearUndo()')
    vim.command('setl nomodified')
    vim.command("setl nomodifiable")
    vim.current.window.cursor = (2, 0)

def ub_get_templates(name_only=False):
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
    __ub_fill_meta_data(post_meta_data)
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
    __ub_fill_meta_data(page_meta_data)
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
    __ub_fill_meta_data(post_meta_data)
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
    __ub_fill_meta_data(page_meta_data)
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
    __ub_fill_meta_data(meta_data)
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
    __ub_fill_meta_data(post_meta_data)
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
    __ub_fill_meta_data(page_meta_data)

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
    __ub_fill_meta_data(meta_data)
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

def __ub_fill_meta_data(meta_data):
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

def __ub_get_html(body_only=True):
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

def __ub_get_post_meta_data():
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

def __ub_get_page_meta_data():
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
        meta_dict = __ub_get_post_meta_data()
    elif ub_is_view('page_edit'):
        meta_dict = __ub_get_page_meta_data()
    else:
        return None

    content = "\n".join(vim.current.buffer[len(meta_dict)+2:])
    return content

def __ub_set_content(lines):
    '''Set the given lines to the content area of the current buffer
    '''
    if ub_is_view('post_edit'):
        meta_dict = __ub_get_post_meta_data()
    elif ub_is_view('page_edit'):
        meta_dict = __ub_get_page_meta_data()
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

