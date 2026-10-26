/* HOST-SIDE measurement harness. It is never linked into a boot artifact and
 * never enters the ESP -- the smoke's no-foreign-object floor scans for that.
 * It exists so the icount instrument can be CALIBRATED against silicon.
 *
 * The identical 127 bytes amu emitted for x86_64-linux, executed on real
 * x86_64 Ubuntu, so the Linux side of the comparison has a number measured
 * with the same code the aiueos side boots.
 *
 * Build and run on an x86_64 Linux host (measured on gad, Ubuntu 24.04.2,
 * AMD RYZEN AI MAX+ 395, load1 0.29-0.37 throughout):
 *
 *   gcc -O2 -o perf-parity-body perf-parity-body.c
 *   perf stat -e instructions,cycles --repeat 3 ./perf-parity-body body.bin 30 10000000
 *   perf stat -e instructions,cycles --repeat 3 ./perf-parity-body body.bin 60 10000000
 *
 * Take the difference between the two sizes and divide by 30 * reps; that
 * cancels the harness's own call overhead, the same shape the QEMU side uses.
 *
 * ABI, read off the artifact rather than assumed:
 *   :fuel-abi {:mode :hidden-context-r9}  -> r9 is the fuel context
 *   :context-abi {:fuel-offset 8}         -> the counter lives at [r9+8]
 *   SysV                                  -> rdi=i, rsi=limit, rdx=acc, rax=ret
 * The body's first act is `cmp QWORD PTR [r9+0x8],0 / jne / ud2`, so a zero
 * fuel word traps rather than miscounts. */
#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <sys/mman.h>

/* rdi/rsi/rdx are "+" and not plain inputs on purpose. The callee CLOBBERS
 * rdx (`lea rdx,[rbx+0x1]`), and declaring it a pure input tells gcc the
 * register still holds `acc` afterwards -- which is true on the first call and
 * false on every later one, because the second iteration of a rep loop then
 * skips reloading it. Measured 2026-09-10 with the plain-input form: rep 0
 * returned 1305, rep 1 returned 30, i.e. `limit` instead of the sum. The
 * harness's own answer check is what caught it; the perf counters did not,
 * because an aborted run still reports plausible instruction totals (830,458
 * for 30 iterations against 824,456 for 60 -- the larger loop "cheaper"). */
static long call_body(void *fn, long i, long limit, long acc, void *ctx) {
    register void *r9 __asm__("r9") = ctx;
    long ret;
    __asm__ volatile("call *%[f]"
                     : "=a"(ret), "+D"(i), "+S"(limit), "+d"(acc)
                     : "r"(r9), [f] "r"(fn)
                     : "rcx", "r8", "r10", "r11", "memory", "cc");
    return ret;
}

int main(int argc, char **argv) {
    if (argc < 4) { fprintf(stderr, "usage: %s <body.bin> <iterations> <reps>\n", argv[0]); return 2; }
    long iterations = atol(argv[2]), reps = atol(argv[3]);

    FILE *f = fopen(argv[1], "rb");
    if (!f) { perror("open"); return 3; }
    unsigned char buf[4096];
    size_t n = fread(buf, 1, sizeof buf, f);
    fclose(f);
    if (n == 0) { fprintf(stderr, "empty body\n"); return 3; }

    void *code = mmap(NULL, 4096, PROT_READ | PROT_WRITE,
                      MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    if (code == MAP_FAILED) { perror("mmap"); return 3; }
    memcpy(code, buf, n);
    if (mprotect(code, 4096, PROT_READ | PROT_EXEC)) { perror("mprotect"); return 3; }

    /* :limits {:memory-bytes 65536}. accumulate allocates nothing and touches
     * only [r9+8], but the context is sized to the artifact's own limit rather
     * than to what this one function happens to reach. */
    void *ctx = calloc(1, 65536);
    if (!ctx) return 3;

    /* Expected answer, computed independently of the code under test:
     * sum of 3i for i in [0, iterations). */
    long expect = 3 * (iterations * (iterations - 1) / 2);

    long value = 0;
    for (long r = 0; r < reps; r++) {
        *(volatile uint64_t *)((char *)ctx + 8) = (uint64_t)1 << 40; /* fuel */
        value = call_body(code, 0, iterations, 0, ctx);
        if (value != expect) {
            fprintf(stderr, "WRONG rep=%ld got=%ld want=%ld\n", r, value, expect);
            return 1;
        }
    }
    printf("bytes=%zu iterations=%ld reps=%ld value=%ld verified\n",
           n, iterations, reps, value);
    return 0;
}
