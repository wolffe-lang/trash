#!/usr/bin/env python3
"""The hardening rows: a command cut at each of its durable steps, and two
commands run at once. Linux, inside the oracle image, on this repository's
commands alone (trash-cli has no cut hook and is never raced).

  harden.py cuts     --rows FILE --candidate DIR [--only RE]
  harden.py capture  --rows FILE --candidate DIR --out DIR [--only RE]
  harden.py stress   --rows FILE --candidate DIR --rounds N --seed S [--only RE]
  harden.py rm-witness --rows FILE [--only RE]
  harden.py selftest

**Cut rows** (tests/cuts/rows.json). A row is a fixture (`steps`: make steps
and uncut runs, as tools/oracle.py reads them) and one command (`cut`). The
command runs once uncut ("whole"), then with TRASH_CUT=1, 2, … until a run
is not cut: the commands end themselves by SIGKILL just before their Nth
durable step, saying `cut before WHAT` on standard error (src/can/cut.lu).
After each cut the harness snapshots the trees, runs `trash-list`, runs the
command again uncut (the rerun) and snapshots again. What is held, per cut:
the step named, the cut run's standard output, the trees after it, the
listing (its lines sorted, since it lists in the host's order), the
rerun's exit status and streams, and the trees after it
("whole" when they are the uncut run's). And a property every cut keeps:
every regular file's bytes that the fixture left (less those under a path
the row's `spend` names, which the command was asked to remove) are still
in some regular file in the home or on the second file system, after the
cut and after the rerun. A capture is held to tests/cuts/expected/ROW.json,
written by hand in tools/expected.py.

**Stress rows** (tests/cuts/stress.json). Two commands (`pair`) after a
fixture, N rounds; each round draws from the seed which command starts
first, a start gap, and a pause (TRASH_PAUSE=K:MS, a sleep before the Kth
durable step) for one of them, then holds the result to the outcomes the
row's `allowed` kind admits. A failure names the round and its draw.

**rm-witness**: GNU rm, run as each permission row's user on its fixture
(`rm -f` for a file, `rm -rf` for a directory), its exit status and its
message, for the note's table of who decided each row.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import re
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
import oracle  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CUT_RE = re.compile(r'(?:^|\n)cut before ([^\n]*)\n?$')
KILLED = -9


def load(path, only):
    rows = json.loads(Path(path).read_text())['rows']
    names = [r['name'] for r in rows]
    if len(names) != len(set(names)):
        raise ValueError('duplicate row names')
    return [r for r in rows if not only or re.search(only, r['name'])]


def fresh(row):
    oracle.clean()
    oracle.CURRENT['home'] = oracle.HOMES[row.get('home', 'root')]
    oracle.home().mkdir(parents=True)
    oracle.XDEV.mkdir(parents=True)
    oracle.OFFSETS.clear()


def command(row, tool, step, extra=None):
    """One command of a row, on the tool, with extra environment."""
    argv = [oracle.unescape(a) for a in step['run']]
    argv[0] = oracle.tool_path(tool, argv[0].decode()).encode()
    env = oracle.env_for(row)
    env.update(extra or {})
    cwd = oracle.where(oracle.unescape(step.get('cwd', '')))
    return oracle.run_step(oracle.as_user(row, argv), cwd, env, oracle.unescape(step.get('stdin', '')), False)


def fixture(row, tool):
    """The row's fixture: its make steps and its uncut runs, which must succeed."""
    for step in row['steps']:
        if 'make' in step:
            oracle.make(step['make'], row.get('tz', 'UTC'))
            oracle.own_fixture(row)
            continue
        r = command(row, tool, step)
        if r.returncode != 0:
            raise SystemExit('FAIL %s fixture: %s exited %d: %s' % (row['name'], ' '.join(step['run']), r.returncode,
                                                                      oracle.show(r.stderr)))


def trees():
    return {'home': oracle.snapshot(bytes(oracle.home())), 'xdev': oracle.snapshot(bytes(oracle.XDEV))}


