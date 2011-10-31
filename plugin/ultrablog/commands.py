#!/usr/bin/env python
# -*- encoding: utf-8 -*-

import vim, xmlrpclib, webbrowser, sys, re, tempfile, os, mimetypes, inspect, types
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
            print >> sys.stderr,str(e)
        except xmlrpclib.Fault, e:
            print >> sys.stderr,"xmlrpc error: %s" % e.faultString
        except xmlrpclib.ProtocolError, e:
            print >> sys.stderr,"xmlrpc error: %s %s" % (e.url, e.errmsg)
        except IOError, e:
            print >> sys.stderr,"network error: %s" % e
        except Exception, e:
            print >> sys.stderr,str(e)
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
    cmd = UBCmdRefresh()
    cmd.execute()

@__ub_exception_handler
def ub_preview(tmpl=None):
    '''Preview the current buffer in a browser
    '''
    cmd = UBCmdPreview(tmpl)
    cmd.execute()

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
def ub_open_item_x(item_type, item_key, scope='local'):
    ''' Open item, this function use __ub_exception_handler and so is suitable to be called directly
    '''
    ub_open_item(item_type, item_key, scope)

def ub_open_item(item_type, item_key, scope='local'):
    ''' Open item, this function do not use the __ub_exception_handler and so can be used programmatically
    '''
    cmd = UBCmdOpen(itemKey=item_key, itemType=item_type, scope=scope)
    cmd.execute()

@__ub_exception_handler
def ub_open_item_under_cursor(view_type=None):
    '''Open the item under cursor, invoked in post or page list
    '''
    cmd = UBCmdOpenItemUnderCursor(view_type)
    cmd.execute()

@__ub_exception_handler
def ub_del_item(item_type, key, scope='local'):
    '''Delete an item
    '''
    cmd = UBCmdDelete(item_type, key, scope)
    cmd.execute()

@__ub_exception_handler
def ub_del_item_under_cursor():
    '''Delete local post, invoked in list view
    '''
    cmd = UBCmdDelItemUnderCursor()
    cmd.execute()

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
    img_url = ub_convert_str(img_url, img_tmpl_info['syntax'], syntax)
    vim.current.range.append(img_url.split("\n"))

@__ub_exception_handler
def ub_blog_this(item_type='post', to_syntax=None, from_syntax=None):
    '''Create a new post/page with content in the current buffer
    '''
    cmd = UBCmdBlogThis(item_type, to_syntax, from_syntax)
    cmd.execute()

@__ub_exception_handler
def ub_convert(to_syntax, from_syntax=None):
    '''Convert the current buffer from one syntax to another
    '''
    cmd = UBCmdConvert(to_syntax, from_syntax)
    cmd.execute()

@__ub_exception_handler
def ub_new_item(item_type='post', mixed='markdown'):
    ''' Create new item: post, page, template
    '''
    cmd = UBCmdNew(item_type, mixed)
    cmd.execute()

