#!/usr/bin/env python3
"""The census: build the probes, run them, and hold what they print to census/expect.json.

  census.py build --wolf WOLF --out DIR [--static]   (static: also DIR/stripped/)
  census.py run --bin DIR --same DIR --other DIR --out RECORD.json
  census.py parse --console FILE --out RECORD.json [--platform NAME]
  census.py verdict --record RECORD.json --platform linux|pax
  census.py table [--linux RECORD.json] [--pax RECORD.json]
  census.py selftest

Every probe (census/NAME/main.lu) prints `ROW row@store observation` lines and
census/run.sh adds `EXIT program@store status` after each. A record maps each
row to the observations it printed (in order) and each program run to its exit
status. `verdict` passes a row when its observation, as one line, matches the
platform's `want` (a regular expression, matched whole), and fails by name a
row that is unexpected, missing, or different, and a program run that did not
exit 0. A row whose platform status is `missing` or `wrong` passes only while
it still shows the gap it was filed for: when the gap heals, the row goes red
and the expectation moves with it.
"""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
EXPECT = ROOT / 'census/expect.json'
STATUSES = ('present', 'missing', 'wrong')


def programs():
    return sorted(p.parent.name for p in (ROOT / 'census').glob('*/main.lu'))


def cmd_build(a):
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    if a.static:
        # wolf has no --static: it links through the first cc on PATH, so a cc that
        # adds -static goes first (as the org's other PAX programs are built).
        shim = out / 'static-cc'
        shim.mkdir(exist_ok=True)
        cc = shutil.which('cc') or shutil.which('gcc')
        (shim / 'cc').write_text('#!/bin/sh\nexec %s -static "$@"\n' % cc)
        (shim / 'cc').chmod(0o755)
        env['PATH'] = str(shim) + os.pathsep + env['PATH']
    bad = 0
    for name in programs():
        exe = out / name
        log = out / (name + '.build.log')
        with log.open('w') as f:
            r = subprocess.run([a.wolf, 'build', str(ROOT / 'census' / name / 'main.lu'), '--no-cache', '-o', str(exe)],
                               stdout=f, stderr=subprocess.STDOUT, env=env)
        if r.returncode != 0:
            print('FAIL census-build-%s exit=%d' % (name, r.returncode))
            print(''.join('  ' + line for line in log.read_text().splitlines(True)[-20:]))
            bad += 1
            continue
        if a.static:
            hdr = subprocess.run(['readelf', '-hW', str(exe)], capture_output=True, text=True).stdout
            seg = subprocess.run(['readelf', '-lW', str(exe)], capture_output=True, text=True).stdout
            if not re.search(r'Type:\s+EXEC', hdr) or 'INTERP' in seg:
                print('FAIL census-build-%s not a static ET_EXEC' % name)
                bad += 1
                continue
            # The PAX image carries a stripped copy: the symbols are a twelfth of
            # the bytes and the console session never reads them.
            (out / 'stripped').mkdir(exist_ok=True)
            subprocess.run(['strip', '-o', str(out / 'stripped' / name), str(exe)], check=True)
        print('PASS census-build-%s%s' % (name, ' static' if a.static else ''))
    return 1 if bad else 0


def parse_lines(lines):
    """name -> list of observations; program@store -> exit status (str)."""
    rows, exits, started, ended = {}, {}, False, False
    for line in lines:
        line = line.rstrip('\r')
        if line == 'CENSUS start':
            started = True
        elif line == 'CENSUS end':
            ended = True
        elif line.startswith('ROW '):
            parts = line[4:].split(' ', 1)
            rows.setdefault(parts[0], []).append(parts[1] if len(parts) > 1 else '')
        elif line.startswith('EXIT '):
            parts = line[5:].split(' ')
            if len(parts) == 2:
                exits[parts[0]] = parts[1]
    return {'rows': rows, 'exits': exits, 'complete': started and ended}


def cmd_run(a):
    env = dict(os.environ)
    for d in (a.same, a.other):
        Path(d).mkdir(parents=True, exist_ok=True)
    r = subprocess.run(['sh', str(ROOT / 'census/run.sh'), os.path.abspath(a.bin), os.path.abspath(a.same),
                        os.path.abspath(a.other)], capture_output=True, text=True, errors='surrogateescape', env=env)
    rec = parse_lines(r.stdout.splitlines())
    rec['stderr'] = r.stderr
    rec['status'] = r.returncode
    Path(a.out).write_text(json.dumps(rec, indent=1, sort_keys=True) + '\n')
    print(r.stdout, end='')
    if r.stderr:
        print(''.join('  stderr: ' + line for line in r.stderr.splitlines(True)), end='')
    return 0 if rec['complete'] else 1


def cmd_parse(a):
    text = Path(a.console).read_text(errors='replace')
    text = re.sub(r'\x1b\[[0-9;?=<>]*[A-Za-z]', '', text)
    lines = [l for l in text.replace('\r', '').split('\n')]
    rec = parse_lines(lines)
    rec['platform'] = a.platform
    Path(a.out).write_text(json.dumps(rec, indent=1, sort_keys=True) + '\n')
    print('PASS census-parse rows=%d complete=%s' % (len(rec['rows']), rec['complete']))
    return 0 if rec['complete'] else 1


def load_expect():
    e = json.loads(EXPECT.read_text())
    for name, row in e['rows'].items():
        for platform, want in row.items():
            if platform == 'note':
                continue
            if want.get('status') not in STATUSES:
                raise ValueError('census/expect.json: %s %s: status must be one of %s' % (name, platform, STATUSES))
            if want['status'] != 'present' and not want.get('gap'):
                raise ValueError('census/expect.json: %s %s: a %s row names its gap' % (name, platform, want['status']))
            re.compile(want['want'])
    return e


