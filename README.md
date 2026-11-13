# trash

A reversible `rm`, written in [wolf](https://github.com/wolffe-lang/wolf-lang),
for PAX and Linux x86-64. `trash FILE…` takes what `rm` takes and moves each
item into the user's trash instead of unlinking it; `trash-list`,
`trash-restore`, `trash-rm` and `trash-empty` look after it until it is
emptied.

**State: hardened.** `trash`, `trash-list`, `trash-restore`, `trash-rm`
and `trash-empty` are written, held to the oracle on Linux and to their own
captures on PAX, and hardened against a power cut part-way, two commands at
once, a trash bigger than its volume, and permissions that refuse a move.
PAX's image carrying them comes next.

## Using it

### The five commands

```
trash [OPTION]... FILE...
trash-list
trash-restore [--sort {date,path,none}] [PATH]
trash-rm PATTERN
trash-empty [-v] [-i] [-f] [--dry-run] [DAYS]
```

- `trash FILE…` puts each FILE in the trash instead of removing it. It takes
  `rm`'s flags: `-f` says nothing of a FILE that is not there, `-i` asks
  first, `-v` says what was trashed, and `-r`, `-R` and `-d` are accepted (a
  directory is always trashed whole). A symbolic link is trashed as the
  link, never what it points to. The exit status is 0, 74 when some FILE
  could not be trashed, and 2 for a usage error.
- `trash-list` prints one line per item: the date and time it was trashed
  and where it came from.
- `trash-restore` puts items back (below).
- `trash-rm PATTERN` removes for good every item whose original name
  matches the shell pattern, or whose whole original path does when
  PATTERN starts with `/`.
- `trash-empty` removes everything in the trash for good, and `trash-empty
  DAYS` only what was trashed more than DAYS days ago. It asks first when
  standard input is a terminal, or with `-i`; `-f` never asks. `-v` names
  what it removes, and `--dry-run` names it and removes nothing.

### Where the trash is

Every user has one trash, `~/Trash`, laid out as the FreeDesktop.org Trash
specification lays one out. `~/Trash/files/` holds the items, each under its
own name or, when that name is taken, `NAME_1`, `NAME_2` and so on.
`~/Trash/info/NAME.trashinfo` records where each came from and when, so `ls
~/Trash/files` shows what is there and any tool that reads the specification
can read it. An item from another file system (PAX's `/tmp` is in memory) is
copied into `~/Trash`, checked byte for byte, given back its modes, owner and
times, and only then removed from where it was; if the home volume has too
little room for it, it is refused before anything is copied.

### Putting something back

`trash-restore` lists, by number, what was trashed from the working
directory or anywhere under it (or from PATH, when one is given), newest
last, and asks which to put back: a number, a list (`0,2`) or a span
(`0-3`). It never puts an item back over anything that is at its path: it
refuses by name instead, and changes nothing. A directory above the path
that has gone since is made again. An item trashed from another file system
is copied back, checked, and only then removed from the trash.

### When something goes wrong

- **A power cut, or a kill, part-way.** Each command syncs what it has made
  before it removes anything, so a cut never loses a file: every item is at
  its old path, in the trash, or both. Run the command again and it finishes
  what was cut short (`trash` takes back the name it had reserved; a
  restore cut just after it linked the item back is completed), or it
  refuses by name and changes nothing. `trash-list` names what a cut can
  leave: an item with no info file (where it came from is not known) and an
  info file with no item.
- **Two commands at once.** Two `trash` runs of the same name get two names.
  A command that is working on an item holds a lock on its info file, and
  another command leaves that item alone: `trash-empty` and `trash-rm` pass
  over it, as if they had run first, and a second `trash-restore` of it is
  refused by name.
- **Permissions.** What `rm` may not remove is refused by name: a file in a
  directory you may not write, and another user's file in a sticky
  directory such as `/tmp`. A file you may move but not read is trashed when
  it is on the home's file system, and refused (left where it is) when it
  would have to be copied.

### What is not done

- One trash only: items on other volumes are copied into `~/Trash` rather
  than kept in a trash of their own, and `--trash-dir`, `--trash-dirs`,
  `--volumes`, `--all-users` and `--overwrite` are not taken.
- A name that is not UTF-8 is refused by name for now: wolf cannot yet name
  such a path (wolf-lang#687).
- Where the host keeps no file locks, two commands at once are not kept
  apart, and `trash` never takes back a name a cut left reserved.
- A restore across file systems that is cut part-way leaves its partial
  copy at the original path, and a second restore refuses that path by
  name; the item is still whole in the trash.
- The trash's `directorysizes` cache is never written, as trash-cli never
  writes it; a file there is kept.
- macOS is not a target: Finder owns `~/.Trash`, and macOS 15 has its own
  `trash(8)`.

## What it does

- **One trash per user, at `~/Trash`.** Inside it, `files/` holds the trashed
  items and `info/` holds one `NAME.trashinfo` per item, recording where it
  came from and when it was trashed, in the layout of the FreeDesktop.org
  Trash specification.
- **The trash-cli command family:** `trash` (with `rm`'s flags `-f -r -R -d -i
  -v --` accepted, so it can stand in for `rm`), `trash-list`,
  `trash-restore`, `trash-rm PATTERN` and `trash-empty [DAYS]`. Their output
  is held to trash-cli's on Linux wherever the specification or trash-cli
  fixes the bytes.
- **Items on another file system** are copied into `~/Trash` (modes, owner,
  times and symlinks as symlinks), verified, then removed, so one trash holds
  everything and survives a reboot. A copy the home volume cannot hold is
  refused by name.
- **Never destructive by surprise:** a restore never overwrites, `.`, `..`,
  `/` and the trash itself are refused by name, and a symlink is trashed as
  the link, never its target.

## The census

`census/` holds one small wolf program per operation the commands need
(rename, telling a cross-device rename apart; an exclusive create; mkdir with
a mode; symbolic links; modes, owners and times; a recursive walk; free space;
local time), and `census/run.sh` runs them on both file systems a trashing
can involve. `census/expect.json` records, for Linux x86-64 and for PAX, what
each prints and whether the call is present, missing or wrong there, with the
upstream issue for each gap. `tools/census.py` runs them on Linux;
`tools/gate-pax` boots PAX under KVM with an ext2 home and the in-memory
`/tmp` and runs the same programs there.

## The oracle

trash-cli, pinned by the digest of its published source archive and of the
wheel built from it (`trash-oracle.toml`), runs in a container image built by
`ci/oracle.Containerfile` from a dated Ubuntu archive snapshot, every package
version locked (`ci/packages.lock`). The image verifies a pinned certificate
package before using it to bootstrap snapshot TLS; a failed index update stops
the build rather than falling back to a live archive. It is only ever run as a
program.

`tools/oracle.py` runs each row of `tests/oracle/rows.json` on trash-cli and
on this repository's commands in matching scratch homes, and compares every
command's exit status, standard output and standard error, and the trees left
behind: every entry's type, mode, bytes, link target and time, and every
`.trashinfo` line by line. The deletion date is the one value normalised: its
shape is held, and its instant must fall inside the run. trash-cli's own
results are recorded in `tests/oracle/golden/`, and the pinned trash-cli must
reproduce them.

## Building and testing

The toolchain is pinned by digest in `wolf-toolchain.toml` (wolf 0.2.38 and
lupin 0.1.60); `tools/fetch-toolchain.py` fetches and checks it.

- `bash tools/gate unit`: the pins, the census, oracle, PAX and hardening
  harnesses' own tests, and the expected captures. Needs only Python 3.11 or later.
- `bash tools/in-container`: builds the oracle image, checks it against its
  locks, and runs `tools/gate linux` inside it: the toolchain, `wolf fmt
  --check`, the census on Linux, the commands and their unit programs, the
  static census and commands for PAX, the oracle's rows on the oracle, the
  commands held to them, and the hardening rows (`tools/harden.py`): each
  command cut at each of its durable steps (`tests/cuts/rows.json`) and two
  commands run at once, in rounds drawn from a seed
  (`tests/cuts/stress.json`). `TRASH_ENGINE=podman` for podman.
  `bash tools/in-container bash tools/gate candidate` is the commands alone.
  The image's root is read-only and every scratch file system a row writes is
  a tmpfs of a fixed size.
- `tools/gate-pax PAXTREE KERNEL INPUTS CENSUS-STATIC HOME.img OUTDIR`: the
  census and then trash's own rows (`tests/pax/rows.json`) on PAX under KVM
  (see the script's header for its inputs).

Every gate step prints `START name` and `END name exit=N`, and the first step
that fails stops the gate.

The commands read two variables a test sets, and nothing else does:
`TRASH_CUT=N` ends a command, by `SIGKILL`, just before its Nth call that
changes the file system, as a power cut would, and `TRASH_PAUSE=N:MS` makes
it wait MS milliseconds there instead.

## Clean room

trash is written from:

- the FreeDesktop.org Trash specification;
- POSIX.1-2024 and the Linux manual pages for the calls it makes (`rename(2)`,
  `open(2)` with `O_EXCL`, `lstat(2)`, `readlink(2)`, `symlink(2)`,
  `utimensat(2)`, `chown(2)`);
- trash-cli's `--help` and manual pages, and black-box runs of a pinned
  trash-cli binary on Linux, which is the oracle;
- macOS's `trash(8)` manual page.

Its authors never read the source of trash-cli or of any other trash
implementation (desktop file managers, `gio`, other `trash` tools).

## Licence

GPL-3.0-or-later with the wolf Training Data Permission. See `LICENSE` and
`LICENSE-TRAINING-DATA`.
