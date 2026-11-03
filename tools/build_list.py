#!/usr/bin/env python3
"""Builds public-lobbies.txt, the list of public Azahar rooms 3DS Link shows, from:

  sources.txt  the lobby servers to read (one URL per line, each answering GET /lobby)
  manual.txt   rooms we add or rename by hand: they win over a lobby (same address and port)
  exclude.txt  rooms to leave out (address:port), for example when the owner asks
  titles.txt   only its first line, the date 3DS Link compares to know the list of titles changed

A line of public-lobbies.txt is `address:port:name` or `address:port:name:secret`: the name has no colon, the secret
is everything after the third one. From a lobby only rooms with no password and network version 4 are taken.

The file is written only when the rooms changed, or when they have not changed for 30 days (the #updated line then
gets today's date: GitHub turns off scheduled workflows of a public repository after 60 days without activity).
Nothing is written when every lobby failed, or when the rooms of the lobbies fell below half of the last list:
the run then fails, so GitHub says so by mail, and the file keeps the rooms it had.
"""
import argparse
import datetime
import ipaddress
import json
import re
import sys
import urllib.request

MAX_BYTES = 64 * 1024          # 3DS Link refuses a bigger list
MAX_ANSWER_BYTES = 1024 * 1024  # a /lobby answer this big is not one
MAX_NAME = 64
MAX_ROOMS_PER_HOST = 20
NETWORK_VERSION = 4
STALE_DAYS = 30
HOST = re.compile(r'^[A-Za-z0-9.-]{1,80}$')
LINK = re.compile(r'(https?://\S+|www\.\S+|\S+\.[a-z]{2,}/\S*)', re.IGNORECASE)


def clean_name(name):
    """A room name as the list carries it: no link, no colon, no control character, one space at a time, at most 64 characters."""
    name = LINK.sub(' ', name or '')
    name = name.replace(':', ' -')
    name = ''.join(c if c.isprintable() else ' ' for c in name)
    name = re.sub(r'\s+', ' ', name).strip(' -|')
    return name[:MAX_NAME].rstrip()


def valid_host(host):
    """A public IPv4 address or a host name. Private, local and reserved addresses are refused, and IPv6 has colons."""
    if not HOST.match(host or ''):
        return False
    try:
        return ipaddress.ip_address(host).is_global
    except ValueError:
        return not re.fullmatch(r'[0-9.]+', host) and '.' in host and not host.lower().endswith(('.local', '.lan', '.localhost'))


def key(host, port):
    return (host.lower(), port)


def parse_line(line, where):
    """address:port:name[:secret] -> (host, port, name, secret); None for blank and comment lines."""
    line = line.rstrip('\r\n')
    if not line.strip() or line.lstrip().startswith('#'):
        return None
    parts = line.split(':', 3)
    if len(parts) < 3:
        raise ValueError(f'{where}: "{line}" is not address:port:name')
    host, port, name = parts[0].strip(), parts[1].strip(), parts[2].strip()
    if not valid_host(host) or not port.isdigit() or not 1 <= int(port) <= 65535:
        raise ValueError(f'{where}: "{line}" has a bad address or port')
    if name != clean_name(name):
        raise ValueError(f'{where}: the name "{name}" has characters the list does not allow, or is longer than {MAX_NAME}')
    return host, int(port), name, parts[3] if len(parts) == 4 else ''


def read_lines(path):
    try:
        with open(path, encoding='utf-8') as f:
            return f.read().splitlines()
    except FileNotFoundError:
        return []


def rooms_of_lobby(answer):
    """The rooms of a /lobby answer that 3DS Link can use: (host, port, name)."""
    rooms = []
    for room in answer.get('rooms', []):
        if not isinstance(room, dict) or room.get('hasPassword') is not False:
            continue
        if room.get('netVersion') != NETWORK_VERSION:
            continue
        host, port = str(room.get('address', '')).strip(), room.get('port')
        if not valid_host(host) or not isinstance(port, int) or not 1 <= port <= 65535:
            continue
        rooms.append((host, port, clean_name(str(room.get('name', '')))))
    return rooms


def fetch(url):
    request = urllib.request.Request(url, headers={'User-Agent': '3DS-Link-Public-Lobbies'})
    with urllib.request.urlopen(request, timeout=30) as response:
        body = response.read(MAX_ANSWER_BYTES + 1)
    if len(body) > MAX_ANSWER_BYTES:
        raise ValueError('the answer is too big')
    return json.loads(body.decode('utf-8'))


