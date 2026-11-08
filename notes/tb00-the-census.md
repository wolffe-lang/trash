# tb00: the census and the scaffold (T0)

T0 measures what a reversible `rm` needs from the toolchain and from PAX
before a line of `trash` is written: which calls each operation makes, which
of them wolf and its standard library have at the pinned release, which PAX
answers, and what trash-cli (the oracle) writes. It also builds the oracle
container, the harness that holds both tools row by row, and the repository's
build, CI and gate.

## Prediction (written before any measurement)

Sources for this section: the FreeDesktop.org Trash specification 1.0, the
POSIX and Linux manual pages it leans on, the wolf specification's OS chapter
and the standard library at the pins, and PAX's own documentation of its
system calls. Nothing here has been run yet.

### Which operations need which calls

| operation | calls it needs |
|---|---|
| `trash` (put) | the arguments as bytes (`env_args_bytes`); `HOME` (`env_get`); the working directory (`os_cwd`), since `Path=` is absolute; `lstat` of each operand (its kind, and its device and inode to refuse `/`, `.`, `..` and the trash itself); `mkdir` with a mode for `~/Trash`, `files/` and `info/`; an exclusive create (`O_EXCL`) of the info file, then its write and close; the wall clock and the local time with its offset for `DeletionDate`; percent-encoding of the path's bytes (own code); `rename` into `files/`, with `EXDEV` told apart from every other failure; on `EXDEV`, the free space of the home volume, a recursive walk, a copy that keeps modes, owners, times and symlinks as symlinks, a verification, then a recursive removal of the original; on any failure after the info file exists, its removal; for `-i`, a line from standard input and whether standard input is a terminal |
| `trash-list` | a listing of `info/` whose names may be any bytes; whole-file reads; percent-decoding (own code) |
| `trash-restore` | the list's calls; `lstat` of the original path (it must be free); `mkdir -p` of missing parents; a rename that never replaces; on `EXDEV`, the copy path above; removal of the info file |
| `trash-rm PATTERN` | the list's calls; a glob matcher (own code); the recursive removal |
| `trash-empty [DAYS]` | the list's calls; `DeletionDate` read back as an instant (the zone's offset at that time); the recursive removal |

### What each platform should have

The pins: wolf 0.2.38 with its bundled standard library, lupin 0.1.60, and
PAX at trunk `db516c69`. "Builtin" is the call the language provides; "std" is
the standard library's wrapper of it.

