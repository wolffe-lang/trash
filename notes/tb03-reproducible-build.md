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

## Results

Scored against the prediction above: as predicted.

- At `7967f80` (the row, on the old builder): red by name at all five, in
  order, `repro-trash` first; every pair of digests differs
  (`FAIL repro-trash a=463ddc2f… b=878644e1…`).
- At `030d9a6` (the change): green at all five, and every other row as
  before: 258 oracle rows, the 8 cut rows, the 6 stress rows at 100 rounds
  (seed `20261108`), the unit programs and every selftest. The PAX rows are
  in the record.
- The plant, `tb03-repro-plant-absolute` (`tools/build.py` hands wolf the
  entry's absolute path again): red by name at `repro-trash`.

The five as the gate builds them (static, stripped; the oracle image's
toolchain, the pinned wolf 0.2.38), the digests a pin quotes:

| command | sha256 | bytes |
|---|---|---|
| `trash` | `f7c2cb3bae1a6188001cadcc96936e6d1ba5aa7e341cb6d27c3fd4f4bfc9d173` | 1853976 |
| `trash-list` | `589a0c19f0ea5b7447d64c380a74b20c1d67fb60596c51c4f9e9dae5b449ac94` | 1858072 |
| `trash-restore` | `6766edc011a2fe41ed15055032ebcd737a6b3f47aeb86d642a332d7be30a0d2f` | 1862168 |
| `trash-rm` | `5ec1aa88a948bfc1c10db3df5c18ecc10946c0399d08b6e1db990137af2299ff` | 1853976 |
| `trash-empty` | `e0487877dbc103315383f0c1b447a1a26fb2c83232f4b0159ad3ea7619ace274` | 1866264 |

## What the row does not hold: the linker

The row holds two paths in one image. It does not hold two images. When
`ld.lld` is on `PATH`, wolf 0.2.38 asks the cc for it (`-fuse-ld=lld`, after
any argument the cc shim adds; neither `wolf build --help` nor its manual
says so), and lld's output is not the system linker's. The oracle image has
no `ld.lld`; PAX's build image (the same Ubuntu 24.04 gcc 13.3 and binutils
2.42) has LLD 18.1.3. There, at this change, the five are each 7 to 11 KB
larger, `.comment` names the linker, and no digest is the gate's. With
`-fuse-ld=bfd` placed after wolf's own arguments, that image's five are byte
for byte the table above, at all five. That flag is not part of this change
(R-tb03-14 below).

## Gaps met

None in trash. The lld choice above is wolf's, made silently; see R-tb03-14.

## SKIPs

None. A row that cannot run fails by name.

## Recommendations

R-tb03-12 (the build's bytes a function of the commit, by this change) and
R-tb03-13 (PAX's hook's footprint, `cross-cutting`) were ruled A.

- R-tb03-14, the linker. (A) The static cc forces the system linker
  (`-fuse-ld=bfd` after wolf's arguments), held by a row that builds with
  an `ld.lld` on `PATH` that refuses to link: the gate's digests are then
  PAX's builder's. (B) As now: PAX's pin quotes its own builder's digests,
  and its note names the linker as the reason they are not the gate's.

The `trash //` divergence (tb01's note) stays a known oracle divergence.

## Done-when

- [x] The prediction committed before any change (`c660414`), and scored
  above.
- [x] The reproducibility row, red by name at all five on the old builder,
  green with the change.
- [x] One plant, `tb03-repro-plant-absolute`, red by name at `repro-trash`.
- [x] The records behind both of a lane host's locks: the Linux gate and the
  PAX rows at the head, and the plant's.
