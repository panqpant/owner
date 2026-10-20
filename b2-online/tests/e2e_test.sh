#!/bin/sh
# End to end over loopback: two copies of the app, each running the test ROM in the real emulator,
# one hosting and one joining. Passes when each game sees the other player and the host's link
# requests come back answered.  Usage: tests/e2e_test.sh path/to/Black2Online
set -e
app=$(cd "$(dirname "$1")" && pwd)/$(basename "$1")
here=$(cd "$(dirname "$0")" && pwd)
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
"$here/testrom/build.sh" "$work/rom" >/dev/null
mkdir -p "$work/host" "$work/join"
cp "$work/rom/testrom.nds" "$work/host/"
cp "$work/rom/testrom.nds" "$work/join/"
export SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy
"$app" "$work/host/testrom.nds" --test-frames 600 --host --screenshot "$work/host.bmp" >"$work/host.txt" 2>/dev/null &
pid=$!
sleep 1
"$app" "$work/join/testrom.nds" --test-frames 480 --join 127.0.0.1 --screenshot "$work/join.bmp" >"$work/join.txt" 2>/dev/null
wait $pid
echo "host: $(cat "$work/host.txt")"
echo "join: $(cat "$work/join.txt")"
[ -n "$E2E_SHOTS" ] && cp "$work/host.bmp" "$work/join.bmp" "$E2E_SHOTS/"
fail=0
saw() { sed -n 's/.*saw the other player \([0-9]*\).*/\1/p' "$1"; }
[ "$(saw "$work/host.txt")" -ge 300 ] || { echo "FAIL: the host barely saw the joiner"; fail=1; }
[ "$(saw "$work/join.txt")" -ge 300 ] || { echo "FAIL: the joiner barely saw the host"; fail=1; }
grep -q "peer valid=1 name=Tester map=427 same=1" "$work/join.txt" || { echo "FAIL: joiner doesn't see the host at the end"; fail=1; }
grep -q "peer valid=0" "$work/host.txt" || { echo "FAIL: the host still shows the joiner after they left"; fail=1; }
answered=$(sed -n 's/.*game counter \([0-9]*\).*/\1/p' "$work/host.txt")
[ "${answered:-0}" -ge 3 ] || { echo "FAIL: only ${answered:-0} link requests answered"; fail=1; }
[ $fail -eq 0 ] && echo "e2e_test: all passed"
exit $fail
