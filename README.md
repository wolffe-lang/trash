# trash

A reversible `rm`, written in [wolf](https://github.com/wolffe-lang/wolf-lang),
for PAX and Linux x86-64. `trash FILE…` takes what `rm` takes and moves each
item into the user's trash instead of unlinking it; `trash-list`,
`trash-restore`, `trash-rm` and `trash-empty` look after it until it is
emptied.

**State: the repository scaffold.** Nothing is implemented yet.

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
