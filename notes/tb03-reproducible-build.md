# tb03: a reproducible build (T3, a follow-up)

The five commands' static builds depend on the path of the tree they are built
from. `tools/build.py` hands wolf each entry by its absolute path, so every
module's absolute path is written into the binary (where a runtime message
would name its source), and the link's GNU build-id, a hash over the link's
inputs, differs with it. Two checkouts of one commit at two paths give two sets
of digests, and no digest can be pinned that both this repository's gate and
PAX's builder reproduce. This follow-up makes the build's bytes a function of
the commit alone.

## Prediction (written before any change)

Sources: the build's own output (the strings of two builds of `trash-rm` at two
paths in an Ubuntu 24.04 container: every `src/can/*.lu` named by its absolute
path; with relative paths, eight bytes still differ, the `.note.gnu.build-id`
section; with relative paths and `-Wl,--build-id=none`, all five byte for byte
the same at two paths), `ld(1)`'s `--build-id` and `readelf(1)`.

### The change

- `tools/build.py` runs wolf from the tree's root and names each entry by its
  path from there (`src/trash.lu`, `tests/pax/rowtool/main.lu`), the output by
  its absolute path; its static `cc` adds `-Wl,--build-id=none`.
- No command changes what it does. The one visible difference is in a message
  the runtime prints when a program traps, which names a source file: it now
  names it from the tree's root (`src/can/args.lu`), not from `/`.

### The row, red first

- `tools/repro.py` (a gate step, `repro`, in the `candidate` and `linux`
  modes): copies the tree to two paths of different depths and names under
  `target/repro/`, builds the five static in each with `tools/build.py
  --static`, and holds each command's stripped binary to its other build by
  sha256: `PASS repro-NAME SHA256 BYTES` when they agree, `FAIL repro-NAME`
  with both digests when they differ. The printed digests are the gate's, the
  ones PAX's pin quotes.
- At `90169ed` (the row committed on the old builder): red by name at all five,
  `repro-trash` first.
- With the change: green at all five; and every other row unchanged (258
  oracle rows, 56 cuts, 6 stress rows, 198 unit rows, 19 PAX rows).

### The plant

One commit, one file, one hunk: `tools/build.py` hands wolf the entry's
absolute path again. Red by name at `repro-trash`.
