__author__ = 'corona'

import sqlite3
try:
    import cPickle as pickle
except ImportError:
    import pickle

def inject_cookies_into_chrome(session, chrome_cookie_file):

    conn = sqlite3.connect(chrome_cookie_file)
    cookies = {}
    cookies_list = []

    #fh = xbmcvfs.File(session_file, 'rb')
    # fh = open(session_file, 'rb')
    # content = fh.read()
    # fh.close()
    # session = pickle.loads(content)

    for cookie in session.cookies:
        #print cookie
        host_key = cookie.domain
        name = cookie.name
        value = cookie.value
        path = cookie.path
        expires = cookie.expires
        encrypted_value = ""
        sql = 'insert or replace into cookies (host_key, name, value, path, secure, httponly, has_expires, expires_utc, last_access_utc, encrypted_value) values (%s, %s, %s, %s, %d, %d, %d, %d, %d, %s );' % (
            "'"+host_key+"'"        if host_key is not None else "",
            "'"+name+"'"            if name is not None else "",
            "'"+value+"'"           if value is not None else "",
            "'"+path+"'"            if path is not None else "",
            0,
            0,
            int(expires)            if expires is not None else 0,
            0,
            0,
            "'"+encrypted_value+"'" if encrypted_value is not None else "NULL"
        )
        conn.execute(sql)

    conn.commit()
    conn.close()

