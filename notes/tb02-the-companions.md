# tb02: the companions (T2)

T2 writes the four commands that look after the trash `trash` fills:
`trash-list`, `trash-restore`, `trash-rm PATTERN` and `trash-empty [DAYS]`,
static programs for PAX and Linux x86-64, built from the same tree as `trash`
and sharing `src/can/` with it, each held to trash-cli's command of the same
name (the oracle) byte for byte where the oracle fixes the bytes.

## Prediction (written before any change)

Sources for this section: tb00's census note and goldens (what `trash-list`
and `trash-restore` print, measured), tb01's note and goldens, the
FreeDesktop.org Trash specification 1.0 (listing, the `info/` and `files/`
pairing, restoring), `rename(2)`, `link(2)`, `mkdir(2)` and `open(2)`, the
wolf specification's OS chapter at 0.2.38, and the oracle's `--help` text and
manual pages, captured from the pinned image for this lane (the clean room
allows both). Nothing below has been run.

### What the help text and the manual pages say

- `trash-list [-h] [--print-completion …] [--version] [--volumes]
  [--trash-dirs] [--trash-dir TRASH_DIRS] [--all-users]`.
- `trash-restore [-h] [--print-completion …] [--sort {date,path,none}]
  [--version] [--overwrite] [path]`: "Restore files from given path instead of
  current directory"; the default sort is by date; `--overwrite` overwrites.
- `trash-empty [-h] [--print-completion …] [--version] [-v] [--trash-dir
  TRASH_DIR] [--all-users] [-i] [-f] [--dry-run] [days]`: `-i` asks before
  emptying, `-f` does not ask, `-v` lists what will be removed, `--dry-run`
  removes nothing.
- `trash-rm PATTERN`: "Removes all files with name 'foo'", `'*.o'` ending in
  `.o`, and `/full/path` with exactly that original location. Its `--help`
  printed nothing, exit 0: the word seems to be taken as a pattern.

### The commands

- **Layout.** Four entries beside `src/trash.lu`, each a thin `main`; what they
  share joins `src/can/`: reading the trash (`info/` in the order the host
  lists it, each info file's first `Path=` and first `DeletionDate=`,
  percent-decoding to bytes), the listing's line, the companions' argument
  parser (argparse's shapes: unambiguous long prefixes, clustered short flags,
  `--`, a value after an option, the `usage:` and `error:` lines, exit 2),
  a glob matcher, the `DAYS` cutoff, removal of an item by held directory, and
  one restore. The unit program grows rows for every pure part.
- **One trash.** Every command reads `~/Trash` alone, as `trash` writes only
  there (R-TB-1, R-TB-3). `--trash-dir`, `--trash-dirs`, `--volumes`,
  `--all-users` and `--print-completion` are unrecognised options, as
  R-tb01-4 made `--trash-dir` for `trash`; `--overwrite` is unrecognised too,
  since a restore never overwrites. `--help` and `--version` are in this
  repository's own words (R-tb01-6). The usage line of an error names only
  what each command takes, so the rows of usage errors diverge from the
  oracle by that line and are held to expected captures.
- **`trash-list`.** One line per info file, `YYYY-MM-DD hh:mm:ss PATH`, in the
  order the host lists `info/`; the path percent-decoded and written as bytes
  (a byte that is not UTF-8 goes out as it is); `????-??-?? ??:??:??` when
  `DeletionDate` is missing; a relative `Path=` read from `/`, as the oracle
  read `docs/rel` with the home on a volume of its own. An info file whose item
  is missing is listed; an item with no info file is not.
