# tb01: `trash` itself (T1)

T1 writes `trash FILE…`: a static program for PAX and Linux x86-64 that moves
each operand into `~/Trash` as the FreeDesktop.org Trash specification lays a
trash out, and as trash-cli's `trash-put` (the oracle) does, with the info file
created first and exclusively, collisions named as the oracle names them, and
an item on another file system copied into the home trash, verified, then
removed.

## Prediction (written before any change)

Sources for this section: tb00's census note and goldens (what `trash-put`
writes, measured), the Trash specification 1.0, `rename(2)`, `open(2)`,
`lstat(2)`, `readlink(2)`, `symlink(2)`, `utimensat(2)` and `chown(2)`,
trash-cli's `--help` (as tb00 captured it), boreutils' `rm`, and the wolf
specification's OS chapter at 0.2.38. Nothing below has been run.

### The program

- **Layout.** `src/trash.lu` is the entry; the code the companions (T2) will
  share lives in one module beside it, `src/can/`: the trash's location and
  directories, the info file, percent-encoding, the deletion date, the copy
  across file systems, and the argument parser. Unit programs
  (`src/*_test.lu`) hold the pure parts (encoding, collision names, the
  parser, quoting, the date, the space estimate) by name.
- **The write order.** For each operand: `lstat` it (never following a final
  link), refuse it if it is `.`, `..`, `/`, the trash, inside the trash, or
  holds the trash; then create `~/Trash`, `files/` and `info/` (`0700`) if
  missing; then reserve a name by creating `info/NAME.trashinfo` with
  `O_EXCL` (`fs_open_perm(p, 4, 0o600)`), trying `NAME`, `NAME_1`, `NAME_2`,
  … on `exists`; then write the three lines; then rename the operand to
  `files/NAME`. A reserved name whose `files/NAME` is already taken (an item
  with no info file) is given up and the next one tried, so a rename never
  replaces an earlier item. If the rename fails other than `cross_device`,
  the info file is removed and the operand reported and left in place.
- **Across file systems.** On `cross_device`: the source tree's size is
  estimated (each file rounded up to the home volume's fragment, one
  fragment per directory and link) and held to `fs_statfs`'s available
  space; short of it, the operand is refused by name before anything is
  copied. Otherwise the tree is copied into `files/NAME` (files by
  `fs_copy_chunk`, links as links, fifos as fifos, directories made `0700`
  while they fill), owner then mode set on each entry, verified against the
  source (kinds, modes, bytes, link targets, the names in every directory),
  the times set last (atime and mtime to the nanosecond, directories after
  their contents), and only then the source removed, walked by held
  directory so a swapped link cannot redirect a removal. A failure before
  the source is touched removes the partial copy and the info file and
  leaves the source whole. A socket or a device in the tree, a name that is
  not UTF-8 inside it, or a link target that is not UTF-8 is such a failure,
  by name.
- **Flags**, as trash-cli's parser takes them: `-f`/`--force`,
  `-i`/`--interactive`, `-r`/`-R`/`--recursive` and `-d`/`--directory`
  (accepted, nothing more), `-v`/`--verbose`, `-h`/`--help`, `--version`,
  `--`; combined short flags; options after operands; unambiguous prefixes
  of the long names. `--trash-dir` and `--print-completion` are not taken:
  this trash is always `~/Trash`.
- **Messages** are the oracle's bytes where it fixes them:
  `trash: cannot trash non existent 'NAME'`, `trash: cannot trash directory
  '.'`, exit 74 when any operand failed; `-f` silent; the usage lines and
  exit 2; `-v`'s `trash: 'NAME' trashed in ~/Trash` on standard error; `-i`'s
  `trash: trash regular file 'NAME'? ` on standard output. `--help` and
  `--version` are in this program's own words; their rows hold the exit
  status and which stream carries the text.
- **`DeletionDate`** is `std.time.local` of the wall clock, formatted
  `%Y-%m-%dT%H:%M:%S`; when no zone data answers, UTC. **`Path=`** is the
  operand made absolute against the working directory, `.` and `..` removed
  and repeated and trailing slashes dropped, without resolving any link, and
  percent-encoded keeping RFC 3986's unreserved set and `/`, upper-case hex.
