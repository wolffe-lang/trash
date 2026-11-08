#!/usr/bin/env python3
"""The oracle harness: one row run on trash-cli and on this repository's tools,
in matching scratch homes, compared field by field.

  oracle.py record   --rows FILE --golden DIR [--only RE]
  oracle.py check    --rows FILE --golden DIR [--only RE]
  oracle.py compare  --rows FILE --candidate DIR [--only RE] [--commands A,B]
  oracle.py capture  --rows FILE --candidate DIR --out DIR [--only RE]
  oracle.py selftest [--live --rows FILE [--only RE]]

A row is a list of steps: `make` steps build a fixture (files, directories and
symbolic links, every one stamped with the same times) and `run` steps run one
command of the trash family with arguments, a working directory and a
standard input. Each tool runs the whole row in a fresh scratch home at one
fixed path, so `Path=` lines, messages and listings name the same paths with
no rewriting; the home is removed before the other tool's run. A second file
system (a tmpfs at /xdev) holds the items a row trashes from elsewhere.

What is compared, per row: every command's exit status, standard output and
standard error; and the trees the row leaves, in the home and on /xdev —
every entry's type, mode, size, bytes (sha256), symbolic link target and
modification time, and the full text of every `.trashinfo` and of
`directorysizes`. Normalised, and only by name:

  - `DeletionDate=` in an info file: its shape must be YYYY-MM-DDThh:mm:ss
    and, read as local time in the row's zone, its instant must lie inside the
    run's window; it then reads `DeletionDate=<in-window>`. A value of the
    wrong shape or outside the window is kept, marked, and differs.
  - A date and time (`YYYY-MM-DD hh:mm:ss`, or with `T`) in a command's
    output, or a number of seconds in `directorysizes`, inside the window:
    `<in-window>`. Fixed dates a fixture wrote are outside it and stay.
  - A modification time inside the window: `<in-window>`.
  - A step marked `"order": "host"`: its standard output's lines sorted, for
    a listing in the order the host's directory hands entries over; and one
    marked `"errors": "host"`, its standard error's lines, for messages about
    entries met in that order.
  - A row marked `"words": "own"` (`--help`, `--version`): each stream reads
    `<text>` when it holds anything, so the row holds the exit status and
    which stream carries the text, and this repository's text is its own.

A `run` step marked `"tty": true` has a terminal for its standard input (a
pty, given the step's input and then the end of input), its output streams
still pipes. A `dated` make step writes an info file whose deletion date is
some seconds from the moment it is made, and the normaliser reads a date that
far from the window as `<in-window+N>` by name. A `tree` make step makes a
tree generated from a seed (`tree_plan`), with its own modes, owners and
times. A row marked `"property": "round-trip"` is snapshotted, exactly and
without moving a time, before its first command, and every entry outside the
trashes must be as it was after its last: a failure is a difference named
`property`, held on every run of the row, the oracle's included.

A row may name `"user": [UID, GID]`: its home and the second file system's
scratch directory are that user's, every entry a fixture makes is given to
it unless the fixture chowns it to another, and every command runs as it
(`setpriv`, every supplementary group dropped), so the host's permission
checks apply as they do to anyone but root.

A row may also name `"home": "small"`: its scratch home is on a small tmpfs
(/small, mounted by tools/in-container), so a copy into the home trash can
be refused for space. A row marked `"times": "exact"` records every entry's
access time too, and both times' nanoseconds; times inside the window are
still `<in-window>`, with their nanoseconds dropped.

A row marked `"diverge"` is one where this repository departs from the oracle
by design (the reason is the mark's text); `compare` holds the candidate to
tests/oracle/expected/ROW.json there instead of to the oracle.

Nothing else is rewritten. A Python traceback in the oracle's output is never
printed or kept (the clean room: it would quote the oracle's source); it is
replaced by a count of its lines and fails the row by name, unless the row
says `"oracle": "crashes"`: a row where the oracle has no answer (it is
marked `diverge` too), whose golden holds the redacted crash so that the
pinned oracle is still seen to crash the same way.

`record` writes each row's normalised oracle capture to the golden directory;
`check` runs the oracle again and holds it to them (the pinned oracle must
reproduce its own goldens); `compare` holds the candidate to a fresh oracle
run, over the rows whose every command the candidate directory holds (or
those `--commands` names); `capture` writes the candidate's own normalised
captures, for review; `selftest` checks the normaliser and the comparer on synthetic captures
(every field a difference can hide in is mutated and must be seen), and with
--live runs every row on the oracle twice and requires them to agree.
"""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import socket
import stat
import subprocess
import sys
import time
import tomllib
import zoneinfo

ROOT = Path(__file__).resolve().parents[1]
SCRATCH = Path('/tmp/trash-rows')
HOME = SCRATCH / 'home'
XDEV = Path('/xdev/trash-rows')
SMALL = Path('/small')
# The scratch home a row runs in: the image's root file system by default, or
# the small tmpfs (`"home": "small"`). Set by run_row for the row it runs.
HOMES = {'root': HOME, 'small': SMALL / 'trash-rows/home'}
CURRENT = {'home': HOME}


def home():
    return CURRENT['home']
FIXTURE_TIME = 1700000000
COMMANDS = ('trash', 'trash-put', 'trash-list', 'trash-restore', 'trash-rm', 'trash-empty')
TRACEBACK = 'Traceback (most recent call last):'
DATE_RE = re.compile(r'\b(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2}:\d{2})\b')
SHAPE_RE = re.compile(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}')


# ---------------------------------------------------------------- paths


def unescape(s):
    """A row's path or argument: UTF-8 text in which \\xHH is one byte."""
    return re.sub(rb'\\x([0-9a-fA-F]{2})', lambda m: bytes([int(m.group(1), 16)]), s.encode('utf-8'))


def show(b):
    """Bytes as text: UTF-8 where it decodes, \\xHH for every byte that does not."""
    return b.decode('utf-8', 'backslashreplace')


def where(path_bytes):
    """A fixture path: relative to the home, or on the second file system with @xdev/."""
    if path_bytes.startswith(b'@xdev/'):
        return os.path.join(bytes(XDEV), path_bytes[len(b'@xdev/'):])
    return os.path.join(bytes(home()), path_bytes)


# ---------------------------------------------------------------- running