class UBCommand(object):
    ''' Abstract parent class for all commands of UB
    '''
    def __init__(self, isContentAware=False):
        self.checkPrerequisites()
        # Set editor mode if the corresponding option has been set
        ub_set_mode()

        self.isContentAware = isContentAware
        self.scope = 'local'
        self.itemType = None
        self.viewScopes = []
        self.enc = vim.eval('&encoding')
        self.syntax = vim.eval('&syntax')
        self.sess = Session()
        self.viewName = ub_get_viewname('%')

        if self.viewName is not None:
            vnameParts = self.viewName.split('_')
            if ub_is_view_of_type('list'):
                self.itemType = vnameParts[1]=='result' and 'post' or vnameParts[1]
                self.scope = vnameParts[0]=='search' and 'local' or vnameParts[0]
            if ub_is_view_of_type('edit'):
                self.itemType = vnameParts[0]

    def checkPrerequisites(self):
        ''' Check the prerequisites
        '''
        if sqlalchemy is None: raise UBException('Cannot find SQLAlchemy !')
        if Base is None or Session is None or Post is None or Template is None:
            raise UBException('Cannot create database objects !')
        if cfg is None: raise UBException('Settings of UltraBlog.vim is missing or invalid !')
        if api is None: raise UBException('Cannot initiate API !')
        if db is None: raise UBException('Cannot connect to database !')

    def checkItemType(self, itemType=None):
        ''' Check if the item type is among the available ones
        '''
        itemType = itemType and itemType or self.itemType
        if not itemType in ['post', 'page', 'tmpl', None]:
            raise UBException('Unknow item type, available types are: post, page and tmpl !')

    def checkScope(self, scope=None):
        '''Check the given scope,
        return True if it is local,
        return False if it is remote,
        raise an exception if it is neither of the upper two
        '''
        scope = scope and scope or self.scope
        if scope=='local':
            return True
        elif scope=='remote':
            return False
        else:
            raise UBException('Invalid scope !')

    def checkSyntax(self, syntax=None):
        ''' Check if the given syntax is among the available ones
        '''
        syntax = syntax is not None and syntax or self.syntax
        valid_syntax = ['markdown', 'html', 'rst', 'textile', 'latex']
        if syntax is None or syntax.lower() not in valid_syntax:
            raise UBException('Unknown syntax, valid syntaxes are %s' % str(valid_syntax))

    def checkViewScope(self, viewName=None):
        ''' Check if the given viewname is among the available ones
        '''
        viewName = viewName is not None and viewName or self.viewName
        if len(self.viewScopes)>0:
            for scope in self.viewScopes:
                if viewName is not None and viewName.endswith(scope): return
            raise UBException('Invalid view, this command is only allowed in %s !' % str(self.viewScopes))

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
        self.checkViewScope()
        if self.isContentAware is True: self.checkSyntax()

    def _exec(self):
        ''' Do the main part of the job
        protected method, called by self.execute()
        '''
        raise UBException('Not implemented yet !')

    def _postExec(self):
        ''' Do something after self._exec()
        protected method, called by self.execute()
        '''
        self.sess.close()

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
        self.pageSize = int(pageSize is not None and pageSize or ub_get_option("ub_%s_pagesize" % self.scope))
        self.pageNo = int(pageNo is not None and pageNo or 1)

    def _preExec(self):
        UBCmdList.doDefault()
        if self.pageNo<1: raise UBException('Page NO. cannot be less than 1 !')
        if self.pageSize<1: raise UBException('Illegal page size (%s) !' % self.pageSize)

    def _exec(self):
        if self.itemType=='tmpl': self._listTemplates()
        else: eval("self._list%s%ss()" % (self.scope.capitalize(), self.itemType.capitalize()))

    def _postExec(self):
        UBCmdList.doDefault()
        vim.command("map <buffer> "+ub_get_option('ub_hotkey_open_item_in_current_view')+" :py ub_open_item_under_cursor('cur')<cr>")
        vim.command("map <buffer> "+ub_get_option('ub_hotkey_open_item_in_splitted_view')+" :py ub_open_item_under_cursor('split')<cr>")
        vim.command("map <buffer> "+ub_get_option('ub_hotkey_open_item_in_tabbed_view')+" :py ub_open_item_under_cursor('tab')<cr>")
        vim.command("map <buffer> "+ub_get_option('ub_hotkey_delete_item')+" :py ub_del_item_under_cursor()<cr>")
        vim.command('call UBClearUndo()')
        vim.command('setl nomodified')
        vim.command("setl nomodifiable")
        vim.current.window.cursor = (2, 0)

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
        vim.command("map <buffer> "+ub_get_option('ub_hotkey_pagedown')+" :py ub_list_items('post', 'local', %d, %d)<cr>" % (self.pageSize, self.pageNo+1))
        vim.command("map <buffer> "+ub_get_option('ub_hotkey_pageup')+" :py ub_list_items('post', 'local', %d, %d)<cr>" % (self.pageSize, self.pageNo-1))

    def _listRemotePosts(self):
        '''List remote posts stored in the blog
        '''
        posts = api.metaWeblog.getRecentPosts('', cfg.loginName, cfg.password, self.pageSize)
        for post in posts:
            local_post = self.sess.query(Post).filter(Post.post_id==post['postid']).first()
            if local_post is None:
                post['id'] = 0
            else:
                post['id'] = local_post.id
                post['post_status'] = local_post.status

        ub_wise_open_view('remote_post_list')
        vim.current.buffer[0] = "==================== Recent Posts ===================="
        tmpl = ub_get_list_template()
        vim.current.buffer.append([(tmpl % (post['id'],post['postid'],post['post_status'],post['title'])).encode(self.enc) for post in posts])

        vim.command("let b:page_size=%s" % self.pageSize)

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

    def _listRemotePages(self):
        '''List remote pages stored in the blog
        '''
        pages = api.wp.getPages('', cfg.loginName, cfg.password)
        for page in pages:
            local_page = self.sess.query(Post).filter(Post.post_id==page['page_id']).filter(Post.type=='page').first()
            if local_page is None:
                page['id'] = 0
            else:
                page['id'] = local_page.id
                page['page_status'] = local_page.status

        ub_wise_open_view('remote_page_list')
        vim.current.buffer[0] = "==================== Blog Pages ===================="
        tmpl = ub_get_list_template()
        vim.current.buffer.append([(tmpl % (page['id'],page['page_id'],page['page_status'],page['title'])).encode(self.enc) for page in pages])

    def _listTemplates(self):
        '''List preview templates
        '''
        tmpls = self.sess.query(Template).all()

        if len(tmpls)==0:
            print >> sys.stderr,'No template found !'
            return

        ub_wise_open_view('local_tmpl_list')
        vim.current.buffer[0] = "==================== Templates ===================="
        line = "%-24s%s"
        vim.current.buffer.append([(line % (tmpl.name,tmpl.description)).encode(self.enc) for tmpl in tmpls])

