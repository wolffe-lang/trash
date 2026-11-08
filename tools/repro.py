#!/usr/bin/env python3
"""The reproducibility row: the five commands built static from two copies of
this tree at two paths, and held to each other by digest.

  repro.py run --wolf WOLF --out DIR
  repro.py selftest

The tree's tracked shape (every file but `.git`, `target`, `.wolf-bin` and
anything the gate writes) is copied to DIR/a/trash and DIR/elsewhere/deeper/b
(two paths of different depths and names), `tools/build.py --static` builds
the commands in each, and each command's stripped binary (the copy PAX
carries) is held to its other build by sha256:

  PASS repro-NAME SHA256 BYTES     the two builds are byte for byte the same
  FAIL repro-NAME a=SHA256 b=SHA256  they differ

A binary whose bytes depend on where the tree is cannot be pinned by digest:
PAX's builder and this repository's gate build at different paths. The digests
the row prints are the gate's, the ones a pin quotes.
"""
import argparse
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
LEFT_OUT = {'.git', 'target', '.wolf-bin'}
NAMES = ('trash', 'trash-list', 'trash-restore', 'trash-rm', 'trash-empty')


def copy_tree(dst):
    """The tree, less what is never the source of a build."""
    def ignore(d, names):
        return [n for n in names if Path(d) == ROOT and n in LEFT_OUT]
    shutil.copytree(ROOT, dst, symlinks=True, ignore=ignore)


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def verdicts(a, b):
    """(lines, failures) for two builds' directories of stripped binaries."""
    lines, bad = [], 0
    for n in NAMES:
        pa, pb = Path(a) / n, Path(b) / n
        if not pa.exists() or not pb.exists():
            lines.append('FAIL repro-%s not built (a=%s b=%s)' % (n, pa.exists(), pb.exists()))
            bad += 1
            continue
        da, db = sha(pa), sha(pb)
        if da == db:
            lines.append('PASS repro-%s %s %d' % (n, da, pa.stat().st_size))
        else:
            lines.append('FAIL repro-%s a=%s b=%s' % (n, da, db))
            bad += 1
    return lines, bad


def cmd_run(a):
    out = Path(a.out).resolve()
    if out.exists():
        shutil.rmtree(out)
    trees = [out / 'a' / 'trash', out / 'elsewhere' / 'deeper' / 'b']
    for t in trees:
        copy_tree(t)
        r = subprocess.run([sys.executable, '-I', 'tools/build.py', '--wolf', a.wolf, '--out', 'target/static',
                            '--static'], cwd=t, capture_output=True, text=True)
        print(''.join('  ' + line for line in r.stdout.splitlines(True)), end='')
        if r.returncode != 0:
            print('FAIL repro-build the build in %s exited %d' % (t, r.returncode))
            print(r.stderr[-2000:])
            return 1
    lines, bad = verdicts(trees[0] / 'target/static/stripped', trees[1] / 'target/static/stripped')
    print('\n'.join(lines))
    print('SUMMARY repro commands=%d failed=%d' % (len(NAMES), bad))
    return 1 if bad else 0


def cmd_selftest(a):
    import tempfile
    fails = 0
    with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as w:
        a_dir, b_dir = Path(w) / 'a', Path(w) / 'b'
        a_dir.mkdir()
        b_dir.mkdir()
        for n in NAMES:
            (a_dir / n).write_bytes(b'same ' + n.encode())
            (b_dir / n).write_bytes(b'same ' + n.encode())
        lines, bad = verdicts(a_dir, b_dir)
        ok = bad == 0 and all(l.startswith('PASS repro-') for l in lines)
        print('%s selftest-repro-same' % ('PASS' if ok else 'FAIL'))
        fails += 0 if ok else 1
        (b_dir / 'trash-rm').write_bytes(b'other')
        lines, bad = verdicts(a_dir, b_dir)
        ok = bad == 1 and any(l.startswith('FAIL repro-trash-rm a=') for l in lines)
        print('%s selftest-repro-differs' % ('PASS' if ok else 'FAIL'))
        fails += 0 if ok else 1
        (b_dir / 'trash').unlink()
        lines, bad = verdicts(a_dir, b_dir)
        ok = bad == 2 and any(l.startswith('FAIL repro-trash not built') for l in lines)
        print('%s selftest-repro-missing' % ('PASS' if ok else 'FAIL'))
        fails += 0 if ok else 1
    print('SUMMARY repro-selftest failed=%d' % fails)
    return 1 if fails else 0


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest='cmd', required=True)
    r = sub.add_parser('run')
    r.add_argument('--wolf', required=True)
    r.add_argument('--out', required=True)
    sub.add_parser('selftest')
    a = p.parse_args()
    return {'run': cmd_run, 'selftest': cmd_selftest}[a.cmd](a)


if __name__ == '__main__':
    sys.exit(main())
