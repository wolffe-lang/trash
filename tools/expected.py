#!/usr/bin/env python3
"""The expected captures of the rows with no oracle, stated by hand: the rows
where this repository departs from the oracle by design (`"diverge"` in
tests/oracle/rows.json), and every PAX row (tests/pax/rows.json).

  expected.py write   (re)writes tests/oracle/expected/ROW.json and
                      tests/pax/expected/ROW.json from the statements below
  expected.py check   fails by name when a file there differs from them, or
                      when a row has no statement or a statement no row

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
OUT_PAX = ROOT / 'tests/pax/expected'
OUT_CUTS = ROOT / 'tests/cuts/expected'
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
    s.update(companions())
    s.update(hardening())
    return s


PH = '/home/rh'
PX = '/tmp/rows'


def pax_statements():
    """PAX's rows: the home on PAX's ext2 disk, the second store its in-memory
    /tmp. The same program, so the same captures as on Linux where the rows
    agree, at PAX's paths."""
    s = {}
    s['pax-put-file'] = cap('pax-put-file', [step(['trash', 'a.txt'])],
                            {**trash_dirs(), 'Trash/files/a.txt': f('hello\n'), 'Trash/info/a.txt.trashinfo': info(PH + '/a.txt')})
    s['pax-put-dir'] = cap('pax-put-dir', [step(['trash', 'd'])], {
        **trash_dirs(), 'Trash/files/d': d(), 'Trash/files/d/f': f('f\n'), 'Trash/files/d/lf': link('f'),
        'Trash/files/d/sub': d(), 'Trash/files/d/sub/g': f('g\n'), 'Trash/info/d.trashinfo': info(PH + '/d')})
    s['pax-put-links'] = cap('pax-put-links', [step(['trash', 'l', 'dl'])], {
        **trash_dirs(), 'Trash/files/l': link('a.txt'), 'Trash/files/dl': link('nowhere/x'),
        'Trash/info/l.trashinfo': info(PH + '/l'), 'Trash/info/dl.trashinfo': info(PH + '/dl'), 'a.txt': f('hello\n')})
    s['pax-put-collision'] = cap('pax-put-collision', [step(['trash', 'a.txt'])] * 3, {
        **trash_dirs(), 'Trash/files/a.txt': f('1\n'), 'Trash/files/a.txt_1': f('2\n'), 'Trash/files/a.txt_2': f('3\n'),
        'Trash/info/a.txt.trashinfo': info(PH + '/a.txt'), 'Trash/info/a.txt_1.trashinfo': info(PH + '/a.txt'),
        'Trash/info/a.txt_2.trashinfo': info(PH + '/a.txt')})
    s['pax-put-names'] = cap('pax-put-names', [step(['trash', 'my file é.txt', 'a.tar.gz'])], {
        **trash_dirs(), 'Trash/files/my file é.txt': f('x\n'), 'Trash/files/a.tar.gz': f('z\n'),
        'Trash/info/my file é.txt.trashinfo': info(PH + '/my%20file%20%C3%A9.txt'),
        'Trash/info/a.tar.gz.trashinfo': info(PH + '/a.tar.gz')})
    n250, n238 = 'n' * 250, 'n' * 238 + '_1'
    s['pax-put-long-name'] = cap('pax-put-long-name', [step(['trash', n250])], {
        **trash_dirs(), 'Trash/files/' + n238: f('l\n'), 'Trash/info/%s.trashinfo' % n238: info(PH + '/' + n250)})
    s['pax-put-refusals'] = cap('pax-put-refusals', [
        step(['trash', '.'], 74, stderr="trash: cannot trash directory '.'\n"),
        step(['trash', '..'], 74, stderr="trash: cannot trash directory '..'\n"),
        step(['trash', '/'], 74, stderr="trash: cannot trash directory '/'\n"),
        step(['trash', 'nope'], 74, stderr="trash: cannot trash non existent 'nope'\n"),
        step(['trash', '-f', 'nope']),
        step(['trash', 'a']),
        step(['trash', 'Trash/files/a'], 74, stderr="trash: cannot trash 'Trash/files/a': it is inside the trash\n"),
        step(['trash', 'Trash'], 74, stderr="trash: cannot trash 'Trash': it is the trash itself\n"),
    ], {**trash_dirs(), 'Trash/files/a': f('a\n'), 'Trash/info/a.trashinfo': info(PH + '/a'), 'sub': d(mtime=W),
        'sub/deeper': d()})
    s['pax-put-flags'] = cap('pax-put-flags', [
        step(['trash', '-v', 'a', 'd'], stderr="trash: 'a' trashed in ~/Trash\ntrash: 'd' trashed in ~/Trash\n"),
        step(['trash', '-i', 'b', 'c'], stdout="trash: trash regular file 'b'? trash: trash regular file 'c'? "),
        step(['trash'], 2, stderr=USAGE + 'trash: error: Please specify the files to trash.\n'),
        step(['trash', '-x', 'c'], 2, stderr=USAGE + 'trash: error: unrecognized arguments: -x\n'),
    ], {**trash_dirs(), 'Trash/files/a': f('a\n'), 'Trash/files/b': f('b\n'), 'Trash/files/d': d(),
        'Trash/info/a.trashinfo': info(PH + '/a'), 'Trash/info/b.trashinfo': info(PH + '/b'),
        'Trash/info/d.trashinfo': info(PH + '/d'), 'c': f('c\n')})
    unreachable = {'type': 'unreachable', 'mode': '?', 'mtime': 0, 'owner': '?'}
    s['pax-put-not-utf8'] = cap('pax-put-not-utf8', [
        step(['trash', '--', 'x\\xffy'], 74, stderr="trash: cannot trash 'x\\xffy': %s\n" % NOT_UTF8),
    ], {'x\\xffy': unreachable})
    s['pax-tmp-file'] = cap('pax-tmp-file', [step(['trash', PX + '/x.txt'])],
                            {**trash_dirs(), 'Trash/files/x.txt': f('x\n'), 'Trash/info/x.txt.trashinfo': info(PX + '/x.txt')})
    z = {'mtime_ns': 0, 'atime': FIX, 'atime_ns': 0}
    s['pax-tmp-tree'] = cap('pax-tmp-tree', [step(['trash', PX + '/d'])], {
        **trash_dirs(**EXACT_W),
        'Trash/files/d': d('0750', 1200000000, mtime_ns=9, atime=1200000001, atime_ns=10),
        'Trash/files/d/dangling': link('nowhere', mtime_ns=0),
        'Trash/files/d/empty': f('', **z),
        'Trash/files/d/f': f('f\n', '0640', 1600000000, '4321:4322', mtime_ns=123456789, atime=1500000000, atime_ns=987654321),
        'Trash/files/d/sub': d(**z),
        'Trash/files/d/sub/ro': d('0500', 1300000000, mtime_ns=7, atime=1300000001, atime_ns=8),
        'Trash/files/d/sub/ro/g': f('g\n', '0444', **z),
        'Trash/files/d/sub/up': link('../f', 1400000000, '4323:4324', mtime_ns=5),
        'Trash/files/d/x.sh': f('#!/bin/sh\n', '0755', **z),
        'Trash/info/d.trashinfo': info(PX + '/d', **EXACT_W),
    })
    s['pax-tmp-collision'] = cap('pax-tmp-collision', [
        step(['trash', 'x.txt']), step(['trash', '-v', PX + '/x.txt'], stderr="trash: '%s/x.txt' trashed in ~/Trash\n" % PX),
    ], {**trash_dirs(), 'Trash/files/x.txt': f('home\n'), 'Trash/files/x.txt_1': f('tmp\n'),
        'Trash/info/x.txt.trashinfo': info(PH + '/x.txt'), 'Trash/info/x.txt_1.trashinfo': info(PX + '/x.txt')})
    s['pax-tmp-space'] = cap('pax-tmp-space', [
        step(['trash', PX + '/big'], 74,
             stderr="trash: cannot trash '%s/big': the home volume has too little free space to copy it\n" % PX),
    ], trash_dirs(), {'big': f(big(41943040))})
    s['pax-tmp-fail-name'] = cap('pax-tmp-fail-name', [
        step(['trash', PX + '/d'], 74,
             stderr="trash: cannot trash '%s/d': the name of an entry in '%s/d' (b\\xffc) is not UTF-8, and wolf cannot "
                    "name such a path yet (wolf-lang#687); %s\n" % (PX, PX, LEFT)),
    ], trash_dirs(), {'d': d(), 'd/a': f('a\n'), 'd/b\\xffc': unreachable, 'd/sub': d(), 'd/sub/z': f('z\n')})
    s.update(pax_companions())
    return s