- **`trash-restore [PATH]`.** The items whose original path is PATH (made
  absolute against the working directory, default the working directory
  itself) or lies under it, sorted by `DeletionDate` (`--sort path`, `none`
  as the help says), each `%4d DATE PATH`, then `What file to restore
  [0..N]: ` on standard output, and the answer read from standard input.
  With nothing to restore, the oracle's `No files trashed from current dir
  ('…')`, exit 0.
- **The restore never replaces** (wolf-lang#706: every rename replaces). The
  destination is reserved by an exclusive creation, never checked and then
  used:
  - a file, a link, a fifo: `link(2)` of the trashed item to its original path
    (`fs_link`, which never replaces and answers `exists` when the path is
    taken; it links a symbolic link itself), then the trashed name removed;
  - a directory: `mkdir(2)` of the original path as an empty, private
    placeholder (`exists` when the path is taken), then `rename(2)` of the
    trashed directory onto it, which may replace only an empty directory: if
    another process empties the path between the two calls and fills it,
    the rename fails (`ENOTEMPTY`, `ENOTDIR`) and nothing is lost; what it can
    replace is our placeholder or another empty directory, which holds
    nothing. PAX's own tests rename a directory onto an empty one
    (`user/elf/tree.c`), so the same order serves both platforms;
  - across file systems (`cross_device` from either call): the trashed item
    is copied back with `trash`'s copy (R-TB-3): the space checked, each
    entry made exclusively (`O_EXCL`, `mkdir`, `symlink`), verified,
    finished (owner, mode, times to the nanosecond), and only then removed
    from the trash. A copy that fails part-way is removed and the trash
    keeps the item.
  - An occupied path is refused with the oracle's `Refusing to overwrite
    existing file "NAME".`, exit 1, nothing changed. Missing parents are made
    as the oracle makes them (mode `0777` less the umask). Only after the
    item is back is its info file removed.
- **`trash-rm PATTERN`.** Every item whose original path's last component
  matches PATTERN as a shell glob (`*`, `?`, `[…]`, `[!…]`), or, when PATTERN
  starts with `/`, whose whole original path matches it, is removed for good:
  the item first (by held directory, so a link inside it is never followed),
  then its info file.
- **`trash-empty [DAYS]`.** Without DAYS, every item and every info file;
  with DAYS, those whose `DeletionDate` is more than DAYS × 24 hours before
  now, read as local time. It asks only when standard input is a terminal
  (`os_isatty`), or under `-i`; `-f` never asks.
- **Orphans both ways** (T3 hardens them): an info file whose item is missing
  is listed, offered for restore (and refused, the item missing), matched by
  `trash-rm`, and removed by `trash-empty`; an item with no info file is
  never listed or restored, and `trash-empty` removes it with the rest.
- **Names wolf cannot reach** (wolf-lang#687): an info file whose name is not
  UTF-8 cannot be opened, so it is named on standard error and skipped; a
  restore whose original path is not UTF-8 is refused by name; an item whose
  tree holds such a name is surveyed before anything is removed and is left
  whole, by name.

### The rows, and what the oracle will answer

Each is a row of `tests/oracle/rows.json`, recorded on the oracle as a golden
and compared with the candidate. tb01's 12 `OUT` rows run again unchanged.

| row | predicted oracle answer |
|---|---|
| `list-empty-dirs` | `Trash/files` and `Trash/info` there but empty: nothing, exit 0 |
| `list-many` | five items (files, a directory, a link): five lines, host order |
| `list-orphans` | an info file with no item listed, an item with no info file not |
| `list-bad-dates` | a malformed, an empty, a zoned and a fractional `DeletionDate`: each `????-??-?? ??:??:??` |
| `list-non-ascii` | `é`, a space and `%` in names trashed: decoded |
| `list-percent` | `%2F`, `%25`, `%zz`, lower-case `%e9`, `%FF`: decoded byte by byte, `%zz` kept as it is, `%FF` a raw byte |
| `list-info-shapes` | a wrong header, a duplicated `Path=` (the first wins), extra lines, CRLF ends, a missing `Path=`, a name not ending `.trashinfo`, a directory named `x.trashinfo`: the header not checked; no `Path=` skipped with a message; the others ignored |
| `list-help`, `list-version` | text on standard output, exit 0 (own words) |
| `list-unknown`, `list-extra`, `list-trash-dir` | `-x`, an operand, `--trash-dir`: usage error, exit 2 (diverging by the usage line) |
| `restore-index-many` | three dated items, sorted by date, `1` restores the middle one |
| `restore-sort-ties` | equal dates: host order |
| `restore-sort-path`, `restore-sort-bad` | `--sort path` by path; `--sort bogus` a usage error, exit 2 (diverging by the usage line) |
| `restore-by-path-file`, `restore-by-path-dir` | `trash-restore PATH` offers what is at PATH or under it |
| `restore-by-path-prefix` | `a` offers `a` and `a/x`, not `ab` |
| `restore-by-path-none` | nothing under PATH: the "No files trashed" line, exit 0 |
| `restore-cwd` | from `sub`, only the items trashed from under `sub` |
| `restore-missing-parents` | `sub/deeper/x` with `sub` gone: both made, `0755` |
| `restore-parent-file` | `sub` now a file: an error naming it, exit 1, the item kept |
| `restore-occupied-dir` | refused as for a file |
| `restore-occupied-link` | a dangling link at the path: the oracle replaces it (diverging: refused here) |
| `restore-dir`, `restore-link` | a tree back whole; a link back as the link |
| `restore-input-empty`, `-eof`, `-word`, `-negative`, `-range`, `-spaces`, `-list`, `-span`, `-span-reversed`, `-zeros`, `-two-words` | empty and EOF: nothing restored, exit 0; a word, `-1`, an index past the end, `1-0`, `0 1`: an error, exit 1, nothing restored; ` 0 `, `00`: index 0; `0,1` and `0-1`: both |
| `restore-orphan-info`, `restore-orphan-item` | the first listed and its restore refused, exit 1; the second never listed |
| `restore-no-date` | listed with question marks, first in date order |
| `restore-overwrite` | `--overwrite`: diverging, an unrecognised option here |
| `restore-help`, `restore-version` | own words |
| `rm-collision` | `a.txt` and `a.txt_1` both go for `a.txt` |
| `rm-full-path` | `/…/sub/a.txt` removes that one, not `/…/a.txt` |
| `rm-question`, `rm-brackets`, `rm-negated`, `rm-star` | shell-glob meanings |
| `rm-star-slash` | `/…/*/a.txt`: `*` crosses `/` |
| `rm-dir`, `rm-inside` | a directory item removed whole; a name inside one never matched |
| `rm-no-match` | silent, exit 0 |
| `rm-no-arg`, `rm-two-args` | a usage message, nonzero |
| `rm-orphan-info`, `rm-orphan-item` | an info file with no item removed when it matches; an item with no info never matched |
| `rm-help` | `--help` taken as a pattern: silent, exit 0 |
| `empty-empty`, `empty-no-trash` | silent, exit 0; nothing made |
| `empty-days-boundary` | items 1 day ± 60 s and ± 1 h old, `trash-empty 1`: the older two go |
| `empty-days-zero` | `trash-empty 0`: everything trashed before now goes |
| `empty-days-bad` | `x`, `-1`, `1.5`: usage errors, exit 2 (diverging by the usage line) |
| `empty-f`, `empty-i-yes`, `empty-i-no` | `-f` silent; `-i` asks on standard output and takes `y` |
| `empty-tty-yes`, `empty-tty-no`, `empty-tty-f` | standard input a terminal: asked, as `-i` asks; `-f` not asked |
| `empty-v`, `empty-dry-run` | one line per item removed; the same, nothing removed |
| `empty-orphans` | both kinds removed |
| `empty-no-date` | `trash-empty 1` keeps an item with no date |
| `empty-readonly-tree` | a directory holding a `0555` directory removed whole |
| `empty-sizes`, `empty-others` | `directorysizes` and a stray file in `Trash/` kept |
| `empty-trash-dir` | `--trash-dir`: diverging, unrecognised here |
| `empty-help`, `empty-version` | own words |

### The rows with no oracle (expected captures)

Written by hand in `tools/expected.py` from the design above, before the
programs:

- **across file systems:** `restore-other-fs` (a file and a tree trashed from
  `/xdev`, which `trash` copies into `~/Trash`: copied back with modes,
  owner and times to the nanosecond, then removed from the trash) and
  `restore-other-fs-occupied` (refused, the trash keeps it);
- **the trash given:** `restore-into-trash` (an info file whose `Path=` lies
  inside `~/Trash`: refused by name, where the oracle would restore into
  the trash and leave an orphan) and `restore-trash-given` (`trash-restore
  ~/Trash`: refused by name);
- **an occupied link:** `restore-occupied-link`;
- **usage errors** in this repository's usage lines (the rows above that say
  so), and `--overwrite`, `--trash-dir` and their kin;
- **a name wolf cannot reach:** `empty-not-utf8-tree` (the tree left whole,
  by name, the rest emptied).

### The round-trip property

`roundtrip-home` and `roundtrip-other-fs`: six trees generated from a seed
(files of random bytes and modes, nested and empty directories, links
relative, absolute and dangling, a fifo, names with spaces and UTF-8, times
with nanoseconds), each trashed and then restored by path. The harness
snapshots the trees before the first command and after the last, and the two
must be equal entry by entry: kind, mode, owner, bytes, link target, and
both times to the nanosecond. On the home's file system the oracle passes
the same property, and the row is compared with it too; across file systems
the candidate alone is held, by the copy both ways.

### PAX under KVM

`pax-list`, `pax-restore`, `pax-rm`, `pax-empty` and `pax-roundtrip`: the
static commands at PAX's console through pelt, in the census's image. On the
ext2 home: the listing, a file and a directory restored (the directory onto
its placeholder), a pattern removed, the trash emptied. From `/tmp` (the
in-memory tree): a tree trashed into the ext2 trash by copy and restored to
`/tmp` by copy, every time kept.

### Red first, and the plant

- Against stubs of the four commands (each refuses everything with one line
  of its own, exit 74, touches nothing): every new compared row, every new
  expected capture, the 12 rows tb01 left out, and every new PAX row red by
  name; tb00's and tb01's other rows green and unchanged.
- With the programs: every row green.
- The plant (`tb02-plant-*`, one hunk on the green head): the restore by a
  plain `rename(2)` with no reservation, so the occupied path is replaced and
  `restore-occupied` goes red by name.

## The oracle, measured on T2's rows

128 rows joined T1's 118 (246 in all), each recorded on trash-cli 0.26.9.29 as
a golden; `oracle.py check` reproduces all 246. 24 of the new rows diverge by
design and are held to expected captures (`tools/expected.py`), five of them
because the oracle crashes there (`"oracle": "crashes"`). The goldens took four
recordings: each asked for rows the last had not thought of (the restore
prompt's grammar, the date's shapes, trash-empty's question).

**Prediction against result** (the misses and what was not foreseen; every
other row held as predicted):

| row | predicted | measured |
|---|---|---|
| `list-bad-dates`, `list-date-shapes` | a date of the wrong shape is question marks | held, and more: the date is read as `strptime` reads `%Y-%m-%dT%H:%M:%S`. The year is four digits; the other fields one or two, the day also a space and one digit; `T` in either case; the date must be real (no 29 February 2021, no second 60), and nothing may lead or trail. It is listed zero-padded: `2020-1-2T3:4:5` lists as `2020-01-02 03:04:05` |
| `list-info-shapes`, `list-info-dir` | no `Path=` skipped with a message | held: `Parse Error: INFO: Unable to parse Path.`; a directory named like an info file is `[Errno 21] Is a directory: 'INFO'`; CRLF ends are line ends |
| `list-trash-kin` | (diverging) | `--volumes` prints the host's mounts in no fixed order, so the row leaves it out |
| `restore-sort-ties` | equal dates in host order | **wrong**: by path |
| `restore-occupied-link` | the oracle replaces a dangling link | **wrong**: it refuses, as for a file; the row is compared |
| `restore-by-path-none` | the "No files trashed" line | held, and it names the working directory even when a path was given |
| `restore-input-eof` | nothing restored, exit 0 | **wrong**: a newline on standard error, exit 1 |
| `restore-input-empty` | nothing restored, exit 0 | held, saying `No files were restored` |
| `restore-input-span-reversed` | an error | **wrong**: `1-0` is an empty span, nothing restored, exit 0 |
| `restore-input-*` (the grammar) | (not foreseen past the rows) | the answer is split at `,`; a piece holding `-` is a span, and one with an empty side is `Invalid entry: open interval: PIECE`; a piece is read as Python's `int()` reads (spaces around it and `+` allowed), else `Invalid entry: not an index: PIECE`; every index is checked before anything is restored (`Invalid entry: out of range 0..N: I`, the first past the end); then the items are restored in order, and the first failure stops the rest (`0,0,1` restores `p0`, refuses the second `0`, exit 1, and leaves `p1`) |
| `restore-no-date`, `restore-bad-date`, `restore-sort-none` | listed | **the oracle crashes** (diverging) |
| `restore-other-fs` | (diverging) | the oracle's restore does not find what its `trash-put` put in the other volume's trash at all |
| `restore-into-trash` | the oracle restores into the trash | there it refused, since the path was taken; it would restore into the trash otherwise (diverging) |
| `restore-trash-given` | (diverging) | the oracle says "No files trashed" |
| `restore-info-shapes` | (not predicted) | an unreadable info file is shown as the oracle's own exception repr (`IOErrorReadingTrashInfo(path=…, error=…)`), a pathless one as `Non parsable trashinfo file: INFO, because Unable to parse Path` |
| `rm-two-args` | a usage message | **wrong**: the first pattern is used, the rest ignored |
| `rm-no-arg` | a usage message, nonzero | held: `Usage:` … `Please specify PATTERN.`, a line naming `fnmatch.fnmatchcase`, exit 8 |
| `rm-star-slash` | `*` crosses `/` | held: fnmatch's rules on the whole path |
| `rm-info-shapes`, `rm-info-dir` | (not predicted) | `trash-rm: INFO: unable to parse 'Path'`; an info directory crashes it (diverging) |
| `empty-days-negative` | a usage error | **wrong**: `-1` empties everything |
| `empty-days-dst` | DAYS × 24 h of real time | **wrong**: civil time: DAYS days back on the calendar, at the same wall-clock time, so across a change to summer time the cut moves by the hour |
| `empty-orphans-days` | (not foreseen) | an item with no info file goes under DAYS too |
| `empty-info-shapes` | (not foreseen) | without DAYS, every item an info file names (there or not), every orphan item and every `*.trashinfo` go; another name in `info/` stays; `-v` and `--dry-run` name each, `removing PATH` and `would remove PATH` |
| `empty-i-*`, `empty-tty-*` | `-i` and a terminal ask | held: `Would empty the following trash directories:`, `    - ~/Trash` spelled out, `Proceed? (y/N) `; a yes is an answer that starts with `y` or `Y`; the last of `-i` and `-f` wins; it asks even with nothing to empty; at the end of input under `-i` it crashes (diverging) |
| `empty-info-shapes-days` | (not foreseen) | the oracle crashes (diverging) |

**Red first.** Against the stubs (`00f42d1`) at `63479cc`: the oracle compare
ran all 246 rows, 140 red (the 128 new and the 12 tb01 left out) and the 106
others green; the PAX rows, 5 of 19 red (the 5 new), the 14 others green.

## What T2 does

- **Layout.** Four entries beside `src/trash.lu`, each a thin `main`:
  `src/trash-list.lu`, `src/trash-restore.lu`, `src/trash-rm.lu`,
  `src/trash-empty.lu`. What they share joins `src/can/`: `scan.lu` (the
  trash read back), `when.lu` (dates read and DAYS's cut), `glob.lu`
  (trash-rm's patterns), `opts.lu` (the command lines), `erase.lu` (an item
  removed for good), `back.lu` (one restore), `pick.lu` (restore's choices)
  and `edge.lu` (the trash's place, the bytes written), beside T1's files.
- **Reading the trash.** `info/` in the order the host lists it; each
  `*.trashinfo` read whole; its first `Path=` and first `DeletionDate=`, no
  header required, lines ended by LF, CR LF or CR; `%HH` decoded to a byte
  (either case), any other `%` kept; a relative path read from `/`
  (R-tb02-6). A date is read as `strptime` reads `%Y-%m-%dT%H:%M:%S` and must
  be real; otherwise it is none. An info file that cannot be read, one with
  no `Path=`, and one whose name is not UTF-8 are named on standard error in
  each command's own words (the oracle's where it has them) and passed over.
- **`trash-list`** writes `YYYY-MM-DD hh:mm:ss PATH` per item, the path's
  bytes as they are, question marks for no date.
- **`trash-restore [PATH]`** offers the items whose original path is PATH
  (made absolute and read lexically) or under it, by date then path (`--sort
  path`: path then date; `--sort none`: as listed), an undated item first
  (R-tb02-4); writes `%4d DATE PATH` and the prompt; reads the answer as the
  oracle reads it (pieces at `,`, spans with `-`, Python's `int()`), checks
  every index before restoring any, restores in order and stops at the first
  failure. The trash given as PATH, a PATH inside it, an original path inside
  it, and one that is not UTF-8 are refused by name (R-tb02-5, wolf-lang#687).
- **How a restore never replaces** (wolf-lang#706: every rename replaces).
  The original path is reserved by a creation that fails when the path is
  taken, never checked and then used (`can.restore`):
  - a file, a link or a fifo goes back by `link(2)` of the trashed item to
    its original path, which never replaces (`exists` when the path is
    taken), and then the trashed name is removed;
  - a directory goes back by `mkdir(2)` of the original path, an empty
    private placeholder (`exists` when taken), and then `rename(2)` of the
    trashed directory onto it. A rename can replace only an empty directory:
    if another process removes the placeholder and puts something there in
    between, the rename fails and nothing is lost; all it can replace is the
    placeholder or another empty directory. PAX renames a directory onto an
    empty one as Linux does (its own probe, `user/elf/tree.c`, renames one, and
    `pax-restore` and `pax-roundtrip` do it on the ext2 home);
  - across file systems (the item's device is not its destination's, or
    either call answers `EXDEV`), or on a file system with no hard links
    (`link` refused, R-tb02-7), `trash`'s copy brings it back: the space
    checked, every entry created exclusively (`O_EXCL`, `mkdir`, `symlink`,
    `mkfifo`), verified, given its owner, mode and times to the nanosecond,
    and only then removed from the trash (R-TB-3);
  - the oracle's own refusal of a path that is there, a dangling link
    included (`Refusing to overwrite existing file "NAME".`), is made first,
    so an occupied path changes nothing; missing directories above are made
    as Python's `makedirs` makes them (mode `0777` less the umask, the
    failing call's `[Errno N]` line otherwise); the info file goes last.
- **`trash-rm PATTERN`** takes the first word as the pattern, whatever it
  looks like, and matches it by fnmatch's rules (`*` crosses `/`) against the
  original path's last component, or the whole path when the pattern starts
  with `/`; each match is removed by held directory (`fs_open_at` with the
  no-follow bit, a directory made writable through its handle), then its info
  file.
- **`trash-empty [DAYS]`** asks only when standard input is a terminal or
  the last of `-i`/`-f` is `-i`, and takes an answer that starts with `y` or
  `Y` (the end of input is a no, R-tb02-4). Without DAYS it removes every item
  an info file names (there or not), every orphan item and every
  `*.trashinfo`; with DAYS, the items whose date is at or before the cut,
  their info files, and every orphan item. The cut is DAYS days back on the
  calendar at the same local wall-clock time, as the oracle counts. `-v`
  says `removing PATH`, `--dry-run` says `would remove PATH`.
- **Orphans, both ways.** An info file whose item is missing is listed,
  offered for restore (and its restore answers the oracle's `[Errno 2]` line
  for the missing item), matched by trash-rm and removed by trash-empty. An
  item with no info file is never listed, offered or matched, and
  trash-empty removes it, with DAYS or without.
- **What wolf cannot reach yet** (wolf-lang#687): an info file whose name is
  not UTF-8 is named and skipped; a restore whose path is not UTF-8 is
  refused; an item whose tree holds such a name is surveyed before anything
  is removed and left whole, by name.

## The rows

- **Oracle rows** (`tests/oracle/rows.json`, 246): 202 compared with
  trash-cli and 44 diverging, held to `tests/oracle/expected/` (written by
  hand in `tools/expected.py` before the programs). No row is left out.
- **Unit rows** (`src/can_test.lu`, 180, listed in `tests/unit-rows.json`):
  104 new, for the info file read, the date read and cut, the calendar
  arithmetic, the patterns, Python's `int()`, the command lines, the quoting
  and restore's answers.
- **PAX rows** (`tests/pax/rows.json`, 19): the 5 new ones list, restore (a
  file, a directory onto its placeholder, a link, then an occupied path
  refused), remove by pattern, empty with DAYS and then all, and a round trip
  of a tree from the in-memory `/tmp` (copied both ways) and one on the ext2
  home (renamed both ways), every time kept to the nanosecond.
- **The round-trip property** (`roundtrip-home`, `roundtrip-other-fs`): six
  generated trees each way; the trees are snapshotted, without moving a time,
  before the first command and held to that after the last.

**Red first, then green.** Against the stubs, 140 of the 246 oracle rows
and 5 of the 19 PAX rows were red, exactly the new and the left-out ones
(above). The first build of the programs that compiled passed every
companion row, and with the unit rows every one of the 246 oracle rows, the
180 unit rows and the 19 PAX rows; the work was then committed file by file,
the tree unchanged (`73f0092`).

## Gaps met

| gap | filed | what T2 does |
|---|---|---|
| Every rename replaces | wolf-lang#706 | a restore reserves its path by `link(2)` or an empty directory (above) |
| A path that is not UTF-8 cannot be named | wolf-lang#687 | named and skipped, refused, or left whole, by name (above) |

No new gap was found: every call the companions need answers on PAX as on
Linux.

## SKIPs

None. A row that cannot run fails by name.

## Recommendations

R-tb02-1 to R-tb02-8 were ruled A (the user's word, about 14:20Z), and each is
implemented as A. R-tb02-9 was ruled A (`cross-cutting`) at the merge.

- R-tb02-1: the options that choose another trash (`--trash-dir`,
  `--trash-dirs`, `--volumes`, `--all-users`), `--print-completion` and
  `--overwrite` are unrecognised options, exit 2, as R-tb01-4 made
  `--trash-dir` for `trash`. (B: take `--trash-dirs` and `--volumes` and
  print `~/Trash`; take `--overwrite` and ignore it with a warning.)
- R-tb02-2: each command's usage line names only what it takes; the rows of
  usage errors diverge by that line. (B: the oracle's usage verbatim, naming
  options that are refused.)
- R-tb02-3: a line where the oracle's output names its own implementation
  (trash-rm's `fnmatch.fnmatchcase` line, restore's exception repr for an
  unreadable info file) is in this repository's words, the rest byte for
  byte. (B: the oracle's bytes.)
- R-tb02-4: where the oracle crashes, an undated or unreadable date sorts
  first, `--sort none` is the order the host lists the trash in, the end of
  input under `trash-empty -i` is a no (as R-tb01-5), an info file DAYS
  cannot read is kept, and trash-rm names an unreadable info file and goes
  on. (B: exit 1 with one line of our own.)
- R-tb02-5: the trash (or a path inside it) given to `trash-restore`, and an
  item whose original path lies inside the trash, are refused by name. (B:
  as the oracle.)
- R-tb02-6: a relative `Path=` in the home trash is read from `/`, as the
  oracle reads it. (B: from the directory that holds the trash, as the
  specification says.)
- R-tb02-7: on a file system with no hard links, a restore on the same file
  system goes by `trash`'s copy, whose exclusive creations never replace.
  (B: refused by name.)
- R-tb02-8: the companions read `~/Trash` alone, as `trash` writes only
  there. (B: also show `$topdir/.Trash-$uid`, the specification's "best
  effort".)
- R-tb02-9: the footprint. (A, recommended) `cross-cutting`: the harness CI
  runs (`tools/oracle.py`, `tools/pax-rows.py`) changed, and its new pieces
  (a terminal, dated fixtures, generated trees, listings in a host's order)
  want a run on CI's hosts before the merge. (B) `module`: no path the audit
  classes as CI, a pin or shared tooling changed. Ruled A.

## Done-when

- [x] The prediction committed before any change (`3d0ffe2`), and scored
  above.
- [x] `trash-list`, `trash-restore`, `trash-rm PATTERN` and `trash-empty
  [DAYS]`, static, for PAX and Linux x86-64, from the same tree as `trash`,
  sharing `src/can/`.
- [x] The listing's format and order, an orphan info listed, a missing date
  as question marks, a relative path from `/`.
- [x] Restore by index and by path, the prompt as the oracle prints it,
  every kind of answer; an occupied path refused by name and never replaced,
  under a reservation; missing parents made; across file systems copied back,
  verified, then removed from the trash.
- [x] trash-rm by the oracle's matching rule, measured; trash-empty with and
  without DAYS, on both sides of the cut, its question, `-f`, `-i`, `-v`,
  `--dry-run`; the options that choose another trash not taken.
- [x] Orphans both ways, each command as the oracle, named above.
- [x] tb01's 12 left-out rows back in, and every census, oracle and PAX row
  of tb00 and tb01 still green.
- [x] The new rows red against the stubs first; the expected captures, the
  PAX rows and the round-trip property; every row green.
- [x] One plant, `tb02-plant-restore-rename`, red by name at
  `restore-occupied`.
- [x] The records behind both of satoyama's locks, the Linux gate and the
  PAX legs in one gauntlet, and the plant's record, both verified.
