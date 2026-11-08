# trash

A reversible `rm`, written in [wolf](https://github.com/wolffe-lang/wolf-lang),
for PAX and Linux x86-64. `trash FILE…` takes what `rm` takes and moves each
item into the user's trash instead of unlinking it; `trash-list`,
`trash-restore`, `trash-rm` and `trash-empty` look after it until it is
emptied.

**State: the census and the scaffold.** The commands are not written yet.
What is here measures what they will need and holds them, once written, to
the oracle: see *The census* and *The oracle* below.

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
version locked (`ci/packages.lock`). It is only ever run as a program.

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

- `bash tools/gate unit`: the pins, and the census and oracle harnesses' own
  tests. Needs only Python 3.11 or later.
- `bash tools/in-container`: builds the oracle image, checks it against its
  locks, and runs `tools/gate linux` inside it: the toolchain, `wolf fmt
  --check`, the census on Linux, the static census for PAX, and the oracle's
  rows. `TRASH_ENGINE=podman` for podman.
- `tools/gate-pax PAXTREE KERNEL INPUTS CENSUS-STATIC HOME.img OUTDIR`: the
  census on PAX under KVM (see the script's header for its inputs).

Every gate step prints `START name` and `END name exit=N`, and the first step
that fails stops the gate.

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
