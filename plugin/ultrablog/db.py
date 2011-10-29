#!/usr/bin/env python

import os,xmlrpclib,sys
import util

try:
    import sqlalchemy
    from sqlalchemy import Table, Column, Integer, Text, String
    from sqlalchemy.ext.declarative import declarative_base
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.sql import union_all,select,case,and_,or_,not_
    from sqlalchemy.exc import OperationalError

    Base = declarative_base()
    Session = sessionmaker()

    class Post(Base):
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

    class Template(Base):
        __tablename__ = 'template'

        name = Column('name', String(32), primary_key=True)
        description = Column('description', String(256))
        content = Column('content', Text)

except ImportError, e:
    sqlalchemy = None
    Base = None
    Session = None
    Post = None
    Template = None
except Exception:
    pass

def ub_upgrade():
    if db is not None:
        conn = db.connect()
        stmt = select([Post.type]).limit(1)
        try:
            result = conn.execute(stmt)
        except OperationalError:
            sql = "alter table post add type varchar(32) not null default 'post'"
            conn.execute(sql)

        stmt = select([Post.status]).limit(1)
        try:
            result = conn.execute(stmt)
        except OperationalError:
            sql = "alter table post add status varchar(32) not null default 'draft'"
            conn.execute(sql)

        conn.close()

def ub_init_template():
    if db is not None:

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

def ub_set_mode():
    '''Set editor mode according to the option ub_editor_mode
    '''
    editor_mode = util.ub_get_option('ub_editor_mode')
    if '1' == editor_mode:
        Session.configure(bind=db)
        Base.metadata.create_all(db)
        ub_init_template()

cfg = None
try:
    cfg = util.ub_get_blog_settings()
except KeyError,e:
    print >> sys.stdout,'Missing key %s in the settings list of UltraBlog.vim !' % str(e)
except:
    pass

try:
    api = xmlrpclib.ServerProxy(cfg.xmlrpc)
    db = sqlalchemy.create_engine("sqlite:///%s" % cfg.dbf)

    Session.configure(bind=db)
    Base.metadata.create_all(db)

    ub_upgrade()
    ub_init_template()
except:
    api = None
    db  = None
