 
" File:        UltraBlog.vim
" Description: Ultimate vim blogging plugin that manages web logs
" Author:      Lenin Lee <lenin.lee at gmail dot com>
" Version:     3.0.0
" Last Change: 2011-07-24
" License:     Copyleft.
"
" ============================================================================

if !has("python")"{{{
    finish
endif"}}}

function! SyntaxCmpl(ArgLead, CmdLine, CursorPos)"{{{
  return "markdown\nhtml\nrst\ntextile\nlatex\n"
endfunction"}}}

function! StatusCmpl(ArgLead, CmdLine, CursorPos)"{{{
  return "draft\npublish\nprivate\npending\n"
endfunction"}}}

function! ScopeCmpl(ArgLead, CmdLine, CursorPos)"{{{
  return "local\nremote\n"
endfunction"}}}

function! UBNewCmpl(ArgLead, CmdLine, CursorPos)"{{{
    let lst = split(a:CmdLine)
    if len(a:ArgLead)>0
        let lst = lst[0:-2]
    endif

    let results = []
    " For the first argument, complete the object type
    if len(lst)==1
        let objects = ['post','page','tmpl']
        for obj in objects
            if stridx(obj,a:ArgLead)==0
                call add(results,obj)
            endif
        endfor
    " For the second argument, complete the syntax for :UBNew post or :UBNew
    " page
    elseif len(lst)==2 && count(['post', 'page'], lst[1])==1
        let syntaxes = ['markdown','html','rst','textile','latex']
        for synx in syntaxes
            if stridx(synx,a:ArgLead)==0
                call add(results,synx)
            endif
        endfor
    endif
    return results
endfunction"}}}

function! UBOpenCmpl(ArgLead, CmdLine, CursorPos)"{{{
    let lst = split(a:CmdLine)
    if len(a:ArgLead)>0
        let lst = lst[0:-2]
    endif

    let results = []
    " For the first argument, complete the object type
    if len(lst)==1
        let objects = ['post','page','tmpl']
        for obj in objects
            if stridx(obj, a:ArgLead)==0
                call add(results, obj)
            endif
        endfor
    " For the third argument, complete the scope
    elseif len(lst)==3
        let scopes = ['local', 'remote']
        for scope in scopes
            if stridx(scope, a:ArgLead)==0
                call add(results, scope)
            endif
        endfor
    endif
    return results
endfunction"}}}

function! UBListCmpl(ArgLead, CmdLine, CursorPos)"{{{
    let lst = split(a:CmdLine)
    if len(a:ArgLead)>0
        let lst = lst[0:-2]
    endif

    let results = []
    " For the first argument, complete the object type
    if len(lst)==1
        let objects = ['post','page','tmpl']
        for obj in objects
            if stridx(obj, a:ArgLead)==0
                call add(results, obj)
            endif
        endfor
    " For the second argument, complete the scope
    elseif len(lst)==2 && count(['post', 'page'], lst[1])==1
        let scopes = ['local', 'remote']
        for scope in scopes
            if stridx(scope, a:ArgLead)==0
                call add(results, scope)
            endif
        endfor
    endif
    return results
endfunction"}}}

function! UBDelCmpl(ArgLead, CmdLine, CursorPos)"{{{
    let lst = split(a:CmdLine)
    if len(a:ArgLead)>0
        let lst = lst[0:-2]
    endif

    let results = []
    " For the first argument, complete the object type
    if len(lst)==1
        let objects = ['post','page','tmpl']
        for obj in objects
            if stridx(obj, a:ArgLead)==0
                call add(results, obj)
            endif
        endfor
    " For the third argument, complete the scope
    elseif len(lst)==3 && count(['post', 'page'], lst[1])==1
        let scopes = ['local', 'remote']
        for scope in scopes
            if stridx(scope, a:ArgLead)==0
                call add(results, scope)
            endif
        endfor
    endif
    return results
endfunction"}}}

function! UBThisCmpl(ArgLead, CmdLine, CursorPos)"{{{
    let lst = split(a:CmdLine)
    if len(a:ArgLead)>0
        let lst = lst[0:-2]
    endif

    let results = []
    " For the first argument, complete the object type
    if len(lst)==1
        let objects = ['post','page']
        for obj in objects
            if stridx(obj, a:ArgLead)==0
                call add(results, obj)
            endif
        endfor
    " For the second argument, complete the scope
    elseif len(lst)==2 && count(['post', 'page'], lst[1])==1
        let syntaxes = ['markdown','html','rst','textile','latex']
        for synx in syntaxes
            if stridx(synx,a:ArgLead)==0
                call add(results,synx)
            endif
        endfor
    endif
    return results
endfunction"}}}

