#!/usr/bin/env python3
"""Reorganize top-level TV release folders into Jellyfin-friendly Series/Season NN folders.

Default is dry-run. Use --apply to actually move files.
"""
from __future__ import annotations

import argparse
import csv
import os
import re
import shutil
from datetime import datetime
from pathlib import Path

ROOT = Path(os.environ.get('TV_ROOT') or '/mnt/files1/data/shared/tv').expanduser()

ALIASES = {
    'Archer': 'Archer (2009)',
    'Bobs Burgers': "Bob's Burgers (2011)",
    'BILLIONS': 'Billions',
    'BILLIONS - Complete': 'Billions',
    'Chappelles Show': "Chappelle's Show",
    'Duck Tales (1989)': 'Duck Tales (1987)',
    'Duck Tales (1987)': 'Duck Tales (1987)',
    'Black Mirror': 'Black Mirror (2011)',
    'Black Mirror (2012)': 'Black Mirror (2011)',
    'Black Mirror (2013)': 'Black Mirror (2011)',
    'Black Mirror (2014)': 'Black Mirror (2011)',
    'Black Mirror (2015)': 'Black Mirror (2011)',
    'Black Mirror (2016)': 'Black Mirror (2011)',
    'Black Mirror (2017)': 'Black Mirror (2011)',
    'Black Mirror (2018)': 'Black Mirror (2011)',
    'Black Mirror (2019)': 'Black Mirror (2011)',
}

SKIP_PATTERNS = [
    # Multi-season/complete-series folders are usually already nested internally; do not flatten blindly.
    re.compile(r'\bS\d{1,2}\s*[-–]\s*S?\d{1,2}\b', re.I),
    re.compile(r'\bSeason\s+\d{1,2}\s*(?:-|–|to)\s*\d{1,2}\b', re.I),
    re.compile(r'\bSeasons\s+\d{1,2}\b', re.I),
    re.compile(r'\bCOMPLETE[ ._-]+SERIES\b', re.I),
]


def clean_title(s: str) -> str:
    s = s.replace('.', ' ').replace('_', ' ')
    s = re.sub(r'\s+', ' ', s).strip(' -._')
    s = re.sub(r'\s+-\s+Complete$', '', s, flags=re.I)
    s = re.sub(r'\s+Complete$', '', s, flags=re.I)
    # Convert trailing bare year to Jellyfin-style (year), e.g. "Chuck 2007".
    m = re.match(r'^(.*?)[\s.]*[\(\[]?(19\d{2}|20\d{2})[\)\]]?$', s)
    if m and not re.search(r'\(\d{4}\)', s):
        title = m.group(1).strip(' -._')
        if title:
            s = f'{title} ({m.group(2)})'
    return ALIASES.get(s, s)


def parse_entry_name(name: str):
    if name.startswith('.') or name in {'@eaDir'}:
        return None
    if any(p.search(name) for p in SKIP_PATTERNS):
        return None

    # Specials folders.
    m = re.search(r'^(?P<title>.+?)\s+Specials\b', name, re.I)
    if m:
        return clean_title(m.group('title')), 0

    # Black Mirror release names use the year of each season; keep the show year.
    m = re.search(r'^(?P<title>Black Mirror)\s*\(S(?P<season>\d{1,2})\)\s*\((?P<year>\d{4})\)', name, re.I)
    if m:
        return 'Black Mirror (2011)', int(m.group('season'))

    # Title Season 1 ... / Title (Year) Season 1 ...
    m = re.search(r'^(?P<title>.+?)\s+(?:SE\s+)?Season\s+(?P<season>\d{1,2})\b', name, re.I)
    if m:
        return clean_title(m.group('title')), int(m.group('season'))

    # Title.S01... or Title S01E02...
    m = re.search(r'^(?P<title>.+?)[\s._-]+S(?P<season>\d{1,2})(?:E\d{1,2})?\b', name, re.I)
    if m:
        return clean_title(m.group('title')), int(m.group('season'))

    return None


def unique_dest(path: Path) -> Path:
    if not path.exists():
        return path
    stem, suffix = path.stem, path.suffix
    parent = path.parent
    i = 1
    while True:
        candidate = parent / f'{stem}__dupe{i}{suffix}'
        if not candidate.exists():
            return candidate
        i += 1


def plan(root: Path):
    moves = []
    skipped = []
    for entry in sorted(root.iterdir(), key=lambda p: p.name.lower()):
        parsed = parse_entry_name(entry.name)
        if not parsed:
            if entry.is_dir():
                skipped.append(entry.name)
            continue
        series, season = parsed
        if not series or series.lower().startswith('season'):
            skipped.append(entry.name)
            continue
        dest_dir = root / series / f'Season {season:02d}'
        moves.append((entry, dest_dir, series, season))
    return moves, skipped


def apply_move(src: Path, dest_dir: Path, writer):
    dest_dir.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        for child in sorted(src.iterdir(), key=lambda p: p.name.lower()):
            dest = unique_dest(dest_dir / child.name)
            writer.writerow([str(child), str(dest)])
            shutil.move(str(child), str(dest))
        try:
            src.rmdir()
        except OSError:
            pass
    else:
        dest = unique_dest(dest_dir / src.name)
        writer.writerow([str(src), str(dest)])
        shutil.move(str(src), str(dest))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', type=Path, default=ROOT)
    ap.add_argument('--apply', action='store_true', help='actually move files; otherwise only print the plan')
    ap.add_argument('--limit', type=int, default=0, help='limit number of top-level entries processed')
    args = ap.parse_args()

    moves, skipped = plan(args.root)
    if args.limit:
        moves = moves[:args.limit]

    print(f'Root: {args.root}')
    print(f'Planned top-level entries: {len(moves)}')
    print(f'Skipped/unclassified dirs: {len(skipped)}')
    for src, dest_dir, series, season in moves[:150]:
        print(f'{src.name}  ->  {series}/Season {season:02d}/')
    if len(moves) > 150:
        print(f'... {len(moves)-150} more')

    if not args.apply:
        print('\nDry run only. Re-run with --apply to move files.')
        return

    log = args.root / f'reorganize_tv_moves_{datetime.now():%Y%m%d_%H%M%S}.csv'
    with log.open('w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['source', 'destination'])
        for src, dest_dir, _, _ in moves:
            if src.exists():
                apply_move(src, dest_dir, writer)
    print(f'Applied. Move log: {log}')


if __name__ == '__main__':
    main()
