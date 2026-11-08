#!/usr/bin/env python3
"""The census on PAX under KVM: one image, one boot, the same probes and driver.

  census-pax.py run --pax PAXTREE --kernel ELF --inputs DIR --census DIR
                    --disk HOME.img --out DIR [--timeout S] [--memory M]
  census-pax.py selftest

The image is PAX's console kernel with an initramfs holding pelt as /bin/sh,
boreutils' printf and mkdir, the static census programs (DIR/stripped from
`census.py build --static`) under /census/bin, census/run.sh, the zone data
PAX's distribution carries (UTC, from its tools/mkzone), and PAX's own
user/fstab, so the ext2 disk a copy of HOME.img gives QEMU
(tools/mkdisk --home's, PAX's own home disk) is mounted at /home. init runs
census/run.sh with SAME on that disk (/home/pax/census) and OTHER in the
in-memory tree (/tmp/census): two stores, as a PAX install has them. The
console is split into the record `census.py verdict --platform pax` reads,
with the kernel's own refusal lines (`user: ... syscall N: ...`) kept beside
it as evidence.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
MARKER = 'halt|PANIC .*'


def load_census():
    spec = importlib.util.spec_from_file_location('census', ROOT / 'tools/census.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def serial_norm(text):
    text = re.sub(r'\x1b\[[0-9;?=<>]*[A-Za-z]', '', text)
    text = re.sub(r'\x1b[()][A-Za-z0-9]', '', text)
    text = re.sub(r'\x1b[c78DEHM=>]', '', text)
    return text.replace('\r', '')


def kernel_lines(text):
    """The kernel's lines a row may need as evidence: refusals and unknown calls."""
    keep = re.compile(r'^(user: .*(syscall|refused|killed).*|fstab: .*|ext2: .*|PANIC .*)$')
    return [l for l in serial_norm(text).split('\n') if keep.match(l)]


def run(cmd, **kw):
    print('RUN ' + ' '.join(map(str, cmd)), flush=True)
    return subprocess.run([str(c) for c in cmd], **kw)


def cmd_run(a):
    pax, out = Path(a.pax), Path(a.out)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    inputs = Path(a.inputs)
    bins = Path(a.census) / 'stripped'
    files = [('/bin/sh', inputs / 'pelt/pelt', 755), ('/bin/printf', inputs / 'bore/printf', 755),
             ('/bin/mkdir', inputs / 'bore/mkdir', 755), ('/census/run.sh', ROOT / 'census/run.sh', 755),
             ('/etc/fstab', pax / 'user/fstab', 644)]
    progs = sorted(p.name for p in bins.iterdir() if p.is_file())
    if not progs:
        raise SystemExit('FAIL census-pax-inputs: no programs in %s' % bins)
    for name in progs:
        files.append(('/census/bin/' + name, bins / name, 755))
    # The zone data PAX's distribution root carries (tools/mkzone): UTC at
    # /etc/localtime and in the zone database, so the image answers local time
    # as an installed PAX does.
    zone = out / 'UTC'
    r = run([pax / 'tools/mkzone', zone], capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit('FAIL census-pax-image mkzone: ' + r.stderr[-400:])
    files += [('/etc/localtime', zone, 644), ('/usr/share/zoneinfo/UTC', zone, 644)]
    script = out / 'census.sh'
    script.write_text('mkdir -p /home/pax/census/same /tmp/census/other\n'
                      '/bin/sh /census/run.sh /census/bin /home/pax/census/same /tmp/census/other\n')
    files.append(('/etc/census.sh', script, 644))
    run_line = out / 'pax-run'
    run_line.write_text('/bin/sh /etc/census.sh\n')
    files.append(('/etc/pax-run', run_line, 644))
    args = ['/tmp/:1777', '/home/:755'] + ['%s=%s:%s' % (d, s, m) for d, s, m in files]
    cpio = out / 'census.cpio'
    r = run([pax / 'tools/mkinitramfs', cpio] + args, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stdout[-2000:], r.stderr[-2000:])
        raise SystemExit('FAIL census-pax-image mkinitramfs')
    iso = out / 'census.iso'
    r = run([pax / 'tools/mkimage', '--conf', pax / 'boot/limine-initramfs.conf', '--add', cpio, 'initramfs.cpio',
             a.kernel, iso], capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stdout[-2000:], r.stderr[-2000:])
        raise SystemExit('FAIL census-pax-image mkimage')
    disk = out / 'home.img'
    shutil.copyfile(a.disk, disk)
    print('KERNEL sha256=%s' % sha(a.kernel))
    print('DISK sha256=%s (a fresh copy)' % sha(a.disk))
    print('ISO sha256=%s programs=%d' % (sha(iso), len(progs)))
    serial = out / 'census.serial'
    cmd = [pax / 'tools/qemu-halt', '--firmware', 'bios', '--serial', serial, '--timeout', str(a.timeout),
           '--qemu', '-m', '--qemu', a.memory, '--elf', a.kernel, '--marker', MARKER,
           '--qemu', '-drive', '--qemu', 'file=%s,if=none,id=d0,format=raw' % disk,
           '--qemu', '-device', '--qemu', 'virtio-blk-pci,drive=d0', iso]
    r = run(cmd, capture_output=True, text=True)
    (out / 'qemu-halt.txt').write_text(r.stdout + r.stderr)
    print('END census-pax-qemu-halt exit=%d' % r.returncode, flush=True)
    text = serial.read_text(errors='replace') if serial.exists() else ''
    census = load_census()
    rec = census.parse_lines(serial_norm(text).split('\n'))
    rec['platform'] = 'pax'
    rec['kernel'] = kernel_lines(text)
    rec['halted'] = r.returncode == 0
    (out / 'pax.json').write_text(json.dumps(rec, indent=1, sort_keys=True) + '\n')
    for line in rec['kernel']:
        print('KERNEL-LINE ' + line)
    print('PASS census-pax-boot rows=%d complete=%s halted=%s' % (len(rec['rows']), rec['complete'], rec['halted']))
    if not rec['complete'] or not rec['halted']:
        print('FAIL census-pax-boot the census did not run to its end and halt: %s'
              % (r.stdout + r.stderr)[-400:].replace('\n', ' | '))
        return 1
    return 0


def cmd_selftest(a):
    text = 'boot\r\n\x1b[0mCENSUS start\r\nROW a@x ok\r\nuser: p pid 3 syscall 999: -ENOSYS\r\nEXIT p@x 0\r\nCENSUS end\r\n'
    census = load_census()
    rec = census.parse_lines(serial_norm(text).split('\n'))
    assert rec['rows'] == {'a@x': ['ok']} and rec['complete'], rec
    assert kernel_lines(text) == ['user: p pid 3 syscall 999: -ENOSYS'], kernel_lines(text)
    print('PASS census-pax-selftest')
    return 0


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest='cmd', required=True)
    r = sub.add_parser('run')
    for k in ('pax', 'kernel', 'inputs', 'census', 'disk', 'out'):
        r.add_argument('--' + k, required=True)
    r.add_argument('--timeout', type=int, default=900)
    r.add_argument('--memory', default='3072M')
    sub.add_parser('selftest')
    a = p.parse_args()
    return {'run': cmd_run, 'selftest': cmd_selftest}[a.cmd](a)


if __name__ == '__main__':
    sys.exit(main())
