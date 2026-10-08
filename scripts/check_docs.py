#!/usr/bin/env python3
"""Check local Markdown links, heading fragments and embedded SVG XML."""
from pathlib import Path
import re
import sys
from urllib.parse import unquote, urlsplit
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
SCOPES = list(ROOT.glob('*.md'))
for folder in ('docs', 'monitor', 'hardware'):
    SCOPES.extend((ROOT / folder).rglob('*.md'))


def headings(path):
    counts = {}
    anchors = set()
    for line in path.read_text().splitlines():
        match = re.match(r'^#{1,6}\s+(.+?)\s*#*$', line)
        if not match:
            continue
        slug = re.sub(r'[^\w\- ]', '', match[1].lower()).replace(' ', '-')
        n = counts.get(slug, 0)
        anchors.add(slug if not n else f'{slug}-{n}')
        counts[slug] = n + 1
    return anchors


errors = []
checked = 0
for path in SCOPES:
    if not path.is_file():
        errors.append(f'Missing guide: {path.relative_to(ROOT)}')
        continue
    # Inline Markdown links/images; external URLs are deliberately not fetched.
    for href in re.findall(r'!?\[[^\]]*\]\(([^)\s]+)(?:\s+"[^"]*")?\)', path.read_text()):
        url = urlsplit(href.strip('<>'))
        if url.scheme or url.netloc:
            continue
        dest = (path.parent / unquote(url.path)).resolve() if url.path else path
        checked += 1
        if not dest.exists():
            errors.append(f'{path.relative_to(ROOT)}: missing {href}')
        elif url.fragment and dest.suffix == '.md' and unquote(url.fragment) not in headings(dest):
            errors.append(f'{path.relative_to(ROOT)}: unknown heading {href}')
for path in (ROOT / 'docs').rglob('*.svg'):
    try:
        ET.parse(path)
    except ET.ParseError as exc:
        errors.append(f'{path.relative_to(ROOT)}: {exc}')
if errors:
    print('\n'.join(errors))
    sys.exit(1)
print(f'PASS: {checked} local documentation links and SVG XML')
