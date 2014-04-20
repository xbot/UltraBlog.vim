#!/usr/bin/env python

import vim,re,types,os
from exceptions import *
from events import UBViewEnterEvent
from eventqueue import UBEventQueue

def ub_wise_open_view(view_name=None, view_type=None):
    '''Wisely decide whether to wipe out the content of current buffer 
    or to open a new splitted window or a new tab.
    '''
    if view_type == 'tab':
        vim.command(":tabnew")
    elif view_type == 'split':
        vim.command(":new")
    elif vim.current.buffer.name is None and vim.eval('&modified')=='0':
        vim.command('setl modifiable')
        del vim.current.buffer[:]
        vim.command('call UBClearUndo()')
        vim.command('setl nomodified')
    else:
        vim.command(":new")

    if view_name is not None:
        vim.command("let b:ub_view_name = '%s'" % view_name)

    UBEventQueue.fireEvent(UBViewEnterEvent(view_name))
    UBEventQueue.processEvents()

def ub_clear_buffer(expr, force=False):
    ''' Clear the specified buffer and reset related statuses
    '''
    nr = ub_get_bufnr(expr)
    if nr is None: return

    if '1' == vim.eval('&modified'):
        if force is True:
            vim.command('setl nomodified')
        else:
            raise UBException(_('The buffer has been changed and cannot be cleared !'))

    vim.command('setl modifiable')
    del vim.buffers[nr-1][:]
    vim.command('setl nomodified')

def ub_check_status(status):
    '''Check if the given status is valid,
    return True if status is publish
    '''
    if status == 'publish':
        return True
    elif status in ['private', 'pending', 'draft']:
        return False
    else:
        raise UBException(_('Invalid status !'))

def ub_check_reserved_word(rw):
    ''' Check if the given parameter is a reserved word
    '''
    try: ub_check_status(rw)
    except UBException: pass
    else: raise UBException(_("'%s' is a reserved word !") % rw)

def ub_is_valid_syntax(syntax):
    '''Check if the given parameter is one of the supported syntaxes
    '''
    return ['markdown', 'html', 'rst', 'latex', 'textile'].count(syntax) == 1

def ub_is_url(url):
    ''' Check if the given string is a valid URL
    '''
    regex = re.compile('^http:\/\/[0-9a-zA-Z]+(\.[0-9a-zA-Z]+)+')
    return regex.match(url) is not None

def ub_is_ubbuf(expr):
    ''' Check if the given buffer number exists and is a buffer of UltraBlog.vim
    '''
    return ub_get_viewname(expr) is not None

def ub_is_view_outdated(expr):
    ''' Check if the given view is outdated
    '''
    nr = ub_get_bufnr(expr)
    if nr is None:
        nr = -1
    return '1' == vim.eval("getbufvar(%d, 'ub_view_is_outdated')" % nr)

def ub_is_view(view_name, expr='%'):
    '''Check if the current view is named by the given parameter
    '''
    nr = ub_get_bufnr(expr)
    if nr is not None:
        return view_name == vim.eval("getbufvar(%d, 'ub_view_name')" % nr)
    return False

def ub_is_view_of_type(view_type, expr='%'):
    '''Check if the type of current view is the same with the given parameter
    '''
    vname = ub_get_viewname(expr)
    if vname is not None:
        return vname.endswith(view_type)
    return False

def ub_is_id(id, strict=False):
    ''' Check if the given parameter is a positive integer
    '''
    if strict is True and type(id) is not types.IntType:
        return False
    return (type(id) is types.IntType and id>0) or (type(id) is types.StringType and id.isdigit() and int(id)>0)

def ub_is_emptystr(str):
    ''' Check if the given parameter is an empty string
    '''
    return type(str) is types.StringType and len(str.strip())==0

def ub_is_cursorline_valid(line_type):
    ''' Check if the cursor line is a normal item line,
    valid types are 'template', 'post', 'page', 'general'
    '''
    parts = vim.current.line.split()
    if line_type=='template':
        return ub_is_view('local_tmpl_list') and vim.current.window.cursor[0]>1 and len(parts)>0
    else:
        is_general_line = vim.current.window.cursor[0]>1 and len(parts)>=3 and parts[0].isdigit() and parts[1].isdigit()
        if line_type=='general':
            return is_general_line
        elif line_type=='post':
            return (ub_is_view('local_post_list') or ub_is_view('remote_post_list')) and is_general_line
        elif line_type=='page':
            return (ub_is_view('local_page_list') or ub_is_view('remote_page_list')) and is_general_line
        elif line_type=='local':
            return (ub_is_view('local_page_list') or ub_is_view('local_post_list')) and is_general_line
        elif line_type=='remote':
            return (ub_is_view('remote_page_list') or ub_is_view('remote_post_list')) and is_general_line
        else:
            return False