# ---------------------------------------------------------------- T2: the companions

LIST_USAGE = 'usage: trash-list [-h] [--version]\n'
RESTORE_USAGE = 'usage: trash-restore [-h] [--sort {date,path,none}] [--version] [path]\n'
EMPTY_USAGE = 'usage: trash-empty [-h] [--version] [-v] [-i] [-f] [--dry-run] [days]\n'
RM_USAGE = ('Usage:\n    trash-rm PATTERN\n\nPlease specify PATTERN.\n'
            "PATTERN is matched as a shell pattern (*, ?, [...] and [!...]) against each item's original name, "
            "or against its whole original path when it starts with '/'.\n")
NOT_UTF8_PATH = "its path is not UTF-8, and wolf cannot name such a path yet (wolf-lang#687)"
PROMPT = 'What file to restore [0..%d]: '
ASK = 'Would empty the following trash directories:\n    - %s/Trash\nProceed? (y/N) ' % H


def fixture_dirs():
    """Trash/, files/ and info/ as a fixture's info files make them: 0755, made in the window."""
    return {'Trash': d('0755', W), 'Trash/files': d('0755', W), 'Trash/info': d('0755', W)}


def fixture_info(path, date=None, text=None):
    """An info file a fixture wrote, stamped with the fixture's time."""
    if text is None:
        text = '[Trash Info]\nPath=%s\n' % path + ('' if date is None else 'DeletionDate=<outside-window:%s>\n' % date)
    return {'type': 'file', 'mode': '0600', 'mtime': FIX, 'owner': '0:0', 'text': text}


def listed(i, date, path):
    return '%4d %s %s\n' % (i, date, path)


def plan_tree(plan, exact=True):
    """A generated tree's entries (tools/oracle.py's tree_plan), as a snapshot reads them."""
    out = {}
    for e in plan:
        ms, mns, as_, ans = e['times']
        rel = e['path'][len('@xdev/'):] if e['path'].startswith('@xdev/') else e['path']
        mode = '%04o' % e['mode']
        if e['kind'] == 'dir':
            out[rel] = d(mode, ms, e['owner'], mtime_ns=mns, atime=as_, atime_ns=ans)
        elif e['kind'] == 'file':
            out[rel] = f(e['data'], mode, ms, e['owner'], mtime_ns=mns, atime=as_, atime_ns=ans)
        elif e['kind'] == 'link':
            out[rel] = link(e['target'], ms, e['owner'], mtime_ns=mns)
        else:
            out[rel] = other(e['kind'], mode, ms, e['owner'], mtime_ns=mns, atime=as_, atime_ns=ans)
    return out