def contents(snap, spend=()):
    """The digests of every regular file in a pair of trees (less those under
    a spent path), as a set."""
    out = set()
    for tname, tree in snap.items():
        for rel, e in tree.items():
            if e['type'] != 'file' or rel.endswith('.trashinfo') or rel.endswith('directorysizes'):
                continue
            if tname == 'home' and any(rel == s or rel.startswith(s + '/') for s in spend):
                continue
            out.add(e['sha256'])
    return out


def norm_trees(t, window, tz):
    cap = {'row': '', 'tz': tz, 'window': window, 'steps': [], 'trees': t, 'offsets': []}
    return oracle.normalise(cap)['trees']


def norm_stream(text, window, tz):
    return oracle.norm_output(text, window, tz)


def result(r, window, tz):
    return {'exit': r.returncode, 'stdout': norm_stream(oracle.show(r.stdout), window, tz),
            'stderr': norm_stream(oracle.show(r.stderr), window, tz)}


def one(row, tool, cut):
    """The fixture, then the row's command (cut before its step `cut`, or
    uncut when None), the listing, the rerun, and what each left."""
    fresh(row)
    start = time.time()
    fixture(row, tool)
    precious = contents(trees(), row.get('spend', ()))
    tz = row.get('tz', 'UTC')
    env = {'TRASH_CUT': str(cut)} if cut else {}
    r = command(row, tool, row['cut'], env)
    out = {'precious': precious}
    err = oracle.show(r.stderr)
    m = CUT_RE.search(err)
    if cut and r.returncode == KILLED and m:
        out['step'] = m.group(1)
        err = err[:m.start()] + ('\n' if m.group(0).startswith('\n') else '')
    elif cut and r.returncode == KILLED:
        out['step'] = '<killed with no cut line>'
    after_cut = trees()
    lst = command(row, tool, {'run': ['trash-list'], 'cwd': row['cut'].get('cwd', '')})
    rerun = command(row, tool, row['cut']) if 'step' in out else None
    after = trees()
    end = time.time()
    w = [start, end]
    out['run'] = {'exit': r.returncode, 'stdout': norm_stream(oracle.show(r.stdout), w, tz),
                  'stderr': norm_stream(err, w, tz)}
    out['cut'] = norm_trees(after_cut, w, tz)
    # the listing is in the order the host lists the trash: its lines are held sorted
    out['list'] = result(lst, w, tz)
    out['list']['stdout'] = oracle.host_order(out['list']['stdout'])
    out['list']['stderr'] = oracle.host_order(out['list']['stderr'])
    if rerun is not None:
        out['rerun'] = result(rerun, w, tz)
        out['after'] = norm_trees(after, w, tz)
    out['lost'] = sorted(precious - contents(after_cut)) + sorted(precious - contents(after))
    oracle.clean()
    return out


def capture(row, tool):
    """A cut row's capture: the whole run, then one entry per cut."""
    whole = one(row, tool, None)
    cap = {'row': row['name'], 'whole': {'run': whole['run'], 'trees': whole['cut']}, 'cuts': []}
    k = 1
    while True:
        c = one(row, tool, k)
        if 'step' not in c:
            if c['run']['exit'] == KILLED:
                cap['cuts'].append({'step': '<killed>'})
            break
        entry = {'step': c['step'], 'run': c['run'], 'trees': c['cut'], 'list': c['list'], 'rerun': c['rerun'],
                 'after': 'whole' if c['after'] == cap['whole']['trees'] else c['after']}
        if c['lost']:
            entry['lost'] = c['lost']
        cap['cuts'].append(entry)
        k += 1
        if k > 200:
            cap['cuts'].append({'step': '<more than 200 steps>'})
            break
    return cap


