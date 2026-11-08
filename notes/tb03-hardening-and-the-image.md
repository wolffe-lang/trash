# tb03: hardening and the image (T3)

T3 hardens the five commands against what a desk or a disk does to a
program: a power cut between two of its calls, a second command running at
the same moment, a trash bigger than the volume that holds it, and
permissions that refuse a move. Then the commands go onto PAX's image (a
second pull request, in PAX's tree). This note is the first part's.

## Prediction (written before any change)

Sources for this section: tb00's, tb01's and tb02's notes and goldens, the
FreeDesktop.org Trash specification 1.0 (section 6 on the info file
"first" and `O_EXCL`, the "emergency case" of an item with no info file,
section 7 on `directorysizes`, section 9 on permissions), `rename(2)`,
`link(2)`, `open(2)`, `flock(2)`, `fsync(2)`, `unlink(2)` and `chmod(2)`, the
wolf specification's OS chapter at 0.2.38 (`fs_lock`, `fs_sync`,
`fs_sync_dir`, `fs_fstat_record`, `fs_truncate`, `os_exit_signal`), and
probes of those calls on the Mac. Nothing below has been run on Linux.

### What the specification asks, and what is not yet done

- The info file is created first, with `O_EXCL`, so two writers of one name
  get two names (section 6). T1 does this. Nothing in the specification
  keeps a second *kind* of writer off a fresh reservation: `trash-empty`
  removes every `*.trashinfo` it lists (the oracle's measured rule), so an
  info file made a moment ago by a running `trash`, whose item has not yet
  arrived, is removed, and the item then lands with no info file. That is
  the specification's "emergency case" made by the commands themselves.
- An item in `files/` with no info file "MUST be clearly presented as such
  to the user". T2's `trash-list`, like the oracle's, says nothing of it.
- An info file with no item is not named by the specification. It is what a
  trashing leaves when it stops between its two steps, and what a restore
  leaves when it stops between its last two.
- `directorysizes` (section 7) is a cache that implementations SHOULD keep
  and MUST write by a temporary file and a rename. The oracle never writes
  one (tb02's `empty-sizes` golden keeps a fixture's file untouched), and
  neither does this repository; a stale entry costs a reader a recount,
  nothing more. T3 keeps it that way and says so.
- Nothing is synced (tb01: "a power cut is T3's").

### The changes

1. **The cut hook** (`src/can/cut.lu`). Every call that changes the file
   system is preceded by a named step: `step("reserve a.txt")`. Under
   `TRASH_CUT=N` the process ends at its Nth step, before that step's call,
   by `SIGKILL` (`os_exit_signal(-9)`), after one line on standard error,
   `cut before WHAT`; under `TRASH_PAUSE=N:MS` it sleeps MS milliseconds
   there instead. The counters live in the environment (each step counts
   one down), since a module `var` is `unsafe`-only at 0.2.38. With neither
   set, a step is one failed `env_get`. This is the injected fault the
   contract asks for, with no `ptrace`: a kill between two calls leaves the
   kernel's state exactly as a power cut leaves a disk that kept every
   completed call.
2. **Syncs.** `trash` syncs the info file and `info/` before it moves the
   item. A copy across file systems syncs every file and directory it made,
   and the rewritten info file, before the source is removed.
   `trash-restore` syncs the restored path's directory before it removes
   the trashed name. These are invisible to a kill; the cut rows witness
   their order by name (`sync info a.txt` before `rename into files/a.txt`).
3. **The reservation is held.** The command that reserves or changes an
   entry holds an exclusive `flock` on its info file while it works:
   `trash` from the exclusive create until the item is in `files/`;
   `trash-restore`, `trash-rm` and `trash-empty` around their change to one
   entry. A command that meets a held lock leaves that entry alone (`trash-rm`
   and `trash-empty` silently, as if they had run first; `trash-restore`
   refuses it by name). A command that takes a lock and then finds the info
   file unlinked (`fs_fstat_record`'s link count 0) knows another command
   removed it first. PAX at the pin answers `fs_lock` `unsupported`
   (the wolf specification's host posture): there the commands proceed
   without it, as T1 and T2 did.
4. **A rerun takes back what a cut left.** `trash`, meeting an info file in
   its way, takes the lock: if it gets it (no command holds that
   reservation) and the info file is empty, or reads "being copied", or
   names this very path, and no item is in `files/` under that name, the
   reservation is stale and is removed, and the name tried again. A "being
   copied" info file whose partial copy is in `files/` has that copy removed
   with it (its source was never touched; see 5). Anything else is passed
   over for the next name, as now. Where locks are not kept, nothing is
   taken back.
5. **Across file systems, the info file says "being copied" until the copy
   is whole.** On `EXDEV` the info file is rewritten as `[Trash Info]` and
   a comment line, with no `Path=`, so no command offers a partial copy as a
   trashed item; the full text is written back and synced only once the
   copy is verified, finished and synced, and only then is the source
   removed.
6. **`trash-list` names both orphans** on standard error, after its
   listing, which is unchanged on standard output: an item with no info
   file (`… has no info file, so where it came from is not known`) and an
   info file with no item (`… names an item that is not in the trash`).
7. **`trash-restore` completes a restore cut after its link**: when the
   original path and the trashed name are one file (the same device and
   inode), the trashed name and the info file are removed and the restore
   is done. Any other occupied path is refused by the oracle's line, as now.
8. **A failed copy removes only what it made.** Today a copy that fails
   removes the whole destination tree, and a restore across file systems
   that loses a race to another restore of the same item fails its first
   exclusive create and then removes the other restore's finished copy.
9. **`trash-empty` removes what it listed, by identity.** It erases each
   item under its info file's lock, then (after the orphans, in the order
   the oracle prints them under `-v`) removes each info file only if it is
   still the file it locked (device and inode); an orphan item is removed
   only while no info file names it.

### The rows

**Cut rows** (`tests/cuts/rows.json`, `tools/harden.py cuts`, Linux in the
oracle image). Each row is a fixture and one command. The harness runs the
command once uncut, then with `TRASH_CUT=1`, `2`, … until a run is not cut;
after each cut it snapshots the trees, runs `trash-list`, runs the command
again uncut (the rerun) and snapshots again. A row holds, per cut: the step
named, the tree after the cut, the listing, the rerun's status and streams,
and the tree after the rerun; and a property every cut must keep: every
byte the fixture made is still in a file somewhere in the home or on the
second file system, after the cut and after the rerun (for `trash-rm` and
`trash-empty`, every byte they were not asked to remove). Its captures
(`tests/cuts/expected/`) are written by hand in `tools/expected.py` from the
design above.

| row | the command | predicted cuts and reruns |
|---|---|---|
| `cut-put-file` | `trash a.txt`, no trash yet | 8 cuts: `make` ×3, `reserve`, `write info`, `sync info`, `sync info/`, `rename`. Before `write info` an empty info file (`Parse Error` in the listing); after it, a whole one with no item (listed, and named as missing its item). Every rerun takes the stale reservation back: the tree after it is the uncut tree |
| `cut-put-dir` | `trash d`, a tree | the same 5 steps after the trash's dirs exist; the rerun completes |
| `cut-put-other-fs` | `trash /xdev/…/t`, a tree with a file, a link and a directory | the 5, then `mark copying`, the copy's makes, the finish of each entry, `sync the copy`, `write info`, `sync info`, and the source's removals, entry by entry. Up to the full info, the rerun takes the reservation back (and its partial copy) and completes; after it, the source is partly removed and the rerun trashes what is left as `t_1`: nothing is lost, and the property holds |
| `cut-restore-file` | `trash-restore` of `a.txt` | `link`, `sync`, `remove` the trashed name, `remove` the info. Cut after the link: the rerun finds one file at both names and completes. Cut before the info's removal: the listing names an info with no item, and the rerun refuses by the oracle's line |
| `cut-restore-dir` | `trash-restore` of `d` | `make` the placeholder, `rename`, `sync`, `remove` the info. Cut after the placeholder: the rerun refuses by name (an empty directory is there) |
| `cut-restore-other-fs` | a tree trashed from `/xdev`, restored | the copy's steps, then the trash's removals, then the info's. Every rerun refuses by name (the path is there), and nothing is lost |
| `cut-rm` | `trash-rm '*.txt'` over a file and a directory item | each entry's removals, then its info. Every rerun completes |
| `cut-empty` | `trash-empty` over a file, a tree and an orphan | each removal. Every rerun completes |

**Stress rows** (`tests/cuts/stress.json`, `tools/harden.py stress`): two
commands at once, N rounds from a seed; each round draws which command
starts first, a start gap, and a pause (`TRASH_PAUSE`) at one step of one
of them, and holds the outcome to the ones the reservations allow.

| row | the two | allowed outcomes | predicted at T2's code (with the hook only) |
|---|---|---|---|
| `race-collide` | `trash d1/a.txt`, `trash d2/a.txt` | `a.txt` and `a.txt_1`, each with an info file naming its own source, both sources gone | held: the exclusive create already does it |
| `race-put-empty` | `trash a.txt`, `trash-empty` | either the trash empty and `a.txt` gone (trash first), or `a.txt` alone in the trash with its info (empty first) | **red**: an item with no info file, when the pause falls between the reservation and the move |
| `race-put-rm` | `trash a.txt`, `trash-rm a.txt` | the same two | **red**, the same way |
| `race-restore-twice` | two `trash-restore` of one file | one restores, the other refuses by name or finds nothing; the trash empty | held |
| `race-restore-twice-dir` | the same of a directory | the same | held |
| `race-restore-twice-other-fs` | the same of a file trashed from `/xdev` | the same | **red**: the loser's failed copy removes the winner's restored file, which the winner has already taken out of the trash, so the file is lost |

N and the seed are recorded below when the rows run.

**Permission rows** (`tests/oracle/rows.json`, run as user 1000, with
`setpriv`, in a home that user owns; the harness's new `"user"` field):

| row | the case | predicted: rm | predicted: the oracle | predicted here |
|---|---|---|---|---|
| `perm-shared-dir` | `shared/f`, another user's file in a `0777` directory | removed | trashed (a rename; the owner kept) | trashed, as both |
| `perm-sticky-other` | `sticky/f`, another user's file in a `1777` directory | `Operation not permitted` | refused, or a copy left behind | refused by name, nothing left in the trash |
| `perm-sticky-own` | the user's own file there | removed | trashed | trashed |
| `perm-readonly-parent` | `ro/f` in a `0555` directory | `Permission denied` | refused | refused by name |
| `perm-unreadable` | `secret`, mode `0000`, the user's | removed | trashed (a rename needs no read) | trashed |
| `perm-unreadable-other-fs` | the same on `/xdev` | removed | its volume's trash | refused by name before anything is removed: the copy cannot read it (section 9: never delete what cannot be trashed) |
| `perm-restore-readonly-parent` | a restore into a `0555` directory | | refused, an `[Errno 13]` line | as the oracle |
| `perm-empty-readonly-tree` | `trash-empty` of the user's tree holding a `0555` directory | | removed | removed (the directory is opened up through its handle) |

GNU `rm` runs on the same fixtures in the image as a witness
(`tools/harden.py rm-witness`), so the note says which of rm and the oracle
decided each row.

**Space rows** (`"home": "small"`, the 2 MiB tmpfs):

- `space-full-trash` (diverging, expected capture): the trash already holds
  1.5 MiB; `trash` of a 1 MiB file from `/xdev` is refused by name before
  anything is copied (no info file, nothing in `files/`, the source whole);
  `trash-empty` frees the volume; the same `trash` then copies it in.
- `space-tree` (diverging): a tree of six 400 KiB files, 2.4 MiB in all, each
  file small enough alone: refused before any is copied.
- `space-empty-v` (compared with the oracle): a 1.5 MiB item in a small
  home's trash, `trash-empty -v`: the oracle's report, `removing PATH` for
  the item and its info file, and nothing about space; the tree after it
  empty.

**Rows that change.** `list-orphans` and `list-made` gain the orphans'
lines on standard error and become diverging rows held to expected
captures, their standard output still the oracle's. Every other oracle,
unit and PAX row is unchanged and stays green.

**Unit rows** for the new pure parts: the cut counters read (`TRASH_CUT`,
`TRASH_PAUSE`), the "being copied" text and how it is recognised, and
`Path=` read back from an info file's text for the take-back.

### Red first, and the plant

- The rows and their captures are committed first; then the hook alone (no
  change of behaviour), against which every cut row is red where the design
  changes something (the take-back, the "being copied" text, the listing's
  orphans, the restore's completion) and `race-put-empty`, `race-put-rm` and
  `race-restore-twice-other-fs` are red; then the hardening, change by
  change, until every row is green.
- The plant (`tb03-plant-*`, one hunk on the green head): `trash-empty`
  erases an entry without taking its lock, and `race-put-empty` goes red by
  name.
