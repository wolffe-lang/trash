#!/usr/bin/env python3
"""The expected captures of the rows where this repository departs from the
oracle by design (`"diverge"` in tests/oracle/rows.json), stated by hand.

  expected.py write   (re)writes tests/oracle/expected/ROW.json from the
                      statements below
  expected.py check   fails by name when a file there differs from them, or
                      when a diverging row has no statement or a statement no row

Each capture is what `tools/oracle.py compare` holds the candidate to: every
command's exit status and streams, and the trees the row leaves, in the
normalised form the harness writes (dates and times inside the run's window
read `<in-window>`). They were written from T1's design before the program
existed, and the candidate went red against every one of them first.
"""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'tests/oracle/expected'
FIX = 1700000000
W = '<in-window>'
H = '/tmp/trash-rows/home'
X = '/xdev/trash-rows'
SMALL_H = '/small/trash-rows/home'
USAGE = 'usage: trash [OPTION]... FILE...\n'


def d(mode='0755', mtime=FIX, owner='0:0', **exact):
    e = {'type': 'dir', 'mode': mode, 'mtime': mtime, 'owner': owner}
    e.update(exact)
    return e


def f(data, mode='0644', mtime=FIX, owner='0:0', **exact):
    if isinstance(data, str):
        data = data.encode()
    e = {'type': 'file', 'mode': mode, 'mtime': mtime, 'owner': owner, 'size': len(data),
         'sha256': hashlib.sha256(data).hexdigest()}
    e.update(exact)
    return e


def link(target, mtime=FIX, owner='0:0', **exact):
    e = {'type': 'link', 'mode': '0777', 'mtime': mtime, 'owner': owner, 'target': target}
    e.update(exact)
    return e


def other(kind, mode, mtime=FIX, owner='0:0', **exact):
    e = {'type': kind, 'mode': mode, 'mtime': mtime, 'owner': owner}
    e.update(exact)
    return e


def info(path, **exact):
    e = {'type': 'file', 'mode': '0600', 'mtime': W, 'owner': '0:0',
         'text': '[Trash Info]\nPath=%s\nDeletionDate=<in-window>\n' % path}
    e.update(exact)
    return e


def trash_dirs(**exact):
    """~/Trash, files/ and info/, made by this run."""
    return {'Trash': d('0700', W, **exact), 'Trash/files': d('0700', W, **exact), 'Trash/info': d('0700', W, **exact)}


def step(argv, exit=0, stdout='', stderr=''):
    return {'argv': argv, 'exit': exit, 'stdout': stdout, 'stderr': stderr}


def cap(row, steps, home, xdev=None, tz='UTC'):
    return {'row': row, 'tz': tz, 'steps': steps, 'trees': {'home': home, 'xdev': xdev or {}}, 'tracebacks': 0}


def big(n):
    block = bytes(i % 251 for i in range(65536))
    out = bytearray()
    while len(out) < n:
        out += block[:n - len(out)]
    return bytes(out)


EXACT_W = {'atime': W}  # an entry this run made: both times inside the window
NOT_UTF8 = "its name is not UTF-8, and wolf cannot name such a path yet (wolf-lang#687)"
LEFT = 'it is left where it was'