def cut_diffs(want, got):
    """Every difference between two cut captures: (field, detail)."""
    diffs = []

    def run_diffs(prefix, a, b):
        for k in ('exit', 'stdout', 'stderr'):
            if a.get(k) != b.get(k):
                detail = oracle.first_diff(a[k], b[k]) if k != 'exit' and a.get(k) is not None and b.get(k) is not None \
                    else 'want %r got %r' % (a.get(k), b.get(k))
                diffs.append(('%s-%s' % (prefix, k), detail))

    def tree_diffs(prefix, a, b):
        if a == 'whole' or b == 'whole':
            if a != b:
                diffs.append((prefix, 'want %s got %s' % ('the whole run\'s trees' if a == 'whole' else 'other trees',
                                                          'the whole run\'s trees' if b == 'whole' else 'other trees')))
                if a != 'whole' and b == 'whole':
                    b = got['whole']['trees']
                elif a == 'whole' and b != 'whole':
                    a = want['whole']['trees']
                else:
                    return
            else:
                return
        fake_a = {'steps': [], 'trees': a, 'tracebacks': 0}
        fake_b = {'steps': [], 'trees': b, 'tracebacks': 0}
        for f, d in oracle.compare(fake_a, fake_b):
            diffs.append(('%s:%s' % (prefix, f), d))

    run_diffs('whole', want['whole']['run'], got['whole']['run'])
    tree_diffs('whole', want['whole']['trees'], got['whole']['trees'])
    wc, gc = want['cuts'], got['cuts']
    if len(wc) != len(gc):
        diffs.append(('cuts', 'want %d cuts got %d' % (len(wc), len(gc))))
    for i, (a, b) in enumerate(zip(wc, gc), 1):
        p = 'cut%d' % i
        if a.get('step') != b.get('step'):
            diffs.append((p + '-step', 'want %r got %r' % (a.get('step'), b.get('step'))))
            continue
        if b.get('lost'):
            diffs.append((p + '-lost', '%d file(s) lost: %s' % (len(b['lost']), ' '.join(x[:12] for x in b['lost']))))
        if 'run' not in a or 'run' not in b:
            continue
        run_diffs(p + '-run', a['run'], b['run'])
        tree_diffs(p + '-trees', a['trees'], b['trees'])
        run_diffs(p + '-list', a['list'], b['list'])
        run_diffs(p + '-rerun', a['rerun'], b['rerun'])
        tree_diffs(p + '-after', a['after'], b['after'])
    for i, b in enumerate(gc[len(wc):], len(wc) + 1):
        diffs.append(('cut%d-step' % i, 'unexpected %r' % b.get('step')))
    return diffs


def cmd_cuts(a):
    oracle.live_guard()
    fails = 0
    rows = load(a.rows, a.only)
    for row in rows:
        path = ROOT / 'tests/cuts/expected' / (row['name'] + '.json')
        if not path.exists():
            fails += oracle.report(row['name'], [('expected', 'a cut row with no expected capture')])
            continue
        got = capture(row, os.path.abspath(a.candidate))
        fails += oracle.report(row['name'], cut_diffs(json.loads(path.read_text()), got),
                               ' (%d cuts)' % len(got['cuts']))
    print('SUMMARY harden-cuts rows=%d failed=%d' % (len(rows), fails))
    return 1 if fails else 0


def cmd_capture(a):
    oracle.live_guard()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    for row in load(a.rows, a.only):
        cap = capture(row, os.path.abspath(a.candidate))
        (out / (row['name'] + '.json')).write_text(json.dumps(cap, indent=1, sort_keys=True, ensure_ascii=False) + '\n')
        print('CAPTURED %s cuts=%d' % (row['name'], len(cap['cuts'])))
    return 0


# ---------------------------------------------------------------- stress


def entries(t, prefix):
    return sorted(rel[len(prefix):] for rel in t if rel.startswith(prefix) and '/' not in rel[len(prefix):])


def info_path(text):
    for line in text.split('\n'):
        if line.startswith('Path='):
            return line[len('Path='):]
    return None


