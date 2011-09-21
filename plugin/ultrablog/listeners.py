#!/usr/bin/env python

from exceptions import *
from util import *
from commands import *
from events import *
from eventqueue import UBEventQueue

class UBListener():
    ''' Parent class of all listeners
    '''
    eventType = None

    @classmethod
    def isTarget(cls, evt):
        return isinstance(evt, cls.eventType)

    @staticmethod
    def processEvent(evt): pass

class UBDebugListener(UBListener):
    ''' Debugging Listener
    '''
    eventType = UBDebugEvent
    
    @staticmethod
    def processEvent(evt):
        print evt.srcObj

class UBTmplDelListener(UBListener):
    ''' Listener for templates deletion events
    1. Delete all buffers which are edit views of the deleted template
    2. Refresh the current view if it is a list view of templates
    3. Mark all other template list views outdated
    '''
    eventType = UBTmplDelEvent

    @staticmethod
    def processEvent(evt):
        for nr in ub_get_buffers(['local_tmpl_list']):
            if nr == ub_get_bufnr('%'):
                ub_list_templates()
            else:
                ub_set_view_outdated(nr)

        for nr in ub_get_buffers(['tmpl_edit']):
            if evt.srcObj == ub_get_meta('name', nr):
                vim.command('bd! %d' % nr)

class UBTmplSaveListener(UBListener):
    ''' Listener for templates creation events
    1. Refresh the current view if it is a list view of templates
    2. Mark all other template list views outdated
    '''
    eventType = UBTmplSaveEvent
    
    @staticmethod
    def processEvent(evt):
        for nr in ub_get_buffers(['local_tmpl_list']):
            if nr == ub_get_bufnr('%'):
                ub_list_templates()
            else:
                ub_set_view_outdated(nr)

class UBRemotePostDelListener(UBListener):
    ''' Listener for remote posts/pages deletion events
    1. Reset the value of post_id column to 0 in the database
    2. Refresh the current view if it is an edit/list view of this post
    3. Mark all edit/list views of posts/pages outdated
    '''
    eventType = UBRemotePostDelEvent

    @staticmethod
    def processEvent(evt):
        sess = Session()
        sess.query(Post).filter(Post.post_id==evt.srcObj).update({Post.post_id:None})
        sess.commit()

        for nr in ub_get_buffers(['post_list','post_edit','page_list','page_edit','search_result_list']):
            if nr == ub_get_bufnr('%'):
                ub_refresh_current_view()
            else:
                ub_set_view_outdated(nr)

class UBLocalPostDelListener(UBListener):
    ''' Listener for local posts/pages deletion events
    1. Delete all buffers that hold the deleted local post/page
    2. Refresh the current view if it is an list view of this post
    3. Mark all list views of posts/pages outdated
    '''
    eventType = UBLocalPostDelEvent

    @staticmethod
    def processEvent(evt):
        for nr in ub_get_buffers(['post_edit','page_edit']):
            if evt.srcObj == ub_get_meta('id', nr):
                vim.command('bd! %d' % nr)

        for nr in ub_get_buffers(['post_list','page_list','search_result_list']):
            if nr == ub_get_bufnr('%'):
                ub_refresh_current_view()
            else:
                ub_set_view_outdated(nr)

class UBPostSaveListener(UBListener):
    ''' Listener for saving posts/pages
    1. Refresh the current view if it is an edit/list view of this post
    2. Mark all edit/list views of posts/pages outdated
    '''
    eventType = UBPostSaveEvent
    
    @staticmethod
    def processEvent(evt):
        for nr in ub_get_buffers(['post_edit','page_edit']):
            if evt.srcObj==ub_get_meta('id', nr):
                if nr==ub_get_bufnr('%'):
                    ub_refresh_current_view()
                else:
                    ub_set_view_outdated(nr)

        for nr in ub_get_buffers(['post_list','page_list','search_result_list']):
            if nr == ub_get_bufnr('%'):
                ub_refresh_current_view()
            else:
                ub_set_view_outdated(nr)

class UBPostSendListener(UBListener):
    ''' Listener for sending posts/pages
    1. Mark all remote list views outdated
    '''
    eventType = UBPostSendEvent

    @staticmethod
    def processEvent(evt):
        for nr in ub_get_buffers(['remote_post_list','remote_page_list']):
            ub_set_view_outdated(nr)

UBEventQueue.registerListener(UBDebugListener)
UBEventQueue.registerListener(UBTmplDelListener)
UBEventQueue.registerListener(UBTmplSaveListener)
UBEventQueue.registerListener(UBLocalPostDelListener)
UBEventQueue.registerListener(UBRemotePostDelListener)
UBEventQueue.registerListener(UBPostSendListener)
UBEventQueue.registerListener(UBPostSaveListener)

if __name__ == '__main__':
    pass
