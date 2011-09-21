#!/usr/bin/env python

import vim,re,types,os
from exceptions import *
try:
    import markdown
except ImportError:
    try:
        import markdown2 as markdown
    except ImportError:
        markdown = None

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

    vim.command('mapclear <buffer>')

def ub_clear_buffer(expr, force=False):
    ''' Clear the specified buffer and reset related statuses
    '''
    nr = ub_get_bufnr(expr)
    if nr is None: return

    if '1' == vim.eval('&modified'):
        if force is True:
            vim.command('setl nomodified')
        else:
            raise UBException('The buffer has been changed and cannot be cleared !')

    vim.command('setl modifiable')
    del vim.buffers[nr-1][:]
    vim.command('setl nomodified')

def ub_check_scope(scope):
    '''Check the given scope,
    return True if it is local,
    return False if it is remote,
    raise an exception if it is neither of the upper two
    '''
    if scope=='local':
        return True
    elif scope=='remote':
        return False
    else:
        raise UBException('Invalid scope !')

def ub_check_status(status):
    '''Check if the given status is valid,
    return True if status is publish
    '''
    if status == 'publish':
        return True
    elif status in ['private', 'pending', 'draft']:
        return False
    else:
        raise UBException('Invalid status !')

def ub_check_syntax(syntax):
    ''' Check if the given syntax is among the available ones
    '''
    valid_syntax = ['markdown', 'html', 'rst', 'textile', 'latex']
    if syntax.lower() not in valid_syntax:
        raise UBException('Unknown syntax, valid syntaxes are %s' % str(valid_syntax))

def ub_check_item_type(item_type):
    ''' Check if the given parameter item type is among the available ones
    '''
    if not item_type in ['post', 'page', 'tmpl']:
        raise UBException('Unknow item type, available types are: post, page and tmpl !')

def ub_check_reserved_word(rw):
    ''' Check if the given parameter is a reserved word
    '''
    try:
        ub_check_status(rw)
    except UBException:
        pass
    else:
        raise UBException("'%s' is a reserved word !" % rw)

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
        return 'template'
    return type

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
    if vim.eval('exists("%s")' % opt) == '1':
        val = vim.eval(opt)
    elif opt == 'ub_converter_command':
        val = 'pandoc'
    elif opt == 'ub_converter_option_from':
        val = '--from=%s'
    elif opt == 'ub_converter_option_to':
        val = '--to=%s'
    elif opt == 'ub_converter_options':
        val = ['--reference-links']
    elif opt == 'ub_hotkey_open_item_in_current_view':
        val = '<enter>'
    elif opt == 'ub_hotkey_open_item_in_splitted_view':
        val = '<s-enter>'
    elif opt == 'ub_hotkey_open_item_in_tabbed_view':
        val = '<c-enter>'
    elif opt == 'ub_hotkey_delete_item':
        val = '<del>'
    elif opt == 'ub_hotkey_pagedown':
        val = '<c-pagedown>'
    elif opt == 'ub_hotkey_pageup':
        val = '<c-pageup>'
    elif opt == 'ub_tmpl_img_url':
        val = "markdown###![%(file)s][]\n[%(file)s]:%(url)s"
    elif opt == 'ub_local_pagesize':
        val = 30
    elif opt == 'ub_remote_pagesize':
        val = 10
    elif opt == 'ub_search_pagesize':
        val = 30
    elif opt == 'ub_default_template':
        val = 'default'
    else:
        val = None

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
        elif opt == 'ub_save_after_opened':
            val = ('1'==val and True) or False

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
        homepage = 'http://sinolog.it/?p=1894'

        def __init__(self, rawSettings):
            self.loginName = rawSettings['login_name'].strip()
            self.password = rawSettings['password'].strip()
            self.xmlrpc = rawSettings['xmlrpc'].strip()
            self.dbf = rawSettings['db'].strip()
        
        @property
        def blogURL(self):
            blog_url = None
            if ub_is_url(self.xmlrpc):
                url_parts = self.xmlrpc.split('/')
                url_parts.pop()
                blog_url = '/'.join(url_parts)
            return blog_url

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

if __name__ == '__main__':
    pass