function! UBPreviewCmpl(ArgLead, CmdLine, CursorPos)"{{{
python <<EOF
templates = ub_get_templates(True)
vim.command('let b:ub_templates=%s' % str(templates))
EOF
    let tmpls = ['publish', 'private', 'draft']
    if exists('b:ub_templates')
        call extend(tmpls, b:ub_templates)
    endif
    return join(tmpls, "\n")
endfunction"}}}

" Clear undo history
function! UBClearUndo()"{{{
    let old_undolevels = &undolevels
    set undolevels=-1
    exe "normal a \<BS>\<Esc>"
    let &undolevels = old_undolevels
    unlet old_undolevels
endfunction"}}}

" Open the item under cursor in list views
function! UBOpenItemUnderCursor(viewType)"{{{
    if s:UBIsView('local_post_list') || s:UBIsView('local_page_list') || s:UBIsView('remote_page_list') || s:UBIsView('remote_post_list') || s:UBIsView('local_tmpl_list') || s:UBIsView('search_result_list')
        exe 'py __ub_list_open_item("'.a:viewType.'")'
    endif
endfunction"}}}

" Check if the current buffer is named with the given name
function! s:UBIsView(viewName)"{{{
    return exists('b:ub_view_name') && b:ub_view_name==a:viewName
endfunction"}}}

" Commands
command! -nargs=* -complete=customlist,UBListCmpl UBList exec('py ub_list_items(<f-args>)')
command! -nargs=* -complete=customlist,UBNewCmpl UBNew exec('py ub_new_item(<f-args>)')
command! -nargs=* -complete=customlist,UBOpenCmpl UBOpen exec('py ub_open_item_x(<f-args>)')
command! -nargs=* -complete=customlist,UBDelCmpl UBDel exec('py ub_del_item(<f-args>)')
command! -nargs=? -complete=custom,StatusCmpl UBSend exec('py ub_send_item(<f-args>)')
command! -nargs=? -complete=customlist,UBThisCmpl UBThis exec('py ub_blog_this(<f-args>)')
command! -nargs=? -complete=custom,UBPreviewCmpl UBPreview exec('py ub_preview(<f-args>)')
command! -nargs=0 UBSave exec('py ub_save_item()')
command! -nargs=1 -complete=file UBUpload exec('py ub_upload_media(<f-args>)')
command! -nargs=* -complete=custom,SyntaxCmpl UBConv exec('py ub_convert(<f-args>)')
command! -nargs=+ UBFind exec('py ub_find(1, <f-args>)')
command! -nargs=0 UBRefresh exec('py ub_refresh_current_view()')

" Auto-commands
au BufEnter * py __ub_on_buffer_enter()

python <<EOF
# -*- coding: utf-8 -*-
import vim,os

for pth in vim.eval('&rtp').split(','): sys.path.append(os.path.join(pth, 'plugin'))
from ultrablog.exceptions import *
from ultrablog.events import *
from ultrablog.commands import *
from ultrablog.listeners import UBEventQueue

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

@__ub_exception_handler
def __ub_list_open_item(view_type=None):
    '''Open the item under cursor, invoked in post or page list
    '''
    parts = vim.current.line.split()
    if ub_is_cursorline_valid('template'):
        ub_open_local_tmpl(parts[0], view_type)
    elif ub_is_cursorline_valid('general'):
        if ub_is_view('local_post_list') or ub_is_view('local_page_list') or ub_is_view('search_result_list'):
            id = int(parts[0])
            sess = Session()
            post = sess.query(Post).filter(Post.id==id).first()
            eval("ub_open_local_%s(%d, '%s')" % (post.type,id,view_type))
        elif ub_is_view('remote_post_list'):
            id = int(parts[1])
            ub_open_remote_post(id, view_type)
        elif ub_is_view('remote_page_list'):
            id = int(parts[1])
            ub_open_remote_page(id, view_type)
        else:
            raise UBException('Invalid view !')

@__ub_exception_handler
def __ub_list_del_item():
    '''Delete local post, invoked in list view
    '''
    info = vim.current.line.split()

    if ub_is_cursorline_valid('template'):
        ub_del_item('tmpl', info[0])
    elif ub_is_cursorline_valid('general'):
        view_name_parts = vim.eval('b:ub_view_name').split('_')
        item_type = view_name_parts[1]
        if int(info[0])>0:
            sess = Session()
            item_type = sess.query(Post.type).filter(Post.id==int(info[0])).first()[0]
            ub_del_item(item_type, int(info[0]), 'local')
        if int(info[1])>0:
            ub_del_item(item_type, int(info[1]), 'remote')
    else:
        raise UBException('Invalid view !')

@__ub_exception_handler
def __ub_on_buffer_enter():
    ''' Triggered by BufEnter event, check if the buffer is outdated
    '''
    if ub_is_view_outdated('%'):
        ub_refresh_current_view()
        ub_set_view_outdated('%', False)

if __name__ == "__main__":
    pass
EOF
