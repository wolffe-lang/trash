## Unreleased

- Hardening. Every command syncs what it has made before it removes
  anything, so a power cut part-way loses no file, and a second run finishes
  what was cut short or refuses by name: `trash` takes back a name it had
  reserved, a restore cut after its link is completed, `trash-rm` and
  `trash-empty` carry on. While an item is copied in from another file
  system its info file says so, so a partial copy is never offered as an
  item. A command at work on an item holds a lock on its info file, and the
  others leave that item alone, so `trash` beside `trash-empty` or
  `trash-rm`, and two restores of one item, lose and duplicate nothing (a
  failed copy back used to remove the other restore's file). `trash-list`
  names an item with no info file and an info file with no item. `trash`
  asks whether the file may be deleted at all before it starts, as
  trash-cli does; a restore into a directory it may not write is refused
  with trash-cli's line.
- Rows that cut each command at each of its durable steps, rows that run two
  commands at once over rounds drawn from a seed, rows run as an ordinary
  user (a shared directory, a sticky one, a read-only parent, a file that
  cannot be read), rows for a trash bigger than its volume, and a witness of
  what GNU rm does on the same fixtures.

- `trash-list`, `trash-restore`, `trash-rm PATTERN` and `trash-empty [DAYS]`,
  held to trash-cli's commands of the same names: the listing's lines and
  its order, the date read as trash-cli reads it, encoded paths decoded;
  restore by number, list or span, by path, sorted by date or path, its
  prompt and every answer as trash-cli takes it; a restore never replaces
  what is at the original path (the path is reserved by a hard link or an
  empty directory, never checked and then used), makes missing directories
  above it, and copies back across file systems; patterns by fnmatch's
  rules, on the name or the whole path; DAYS counted on the calendar in
  local time; `-i`, `-f`, `-v` and `--dry-run`, and the question asked on a
  terminal. Linux x86-64 and PAX.
- The oracle's rows for the companions (246 rows in all), the captures of
  the rows with no oracle, the companions on PAX under KVM, a round-trip
  property over generated trees, and unit rows for the shared module's new
  parts. The harness gives a step a terminal, dates a fixture from now,
  generates trees, and holds a round trip.

- `trash`: files, directories and symbolic links moved into `~/Trash` in the
  Trash specification's order, the info file created exclusively first;
  collisions and long names named as trash-cli names them; trash-cli's flags,
  messages, prompts and exit codes; items on another file system copied,
  verified and then removed, refused before copying when the home volume is
  too small; `.`, `..`, `/`, the trash, anything in it and what holds it
  refused by name. Linux x86-64 and PAX.
- The oracle's rows for `trash` (118 in all), the captures of the rows with
  no oracle, `trash`'s rows on PAX under KVM, and unit programs for the
  shared module.
- The oracle harness runs with every write capped, and never hands trash-cli
  a path that begins with two slashes (it copies the whole root file system
  for one).

- The repository scaffold: licence, README and its clean-room list.
- The census: one wolf program per operation the commands need, run on Linux
  x86-64 and on PAX, with what each platform answers recorded.
- The oracle: trash-cli pinned in a container image, the harness that holds
  this repository's commands to it row by row, and its recorded results.
- The gate (`tools/gate`, `tools/gate-pax`) and CI on Linux.
