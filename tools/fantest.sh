#!/bin/bash
# Find out which EC PWM output drives which fan: ramps each PWM channel to 100%
# for 15 s and prints every fan's RPM. The fans get loud.
#
# Needs the out-of-tree nct6687 driver (https://github.com/Fred78290/nct6687d),
# built but not installed (run `make` in its directory):
#   sudo ./fantest.sh /path/to/nct6687d/nct6687.ko
#
# Swaps the read-only nct6683 driver for nct6687 until the next reboot.
# Restores every channel's mode and, for manual channels, its duty on exit.
set -u
ko=${1:?usage: sudo $0 /path/to/nct6687.ko}
[ "$EUID" -eq 0 ] || { echo "run with sudo"; exit 1; }
rmmod nct6683 2>/dev/null
insmod "$ko" || exit 1
sleep 2
name=$(grep -l -E '^nct668[67]$' /sys/class/hwmon/hwmon*/name | head -1)
[ -n "$name" ] || { echo "nct6687 hwmon device not found"; exit 1; }
hw=$(dirname "$name")
echo "hwmon: $hw"
cd "$hw" || exit 1

declare -A orig_en orig_pwm
for p in pwm[0-9]; do
	orig_en[$p]=$(cat "${p}_enable")
	orig_pwm[$p]=$(cat "$p")
done

restore_one() {
	local p=$1
	echo "${orig_en[$p]}" > "${p}_enable"
	[ "${orig_en[$p]}" = 1 ] && echo "${orig_pwm[$p]}" > "$p"
}
restore_all() { for p in "${!orig_en[@]}"; do restore_one "$p"; done; }
trap restore_all EXIT

fans() { for f in fan*_input; do printf '%s=%s ' "${f%_input}" "$(cat "$f")"; done; }

echo "--- baseline: $(fans)"
for p in pwm[0-9]; do
	echo "$p=${orig_pwm[$p]} enable=${orig_en[$p]}"
done
for p in pwm[0-9]; do
	echo 1 > "${p}_enable" 2>/dev/null || { echo "$p: manual mode not accepted"; continue; }
	echo 255 > "$p"
	sleep 15
	echo "--- $p @100%: $(fans)"
	restore_one "$p"
	sleep 5
done
