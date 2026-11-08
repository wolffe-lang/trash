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

## What T3 does

- **The cut hook** (`src/can/cut.lu`): `step(WHAT)` before every call that
  changes the file system, in all five commands. `TRASH_CUT=N` ends the
  process by `SIGKILL` just before its Nth step, saying `cut before WHAT`;
  `TRASH_PAUSE=N:MS` sleeps there. Unset, a step is two failed `env_get`s.
- **Holds** (`src/can/hold.lu`): an exclusive `flock` on an entry's info file,
  tried once, with the link count read after it (0: another command removed
  the file first). `trash` holds its reservation from the exclusive create
  until the item is in; `trash-restore` holds the entry for the whole
  restore and refuses one another command holds (`another command is at
  work on it in the trash`, or `it is no longer in the trash`); `trash-rm`
  and `trash-empty` hold each entry around its removal and pass over one
  they cannot hold. `trash-empty` removes an entry's info file, after the
  orphans as the oracle orders its report, only while it is still the file
  it held (device and inode), and an orphan item only while no info file
  names it.
- **The take-back** (`can.put`): a reservation in `trash`'s way that no
  command holds, with no item in `files/` and an info file that is empty,
  reads "being copied", or names this very path, is stale: it is removed and
  the name tried again. A "being copied" one whose partial copy is in
  `files/` has that copy removed with it. A rerun after a cut therefore ends
  in the uncut run's tree.
- **Across file systems** (`can.put`, `can.copy`): on `EXDEV` the info file
  is rewritten as `[Trash Info]` and `# being copied into the trash`, synced;
  the copy is made, verified and finished, each file synced as it is
  written and every directory after; the full info file is written back and
  synced; only then is the source removed. A failed copy removes only what
  it made. Entries are copied and removed in the order of their names.
- **Syncs**: the info file and `info/` before the move; the copy before the
  source goes; a restored path's directory before the trashed name goes.
- **`trash-restore`**: a restore cut after its link (the original path and
  the trashed name one file) is finished by a rerun; a trashed name found
  already gone after the link means another restore finished this one, and
  the link is kept; a missing directory
  above the path is made only when it is missing (at T2 the parent was
  always asked for, a call that changed nothing); a link refused with
  `EACCES` is the oracle's `[Errno 13]` line, and only `EPERM` (a file
  system with no hard links) goes to the copy.
