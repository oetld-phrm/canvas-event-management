"""Shared authentication, HTTP, and input validation."""
import getpass
import os
import re
from pathlib import Path
import requests

def resolve_input_path(value, filename):
    """Use explicit paths as supplied; otherwise prefer local then package data."""
    if value is not None:
        return Path(value)
    local = Path(filename)
    return local if local.is_file() else Path(__file__).resolve().parent / filename

def canvas_request(session, method, url, **kwargs):
    """Make one API request with a timeout and no automatic write retries.

    A timed-out write may already have reached Canvas. Preview before retrying.
    Redirects are rejected rather than forwarding the API token elsewhere.
    """
    print(f'Canvas {method.upper()}: {url}', flush=True)
    r = session.request(method, url, timeout=(10, 60), allow_redirects=False, **kwargs)
    if not 200 <= r.status_code < 300:
        raise RuntimeError(f'Canvas HTTP {r.status_code}: {r.text[:800]}')
    return r.json()

def validate_base_url(value):
    """Accept either an HTTPS instance URL or that URL ending in /api/v1."""
    base = value.strip().rstrip('/').removesuffix('/api/v1')
    if not re.fullmatch(r'https://[A-Za-z0-9.-]+(?::[0-9]+)?', base):
        raise ValueError('Use an HTTPS instance URL such as https://school.instructure.com')
    return base

def connect(value=None):
    base = validate_base_url(value or os.getenv('CANVAS_URL') or input('Canvas instance URL: '))
    token = os.getenv('CANVAS_API_TOKEN') or getpass.getpass('Canvas API token: ')
    if not token.strip():
        raise ValueError('API token is required')
    session = requests.Session()
    session.headers['Authorization'] = f'Bearer {token.strip()}'
    return base, session


def run(main):
    try:
        return main()
    except (ValueError, OSError, KeyError, ImportError, RuntimeError, requests.RequestException) as exc:
        print(str(exc))
        return 1
