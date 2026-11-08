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
