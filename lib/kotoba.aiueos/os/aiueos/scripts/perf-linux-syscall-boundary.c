/* What one Linux syscall boundary costs in retired instructions, measured the
 * same way and in the same unit as the aiueos side (ADR-0211).
 *
 * This is HALF of a comparison. The other half does not exist yet: aiueos has
 * no ring 3, no syscall entry/exit and no capability handle table outside the
 * reference profile, so there is nothing to put beside this number today. It
 * is measured now so that when that path lands, the comparison is one
 * subtraction rather than a fresh experiment on a machine whose state has
 * drifted.
 *
 * SYS_getpid is chosen because the kernel-side work is close to nothing, so
 * what remains is the boundary: entry, the mitigation trampolines, and exit.
 * glibc does not cache it (the cache was removed in 2.25), and this calls the
 * raw syscall anyway rather than trusting that.
 *
 * Two sizes and a difference, so the loop's own bookkeeping cancels. */
#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <sys/syscall.h>

/* The difference between two SIZES cancels everything constant, but not the
 * loop's own per-iteration bookkeeping, because iterations scale 1:1 with
 * syscalls. So there is a second arm: the identical loop with the syscall
 * replaced by a volatile read. Subtracting arm B from arm A leaves the
 * boundary, and neither arm is an estimate. */
static volatile long sink_source = 0;

int main(int argc, char **argv) {
    if (argc < 2) { fprintf(stderr, "usage: %s <count> [null]\n", argv[0]); return 2; }
    long count = atol(argv[1]);
    int null_arm = (argc > 2 && argv[2][0] == 'n');
    long seen = 0;
    if (null_arm) {
        sink_source = (long)getpid();
        for (long i = 0; i < count; i++) {
            long pid = sink_source;
            seen += pid;
        }
    } else
    for (long i = 0; i < count; i++) {
        long pid = syscall(SYS_getpid);
        seen += pid;          /* consume it, so the call cannot be elided */
    }
    /* An oracle, cheap but real: every call must have returned this process's
     * pid, so `seen` is exactly count * getpid(). A run that skipped calls, or
     * whose return value never reached this loop, fails here rather than
     * reporting a smaller instruction count as if it were a faster boundary. */
    long expect_unit = (long)getpid();
    if (count != 0 && seen / count != expect_unit) {
        fprintf(stderr, "WRONG seen=%ld count=%ld unit=%ld\n", seen, count, expect_unit);
        return 1;
    }
    printf("count=%ld pid=%ld verified\n", count, expect_unit);
    return 0;
}