class UBCmdFind(UBCommand):
    ''' Context search
    '''
    def __init__(self, pageNo, *keywords):
        UBCommand.__init__(self)
        self.pageSize = int(ub_get_option("ub_%s_pagesize" % self.scope))
        self.pageNo = int(pageNo is not None and pageNo or 1)
        self.keywords = keywords

    def _preExec(self):
        UBCmdFind.doDefault()
        if self.pageNo<1: raise UBException('Page NO. cannot be less than 1 !')
        if self.pageSize<1: raise UBException('Illegal page size (%s) !' % self.pageSize)

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
        vim.command("map <buffer> "+ub_get_option('ub_hotkey_open_item_in_current_view')+" :py ub_open_item_under_cursor('cur')<cr>")
        vim.command("map <buffer> "+ub_get_option('ub_hotkey_open_item_in_splitted_view')+" :py ub_open_item_under_cursor('split')<cr>")
        vim.command("map <buffer> "+ub_get_option('ub_hotkey_open_item_in_tabbed_view')+" :py ub_open_item_under_cursor('tab')<cr>")
        vim.command("map <buffer> "+ub_get_option('ub_hotkey_delete_item')+" :py ub_del_item_under_cursor()<cr>")
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
        UBCommand.__init__(self, True)
        self.item = None
        self.itemKey = ub_get_meta('id')
        self.viewScopes = ['post_edit', 'page_edit', 'tmpl_edit']

    def _preExec(self):
        UBCmdSave.doDefault()
        # Do not bother if the current buffer is not modified
        if vim.eval('&modified')=='0': raise UBException('This buffer has not been modified !')

    def _exec(self):
        eval('self._load%s()' % self.itemType.capitalize())
        self.sess.add(self.item)
        self.sess.commit()
        self.itemKey = self.item.getKey(self.enc)

    def _postExec(self):
        UBCmdSave.doDefault()

        ub_set_meta(self.item.getKeyProperty(), self.itemKey)
        vim.command('setl nomodified')
        
        evt = eval("UB%sSaveEvent('%s')" % (self.itemType=='tmpl' and 'Tmpl' or 'Post', self.itemKey));
        UBEventQueue.fireEvent(evt)
        UBEventQueue.processEvents()

    def _loadTmpl(self):
        '''Save the current template to local database
        '''
        self.itemKey = ub_get_meta('name').decode(self.enc)

        # Check if the given name is a reserved word
        ub_check_reserved_word(self.itemKey)

        tmpl = self.sess.query(Template).filter(Template.name==self.itemKey).first()
        if tmpl is None:
            tmpl = Template()
            tmpl.name = self.itemKey

        tmpl.content = "\n".join(vim.current.buffer[len(ub_get_tmpl_meta_data())+2:]).decode(self.enc)
        tmpl.description = ub_get_meta('description').decode(self.enc)

        self.item = tmpl

    def _loadPost(self):
        '''Save the current buffer to local database
        '''
        if self.itemKey is None:
            post = Post()
        else:
            post = self.sess.query(Post).filter(Post.id==self.itemKey).first()

        post.content = "\n".join(vim.current.buffer[len(ub_get_post_meta_data())+2:]).decode(self.enc)
        post.post_id = ub_get_meta('post_id')
        post.title = ub_get_meta('title').decode(self.enc)
        post.categories = ub_get_meta('categories').decode(self.enc)
        post.tags = ub_get_meta('tags').decode(self.enc)
        post.slug = ub_get_meta('slug').decode(self.enc)
        post.status = ub_get_meta('status').decode(self.enc)
        post.syntax = self.syntax

        self.item = post

    def _loadPage(self):
        '''Save the current page to local database
        '''
        if self.itemKey is None:
            page = Post()
            page.type = 'page'
        else:
            page = self.sess.query(Post).filter(Post.id==self.itemKey).first()

        page.content = "\n".join(vim.current.buffer[len(ub_get_page_meta_data())+2:]).decode(self.enc)
        page.post_id = ub_get_meta('post_id')
        page.title = ub_get_meta('title').decode(self.enc)
        page.slug = ub_get_meta('slug').decode(self.enc)
        page.status = ub_get_meta('status').decode(self.enc)
        page.syntax = self.syntax

        self.item = page

