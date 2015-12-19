# -*- coding: utf-8 -*-
'''
    flask.ext.session_management
    ---------------
    This module provides session management for Flask.

    :copyright: (c) 2015 by Nam Pham.
    :license: MIT.
'''

__version_info__ = ('0', '1', '0')
__version__ = '.'.join(__version_info__)
__author__ = 'NamPNQ'
__license__ = 'MIT'
__copyright__ = '(c) 2015 by Nam Pham'
__all__ = ['SessionManager']

import pickle
from datetime import timedelta
from uuid import uuid4
from redis import Redis, ConnectionPool
from werkzeug.datastructures import CallbackDict
from flask.sessions import SessionInterface, SessionMixin


class _Missing(object):

    def __repr__(self):
        return 'no value'

    def __reduce__(self):
        return '_missing'

_missing = _Missing()


class RedisSession(CallbackDict, SessionMixin):

    def __init__(self, initial=None, sid=None, new=False):
        def on_update(self):
            self.modified = True
        CallbackDict.__init__(self, initial, on_update)
        self.sid = sid
        self.new = new
        self.modified = False
        self.u_flag = None

    def __setitem__(self, key, val):
        super(RedisSession, self).__setitem__(key, val)
        if key == 'user_id':
            self.u_flag = 'login'
            self.user_id = val

    def pop(self, key, default=_missing):
        if default is _missing:
            rv = super(RedisSession, self).pop(key)
        else:
            rv = super(RedisSession, self).pop(key, default)
        if key == 'user_id':
            self.u_flag = 'logout'
            self.user_id = rv
        return rv


class RedisSessionInterface(SessionInterface):
    serializer = pickle
    session_class = RedisSession

    def __init__(self, redis=None, prefix='session:'):
        if redis is None:
            redis = Redis()
        self.redis = redis
        self.prefix = prefix

    def generate_sid(self):
        return str(uuid4())

    def get_redis_expiration_time(self, app, session):
        if session.permanent:
            return app.permanent_session_lifetime
        return timedelta(days=1)

    def open_session(self, app, request):
        sid = request.cookies.get(app.session_cookie_name)
        if not sid:
            sid = self.generate_sid()
            return self.session_class(sid=sid, new=True)
        val = self.redis.get(self.prefix + sid)
        if val is not None:
            data = self.serializer.loads(val)
            return self.session_class(data, sid=sid)
        return self.session_class(sid=sid, new=True)

    def save_session(self, app, session, response):
        from flask import request

        domain = self.get_cookie_domain(app)
        ua = request.user_agent
        ip = request.remote_addr
        session_info = self.redis.get(self.prefix + session.sid + ':info')
        if not session_info:
            self.redis.set(self.prefix + session.sid + ':info',
                           self.serializer.dumps({'ip': ip,
                                                  'platform': ua.platform,
                                                  'browser': ua.browser,
                                                  'version': ua.version,
                                                  'language': ua.language}))
        if session.u_flag == 'login':
            self.redis.sadd(self.prefix + 'user:' + session.user_id,
                            session.sid)
        elif session.u_flag == 'logout':
            self.redis.srem(self.prefix + 'user:' + session.user_id,
                            session.sid)
        if not session:
            self.redis.delete(self.prefix + session.sid)
            if session.modified:
                response.delete_cookie(app.session_cookie_name,
                                       domain=domain)
            return
        redis_exp = self.get_redis_expiration_time(app, session)
        cookie_exp = self.get_expiration_time(app, session)
        val = self.serializer.dumps(dict(session))
        self.redis.setex(self.prefix + session.sid, val,
                         int(redis_exp.total_seconds()))
        response.set_cookie(app.session_cookie_name, session.sid,
                            expires=cookie_exp, httponly=True,
                            domain=domain)


class SessionManager():
    def __init__(self, prefix='session:', app=None):
        self.prefix = prefix
        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        pool = ConnectionPool(
            host=app.config.get('SM_REDIS_HOST', 'localhost'),
            port=app.config.get('SM_REDIS_PORT', 6379),
            db=app.config.get('SM_REDIS_DB', 0))
        self.redis = Redis(connection_pool=pool)
        self.session_interface = RedisSessionInterface(redis=self.redis,
                                                       prefix=self.prefix)
        self.serializer = self.session_interface.serializer
        app.session_interface = self.session_interface

    def get_user_sessions(self, uid):
        return self.redis.smembers('%suser:%s' % (self.prefix, uid))

    def get_session_info(self, sid):
        val = self.redis.get('%s%s:info' % (self.prefix, sid))
        return self.serializer.loads(val)

    def destroy_session(self, sid):
        val = self.redis.get('%s%s' % (self.prefix, sid))
        val = self.serializer.loads(val) if val else {}
        if 'user_id' in val.keys():
            self.redis.srem(self.prefix + 'user:' + val['user_id'], sid)
        self.redis.delete('%s%s' % (self.prefix, sid))
