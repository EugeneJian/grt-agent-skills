#!/usr/bin/env python3
"""Receive the employee's browser login on loopback; never log URL tokens."""
import argparse
import html
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import socket
import sys
import threading
import urllib.parse

import api_session
import query_data


def complete_session(profile, base, key, email, refresh):
    if not isinstance(refresh,str) or not 8 <= len(refresh) <= 4096:
        raise ValueError('Invalid callback session')
    session=api_session.auth_token(base,key,'refresh_token',{'refresh_token':refresh})
    user=session.get('user',{})
    if user.get('email','').casefold()!=email.casefold() or not user.get('email_confirmed_at'):
        raise ValueError('Callback does not match the verified employee email')
    if query_data.jwt_role(session.get('access_token',''))!='authenticated':
        raise ValueError('Expected an employee Auth session')
    saved=api_session.saved_session(base,key,session)
    api_session.write_session(profile,saved)


def page(email, nonce):
    return '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>公司数据只读登录</title>
<style>body{font:17px system-ui;max-width:660px;margin:100px auto;padding:24px;color:#163043}button{padding:12px 20px;font:inherit}p{line-height:1.7}</style>
<h1>公司数据只读登录</h1><p>EMAIL</p><p id="status">正在接收登录结果…</p>
<button id="send" hidden>发送新的登录邮件</button>
<script nonce="NONCE">
const csrf=CSRF;
const params=new URLSearchParams(location.hash.slice(1));
let refresh=params.get('refresh_token');
const hadError=params.has('error');
history.replaceState(null,'',location.pathname);
const status=document.getElementById('status'),button=document.getElementById('send');
async function post(path,data){const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({csrf,...data})});if(!r.ok)throw Error('failed');return r.json();}
if(refresh){post('/complete',{refresh_token:refresh}).then(()=>{refresh=null;status.textContent='登录已安全保存，可以返回聊天继续验证。';}).catch(()=>{refresh=null;status.textContent='登录链接已过期或会话不匹配，请重新发送邮件。';button.hidden=false;});}
else{status.textContent=hadError?'链接已使用或过期，请重新发送邮件。':'接收器已就绪。请刷新之前的登录回调标签页，或重新发送邮件。';button.hidden=false;}
button.onclick=async()=>{button.disabled=true;try{await post('/request-email',{});status.textContent='已请求登录邮件。请点击邮件中的最新登录链接。';}catch{status.textContent='请求失败或过于频繁，请稍后再试。';}finally{button.disabled=false;}};
</script></html>'''.replace('EMAIL',html.escape(email)).replace('NONCE',nonce).replace('CSRF',json.dumps(nonce))


class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):
        pass  # Browser callback URLs and Auth data must never enter request logs.

    def reply(self,status,body,content_type='application/json'):
        data=body.encode()
        self.send_response(status)
        self.send_header('Content-Type',content_type+'; charset=utf-8')
        self.send_header('Content-Length',str(len(data)))
        self.send_header('Cache-Control','no-store')
        self.send_header('Referrer-Policy','no-referrer')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Content-Security-Policy',"default-src 'none'; script-src 'nonce-"+self.server.nonce+"'; style-src 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'; form-action 'self'")
        self.end_headers()
        self.wfile.write(data)

    def trusted_host(self):
        return self.headers.get('Host') in self.server.hosts

    def do_GET(self):
        if not self.trusted_host():
            return self.reply(403,'{}')
        if self.path not in ('/','/callback'):
            return self.reply(404,'{}')
        self.reply(200,page(self.server.email,self.server.nonce),'text/html')

    def do_POST(self):
        if not self.trusted_host() or self.headers.get('Origin') not in self.server.origins:
            return self.reply(403,'{}')
        try:
            size=int(self.headers.get('Content-Length','0'))
            if not 0<size<=16384:
                return self.reply(413,'{}')
            value=json.loads(self.rfile.read(size))
            if not isinstance(value,dict) or value.get('csrf')!=self.server.nonce:
                return self.reply(403,'{}')
            if self.path=='/complete':
                complete_session(self.server.profile,self.server.base,self.server.key,self.server.email,value.get('refresh_token'))
                self.reply(200,'{"ok":true}')
                print('Employee Auth session saved with mode 0600. No tokens logged.',flush=True)
                threading.Timer(2,self.server.finish).start()
            elif self.path=='/request-email':
                api_session.auth_request(self.server.base,self.server.key,'/otp',{'email':self.server.email,'create_user':True})
                self.reply(200,'{"ok":true}')
            else:
                self.reply(404,'{}')
        except (ValueError,OSError,KeyError):
            self.reply(400,'{"error":"Authentication could not be completed"}')


class IPv6Server(ThreadingHTTPServer):
    address_family=socket.AF_INET6
    def server_bind(self):
        self.socket.setsockopt(socket.IPPROTO_IPV6,socket.IPV6_V6ONLY,1)
        super().server_bind()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',default=os.environ.get('COMPANY_SQL_CONFIG',str(Path.home()/'.config/company-sql/profiles.json')))
    parser.add_argument('--profile',default='cloud')
    parser.add_argument('--email',required=True)
    parser.add_argument('--port',type=int,default=3000)
    args=parser.parse_args()
    try:
        if not 1<=args.port<=65535:
            raise ValueError('Callback port must be 1-65535')
        profile=query_data.configured_profile(query_data.read_json(args.config),args.profile)
        if profile['engine']!='supabase_api' or not api_session.session_path(profile):
            raise ValueError('Choose an API profile with credentials_file')
        base=profile.get('url') or os.environ.get(profile.get('url_env','COMPANY_SUPABASE_URL'),'')
        parsed=urllib.parse.urlsplit(base)
        if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ('','/'):
            raise ValueError('Use an HTTPS project origin')
        key=api_session.read_session(profile,base).get('apikey') or os.environ.get(profile.get('apikey_env','COMPANY_SUPABASE_API_KEY'),'')
        if not key or key.startswith('sb_secret_') or query_data.jwt_role(key) not in (None,'anon'):
            raise ValueError('Provide a publishable or anon key')
        servers=[ThreadingHTTPServer(('127.0.0.1',args.port),Handler)]
        if socket.has_ipv6:
            try:servers.append(IPv6Server(('::1',args.port),Handler))
            except OSError:
                for server in servers:server.server_close()
                raise ValueError('IPv6 callback port unavailable; choose another port or stop the existing listener')
        stopped=threading.Event()
        nonce=secrets.token_urlsafe(32)
        for server in servers:
            server.profile,server.base,server.key,server.email=profile,base,key,args.email
            server.nonce=nonce
            server.hosts={f'localhost:{args.port}',f'127.0.0.1:{args.port}',f'[::1]:{args.port}'}
            server.origins={'http://'+host for host in server.hosts}
            server.finish=stopped.set
            threading.Thread(target=server.serve_forever,kwargs={'poll_interval':0.2},daemon=True).start()
        expiry=threading.Timer(600,stopped.set)
        expiry.start()
        print(f'Local Auth callback ready at http://localhost:{args.port}/ (10 minutes, loopback only)',flush=True)
        try:stopped.wait()
        finally:
            expiry.cancel()
            for server in servers:server.shutdown();server.server_close()
        return 0
    except (ValueError,OSError,KeyError) as error:
        print('auth_callback: '+str(error),file=sys.stderr)
        return 2


if __name__=='__main__':
    sys.exit(main())