class UBCmdSend(UBCommand):
    ''' Send item
    '''
    def __init__(self, status=None):
        UBCommand.__init__(self, True)
        self.status = status is not None and status or ub_get_meta('status')
        self.publish = ub_check_status(self.status)
        self.item = None
        self.viewScopes = ['post_edit', 'page_edit'];
        self.postId = ub_get_meta('post_id')

    def _exec(self):
        eval('self._load%s()' % self.itemType.capitalize())
        if self.postId is None:
            self.postId = api.metaWeblog.newPost('', cfg.loginName, cfg.password, self.item, self.publish)
        else:
            api.metaWeblog.editPost(self.postId, cfg.loginName, cfg.password, self.item, self.publish)
        msg = "%s sent as %s !" % (self.itemType.capitalize(), self.status)
        print >> sys.stdout,msg

    def _postExec(self):
        UBCmdSend.doDefault()

        if self.postId != ub_get_meta('post_id'):
            ub_set_meta('post_id', self.postId)
        if self.status != ub_get_meta('status'):
            ub_set_meta('status', self.status)

        saveit = ub_get_option('ub_save_after_sent')
        if '1'==vim.eval('&modified') and saveit is not None and saveit.isdigit() and int(saveit) == 1:
            ub_save_item()
        
        evt = eval("UBPostSendEvent(%s)" % self.postId)
        UBEventQueue.fireEvent(evt)
        UBEventQueue.processEvents()

    def _loadPost(self):
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

    def _loadPage(self):
        '''Send the current page to the blog
        '''
        self.item = dict(\
            title = ub_get_meta('title'),
            description = ub_get_html(),
            wp_slug = ub_get_meta('slug'),
            post_type = 'page',
            page_status = self.status
        )

