#!/usr/bin/env python3
"""trash's rows on PAX under KVM: one image, one boot, every row of
tests/pax/rows.json, each held to its expected capture in tests/pax/expected/.

  pax-rows.py run --pax PAXTREE --kernel ELF --inputs DIR --bin DIR --mkname FILE
                  --disk HOME.img --out DIR [--timeout S] [--memory M]
  pax-rows.py selftest

The image is the census's (tools/census-pax.py): PAX's console kernel with an
initramfs holding pelt as /bin/sh, boreutils' printf and mkdir, the zone data
PAX's distribution carries (UTC) and PAX's own user/fstab, so the ext2 disk a
copy of HOME.img gives QEMU is mounted at /home. Beside them: the static
`trash` and `rowtool` (DIR, stripped) and the C fixture `mkname`, which makes
the bytes that are not UTF-8.

Each row runs in a fresh home on the ext2 disk (/home/rh, HOME) with a second
store in the in-memory tree (/tmp/rows): `rowtool` makes the fixture, each
command runs through pelt with its streams in files, and `rowtool` prints its
exit status, its streams and then every entry of both trees as `PAXROW`
lines, in hex. Those lines become the capture tools/oracle.py builds on
Linux, normalised by the same code (the window is the row's own, read from
PAX's clock), and are compared with the same comparer. No row has an oracle
on PAX: the expected captures are this repository's (tools/expected.py).
"""
import argparse
import importlib.util
import json
from pathlib import Path
import re
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
ROWS = ROOT / 'tests/pax/rows.json'
EXPECTED = ROOT / 'tests/pax/expected'
HOME = '/home/rh'
XDEV = '/tmp/rows'
IO = '/tmp/io'
KINDS = {'0': 'file', '1': 'dir', '3': 'link', '4': 'fifo', '5': 'socket'}


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


oracle = load('oracle', ROOT / 'tools/oracle.py')
census_pax = load('census_pax', ROOT / 'tools/census-pax.py')


def where(p):
    """A row's path on PAX: relative to the home, or @tmp/ for the second store."""
    if p.startswith('@tmp/'):
        return XDEV + '/' + p[len('@tmp/'):]
    return HOME + ('/' + p if p else '')


def q(word):
    """One shell word for pelt: single-quoted (no row's word holds a quote)."""
    assert "'" not in word, word
    return "'%s'" % word


def hexs(s):
    return s.encode('utf-8').hex() or '-'