| row | builtin and std at the pin | Linux x86-64 | PAX under KVM |
|---|---|---|---|
| rename, same file system | `fs_rename`; std `move_file` | present | present |
| rename across file systems | `fs_rename` answers `cross_device` | present | present: the in-memory tree and an ext2 volume are two stores, and a rename between them is `EXDEV` |
| rename of a missing file | `not_found`, not `cross_device` | present | present |
| a rename that never replaces | none: `fs_rename` always replaces | missing | missing |
| create with `O_EXCL` | `fs_open_perm(path, 4, mode)`; std `create_private`, `create_new_with_mode` | present: a second create answers `exists` | present |
| mkdir with a mode | `fs_create_dir_mode`; std `create_dir_mode` | present: `0o700` reads back | present |
| `lstat` | `fs_lstat`; std `lstat` | present: a link is kind 3, its size its target's length | present |
| `readlink` | `fs_read_link`; std `read_link` | present: the target's bytes verbatim | present |
| `symlink` | `fs_symlink`; std `symlink` | present | present on the in-memory tree and on ext2 |
| chmod | `fs_set_mode`; std `set_mode` | present | present |
| chown, of a file and of a link itself | `fs_set_owner`; std `set_owner`, `set_link_owner` | present | present |
| setting times, of a file and of a link itself | `fs_set_times`; std `set_times`, `set_link_times` | present to the nanosecond | present on the in-memory tree; on a small ext2 volume (128-byte inodes) whole seconds only, so the nanoseconds read back as 0 |
| a recursive walk | `fs_read_dir_entries` and the directory-handle family (`fs_open_at`, `fs_lstat_at`, `fs_read_dir_entries_at`, `fs_remove_at`, `fs_remove_dir_at`); std `entries` only, no wrapper of the handle family | present | present |
| a name that is not UTF-8 | listed as bytes, but every path call takes a `str` (wolf-lang#687) | missing: such a name can be listed and not renamed, copied or removed | missing, the same |
| free space on the home volume | `fs_statfs`; no std wrapper | present | present |
| the wall clock | `time_unix_ms`; std `time.unix_ms` | present | present: the RTC's reading at boot plus the ticks since |
| local time with its offset | std `time.local`, `time.format` | present with the system zone file, and with `TZ` | wrong: no zone file on the image, so with `TZ` unset `time.local` answers a row (`zone` or `io`) instead of a time; an explicit POSIX `TZ` rule or an empty `TZ` (UTC) works |
| the working directory | `os_cwd`; std `env.cwd` | present | present |
| arguments that are not UTF-8 | `env_args` traps; `env_args_bytes` answers the bytes | present | present |
| a copy the host makes | `fs_copy_chunk`; no std wrapper | present | present, also between the two stores |
| removal of a file and of an empty directory | `fs_remove`, `fs_remove_dir` | present | present |

Expected gaps to file: the standard library has no wrapper for `fs_statfs`,
`fs_copy_chunk` or the directory-handle family (wolf-std); the image has no
zone data, so local time is unanswerable with `TZ` unset (PAX). The rename
that never replaces and the byte path are already filed upstream, and T1
names them where it meets them.

### What `trash-put` writes

trash-cli's home trash is `$XDG_DATA_HOME/Trash`. With `XDG_DATA_HOME` set to
`$HOME`, it is `~/Trash`, the layout this repository uses, so both tools can be
run in matching scratch homes and their trees compared directly.

1. **A plain file** `~/a.txt`: `~/Trash/files/a.txt` is the same file, moved
   (bytes, mode and times unchanged), and `~/Trash/info/a.txt.trashinfo` is
   exactly three lines, each ending in a newline:

   ```
   [Trash Info]
   Path=/HOME/a.txt
   DeletionDate=YYYY-MM-DDThh:mm:ss
   ```

   `Path=` absolute; `DeletionDate=` local time to the second, no zone. The
   info file's mode `0600`; `Trash`, `files` and `info` made `0700`. Exit
   status 0, nothing on standard output or standard error.
2. **A directory** `~/d` with contents: `files/d` is the whole tree, moved;
   one info file, `d.trashinfo`, none for what is inside.
3. **A symbolic link** `~/l -> a.txt`: `files/l` is the link itself, its
   target bytes unchanged; the target stays where it is.
4. **A name collision**, a second `a.txt` trashed from elsewhere: a new name
   built from the old, `a_1.txt` (then `a_2.txt`), with its own info file;
   nothing earlier is overwritten.
5. **Spaces and non-ASCII bytes**: `~/my file é.txt` keeps its name in
   `files/`, and `Path=` percent-encodes every byte outside the unreserved set
   while keeping `/`: `Path=/HOME/my%20file%20%C3%A9.txt`. A name holding the
   byte `0xff` keeps it in `files/` and writes `%FF` in `Path=`.
6. **Refusals**: a missing operand is named on standard error with a nonzero
   status and nothing is written; `.` and `..` are refused by name.

## The census, measured

**How.** One wolf program per operation (`census/NAME/main.lu`), each
printing `ROW row@store observation` lines; `census/run.sh` runs them, once
per store where the store matters, and adds an `EXIT` line after each program.
`census/expect.json` holds, per platform, the observation each row must print
(a regular expression, matched whole) and whether the call is present,
missing or wrong there; `tools/census.py verdict` holds a record to it, and a
missing or wrong row passes only while it still shows the gap it names.

- **Linux x86-64:** the oracle image (Ubuntu 24.04), `same` on the file system
  the work tree is mounted from (ext4) and `other` on a tmpfs.
- **PAX under KVM:** trunk `db516c69`'s console kernel, one boot. `same` is on
  PAX's own home disk (`tools/mkdisk --home`, ext2, the digest PAX records for
  it), mounted at `/home` by PAX's `user/fstab`; `other` is the in-memory tree
  at `/tmp`. The probes are static, built by the pinned wolf through a `cc`
  that adds `-static`, and stripped for the image; the image carries pelt as
  `/bin/sh`, boreutils' `printf` and `mkdir`, and the UTC zone data PAX's
  distribution carries.
- Bytes that are not UTF-8, in a name and in an argument, are made by a small C
  fixture (`census/fixture/mkname.c`): the shell's own route for them is a row
  of its own (below).

**The result, by operation** (57 rows; `tools/census.py table` prints every
row with its observation):

