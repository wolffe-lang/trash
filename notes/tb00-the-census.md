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

(Filled from the measurements; see below.)