def statements():
    s = {}
    # The trash itself, and what is inside it.
    s['put-trash-itself'] = cap('put-trash-itself', [
        step(['trash', 'a.txt']),
        step(['trash', 'Trash/files/a.txt'], 74, stderr="trash: cannot trash 'Trash/files/a.txt': it is inside the trash\n"),
        step(['trash', 'Trash'], 74, stderr="trash: cannot trash 'Trash': it is the trash itself\n"),
    ], {**trash_dirs(), 'Trash/files/a.txt': f('hello\n'), 'Trash/info/a.txt.trashinfo': info(H + '/a.txt')})
    s['put-trash-inside'] = cap('put-trash-inside', [
        step(['trash', 'a.txt']),
        step(['trash', 'Trash/files'], 74, stderr="trash: cannot trash 'Trash/files': it is inside the trash\n"),
        step(['trash', 'Trash/info/'], 74, stderr="trash: cannot trash 'Trash/info/': it is inside the trash\n"),
        step(['trash', 'Trash/'], 74, stderr="trash: cannot trash 'Trash/': it is the trash itself\n"),
        step(['trash', H + '/Trash'], 74, stderr="trash: cannot trash '%s/Trash': it is the trash itself\n" % H),
        step(['trash', 'tl/files/a.txt'], 74, stderr="trash: cannot trash 'tl/files/a.txt': it is inside the trash\n"),
        step(['trash', 'tl']),
    ], {**trash_dirs(), 'Trash/files/a.txt': f('hello\n'), 'Trash/files/tl': link('Trash'),
        'Trash/info/a.txt.trashinfo': info(H + '/a.txt'), 'Trash/info/tl.trashinfo': info(H + '/tl')})
    s['put-home'] = cap('put-home', [
        step(['trash', H], 74, stderr="trash: cannot trash '%s': it holds the trash\n" % H),
    ], {'a.txt': f('hello\n')})
    s['put-mount-point'] = cap('put-mount-point', [
        step(['trash', '/xdev'], 74, stderr="trash: cannot trash '/xdev': it is a mount point\n"),
    ], {}, {'x.txt': f('x\n')})
    # The root, and . or .. once trailing slashes go.
    s['put-root'] = cap('put-root', [step(['trash', '/'], 74, stderr="trash: cannot trash directory '/'\n")], {})
    s['put-root-spellings'] = cap('put-root-spellings', [
        step(['trash', '///'], 74, stderr="trash: cannot trash directory '///'\n"),
        step(['trash', '/.'], 74, stderr="trash: cannot trash '.' directory '/.'\n"),
        step(['trash', '/tmp/../..'], 74, stderr="trash: cannot trash '..' directory '/tmp/../..'\n"),
        step(['trash', '../../../../..'], 74, stderr="trash: cannot trash '..' directory '../../../../..'\n"),
    ], {'sub': d()})
    s['put-dot-slash'] = cap('put-dot-slash', [
        step(['trash', './'], 74, stderr="trash: cannot trash directory './'\n"),
        step(['trash', 'deeper/.//'], 74, stderr="trash: cannot trash '.' directory 'deeper/.//'\n"),
        step(['trash', 'deeper/../'], 74, stderr="trash: cannot trash '..' directory 'deeper/../'\n"),
    ], {'sub': d(mtime=W), 'sub/deeper': d()})
    # A name wolf cannot reach yet.
    s['put-not-utf8'] = cap('put-not-utf8', [
        step(['trash', 'x\\xffy'], 74, stderr="trash: cannot trash 'x\\xffy': %s\n" % NOT_UTF8),
    ], {'x\\xffy': f('x\n')})
    # The end of input under -i is a no.
    s['put-interactive-eof'] = cap('put-interactive-eof', [
        step(['trash', '-i', 'a'], 0, stdout="trash: trash regular file 'a'? "),
    ], {'a': f('a\n')})
    # --trash-dir is not taken: this trash is always ~/Trash.
    unknown = USAGE + 'trash: error: unrecognized arguments: --trash-dir\n'
    s['put-other-fs-home-trash'] = cap('put-other-fs-home-trash', [
        step(['trash', '--trash-dir', H + '/Trash', X + '/x.txt'], 2, stderr=unknown),
    ], {}, {'x.txt': f('x\n')})
    s['put-other-fs-dir-home-trash'] = cap('put-other-fs-dir-home-trash', [
        step(['trash', '--trash-dir', H + '/Trash', X + '/d'], 2, stderr=unknown),
    ], {}, {'d': d(), 'd/f': f('f\n', '0640'), 'd/l': link('f')})
    # Across file systems: copied, verified, then the source removed.
    s['put-other-fs'] = cap('put-other-fs', [step(['trash', X + '/x.txt'])],
                            {**trash_dirs(), 'Trash/files/x.txt': f('x\n'), 'Trash/info/x.txt.trashinfo': info(X + '/x.txt')})
    s['put-other-fs-collision'] = cap('put-other-fs-collision', [step(['trash', 'x.txt']), step(['trash', X + '/x.txt'])],
                                      {**trash_dirs(), 'Trash/files/x.txt': f('home\n'), 'Trash/files/x.txt_1': f('xdev\n'),
                                       'Trash/info/x.txt.trashinfo': info(H + '/x.txt'),
                                       'Trash/info/x.txt_1.trashinfo': info(X + '/x.txt')})
    s['put-other-fs-verbose'] = cap('put-other-fs-verbose', [
        step(['trash', '-v', X + '/x.txt'], stderr="trash: '%s/x.txt' trashed in ~/Trash\n" % X),
    ], {**trash_dirs(), 'Trash/files/x.txt': f('x\n'), 'Trash/info/x.txt.trashinfo': info(X + '/x.txt')})
    z = {'mtime_ns': 0, 'atime': FIX, 'atime_ns': 0}  # a fixture entry's stamp, exactly
    s['put-other-fs-tree'] = cap('put-other-fs-tree', [step(['trash', X + '/d'])], {
        **trash_dirs(**EXACT_W),
        'Trash/files/d': d('0750', 1200000000, mtime_ns=9, atime=1200000001, atime_ns=10),
        'Trash/files/d/dangling': link('nowhere', mtime_ns=0),
        'Trash/files/d/empty': f('', **z),
        'Trash/files/d/f': f('f\n', '0640', 1600000000, '4321:4322', mtime_ns=123456789, atime=1500000000, atime_ns=987654321),
        'Trash/files/d/p': other('fifo', '0600', **z),
        'Trash/files/d/sub': d(**z),
        'Trash/files/d/sub/ro': d('0500', 1300000000, mtime_ns=7, atime=1300000001, atime_ns=8),
        'Trash/files/d/sub/ro/g': f('g\n', '0444', **z),
        'Trash/files/d/sub/up': link('../f', 1400000000, '4323:4324', mtime_ns=5),
        'Trash/files/d/x.sh': f('#!/bin/sh\n', '0755', **z),
        'Trash/info/d.trashinfo': info(X + '/d', **EXACT_W),
    })
    s['put-other-fs-symlink'] = cap('put-other-fs-symlink', [step(['trash', X + '/l'])], {
        **trash_dirs(**EXACT_W),
        'Trash/files/l': link('t', 1400000000, mtime_ns=11),
        'Trash/info/l.trashinfo': info(X + '/l', **EXACT_W),
    }, {'t': f('t\n', **z)})
    s['put-other-fs-space'] = cap('put-other-fs-space', [
        step(['trash', X + '/big'], 74,
             stderr="trash: cannot trash '%s/big': the home volume has too little free space to copy it\n" % X),
    ], trash_dirs(), {'big': f(big(3145728))})
    s['put-other-fs-fits'] = cap('put-other-fs-fits', [step(['trash', X + '/fits'])],
                                 {**trash_dirs(), 'Trash/files/fits': f(big(262144)),
                                  'Trash/info/fits.trashinfo': info(X + '/fits')})
    s['put-other-fs-fail-socket'] = cap('put-other-fs-fail-socket', [
        step(['trash', X + '/d'], 74,
             stderr="trash: cannot trash '%s/d': '%s/d/s' is a socket, which cannot be copied to the home volume; %s\n"
             % (X, X, LEFT)),
    ], trash_dirs(), {'d': d(), 'd/a': f('a\n'), 'd/s': other('socket', '0755'), 'd/z': f('z\n')})
    s['put-other-fs-fail-name'] = cap('put-other-fs-fail-name', [
        step(['trash', X + '/d'], 74,
             stderr="trash: cannot trash '%s/d': the name of an entry in '%s/d' (b\\xffc) is not UTF-8, and wolf cannot "
                    "name such a path yet (wolf-lang#687); %s\n" % (X, X, LEFT)),
    ], trash_dirs(), {'d': d(), 'd/a': f('a\n'), 'd/b\\xffc': f('b\n'), 'd/sub': d(), 'd/sub/z': f('z\n')})
    return s


