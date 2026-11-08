#!/usr/bin/env python3
"""Build the commands: every `src/NAME.lu` that is an entry (`//! member: false`)
and not a unit program (`*_test.lu`), with the pinned wolf.

  build.py --wolf WOLF --out DIR [--static] [--entry PATH:NAME ...]

The default tier, warnings denied. wolf runs from the tree's root and is handed
each entry by its path from there (`src/trash.lu`), so no path above the tree
is written into a binary; with --static the link goes through a cc that adds
-static (wolf has no --static) and -Wl,--build-id=none, so the bytes do not
depend on where the tree is, and every command is checked to be a
static ET_EXEC with no interpreter, and a stripped copy is kept in
DIR/stripped for the PAX image, as tools/census.py builds the census.
--entry builds the named entries instead (a test fixture such as the PAX
rows' rowtool, which is no command).
"""
import argparse
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def commands():
    out = []
    for p in sorted((ROOT / 'src').glob('*.lu')):
        if p.name.endswith('_test.lu'):
            continue
        if '//! member: false' in p.read_text().split('\n', 3)[0]:
            out.append(p)
    return out


def static_env(out):
    shim = out / 'static-cc'
    shim.mkdir(parents=True, exist_ok=True)
    cc = shutil.which('cc') or shutil.which('gcc')
    (shim / 'cc').write_text('#!/bin/sh\nexec %s -static -Wl,--build-id=none "$@"\n' % cc)
    (shim / 'cc').chmod(0o755)
    env = dict(os.environ)
    env['PATH'] = str(shim) + os.pathsep + env['PATH']
    return env


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--wolf', required=True)
    p.add_argument('--out', required=True)
    p.add_argument('--static', action='store_true')
    p.add_argument('--entry', action='append', default=[])
    a = p.parse_args()
    # wolf runs from the tree's root: a path to it is made absolute first.
    wolf = str(Path(a.wolf).resolve()) if os.sep in a.wolf else a.wolf
    out = Path(a.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    env = static_env(out) if a.static else dict(os.environ)
    srcs = [(p, p.stem) for p in commands()]
    if a.entry:
        srcs = [(ROOT / e.split(':')[0], e.split(':')[1]) for e in a.entry]
    if not srcs:
        print('FAIL build-commands no entry in src/')
        return 1
    bad = 0
    for src, name in srcs:
        exe = out / name
        log = out / (name + '.build.log')
        with log.open('w') as f:
            r = subprocess.run([wolf, 'build', str(src.resolve().relative_to(ROOT)), '--no-cache', '--deny-warnings',
                                '-o', str(exe)], stdout=f, stderr=subprocess.STDOUT, env=env, cwd=ROOT)
        if r.returncode != 0:
            print('FAIL build-%s exit=%d' % (name, r.returncode))
            print(''.join('  ' + line for line in log.read_text().splitlines(True)[-30:]))
            bad += 1
            continue
        if a.static:
            hdr = subprocess.run(['readelf', '-hW', str(exe)], capture_output=True, text=True).stdout
            seg = subprocess.run(['readelf', '-lW', str(exe)], capture_output=True, text=True).stdout
            if not re.search(r'Type:\s+EXEC', hdr) or 'INTERP' in seg:
                print('FAIL build-%s not a static ET_EXEC' % name)
                bad += 1
                continue
            (out / 'stripped').mkdir(exist_ok=True)
            subprocess.run(['strip', '-o', str(out / 'stripped' / name), str(exe)], check=True)
        print('PASS build-%s%s' % (name, ' static' if a.static else ''))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