def ub_get_item_type_name(type):
    ''' Get item type name by type
    '''
    if type == 'tmpl':
        return _('template')
    elif type in ['result','post']:
        return _('post')
    elif type == 'page':
        return _('page')
    return type

def ub_get_scope_name(scope):
    ''' Get scope name
    '''
    if scope == 'local':
        return _('local')
    elif scope == 'remote':
        return _('remote')
    return scope

def ub_get_status_label(status):
    ''' Get status label
    '''
    if status == 'publish':
        return _('publish')
    elif status == 'draft':
        return _('draft')
    elif status == 'private':
        return _('private')
    elif status == 'pending':
        return _('pending')
    return status

def ub_get_list_template():
    '''Return a template string for post or page list
    '''
    col1_width = 10
    tmp = ub_get_option('ub_list_col1_width')
    if tmp is not None and tmp.isdigit() and int(tmp)>0:
        col1_width = int(tmp)

    col2_width = 10
    tmp = ub_get_option('ub_list_col2_width')
    if tmp is not None and tmp.isdigit() and int(tmp)>0:
        col2_width = int(tmp)

    col3_width = 10
    tmp = ub_get_option('ub_list_col3_width')
    if tmp is not None and tmp.isdigit() and int(tmp)>0:
        col3_width = int(tmp)

    tmpl = "%%-%ds%%-%ds%%-%ds%%s"

    tmpl = tmpl % (col1_width,col2_width,col3_width)

    return tmpl

def ub_get_option(opt, deal=False):
    '''Get the value of an UltraBlog option
    '''
    def __get_positive(val, default):
        """Convert val to integer and return it if val is a positive integer or a digit string representing a positive integer,
        or default will be returned.
        """
        if (type(val) is types.IntType and val>0) \
                or (type(val) is types.StringType and val.isdigit() and int(val)>0):
            val = int(val)
        else:
            val = default
        return val
    def __get_boolean(val, default):
        """Return True if val is 1 or '1', or return False if val is 0 or '0', or default will be returned."""
        if val in [1,'1']: return True
        elif val in [0,'0']: return False
        else: return default

    val = None
    if vim.eval('exists("%s")' % opt) == '1':
        val = vim.eval(opt)

    if opt == 'ub_converter_command':
        val = val is None and 'pandoc' or val
    elif opt == 'ub_converter_option_from':
        val = val is None and '--from=%s' or val
    elif opt == 'ub_converter_option_to':
        val = val is None and '--to=%s' or val
    elif opt == 'ub_converter_options':
        val = val is None and ['--reference-links'] or val
    elif opt == 'ub_hotkey_open_item_in_current_view':
        val = val is None and '<enter>' or val
    elif opt == 'ub_hotkey_open_item_in_splitted_view':
        val = val is None and '<s-enter>' or val
    elif opt == 'ub_hotkey_open_item_in_tabbed_view':
        val = val is None and '<c-enter>' or val
    elif opt == 'ub_hotkey_delete_item':
        val = val is None and '<del>' or val
    elif opt == 'ub_hotkey_pagedown':
        val = val is None and '<c-pagedown>' or val
    elif opt == 'ub_hotkey_pageup':
        val = val is None and '<c-pageup>' or val
    elif opt == 'ub_hotkey_save_current_item':
        val = val is None and '<c-s>' or val
    elif opt == 'ub_tmpl_img_url':
        val = val is None and "markdown###![%(file)s][]\n[%(file)s]:%(url)s" or val
    elif opt == 'ub_default_template':
        val = val is None and 'default' or val
    elif opt == 'ub_local_pagesize':
        val = __get_positive(val, 30)
    elif opt == 'ub_remote_pagesize':
        val = __get_positive(val, 10)
    elif opt == 'ub_search_pagesize':
        val = __get_positive(val, 30)
    elif opt == 'ub_socket_timeout':
        val = __get_positive(val, 10)
    elif opt == 'ub_viewer_width':
        val = __get_positive(val, 900)
    elif opt == 'ub_viewer_height':
        val = __get_positive(val, 600)
    elif opt == 'ub_debug':
        val = __get_boolean(val, False)
    elif opt == 'ub_use_ubviewer':
        val = __get_boolean(val, True)
    elif opt == 'ub_save_after_opened':
        val = __get_boolean(val, False)

    if deal:
        if opt == 'ub_tmpl_img_url':
            tmp = val.split('###')
            val = {'tmpl':'', 'syntax':''}
            if len(tmp) == 2:
                val['syntax'] = tmp[0]
                val['tmpl'] = tmp[1]
            else:
                val['syntax'] = ''
                val['tmpl'] = tmp[0]

    return val

