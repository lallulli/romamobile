from __future__ import print_function
import logging
from django.contrib.sessions.backends import signed_cookies
from django.contrib.sessions.backends import cached_db as stored_backend


class SessionStore(object):
    def __init__(self, session_key=None):
        if session_key is None:
            ss = signed_cookies.SessionStore()
        elif len(session_key) == 32:
            ss = stored_backend.SessionStore(session_key)
        else:
            so = signed_cookies.SessionStore(session_key)
            ss = stored_backend.SessionStore()
            ss.update(so._session)
        object.__setattr__(self, '_store', ss)

    def __getattr__(self, item):
        return getattr(self._store, item)

    def __setattr__(self, key, value):
        setattr(self._store, key, value)

    def __contains__(self, key):
        return self._store.__contains__(key)

    def __setitem__(self, key, value):
        self._store.__setitem__(key, value)

    def __delitem__(self, key):
        self._store.__delitem__(key)

    def __getitem__(self, key):
        return self._store.__getitem__(key)


# At bottom to avoid circular import
# from django.contrib.sessions.models import Session