def oracle_tool():
    import importlib.util
    spec = importlib.util.spec_from_file_location('oracle', ROOT / 'tools/oracle.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def companions():
    """The companions' rows where this repository departs from the oracle."""
    s = {}
    unknown = lambda usage, prog, words: usage + '%s: error: unrecognized arguments: %s\n' % (prog, words)
    # Usage errors, in this repository's usage lines.
    s['list-unknown'] = cap('list-unknown', [step(['trash-list', '-x'], 2, stderr=unknown(LIST_USAGE, 'trash-list', '-x'))], {})
    s['list-extra'] = cap('list-extra', [step(['trash-list', 'extra'], 2,
                                               stderr=unknown(LIST_USAGE, 'trash-list', 'extra'))], {})
    s['list-trash-kin'] = cap('list-trash-kin', [
        step(['trash-list', '--trash-dir', H + '/Trash'], 2,
             stderr=unknown(LIST_USAGE, 'trash-list', '--trash-dir %s/Trash' % H)),
        step(['trash-list', '--trash-dirs'], 2, stderr=unknown(LIST_USAGE, 'trash-list', '--trash-dirs')),
        step(['trash-list', '--all-users'], 2, stderr=unknown(LIST_USAGE, 'trash-list', '--all-users')),
        step(['trash-list', '--print-completion', 'bash'], 2,
             stderr=unknown(LIST_USAGE, 'trash-list', '--print-completion bash')),
    ], {})
    one = {**fixture_dirs(), 'Trash/files/a': f('a\n'), 'Trash/info/a.trashinfo': fixture_info(H + '/a', '2021-01-01T00:00:00')}
    s['restore-sort-bad'] = cap('restore-sort-bad', [
        step(['trash-restore', '--sort', 'bogus'], 2,
             stderr=RESTORE_USAGE + "trash-restore: error: argument --sort: invalid choice: 'bogus' "
                                    "(choose from 'date', 'path', 'none')\n"),
    ], one)
    s['restore-sort-none'] = cap('restore-sort-none', [
        step(['trash-restore', '--sort', 'none'], stdout=listed(0, '2021-01-01 00:00:00', H + '/a') + PROMPT % 0),
    ], {**fixture_dirs(), 'a': f('a\n')})
    s['restore-no-date'] = cap('restore-no-date', [
        step(['trash-restore'], stdout=listed(0, '????-??-?? ??:??:??', H + '/nd') + listed(1, '2020-01-01 00:00:00', H + '/d1') +
             PROMPT % 1),
    ], {**fixture_dirs(), 'Trash/files/d1': f('d1\n'), 'Trash/info/d1.trashinfo': fixture_info(H + '/d1', '2020-01-01T00:00:00'),
        'nd': f('nd\n')})
    put_a = {**trash_dirs(), 'Trash/files/a.txt': f('a\n'), 'Trash/info/a.txt.trashinfo': info(H + '/a.txt')}
    s['restore-overwrite'] = cap('restore-overwrite', [
        step(['trash', 'a.txt']),
        step(['trash-restore', '--overwrite'], 2, stderr=unknown(RESTORE_USAGE, 'trash-restore', '--overwrite')),
    ], {**put_a, 'a.txt': f('new\n')})
    # Across file systems: copied back, then removed from the trash.
    z = {'mtime_ns': 0, 'atime': FIX, 'atime_ns': 0}
    s['restore-other-fs'] = cap('restore-other-fs', [
        step(['trash', X + '/x.txt', X + '/t']),
        step(['trash-restore', X + '/x.txt'], stdout=listed(0, W, X + '/x.txt') + PROMPT % 0),
        step(['trash-restore', X + '/t'], stdout=listed(0, W, X + '/t') + PROMPT % 0),
    ], trash_dirs(**EXACT_W), {
        'x.txt': f('x\n', '0640', FIX, '1000:1000', **z),
        't': d('0750', **z),
        't/f': f('f\n', '0644', 1600000000, mtime_ns=123456789, atime=1600000001, atime_ns=987654321),
        't/l': link('f', mtime_ns=0),
    })
    s['restore-other-fs-occupied'] = cap('restore-other-fs-occupied', [
        step(['trash', X + '/x.txt']),
        step(['trash-restore', X + '/x.txt'], 1, stdout=listed(0, W, X + '/x.txt') + PROMPT % 0,
             stderr='Refusing to overwrite existing file "x.txt".\n'),
    ], {**trash_dirs(), 'Trash/files/x.txt': f('x\n'), 'Trash/info/x.txt.trashinfo': info(X + '/x.txt')}, {'x.txt': f('new\n')})
    # The trash itself.
    s['restore-into-trash'] = cap('restore-into-trash', [
        step(['trash-restore'], 1,
             stdout=listed(0, '2020-01-01 00:00:00', H + '/Trash/files/a.txt') + listed(1, '2021-01-01 00:00:00', H + '/a.txt') +
             PROMPT % 1,
             stderr="trash-restore: cannot restore '%s/Trash/files/a.txt': it is inside the trash\n" % H),
    ], {**fixture_dirs(), 'Trash/files/a.txt': f('a.txt\n'), 'Trash/files/a.txt_1': f('a.txt_1\n'),
        'Trash/info/a.txt.trashinfo': fixture_info(H + '/a.txt', '2021-01-01T00:00:00'),
        'Trash/info/a.txt_1.trashinfo': fixture_info(H + '/Trash/files/a.txt', '2020-01-01T00:00:00')})
    s['restore-trash-given'] = cap('restore-trash-given', [
        step(['trash', 'a.txt']),
        step(['trash-restore', H + '/Trash'], 1,
             stderr="trash-restore: cannot restore from '%s/Trash': it is the trash itself\n" % H),
    ], put_a)
    # Names wolf cannot reach yet.
    s['restore-not-utf8'] = cap('restore-not-utf8', [
        step(['trash-restore'], 1, stdout=listed(0, '2020-01-01 00:00:00', H + '/x\\xffy') + PROMPT % 0,
             stderr="trash-restore: cannot restore '%s/x\\xffy': %s\n" % (H, NOT_UTF8_PATH)),
    ], {**fixture_dirs(), 'Trash/files/x': f('x\n'), 'Trash/info/x.trashinfo': fixture_info(H + '/x%FFy', '2020-01-01T00:00:00')})
    s['list-not-utf8-info'] = cap('list-not-utf8-info', [
        step(['trash-list'], stdout='2021-01-01 00:00:00 %s/ok\n' % H,
             stderr="trash-list: cannot read '%s/Trash/info/x\\xffy.trashinfo': %s\n" % (H, NOT_UTF8)),
    ], {**fixture_dirs(), 'Trash/files/ok': f('ok\n'), 'Trash/files/x\\xffy': f('x\n'),
        'Trash/info/ok.trashinfo': fixture_info(H + '/ok', '2021-01-01T00:00:00'),
        'Trash/info/x\\xffy.trashinfo': fixture_info(H + '/xy', '2020-01-01T00:00:00')})
    s['empty-not-utf8-tree'] = cap('empty-not-utf8-tree', [
        step(['trash', 'd', 'a.txt']),
        step(['trash-empty'], 1,
             stderr="trash-empty: cannot remove '%s/Trash/files/d': the name of an entry in '%s/Trash/files/d' (x\\xffy) is "
                    "not UTF-8, and wolf cannot name such a path yet (wolf-lang#687); it is left in the trash\n" % (H, H)),
    ], {**trash_dirs(), 'Trash/files/d': d(), 'Trash/files/d/x\\xffy': f('x\n'), 'Trash/info/d.trashinfo': info(H + '/d')})
    # trash-rm's usage text: its last line in this repository's words.
    s['rm-no-arg'] = cap('rm-no-arg', [
        step(['trash', 'a.txt']), step(['trash-rm'], 8, stderr=RM_USAGE),
        step(['trash-list'], stdout='%s %s/a.txt\n' % (W, H)),
    ], put_a)
    # trash-empty's usage errors, and the end of input under -i (a no).
    for name, arg in (('word', 'x'), ('fraction', '1.5')):
        s['empty-days-' + name] = cap('empty-days-' + name, [
            step(['trash', 'a.txt']),
            step(['trash-empty', arg], 2, stderr=EMPTY_USAGE + "trash-empty: error: argument days: invalid int value: '%s'\n" % arg),
            step(['trash-list'], stdout='%s %s/a.txt\n' % (W, H)),
        ], put_a)
    s['empty-trash-dir'] = cap('empty-trash-dir', [
        step(['trash', 'a.txt']),
        step(['trash-empty', '--trash-dir', H + '/Trash'], 2, stderr=unknown(EMPTY_USAGE, 'trash-empty', '--trash-dir')),
    ], put_a)
    s['empty-i-eof'] = cap('empty-i-eof', [
        step(['trash', 'a.txt']), step(['trash-empty', '-i'], stdout=ASK),
        step(['trash-list'], stdout='%s %s/a.txt\n' % (W, H)),
    ], put_a)
    # An info file that cannot be read or parsed: kept under DAYS; named in restore's own words.
    nopath_text = '[Trash Info]\nDeletionDate=<outside-window:2020-01-01T00:00:00>\n'
    s['empty-info-shapes-days'] = cap('empty-info-shapes-days', [step(['trash-empty', '1'])], {
        **fixture_dirs(), 'Trash/files/empty': f('empty\n'), 'Trash/files/nopath': f('nopath\n'),
        'Trash/info/empty.trashinfo': fixture_info(None, text=''), 'Trash/info/nopath.trashinfo': fixture_info(None, text=nopath_text),
        'Trash/info/notinfo.txt': f('n\n', '0600'), 'Trash/info/sub.trashinfo': d('0700'), 'Trash/info/sub.trashinfo/f': f('f\n')})
    sub = H + '/Trash/info/sub.trashinfo'
    s['restore-info-shapes'] = cap('restore-info-shapes', [
        step(['trash-restore'], stdout=listed(0, '2020-01-01 00:00:00', H + '/ok') + PROMPT % 0,
             stderr=''.join(sorted([
                 "Unreadable trashinfo file: %s, because [Errno 21] Is a directory: '%s'\n" % (sub, sub),
                 'Non parsable trashinfo file: %s/Trash/info/nopath.trashinfo, because Unable to parse Path\n' % H,
                 'Non parsable trashinfo file: %s/Trash/info/empty.trashinfo, because Unable to parse Path\n' % H]))),
    ], {**fixture_dirs(), 'Trash/files/empty': f('empty\n'), 'Trash/files/nopath': f('nopath\n'),
        'Trash/info/empty.trashinfo': fixture_info(None, text=''), 'Trash/info/nopath.trashinfo': fixture_info(None, text=nopath_text),
        'Trash/info/sub.trashinfo': d('0700'), 'ok': f('ok\n')})
    s['restore-bad-date'] = cap('restore-bad-date', [
        step(['trash-restore'], stdout=listed(0, '????-??-?? ??:??:??', H + '/bad') + listed(1, '2020-01-01 00:00:00', H + '/d1') +
             PROMPT % 1),
    ], {**fixture_dirs(), 'Trash/files/d1': f('d1\n'), 'Trash/info/d1.trashinfo': fixture_info(H + '/d1', '2020-01-01T00:00:00'),
        'bad': f('bad\n')})
    isdir = "[Errno 21] Is a directory: '%s/Trash/info/sub.trashinfo'" % H
    s['rm-info-dir'] = cap('rm-info-dir', [
        step(['trash-rm', 'ok'], stderr='trash-rm: %s\n' % isdir), step(['trash-list'], stderr=isdir + '\n'),
    ], {**fixture_dirs(), 'Trash/info/sub.trashinfo': d('0700')})
    # The round trip across file systems: copied in, copied back, every entry as it was.
    oracle = oracle_tool()
    trees = {}
    for i in range(1, 7):
        trees.update(plan_tree(oracle.tree_plan('@xdev/t%d' % i, 10 + i)))
    c = cap('roundtrip-other-fs', [step(['trash'] + [X + '/t%d' % i for i in range(1, 7)])] +
            [step(['trash-restore', X + '/t%d' % i], stdout=listed(0, W, X + '/t%d' % i) + PROMPT % 0) for i in range(1, 7)],
            trash_dirs(**EXACT_W), trees)
    c['property'] = []
    s['roundtrip-other-fs'] = c
    return s


def pax_companions():
    """The companions on PAX, at PAX's paths."""
    s = {}
    pdirs = {'Trash': d('0755', W), 'Trash/files': d('0755', W), 'Trash/info': d('0755', W)}
    s['pax-list'] = cap('pax-list', [
        step(['trash', 'a.txt', 'd']),
        step(['trash-list'], stdout='2020-01-02 03:04:05 %s/old one\n%s %s/a.txt\n%s %s/d\n' % (PH, W, PH, W, PH)),
    ], {**pdirs, 'Trash/files/a.txt': f('a\n'), 'Trash/files/d': d(), 'Trash/files/d/f': f('f\n'), 'Trash/files/old': f('o\n'),
        'Trash/info/a.txt.trashinfo': info(PH + '/a.txt'), 'Trash/info/d.trashinfo': info(PH + '/d'),
        'Trash/info/old.trashinfo': fixture_info(PH + '/old%20one', '2020-01-02T03:04:05')})
    s['pax-restore'] = cap('pax-restore', [
        step(['trash', 'a.txt', 'd', 'l']),
        step(['trash-restore', PH + '/a.txt'], stdout=listed(0, W, PH + '/a.txt') + PROMPT % 0),
        step(['trash-restore', PH + '/d'], stdout=listed(0, W, PH + '/d') + PROMPT % 0),
        step(['trash-restore', PH + '/l'], stdout=listed(0, W, PH + '/l') + PROMPT % 0),
        step(['trash', 'a.txt']),
        step(['trash-restore', PH + '/a.txt'], 1, stdout=listed(0, W, PH + '/a.txt') + PROMPT % 0,
             stderr='Refusing to overwrite existing file "a.txt".\n'),
    ], {**trash_dirs(), 'Trash/files/a.txt': f('a\n'), 'Trash/info/a.txt.trashinfo': info(PH + '/a.txt'), 'a.txt': f('new\n'),
        'd': d(), 'd/f': f('f\n'), 'l': link('a.txt')})
    s['pax-rm'] = cap('pax-rm', [
        step(['trash', 'a.txt', 'b.txt', 'c.log']), step(['trash-rm', '*.txt']),
        step(['trash-list'], stdout='%s %s/c.log\n' % (W, PH)),
    ], {**trash_dirs(), 'Trash/files/c.log': f('c\n'), 'Trash/info/c.log.trashinfo': info(PH + '/c.log')})
    s['pax-empty'] = cap('pax-empty', [
        step(['trash', 'a.txt']), step(['trash-empty', '1']), step(['trash-list'], stdout='%s %s/a.txt\n' % (W, PH)),
        step(['trash-empty']), step(['trash-list']),
    ], pdirs)
    z = {'mtime_ns': 0, 'atime': FIX, 'atime_ns': 0}
    s['pax-roundtrip'] = cap('pax-roundtrip', [
        step(['trash', PX + '/t', 'h']),
        step(['trash-restore', PX + '/t'], stdout=listed(0, W, PX + '/t') + PROMPT % 0),
        step(['trash-restore', PH + '/h'], stdout=listed(0, W, PH + '/h') + PROMPT % 0),
    ], {**trash_dirs(**EXACT_W), 'h': d('0700', **z), 'h/x': f('x\n', '0600', 1500000000, mtime_ns=5, atime=1500000002, atime_ns=7),
        'h/up': link('../h', mtime_ns=0)}, {
        't': d('0750', **z), 't/f': f('f\n', '0640', 1600000000, mtime_ns=123456789, atime=1600000001, atime_ns=987654321),
        't/sub': d(**z), 't/sub/g': f('g\n', **z), 't/l': link('f', mtime_ns=0)})
    return s


T = H + '/Trash'
PENDING = '[Trash Info]\n# being copied into the trash\n'
NO_ITEM = "trash-list: '%s/info/%%s.trashinfo' names an item that is not in the trash\n" % T
NO_INFO = "trash-list: '%s/files/%%s' has no info file, so where it came from is not known\n" % T
UNPARSED = 'Parse Error: %s/info/%%s.trashinfo: Unable to parse Path.\n' % T


def ran(exit=0, stdout='', stderr=''):
    return {'exit': exit, 'stdout': stdout, 'stderr': stderr}


def lines(*xs):
    """A listing's lines as the cut harness holds them: sorted."""
    return ''.join(sorted(xs))


def cut(step_name, trees, listing, rerun, after='whole', run=None):
    return {'step': step_name, 'run': run or ran(-9), 'trees': trees, 'list': listing, 'rerun': rerun, 'after': after}


def cut_cap(row, whole_run, whole_trees, cuts):
    return {'row': row, 'whole': {'run': whole_run, 'trees': whole_trees}, 'cuts': cuts}


def homes(home, xdev=None):
    return {'home': home, 'xdev': xdev or {}}


def cut_statements():
    """The cut rows (tests/cuts/rows.json): the state each cut leaves, what
    the listing names, and what the rerun does. Written from T3's design
    (notes/tb03-hardening-and-the-image.md) before the hook and the
    hardening existed."""
    s = {}
    fixdirs = {'Trash': d('0700'), 'Trash/files': d('0700'), 'Trash/info': d('0700')}
    empty_info = {'type': 'file', 'mode': '0600', 'mtime': W, 'owner': '0:0', 'text': ''}
    pending = {'type': 'file', 'mode': '0600', 'mtime': W, 'owner': '0:0', 'text': PENDING}

    # trash a.txt, with no trash yet.
    a = {'a.txt': f('a\n')}
    ainfo = 'Trash/info/a.txt.trashinfo'
    full_a = {**trash_dirs(), ainfo: info(H + '/a.txt')}
    whole = {**trash_dirs(), 'Trash/files/a.txt': f('a\n'), ainfo: info(H + '/a.txt')}
    quiet = ran()
    listed_a = ran(stdout='%s %s/a.txt\n' % (W, H), stderr=NO_ITEM % 'a.txt')
    s['cut-put-file'] = cut_cap('cut-put-file', quiet, homes(whole), [
        cut('make ' + T, homes(a), quiet, quiet),
        cut('make %s/files' % T, homes({**a, 'Trash': d('0700', W)}), quiet, quiet),
        cut('make %s/info' % T, homes({**a, 'Trash': d('0700', W), 'Trash/files': d('0700', W)}), quiet, quiet),
        cut('reserve %s/info/a.txt.trashinfo' % T, homes({**a, **trash_dirs()}), quiet, quiet),
        cut('write %s/info/a.txt.trashinfo' % T, homes({**a, **trash_dirs(), ainfo: empty_info}),
            ran(stderr=UNPARSED % 'a.txt'), quiet),
        cut('sync %s/info/a.txt.trashinfo' % T, homes({**a, **full_a}), listed_a, quiet),
        cut('sync %s/info' % T, homes({**a, **full_a}), listed_a, quiet),
        cut('rename %s/a.txt to %s/files/a.txt' % (H, T), homes({**a, **full_a}), listed_a, quiet),
    ])

    # trash d, a tree, into a trash that is there.
    tree = {'d': d(), 'd/f': f('f\n'), 'd/g': d(), 'd/g/h': f('h\n')}
    dinfo = 'Trash/info/d.trashinfo'
    there = {'Trash': d('0700'), 'Trash/files': d('0700'), 'Trash/info': d('0700', W)}
    listed_d = ran(stdout='%s %s/d\n' % (W, H), stderr=NO_ITEM % 'd')
    s['cut-put-dir'] = cut_cap('cut-put-dir', quiet, homes({
        'Trash': d('0700'), 'Trash/files': d('0700', W), 'Trash/info': d('0700', W),
        **{'Trash/files/' + k: v for k, v in tree.items()}, dinfo: info(H + '/d')}), [
        cut('reserve %s/info/d.trashinfo' % T, homes({**fixdirs, **tree}), quiet, quiet),
        cut('write %s/info/d.trashinfo' % T, homes({**there, **tree, dinfo: empty_info}), ran(stderr=UNPARSED % 'd'), quiet),
        cut('sync %s/info/d.trashinfo' % T, homes({**there, **tree, dinfo: info(H + '/d')}), listed_d, quiet),
        cut('sync %s/info' % T, homes({**there, **tree, dinfo: info(H + '/d')}), listed_d, quiet),
        cut('rename %s/d to %s/files/d' % (H, T), homes({**there, **tree, dinfo: info(H + '/d')}), listed_d, quiet),
    ])

    # trash /xdev/…/t, a tree on another file system: copied, verified,
    # finished, synced, its info file written whole, then the source removed.
    src = {'t': d('0750'), 't/f': f('f\n', '0640'), 't/l': link('f')}
    tinfo = 'Trash/info/t.trashinfo'
    tpath = X + '/t'
    listed_t_orphan = ran(stdout='%s %s\n' % (W, tpath), stderr=NO_ITEM % 't')
    listed_t = ran(stdout='%s %s\n' % (W, tpath))
    unparsed_t = ran(stderr=UNPARSED % 't')
    finished = {'Trash/files/t': d('0750'), 'Trash/files/t/f': f('f\n', '0640'), 'Trash/files/t/l': link('f')}
    whole_t = {'Trash': d('0700'), 'Trash/files': d('0700', W), 'Trash/info': d('0700', W), **finished,
               tinfo: info(tpath)}
    filesw = {'Trash': d('0700'), 'Trash/files': d('0700', W), 'Trash/info': d('0700', W)}

    def ht(home, xdev=src):
        return homes(home, xdev)

    def copy_t_1(xdev_left):
        """The rerun after the source was partly removed: what is left
        trashed again, as t_1, beside the whole copy."""
        out = {**whole_t, 'Trash/info/t_1.trashinfo': info(tpath)}
        for rel, e in xdev_left.items():
            out['Trash/files/t_1' + rel[1:]] = e
        return homes(out)
    t_reserved = {**there, tinfo: empty_info}
    t_full = {**there, tinfo: info(tpath)}
    t_pend = {**there, tinfo: pending}
    s['cut-put-other-fs'] = cut_cap('cut-put-other-fs', quiet, homes(whole_t), [
        cut('reserve %s/info/t.trashinfo' % T, ht(fixdirs), quiet, quiet),
        cut('write %s/info/t.trashinfo' % T, ht(t_reserved), unparsed_t, quiet),
        cut('sync %s/info/t.trashinfo' % T, ht(t_full), listed_t_orphan, quiet),
        cut('sync %s/info' % T, ht(t_full), listed_t_orphan, quiet),
        cut('rename %s to %s/files/t' % (tpath, T), ht(t_full), listed_t_orphan, quiet),
        cut('mark %s/info/t.trashinfo copying' % T, ht(t_full), listed_t_orphan, quiet),
        cut('sync %s/info/t.trashinfo' % T, ht(t_pend), unparsed_t, quiet),
        cut('make %s/files/t' % T, ht(t_pend), unparsed_t, quiet),
        cut('write %s/files/t/f' % T, ht({**filesw, tinfo: pending, 'Trash/files/t': d('0700', W)}), unparsed_t, quiet),
        cut('link %s/files/t/l' % T, ht({**filesw, tinfo: pending, 'Trash/files/t': d('0700', W),
                                          'Trash/files/t/f': f('f\n', '0600', W)}), unparsed_t, quiet),
        cut('finish %s/files/t/f' % T, ht({**filesw, tinfo: pending, 'Trash/files/t': d('0700', W),
                                            'Trash/files/t/f': f('f\n', '0600', W), 'Trash/files/t/l': link('f', W)}),
            unparsed_t, quiet),
        cut('finish %s/files/t/l' % T, ht({**filesw, tinfo: pending, 'Trash/files/t': d('0700', W),
                                            'Trash/files/t/f': f('f\n', '0640'), 'Trash/files/t/l': link('f', W)}),
            unparsed_t, quiet),
        cut('finish %s/files/t' % T, ht({**filesw, tinfo: pending, 'Trash/files/t': d('0700', W),
                                          'Trash/files/t/f': f('f\n', '0640'), 'Trash/files/t/l': link('f')}),
            unparsed_t, quiet),
        cut('sync %s/files/t' % T, ht({**filesw, tinfo: pending, **finished}), unparsed_t, quiet),
        cut('write %s/info/t.trashinfo' % T, ht({**filesw, tinfo: pending, **finished}), unparsed_t, quiet),
        cut('sync %s/info/t.trashinfo' % T, ht(whole_t), listed_t, quiet, copy_t_1(src)),
        cut('remove %s/f' % tpath, ht(whole_t), listed_t, quiet, copy_t_1(src)),
        cut('remove %s/l' % tpath, ht(whole_t, {'t': d('0750', W), 't/l': link('f')}), listed_t, quiet,
            copy_t_1({'t': d('0750', W), 't/l': link('f')})),
        cut('remove %s' % tpath, ht(whole_t, {'t': d('0750', W)}), listed_t, quiet, copy_t_1({'t': d('0750', W)})),
    ])

    # trash-restore of a file: linked back, the trashed name removed, then the info file.
    prompt_a = listed(0, W, H + '/a.txt') + PROMPT % 0
    shown = ran(-9, prompt_a)
    in_trash = {**trash_dirs(), 'Trash/files/a.txt': f('a\n'), ainfo: info(H + '/a.txt')}
    back = {**trash_dirs(), 'a.txt': f('a\n')}
    linked = {**in_trash, 'a.txt': f('a\n')}
    left_info = {**trash_dirs(), ainfo: info(H + '/a.txt'), 'a.txt': f('a\n')}
    refused_a = ran(1, prompt_a, 'Refusing to overwrite existing file "a.txt".\n')
    s['cut-restore-file'] = cut_cap('cut-restore-file', ran(0, prompt_a), homes(back), [
        cut('link %s/files/a.txt to %s/a.txt' % (T, H), homes(in_trash), ran(stdout='%s %s/a.txt\n' % (W, H)),
            ran(0, prompt_a), run=shown),
        cut('sync ' + H, homes(linked), ran(stdout='%s %s/a.txt\n' % (W, H)), ran(0, prompt_a), run=shown),
        cut('remove %s/files/a.txt' % T, homes(linked), ran(stdout='%s %s/a.txt\n' % (W, H)), ran(0, prompt_a), run=shown),
        cut('remove %s/info/a.txt.trashinfo' % T, homes(left_info), listed_a, refused_a, homes(left_info), run=shown),
    ])

    # trash-restore of a directory: its placeholder made, renamed onto, then the info file.
    prompt_d = listed(0, W, H + '/d') + PROMPT % 0
    shown_d = ran(-9, prompt_d)
    dtree = {'d': d(), 'd/f': f('f\n')}
    d_in = {**trash_dirs(), 'Trash/files/d': d(), 'Trash/files/d/f': f('f\n'), dinfo: info(H + '/d')}
    placeholder = {**d_in, 'd': d('0700', W)}
    d_back_info = {**trash_dirs(), dinfo: info(H + '/d'), **dtree}
    refused_d = ran(1, prompt_d, 'Refusing to overwrite existing file "d".\n')
    s['cut-restore-dir'] = cut_cap('cut-restore-dir', ran(0, prompt_d), homes({**trash_dirs(), **dtree}), [
        cut('make %s/d' % H, homes(d_in), ran(stdout='%s %s/d\n' % (W, H)), ran(0, prompt_d), run=shown_d),
        cut('rename %s/files/d to %s/d' % (T, H), homes(placeholder), ran(stdout='%s %s/d\n' % (W, H)), refused_d,
            homes(placeholder), run=shown_d),
        cut('sync ' + H, homes(d_back_info), listed_d, refused_d, homes(d_back_info), run=shown_d),
        cut('remove %s/info/d.trashinfo' % T, homes(d_back_info), listed_d, refused_d, homes(d_back_info), run=shown_d),
    ])

    # trash-restore of a file trashed from another file system: copied back,
    # finished, synced, the trashed item removed, then the info file.
    xpath = X + '/x'
    prompt_x = listed(0, W, xpath) + PROMPT % 0
    shown_x = ran(-9, prompt_x)
    x_in = {**trash_dirs(), 'Trash/files/x': f('x\n'), 'Trash/info/x.trashinfo': info(xpath)}
    x_left = {**trash_dirs(), 'Trash/info/x.trashinfo': info(xpath)}
    refused_x = ran(1, prompt_x, 'Refusing to overwrite existing file "x".\n')
    listed_x = ran(stdout='%s %s\n' % (W, xpath))
    s['cut-restore-other-fs'] = cut_cap('cut-restore-other-fs', ran(0, prompt_x), homes(trash_dirs(), {'x': f('x\n')}), [
        cut('write ' + xpath, homes(x_in), listed_x, ran(0, prompt_x), run=shown_x),
        cut('finish ' + xpath, homes(x_in, {'x': f('x\n', '0600', W)}), listed_x, refused_x,
            homes(x_in, {'x': f('x\n', '0600', W)}), run=shown_x),
        cut('sync ' + xpath, homes(x_in, {'x': f('x\n')}), listed_x, refused_x, homes(x_in, {'x': f('x\n')}), run=shown_x),
        cut('remove %s/files/x' % T, homes(x_in, {'x': f('x\n')}), listed_x, refused_x, homes(x_in, {'x': f('x\n')}),
            run=shown_x),
        cut('remove %s/info/x.trashinfo' % T, homes(x_left, {'x': f('x\n')}),
            ran(stdout='%s %s\n' % (W, xpath), stderr=NO_ITEM % 'x'), refused_x, homes(x_left, {'x': f('x\n')}),
            run=shown_x),
    ])

    # trash-rm '*.txt': each match's item, then its info file; keep.log stays.
    items = {'Trash/files/a.txt': f('a\n'), 'Trash/files/d.txt': d(), 'Trash/files/d.txt/f': f('f\n'),
             'Trash/files/keep.log': f('k\n')}
    infos = {'Trash/info/a.txt.trashinfo': info(H + '/a.txt'), 'Trash/info/d.txt.trashinfo': info(H + '/d.txt'),
             'Trash/info/keep.log.trashinfo': info(H + '/keep.log')}
    keep = {**trash_dirs(), 'Trash/files/keep.log': f('k\n'), 'Trash/info/keep.log.trashinfo': info(H + '/keep.log')}
    la, ld, lk = ('%s %s/%s\n' % (W, H, n) for n in ('a.txt', 'd.txt', 'keep.log'))
    rm_tree = {**trash_dirs(), **items, **infos}

    def less(tree, *gone, **changed):
        out = {k: v for k, v in tree.items() if k not in gone}
        for k, v in changed.items():
            out[k.replace('__', '/').replace('_dot_', '.')] = v
        return out
    s1 = less(rm_tree, 'Trash/files/a.txt')
    s2 = less(s1, 'Trash/info/a.txt.trashinfo')
    s3 = {**less(s2, 'Trash/files/d.txt/f'), 'Trash/files/d.txt': d(mtime=W)}
    s4 = less(s3, 'Trash/files/d.txt')
    s['cut-rm'] = cut_cap('cut-rm', quiet, homes(keep), [
        cut('remove %s/files/a.txt' % T, homes(rm_tree), ran(stdout=lines(la, ld, lk)), quiet),
        cut('remove %s/info/a.txt.trashinfo' % T, homes(s1), ran(stdout=lines(la, ld, lk), stderr=NO_ITEM % 'a.txt'), quiet),
        cut('remove %s/files/d.txt/f' % T, homes(s2), ran(stdout=lines(ld, lk)), quiet),
        cut('remove %s/files/d.txt' % T, homes(s3), ran(stdout=lines(ld, lk)), quiet),
        cut('remove %s/info/d.txt.trashinfo' % T, homes(s4), ran(stdout=lines(ld, lk), stderr=NO_ITEM % 'd.txt'), quiet),
    ])

    # trash-empty over a file, a tree and an item with no info file: each item,
    # then the orphan, then each info file.
    e0 = {**trash_dirs(), 'Trash/files/a.txt': f('a\n'), 'Trash/files/d': d(), 'Trash/files/d/f': f('f\n'),
          'Trash/files/stray': f('s\n'), ainfo: info(H + '/a.txt'), dinfo: info(H + '/d')}
    la, ldd = '%s %s/a.txt\n' % (W, H), '%s %s/d\n' % (W, H)
    e1 = less(e0, 'Trash/files/a.txt')
    e2 = {**less(e1, 'Trash/files/d/f'), 'Trash/files/d': d(mtime=W)}
    e3 = less(e2, 'Trash/files/d')
    e4 = less(e3, 'Trash/files/stray')
    e5 = less(e4, ainfo)
    s['cut-empty'] = cut_cap('cut-empty', quiet, homes(trash_dirs()), [
        cut('remove %s/files/a.txt' % T, homes(e0), ran(stdout=lines(la, ldd), stderr=NO_INFO % 'stray'), quiet),
        cut('remove %s/files/d/f' % T, homes(e1), ran(stdout=lines(la, ldd), stderr=lines(NO_INFO % 'stray', NO_ITEM % 'a.txt')),
            quiet),
        cut('remove %s/files/d' % T, homes(e2), ran(stdout=lines(la, ldd), stderr=lines(NO_INFO % 'stray', NO_ITEM % 'a.txt')),
            quiet),
        cut('remove %s/files/stray' % T, homes(e3),
            ran(stdout=lines(la, ldd), stderr=lines(NO_INFO % 'stray', NO_ITEM % 'a.txt', NO_ITEM % 'd')), quiet),
        cut('remove %s/info/a.txt.trashinfo' % T, homes(e4),
            ran(stdout=lines(la, ldd), stderr=lines(NO_ITEM % 'a.txt', NO_ITEM % 'd')), quiet),
        cut('remove %s/info/d.trashinfo' % T, homes(e5), ran(stdout=ldd, stderr=NO_ITEM % 'd'), quiet),
    ])
    return s


def hardening():
    """T3's oracle rows that depart from the oracle: the listing that names
    both orphans (from the oracle's own goldens, its standard error added),
    a file the copy cannot read, and the space rows."""
    s = {}
    for row, extra in (('list-orphans', [NO_ITEM % 'gone', NO_INFO % 'noinfo']),
                       ('list-made', [NO_ITEM % 'orphan', NO_INFO % 'noinfo'])):
        c = json.loads((ROOT / 'tests/oracle/golden' / (row + '.json')).read_text())
        c['steps'][0]['stderr'] = ''.join(sorted(c['steps'][0]['stderr'].splitlines(True) + extra))
        s[row] = c
    u = '1000:1000'
    s['perm-unreadable-other-fs'] = cap('perm-unreadable-other-fs', [
        step(['trash', X + '/secret'], 74, stderr="trash: cannot trash '%s/secret': cannot open '%s/secret': Permission denied; "
             "%s\n" % (X, X, LEFT)),
    ], trash_dirs(owner=u), {'secret': f('s\n', '0000', owner=u)})
    small = 'the home volume has too little free space to copy it'
    s['space-full-trash'] = cap('space-full-trash', [
        step(['trash', 'fill']),
        step(['trash', X + '/big'], 74, stderr="trash: cannot trash '%s/big': %s\n" % (X, small)),
        step(['trash-list'], stdout='%s %s/fill\n' % (W, SMALL_H)),
        step(['trash-empty']),
        step(['trash', X + '/big']),
        step(['trash-list'], stdout='%s %s/big\n' % (W, X)),
    ], {**trash_dirs(), 'Trash/files/big': f(big(1048576)), 'Trash/info/big.trashinfo': info(X + '/big')})
    s['space-tree'] = cap('space-tree', [
        step(['trash', X + '/t'], 74, stderr="trash: cannot trash '%s/t': %s\n" % (X, small)),
    ], trash_dirs(), {'t': d(), **{'t/' + n: f(big(409600)) for n in 'abcdef'}})
    return s


def cut_rows():
    return {r['name'] for r in json.loads((ROOT / 'tests/cuts/rows.json').read_text())['rows']}


def rendered(c):
    return json.dumps(c, indent=1, sort_keys=True, ensure_ascii=False) + '\n'


def diverging():
    rows = json.loads((ROOT / 'tests/oracle/rows.json').read_text())['rows']
    return {r['name'] for r in rows if r.get('diverge')}


def pax_rows():
    return {r['name'] for r in json.loads((ROOT / 'tests/pax/rows.json').read_text())['rows']}


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else 'check'
    bad = 0
    total = 0
    for s, want, out in ((statements(), diverging(), OUT), (pax_statements(), pax_rows(), OUT_PAX),
                         (cut_statements(), cut_rows(), OUT_CUTS)):
        rel = out.relative_to(ROOT)
        total += len(s)
        for name in sorted(want - set(s)):
            print('FAIL expected-%s a row with no statement' % name)
            bad += 1
        for name in sorted(set(s) - want):
            print('FAIL expected-%s a statement with no row' % name)
            bad += 1
        if mode == 'write':
            out.mkdir(parents=True, exist_ok=True)
            for name, c in sorted(s.items()):
                (out / (name + '.json')).write_text(rendered(c))
                print('WROTE %s/%s.json' % (rel, name))
            continue
        for name, c in sorted(s.items()):
            path = out / (name + '.json')
            if not path.exists() or path.read_text() != rendered(c):
                print('FAIL expected-%s %s/%s.json differs from its statement' % (name, rel, name))
                bad += 1
            else:
                print('PASS expected-%s' % name)
        for p in sorted(out.glob('*.json')):
            if p.stem not in s:
                print('FAIL expected-%s a file with no statement' % p.stem)
                bad += 1
    if mode != 'write':
        print('SUMMARY expected rows=%d failed=%d' % (total, bad))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