def ub_get_meta(item, buf=None):
    '''Get value of the given item from meta data in the current buffer
    '''
    def __get_value(item, line):
        tmp = line.split(':')
        val = ':'.join(tmp[1:]).strip()
        if item.endswith('id'):
            if val.isdigit():
                val = int(val)
                if val<=0:
                    return None
            else:
                return None
        return val

    nr = ub_get_bufnr(buf)
    if nr is None: nr = int(vim.eval("bufnr('%')"))
    regex_meta_end = re.compile('^\s*-->')
    regex_item = re.compile('^\$'+item+':\s*')
    for line in vim.eval("getbufline(%d,0,'$')" % nr):
        if regex_meta_end.match(line):
            break
        if regex_item.match(line):
            return __get_value(item, line)
    return None

def ub_set_meta(item, value):
    '''Set value of the given item from meta data in the current buffer
    '''
    regex_meta_end = re.compile('^\s*-->')
    regex_item = re.compile('^\$'+item+':\s*')
    for i in range(0,len(vim.current.buffer)):
        if regex_meta_end.match(vim.current.buffer[i]):
            break
        if regex_item.match(vim.current.buffer[i]):
            vim.current.buffer[i] = "$%-17s%s" % (item+':',value)
            return True
    return False

def ub_get_buffers(viewnames=None):
    ''' Return a list of buffer numbers which belongs to UltraBlog.vim
    If parameter viewnames is given, buffers which has the given name will be returned
    '''
    bufs = []
    for nr in range(int(vim.eval("bufnr('$')"))+1):
        if viewnames is None and ub_is_ubbuf(nr):
            bufs.append(nr)
        if type(viewnames) is types.ListType:
            for viewname in viewnames:
                if ub_is_view_of_type(viewname, nr):
                    bufs.append(nr)
    return bufs

def ub_get_bufvar(key, expr='%'):
    ''' Return the value of the given buffer variable
    '''
    nr = ub_get_bufnr(expr)
    if nr is None: return None
    return vim.eval("getbufvar(%d, '%s')" % (nr,key))

def ub_get_viewname(expr):
    ''' Return the value of variable b:ub_view_name in buffer nr
    '''
    return ub_get_bufvar('ub_view_name', expr)

def ub_get_bufnr(expr):
    ''' Return the buffer number which matches the given expression
    '''
    nr = None
    if type(expr) is types.IntType:
        nr = vim.eval("bufnr(%d)" % expr)
    elif type(expr) is types.StringType:
        if expr.isdigit():
            nr = vim.eval("bufnr(%d)" % expr)
        else:
            nr = vim.eval("bufnr('%s')" % expr)

    if type(nr) is types.StringType and nr.isdigit() and int(nr)>0 and expr not in [0,'0']:
        return int(nr)
    return None

def ub_get_blog_settings():
    '''Get the blog settings from vimrc and raise exception if none found
    '''
    class UBConfiguration:
        homepage = 'http://0x3f.org/blog/ultrablog-as-an-ultimate-vim-blogging-plugin/'

        def __init__(self, rawSettings):
            self.loginName = rawSettings['login_name'].strip()
            self.password = rawSettings['password'].strip()
            self.dbf = rawSettings['db'].strip()
            self.url = rawSettings['url'].strip()
            self.url = self.url.endswith('/') and self.url or self.url+'/'
            self.uri = rawSettings['xmlrpc_uri'].strip()
            self.uri = self.uri.startswith('/') and self.uri[1:] or self.uri
            self.xmlrpc = self.url+self.uri
            self.categories = rawSettings.has_key('categories') and rawSettings['categories'].strip() or ''

    if vim.eval('exists("ub_blog")') == '0':
        return None

    settings = vim.eval('ub_blog')
    cfg = UBConfiguration(settings)

    # Manipulate db file path
    editor_mode = ub_get_option('ub_editor_mode')
    if editor_mode is not None and editor_mode.isdigit() and int(editor_mode) == 1:
        cfg.dbf = ''
    elif cfg.dbf is None or cfg.dbf=='':
        cfg.dbf = os.path.normpath(os.path.expanduser('~')+'/.vim/UltraBlog.db')
    else:
        cfg.dbf = os.path.abspath(vim.eval("expand('%s')" % cfg.dbf))

    return cfg

