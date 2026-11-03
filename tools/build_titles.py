#!/usr/bin/env python3
"""Builds titles.txt: for every 3DS application title, its region and its game family.

3DS Link reads it to say which edition of a game each player in a room has. It is built on a PC from
three public title lists, downloaded by hand (they are not kept in this repository):

  --hax    the folder with list_GB.json, list_JP.json, list_KR.json, list_TW.json, list_US.json
           of https://github.com/hax0kartik/3dsdb (from the eShop)
  --scene  releases.xml of http://3dsdb.com/xml.php (cartridge releases)
  --ghost  title_catalog.json of https://github.com/ghost-land/3dsdb (only for the titles the other two lack)

A line of titles.txt is `id:region:family`:
  id      the low 32 bits of the title id, in hex, without leading zeros (an update or a DLC of a game has the
          same low bits, so it finds its game)
  region  JPN, USA, EUR, KOR, TWN, or FREE when the same id is sold in more than one region
  family  the first three characters of the product code (CTR-P-AQEP -> AQE): the editions of one game share
          them; twins.txt joins the versions of one game that have different ones (Pokemon X and Y)
"""
import argparse
import datetime
import json
import re
import sys
import xml.etree.ElementTree as ET

PRODUCT_CODE = re.compile(r'^(?:CTR|KTR)-(?:[A-Z]-)?([A-Z0-9]{4})$')
STORE_REGION = {'GB': 'EUR', 'US': 'USA', 'JP': 'JPN', 'KR': 'KOR', 'TW': 'TWN'}
SCENE_REGION = {'EUR': 'EUR', 'GER': 'EUR', 'FRA': 'EUR', 'SPA': 'EUR', 'ITA': 'EUR', 'UKV': 'EUR', 'NLD': 'EUR', 'RUS': 'EUR',
                'USA': 'USA', 'JPN': 'JPN', 'KOR': 'KOR', 'TWN': 'TWN', 'CHN': 'TWN', 'WLD': 'FREE'}
GHOST_REGION = {'EU': 'EUR', 'US': 'USA', 'JP': 'JPN', 'KR': 'KOR', 'TW': 'TWN', 'FREE': 'FREE'}


def application_id(title_id):
    """The low 32 bits of an application title id (0004 0000 xxxx xxxx), or None."""
    title_id = (title_id or '').strip().upper()
    if not re.fullmatch(r'[0-9A-F]{16}', title_id) or not title_id.startswith('00040000'):
        return None
    return int(title_id[8:], 16)


def code4(product_code):
    match = PRODUCT_CODE.match((product_code or '').strip().upper())
    return match.group(1) if match else None


def add(table, source, low, code, region):
    if low is None or code is None or region is None:
        return
    entry = table.setdefault(low, {}).setdefault(source, {'codes': [], 'regions': set()})
    if code not in entry['codes']:
        entry['codes'].append(code)
    entry['regions'].add(region)


def read_twins(path):
    """Each line is a group of families that are one game: every family maps to the first of its line."""
    canonical = {}
    with open(path, encoding='utf-8') as f:
        for line in f:
            line = line.split('#', 1)[0].split()
            for family in line:
                if not re.fullmatch(r'[A-Z0-9]{3}', family):
                    sys.exit(f'twins.txt: "{family}" is not a family of three characters')
                if family in canonical:
                    sys.exit(f'twins.txt: {family} is in two groups')
                canonical[family] = line[0]
    return canonical


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--hax', required=True)
    parser.add_argument('--scene', required=True)
    parser.add_argument('--ghost', required=True)
    parser.add_argument('--twins', default='twins.txt')
    parser.add_argument('--out', default='titles.txt')
    parser.add_argument('--stamp', default=datetime.date.today().isoformat(), help='the date 3DS Link compares to know the list changed')
    args = parser.parse_args()

    table = {}
    for store, region in STORE_REGION.items():
        with open(f'{args.hax}/list_{store}.json', encoding='utf-8') as f:
            for e in json.load(f):
                add(table, 'hax', application_id(e.get('TitleID')), code4(e.get('Product Code')), region)
    for release in ET.parse(args.scene).getroot().findall('release'):
        add(table, 'scene', application_id(release.findtext('titleid')), code4(release.findtext('serial')),
            SCENE_REGION.get((release.findtext('region') or '').strip()))
    with open(args.ghost, encoding='utf-8') as f:
        catalog = json.load(f)
    for title in catalog['titles']:
        for releases in title['releases'].values():
            for release in releases:
                base = release.get('base')
                if base:
                    add(table, 'ghost', application_id(base.get('tid')), code4(base.get('product_code')), GHOST_REGION.get(base.get('market')))

    twins = read_twins(args.twins)
    lines = []
    for low in sorted(table):
        sources = table[low]
        # the eShop and the cartridge lists agree on 99.8% of their ids; the third is used only when both lack the title
        trusted = [sources[s] for s in ('hax', 'scene') if s in sources] or [sources['ghost']]
        regions = set().union(*(s['regions'] for s in trusted))
        code = trusted[0]['codes'][0]
        region = 'FREE' if len(regions) != 1 or 'FREE' in regions else regions.pop()
        family = twins.get(code[:3], code[:3])
        lines.append(f'{low:X}:{region}:{family}')

    with open(args.out, 'w', encoding='utf-8', newline='\n') as f:
        f.write(f'#titles {args.stamp}\n')
        f.write('# id:region:family - made by tools/build_titles.py, do not edit by hand (see the README)\n')
        f.write('\n'.join(lines) + '\n')
    print(f'{len(lines)} titles written to {args.out}')


if __name__ == '__main__':
    main()