def tree_plan(root, seed):
    """A tree generated from a seed, as a plan: one dict per entry, parents
    before children, each with its path (under the fixture's base), kind,
    mode, owner, times (mtime s, ns, atime s, ns) and, for a file its bytes,
    for a link its target. Pure: tools/expected.py builds expected captures
    from the same plan. The top is always a directory."""
    import random
    rng = random.Random(seed)
    plan = []
    words = ['f', 'g h', 'é', 'x.txt', '.h', 'ü ber', 'n']
    counts = {'fifo': 0}

    def times():
        return [rng.randrange(1500000000, 1690000000), rng.randrange(10**9),
                rng.randrange(1500000000, 1690000000), rng.randrange(10**9)]

    def owner():
        return rng.choice(['0:0', '0:0', '0:0', '1000:1000', '0:100'])

    def gen(path, depth):
        plan.append({'path': path, 'kind': 'dir', 'mode': rng.choice([0o755, 0o700, 0o750]), 'owner': owner(),
                     'times': times()})
        n = rng.randrange(2, 6) if depth < 2 else rng.randrange(0, 3)
        for i in range(n):
            child = '%s/%s%d' % (path, rng.choice(words), i)
            pick = rng.random()
            if pick < 0.45:
                size = rng.choice([0, 1, 100, 5000, 70000])
                data = bytes(rng.randrange(256) for _ in range(size))
                plan.append({'path': child, 'kind': 'file', 'mode': rng.choice([0o644, 0o600, 0o755, 0o640, 0o444]),
                             'owner': owner(), 'times': times(), 'data': data})
            elif pick < 0.65:
                target = rng.choice(['../x', '/nowhere/at/all', 'f0', 'é dangling', '.'])
                plan.append({'path': child, 'kind': 'link', 'mode': 0o777, 'owner': owner(), 'times': times(),
                             'target': target})
            elif pick < 0.72 and counts['fifo'] == 0:
                counts['fifo'] += 1
                plan.append({'path': child, 'kind': 'fifo', 'mode': 0o640, 'owner': owner(), 'times': times()})
            elif depth < 3:
                gen(child, depth + 1)
            else:
                plan.append({'path': child, 'kind': 'dir', 'mode': 0o755, 'owner': owner(), 'times': times()})
    gen(root, 0)
    return plan


def make_plan(plan):
    """Make a generated tree's entries, then their owners, then their times,
    each entry before the directory that holds it."""
    for e in plan:
        p = where(unescape(e['path']))
        if e['kind'] == 'dir':
            os.makedirs(p)
            os.chmod(p, e['mode'])
        elif e['kind'] == 'file':
            with open(p, 'wb') as f:
                f.write(e['data'])
            os.chmod(p, e['mode'])
        elif e['kind'] == 'link':
            os.symlink(unescape(e['target']), p)
        elif e['kind'] == 'fifo':
            os.mkfifo(p, e['mode'])
            os.chmod(p, e['mode'])
    for e in plan:
        uid, gid = (int(x) for x in e['owner'].split(':'))
        os.lchown(where(unescape(e['path'])), uid, gid)
    for e in reversed(plan):
        ms, mns, as_, ans = e['times']
        os.utime(where(unescape(e['path'])), ns=(as_ * 10**9 + ans, ms * 10**9 + mns), follow_symlinks=False)


# The offsets (in seconds from the moment a fixture is made) of the deletion
# dates a row's `dated` info files carry: the normaliser reads a date that
# far from the run's window as `<in-window+N>`, by name. Set by run_row.
OFFSETS = []


def local_text(t, tz):
    return datetime.datetime.fromtimestamp(t, zoneinfo.ZoneInfo(tz)).strftime('%Y-%m-%dT%H:%M:%S')


def make(ops, tz='UTC'):
    made, later = [], []
    for op in ops:
        kind = op[0]
        if kind == 'tree':
            # ["tree", path, seed]: a generated tree (tree_plan), with its own
            # modes, owners and times, kept as they are.
            later.append(('plan', tree_plan(op[1], int(op[2]))))
            continue
        if kind == 'dated':
            # ["dated", name, path, offset]: Trash/info/NAME.trashinfo, its
            # Path= the given text and its DeletionDate= local time `offset`
            # seconds from now; Trash/files/NAME a small file, unless the
            # path is "-" (an info file with no item).
            name, path, off = op[1], op[2], int(op[3])
            OFFSETS.append(off)
            info = where(b'Trash/info/' + unescape(name) + b'.trashinfo')
            os.makedirs(os.path.dirname(info), exist_ok=True)
            with open(info, 'wb') as f:
                f.write(b'[Trash Info]\nPath=' + unescape(path) + b'\nDeletionDate=' +
                        local_text(int(time.time()) + off, tz).encode() + b'\n')
            os.chmod(info, 0o600)
            made.append(info)
            if len(op) < 5 or op[4] != '-':
                item = where(b'Trash/files/' + unescape(name))
                os.makedirs(os.path.dirname(item), exist_ok=True)
                with open(item, 'wb') as f:
                    f.write(b'd\n')
                os.chmod(item, 0o644)
                made.append(item)
            continue
        if kind == 'big':
            # ["big", path, bytes]: a file of that many bytes, 0..250 repeated.
            p = where(unescape(op[1]))
            os.makedirs(os.path.dirname(p), exist_ok=True)
            block = bytes(i % 251 for i in range(65536))
            with open(p, 'wb') as f:
                left = int(op[2])
                while left > 0:
                    f.write(block[:left])
                    left -= len(block[:left])
            os.chmod(p, 0o644)
            made.append(p)
        elif kind == 'fifo':
            p = where(unescape(op[1]))
            os.makedirs(os.path.dirname(p), exist_ok=True)
            os.mkfifo(p, int(op[2], 8) if len(op) > 2 else 0o644)
            os.chmod(p, int(op[2], 8) if len(op) > 2 else 0o644)
            made.append(p)
        elif kind == 'socket':
            p = where(unescape(op[1]))
            os.makedirs(os.path.dirname(p), exist_ok=True)
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.bind(p)
            s.close()
            made.append(p)
        elif kind == 'chown':
            # ["chown", path, uid, gid]: the entry itself, never a link's target.
            later.append(('chown', where(unescape(op[1])), int(op[2]), int(op[3])))
        elif kind == 'times':
            # ["times", path, mtime_s, mtime_ns, atime_s, atime_ns]: after the
            # fixture's own stamping, so these times are the ones that stay.
            later.append(('times', where(unescape(op[1])), int(op[2]), int(op[3]), int(op[4]), int(op[5])))
        elif kind == 'file':
            p = where(unescape(op[1]))
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, 'wb') as f:
                f.write(unescape(op[2]))
            os.chmod(p, int(op[3], 8) if len(op) > 3 else 0o644)
            made.append(p)
        elif kind == 'dir':
            p = where(unescape(op[1]))
            os.makedirs(p, exist_ok=True)
            os.chmod(p, int(op[2], 8) if len(op) > 2 else 0o755)
            made.append(p)
        elif kind == 'link':
            p = where(unescape(op[2]))
            os.makedirs(os.path.dirname(p), exist_ok=True)
            os.symlink(unescape(op[1]), p)
            made.append(p)
        elif kind == 'remove':
            p = where(unescape(op[1]))
            if os.path.isdir(p) and not os.path.islink(p):
                shutil.rmtree(p)
            elif os.path.lexists(p):
                os.remove(p)
        else:
            raise ValueError('unknown make op: %r' % (op,))
    # Every entry the step made gets the fixture's times, deepest first, so a
    # directory's own time is set after its entries were made.
    for p in sorted(made, key=lambda q: -q.count(b'/')):
        os.utime(p, (FIXTURE_TIME, FIXTURE_TIME), follow_symlinks=False)
    for op in later:
        if op[0] == 'plan':
            make_plan(op[1])
        elif op[0] == 'chown':
            os.lchown(op[1], op[2], op[3])
        else:
            _, p, ms, mns, as_, ans = op
            os.utime(p, ns=(as_ * 10**9 + ans, ms * 10**9 + mns), follow_symlinks=False)


