#!/usr/bin/env python3
"""Load/refresh an explicitly configured Auth session; never use MCP credentials."""
import base64
from contextlib import contextmanager
import json
import os
from pathlib import Path
import tempfile
import time
import urllib.error
import urllib.request


class SessionError(ValueError):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise SessionError('Auth redirects are refused')


def session_path(profile):
    value = profile.get('credentials_file')
    return Path(value).expanduser() if value else None


def read_session(profile, base):
    path = session_path(profile)
    if path is None or not path.exists():
        return {}
    stat = path.stat()
    if os.name != 'nt' and (stat.st_mode & 0o077 or stat.st_uid != os.getuid()):
        raise SessionError('Session file must be owned by the current user with mode 0600')
    value = json.loads(path.read_text())
    if not isinstance(value, dict) or value.get('project_url', '').rstrip('/') != base.rstrip('/'):
        raise SessionError('Session file is bound to a different project URL')
    return value


def write_session(profile, value):
    path = session_path(profile)
    if path is None:
        raise SessionError('Set credentials_file to save an Auth session')
    path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, mode='w', delete=False) as file:
        json.dump(value, file)
        file.flush()
        os.fsync(file.fileno())
        temp = file.name
    os.chmod(temp, 0o600)
    os.replace(temp, path)


def expires_at(value):
    try:
        payload = value['access_token'].split('.')[1]
        return float(json.loads(base64.urlsafe_b64decode(payload+'='*(-len(payload) % 4)))['exp'])
    except (KeyError, ValueError, IndexError):
        return 0


@contextmanager
def refresh_lock(profile):
    path = session_path(profile)
    lock = Path(str(path)+'.refresh-lock')
    deadline = time.monotonic()+35
    while True:
        try:
            lock.mkdir(mode=0o700)
            break
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise SessionError('Another process holds the Auth refresh lock; retry or check the lock owner')
            time.sleep(0.1)
    try:
        yield
    finally:
        lock.rmdir()


def auth_request(base, key, path, body, require_session=False):
    if path not in ('/otp','/verify','/token?grant_type=password','/token?grant_type=refresh_token'):
        raise SessionError('Unsupported Auth endpoint')
    if key.startswith('sb_secret_'):
        raise SessionError('Use a publishable key for Auth')
    if key.count('.') == 2:
        try:
            payload=key.split('.')[1]
            if json.loads(base64.urlsafe_b64decode(payload+'='*(-len(payload)%4))).get('role') != 'anon':
                raise SessionError('Use a publishable or anon project key for Auth')
        except (ValueError,KeyError):
            raise SessionError('Invalid public project key')
    req = urllib.request.Request(base.rstrip('/')+'/auth/v1'+path,
                                 data=json.dumps(body).encode(), method='POST',
                                 headers={'apikey':key,'Content-Type':'application/json'})
    try:
        with urllib.request.build_opener(NoRedirect()).open(req, timeout=30) as response:
            session = json.load(response)
    except urllib.error.HTTPError as error:
        raise SessionError(f'Auth returned HTTP {error.code}; sign in again if the session expired or was revoked')
    except (urllib.error.URLError, TimeoutError):
        raise SessionError('Auth connection failed; check DNS, TLS and network')
    if not isinstance(session, dict) or (require_session and (not session.get('access_token') or not session.get('refresh_token'))):
        raise SessionError('Auth returned an incomplete session')
    return session


def auth_token(base, key, grant, body):
    if grant not in ('password','refresh_token'):
        raise SessionError('Unsupported Auth grant')
    return auth_request(base,key,'/token?grant_type='+grant,body,True)


def saved_session(base, key, session):
    user = session.get('user', {})
    return {'project_url':base.rstrip('/'),'apikey':key,'access_token':session['access_token'],
            'refresh_token':session['refresh_token'],
            'principal_id':user.get('id'),'email':user.get('email')}


def credentials(profile, base):
    key = os.environ.get(profile.get('apikey_env','COMPANY_SUPABASE_API_KEY'), '')
    token = os.environ.get(profile.get('jwt_env','COMPANY_SUPABASE_USER_JWT'), '')
    if key and token:
        return key, token
    current = read_session(profile, base)
    key = key or current.get('apikey', '')
    if token:  # Explicit environment tokens are not replaced by file sessions.
        return key, token
    if not current.get('access_token'):
        return key, ''
    if expires_at(current) > time.time()+60:
        return key, current['access_token']
    if not current.get('refresh_token'):
        raise SessionError('Session expired without a refresh token; sign in again')
    with refresh_lock(profile):
        current = read_session(profile, base)
        if expires_at(current) <= time.time()+60:
            session = auth_token(base, key, 'refresh_token', {'refresh_token':current['refresh_token']})
            current = saved_session(base, key, session)
            write_session(profile, current)
    return key, current['access_token']
