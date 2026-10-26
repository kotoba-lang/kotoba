/* A TCG plugin that counts executed guest instructions and prints the total on
 * exit. QEMU here is built with plugin support but ships no plugin libraries.
 *
 * READ THIS BEFORE USING IT FOR A BOUNDARY MEASUREMENT: a whole-run total is
 * NOT the way to measure a small region, and this file exists partly to record
 * why. Measured 2026-09-10, one unmodified image booted twice under
 * `-icount shift=0,sleep=off`:
 *
 *     run 1   1,532,182,814
 *     run 2   1,528,370,810      <- 3,812,004 apart, SAME image
 *
 * and two images differing by 30 loop iterations (a 450-instruction signal)
 * came out 16,949,555 apart. icount makes the guest CLOCK deterministic; it
 * does not make OVMF's device-polling loops spin the same number of times, and
 * the firmware is ~1.5e9 instructions of that. A region measured by bracketing
 * INSIDE the guest with `kernel-rdtsc` was byte-identical across three runs in
 * the same session, because it runs after boot and touches no devices.
 *
 * So: use this for coarse whole-run work, never for a boundary. To price a
 * capability call, the guest has to bracket it.
 *
 * Build (macOS/Homebrew; note ${=VAR} -- zsh does not word-split unquoted):
 *   GLIB=$(pkg-config --cflags glib-2.0)
 *   cc -O2 -shared -fPIC -I/opt/homebrew/include ${=GLIB} \
 *      -undefined dynamic_lookup -o libinsn.dylib qemu-insn-count-plugin.c
 *   qemu-system-x86_64 ... -plugin ./libinsn.dylib     # prints GUEST-INSNS to stderr
 */
#include <stdint.h>
#include <stdio.h>
#include <qemu-plugin.h>

QEMU_PLUGIN_EXPORT int qemu_plugin_version = QEMU_PLUGIN_VERSION;

static struct qemu_plugin_scoreboard *board;
static qemu_plugin_u64 counter;

static void tb_trans(qemu_plugin_id_t id, struct qemu_plugin_tb *tb)
{
    size_t n = qemu_plugin_tb_n_insns(tb);
    qemu_plugin_register_vcpu_tb_exec_inline_per_vcpu(
        tb, QEMU_PLUGIN_INLINE_ADD_U64, counter, (uint64_t) n);
}

static void at_exit(qemu_plugin_id_t id, void *data)
{
    /* stderr, because the guest owns stdout in these smokes. */
    fprintf(stderr, "GUEST-INSNS %llu\n",
            (unsigned long long) qemu_plugin_u64_sum(counter));
    qemu_plugin_scoreboard_free(board);
}

QEMU_PLUGIN_EXPORT int qemu_plugin_install(qemu_plugin_id_t id,
                                           const qemu_info_t *info,
                                           int argc, char **argv)
{
    board = qemu_plugin_scoreboard_new(sizeof(uint64_t));
    counter = qemu_plugin_scoreboard_u64(board);
    qemu_plugin_register_vcpu_tb_trans_cb(id, tb_trans);
    qemu_plugin_register_atexit_cb(id, at_exit, NULL);
    return 0;
}
