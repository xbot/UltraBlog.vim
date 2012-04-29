 
" File:        UltraBlog.vim
" Description: Ultimate vim blogging plugin that manages web logs
" Author:      Lenin Lee <lenin.lee at gmail dot com>
" Version:     3.5.0
" License:     The New BSD License
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
    " For the second argument, complete the syntax to be converted to
    " For the third argument, complete the syntax to be converted from
    elseif (len(lst)==2 || len(lst)==3) && count(['post', 'page'], lst[1])==1
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
enc = vim.eval('&encoding')
templates = [tmpl.encode(enc) for tmpl in ub_get_templates(True)]
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

" Commands
command! -nargs=* -complete=customlist,UBListCmpl UBList exec('py ub_list_items(<f-args>)')
command! -nargs=* -complete=customlist,UBNewCmpl UBNew exec('py ub_new_item(<f-args>)')
command! -nargs=* -complete=customlist,UBOpenCmpl UBOpen exec('py ub_open_item_x(<f-args>)')
command! -nargs=* -complete=customlist,UBDelCmpl UBDel exec('py ub_del_item(<f-args>)')
command! -nargs=* -complete=customlist,UBThisCmpl UBThis exec('py ub_blog_this(<f-args>)')
command! -nargs=+ UBFind exec('py ub_search(0, 1, <f-args>)')
command! -nargs=+ UBRegexSearch exec('py ub_search(1, 1, <f-args>)')
command! -nargs=+ UBReplace exec('py ub_replace(0, <f-args>)')
command! -nargs=+ UBRegexReplace exec('py ub_replace(1, <f-args>)')
command! -nargs=0 UBEnableDebug exec('py ub_debug(1)')
command! -nargs=0 UBDisableDebug exec('py ub_debug(0)')
command! -nargs=0 UBToggleDebug exec('py ub_debug(2)')

" Auto-commands
autocmd! BufEnter * py __ub_on_buffer_enter()

python <<EOF
# -*- coding: utf-8 -*-
import vim,os

for pth in vim.eval('&rtp').split(','): sys.path.append(os.path.join(pth, 'plugin'))
from ultrablog.exceptions import *
from ultrablog.events import *
from ultrablog.commands import *
from ultrablog.listeners import UBEventQueue

def __ub_on_buffer_enter():
    ''' Triggered by BufEnter event, check if the buffer is outdated
    '''
    if ub_is_view_outdated('%'):
        ub_refresh_current_view()
        ub_set_view_outdated('%', False)
EOF
