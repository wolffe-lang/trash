"""An image prefix keeps independent oracle builds apart."""
import os
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parent.parent
tmp = root / 'target' / 'tmp'
tmp.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(dir=tmp) as work:
    work = Path(work)
    engine = work / 'engine'
    capture = work / 'capture'
    engine.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$CAPTURE"\nexit 1\n')
    engine.chmod(0o755)
    env = dict(os.environ, TRASH_ENGINE=str(engine), TRASH_IMAGE_PREFIX='test-oracle', CAPTURE=str(capture))
    result = subprocess.run(['bash', str(root / 'tools/in-container')], cwd=root, env=env,
                            text=True, capture_output=True)
    assert result.returncode != 0, 'the fake engine must stop the build'
    first = capture.read_text().splitlines()[0]
    assert first.startswith('image inspect test-oracle:'), first
print('PASS oracle image prefix')
