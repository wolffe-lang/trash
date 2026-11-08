#!/usr/bin/env python3
"""The unit programs: every `src/*_test.lu`, built with the pinned wolf and run,
held to the rows tests/unit-rows.json names for it.

  unit.py --wolf WOLF --out DIR

A program passes when it exits 0, prints `PASS row` exactly once for every
row its inventory names, prints no row the inventory does not name, and
prints no `FAIL` line. A program with no inventory, or an inventory with no
program, fails by name: a count of programs run is never a pass.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--wolf', required=True)
    p.add_argument('--out', required=True)
    a = p.parse_args()
    out = Path(a.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    want = json.loads((ROOT / 'tests/unit-rows.json').read_text())['programs']
    sources = {s.name: s for s in sorted((ROOT / 'src').glob('*_test.lu'))}
    bad = 0
    for name in sorted(set(want) ^ set(sources)):
        print('FAIL unit-inventory %s: a program and its rows must both be there' % name)
        bad += 1
    if not want:
        print('FAIL unit-inventory no unit program is named')
        bad += 1
    for name in sorted(set(want) & set(sources)):
        exe = out / Path(name).stem
        b = subprocess.run([a.wolf, 'build', str(sources[name]), '--no-cache', '--deny-warnings', '-o', str(exe)],
                           capture_output=True, text=True)
        if b.returncode != 0:
            print('FAIL unit-build-%s exit=%d' % (name, b.returncode))
            print(''.join('  ' + l for l in (b.stdout + b.stderr).splitlines(True)[-40:]))
            bad += 1
            continue
        r = subprocess.run([str(exe)], capture_output=True, text=True, timeout=120, cwd=out)
        lines = r.stdout.splitlines()
        print(r.stdout, end='')
        passed = [l[5:] for l in lines if l.startswith('PASS ')]
        for row in want[name]:
            n = passed.count(row)
            if n != 1:
                print('FAIL unit-%s %s printed PASS %d times' % (Path(name).stem, row, n))
                bad += 1
        for row in sorted(set(passed) - set(want[name])):
            print('FAIL unit-%s %s is not in tests/unit-rows.json' % (Path(name).stem, row))
            bad += 1
        fails = [l for l in lines if l.startswith('FAIL ')]
        if fails or r.returncode != 0:
            print('FAIL unit-%s exit=%d with %d FAIL line(s)%s' % (Path(name).stem, r.returncode, len(fails),
                                                                ('; stderr: ' + r.stderr[-400:]) if r.stderr else ''))
            bad += 1
        else:
            print('PASS unit-%s rows=%d' % (Path(name).stem, len(want[name])))
    print('SUMMARY unit programs=%d failed=%d' % (len(set(want) & set(sources)), bad))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