- **Names that are not UTF-8** are read with `env_args_bytes` and refused by
  name, the message naming wolf-lang#687; nothing is touched.

### The new rows, and what the oracle will answer

Each is a row of `tests/oracle/rows.json`, recorded on the oracle as a golden
and compared with the candidate.

| row | predicted oracle answer |
|---|---|
| `-R` on a directory | trashed, silent, exit 0 |
| `-f` on a present file | trashed, silent, exit 0 |
| `-f` with no operand | the usage lines and `Please specify the files to trash.`, exit 2 |
| `--help`, `--version` | text on standard output, exit 0 |
| `/` | exit 74 and a line naming `'/'`; nothing changes |
| `sub/.` and `sub/..` | `cannot trash directory`, exit 74, like `.` and `..` |
| `-i` on a directory, a link and an empty file | `trash directory 'd'? `, `trash symbolic link 'l'? `, `trash regular empty file 'e'? ` |
| `-i` answered `Y`, `yes`, ` y` | `Y` and `yes` are yes; ` y` is no |
| `-fi` and `-if` | both flags hold: the question is asked, a missing operand is silent |
| `--force`, `--verbose`, `--interactive`, `--recursive`, `--directory` | taken as the short flags |
| `--verb` | taken as `--verbose` |
| `--v` | ambiguous, exit 2 |
| `-vx` | refused, exit 2, nothing trashed |
| an option after an operand (`trash a.txt -v`) | the option holds |
| a missing name holding `'` | quoted plainly: `'it's'` |
| a file named `-1` | trashed as a name (the parser takes a negative number as an operand) |
| a directory named with a slash (`d/`) | `d` trashed, `Path=` without the slash |
| an operand through a linked directory (`ld/x`, `ld -> d`) | `Path=` keeps `ld`, unresolved |
| an item already in `files/` with no info file | trash-cli takes the name and its rename replaces the item (this row diverges: here the item is kept and the new one is `a.txt_1`) |
| an info file with no item | the new item is `a.txt_1` |
| a 250-byte name (its info name is past the limit) | refused, exit 74 |
| the home itself, which holds the trash | refused, exit 74, nothing changes |
| the mount point of the second file system | refused, exit 74 |

### The rows with no oracle (expected captures)

`tests/oracle/expected/ROW.json`, written by hand from the design above
before the program, and the candidate held to them:

