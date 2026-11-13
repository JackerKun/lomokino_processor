"""Read the public GitHub release in the update worker."""

import json
from pathlib import Path
import re

REPOSITORY = 'JackerKun/lomokino_processor'
PROJECT_URL = f'https://github.com/{REPOSITORY}'
LATEST_RELEASE_URL = f'https://api.github.com/repos/{REPOSITORY}/releases/latest'
VERSION_PATTERN = re.compile(r'v?([0-9]+)\.([0-9]+)\.([0-9]+)')
WORKER_FLAG = '--lomokino-update-worker'
MAX_RESPONSE_BYTES = 1024 * 1024


def version_key(tag):
    match = VERSION_PATTERN.fullmatch(tag) if isinstance(tag, str) else None
    if not match:
        return None
    try:
        return tuple(map(int, match.groups()))
    except ValueError:
        return None


def is_newer_release(tag, current_version):
    candidate = version_key(tag)
    current = version_key(current_version)
    return candidate is not None and current is not None and candidate > current


def latest_release_tag(data):
    try:
        release = json.loads(data)
    except (ValueError, RecursionError):
        return None
    if (not isinstance(release, dict) or release.get('draft') is not False
            or release.get('prerelease') is not False):
        return None
    tag = release.get('tag_name')
    return tag if version_key(tag) is not None else None


def fetch_latest_release(destination):
    """Write a validated tag for the GUI to read after the worker exits."""
    from http.client import HTTPException
    import ssl
    import sys
    from urllib.request import HTTPRedirectHandler, HTTPSHandler, Request, build_opener

    class NoRedirect(HTTPRedirectHandler):
        def redirect_request(self, *args):
            return None

    request = Request(LATEST_RELEASE_URL, headers={
        'Accept': 'application/vnd.github+json',
        'User-Agent': 'LomoKino-Studio',
    })
    try:
        context = ssl.create_default_context()
        if sys.platform == 'darwin' and context.cert_store_stats()['x509_ca'] == 0:
            context.load_verify_locations('/etc/ssl/cert.pem')
        opener = build_opener(NoRedirect(), HTTPSHandler(context=context))
        with opener.open(request, timeout=5) as response:
            if response.status != 200:
                return 1
            data = response.read(MAX_RESPONSE_BYTES + 1)
        tag = latest_release_tag(data) if len(data) <= MAX_RESPONSE_BYTES else None
        if tag is None:
            return 1
        Path(destination).write_text(tag, encoding='ascii')
    except (OSError, HTTPException):
        return 1
    return 0