class UBCmdOpen(UBCommand):
    ''' Open an item
    '''
    def __init__(self, itemKey, itemType, scope='local', viewType=None):
        UBCommand.__init__(self)
        self.itemKey = itemType=='tmpl' and itemKey.decode(self.enc) or int(itemKey)
        self.itemType = itemType
        self.scope = scope
        self.viewType = viewType
        self.saveIt = ub_get_option('ub_save_after_opened', True)
        self.metaData = None
        self.item = None

    def _exec(self):
        eval("self._load%s%s()" % (self.scope.capitalize(), self.itemType.capitalize()))
        ub_wise_open_view('%s_edit' % self.itemType, self.viewType)
        self.metaData = self.item.getMetaDict(self.enc)
        ub_fill_meta_data(self.metaData)
        vim.current.buffer.append(self.item.content.encode(self.enc).split("\n"))

    def _postExec(self):
        UBCmdOpen.doDefault()

        vim.command('setl filetype=%s' % self.item.syntax)
        vim.command('setl wrap')
        vim.command('call UBClearUndo()')
        if self.itemType=='tmpl' or ub_is_id(self.item.id): vim.command('setl nomodified')
        vim.current.window.cursor = (len(self.metaData)+3, 0)

    def _loadLocalPost(self):
        '''Open local post
        '''
        self.item = self.sess.query(Post).filter(Post.id==self.itemKey).first()
        if self.item is None: raise UBException('No post found !')

    def _loadLocalPage(self):
        '''Open local page
        '''
        self.item = self.sess.query(Post).filter(Post.id==self.itemKey).filter(Post.type=='page').first()
        if self.item is None: raise UBException('No page found !')

    def _loadRemotePost(self):
        '''Open remote post
        '''
        self.item = self.sess.query(Post).filter(Post.post_id==self.itemKey).first()

        # Fetch the remote post if there is not a local copy
        if self.item is None:
            remote_post = api.metaWeblog.getPost(self.itemKey, cfg.loginName, cfg.password)
            self.item = Post()
            self.item.post_id = self.itemKey
            self.item.title = remote_post['title']
            self.item.content = remote_post['description']
            self.item.categories = ', '.join(remote_post['categories'])
            self.item.tags = remote_post['mt_keywords']
            self.item.slug = remote_post['wp_slug']
            self.item.status = remote_post['post_status']
            self.item.syntax = 'html'

            if self.saveIt is True:
                self.sess.add(self.item)
                self.sess.commit()

    def _loadRemotePage(self):
        '''Open remote page
        '''
        self.item = self.sess.query(Post).filter(Post.post_id==self.itemKey).filter(Post.type=='page').first()

        # Fetch the remote page if there is not a local copy
        if self.item is None:
            remote_page = api.wp.getPage('', self.itemKey, cfg.loginName, cfg.password)
            self.item = Post()
            self.item.type = 'page'
            self.item.post_id = self.itemKey
            self.item.title = remote_page['title']
            self.item.content = remote_page['description']
            self.item.slug = remote_page['wp_slug']
            self.item.status = remote_page['page_status']
            self.item.syntax = 'html'

            if self.saveIt is True:
                self.sess.add(self.item)
                self.sess.commit()

    def _loadLocalTmpl(self):
        '''Open template
        '''
        self.item = self.sess.query(Template).filter(Template.name==self.itemKey).first()
        if self.item is None: raise UBException('No template found !')
        self.item.syntax = 'html'

class UBCmdPreview(UBCommand):
    ''' Preview command
    '''
    def __init__(self, tmpl=None):
        UBCommand.__init__(self, True)
        self.tmpl = tmpl is not None and tmpl or ub_get_option('ub_default_template')
        self.viewScopes = ['post_edit', 'page_edit']

    def _exec(self):
        prv_url = ''
        if self.tmpl in ['private', 'publish', 'draft']:
            ub_send_item(self.tmpl)

            if ub_is_view('page_edit'):
                prv_url = "%s?page_id=%s&preview=true"
            else:
                prv_url = "%s?p=%s&preview=true"

            prv_url = prv_url % (cfg.url, ub_get_meta('post_id'))
        else:
            template = self.sess.query(Template).filter(Template.name==self.tmpl.decode(self.enc)).first()
            if template is None:
                raise UBException("Template '%s' is not found !" % self.tmpl)

            tmpl_str = template.content.encode(self.enc)

            draft = {}
            draft['title'] = ub_get_meta('title')
            draft['content'] = ub_get_html()

            tmpfile = tempfile.mktemp(suffix='.html')
            fp = open(tmpfile, 'w')
            fp.write(tmpl_str % draft)
            fp.close()
            prv_url = "file://%s" % tmpfile

        webbrowser.open(prv_url)

