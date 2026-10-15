#!/usr/bin/env python3
"""Attach a video (plus an optional "before" video and images) to a Jira issue, post ONE comment that embeds them, then verify every embed rendered.

    python3 post_jira_video.py ABC-123 docs/videos/ABC-123-fix-v1.mp4 comment.txt --dry-run
    python3 post_jira_video.py ABC-123 docs/videos/ABC-123-fix-v1.mp4 comment.txt --before docs/videos/ABC-123-before-v1.mp4

comment.txt is Jira wiki markup; the line `{video}` is replaced by `!<file name>|width=900!`, the line `{before}`
by the same embed for the `--before` video, and the line `{images}` by one embed per `--attach` image, in the order given.
Show the user the --dry-run output and get a clear yes before the real run.

The site and its credentials come from ~/.config/demo-video/jira-sites.json, keyed by the ticket's
project prefix ("*" for any other): {"ABC": {"env": "~/.claude/abc-atlassian.env", "site": "https://abc.atlassian.net"}}.
The env file holds ATLASSIAN_EMAIL and ATLASSIAN_API_TOKEN; they are never printed. An ATLASSIAN_SITE in the
environment that points at another site stops the run instead of posting there.
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path


SITES_FILE = Path.home() / '.config' / 'demo-video' / 'jira-sites.json'


def site_for(key):
    if not SITES_FILE.exists():
        sys.exit(f'No Jira sites configured: write {SITES_FILE}')
    sites = json.loads(SITES_FILE.read_text())
    entry = sites.get(key.split('-')[0].upper()) or sites.get('*')
    if not entry:
        sys.exit(f'No Jira site for {key} in {SITES_FILE}')
    return Path(os.path.expanduser(entry['env'])), entry['site'].rstrip('/')


def load_env(key):
    path, site = site_for(key)
    env_file = path
    values = {}
    if path.exists():
        for line in path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                values[k.strip().removeprefix('export ')] = v.strip().strip('"').strip("'")
    configured = (os.environ.get('ATLASSIAN_SITE') or values.get('ATLASSIAN_SITE') or site).rstrip('/')
    if not configured.startswith('http'):
        configured = 'https://' + configured
    if configured != site:
        sys.exit(f'{key} belongs to {site}, but ATLASSIAN_SITE is {configured}; refusing to post there')
    email = values.get('ATLASSIAN_EMAIL') or os.environ.get('ATLASSIAN_EMAIL')
    token = values.get('ATLASSIAN_API_TOKEN') or os.environ.get('ATLASSIAN_API_TOKEN')
    if not email or not token:
        sys.exit(f'Missing ATLASSIAN_EMAIL / ATLASSIAN_API_TOKEN for {site} ({env_file})')
    return site, f'{email}:{token}'


def curl(auth, *args):
    out = subprocess.run(['curl', '-s', '-w', '\n%{http_code}', '-u', auth, *args], capture_output=True, text=True)
    body, _, code = out.stdout.rpartition('\n')
    return int(code), body


def main(argv):
    dry = '--dry-run' in argv
    argv = [a for a in argv if a != '--dry-run']
    flags = ('--attach', '--before')
    images = [Path(argv[i + 1]) for i, a in enumerate(argv[:-1]) if a == '--attach']
    befores = [Path(argv[i + 1]) for i, a in enumerate(argv[:-1]) if a == '--before']
    args = [a for i, a in enumerate(argv) if a not in flags and (i == 0 or argv[i - 1] not in flags)]
    if len(args) != 3 or len(befores) > 1:
        sys.exit(__doc__)
    key, video, comment_file = args[0], Path(args[1]), Path(args[2])
    videos = [*befores, video]
    for f in [*videos, *images]:
        if not f.exists():
            sys.exit(f'No such file: {f}')
    text = comment_file.read_text().strip()
    if images and '{images}' not in text:
        sys.exit('--attach given but comment.txt has no {images} line')
    if befores and '{before}' not in text:
        sys.exit('--before given but comment.txt has no {before} line')
    if '{video}' not in text:
        sys.exit('comment.txt has no {video} line')
    text = text.replace('{video}', f'!{video.name}|width=900!')
    if befores:
        text = text.replace('{before}', f'!{befores[0].name}|width=900!')
    text = text.replace('{images}', '\n'.join(f'!{f.name}|width=900!' for f in images))
    site, auth = load_env(key)
    listed = '\n'.join(f'Attachment: {f.name} ({f.stat().st_size} bytes)' for f in [*videos, *images])
    print(f'Site: {site}\nIssue: {key}\n{listed}\n--- comment ---\n{text}\n---------------')
    if dry:
        print('(dry run: nothing sent)')
        return
    api = f'{site}/rest/api/2/issue/{key}'
    uploaded = []
    for f, mime in [*[(v, 'video/mp4') for v in videos], *[(i, 'image/png') for i in images]]:
        code, body = curl(auth, '-H', 'X-Atlassian-Token: no-check', '-F', f'file=@{f};type={mime}', f'{api}/attachments')
        if code != 200:
            sys.exit(f'Upload of {f.name} failed: HTTP {code}')
        att = json.loads(body)[0]
        if att['size'] != f.stat().st_size:
            sys.exit(f"Uploaded size of {f.name} {att['size']} != local {f.stat().st_size}")
        print(f"uploaded attachment {att['id']} {f.name} ({att['size']} bytes)")
        uploaded.append(att)
    code, body = curl(auth, '-H', 'Content-Type: application/json', '--data', json.dumps({'body': text}),
                      f'{api}/comment')
    if code != 201:
        sys.exit(f'Comment failed: HTTP {code}')
    comment_id = json.loads(body)['id']
    # Wiki markup converts `!file.mp4|width=900!` into an ADF media node with a bogus 900x183 size and no
    # alt; the new issue view then shows "Creating preview..." forever instead of a player. Rewrite the
    # node the way Jira's own editor stores it: the video's real size, its file name, 900 px display width.
    # Media nodes come in the comment's order; only video nodes are rewritten, images render as is.
    sizes = {}
    for v in videos:
        probe = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries',
                                'stream=width,height', '-of', 'csv=p=0', str(v)], capture_output=True, text=True)
        sizes[v.name] = tuple(int(n) for n in probe.stdout.strip().split(','))
    v3 = api.replace('/rest/api/2/', '/rest/api/3/')
    code, body = curl(auth, f'{v3}/comment/{comment_id}')
    adf = json.loads(body)['body']
    order = iter(re.findall(r'!([^|!\n]+)\|width=900!', text))

    def fix(node):
        if node.get('type') == 'mediaSingle':
            name = next(order, None)
            if name not in sizes:
                return
            vw, vh = sizes[name]
            node['attrs'] = {'width': 900, 'widthType': 'pixel', 'layout': 'center'}
            for media in node.get('content', []) or []:
                if media.get('type') == 'media':
                    a = media['attrs']
                    media['attrs'] = {'type': 'file', 'id': a['id'], 'collection': a.get('collection', ''),
                                      'alt': name, 'width': vw, 'height': vh}
            return
        for child in node.get('content', []) or []:
            fix(child)

    fix(adf)
    code, _ = curl(auth, '-X', 'PUT', '-H', 'Content-Type: application/json', '--data', json.dumps({'body': adf}),
                   f'{v3}/comment/{comment_id}')
    if code != 200:
        sys.exit(f'Fixing the video node failed: HTTP {code}')
    code, body = curl(auth, f'{api}/comment/{comment_id}?expand=renderedBody')
    rendered = json.loads(body).get('renderedBody', '')
    missing = [a['filename'] for a in uploaded if f"attachment/content/{a['id']}" not in rendered]
    print(f'comment {comment_id} posted; all embeds render: {not missing}')
    print(f'{site}/browse/{key}?focusedCommentId={comment_id}')
    if missing:
        sys.exit(f'Embeds that did not render: {missing} - check the comment in Jira')


if __name__ == '__main__':
    main(sys.argv[1:])