def body_lines(text_lines):
    return [line for line in text_lines if line.strip() and not line.startswith('#')]


def header_value(text_lines, word):
    for line in text_lines:
        if line.startswith(f'#{word} '):
            return line.split(' ', 1)[1].strip()
    return None


def build(lobby_rooms, manual, exclude, previous, titles_stamp, today):
    """Returns (text, reason) for the new file, or (None, reason) when it must not be written."""
    excluded = set()
    for i, line in enumerate(exclude, 1):
        line = line.split('#', 1)[0].strip()
        if line:
            host, _, port = line.rpartition(':')
            excluded.add(key(host, int(port)))

    rooms = {}
    per_host = {}
    for host, port, name in sorted(lobby_rooms, key=lambda r: key(r[0], r[1])):
        k = key(host, port)
        if k in excluded or k in rooms or per_host.get(k[0], 0) >= MAX_ROOMS_PER_HOST:
            continue
        per_host[k[0]] = per_host.get(k[0], 0) + 1
        rooms[k] = (host, port, name, '')
    from_lobbies = len(rooms)
    for i, line in enumerate(manual, 1):
        room = parse_line(line, f'manual.txt:{i}')
        if room and key(room[0], room[1]) not in excluded:
            rooms[key(room[0], room[1])] = room

    lines = []
    for k in sorted(rooms):
        host, port, name, secret = rooms[k]
        lines.append(f'{host}:{port}:{name}' + (f':{secret}' if secret else ''))

    before = body_lines(previous)
    before_from_lobbies = int(header_value(previous, 'lobby-rooms') or 0)
    if before_from_lobbies and from_lobbies < before_from_lobbies // 2:
        return None, f'the lobbies gave {from_lobbies} rooms, the last list had {before_from_lobbies}: not written'
    last = header_value(previous, 'updated')
    stale = True
    if last:
        stale = (today - datetime.date.fromisoformat(last)).days >= STALE_DAYS
    same = lines == before and header_value(previous, 'titles') == titles_stamp
    if same and not stale:
        return None, 'nothing changed'

    text = '\n'.join([
        f'#updated {today.isoformat()}',
        f'#titles {titles_stamp}',
        f'#lobby-rooms {from_lobbies}',
        '# address:port:name[:secret] - made by tools/build_list.py, do not edit by hand: change manual.txt or exclude.txt',
        *lines,
    ]) + '\n'
    if len(text.encode('utf-8')) > MAX_BYTES:
        return None, f'the list would be {len(text.encode("utf-8"))} bytes, more than {MAX_BYTES}: not written'
    return text, ('the rooms changed' if not same else f'no change for {STALE_DAYS} days: the date is renewed')


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--out', default='public-lobbies.txt')
    parser.add_argument('--lobby-file', action='append', default=[], help='read a saved /lobby answer instead of sources.txt (for a test)')
    parser.add_argument('--today', default=None, help='YYYY-MM-DD (for a test)')
    args = parser.parse_args()
    today = datetime.date.fromisoformat(args.today) if args.today else datetime.datetime.now(datetime.timezone.utc).date()

    answers, failures = [], []
    if args.lobby_file:
        for path in args.lobby_file:
            with open(path, encoding='utf-8') as f:
                answers.append(json.load(f))
    else:
        for url in body_lines(read_lines('sources.txt')):
            url = url.strip()
            try:
                answers.append(fetch(url))
            except Exception as e:  # one lobby that fails must not stop the others
                failures.append(f'{url}: {e}')
    for failure in failures:
        print(f'lobby failed: {failure}')
    if not answers:
        sys.exit('no lobby answered: the list is not written')

    lobby_rooms = [room for answer in answers for room in rooms_of_lobby(answer)]
    titles_stamp = header_value(read_lines('titles.txt'), 'titles') or ''
    try:
        text, reason = build(lobby_rooms, read_lines('manual.txt'), read_lines('exclude.txt'), read_lines(args.out), titles_stamp, today)
    except ValueError as e:
        sys.exit(str(e))
    print(reason)
    if text is None:
        if reason != 'nothing changed':
            sys.exit(1)
        return
    with open(args.out, 'w', encoding='utf-8', newline='\n') as f:
        f.write(text)


if __name__ == '__main__':
    main()