def outcome(row, snap, results):
    """Why the round's result is not one the row's kind allows, or None."""
    kind = row['allowed']
    home = snap['home']
    files, infos = entries(home, 'Trash/files/'), entries(home, 'Trash/info/')
    H = str(oracle.home())
    if kind == 'collide':
        if [r.returncode for r in results] != [0, 0]:
            return 'exit statuses %r' % [r.returncode for r in results]
        if files != ['a.txt', 'a.txt_1'] or infos != ['a.txt.trashinfo', 'a.txt_1.trashinfo']:
            return 'files %r infos %r' % (files, infos)
        seen = set()
        for name in files:
            p = info_path(home['Trash/info/%s.trashinfo' % name].get('text', ''))
            want = {H + '/d1/a.txt': row['contents'][0], H + '/d2/a.txt': row['contents'][1]}.get(p)
            if want is None or p in seen:
                return 'info %s names %r' % (name, p)
            seen.add(p)
            if home['Trash/files/' + name].get('sha256') != hashlib.sha256(want.encode()).hexdigest():
                return 'files/%s does not hold the bytes of %s' % (name, p)
        if 'd1/a.txt' in home or 'd2/a.txt' in home:
            return 'a source is still there'
        return None
    if kind in ('put-empty', 'put-rm'):
        item = row['item']
        if [r.returncode for r in results] != [0, 0]:
            return 'exit statuses %r' % [r.returncode for r in results]
        if item in home:
            return '%s is still where it was' % item
        if files == [] and infos == []:
            return None
        if files == [item] and infos == [item + '.trashinfo']:
            p = info_path(home['Trash/info/%s.trashinfo' % item].get('text', ''))
            if p != H + '/' + item:
                return 'its info file names %r' % p
            if home['Trash/files/' + item].get('sha256') != hashlib.sha256(row['contents'][0].encode()).hexdigest():
                return 'files/%s does not hold its bytes' % item
            return None
        return 'files %r infos %r' % (files, infos)
    if kind in ('restore-twice', 'restore-twice-dir', 'restore-twice-other-fs'):
        codes = sorted(r.returncode for r in results)
        if codes[0] != 0 or codes[1] not in (0, 1):
            return 'exit statuses %r' % [r.returncode for r in results]
        if files != [] or infos != []:
            return 'the trash still holds files %r infos %r' % (files, infos)
        where = snap['xdev'] if kind == 'restore-twice-other-fs' else home
        item = row['item']
        want = hashlib.sha256(row['contents'][0].encode()).hexdigest()
        key = item + '/f' if kind == 'restore-twice-dir' else item
        if where.get(key, {}).get('sha256') != want:
            return '%s is not back with its bytes (%r)' % (key, where.get(key))
        copies = sum(1 for t in snap.values() for e in t.values() if e.get('sha256') == want)
        if copies != 1:
            return '%d copies of its bytes' % copies
        return None
    raise ValueError('unknown outcome kind: ' + kind)


def draw(rng, row):
    p = row.get('pause', {})
    lo, hi = p.get('steps', [1, 8])
    return {'first': rng.randrange(2), 'gap_ms': rng.choice([0, 0, 1, 2, 5]), 'paused': rng.randrange(2),
            'k': rng.randint(lo, hi), 'ms': rng.choice(p.get('ms', [5, 20, 50]))}