| operation | wolf at the pin | Linux x86-64 | PAX |
|---|---|---|---|
| rename, same file system (a file, a directory, a symbolic link as itself) | `fs_rename` | present | present |
| rename across file systems, `EXDEV` told apart (a file, a directory) | `fs_rename`'s `cross_device` | present: `cross_device`, errno 18 | present: `cross_device`, errno 18 |
| rename of a missing file | `not_found` | present | present |
| a rename that never replaces | none | missing (wolf-lang#706) | missing (wolf-lang#706) |
| a hard link, which never replaces | `fs_link` | present: `exists` over a name, `cross_device` across | present, the same |
| create with `O_EXCL` and a mode | `fs_open_perm(p, 4, 0o600)` | present: `exists` the second time, mode 600 | present |
| mkdir with a mode | `fs_create_dir_mode` | present: 700 | present |
| `symlink`, `lstat`, `readlink` (a link and a dangling one) | `fs_symlink`, `fs_lstat`, `fs_read_link` | present | present |
| chmod | `fs_set_mode` | present | present |
| chown, of a file and of a link itself | `fs_set_owner` | present | present |
| times, of a file and of a link itself, to the nanosecond | `fs_set_times` | present | present on both stores |
| a recursive walk, by path and by held directory | `fs_read_dir_entries`, the `_at` calls | present | present |
| removal: a file, a link (never its target), an empty directory, and by held directory | `fs_remove`, `fs_remove_dir`, `fs_remove_at`, `fs_remove_dir_at` | present | present |
| a name that is not UTF-8 | listed as bytes; no path call takes it | missing (wolf-lang#687) | missing (wolf-lang#687) |
| arguments that are not UTF-8 | `env_args_bytes` | present | present |
| the same bytes through the shell (`$(printf ...)`) | | present (dash) | wrong: pelt makes the byte `?` (pelt#20) |
| free space | `fs_statfs` (no std wrapper, wolf-std#141) | present | present on both stores |
| a copy the host makes, across file systems | `fs_copy_chunk` (no std wrapper, wolf-std#141) | present | present |
| syncs of a file and of its directory | `fs_sync`, `fs_sync_dir` | present | present |
| may this process write the directory | `fs_access` | present | present |
| the wall clock | `time_unix_ms` | present | present |
| local time with its offset: `TZ` unset, empty, a POSIX rule | std `time.local` | present | present (UTC from the distribution's `/etc/localtime`) |
| local time in a named zone | std `time.local` | present | missing: the image carries the UTC zone alone, by design |
| the working directory | `os_cwd` | present | present |

**Prediction against result.**

- Held: every row on Linux, as predicted; on PAX, every system call trash
  needs is there on both stores, `EXDEV` between them, as predicted; the
  standard library lacks the three groups of wrappers predicted, and the two
  known language gaps show as predicted.
- Wrong, each now measured:
  - PAX's ext2 home disk keeps nanoseconds: it has 256-byte inodes (the kernel
    says so at mount), not the 128-byte inodes predicted.
  - Local time with `TZ` unset is answered on PAX: an installed PAX carries
    UTC at `/etc/localtime` (its `tools/mkzone`). The first image had no zone
    data at all and answered `zone`; the census image now carries what the
    distribution does.
  - Not foreseen: PAX's shell loses a byte that is not UTF-8 in a command
    substitution (it becomes `?`, and a script holding one is refused). The
    same pelt does the same on Linux, so it is the shell's, already filed as
    pelt#20; PAX itself passes such bytes whole, in a name and in `argv`.
- **Red first.** The first PAX take (`5e4cecf`) was red on 9 rows: the shell's
  `?` for the non-UTF-8 fixtures (7 rows) and the two ext2 time rows. With
  the fixture made in C (`92b5d36`) it was red on 3, and with the
  distribution's zone data (`e91c31f`) on 4, the local-time row now answering
  where the prediction said it would not. The expectations then moved to the
  measurement (`census/expect.json`), each moved row named above.

## The gaps, and how T1 meets them

| gap | filed | what T1 does |
|---|---|---|
| A name that is not UTF-8 can be listed and not renamed, copied or removed: every path call takes a `str`. | wolf-lang#687 (open) | `trash` reads its operands with `env_args_bytes` and refuses one that is not UTF-8 by name, touching nothing; the list shows an entry whose name it cannot reach, and leaves it. Waits for #687. |
| Every rename replaces. | wolf-lang#706 (open) | Trashing is safe without it: the exclusive create of the info file reserves the name in `files/`, as the specification asks. A restore must never overwrite: a file or a symbolic link goes back by `fs_link` and then `fs_remove` of the trashed name (a link never replaces; measured on both platforms); a directory by a check and then the rename, the window between them named in the code. Waits for #706. |
| `std.fs` has no wrapper for `fs_statfs`, `fs_copy_chunk` or the held-directory calls. | wolf-std#141 (filed by this lane) | T1 calls the builtins directly. |
| PAX's shell turns a byte that is not UTF-8 into `?` in a command substitution. | pelt#20 (open) | Nothing: the program receives whatever the shell passes. A name made otherwise reaches `trash` whole on PAX, and meets #687. |
| PAX's image carries the UTC zone alone. | not a gap: the distribution's choice | `DeletionDate` on PAX is UTC unless `TZ` names a POSIX rule; when no zone data answers at all, T1 writes UTC, as a C library does without `/etc/localtime`. |

No PAX kernel gap was found: every call trash needs answers on PAX as it does
on Linux, on the ext2 volume and on the in-memory tree.

## The oracle, and what `trash-put` writes

**The image.** trash-cli 0.26.9.29, the newest release on PyPI when this lane
started. PyPI publishes only its source archive, so the image builds a wheel
from it (setuptools alone, no build isolation, `SOURCE_DATE_EPOCH` fixed) and
installs that. Two builds gave the same bytes, and the wheel is pinned by that
digest beside the archive's (`trash-oracle.toml`, `ci/oracle-*.txt`). Its two
dependencies are published wheels pinned by hash. The base is Ubuntu 24.04 by
digest, its packages from the archive snapshot `20261107T000000Z`, the whole
closure locked (`ci/packages.lock`); `tools/in-container` refuses an image
whose closure or oracle manifest differs, and `tools/check-pins.py` holds
every file that repeats a pin to it. The oracle is run only as a program, and
a Python traceback in its output would be redacted and fail its row (none
occurred).

**The harness** (`tools/oracle.py`) runs a row's steps on one tool in a
scratch home at a fixed path, snapshots the home, the second file system and
any per-volume trash at the top of either, removes everything, and runs the
same steps on the other tool at the same path. Both tools see
`XDG_DATA_HOME=$HOME`, so trash-cli's home trash is `~/Trash`, this
repository's layout, and the two trees compare with no path rewritten. The
comparison is every command's exit status, standard output and standard
error, and every entry's type, mode, owner, size, bytes, link target and
modification time, with each `.trashinfo` held line by line. Normalised by
name, and only these: `DeletionDate=` (its shape held, its instant, read in
the row's zone, inside the run's window), dates and times in a command's
output inside the window, modification times inside the window, and the
lines of a listing a row marks as host-ordered.

**Its own tests.** `oracle.py selftest` checks the normaliser on a synthetic
capture and then mutates 22 fields a difference could hide in — the `Path=`
line, a missing `Path=`, the header, an extra line, a date outside the
window, a date of the wrong shape, a date written in UTC where local time is
due, the info file's mode, a file's bytes, mode and time, a link turned into
a file, a link's target, a directory's mode, an extra and a missing entry,
something left behind on the other file system, an exit status, both
streams, a fixed date in a listing, and a traceback; each must be seen by
name. With `--live` it runs every row on trash-cli twice and requires the two
captures to agree, and `oracle.py check` holds trash-cli to its recorded
goldens (`tests/oracle/golden/`, 44 rows). Both pass.

**Prediction against result** (the goldens):

| case | predicted | measured |
|---|---|---|
| a plain file | moved unchanged; info file of three lines, `Path=` absolute, `DeletionDate=` local time to the second; info `0600`; `Trash`, `files`, `info` `0700`; silent, exit 0 | held, every byte |
| a directory | the tree moved whole, one info file | held |
| a symbolic link | the link, its target untouched | held; and `trash l/`, a link to a directory named with a slash, also trashes the link, not the directory |
| a name collision | `a_1.txt`, then `a_2.txt` | **wrong**: `a.txt_1`, then `a.txt_2`: the suffix follows the whole name, extension and all (`a.tar.gz_1`, `.hidden_1`, `noext_1`, a directory `dd_1`); the info files follow the names |
| spaces and non-ASCII | `Path=…/my%20file%20%C3%A9.txt`, `%FF` for the byte 0xff, `/` kept | held. The bytes left unencoded are RFC 3986's unreserved set, letters, digits and `-._~`, with `/`; everything else is encoded in upper-case hex, RFC 2396's marks `!*'()` included; a tab is `%09`, a newline `%0A` |
| refusals | a missing operand named on standard error, nonzero; `.` and `..` refused | held: `trash: cannot trash non existent 'nope'` and `trash: cannot trash directory '.'`, each exit 74; `-f` makes a missing operand silent with exit 0; the other operands are still trashed |

Measured beyond the prediction, for T1 and T2 to be held to:

- No operand: `usage: trash [OPTION]... FILE...` and `trash: error: Please
  specify the files to trash.` on standard error, exit 2; an unknown option,
  exit 2. `-r`, `-R`, `-d` and `-f` together are accepted.
- `-v` writes `trash: 'a.txt' trashed in ~/Trash` to standard error; `-i`
  asks `trash: trash regular file 'a.txt'? ` on standard output and takes `y`.
- **Another file system:** trash-cli trashes into that volume's own trash
  (`/xdev/.Trash-0`, `Path=` relative to the volume's top), and with
  `--trash-dir ~/Trash` it refuses (exit 74, "not in the same volume"). It
  never copies across file systems, so this repository's copy into `~/Trash`
  has no oracle: those three rows are marked as diverging by design, and the
  candidate is held to captures of its own (`tests/oracle/expected/`, written
  with T1).
- **The trash itself:** trash-cli trashes `Trash/files/a.txt` back into the
  trash as `a.txt_1`, leaving `a.txt.trashinfo` orphaned, and trashes `Trash`
  by moving the whole home trash into the root volume's trash
  (`/.Trash-0`). This repository refuses both by name; the row diverges.
- `trash-list` prints `YYYY-MM-DD hh:mm:ss PATH`, the path decoded, in the
  order the directory hands the info files over (the row compares its lines
  as a set, by name); an info file with no item is listed, an item with no
  info file is not; a missing `DeletionDate` prints `????-??-?? ??:??:??`; a
  relative `Path=` is read from the volume's top (`docs/rel` lists as
  `/docs/rel`).
- `trash-restore` lists `   0 DATE PATH` and asks `What file to restore
  [0..0]: ` on standard output; it restores and removes the info file; it
  recreates a missing parent directory; over an occupied path it prints
  `Refusing to overwrite existing file "a.txt".` on standard error and exits
  1, changing nothing; with nothing to restore, `No files trashed from current
  dir ('/path')`, exit 0.
- `trash-rm '*.txt'` matches the original names; `trash-empty` empties
  without asking when standard input is not a terminal; `trash-empty 1`
  removes what was trashed more than a day ago and keeps the rest.
- `DeletionDate` is local time: the row run with `TZ=Asia/Tokyo` lies in the
  window only when read as Tokyo time.

## The scaffold

- `wolf-toolchain.toml` pins wolf 0.2.38 and lupin 0.1.60 by archive digest,
  from two reads of the release metadata (`tests/pin-read-*.json`);
  `tools/fetch-toolchain.py` reads every archive twice and checks the staged
  versions and the bundled standard library's revision.
- `tools/gate unit` (pins, the census, PAX and oracle harnesses' own tests)
  and `tools/gate linux` (in the oracle image: the toolchain, `wolf fmt
  --check`, the census built, run and held on Linux, the static census for
  PAX, the oracle twice per row and against its goldens).
- The PAX build path: `tools/census.py build --static` builds through a `cc`
  that adds `-static` (wolf has no `--static`), checks every program is a
  static `ET_EXEC` with no interpreter, and keeps a stripped copy for an
  image. `tools/gate-pax` boots the result. The image hook in PAX's tree
  (`tools/mktrash`, `user/trash.pin`) comes with T3.
- CI on Linux (`.github/workflows/ci.yml`): `tools/gate unit` and
  `tools/in-container` on Ubuntu 24.04, on a pull request labelled
  `full-matrix`, on every push to `trunk`, nightly and by hand.

## SKIPs

None. No row skips: a row that does not run fails by name.

## Recommendations

Each is implemented.

- R-tb00-1: the PAX census image carries the zone data PAX's distribution
  carries (UTC), not none.
- R-tb00-2: the PAX probes are the default tier, static glibc, stripped for
  the image.
- R-tb00-3: the oracle's wheel is built in the image from the pinned source
  archive and pinned by its own digest.
- R-tb00-4: when no zone data answers, `DeletionDate` is written in UTC.
- R-tb00-5: both tools run with `XDG_DATA_HOME=$HOME`, so trash-cli's home
  trash is `~/Trash` and the trees compare without rewriting a path.
  (B: two homes at two paths with the paths rewritten — more normalisation,
  and a `Path=` difference could hide in it.)
- R-tb00-6: the two runs of a row share one fixed scratch path, one after the
  other.
- R-tb00-7: collisions are named as the oracle names them, `NAME_1` after
  the whole name.
- R-tb00-8: the rows where this repository departs from the oracle by
  design (the trash itself refused; another file system copied into
  `~/Trash`) are marked `diverge`, and the candidate is held to its own
  expected captures there.
- R-tb00-9: a listing in host order is compared as a set of lines, by name,
  and T2 lists in host order as the oracle does.
- R-tb00-10: CI runs on a pull request only when it is labelled
  `full-matrix`; the local record is the gate otherwise.
