#!/usr/bin/env python3
"""Sign in with an existing Supabase Auth identity; password is never saved."""
import argparse
import getpass
import os
import re
from pathlib import Path
import sys
import urllib.parse

import api_session
import query_data


def email_proof(base, email, proof):
    proof=proof.strip()
    if re.fullmatch(r'\d{6,8}',proof):
        return {'email':email,'token':proof,'type':'email'}
    parsed=urllib.parse.urlsplit(proof)
    origin=urllib.parse.urlsplit(base)
    if parsed.scheme!='https' or parsed.netloc!=origin.netloc or parsed.path!='/auth/v1/verify':
        raise ValueError('Paste the original confirmation link from this Supabase project, before opening it')
    query=urllib.parse.parse_qs(parsed.query)
    token=(query.get('token_hash') or query.get('token') or [''])[0]
    kind=(query.get('type') or ['email'])[0]
    if not token or len(token)>2048 or kind not in ('email','magiclink','signup'):
        raise ValueError('Unrecognized email confirmation link')
    return {'token_hash':token,'type':kind}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',default=os.environ.get('COMPANY_SQL_CONFIG',str(Path.home()/'.config/company-sql/profiles.json')))
    parser.add_argument('--profile',default='cloud')
    parser.add_argument('--email',required=True)
    parser.add_argument('--email-link',action='store_true',help='Request a one-time email login link instead of a password')
    args = parser.parse_args()
    try:
        profile = query_data.configured_profile(query_data.read_json(args.config),args.profile)
        if profile['engine'] != 'supabase_api' or not api_session.session_path(profile):
            raise ValueError('Choose an API profile with credentials_file')
        base = profile.get('url') or os.environ.get(profile.get('url_env','COMPANY_SUPABASE_URL'),'')
        parsed = urllib.parse.urlsplit(base)
        if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ('','/'):
            raise ValueError('Supabase URL must be an HTTPS project origin')
        existing = api_session.read_session(profile,base)
        key = os.environ.get(profile.get('apikey_env','COMPANY_SUPABASE_API_KEY'),'') or existing.get('apikey','')
        if not key or key.startswith('sb_secret_') or query_data.jwt_role(key) not in (None,'anon'):
            raise ValueError('Provide a publishable project key through the configured session file or environment')
        if not sys.stdin.isatty():
            raise ValueError('Run interactively in a terminal to enter the Auth password')
        if args.email_link:
            api_session.auth_request(base,key,'/otp',{'email':args.email,'create_user':True})
            print('Login email requested. Copy its original confirmation link BEFORE opening it; paste only here, not in chat.',flush=True)
            proof=getpass.getpass('Email code or original confirmation link (hidden): ')
            session=api_session.auth_request(base,key,'/verify',email_proof(base,args.email,proof),True)
        else:
            password = getpass.getpass('Supabase Auth password (not saved): ')
            session = api_session.auth_token(base,key,'password',{'email':args.email,'password':password})
        if session.get('user',{}).get('email','').casefold()!=args.email.casefold():
            raise ValueError('The authenticated email does not match the requested employee identity')
        api_session.write_session(profile,api_session.saved_session(base,key,session))
        print('Signed in; session saved with mode 0600. No password saved.')
        return 0
    except (ValueError,OSError,KeyError) as error:
        print('auth_login: '+str(error),file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
