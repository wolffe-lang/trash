"""An index failure must not fall through to package installation."""
import os
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parent.parent
tmp = root / 'target' / 'tmp'
tmp.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(dir=tmp) as directory:
    directory = Path(directory)
    apt = directory / 'apt-get'
    apt.write_text('''#!/bin/sh
case " $* " in
  *" APT::Update::Error-Mode=any "*) exit 100 ;;
  *) exit 0 ;;
esac
''')
    apt.chmod(0o755)
    env = dict(os.environ, PATH=str(directory) + os.pathsep + os.environ['PATH'])
    result = subprocess.run(['sh', str(root / 'ci/snapshot-update.sh'), '20261107T000000Z'],
                            env=env, capture_output=True, text=True)
    assert result.returncode != 0, 'snapshot index failure was ignored'
    assert 'FAIL snapshot-index' in result.stderr, result.stderr
    apt.write_text('#!/bin/sh\nexit 0\n')
    result = subprocess.run(['sh', str(root / 'ci/snapshot-update.sh'), '20261107T000000Z'],
                            env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
print('PASS snapshot-index failure stops the build and success continues')