- across file systems on Linux (the image's root file system to a tmpfs): a
  file; a tree with modes, a link, a nested directory, an owner other than
  the runner's and times with nanoseconds, every time kept; a link as the
  operand; a collision; `-v`;
- the space refusal: the home on a small tmpfs, the item larger than its
  free space: refused by name, the source whole;
- a failure mid-copy, twice: a socket inside the tree, and a name that is
  not UTF-8 inside it: the partial copy and the info file gone, the source
  whole, exit 74;
- the trash itself and items inside it, refused by name; a name that is not
  UTF-8, refused by name (the oracle trashes it; this program cannot reach
  it until wolf-lang#687);
- `--trash-dir`, refused as an option this program does not take.

### PAX under KVM

The static `trash` on PAX's console, through pelt, in the census's image,
with a small static fixture program that makes files and prints a tree's
snapshot. Predicted: on the ext2 home a file, a tree, a link and a
three-deep collision trash exactly as on Linux; from `/tmp` (the in-memory
tree) a file and a tree are copied into `/home/pax/Trash` with modes and
nanosecond times kept (PAX's ext2 keeps nanoseconds, measured by tb00) and the
source removed; an item larger than the home's free space is refused by name;
a tree in `/tmp` holding a name that is not UTF-8 fails mid-copy and leaves
the source whole; `DeletionDate` is UTC, the zone the image carries.

### Red first, and the plant

- Against the stub (`trash` refuses everything with one line of its own,
  exit 74, touches nothing): every compared row red by name. A row whose
  oracle answer leaves the tree alone (no operand, an unknown option, `.`,
  `..`, a missing operand) is red by its message or its exit status, since
  the stub's one line is no line of the oracle's. Every expected-capture
  row is red; the PAX rows are red.
- With the program: every compared row green, every expected capture equal,
  every PAX row green; tb00's census and goldens unchanged and green.
- The plant (`tb01-plant-*`, one hunk on the green head): the rename moved
  before the info file's exclusive create, so the second trashing of
  `a.txt` replaces `files/a.txt` and `put-collision` goes red by name
  (`files/a.txt_1` missing).

## The oracle, measured on T1's rows

75 rows joined tb00's 43 (118 in all), each recorded on trash-cli 0.26.9.29 as
a golden (`tests/oracle/golden/`). tb00's goldens are unchanged, but for
three of its diverging rows that read a volume trash, re-recorded when the
scratch home moved to a file system of its own (below).

**Prediction against result.**

| row | predicted | measured |
|---|---|---|
| `-R`; `-f` on a present file; `-f` with no operand | trashed silently; the usage error, exit 2 | held |
| `--help`, `--version` | text on standard output, exit 0 | held (`--help` also wins over an unknown option met before it) |
| `/` | exit 74, a line naming `'/'` | held, in the oracle's long form (each trash it knows, each failure) |
| `sub/.`, `sub/..` | like `.` and `..` | **wrong**: `cannot trash '.' directory 'sub/.'`, a message of its own; and `./` and `deeper/.//` are not refused at all (the first fails to move, the second trashes `deeper`) |
| `-i` kinds | `directory`, `symbolic link`, `regular empty file` | held; a fifo or a socket is an `entry` |
| `-i` answers | `Y` and `yes` yes, ` y` no | held; an empty line is no |
| `-fi`, `-if` | both flags hold | **wrong**: the last wins, as in rm |
| long flags, `--verb`, `--v`, `-vx` | as the short ones; ambiguous; refused | held; `-xv` names `-xv`, `-vxq` names `-xq`, `--verbose=1` is `ignored explicit argument '1'` |
| an option after an operand | it holds | held |
| a name holding `'` | plain quotes | held |
| a file named `-1` | an operand | **wrong**: `refusing to treat existing file -1 as an option (use './-1' or a '--' separator)`, exit 2, for any word before `--` that looks like an option and names something there; a missing `-1` is an operand |
| `d/` | `d` trashed | held |
| `ld/x`, `ld -> d` | `Path=` keeps `ld` | **wrong**: `Path=` is the parent's real path (`…/d/x`); and `lq/../x` is read lexically before anything is done, so it trashes `./x`, not the `x` the host would reach |
| an item in `files/` with no info file | its rename replaces it | **wrong**: the new item is `a.txt_1` |
| an info file with no item | `a.txt_1` | held |
| a 250-byte name | refused | **wrong**: shortened. A try whose info file name would pass 255 bytes is skipped, and every later try keeps the name as long, in code points, as the original: `NAME[:len-len(suffix)-10] + suffix`. `NAME_1` is still tried whole first (a 244-byte name's second trashing is `…_2`) |
| the home, which holds the trash | refused | **wrong**: trash-cli moves the whole home into the volume trash at its top |
| the mount point of `/xdev` | refused | held, in the long form |
| `-i` at the end of input | (not predicted) | trash-cli crashes (exit 1, a redacted traceback) |
| `-i` on a dangling link | (not predicted) | no question is asked, and the link is trashed |

**A path that begins with two slashes.** Given `trash //`, trash-cli copies
the whole root file system into its trash. Python keeps exactly two leading
slashes as they are, so the oracle's guard against moving `/` into itself does
not see `/`, the move fails, and its fallback copies the tree. `/` and `///` are
refused. It was seen once in the oracle's scratch container, and stopped
before anything was removed. Since then the harness refuses to hand the oracle
any path that begins with exactly two slashes (`oracle-guard`, with a selftest
row of its own), and every write a row can make is capped: the container's
root is read-only, and the scratch home (`/tmp`), `/xdev` and `/small` are tmpfs
of 32, 32 and 2 MiB, which `tools/oracle.py` checks before it runs the oracle.
The move put the home on its own volume. Nine diverging rows' goldens changed,
each by that alone: the volume trash is `/tmp/.Trash-0` with relative paths,
the refusal of `/` is the short `because deleting it is not allowed`, and
`--trash-dir` names `/tmp` as the trash's volume. The other 109 goldens are
unchanged byte for byte.

## What T1 does

- **Layout.** `src/trash.lu` is the command; `src/can/` is the module T2 will
  share: `text.lu` (words as messages show them), `paths.lu` (lexical paths,
  `Path=`'s encoding), `names.lu` (collision names, the info text, the
  deletion date), `args.lu` (the parser), `put.lu` (one operand), `copy.lu`
  (across file systems).
- **One operand, in order.**
  1. A name that is not UTF-8 is refused by name (`wolf-lang#687`).
  2. The oracle's refusals by spelling (`.`, `..`, `X/.`, `X/..`), then the
     same once trailing slashes go (`./`, `deeper/.//`).
  3. `lstat` of the operand as given: missing is `cannot trash non existent`
     (silent under `-f`).
  4. The operand read lexically against the working directory; `/` refused.
  5. The trash's real path against the operand's (its parent resolved): the
     trash itself, anything inside it, and a directory that holds it refused.
  6. A directory on another device than its parent (a mount point) refused.
  7. `-i`: the question, when the path resolves (not for a dangling link).
  8. `~/Trash`, `files/`, `info/` made `0700` if missing.
  9. The name reserved: `info/NAME.trashinfo` created with `O_EXCL`
     (`0600`), tries named as the oracle names them; a name whose item is
     already in `files/` is given back and the next one tried.
  10. The three lines written, then `rename(2)` into `files/`. A failure
      other than `EXDEV` removes the info file and reports the operand.
  11. On `EXDEV`: the tree surveyed (its size, rounded to the home volume's
      fragment, against `fs_statfs`'s available bytes, and every entry's
      record kept as it was read), then four passes: copy (private modes),
      verify (kinds, bytes, link targets, the names in every directory),
      finish (owner, then mode, read back, then atime and mtime to the
      nanosecond, inner entries first), and only then the source removed by
      held directory, only what was copied. A failure before the last pass
      removes the copy and the info file; the source is whole.
- **What the copy cannot do, by name:** a socket or a device; a name or a
  link target that is not UTF-8 (`wolf-lang#687`). Hard links inside a tree
  are copied as separate files. When the host refuses an owner, the set-id
  bits go with it, as `cp -p` drops them. Every byte is read twice, by the
  verification. Nothing is synced (a power cut is T3's).
- **No rename that never replaces** (`wolf-lang#706`): the reservation of the
  info file, and the check of `files/` under it, keep two runs off one name.

## The rows

- **Oracle rows** (`tests/oracle/rows.json`, 118): 86 compared with trash-cli
  and 20 diverging, held to `tests/oracle/expected/` (written by hand in
  `tools/expected.py` before the program); 12 left out by name, each needing
  a T2 command.
- **Unit rows** (`src/can_test.lu`, 76, listed in `tests/unit-rows.json`):
  the module's pure parts, including the parser on every shape the oracle
  answered.
- **PAX rows** (`tests/pax/rows.json`, 14, `tools/pax-rows.py`): one boot of
  PAX's console kernel under KVM, the home on its ext2 disk and the second
  store its in-memory `/tmp`, through pelt; `rowtool` (a static wolf
  program) makes each fixture and prints what the harness needs to build the
  oracle harness's capture, normalised and compared by the same code, held
  to `tests/pax/expected/`.

**Red first.**
- The stub (`f146503`) against the compared and diverging rows: 106 of 106 red,
  at `c29c3fa` and again at `b1ea07f` with the scratch home capped.
- The first program (`6c0fdf6`): 102 of 106. Red by name were
  `put-long-name-utf8`, `put-long-name-utf8-short` and `put-long-collision-utf8`
  (a trap: a trailing slash looked for by slicing the last byte of `é`, fixed
  in `061372d`), and `put-other-fs-tree` (two directories' access times, lost
  to the survey's listing, fixed in `f63b1da`).
- The PAX rows against the stub, built static from `f146503`: 14 of 14 red at
  `400b6d2`. With the program: 9 of 14, the five reds a name that is not UTF-8
  left behind by an earlier row, since no wolf call can remove it (the C
  fixture removes it since `2729d7d`); then 14 of 14 at `0df3a87`.

## Where the oracle and rm part, and what T1 follows

The oracle's bytes win where it fixes them; elsewhere, rm and boreutils'
`rm`.

- Followed from the oracle: the last of `-f` and `-i` wins (as rm too);
  `-i` asks nothing of a dangling link (R-tb01-1); `..` is read lexically
  and `Path=` takes the parent's real path (R-tb01-2); an option-shaped
  word that names a file is refused; long names are shortened.
- Followed from rm, where the oracle has no answer: the end of input under
  `-i` is a no, exit 0 (the oracle crashes; R-tb01-5).
- Refused here, where the oracle does something else (R-tb01-3): `/` in every
  spelling, `./` and the like, the trash and what is in it, a directory that
  holds the trash, a mount point.
- Not taken (R-tb01-4): `--trash-dir` and `--print-completion`, refused as
  unrecognised options.
- In this program's own words (R-tb01-6): `--help` and `--version`.

## Gaps met

| gap | filed | what T1 does |
|---|---|---|
| A path that is not UTF-8 cannot be named | wolf-lang#687 | refuses such an operand by name; a copy across file systems meeting one inside a tree, or as a link's target, fails by name and leaves the source whole |
| Every rename replaces | wolf-lang#706 | the exclusive create of the info file reserves the name, and `files/` is checked under it |
| A `copy` of a map's list value is not yet compiled at 0.2.38 ("cannot compile this yet") | not filed (R-tb01-8) | the survey's records live in a list behind a name-to-index map |
| A non-UTF-8 name cannot be removed by wolf | wolf-lang#687 | the PAX rows remove theirs with the C fixture |

## SKIPs

None. A row that cannot run fails by name; the 12 rows that need T2's
commands are listed as `OUT` by name and counted apart.

## Recommendations

R-tb01-1 to R-tb01-7 were each ruled A, as recommended, and are
implemented.

- R-tb01-1: `-i` matches the oracle and asks nothing of a dangling link.
- R-tb01-2: operands are read lexically; `Path=` is the parent's real path.
- R-tb01-3: `/` in every spelling, `./` and its kin, the trash and anything in
  it, a directory holding it, and a mount point are refused by name.
- R-tb01-4: `--trash-dir` and `--print-completion` are unrecognised options.
- R-tb01-5: the end of input under `-i` is a no, exit 0.
- R-tb01-6: `--help` and `--version` in this program's own words, compared by
  exit status and stream.
- R-tb01-7: an entry the copy cannot make is found at copy time; the partial
  copy is removed and the source left whole.
- R-tb01-8 (open): file the 0.2.38 refusal of `copy` on a map's list value
  upstream with its four-line witness. (A) File it as a wolf-lang issue,
  recommended; (B) leave the workaround's comment as the only record.
- R-tb01-9 (open): the footprint. (A) `cross-cutting`, recommended:
  `tools/in-container`, which CI runs, changed its mounts. (B) `module`: no
  path the audit classes as CI changed.

## Done-when

- [x] The prediction committed before any change (`73ccd96`), and scored
  above.
- [x] `trash FILE…`, static, for PAX and Linux x86-64: files, directories and
  symbolic links (the link, never its target), the info file created with
  `O_EXCL` before the rename and removed when the rename fails.
- [x] Collisions named as the oracle names them, three deep, by the exclusive
  create; long names shortened as it shortens them.
- [x] Across file systems: the space refused by name before any copy;
  modes, owner, times to the nanosecond and links kept; the copy verified,
  then the source removed; a failure part-way leaves the source whole.
- [x] The flags as trash-cli takes them, its messages, prompts and exit
  codes; `--help` and `--version` in this program's own words.
- [x] The refusals by name: `.`, `..`, `/`, the trash and anything in it, a
  missing operand without `-f`, and a name that is not UTF-8 (wolf-lang#687).
- [x] `DeletionDate` in local time, UTC when no zone answers; `Path=` as the
  oracle encodes it.
- [x] tb00's census and oracle rows still green; the new oracle rows red
  against the stub first; the expected-capture rows and the PAX rows red
  first; every row green at the head.
- [x] One plant, `tb01-plant-rename-first`: the rename before the info file's
  exclusive create, red by name at `put-collision`.
- [x] The records behind both of a lane host's locks, the Linux gate and the
  PAX legs in one gauntlet, and the plant's record, both verified.