def verdict(rec, expect, platform):
    """(failures, lines): one PASS or FAIL line per expected row, plus the exits."""
    out, fails = [], 0
    rows = rec['rows']
    if not rec.get('complete'):
        out.append('FAIL census-incomplete the record has no CENSUS end line')
        fails += 1
    for name in sorted(expect['rows']):
        want = expect['rows'][name].get(platform)
        if want is None:
            continue
        got = rows.get(name)
        if got is None:
            out.append('FAIL %s no-result' % name)
            fails += 1
            continue
        obs = ' | '.join(got)
        if re.fullmatch(want['want'], obs):
            tag = want['status'] + ('' if want['status'] == 'present' else ' (%s)' % want['gap'])
            out.append('PASS %s %s: %s' % (name, tag, obs))
        else:
            out.append('FAIL %s want %r got %r' % (name, want['want'], obs))
            fails += 1
    for name in sorted(rows):
        if name not in expect['rows'] or platform not in expect['rows'][name]:
            out.append('FAIL %s unexpected: %s' % (name, ' | '.join(rows[name])))
            fails += 1
    for prog, status in sorted(rec['exits'].items()):
        if status != '0':
            out.append('FAIL exit-%s status=%s' % (prog, status))
            fails += 1
    return fails, out


def cmd_verdict(a):
    rec = json.loads(Path(a.record).read_text())
    fails, lines = verdict(rec, load_expect(), a.platform)
    print('\n'.join(lines))
    print('SUMMARY census %s rows=%d failed=%d' % (a.platform, len(lines), fails))
    return 1 if fails else 0


def cmd_table(a):
    e = load_expect()
    recs = {}
    for platform in ('linux', 'pax'):
        path = getattr(a, platform)
        if path:
            recs[platform] = json.loads(Path(path).read_text())['rows']
    print('| row | Linux x86-64 | PAX | note |')
    print('|---|---|---|---|')
    for name in sorted(e['rows']):
        row = e['rows'][name]
        cells = []
        for platform in ('linux', 'pax'):
            w = row.get(platform)
            if w is None:
                cells.append('not run')
                continue
            got = ' \\| '.join(recs.get(platform, {}).get(name, ['?']))
            cells.append('%s%s: `%s`' % (w['status'], '' if w['status'] == 'present' else ' (%s)' % w['gap'], got))
        print('| %s | %s | %s | %s |' % (name, cells[0], cells[1], row.get('note', '')))
    return 0


def cmd_selftest(a):
    sample = ['noise', 'CENSUS start', 'ROW a@x ok', 'EXIT p@x 0', 'ROW b@x one', 'ROW b@x two',
              'EXIT q@x 134', 'CENSUS end']
    rec = parse_lines(sample)
    assert rec['rows'] == {'a@x': ['ok'], 'b@x': ['one', 'two']}, rec
    assert rec['exits'] == {'p@x': '0', 'q@x': '134'}, rec
    assert rec['complete']
    expect = {'rows': {
        'a@x': {'linux': {'want': 'ok', 'status': 'present'}},
        'b@x': {'linux': {'want': 'one \\| two', 'status': 'missing', 'gap': 'x#1'}},
        'c@x': {'linux': {'want': 'ok', 'status': 'present'}},
    }}
    fails, lines = verdict(rec, expect, 'linux')
    text = '\n'.join(lines)
    assert 'PASS a@x present' in text, text
    assert 'PASS b@x missing (x#1)' in text, text
    assert 'FAIL c@x no-result' in text, text
    assert 'FAIL exit-q@x status=134' in text, text
    assert fails == 2, (fails, text)
    rec['rows']['a@x'] = ['changed']
    fails, lines = verdict(rec, expect, 'linux')
    assert any(l.startswith("FAIL a@x want 'ok' got 'changed'") for l in lines), lines
    rec['rows']['d@x'] = ['new']
    fails, lines = verdict(rec, expect, 'linux')
    assert any(l.startswith('FAIL d@x unexpected') for l in lines), lines
    incomplete = parse_lines(sample[:-1])
    fails, lines = verdict(incomplete, expect, 'linux')
    assert lines[0].startswith('FAIL census-incomplete'), lines
    load_expect()
    print('PASS census-selftest')
    return 0


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest='cmd', required=True)
    b = sub.add_parser('build')
    b.add_argument('--wolf', required=True)
    b.add_argument('--out', required=True)
    b.add_argument('--static', action='store_true')
    r = sub.add_parser('run')
    for k in ('bin', 'same', 'other', 'out'):
        r.add_argument('--' + k, required=True)
    pa = sub.add_parser('parse')
    pa.add_argument('--console', required=True)
    pa.add_argument('--out', required=True)
    pa.add_argument('--platform', default='pax')
    v = sub.add_parser('verdict')
    v.add_argument('--record', required=True)
    v.add_argument('--platform', required=True, choices=('linux', 'pax'))
    t = sub.add_parser('table')
    t.add_argument('--linux')
    t.add_argument('--pax')
    sub.add_parser('selftest')
    a = p.parse_args()
    return {'build': cmd_build, 'run': cmd_run, 'parse': cmd_parse, 'verdict': cmd_verdict,
            'table': cmd_table, 'selftest': cmd_selftest}[a.cmd](a)


if __name__ == '__main__':
    sys.exit(main())