def rendered(c):
    return json.dumps(c, indent=1, sort_keys=True, ensure_ascii=False) + '\n'


def diverging():
    rows = json.loads((ROOT / 'tests/oracle/rows.json').read_text())['rows']
    return {r['name'] for r in rows if r.get('diverge')}


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else 'check'
    s = statements()
    bad = 0
    want = diverging()
    for name in sorted(want - set(s)):
        print('FAIL expected-%s a diverging row with no statement' % name)
        bad += 1
    for name in sorted(set(s) - want):
        print('FAIL expected-%s a statement with no diverging row' % name)
        bad += 1
    if mode == 'write':
        OUT.mkdir(parents=True, exist_ok=True)
        for name, c in sorted(s.items()):
            (OUT / (name + '.json')).write_text(rendered(c))
            print('WROTE %s' % name)
        return 1 if bad else 0
    for name, c in sorted(s.items()):
        path = OUT / (name + '.json')
        if not path.exists() or path.read_text() != rendered(c):
            print('FAIL expected-%s tests/oracle/expected/%s.json differs from its statement' % (name, name))
            bad += 1
        else:
            print('PASS expected-%s' % name)
    for p in sorted(OUT.glob('*.json')):
        if p.stem not in s:
            print('FAIL expected-%s a file with no statement' % p.stem)
            bad += 1
    print('SUMMARY expected rows=%d failed=%d' % (len(s), bad))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
