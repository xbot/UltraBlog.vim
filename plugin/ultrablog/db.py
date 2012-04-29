#!/usr/bin/env python

import xmlrpclib,socket
import util as u

try:
    import sqlalchemy
    from sqlalchemy import Table, Column, Integer, Text, String
    from sqlalchemy.ext.declarative import declarative_base
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.sql import union_all,select,case,and_,or_,not_
    from sqlalchemy.exc import OperationalError

    Base = declarative_base()
    Session = sessionmaker()

    class Item(object):
        def getKey(self, encoding=None): pass
        def getName(self, encoding=None): pass
        def getKeyProperty(self): pass
        def getNameProperty(self): pass
        def getMetaDict(self, encoding=None): pass
        def _encode(self, val, encoding): return encoding is not None and val.encode(encoding) or val

    class Post(Base,Item):
        __tablename__ = 'post'

        id = Column('id', Integer, primary_key=True)
        post_id = Column('post_id', Integer)
        title = Column('title', String(256))
        categories = Column('categories', Text)
        tags = Column('tags', Text)
        content = Column('content', Text)
        slug = Column('slug', Text)
        syntax = Column('syntax', String(64), nullable=False, default='markdown')
        type = Column('type', String(32), nullable=False, default='post')
        status = Column('status', String(32), nullable=False, default='draft')

        def getKey(self, encoding=None):
            return self.id
        def getName(self, encoding=None):
            return encoding is not None and self.title.encode(encoding) or self.title
        def getKeyProperty(self):
            return 'id'
        def getNameProperty(self):
            return 'title'
        def getMetaDict(self, encoding=None):
            meta = dict(\
                id = self.id is not None and self.id or 0,
                post_id = self.post_id is not None and self.post_id or 0,
                title = self.title is not None and self._encode(self.title, encoding) or '',
                categories = self.categories is not None and self._encode(self.categories, encoding) or '',
                tags = self.tags is not None and self._encode(self.tags, encoding) or '',
                slug = self.slug is not None and self._encode(self.slug, encoding) or '',
                status = self.status is not None and self._encode(self.status, encoding) or '')
            if self.type=='page': del meta['categories'], meta['tags']
            return meta

    class Template(Base,Item):
        __tablename__ = 'template'

        name = Column('name', String(32), primary_key=True)
        description = Column('description', String(256))
        content = Column('content', Text)

        def getKey(self, encoding=None):
            return self._encode(self.name, encoding)
        def getName(self, encoding=None):
            return self._encode(self.name, encoding)
        def getKeyProperty(self):
            return 'name'
        def getNameProperty(self):
            return 'name'
        def getMetaDict(self, encoding=None):
            return dict(\
                name = self.name is not None and self._encode(self.name, encoding) or '',
                description = self.description is not None and self._encode(self.description, encoding) or '')

except ImportError, e:
    sqlalchemy = None
    Base = None
    Session = None
    Post = None
    Template = None
except:pass

def ub_upgrade(db):
    conn = db.connect()
    stmt = select([Post.type]).limit(1)
    try:
        conn.execute(stmt)
    except OperationalError:
        sql = "alter table post add type varchar(32) not null default 'post'"
        conn.execute(sql)

    stmt = select([Post.status]).limit(1)
    try:
        conn.execute(stmt)
    except OperationalError:
        sql = "alter table post add status varchar(32) not null default 'draft'"
        conn.execute(sql)

    conn.close()

def ub_init_template():
    sess = Session()
    tmpl = sess.query(Template).filter(Template.name=='default').first()
    if tmpl is None:
        tmpl = Template()
        tmpl.name = 'default'
        tmpl.description = 'The default template for previewing drafts.'
        tmpl.content = \
'''<html>
<head>
    <meta http-equiv="Content-Type" content="text/html; charset=utf-8">
    <title>%(title)s</title>
    <style>
        body
        {
            font-family: "DejaVu Sans YuanTi","YaHei Consolas Hybrid","Microsoft YaHei";
            font-size: 14px;
            background-color: #D9DADC;
        }

        code
        {
            font-family: "Monaco","YaHei Consolas Hybrid";
            border: 1px solid #333;
            background-color: #DCDCDC;
            padding: 0px 3px;
            margin: 0px 5px;
        }

        pre
        {
            font-family: "Monaco","YaHei Consolas Hybrid";
            border: 1px solid #333;
            background-color: #B7D0DB;
            padding: 10px;
        }

        table,td,th {border-collapse: collapse;}
        table
        {
            border-left: 1px solid #333;
            border-bottom: 1px solid #333;
        }
        td,th
        {
            border-top: 1px solid #333;
            border-right: 1px solid #333;
        }
        th {background-color:#ebeff9;}
        td {padding: 5px;}

        blockquote {border: 1px dashed #333; background-color: #B7D0DB; padding: 10px;}
        img {margin-left:auto;margin-right:auto;padding:10px;border:1px solid #000;-moz-box-shadow:3px 3px 4px #000;-webkit-box-shadow:3px 3px 4px #000;box-shadow:3px 3px 4px #000;background:#fff;filter:progid:DXImageTransform.Microsoft.Shadow(Strength=4,Direction=135,Color='#000000');}
        a img{padding:10px;border:1px solid #000;-moz-box-shadow:3px 3px 4px #000;-webkit-box-shadow:3px 3px 4px #000;box-shadow:3px 3px 4px #000;background:#fff;filter:progid:DXImageTransform.Microsoft.Shadow(Strength=4,Direction=135,Color='#000000');}

        .container {width: 80%%;margin:0px auto;padding:20px;background-color: #FFFFFF;}
        .title {font-size: 24px; font-weight: bold;}
        .content {}
    </style>
</head>
<body>
    <div class="container">
        <div class="title">%(title)s</div>
        <div class="content">
            %(content)s
        </div>
    </div>
</body>
</html>'''
        sess.add(tmpl)
        sess.commit()
        sess.close()

def ub_set_mode(db):
    '''Set editor mode according to the option ub_editor_mode
    '''
    editor_mode = u.ub_get_option('ub_editor_mode')
    if '1' == editor_mode:
        Session.configure(bind=db)
        Base.metadata.create_all(db)
        ub_init_template()

cfg = None
try:
    cfg = u.ub_get_blog_settings()
except KeyError,e:
    msg = _('Missing key %s in the settings list of UltraBlog.vim !') % str(e)
    u.ub_echoerr(msg)
except:
    pass

try:
    socket.setdefaulttimeout(u.ub_get_option('ub_socket_timeout'))
    api = xmlrpclib.ServerProxy(cfg.xmlrpc)
    dbe = sqlalchemy.create_engine("sqlite:///%s" % cfg.dbf)
    dbg_enabled = u.ub_get_option('ub_debug')
    if dbg_enabled == 1: dbe.echo = True

    Session.configure(bind=dbe)
    Base.metadata.create_all(dbe)

    ub_upgrade(dbe)
    ub_init_template()
except:
    api = None
    dbe  = None
