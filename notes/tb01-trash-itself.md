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