- **`trash`** asks whether the operand may be deleted at all (`access(2)` of
  its directory for writing) before it makes anything, and refuses in the
  oracle's words: `cannot trash regular file 'ro/f' because deleting it is
  not allowed`.
- **`trash-list`** names both orphans on standard error: `'…/files/NAME' has
  no info file, so where it came from is not known` and `'…/info/NAME.trashinfo'
  names an item that is not in the trash`. Its standard output is the
  oracle's.

## The rows, measured

- **Oracle rows** (`tests/oracle/rows.json`): 258, of which 206 are compared
  with trash-cli and 52 diverge, held to `tests/oracle/expected/`. New: 9
  permission rows run as user 1000 and 3 space rows; `list-orphans` and
  `list-made` now diverge by their standard error alone.
- **Cut rows** (`tests/cuts/rows.json`): 8 rows, 56 cuts, every cut held to
  its hand-written capture (`tools/expected.py`).
- **Stress rows** (`tests/cuts/stress.json`): 6 rows, **N = 100 rounds each,
  seed `20261108`**; the pause falls at one of the first 3 to 8 steps of one
  command, for 5, 20 or 50 ms.
- **Unit rows**: 198 (18 new: the hook's counters, which reservations are
  stale, the "being copied" text).
- **PAX rows**: the 19 of T2, unchanged.

**Red first.**
- At `5f92f3f` (the rows, their captures and the hook, no hardening): 4 of
  258 oracle rows red (`list-made`, `list-orphans`: no orphan named;
  `perm-readonly-parent`: rm's reason and a trash made, where the oracle
  refuses before making anything; `perm-restore-readonly-parent`: the
  refused link taken for a file system with no hard links), and all 8 cut
  rows red, each by name: no take-back (a rerun after a cut made `a.txt_1`
  beside an empty or orphaned info file), no syncs, no "being copied", the
  restore's link not finished, no orphan named, and the host's order of the
  entries (tmpfs lists the newest first: `d.txt` before `a.txt`).
- The stress rows at `7fa4499` (the same program; the harness then gave
  each racing command its input at its start, where the first take had run
  the two restores one after the other): `race-put-empty` 8 of 100 rounds
  and `race-put-rm` 3 of 100 left an item with no info file;
  `race-restore-twice-other-fs` 26 of 100 **lost the file**: the restore
  that lost the race failed its first exclusive create (or found the
  trashed item gone) and removed the copy the other had finished, after the
  other had already taken the item out of the trash. `race-collide`,
  `race-restore-twice` and `race-restore-twice-dir` held, as predicted.
- With the hardening: every oracle row, every cut and every round green, at
  the first build that compiled (one move error in `trash-rm` aside).
- **The plant found one more.** With every hold made shared (so that it
  excludes nothing, the plant below), `race-restore-twice` lost the file in
  27 of 100 rounds: one restore finished the other's (its link made, the
  trashed name still there), and the other, finding its trashed name gone,
  undid its own link, the only name left. A host that keeps no locks could
  do the same, so a trashed name already gone now means a restore another
  command finished, and the link is kept (`3544d81`); with the plant, that
  row then held. Two other robustness fixes came from reading the code
  against PAX's kernel: only a lock another file holds is busy, and any
  other refusal of `flock` (`ENOLCK` included) is a host that keeps none
  (`490a52c`), so a refusal of the call can never make `trash` pass over
  every name.

**Prediction against result.**

| prediction | result |
|---|---|
| cut rows: the steps, states, listings and reruns stated | held, every one of the 56, as written before the hardening |
| `race-put-empty`, `race-put-rm` red at T2's code | held |
| `race-restore-twice-other-fs` red at T2's code | held, and worse than predicted: 26 of 100 rounds, by both orders of the race |
| `race-collide`, `race-restore-twice(-dir)` held at T2's code | held |
| `perm-sticky-other`: the oracle refuses or leaves a copy | refuses, in its long form naming each trash it tried, and leaves an empty `/tmp/.Trash-1000` made |
| `perm-readonly-parent`: the oracle refuses | refuses before making anything: `cannot trash regular file 'ro/f' because deleting it is not allowed` (not foreseen: its own words, and its check before the start, which section 9 asks for) |
| `perm-unreadable-other-fs`: the oracle uses its volume's trash | held (a rename, since the file is on that volume) |
| `perm-restore-readonly-parent`: the oracle's `[Errno 13]` line | held |
| `perm-empty-readonly-tree`: the oracle removes it | **wrong**: as the user it cannot; it says `cannot remove …/files/d` twice, exits 0, and removes the info file, leaving the item with none |
| `perm-trash-readonly` (not predicted) | the oracle falls back to the volume trash at the top of the home's file system |
| `space-empty-v`: the oracle reports only what it removes | held |

**Who decided each permission row** (GNU rm's own answers from `rm-witness`,
run as the user on the same fixtures):

| row | rm | the oracle | here | decided by |
|---|---|---|---|---|
| `perm-shared-dir` | removed | trashed | trashed (compared) | both |
| `perm-sticky-other` | `Operation not permitted`, kept | refused (long form) | refused, `Operation not permitted`, nothing outside `~/Trash` (diverges) | both refuse; rm's words |
| `perm-sticky-own` | removed | trashed | trashed (compared) | both |
| `perm-readonly-parent` | `Permission denied`, kept | refused before the start | the oracle's words (compared) | both refuse; the oracle's words |
| `perm-unreadable` | removed | trashed | trashed (compared) | both |
| `perm-unreadable-other-fs` | removed | trashed in its volume's trash | refused by name, left where it was (diverges) | the specification (section 9: never delete what cannot be trashed), R-TB-3 |
| `perm-trash-readonly` | (removes) | trashed in the volume trash | refused by name (diverges) | R-TB-3, one trash |
| `perm-restore-readonly-parent` | | `[Errno 13]` line, exit 1 | the oracle's line (compared) | the oracle |
| `perm-empty-readonly-tree` | `Permission denied` | cannot, and orphans the item | removed whole (diverges) | R-tb03-8 (T2's rule) |

**What a cut leaves, and what a rerun does** (from the captures):

| command | a cut can leave | the rerun |
|---|---|---|
| `trash` (same file system) | an empty info file, or a whole one with the item still where it was | takes the reservation back and ends as the uncut run |
| `trash` (another file system) | the reservation; "being copied" and a partial copy; the whole copy and its info file with the source whole or partly removed | up to the full info file, takes it back (and its partial copy) and ends as the uncut run; after it, trashes what is left of the source as `NAME_1`. Nothing is lost; what was left is in the trash twice |
| `trash-restore` (a file) | the path linked back, the trashed name still there; or the info file alone | finishes the restore; or refuses by the oracle's line, the file back |
| `trash-restore` (a directory) | the empty placeholder; or the directory back with its info file | refuses by name (the oracle's line) |
| `trash-restore` (another file system) | a partial or whole copy at the path, the item whole in the trash; or the item gone and its info file left | refuses by name |
| `trash-rm`, `trash-empty` | an item part-removed, or an info file whose item is gone | carries on, and ends as the uncut run |

## The plant

`tb03-plant-unheld` (one token on the green head): a hold takes a shared lock
(`fs_lock(fd, 1)`), which never excludes another. Red by name at
`race-put-empty` (16 of 100 rounds), and at `race-put-rm` (10) and
`race-collide` (5: a live reservation taken back as stale, and one file then
renamed over the other's, since every rename replaces, wolf-lang#706);
every cut row and the restore races hold.

## Gaps met

None new. PAX's kernel implements `flock` (its own syscall table, px62),
where the wolf specification's host note at 0.2.38 expected `unsupported`;
the PAX rows do not race, so either answer serves them, and the image's KVM
leg (the second part) runs the commands there.

## SKIPs

None. A row that cannot run fails by name.

## Recommendations

Each is implemented as recommended (A).

- R-tb03-1, the cut hook. (A) In the shipped commands, read from the
  environment, a no-op unless set. (B) A separate test build: wolf has no
  conditional compilation, and a second build is not what ships. (C) Stops
  under `ptrace`: the contract asks for none.
- R-tb03-2, keeping two commands apart. (A) A `flock` on the entry's info
  file, held by the command at work on that entry; on a host with no locks,
  as T2. (B) None: `trash` beside `trash-empty` or `trash-rm` can leave an
  item with no info file (measured, 8 and 3 rounds of 100). (C) One lock for
  the whole trash: every command would wait on every other.
- R-tb03-3, a reservation a cut left. (A) `trash` takes it back when no
  command holds it, no item is in `files/`, and it is empty, "being copied",
  or names this very path; never where the host keeps no locks. (B) Never:
  a rerun takes the next name and the stale info file stays, listed with
  no item.
- R-tb03-4, a partial copy. (A) The info file reads "being copied" (no
  `Path=`) until the copy is whole and synced. (B) The full info file from
  the start: a cut leaves a partial copy listed and offered as the item.
- R-tb03-5, naming orphans. (A) `trash-list` names both kinds on standard
  error, its standard output still the oracle's. (B) As the oracle, naming
  neither (the specification's MUST is not met). (C) Marked in the listing
  itself.
- R-tb03-6, a restore cut after its link. (A) A rerun finishes it (the path
  and the trashed name are one file). (B) It refuses, as for any occupied
  path.
- R-tb03-7, a file the user may not delete. (A) Asked before anything is
  made, in the oracle's words. (B) The rename's own refusal, in rm's.
- R-tb03-8, `trash-empty` of the user's own tree that holds a read-only
  directory. (A) Removed whole, the directory opened up through its handle
  (T2's rule): the user asked for the trash to be emptied, and owns what is
  in it. (B) As rm and the oracle: refused, the item and its info file kept
  and named (the oracle removes the info file and orphans the item).
- R-tb03-9, the sticky refusal's words. (A) rm's reason, `Operation not
  permitted`. (B) The oracle's long form, which names the volume trashes
  this repository never uses.
- R-tb03-10, the footprint. (A) `cross-cutting`: `tools/gate` and
  `tools/oracle.py`, which CI runs, changed, and CI runs the new harness.
  (B) `module`.

## Done-when

- [x] R-tb02-9 recorded as ruled A in tb02's note (`31472ce`).
- [x] The prediction committed before any change (`dde4db0`), and scored
  above.
- [x] Each command cut at every durable step by an injected fault (no
  `ptrace`); orphans both ways handled as the specification says and named
  by `trash-list`; every rerun completes or refuses by name; no file lost.
  Held to their own captures, red first.
- [x] Two `trash` of colliding names, `trash` against `trash-empty` (and
  `trash-rm`), two `trash-restore` of one item (a file, a directory, a file
  from another file system): nothing lost or duplicated; N = 100 rounds,
  seed `20261108`; red first where T2 was wrong.
- [x] A trash bigger than its volume: `trash` refuses by name before
  copying; `trash-empty` frees the space and reports as the oracle does.
- [x] Permissions: another user's file in a shared directory, a sticky
  directory (in the scratch home's tmpfs), a read-only parent, a file that
  cannot be read but may be moved; each decided as above.
- [x] The README's user section.
- [x] One plant, `tb03-plant-unheld`, red by name at `race-put-empty`.
- [x] The records behind both of satoyama's locks: the Linux gate and the
  PAX legs in one gauntlet at the head, and the plant's record, both
  verified (their paths and digests are in the hand-back).
