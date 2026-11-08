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
    for s, want, out in ((statements(), diverging(), OUT), (pax_statements(), pax_rows(), OUT_PAX)):
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