class UBCmdDelete(UBCommand):
    def __init__(self, itemType, itemKey, scope='local'):
        UBCommand.__init__(self)
        self.itemType = itemType
        self.itemKey = itemType=='tmpl' and itemKey or int(itemKey)
        self.scope = scope
        self.itemTypeName = ub_get_item_type_name(self.itemType)
        self.itemName = self.itemKey

        self.item = None
        if self.itemType == 'tmpl':
            self.item = self.sess.query(Template).filter(Template.name==self.itemKey.decode(self.enc)).first()
        elif self.scope=='local':
            self.item = self.sess.query(Post).filter(Post.type==self.itemType).filter(Post.id==self.itemKey).first()

    def _preExec(self):
        UBCmdDelete.doDefault()
        # When deleting local items, check if it exists
        if (self.scope=='local' or self.itemType=='tmpl'):
            if self.item is None:
                raise UBException('Cannot find %s by key value %s !' % (self.itemTypeName,self.itemKey))
            else:
                self.itemName = self.item.getName(self.enc)
        # Ask for confirmation
        choice = vim.eval("confirm('Are you sure to delete %s %s \"%s\" ?', '&Yes\n&No')" % (self.scope.encode(self.enc), self.itemTypeName.encode(self.enc), self.itemName))
        if choice != '1': raise UBException('Deletion canceled !')

    def _exec(self):
        try:
            if self.itemType == 'tmpl':
                self.sess.query(Template).filter(Template.name==self.itemKey.decode(self.enc)).delete()
                UBEventQueue.fireEvent(UBTmplDelEvent(self.itemKey))
            else:
                if self.scope=='remote':
                    if self.itemType=='page':
                        api.wp.deletePage('', cfg.loginName, cfg.password, self.itemKey)
                    else:
                        api.metaWeblog.deletePost('', self.itemKey, cfg.loginName, cfg.password)
                    UBEventQueue.fireEvent(UBRemotePostDelEvent(self.itemKey))
                else:
                    self.sess.query(Post).filter(Post.type==self.itemType).filter(Post.id==self.itemKey).delete()
                    UBEventQueue.fireEvent(UBLocalPostDelEvent(self.itemKey))
        except Exception,e:
            self.sess.rollback()
            self.sess.close()
            raise e
        else:
            self.sess.commit()
            UBEventQueue.processEvents()
            print >> sys.stdout, '%s %s "%s" was deleted !' % (self.scope.capitalize().encode(self.enc), self.itemTypeName.encode(self.enc), self.itemName)

class UBCmdOpenItemUnderCursor(UBCommand):
    def __init__(self, viewType=None):
        UBCommand.__init__(self)
        self.viewType = viewType
        self.viewScopes = ['list']

        lineParts = vim.current.line.split()
        if ub_is_cursorline_valid('template'):
            self.itemKey = lineParts[0]
        elif ub_is_cursorline_valid('general'):
            if self.scope == 'local':
                self.itemKey = int(lineParts[0])
                self.itemType = self.sess.query(Post.type).filter(Post.id==self.itemKey).first()[0]
            else:
                self.itemKey = int(lineParts[1])
        else: raise UBException('This is not an item !')

    def _exec(self):
        cmd = UBCmdOpen(itemKey=self.itemKey, itemType=self.itemType, scope=self.scope, viewType=self.viewType)
        cmd.execute()

class UBCmdDelItemUnderCursor(UBCommand):
    def __init__(self):
        UBCommand.__init__(self)
        self.viewScopes = ['list']
        self.postId = None

        lineParts = vim.current.line.split()
        if ub_is_cursorline_valid('template'):
            self.itemKey = lineParts[0]
        elif ub_is_cursorline_valid('general'):
            self.itemKey = int(lineParts[0])
            self.postId = int(lineParts[1])
            rslt = self.sess.query(Post.type).filter(
                    or_(
                        and_(Post.id>0, Post.id==self.itemKey), 
                        and_(Post.post_id>0, Post.post_id==self.postId)
                    )
                ).first()
            self.itemType = rslt is not None and rslt[0] or self.itemType
        else: raise UBException('This is not an item !')

    def _exec(self):
        if ub_is_id(self.itemKey, True) or self.itemType=='tmpl':
            ub_del_item(self.itemType, self.itemKey, 'local')
        if ub_is_id(self.postId, True):
            ub_del_item(self.itemType, self.postId, 'remote')

