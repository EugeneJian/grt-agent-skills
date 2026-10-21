#!/usr/bin/env python3
"""Initialize per-computer cloud configuration without copying an Auth session."""
import argparse
import getpass
import json
import os
from pathlib import Path
import sys
import urllib.parse

import api_session
import query_data


def project_origin(value):
    parsed = urllib.parse.urlsplit(value)
    if (parsed.scheme != 'https' or not parsed.hostname or parsed.username
            or parsed.password or parsed.query or parsed.fragment
            or parsed.path not in ('', '/') or parsed.port not in (None, 443)):
        raise ValueError('Use an HTTPS project origin, without credentials or a path')
    return value.rstrip('/')


def public_key(value):
    if not isinstance(value, str):
        raise ValueError('Provide a public project key as text')
    value = value.strip()
    if value.startswith('sb_publishable_') and len(value) > len('sb_publishable_'):
        return value
    if value.count('.') == 2 and query_data.jwt_role(value) == 'anon':
        return value
    raise ValueError('Use a publishable or legacy anon key, never an employee JWT or secret key')


def initialize(config_path, url, key=None, session_path=None):
    config_path = Path(config_path).expanduser()
    if config_path.is_symlink():
        raise ValueError('Config path is a symlink; choose its real path explicitly')
    config = query_data.read_json(config_path) if config_path.exists() else {'profiles': {}}
    if not isinstance(config, dict) or not isinstance(config.get('profiles'), dict):
        raise ValueError('Invalid existing profile configuration; no files changed')
    url = project_origin(url)
    profile = config['profiles'].get('cloud')
    if profile is not None:
        profile = query_data.configured_profile(config, 'cloud')
        current_url = profile.get('url') or os.environ.get(profile.get('url_env', 'COMPANY_SUPABASE_URL'), '')
        if profile['engine'] != 'supabase_api' or current_url.rstrip('/') != url:
            raise ValueError('Existing cloud profile targets another project; no files changed')
        if not profile.get('credentials_file'):
            raise ValueError('Existing cloud profile has no credentials_file; configure it explicitly')
        if session_path and Path(profile['credentials_file']).expanduser() != Path(session_path).expanduser():
            raise ValueError('Existing cloud session path differs; no files changed')
    else:
        profile = {'engine': 'supabase_api', 'url': url,
                   'apikey_env': 'COMPANY_SUPABASE_API_KEY',
                   'jwt_env': 'COMPANY_SUPABASE_USER_JWT', 'api_schema': 'agent_api',
                   'credentials_file': str(session_path or '~/.config/company-sql/cloud-auth.json'),
                   'max_rows': 1000, 'timeout_seconds': 30}
    target = api_session.session_path(profile)
    if target.is_symlink() or target.absolute() == config_path.absolute():
        raise ValueError('Choose a regular session file separate from the config')
    existing = api_session.read_session(profile, url)
    if target.exists():
        public_key(existing.get('apikey', ''))
        created = False  # Never replace an existing employee session during installation.
    else:
        key = public_key(key or os.environ.get('COMPANY_SUPABASE_API_KEY', '')
                         or getpass.getpass('Project publishable key (not an employee token): '))
        api_session.write_session(profile, {'project_url': url, 'apikey': key})
        created = True
    config['profiles']['cloud'] = profile
    config.setdefault('default_profile', 'cloud')
    api_session.write_session({'credentials_file': str(config_path)}, config)
    return {'default_profile': config['default_profile'], 'config': str(config_path),
            'session_file': str(target), 'public_key_seed_created': created,
            'existing_session_preserved': not created}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', required=True, help='HTTPS Supabase project URL')
    parser.add_argument('--config', default=os.environ.get('COMPANY_SQL_CONFIG', str(Path.home()/'.config/company-sql/profiles.json')))
    parser.add_argument('--session-file', help='Optional per-computer session path')
    args = parser.parse_args(argv)
    try:
        print(json.dumps(initialize(args.config, args.url, session_path=args.session_file), ensure_ascii=False))
        print('Next: run auth_callback.py --config <config> --profile cloud --email <employee email>.')
        return 0
    except (ValueError, OSError, KeyError, EOFError) as error:
        print('setup_cloud: '+str(error), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