def ub_set_view_outdated(expr, outdated=True):
    ''' Set the specified view to be outdated
    '''
    nr = ub_get_bufnr(expr)
    val = (outdated is True and 1) or 0
    if nr is not None:
        vim.command("call setbufvar(%d,'ub_view_is_outdated',%d)" % (nr,val))

def ub_fill_meta_data(meta_data):
    if ub_is_view('post_edit'):
        __ub_fill_post_meta_data(meta_data)
    elif ub_is_view('page_edit'):
        __ub_fill_page_meta_data(meta_data)
    elif ub_is_view('tmpl_edit'):
        __ub_fill_tmpl_meta_data(meta_data)
    else:
        raise UBException(_('Invalid view !'))

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
    content = ub_get_content()
    syntax = vim.eval('&syntax')
    enc = vim.eval('&encoding')
    html = ub_convert_str(content, syntax, 'html', enc)

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

def ub_get_tmpl_meta_data():
    return dict(\
        name = ub_get_meta('name'),
        description = ub_get_meta('description')
    )

def ub_get_content():
    '''Generate content from the current buffer
    '''
    if ub_is_view('post_edit'):
        meta_dict = ub_get_post_meta_data()
    elif ub_is_view('page_edit'):
        meta_dict = ub_get_page_meta_data()
    elif ub_is_view('tmpl_edit'):
        meta_dict = ub_get_tmpl_meta_data()
    else:
        return "\n".join(vim.current.buffer[:])

    return "\n".join(vim.current.buffer[len(meta_dict)+2:])

def ub_set_content(lines):
    '''Set the given lines to the content area of the current buffer
    '''
    meta_dict = None
    if ub_is_view('post_edit'):
        meta_dict = ub_get_post_meta_data()
    elif ub_is_view('page_edit'):
        meta_dict = ub_get_page_meta_data()
    elif ub_is_view('tmpl_edit'):
        meta_dict = ub_get_tmpl_meta_data()

    idx = meta_dict is not None and len(meta_dict)+2 or 0
    del vim.current.buffer[idx:]
    vim.current.buffer.append(lines, idx)
    return True

def ub_convert_str(content, from_syntax, to_syntax, encoding=None):
    if from_syntax == to_syntax \
        or not ub_is_valid_syntax(from_syntax) \
        or not ub_is_valid_syntax(to_syntax):
        return content

    if from_syntax == 'markdown' and to_syntax == 'html':
        try:
            import markdown
        except ImportError:
            try:
                import markdown2 as markdown
            except ImportError:
                raise UBException(_('Missing module: python-markdown or python-markdown2 !'))
        if encoding is not None:
            new_content = markdown.markdown(content.decode(encoding)).encode(encoding)
        else:
            new_content = markdown.markdown(content)
    elif from_syntax == 'html' and to_syntax == 'markdown':
        try:
            import html2text
        except ImportError:
            raise UBException(_('Missing module: python-html2text !'))
        if encoding is not None:
            new_content = html2text.html2text(content.decode(encoding)).encode(encoding)
        else:
            new_content = html2text.html2text(content)
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

def ub_get_templates(name_only=False):
    ''' Fetch and return a list of templates
    '''
    tmpls = []

    try:
        sess = Session()
        tmpls = sess.query(Template).all()
        sess.close()

        if name_only is True: tmpls = [tmpl.name for tmpl in tmpls]
    except:
        pass

    return tmpls

def ub_echoerr(msg):
    cmd = '''echoerr "%s"''' % msg.replace('"', "'")
    vim.command(cmd)

def ub_echo(msg):
    cmd = '''echo "%s"''' % msg.replace('"', "'")
    vim.command(cmd)

def raw(text):
    """Returns a raw string representation of text"""
    escape_dict={'\a':r'\a', '\b':r'\b', '\c':r'\c', '\f':r'\f', '\n':r'\n',
               '\r':r'\r', '\t':r'\t', '\v':r'\v', '\'':r'\'', '\"':r'\"',
               '\0':r'\0', '\1':r'\1', '\2':r'\2', '\3':r'\3', '\4':r'\4',
               '\5':r'\5', '\6':r'\6', '\7':r'\7', '\8':r'\8', '\9':r'\9'}
    return "".join([escape_dict.get(char,char) for char in text])

def regex_replace(string, expr, repl):
    """Do substitutions on the string for repls matching the expr"""
    r = re.compile(raw(expr))
    return r.sub(repl, string)

def regexp_search(expr, item):
    """Check if the item has a sub-string which matches the expr"""
    reg = re.compile(expr)
    return reg.search(item) is not None

def is_in_console():
    """Return True if invoked under console"""
    if os.name == 'posix' and os.environ.has_key('DISPLAY') is False:
        return True
    return False
