## Unreleased

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