def oracle_guard(row, tool, argv):
    """Refuse to hand the oracle a path that begins with exactly two slashes.
    Python keeps such a path as it is, the oracle's check against moving '/'
    into itself misses it, and its fallback copies the whole root file system
    into the trash (measured once, in a scratch container, and stopped)."""
    if tool != oracle_bin():
        return
    for word in argv[1:]:
        if word.startswith(b'//') and not word.startswith(b'///'):
            raise SystemExit('FAIL oracle-guard %s: %r begins with two slashes; the oracle would copy the root file '
                             'system for it' % (row['name'], show(word)))


def tool_path(tool, command):
    if command not in COMMANDS:
        raise ValueError('not a command of the trash family: ' + command)
    return os.path.join(tool, command)


def env_for(row):
    return {'HOME': str(home()), 'XDG_DATA_HOME': str(home()), 'TZ': row.get('tz', 'UTC'),
            'LC_ALL': 'C.UTF-8', 'PATH': '/usr/bin:/bin'}


SETPRIV = '/usr/bin/setpriv'


def as_user(row, argv):
    """A command line run as the row's user, when it names one."""
    if not row.get('user'):
        return argv
    uid, gid = row['user']
    return [SETPRIV.encode(), b'--reuid=%d' % uid, b'--regid=%d' % gid, b'--clear-groups', b'--'] + argv


def own_fixture(row):
    """A user row's fixture is the user's: every entry under the home and the
    second file system's scratch directory still owned by root is given to
    the row's user (an entry the fixture chowned elsewhere keeps its owner)."""
    if not row.get('user'):
        return
    uid, gid = row['user']
    for top in (bytes(home()), bytes(XDEV)):
        os.lchown(top, uid, gid)
        for dirpath, dirnames, filenames in os.walk(top):
            for name in dirnames + filenames:
                p = os.path.join(dirpath, name)
                if os.lstat(p).st_uid == 0:
                    os.lchown(p, uid, gid)


# The tops of the two file systems a row touches, where a tool may make a
# per-volume trash (`$topdir/.Trash-$uid`): the image's root, which holds the
# scratch home, and the second file system.
TOPS = (('root-top', Path('/')), ('tmp-top', Path('/tmp')), ('xdev-top', Path('/xdev')), ('small-top', SMALL))
# The largest file system a row may write to (tools/in-container mounts /tmp,
# /xdev and /small at 32 MiB or less): a command that copies without end
# fails on a full tmpfs instead of filling the host.
CAP = 64 * 1024 * 1024


def clean():
    # Only ever inside the oracle image: this removes what a tool left at the
    # tops of its file systems.
    assert Path('/opt/oracle-manifest.txt').exists(), 'clean() outside the oracle image'
    for d in (SCRATCH, XDEV, SMALL / 'trash-rows'):
        if d.exists():
            shutil.rmtree(d)
    for _, top in TOPS:
        if not top.is_dir():
            continue
        for p in top.glob('.Trash*'):
            shutil.rmtree(p) if p.is_dir() and not p.is_symlink() else p.unlink()


def run_row(row, tool):
    """The row on one tool: its steps' results and the trees it leaves, raw."""
    clean()
    where_home = row.get('home', 'root')
    CURRENT['home'] = HOMES[where_home]
    if where_home == 'small' and (not SMALL.is_dir() or os.stat(SMALL).st_dev == os.stat('/').st_dev):
        raise SystemExit('FAIL oracle-small: /small is not a file system of its own (tools/in-container mounts it)')
    home().mkdir(parents=True)
    XDEV.mkdir(parents=True)
    steps = []
    OFFSETS.clear()
    before = None
    start = time.time()
    own_fixture(row)
    for step in row['steps']:
        if 'make' in step:
            make(step['make'], row.get('tz', 'UTC'))
            own_fixture(row)
            continue
        if row.get('property') == 'round-trip' and before is None:
            before = {'home': kept_snapshot(bytes(home())), 'xdev': kept_snapshot(bytes(XDEV))}
        argv = [unescape(a) for a in step['run']]
        oracle_guard(row, tool, argv)
        argv[0] = tool_path(tool, argv[0].decode()).encode()
        cwd = where(unescape(step.get('cwd', '')))
        r = run_step(as_user(row, argv), cwd, env_for(row), unescape(step.get('stdin', '')), step.get('tty', False))
        steps.append({'argv': [show(a) for a in [unescape(step['run'][0])] + argv[1:]], 'order': step.get('order', 'kept'),
                      'errors': step.get('errors', 'kept'), 'exit': r.returncode, 'stdout': show(r.stdout),
                      'stderr': show(r.stderr)})
    end = time.time()
    exact = row.get('times') == 'exact'
    trees = {'home': snapshot(bytes(home()), exact), 'xdev': snapshot(bytes(XDEV), exact)}
    prop = None
    if row.get('property') == 'round-trip':
        prop = round_trip(before, trees) if before is not None else ['no command ran']
    for label, top in TOPS:
        if not top.is_dir():
            continue
        for p in sorted(top.glob('.Trash*')):
            trees[label + '/' + p.name] = snapshot(bytes(p), exact)
    clean()
    cap = {'row': row['name'], 'tz': row.get('tz', 'UTC'), 'window': [start, end], 'steps': steps, 'trees': trees,
           'offsets': sorted(set(OFFSETS))}
    if row.get('words') == 'own':
        cap['own_words'] = True
    if prop is not None:
        cap['property'] = prop
    return cap


