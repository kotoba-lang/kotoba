#!/bin/sh
set -eu

driver_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
build_dir=$(mktemp -d "${TMPDIR:-/tmp}/aiueos-native-drivers.XXXXXX")
trap 'rm -rf "$build_dir"' EXIT HUP INT TERM

cc_bin=${CC:-clang}
common_flags="-std=c11 -Wall -Wextra -Werror -Wpedantic -Wconversion -Wsign-conversion -Wshadow -Wstrict-prototypes"
freestanding_flags="--target=x86_64-none-elf -ffreestanding -fno-builtin -fno-stack-protector"

for module in nvme xhci ethernet; do
  "$cc_bin" $common_flags $freestanding_flags -I"$driver_dir" \
    -c "$driver_dir/$module.c" -o "$build_dir/$module.o"
done

"$cc_bin" $common_flags -I"$driver_dir" \
  "$driver_dir/nvme.c" "$driver_dir/xhci.c" "$driver_dir/ethernet.c" \
  "$driver_dir/tests/native_drivers_test.c" -o "$build_dir/native-drivers-test"
"$build_dir/native-drivers-test"
printf '%s\n' "native-driver freestanding compile: PASS (x86_64-none-elf)"
