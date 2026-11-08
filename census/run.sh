#!/bin/sh
# census/run.sh BIN SAME OTHER: every census program, once per store where the
# store matters. SAME is an empty directory on the file system that holds the
# home (and so the trash), OTHER an empty one on a different file system. Each
# program prints `ROW name@store observation` lines; this script adds one
# `EXIT program@store status` line after each run, so a trap or a crash is a
# fact of the record and never a missing row. The same script runs under bash
# and dash on Linux and under pelt on PAX: POSIX shell only, and no tool but
# printf and mkdir.
bin=$1 same=$2 other=$3

run() { # program label args...
    p=$1 label=$2
    shift 2
    "$bin/$p" "$label" "$@"
    printf 'EXIT %s@%s %s\n' "$p" "$label" "$?"
}

printf 'CENSUS start\n'
for store in same other; do
    if [ "$store" = same ]; then d=$same; else d=$other; fi
    mkdir -p "$d/excl" "$d/md" "$d/links" "$d/changes" "$d/walk" "$d/names/nu" "$d/remove"
    run create-excl "$store" "$d/excl"
    run mkdir-mode "$store" "$d/md"
    run links "$store" "$d/links"
    run changes "$store" "$d/changes"
    run walk "$store" "$d/walk"
    printf '' > "$d/names/nu/$(printf 'x\377y')"
    run names "$store" "$d/names"
    run statfs "$store" "$d"
    run remove "$store" "$d/remove"
done
mkdir -p "$same/rename" "$other/rename" "$same/copy" "$other/copy"
run rename across "$same/rename" "$other/rename"
run copy across "$same/copy" "$other/copy"
run clock now
run args bytes "$(printf 'a\377b')"
(cd "$same" && run cwd same)
(unset TZ; run local-time unset 1700000000)
(TZ=; export TZ; run local-time empty 1700000000)
(TZ='CET-1CEST,M3.5.0,M10.5.0/3'; export TZ; run local-time rule 1700000000)
(TZ=Europe/Berlin; export TZ; run local-time named 1700000000)
printf 'CENSUS end\n'