class UBCmdNew(UBCommand):
    def __init__(self, itemType='post', mixed='markdown'):
        UBCommand.__init__(self, True)

        self.itemType = itemType
        self.syntax = mixed
        if self.itemType=='tmpl':
            self.itemKey = mixed
            self.syntax = 'html'

    def _exec(self):
        eval('self._createNew%s()' % self.itemType.capitalize())

    def _createNewPost(self):
        item = Post()
        metaData = item.getMetaDict()
        metaData['categories'] = self.__getCategories()
        metaData['status'] = 'draft'

        ub_wise_open_view('post_edit')
        ub_fill_meta_data(metaData)
        self.__appendPromotionLink()

    def _createNewPage(self):
        item = Post()
        item.type = 'page'
        metaData = item.getMetaDict()
        metaData['status'] = 'draft'

        ub_wise_open_view('page_edit')
        ub_fill_meta_data(metaData)

    def _createNewTmpl(self):
        # Check if the given name is a reserved word
        ub_check_reserved_word(self.itemKey)
        # Check if the given name is already existing
        if self.sess.query(Template).filter(Template.name==self.itemKey.decode(self.enc)).first() is not None:
            self.sess.close()
            raise UBException('Template "%s" exists !' % self.itemKey)

        item = Template()
        metaData = item.getMetaDict()
        metaData['name'] = self.itemKey
        ub_wise_open_view('tmpl_edit')
        ub_fill_meta_data(metaData)
        fw = '''<html>
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

    def _postExec(self):
        UBCmdNew.doDefault()

        vim.command('setl filetype=%s' % self.syntax)
        vim.command('setl nowrap')
        vim.command('call UBClearUndo()')
        vim.command('setl nomodified')
        if self.itemType=='tmpl': vim.current.window.cursor = (3, len(vim.current.buffer[2])-1)
        else: vim.current.window.cursor = (4, len(vim.current.buffer[3])-1)

    def __getCategories(self):
        cats = api.metaWeblog.getCategories('', cfg.loginName, cfg.password)
        return ', '.join([cat['description'].encode(self.enc) for cat in cats])

    def __appendPromotionLink(self):
        doit = ub_get_option('ub_append_promotion_link')
        if doit is not None and doit.isdigit() and int(doit) == 1:
            if self.syntax == 'markdown':
                link = 'Posted via [UltraBlog.vim](%s).' % cfg.homepage
            else:
                link = 'Posted via <a href="%s">UltraBlog.vim</a>.' % cfg.homepage
            vim.current.buffer.append(link)

class UBCmdBlogThis(UBCommand):
    def __init__(self, itemType='post', toSyntax=None, fromSyntax=None):
        UBCommand.__init__(self, True)

        self.itemType = itemType
        self.toSyntax = toSyntax is not None and toSyntax or self.syntax
        self.syntax = fromSyntax is not None and fromSyntax or self.toSyntax

    def _preExec(self):
        UBCmdBlogThis.doDefault()
        self.checkSyntax(self.toSyntax)

    def _exec(self):
        bf = vim.current.buffer[:]
        ub_new_item(self.itemType, self.toSyntax)
        regex_meta_end = re.compile('^\s*-->')
        for line_num in range(0, len(vim.current.buffer)):
            line = vim.current.buffer[line_num]
            if regex_meta_end.match(line): break
        vim.current.buffer.append(ub_convert_str("\n".join(bf), self.syntax, self.toSyntax, self.enc).split("\n"), line_num+1)

class UBCmdConvert(UBCommand):
    def __init__(self, toSyntax, fromSyntax=None):
        UBCommand.__init__(self, True)
        self.toSyntax = toSyntax
        self.syntax = fromSyntax is not None and fromSyntax or self.syntax

    def _preExec(self):
        UBCmdConvert.doDefault()
        self.checkSyntax(self.toSyntax)

    def _exec(self):
        content = ub_get_content()
        content = ub_convert_str(content, self.syntax, self.toSyntax, self.enc)
        ub_set_content(content.split("\n"))
        vim.command('setl filetype=%s' % self.toSyntax)

class UBCmdRefresh(UBCommand):
    def __init__(self):
        UBCommand.__init__(self)
        self.viewScopes = ['list','edit']

    def _exec(self):
        if self.viewName == 'search_result_list':
            kws = ub_get_bufvar('ub_keywords')
            pno = ub_get_bufvar('page_no')
            ub_find(pno, *kws)
        elif ub_is_view_of_type('list'):
            psize = ub_get_bufvar('page_size')
            pno = ub_get_bufvar('page_no')
            ub_list_items(self.itemType, self.scope, psize, pno)
        elif ub_is_view_of_type('edit'):
            itemKey = self.itemType=='tmpl' and ub_get_meta('name') or ub_get_meta('id')
            if itemKey is not None:
                modified = '1'==vim.eval('&modified')
                vim.command('setl nomodified')
                try:
                    ub_open_item(self.itemType, itemKey, 'local')
                except Exception, e:
                    vcmd = modified is True and 'setl modified' or 'setl nomodified'
                    vim.command(vcmd)
                    print >> sys.stderr,str(e)
            else:
                raise UBException('Cannot find key value of the current buffer !')