def run_step(argv, cwd, env, data, tty):
    """One command. With tty, its standard input is a terminal (a pty's other
    end), given the bytes as typed and then the end of input (^D twice, so
    a partial last line is ended too); its output streams stay pipes."""
    if not tty:
        return subprocess.run(argv, cwd=cwd, env=env, input=data, capture_output=True, timeout=120)
    import pty
    master, slave = pty.openpty()
    try:
        os.write(master, data + b'\x04\x04')
        p = subprocess.Popen(argv, cwd=cwd, env=env, stdin=slave, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        os.close(slave)
        slave = -1
        out, err = p.communicate(timeout=120)
        return subprocess.CompletedProcess(argv, p.returncode, out, err)
    finally:
        if slave >= 0:
            os.close(slave)
        os.close(master)


def kept_snapshot(top):
    """An exact snapshot that leaves every time as it found it: reading a
    file's bytes and listing a directory move their access times, so each
    entry's times are put back once the walk is done (links' are not held).
    The walk reads each entry's record before it reads or lists the entry."""
    raw = {}
    snap = snapshot(top, True, raw)
    for rel in sorted(snap, key=lambda r: -r.count('/')):
        e = snap[rel]
        if e['type'] != 'link':
            os.utime(raw[rel], ns=(e['atime'] * 10**9 + e['atime_ns'], e['mtime'] * 10**9 + e['mtime_ns']),
                     follow_symlinks=False)
    return snap


def round_trip(before, after):
    """The round-trip property: every entry outside the trashes is as it was
    before the first command, field by field (kind, mode, owner, bytes, link
    target, both times to the nanosecond). Its failures, by entry."""
    out = []
    for tname in ('home', 'xdev'):
        a = {k: v for k, v in before[tname].items() if not k.split('/')[0].startswith(('Trash', '.Trash'))}
        b = {k: v for k, v in after[tname].items() if not k.split('/')[0].startswith(('Trash', '.Trash'))}
        for rel in sorted(set(a) | set(b)):
            if rel not in b:
                out.append('%s:%s missing' % (tname, rel))
            elif rel not in a:
                out.append('%s:%s unexpected' % (tname, rel))
            elif a[rel] != b[rel]:
                keys = sorted(k for k in set(a[rel]) | set(b[rel]) if a[rel].get(k) != b[rel].get(k))
                out.append('%s:%s %s' % (tname, rel, ' '.join('%s want %r got %r' % (k, a[rel].get(k), b[rel].get(k))
                                                               for k in keys)))
    return out


def snapshot(top, exact=False, raw=None):
    """Every entry under top: what the comparison reads, raw. With exact, the
    access time and both times' nanoseconds too. `raw`, when given, maps
    each entry's name as shown to its path's bytes."""
    out = {}
    if not os.path.lexists(top):
        return out
    for dirpath, dirnames, filenames in os.walk(top):
        dirnames.sort()
        for name in sorted(dirnames) + sorted(filenames):
            p = os.path.join(dirpath, name)
            rel = show(os.path.relpath(p, top))
            if raw is not None:
                raw[rel] = p
            st = os.lstat(p)
            e = {'mode': '%04o' % stat.S_IMODE(st.st_mode), 'mtime': int(st.st_mtime), 'owner': '%d:%d' % (st.st_uid, st.st_gid)}
            if exact:
                e.update(mtime_ns=st.st_mtime_ns % 10**9)
                if not stat.S_ISLNK(st.st_mode):
                    # A link's access time moves whenever a path is resolved
                    # through it, this walk's own included: it is not kept.
                    e.update(atime=st.st_atime_ns // 10**9, atime_ns=st.st_atime_ns % 10**9)
            if stat.S_ISLNK(st.st_mode):
                e.update(type='link', target=show(os.readlink(p)))
            elif stat.S_ISDIR(st.st_mode):
                e.update(type='dir')
            elif stat.S_ISFIFO(st.st_mode):
                e.update(type='fifo')
            elif stat.S_ISSOCK(st.st_mode):
                e.update(type='socket')
            elif stat.S_ISREG(st.st_mode):
                data = open(p, 'rb').read()
                e.update(type='file', size=len(data), sha256=hashlib.sha256(data).hexdigest())
                if name.endswith(b'.trashinfo') or name == b'directorysizes':
                    e['text'] = show(data)
            else:
                e.update(type='other')
            out[rel] = e
        # os.walk follows no links into directories by default; a link to a
        # directory is listed in dirnames and must not be descended.
        dirnames[:] = [d for d in dirnames if not os.path.islink(os.path.join(dirpath, d))]
    return out


# ---------------------------------------------------------------- normalising


def in_window(t, window):
    return window[0] - 2 <= t <= window[1] + 2


def named(t, window, offsets):
    """A time's name: `<in-window>` inside the run's window, `<in-window+N>`
    N seconds from it for an offset the row's dated fixtures declared, else
    None (the time is kept as it is)."""
    if in_window(t, window):
        return '<in-window>'
    for off in offsets:
        if in_window(t - off, window):
            return '<in-window%+d>' % off
    return None


def local_instant(date, clock, tz):
    try:
        d = datetime.datetime.strptime(date + 'T' + clock, '%Y-%m-%dT%H:%M:%S')
    except ValueError:
        return None
    return d.replace(tzinfo=zoneinfo.ZoneInfo(tz)).timestamp()


def norm_deletion_date(value, window, tz, offsets=()):
    if not SHAPE_RE.fullmatch(value):
        return '<bad-shape:%s>' % value
    t = local_instant(value[:10], value[11:], tz)
    if t is None:
        return '<bad-shape:%s>' % value
    return named(t, window, offsets) or '<outside-window:%s>' % value


def norm_info(text, window, tz, offsets=()):
    out = []
    for line in text.split('\n'):
        if line.startswith('DeletionDate='):
            line = 'DeletionDate=' + norm_deletion_date(line[len('DeletionDate='):], window, tz, offsets)
        out.append(line)
    return '\n'.join(out)


def norm_sizes(text, window):
    return re.sub(r'\b\d{9,}\b', lambda m: '<in-window>' if in_window(int(m.group(0)), window) else m.group(0), text)


def norm_output(text, window, tz, offsets=()):
    def date(m):
        t = local_instant(m.group(1), m.group(2), tz)
        return (named(t, window, offsets) if t is not None else None) or m.group(0)
    return DATE_RE.sub(date, text)


def host_order(text):
    """A listing in the order the host's directory hands entries over, which no
    two file systems share: its lines sorted, for a step that says so by name."""
    lines = text.split('\n')
    tail = lines.pop() if lines and lines[-1] == '' else None
    return '\n'.join(sorted(lines) + ([tail] if tail is not None else []))


def redact(text):
    """(text, lines redacted): a traceback and everything after it in the stream."""
    i = text.find(TRACEBACK)
    if i < 0:
        return text, 0
    n = text[i:].count('\n') + 1
    return text[:i] + '<traceback redacted: %d lines>\n' % n, n


def normalise(cap):
    """The capture as compared: raw times and dates replaced by name, tracebacks gone."""
    w, tz, offs = cap['window'], cap['tz'], cap.get('offsets', [])
    steps, tracebacks = [], 0
    for s in cap['steps']:
        out, n1 = redact(s['stdout'])
        err, n2 = redact(s['stderr'])
        tracebacks += bool(n1) + bool(n2)
        out = norm_output(out, w, tz, offs)
        if s.get('order') == 'host':
            out = host_order(out)
        err = norm_output(err, w, tz, offs)
        if s.get('errors') == 'host':
            err = host_order(err)
        if cap.get('own_words'):
            # this repository's --help and --version are in its own words
            out, err = ('<text>' if out else ''), ('<text>' if err else '')
        steps.append({'argv': s['argv'], 'exit': s['exit'], 'stdout': out, 'stderr': err})
    trees = {}
    for tname, tree in cap['trees'].items():
        t = {}
        for rel, e in tree.items():
            e = dict(e)
            if in_window(e['mtime'], w):
                e['mtime'] = '<in-window>'
                e.pop('mtime_ns', None)
            if 'atime' in e and in_window(e['atime'], w):
                e['atime'] = '<in-window>'
                e.pop('atime_ns', None)
            if 'text' in e:
                e['text'] = norm_sizes(e['text'], w) if rel.endswith('directorysizes') else norm_info(e['text'], w, tz, offs)
                if rel.endswith('directorysizes'):
                    # its bytes carry the window's numbers: the text is held instead
                    e.pop('sha256', None)
                    e.pop('size', None)
            if rel.endswith('.trashinfo'):
                # the text is held line by line; its bytes and length carry the date
                e.pop('sha256', None)
                e.pop('size', None)
            t[rel] = e
        trees[tname] = t
    out = {'row': cap['row'], 'tz': tz, 'steps': steps, 'trees': trees, 'tracebacks': tracebacks}
    if 'property' in cap:
        # the round-trip property's failures, by entry (none when it held)
        out['property'] = list(cap['property'])
    return out


# ---------------------------------------------------------------- comparing


def first_diff(a, b):
    al, bl = a.split('\n'), b.split('\n')
    for i in range(max(len(al), len(bl))):
        x = al[i] if i < len(al) else '<none>'
        y = bl[i] if i < len(bl) else '<none>'
        if x != y:
            return 'line %d: want %r got %r' % (i + 1, x, y)
    return 'equal'


def compare(want, got):
    """Every difference between two normalised captures: (field, detail)."""
    diffs = []
    if len(want['steps']) != len(got['steps']):
        diffs.append(('steps', 'want %d commands got %d' % (len(want['steps']), len(got['steps']))))
    for i, (a, b) in enumerate(zip(want['steps'], got['steps']), 1):
        if a['exit'] != b['exit']:
            diffs.append(('step%d-exit' % i, 'want %s got %s' % (a['exit'], b['exit'])))
        for k in ('stdout', 'stderr'):
            if a[k] != b[k]:
                diffs.append(('step%d-%s' % (i, k), first_diff(a[k], b[k])))
    for tname in sorted(set(want['trees']) | set(got['trees'])):
        ta, tb = want['trees'].get(tname, {}), got['trees'].get(tname, {})
        for rel in sorted(set(ta) | set(tb)):
            if rel not in tb:
                diffs.append(('%s:%s' % (tname, rel), 'missing'))
                continue
            if rel not in ta:
                diffs.append(('%s:%s' % (tname, rel), 'unexpected %s' % tb[rel]['type']))
                continue
            for k in sorted(set(ta[rel]) | set(tb[rel])):
                x, y = ta[rel].get(k), tb[rel].get(k)
                if x != y:
                    detail = first_diff(x, y) if k == 'text' and x and y else 'want %r got %r' % (x, y)
                    diffs.append(('%s:%s:%s' % (tname, rel, k), detail))
    if got.get('tracebacks'):
        diffs.append(('traceback', '%d stream(s) redacted' % got['tracebacks']))
    if 'property' in want or 'property' in got:
        # the round trip's failures, held as a list: a run fails where the
        # capture it is held to held, and is seen to hold where it failed
        if 'property' not in got:
            diffs.append(('property', 'not checked'))
        else:
            a, b = want.get('property', []), got['property']
            diffs.extend(('property', failure) for failure in b if failure not in a)
            diffs.extend(('property', 'held where it failed: ' + failure) for failure in a if failure not in b)
    return diffs


# ---------------------------------------------------------------- the commands


def load_rows(path, only):
    rows = json.loads(Path(path).read_text())['rows']
    names = [r['name'] for r in rows]
    if len(names) != len(set(names)):
        raise ValueError('duplicate row names')
    return [r for r in rows if not only or re.search(only, r['name'])]


def oracle_bin():
    return tomllib.loads((ROOT / 'trash-oracle.toml').read_text())['trash-cli']['bin']


def live_guard():
    if not Path('/opt/oracle-manifest.txt').exists():
        raise SystemExit('FAIL oracle-outside-the-image: the live modes run only in the oracle image (tools/in-container)')
    Path('/xdev').mkdir(exist_ok=True)
    HOME.parent.mkdir(parents=True, exist_ok=True)
    if os.stat('/xdev').st_dev == os.stat(HOME.parent).st_dev:
        raise SystemExit('FAIL oracle-xdev: /xdev is not a second file system')
    for top in ('/tmp', '/xdev'):
        v = os.statvfs(top)
        if os.stat(top).st_dev == os.stat('/').st_dev or v.f_blocks * v.f_frsize > CAP:
            raise SystemExit('FAIL oracle-cap: %s is not a file system of its own of at most %d bytes '
                             '(tools/in-container mounts one)' % (top, CAP))


def report(name, diffs, extra=''):
    if diffs:
        for field, detail in diffs:
            print('FAIL %s %s: %s' % (name, field, detail))
        return 1
    print('PASS %s%s' % (name, extra))
    return 0


def oracle_diffs(row, want, got):
    """compare(), less the crash a row says the oracle makes."""
    diffs = compare(want, got)
    if row.get('oracle') == 'crashes':
        diffs = [d for d in diffs if d[0] != 'traceback']
    return diffs


def cmd_record(a):
    live_guard()
    out = Path(a.golden)
    out.mkdir(parents=True, exist_ok=True)
    fails = 0
    for row in load_rows(a.rows, a.only):
        cap = normalise(run_row(row, oracle_bin()))
        (out / (row['name'] + '.json')).write_text(json.dumps(cap, indent=1, sort_keys=True, ensure_ascii=False) + '\n')
        if cap['tracebacks'] and row.get('oracle') != 'crashes':
            fails += report(row['name'], [('traceback', 'the oracle crashed; its output is redacted')])
        else:
            print('RECORDED %s commands=%d' % (row['name'], len(cap['steps'])))
    return 1 if fails else 0


def cmd_check(a):
    live_guard()
    fails = 0
    rows = load_rows(a.rows, a.only)
    for row in rows:
        path = Path(a.golden) / (row['name'] + '.json')
        if not path.exists():
            fails += report(row['name'], [('golden', 'none recorded')])
            continue
        fails += report(row['name'], oracle_diffs(row, json.loads(path.read_text()), normalise(run_row(row, oracle_bin()))))
    names = {r['name'] for r in load_rows(a.rows, None)}
    for g in sorted(Path(a.golden).glob('*.json')):
        if g.stem not in names:
            fails += report(g.stem, [('golden', 'a golden with no row')])
    print('SUMMARY oracle-check rows=%d failed=%d' % (len(rows), fails))
    return 1 if fails else 0


def row_commands(row):
    return sorted({unescape(st['run'][0]).decode() for st in row['steps'] if 'run' in st})


def candidate_rows(a):
    """The rows the candidate can run: every command they use is in the
    candidate directory (or in --commands). The others are named, not run."""
    if a.commands:
        have = set(a.commands.split(','))
    else:
        have = {c for c in COMMANDS if os.access(os.path.join(a.candidate, c), os.X_OK)}
    rows, out = [], []
    for row in load_rows(a.rows, a.only):
        missing = [c for c in row_commands(row) if c not in have]
        (out if missing else rows).append((row, missing))
    for row, missing in out:
        print('OUT %s needs %s' % (row['name'], ' '.join(missing)))
    return [r for r, _ in rows]


def cmd_compare(a):
    live_guard()
    fails = 0
    rows = candidate_rows(a)
    if not rows:
        print('FAIL oracle-compare no row the candidate can run')
        return 1
    for row in rows:
        got = normalise(run_row(row, os.path.abspath(a.candidate)))
        if row.get('diverge'):
            # This repository departs from the oracle here by design (the row
            # says why): the candidate is held to its own expected capture.
            path = ROOT / 'tests/oracle/expected' / (row['name'] + '.json')
            if not path.exists():
                fails += report(row['name'], [('expected', 'a diverging row with no expected capture')])
                continue
            fails += report(row['name'], compare(json.loads(path.read_text()), got), ' (diverges: %s)' % row['diverge'])
            continue
        want = normalise(run_row(row, oracle_bin()))
        fails += report(row['name'], compare(want, got))
    print('SUMMARY oracle-compare rows=%d failed=%d' % (len(rows), fails))
    return 1 if fails else 0


def cmd_capture(a):
    live_guard()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    rows = candidate_rows(a)
    for row in rows:
        cap = normalise(run_row(row, os.path.abspath(a.candidate)))
        (out / (row['name'] + '.json')).write_text(json.dumps(cap, indent=1, sort_keys=True, ensure_ascii=False) + '\n')
        print('CAPTURED %s commands=%d' % (row['name'], len(cap['steps'])))
    return 0


def synthetic():
    """A capture shaped like trashing one file, for the comparer's own tests."""
    now = 1794100000.0
    date = datetime.datetime.fromtimestamp(now + 1, zoneinfo.ZoneInfo('Europe/Berlin')).strftime('%Y-%m-%dT%H:%M:%S')
    info = '[Trash Info]\nPath=/tmp/trash-rows/home/a%%20b.txt\nDeletionDate=%s\n' % date
    return {
        'row': 'synthetic', 'tz': 'Europe/Berlin', 'window': [now, now + 3],
        'steps': [{'argv': ['trash', 'a b.txt'], 'exit': 0, 'stdout': '', 'stderr': ''},
                  {'argv': ['trash-list'], 'exit': 0,
                   'stdout': '%s /tmp/trash-rows/home/a b.txt\n2020-01-02 03:04:05 /old\n' % date.replace('T', ' '), 'stderr': ''}],
        'trees': {'home': {
            'Trash': {'type': 'dir', 'mode': '0700', 'mtime': int(now) + 1, 'owner': '0:0'},
            'Trash/files': {'type': 'dir', 'mode': '0700', 'mtime': int(now) + 1, 'owner': '0:0'},
            'Trash/files/a b.txt': {'type': 'file', 'mode': '0644', 'mtime': FIXTURE_TIME, 'owner': '0:0', 'size': 5,
                                    'sha256': hashlib.sha256(b'hello').hexdigest(),
                                    'mtime_ns': 123456789, 'atime': FIXTURE_TIME - 9, 'atime_ns': 5},
            'Trash/files/l': {'type': 'link', 'mode': '0777', 'mtime': FIXTURE_TIME, 'owner': '0:0', 'target': 'a b.txt'},
            'Trash/info': {'type': 'dir', 'mode': '0700', 'mtime': int(now) + 1, 'owner': '0:0'},
            'Trash/info/a b.txt.trashinfo': {'type': 'file', 'mode': '0600', 'mtime': int(now) + 1, 'owner': '0:0',
                                             'size': len(info), 'sha256': hashlib.sha256(info.encode()).hexdigest(), 'text': info},
        }, 'xdev': {}},
    }


def mutations():
    """name -> (mutate(capture), the field the comparer must name)."""
    info = 'Trash/info/a b.txt.trashinfo'

    def text(c, f):
        e = c['trees']['home'][info]
        e['text'] = f(e['text'])

    def date(c, v):
        text(c, lambda t: re.sub(r'DeletionDate=.*', 'DeletionDate=' + v, t))
    return {
        'path-line': (lambda c: text(c, lambda t: t.replace('a%20b.txt', 'a b.txt')), 'home:%s:text' % info),
        'path-missing': (lambda c: text(c, lambda t: re.sub(r'Path=.*\n', '', t)), 'home:%s:text' % info),
        'header': (lambda c: text(c, lambda t: t.replace('[Trash Info]', '[Trash info]')), 'home:%s:text' % info),
        'extra-line': (lambda c: text(c, lambda t: t + 'Extra=1\n'), 'home:%s:text' % info),
        'date-outside': (lambda c: date(c, '2020-01-02T03:04:05'), 'home:%s:text' % info),
        'date-shape': (lambda c: date(c, datetime.datetime.fromtimestamp(c['window'][0], zoneinfo.ZoneInfo(c['tz'])).strftime('%Y%m%dT%H:%M:%S')), 'home:%s:text' % info),
        'date-utc': (lambda c: date(c, datetime.datetime.fromtimestamp(c['window'][0], datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')), 'home:%s:text' % info),
        'info-mode': (lambda c: c['trees']['home'][info].update(mode='0644'), 'home:%s:mode' % info),
        'file-bytes': (lambda c: c['trees']['home']['Trash/files/a b.txt'].update(sha256='0' * 64), 'home:Trash/files/a b.txt:sha256'),
        'file-mode': (lambda c: c['trees']['home']['Trash/files/a b.txt'].update(mode='0600'), 'home:Trash/files/a b.txt:mode'),
        'file-mtime': (lambda c: c['trees']['home']['Trash/files/a b.txt'].update(mtime=FIXTURE_TIME + 1), 'home:Trash/files/a b.txt:mtime'),
        'file-mtime-ns': (lambda c: c['trees']['home']['Trash/files/a b.txt'].update(mtime_ns=123456788), 'home:Trash/files/a b.txt:mtime_ns'),
        'file-atime': (lambda c: c['trees']['home']['Trash/files/a b.txt'].update(atime=FIXTURE_TIME), 'home:Trash/files/a b.txt:atime'),
        'file-atime-ns': (lambda c: c['trees']['home']['Trash/files/a b.txt'].update(atime_ns=6), 'home:Trash/files/a b.txt:atime_ns'),
        'file-as-fifo': (lambda c: c['trees']['home']['Trash/files/a b.txt'].update(type='fifo'), 'home:Trash/files/a b.txt:type'),
        'link-as-file': (lambda c: c['trees']['home']['Trash/files/l'].update(type='file'), 'home:Trash/files/l:type'),
        'link-target': (lambda c: c['trees']['home']['Trash/files/l'].update(target='elsewhere'), 'home:Trash/files/l:target'),
        'dir-mode': (lambda c: c['trees']['home']['Trash'].update(mode='0755'), 'home:Trash:mode'),
        'extra-entry': (lambda c: c['trees']['home'].update({'Trash/files/a b_1.txt': dict(c['trees']['home']['Trash/files/a b.txt'])}),
                        'home:Trash/files/a b_1.txt'),
        'missing-entry': (lambda c: c['trees']['home'].pop('Trash/files/l'), 'home:Trash/files/l'),
        'left-behind': (lambda c: c['trees']['xdev'].update({'x.txt': {'type': 'file', 'mode': '0644', 'mtime': FIXTURE_TIME, 'owner': '0:0', 'size': 0, 'sha256': '0' * 64}}),
                        'xdev:x.txt'),
        'exit': (lambda c: c['steps'][0].update(exit=1), 'step1-exit'),
        'stdout': (lambda c: c['steps'][1].update(stdout=c['steps'][1]['stdout'].replace('/old', '/new')), 'step2-stdout'),
        'stdout-date': (lambda c: c['steps'][1].update(stdout=c['steps'][1]['stdout'].replace('2020-01-02', '2020-01-03')), 'step2-stdout'),
        'stderr': (lambda c: c['steps'][0].update(stderr='trash: x\n'), 'step1-stderr'),
        'traceback': (lambda c: c['steps'][0].update(stderr=TRACEBACK + '\n  File "x", line 1\nError: y\n'), 'traceback'),
    }


def guarded():
    """The oracle is never handed '//' or '//x', and is handed '/' and '///'."""
    def refused(word):
        try:
            oracle_guard({'name': 'g'}, oracle_bin(), [b'trash', word])
        except SystemExit:
            return True
        return False
    return refused(b'//') and refused(b'//tmp/..') and not refused(b'/') and not refused(b'///x')


def in_window_ns(base):
    import copy
    c = copy.deepcopy(base)
    c['trees']['home']['Trash'].update(mtime_ns=77)
    return c


def own_words(base):
    """An own-words row holds which stream carries text, not the text."""
    import copy
    a, b, c = copy.deepcopy(base), copy.deepcopy(base), copy.deepcopy(base)
    for x in (a, b, c):
        x['own_words'] = True
    a['steps'][0].update(stdout='usage: ours\n')
    b['steps'][0].update(stdout='usage: theirs\nmore\n')
    c['steps'][0].update(stderr='usage: ours\n')
    na, nb, nc = normalise(a), normalise(b), normalise(c)
    return compare(na, nb) == [] and any(f == 'step1-stdout' for f, _ in compare(na, nc))


def offsets_named():
    """A date a declared offset from the window reads by that offset; an
    undeclared one is kept."""
    w = [1794100000.0, 1794100003.0]
    t = local_text(int(w[0]) - 86460, 'UTC')
    named_one = norm_deletion_date(t, w, 'UTC', [-86460]) == '<in-window-86460>'
    kept = norm_deletion_date(t, w, 'UTC', [-86340]) == '<outside-window:%s>' % t
    listed = norm_output('   0 %s /x\n' % t.replace('T', ' '), w, 'UTC', [-86460]) == '   0 <in-window-86460> /x\n'
    return named_one and kept and listed


def plan_ok():
    """The generator is a pure function of its seed, and makes every kind."""
    a, b = tree_plan('t', 7), tree_plan('t', 7)
    kinds = {e['kind'] for s in range(1, 7) for e in tree_plan('t', s)}
    return a == b and a != tree_plan('t', 8) and kinds == {'dir', 'file', 'link', 'fifo'}


def tty_ok():
    """A step marked tty reads a terminal, and its input ends."""
    r = run_step([b'/bin/sh', b'-c', b'[ -t 0 ] && echo tty; cat'], b'/', {'PATH': '/usr/bin:/bin'}, b'y\n', True)
    return r.returncode == 0 and r.stdout.replace(b'\r', b'') == b'tty\ny\n'


def property_seen(base):
    """A round trip that failed is a difference by name; one that held is
    none; the same failures twice are none."""
    import copy
    held, broken = copy.deepcopy(base), copy.deepcopy(base)
    held['property'] = []
    broken['property'] = ['home:t0/f0 mode want 420 got 384']
    nh, nb = normalise(held), normalise(broken)
    return compare(nh, nh) == [] and compare(nb, nb) == [] and \
        any(f == 'property' for f, _ in compare(nh, nb)) and any(f == 'property' for f, _ in compare(nb, nh))


def cmd_selftest(a):
    import copy
    fails = 0
    base = synthetic()
    n = normalise(base)
    info = n['trees']['home']['Trash/info/a b.txt.trashinfo']['text']
    checks = [
        ('normalise-date', 'DeletionDate=<in-window>' in info, info),
        ('normalise-path-kept', 'Path=/tmp/trash-rows/home/a%20b.txt' in info, info),
        ('normalise-list-date', n['steps'][1]['stdout'].startswith('<in-window> /tmp/trash-rows/home/a b.txt\n'), n['steps'][1]['stdout']),
        ('normalise-fixed-date-kept', '2020-01-02 03:04:05 /old' in n['steps'][1]['stdout'], n['steps'][1]['stdout']),
        ('normalise-dir-mtime', n['trees']['home']['Trash']['mtime'] == '<in-window>', n['trees']['home']['Trash']),
        ('normalise-fixture-mtime-kept', n['trees']['home']['Trash/files/a b.txt']['mtime'] == FIXTURE_TIME, ''),
        ('normalise-bad-shape', norm_deletion_date('20261108T01:02:03', [0, 1], 'UTC') == '<bad-shape:20261108T01:02:03>', ''),
        ('normalise-outside', norm_deletion_date('2020-01-02T03:04:05', [0, 1], 'UTC') == '<outside-window:2020-01-02T03:04:05>', ''),
        ('host-order', host_order('b\na\n') == 'a\nb\n' and host_order('b\na') == 'a\nb', ''),
        ('redact', redact('ok\n' + TRACEBACK + '\n  File "x"\nE\n') == ('ok\n<traceback redacted: 4 lines>\n', 4), ''),
        ('self-equal', compare(n, normalise(copy.deepcopy(base))) == [], compare(n, normalise(copy.deepcopy(base)))),
        ('normalise-ns-kept', n['trees']['home']['Trash/files/a b.txt'].get('mtime_ns') == 123456789, ''),
        ('normalise-ns-in-window-dropped', 'mtime_ns' not in normalise(in_window_ns(base))['trees']['home']['Trash'], ''),
        ('own-words', own_words(base), ''),
        ('oracle-guard', guarded(), ''),
        ('normalise-offset', offsets_named(), ''),
        ('tree-plan', plan_ok(), ''),
        ('tty-step', tty_ok(), ''),
        ('property-seen', property_seen(base), ''),
        ('as-user', as_user({'user': [1000, 1000]}, [b'trash', b'a']) ==
         [SETPRIV.encode(), b'--reuid=1000', b'--regid=1000', b'--clear-groups', b'--', b'trash', b'a'] and
         as_user({}, [b'trash']) == [b'trash'], ''),
    ]
    for name, ok, detail in checks:
        if ok:
            print('PASS selftest-%s' % name)
        else:
            print('FAIL selftest-%s %r' % (name, detail))
            fails += 1
    for name, (mutate, field) in sorted(mutations().items()):
        c = copy.deepcopy(base)
        mutate(c)
        diffs = compare(n, normalise(c))
        if any(f == field for f, _ in diffs):
            print('PASS selftest-%s seen as %s' % (name, field))
        else:
            print('FAIL selftest-%s the comparer did not see it at %s (it saw %r)' % (name, field, diffs))
            fails += 1
    if a.live:
        live_guard()
        for row in load_rows(a.rows, a.only):
            one = normalise(run_row(row, oracle_bin()))
            two = normalise(run_row(row, oracle_bin()))
            fails += report('live-' + row['name'], oracle_diffs(row, one, two), ' (the oracle twice, the same)')
    print('SUMMARY oracle-selftest failed=%d' % fails)
    return 1 if fails else 0


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest='cmd', required=True)
    for name in ('record', 'check', 'compare', 'capture'):
        s = sub.add_parser(name)
        s.add_argument('--rows', required=True)
        s.add_argument('--only')
        if name in ('record', 'check'):
            s.add_argument('--golden', required=True)
        else:
            s.add_argument('--candidate', required=True)
            s.add_argument('--commands')
        if name == 'capture':
            s.add_argument('--out', required=True)
    s = sub.add_parser('selftest')
    s.add_argument('--live', action='store_true')
    s.add_argument('--rows')
    s.add_argument('--only')
    a = p.parse_args()
    return {'record': cmd_record, 'check': cmd_check, 'compare': cmd_compare, 'capture': cmd_capture,
            'selftest': cmd_selftest}[a.cmd](a)


if __name__ == '__main__':
    sys.exit(main())