def script(rows):
    """The shell script PAX runs: every row, in order."""
    out = ['HOME=%s; export HOME' % HOME, 'mkdir -p %s' % IO]
    for row in rows:
        name = row['name']
        exact = '1' if row.get('times') == 'exact' else '0'
        out.append('/bin/rowtool begin %s' % name)
        out.append('/bin/rowtool clean %s %s' % (HOME, XDEV))
        n = 0
        for st in row['steps']:
            if 'make' in st:
                made, later = [], []
                for op in st['make']:
                    kind = op[0]
                    if kind == 'file':
                        p = where(op[1])
                        out.append('/bin/rowtool file %s %s %s' % (q(p), hexs(op[2]), op[3] if len(op) > 3 else '0644'))
                        made.append(p)
                    elif kind == 'dir':
                        p = where(op[1])
                        out.append('/bin/rowtool dir %s %s' % (q(p), op[2] if len(op) > 2 else '0755'))
                        made.append(p)
                    elif kind == 'link':
                        p = where(op[2])
                        out.append('/bin/rowtool link %s %s' % (q(op[1]), q(p)))
                        made.append(p)
                    elif kind == 'big':
                        p = where(op[1])
                        out.append('/bin/rowtool big %s %s' % (q(p), op[2]))
                        made.append(p)
                    elif kind == 'name':
                        out.append('/bin/mkname file %s %s' % (q(where(op[1])), op[2]))
                    elif kind == 'chown':
                        later.append('/bin/rowtool chown %s %s %s' % (q(where(op[1])), op[2], op[3]))
                    elif kind == 'times':
                        later.append('/bin/rowtool times %s %s %s %s %s' % ((q(where(op[1])),) + tuple(op[2:6])))
                    else:
                        raise ValueError('unknown make op on PAX: %r' % (op,))
                if made:
                    deepest = sorted(made, key=lambda p: -p.count('/'))
                    out.append('/bin/rowtool stamp ' + ' '.join(q(p) for p in deepest))
                out.extend(later)
                continue
            n += 1
            out.append('cd %s' % q(where(st.get('cwd', ''))))
            out.append('/bin/rowtool write %s/in %s' % (IO, hexs(st.get('stdin', ''))))
            if 'exec' in st:
                prog, label, data = st['exec']
                cmd = '/bin/mkname exec /bin/%s %s %s' % (prog, q(label), data)
            else:
                cmd = '/bin/%s %s' % (st['run'][0], ' '.join(q(w) for w in st['run'][1:]))
            out.append('%s < %s/in > %s/out 2> %s/err' % (cmd, IO, IO, IO))
            out.append('/bin/rowtool step %s %d $? %s/out %s/err' % (name, n, IO, IO))
            out.append('cd /')
        out.append('/bin/rowtool snap %s home %s %s' % (name, HOME, exact))
        out.append('/bin/rowtool snap %s xdev %s %s' % (name, XDEV, exact))
        # A name that is not UTF-8 outlives its row otherwise: no wolf call can
        # name it to remove it (wolf-lang#687), so the C fixture does.
        for st in row['steps']:
            for op in st.get('make', []):
                if op[0] == 'name':
                    out.append('/bin/mkname rm %s %s' % (q(where(op[1])), op[2]))
        out.append('/bin/rowtool end %s' % name)
    out.append('printf "PAXROWS done\\n"')
    return '\n'.join(out) + '\n'


def argv_of(st):
    if 'exec' in st:
        prog, label, data = st['exec']
        return [prog, label, oracle.show(bytes.fromhex(data))]
    return list(st['run'])


def unhex(h):
    return b'' if h == '-' else bytes.fromhex(h)


def captures(lines, rows):
    """name -> the raw capture tools/oracle.py's normalise() reads."""
    by = {r['name']: r for r in rows}
    caps = {}
    for line in lines:
        if not line.startswith('PAXROW '):
            continue
        f = line.split(' ')
        kind, name = f[1], f[2]
        if name not in by:
            continue
        c = caps.setdefault(name, {'row': name, 'tz': 'UTC', 'window': [None, None], 'steps': [],
                                   'trees': {'home': {}, 'xdev': {}}, 'ended': False})
        if kind == 'begin':
            c['window'][0] = int(f[3]) / 1000
        elif kind == 'end':
            c['window'][1] = int(f[3]) / 1000
            c['ended'] = True
        elif kind == 'step':
            runs = [st for st in by[name]['steps'] if 'make' not in st]
            st = runs[int(f[3]) - 1]
            c['steps'].append({'argv': argv_of(st), 'order': st.get('order', 'kept'), 'errors': st.get('errors', 'kept'),
                               'exit': int(f[4]),
                               'stdout': oracle.show(unhex(f[5])), 'stderr': oracle.show(unhex(f[6]))})
        elif kind == 'entry':
            tree, rel = f[3], oracle.show(unhex(f[4]))
            if f[5] == 'unreachable':
                c['trees'][tree][rel] = {'type': 'unreachable', 'mode': '?', 'mtime': 0, 'owner': '?'}
                continue
            k, mode, owner, size, ms, mns, at, ans, digest, target, text = f[5:16]
            e = {'mode': mode, 'mtime': int(ms), 'owner': owner, 'type': KINDS.get(k, 'other')}
            if by[name].get('times') == 'exact':
                e['mtime_ns'] = int(mns)
                if k != '3':
                    e.update(atime=int(at), atime_ns=int(ans))
            if k == '0':
                e.update(size=int(size), sha256=digest)
                if text != '-':
                    e['text'] = oracle.show(unhex(text))
            if k == '3':
                e['target'] = oracle.show(unhex(target))
            c['trees'][tree][rel] = e
    return caps


