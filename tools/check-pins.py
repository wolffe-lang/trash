#!/usr/bin/env python3
"""Hold every pin to the facts it repeats, before anything is downloaded or run.

The toolchain: wolf-toolchain.toml against two independent reads of the release
metadata. The oracle: trash-oracle.toml against two reads of PyPI's, the
requirement files the image installs from, its base image, its archive
snapshot, and the manifest the image wrote (ci/oracle-manifest.lock).
"""
import json
from pathlib import Path
import re
import tomllib

ROOT = Path(__file__).resolve().parents[1]
TARGETS = ('aarch64-apple-darwin', 'x86_64-unknown-linux-gnu', 'aarch64-unknown-linux-gnu')


def hash_line(path, name):
    for line in (ROOT / path).read_text().splitlines():
        m = re.fullmatch(r'%s==(\S+) --hash=sha256:([0-9a-f]{64})' % re.escape(name), line.strip())
        if m:
            return m.group(1), m.group(2)
    raise ValueError('%s: no pinned line for %s' % (path, name))


def main():
    pins = tomllib.loads((ROOT / 'wolf-toolchain.toml').read_text())
    first = json.loads((ROOT / 'tests/pin-read-1.json').read_text())
    second = json.loads((ROOT / 'tests/pin-read-2.json').read_text())
    if first != second:
        raise ValueError('the two release metadata reads differ')
    for name in ('wolf', 'lupin'):
        pin = pins[name]
        if first[name]['tag'] != 'v' + pin['version']:
            raise ValueError('release tag differs from the pin: ' + name)
        assets = {a['name']: a for a in first[name]['assets']}
        for target in TARGETS:
            asset = assets['%s-%s-%s.tar.gz' % (name, pin['version'], target)]
            if asset['digest'] != 'sha256:' + pin[target]:
                raise ValueError('archive pin differs from the release: %s/%s' % (name, target))
    oracle = tomllib.loads((ROOT / 'trash-oracle.toml').read_text())
    tc = oracle['trash-cli']
    one = json.loads((ROOT / 'tests/oracle-pypi-read-1.json').read_text())
    two = json.loads((ROOT / 'tests/oracle-pypi-read-2.json').read_text())
    if one != two:
        raise ValueError('the two PyPI metadata reads differ')
    if one['version'] != tc['version']:
        raise ValueError('PyPI version differs from the pin')
    sdists = {f['filename']: f['sha256'] for f in one['files'] if f['packagetype'] == 'sdist'}
    if sdists.get(tc['sdist']) != tc['sdist_sha256']:
        raise ValueError('the source archive pin differs from PyPI')
    if hash_line('ci/oracle-sdist.txt', 'trash-cli') != (tc['version'], tc['sdist_sha256']):
        raise ValueError('ci/oracle-sdist.txt differs from the pin')
    if hash_line('ci/oracle-wheel.txt', 'trash-cli') != (tc['version'], tc['wheel_sha256']):
        raise ValueError('ci/oracle-wheel.txt differs from the pin')
    manifest = (ROOT / 'ci/oracle-manifest.lock').read_text().splitlines()
    if '%s  %s' % (tc['wheel_sha256'], tc['wheel']) not in manifest:
        raise ValueError('the image manifest does not hold the pinned wheel')
    if 'version %s' % tc['version'] not in manifest or 'trash-cli==%s' % tc['version'] not in manifest:
        raise ValueError('the image manifest does not name the pinned version')
    base = (ROOT / 'ci/oracle.Containerfile').read_text().splitlines()[0].removeprefix('FROM ')
    if base != oracle['container']['base']:
        raise ValueError('the image base differs from the pin')
    if (ROOT / 'ci/apt-snapshot').read_text().strip() != oracle['container']['apt_snapshot']:
        raise ValueError('the archive snapshot differs from the pin')
    print('PASS pin-metadata toolchains=2 oracle=trash-cli-%s wheel=%s' % (tc['version'], tc['wheel_sha256'][:12]))


if __name__ == '__main__':
    main()
