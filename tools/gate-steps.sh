# Step helpers sourced by tools/gate. Every END is a real child exit: a step's
# output is indented two spaces, except a failing step's `FAIL ` lines, which
# reach column 0 so a record can name the red row.
step() {
  local name=$1 start=$SECONDS rc=0
  shift
  printf 'START %s\n' "$name"
  "$@" > "target/gate/$name.log" 2>&1 || rc=$?
  if [ "$rc" -eq 0 ]; then
    sed 's/^/  /' "target/gate/$name.log"
  else
    awk '/^FAIL / {print; next} {print "  " $0}' "target/gate/$name.log"
  fi
  printf 'END %s exit=%s secs=%s\n' "$name" "$rc" "$((SECONDS-start))"
  return "$rc"
}
