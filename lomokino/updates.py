"""Check the public GitHub release without blocking the application."""

import json
import re

from PyQt6.QtCore import QUrl
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

REPOSITORY = 'JackerKun/lomokino_processor'
PROJECT_URL = f'https://github.com/{REPOSITORY}'
LATEST_RELEASE_URL = f'https://api.github.com/repos/{REPOSITORY}/releases/latest'
VERSION_PATTERN = re.compile(r'v?([0-9]+)\.([0-9]+)\.([0-9]+)')


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


def check_latest_release(parent, on_result):
    network = QNetworkAccessManager(parent)
    request = QNetworkRequest(QUrl(LATEST_RELEASE_URL))
    request.setRawHeader(b'Accept', b'application/vnd.github+json')
    request.setRawHeader(b'User-Agent', b'LomoKino-Studio')
    request.setAttribute(QNetworkRequest.Attribute.RedirectPolicyAttribute,
                         QNetworkRequest.RedirectPolicy.SameOriginRedirectPolicy)
    request.setTransferTimeout(5000)

    def finished(reply):
        network.deleteLater()
        if reply.error() != QNetworkReply.NetworkError.NoError:
            on_result(None)
        else:
            on_result(latest_release_tag(bytes(reply.readAll())))

    network.finished.connect(finished)
    network.get(request)