def verdict(caps, rows):
    fails = 0
    for row in rows:
        name = row['name']
        c = caps.get(name)
        if c is None or not c['ended'] or c['window'][0] is None:
            fails += oracle.report(name, [('pax', 'the row did not run to its end on PAX')])
            continue
        got = oracle.normalise(c)
        path = EXPECTED / (name + '.json')
        if not path.exists():
            fails += oracle.report(name, [('expected', 'a PAX row with no expected capture')])
            continue
        fails += oracle.report(name, oracle.compare(json.loads(path.read_text()), got), ' (PAX)')
    return fails


def cmd_run(a):
    pax, out = Path(a.pax), Path(a.out)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    rows = json.loads(ROWS.read_text())['rows']
    inputs, bins = Path(a.inputs), Path(a.bin)
    files = [('/bin/sh', inputs / 'pelt/pelt', 755), ('/bin/printf', inputs / 'bore/printf', 755),
             ('/bin/mkdir', inputs / 'bore/mkdir', 755), ('/bin/trash', bins / 'trash', 755),
             ('/bin/rowtool', bins / 'rowtool', 755), ('/bin/mkname', Path(a.mkname), 755),
             ('/etc/fstab', pax / 'user/fstab', 644)]
    for _, src, _ in files:
        if not Path(src).is_file():
            raise SystemExit('FAIL pax-rows-inputs: %s is missing' % src)
    zone = out / 'UTC'
    r = census_pax.run([pax / 'tools/mkzone', zone], capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit('FAIL pax-rows-image mkzone: ' + r.stderr[-400:])
    files += [('/etc/localtime', zone, 644), ('/usr/share/zoneinfo/UTC', zone, 644)]
    (out / 'rows.sh').write_text(script(rows))
    files.append(('/etc/rows.sh', out / 'rows.sh', 644))
    (out / 'pax-run').write_text('/bin/sh /etc/rows.sh\n')
    files.append(('/etc/pax-run', out / 'pax-run', 644))
    args = ['/tmp/:1777', '/home/:755'] + ['%s=%s:%s' % (d, s, m) for d, s, m in files]
    cpio = out / 'rows.cpio'
    r = census_pax.run([pax / 'tools/mkinitramfs', cpio] + args, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stdout[-2000:], r.stderr[-2000:])
        raise SystemExit('FAIL pax-rows-image mkinitramfs')
    iso = out / 'rows.iso'
    r = census_pax.run([pax / 'tools/mkimage', '--conf', pax / 'boot/limine-initramfs.conf', '--add', cpio, 'initramfs.cpio',
                        a.kernel, iso], capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stdout[-2000:], r.stderr[-2000:])
        raise SystemExit('FAIL pax-rows-image mkimage')
    disk = out / 'home.img'
    shutil.copyfile(a.disk, disk)
    print('KERNEL sha256=%s' % census_pax.sha(a.kernel))
    print('DISK sha256=%s (a fresh copy)' % census_pax.sha(a.disk))
    print('TRASH sha256=%s ROWTOOL sha256=%s MKNAME sha256=%s' % (census_pax.sha(bins / 'trash'), census_pax.sha(bins / 'rowtool'),
                                                                 census_pax.sha(a.mkname)))
    print('ISO sha256=%s rows=%d' % (census_pax.sha(iso), len(rows)))
    serial = out / 'rows.serial'
    cmd = [pax / 'tools/qemu-halt', '--firmware', 'bios', '--serial', serial, '--timeout', str(a.timeout),
           '--qemu', '-m', '--qemu', a.memory, '--elf', a.kernel, '--marker', census_pax.MARKER,
           '--qemu', '-drive', '--qemu', 'file=%s,if=none,id=d0,format=raw' % disk,
           '--qemu', '-device', '--qemu', 'virtio-blk-pci,drive=d0', iso]
    r = census_pax.run(cmd, capture_output=True, text=True)
    (out / 'qemu-halt.txt').write_text(r.stdout + r.stderr)
    print('END pax-rows-qemu-halt exit=%d' % r.returncode, flush=True)
    text = serial.read_text(errors='replace') if serial.exists() else ''
    lines = census_pax.serial_norm(text).split('\n')
    for line in census_pax.kernel_lines(text):
        if 'syscall 273' not in line and 'syscall 334' not in line:
            print('KERNEL-LINE ' + line)
    done = 'PAXROWS done' in lines
    caps = captures(lines, rows)
    (out / 'captures.json').write_text(json.dumps(caps, indent=1, sort_keys=True, ensure_ascii=False) + '\n')
    fails = verdict(caps, rows)
    if not done or r.returncode != 0:
        print('FAIL pax-rows-boot the rows did not run to their end and halt: %s'
              % (r.stdout + r.stderr)[-400:].replace('\n', ' | '))
        fails += 1
    print('SUMMARY pax-rows rows=%d failed=%d' % (len(rows), fails))
    return 1 if fails else 0


def cmd_selftest(a):
    """The parser and the comparer on a synthetic console, and the script's shape."""
    rows = [{'name': 'r1', 'times': 'exact', 'steps': [{'make': [['file', 'a.txt', 'hi\n']]}, {'run': ['trash', 'a.txt']}]}]
    s = script(rows)
    ok = "/bin/trash 'a.txt' < /tmp/io/in > /tmp/io/out 2> /tmp/io/err" in s and "/bin/rowtool stamp '/home/rh/a.txt'" in s
    info = '[Trash Info]\nPath=/home/rh/a.txt\nDeletionDate=1970-01-01T00:00:05\n'.encode().hex()
    console = ['\x1b[0mboot', 'PAXROW begin r1 4000', 'PAXROW step r1 1 0 - -',
               'PAXROW entry r1 home %s 1 0700 0:0 - 5 1 5 2 - - -' % b'Trash'.hex(),
               'PAXROW entry r1 home %s 0 0600 0:0 80 5 1 5 2 %s - %s' % (b'Trash/info/a.txt.trashinfo'.hex(), '0' * 64, info),
               'PAXROW entry r1 xdev %s unreachable' % b'b\xffc'.hex(), 'PAXROW end r1 6000']
    caps = captures(console, rows)
    n = oracle.normalise(caps['r1'])
    home = n['trees']['home']
    ok = ok and home['Trash']['mtime'] == '<in-window>' and 'mtime_ns' not in home['Trash']
    ok = ok and home['Trash/info/a.txt.trashinfo']['text'].endswith('DeletionDate=<in-window>\n')
    ok = ok and n['trees']['xdev']['b\\xffc']['type'] == 'unreachable' and n['steps'][0]['argv'] == ['trash', 'a.txt']
    bad = dict(caps['r1'])
    bad['steps'] = [dict(caps['r1']['steps'][0], exit=74)]
    ok = ok and any(f == 'step1-exit' for f, _ in oracle.compare(n, oracle.normalise(bad)))
    print(('PASS' if ok else 'FAIL') + ' pax-rows-selftest')
    return 0 if ok else 1


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest='cmd', required=True)
    r = sub.add_parser('run')
    for k in ('pax', 'kernel', 'inputs', 'bin', 'mkname', 'disk', 'out'):
        r.add_argument('--' + k, required=True)
    r.add_argument('--timeout', type=int, default=900)
    r.add_argument('--memory', default='3072M')
    sub.add_parser('selftest')
    a = p.parse_args()
    return {'run': cmd_run, 'selftest': cmd_selftest}[a.cmd](a)


if __name__ == '__main__':
    sys.exit(main())