def round_once(row, tool, d):
    fresh(row)
    fixture(row, tool)
    procs = [None, None]
    order = [d['first'], 1 - d['first']]
    for n, who in enumerate(order):
        step = row['pair'][who]
        argv = [oracle.unescape(x) for x in step['run']]
        argv[0] = oracle.tool_path(tool, argv[0].decode()).encode()
        env = oracle.env_for(row)
        if who == d['paused']:
            env['TRASH_PAUSE'] = '%d:%d' % (d['k'], d['ms'])
        cwd = oracle.where(oracle.unescape(step.get('cwd', '')))
        procs[who] = subprocess.Popen(oracle.as_user(row, argv), cwd=cwd, env=env, stdin=subprocess.PIPE,
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        # Each command's input is written whole and closed at its start, so
        # neither waits on the other's end to be answered.
        procs[who].stdin.write(oracle.unescape(step.get('stdin', '')))
        procs[who].stdin.close()
        if n == 0 and d['gap_ms']:
            time.sleep(d['gap_ms'] / 1000)
    results = []
    for who in (0, 1):
        out, err = procs[who].communicate(timeout=120)
        results.append(subprocess.CompletedProcess([], procs[who].returncode, out, err))
    snap = trees()
    oracle.clean()
    return outcome(row, snap, results), results


def cmd_stress(a):
    oracle.live_guard()
    fails = 0
    rows = load(a.rows, a.only)
    for row in rows:
        rng = random.Random('%s:%s' % (a.seed, row['name']))
        bad = 0
        for i in range(a.rounds):
            d = draw(rng, row)
            why, results = round_once(row, os.path.abspath(a.candidate), d)
            if why:
                bad += 1
                if bad <= 5:
                    errs = ' | '.join(oracle.show(r.stderr).strip().replace('\n', ' / ') for r in results)
                    print('FAIL %s round=%d %s: %s [stderr: %s]' % (row['name'], i, json.dumps(d, sort_keys=True), why, errs))
        if bad:
            print('FAIL %s %d of %d rounds outside the allowed outcomes (seed %s)' % (row['name'], bad, a.rounds, a.seed))
            fails += 1
        else:
            print('PASS %s rounds=%d seed=%s' % (row['name'], a.rounds, a.seed))
    print('SUMMARY harden-stress rows=%d rounds=%d seed=%s failed=%d' % (len(rows), a.rounds, a.seed, fails))
    return 1 if fails else 0


# ---------------------------------------------------------------- rm


def cmd_rm_witness(a):
    oracle.live_guard()
    rows = json.loads(Path(a.rows).read_text())['rows']
    for row in rows:
        if a.only and not re.search(a.only, row['name']):
            continue
        fresh(row)
        target = None
        for step in row['steps']:
            if 'make' in step:
                oracle.make(step['make'], row.get('tz', 'UTC'))
                oracle.own_fixture(row)
            elif step['run'][0] == 'trash':
                target = step
                break
            else:
                break
        if target is None:
            oracle.clean()
            continue
        op = target['run'][-1]
        p = oracle.where(oracle.unescape(op)) if not op.startswith('/') else oracle.unescape(op)
        flags = [b'-rf'] if os.path.isdir(p) and not os.path.islink(p) else [b'-f']
        cwd = oracle.where(oracle.unescape(target.get('cwd', '')))
        r = oracle.run_step(oracle.as_user(row, [b'/usr/bin/rm'] + flags + [oracle.unescape(op)]), cwd,
                            oracle.env_for(row), b'', False)
        gone = not os.path.lexists(p)
        print('RM %s exit=%d %s stderr=%r' % (row['name'], r.returncode, 'removed' if gone else 'kept',
                                              oracle.show(r.stderr).strip()))
        oracle.clean()
    return 0


# ---------------------------------------------------------------- selftest


def cmd_selftest(a):
    fails = 0
    tree = {'home': {'a.txt': {'type': 'file', 'sha256': 'aa', 'mode': '0644', 'mtime': 1, 'owner': '0:0', 'size': 1},
                     'Trash/files/b': {'type': 'file', 'sha256': 'bb', 'mode': '0644', 'mtime': 1, 'owner': '0:0', 'size': 1},
                     'Trash/info/b.trashinfo': {'type': 'file', 'sha256': 'cc', 'mode': '0600', 'mtime': 1, 'owner': '0:0',
                                                'size': 1, 'text': ''}},
            'xdev': {'x': {'type': 'file', 'sha256': 'dd', 'mode': '0644', 'mtime': 1, 'owner': '0:0', 'size': 1}}}
    whole = {'run': {'exit': 0, 'stdout': '', 'stderr': ''}, 'trees': tree}
    good = {'row': 'r', 'whole': whole, 'cuts': [
        {'step': 'reserve x', 'run': {'exit': -9, 'stdout': '', 'stderr': ''}, 'trees': tree,
         'list': {'exit': 0, 'stdout': '', 'stderr': ''}, 'rerun': {'exit': 0, 'stdout': '', 'stderr': ''}, 'after': 'whole'}]}
    import copy

    def sees(field, f, prefix=False):
        c = copy.deepcopy(good)
        f(c)
        return any((x.startswith(field) if prefix else x == field) for x, _ in cut_diffs(good, c))

    def other_after(c):
        c['cuts'][0]['after'] = copy.deepcopy(tree)
        c['cuts'][0]['after']['home'].pop('a.txt')
    checks = [
        ('contents', contents(tree) == {'aa', 'bb', 'dd'} and contents(tree, ['Trash/files/b']) == {'aa', 'dd'}),
        ('self-equal', cut_diffs(good, copy.deepcopy(good)) == []),
        ('step', sees('cut1-step', lambda c: c['cuts'][0].update(step='write x'))),
        ('lost', sees('cut1-lost', lambda c: c['cuts'][0].update(lost=['ee']))),
        ('fewer-cuts', sees('cuts', lambda c: c['cuts'].pop())),
        ('more-cuts', sees('cut2', lambda c: c['cuts'].append(dict(c['cuts'][0])), True)),
        ('rerun-exit', sees('cut1-rerun-exit', lambda c: c['cuts'][0]['rerun'].update(exit=74))),
        ('list-stderr', sees('cut1-list-stderr', lambda c: c['cuts'][0]['list'].update(stderr='trash-list: x\n'))),
        ('after-not-whole', sees('cut1-after', other_after)),
        ('trees-entry', sees('cut1-trees:home:a.txt', lambda c: c['cuts'][0].update(trees={'home': {}, 'xdev': tree['xdev']}),
                             True)),
        ('cut-line', CUT_RE.search('x\ncut before reserve a\n').group(1) == 'reserve a' and
         CUT_RE.search('cut before b\n').group(1) == 'b' and CUT_RE.search('cut before b\nmore\n') is None),
        ('info-path', info_path('[Trash Info]\nPath=/a\nPath=/b\n') == '/a' and info_path('[Trash Info]\n') is None),
    ]
    oracle.CURRENT['home'] = Path('/h')
    row = {'allowed': 'put-empty', 'item': 'a.txt', 'contents': ['a\n']}
    ok = subprocess.CompletedProcess([], 0, b'', b'')
    sha = hashlib.sha256(b'a\n').hexdigest()
    kept = {'home': {'Trash/files/a.txt': {'type': 'file', 'sha256': sha},
                     'Trash/info/a.txt.trashinfo': {'type': 'file', 'text': '[Trash Info]\nPath=/h/a.txt\n'}}, 'xdev': {}}
    orphan = {'home': {'Trash/files/a.txt': {'type': 'file', 'sha256': sha}}, 'xdev': {}}
    checks += [
        ('outcome-kept', outcome(row, kept, [ok, ok]) is None),
        ('outcome-emptied', outcome(row, {'home': {}, 'xdev': {}}, [ok, ok]) is None),
        ('outcome-orphan', outcome(row, orphan, [ok, ok]) is not None),
        ('outcome-left', outcome(row, {'home': {'a.txt': {'type': 'file', 'sha256': sha}}, 'xdev': {}}, [ok, ok]) is not None),
        ('outcome-lost-restore', outcome({'allowed': 'restore-twice-other-fs', 'item': 'x', 'contents': ['a\n']},
                                         {'home': {}, 'xdev': {}}, [ok, ok]) is not None),
        ('outcome-restored', outcome({'allowed': 'restore-twice-other-fs', 'item': 'x', 'contents': ['a\n']},
                                     {'home': {}, 'xdev': {'x': {'type': 'file', 'sha256': sha}}},
                                     [ok, subprocess.CompletedProcess([], 1, b'', b'')]) is None),
        ('draw', draw(random.Random('s'), {}) == draw(random.Random('s'), {})),
    ]
    for name, good_one in checks:
        print('%s selftest-%s' % ('PASS' if good_one else 'FAIL', name))
        fails += 0 if good_one else 1
    print('SUMMARY harden-selftest failed=%d' % fails)
    return 1 if fails else 0


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest='cmd', required=True)
    for name in ('cuts', 'capture', 'stress', 'rm-witness'):
        s = sub.add_parser(name)
        s.add_argument('--rows', required=True)
        s.add_argument('--only')
        if name != 'rm-witness':
            s.add_argument('--candidate', required=True)
        if name == 'capture':
            s.add_argument('--out', required=True)
        if name == 'stress':
            s.add_argument('--rounds', type=int, required=True)
            s.add_argument('--seed', required=True)
    sub.add_parser('selftest')
    a = p.parse_args()
    return {'cuts': cmd_cuts, 'capture': cmd_capture, 'stress': cmd_stress, 'rm-witness': cmd_rm_witness,
            'selftest': cmd_selftest}[a.cmd](a)


if __name__ == '__main__':
    sys.exit(main())
