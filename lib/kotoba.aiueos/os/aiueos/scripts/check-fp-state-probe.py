#!/usr/bin/env python3
"""JUN-855 gate: judge the AIUEOS_FP_PROBE line of a kernel serial log.

    check-fp-state-probe.py --serial kernel-serial.log --expect preserved|clobbered

The line is printed by kernel/process.c when the kernel is built with
AIUEOS_FP_PROBE=measure|poison|fxsave (see build-uefi.sh). Two CPL3 processes each hold a different
value in xmm0/xmm7, x87 st0, the x87 control word and MXCSR and re-read them in a loop while the APIC timer
preempts them. A counter is a number of events in which a process found somebody else's value.

  preserved   every event counter is 0 in both processes
  clobbered   every process saw xmm, x87 and MXCSR events (the stock kernel; also the poison control)

Either verdict is refused as vacuous unless both processes ran (>= 100000 checks, >= 100 SYSCALLs, >= 20 TSC
gaps) and the scheduler switched user tasks >= 400 times while they ran, and AIUEOS_RING3_OK is present.
Exit 0 = expectation met, 1 = expectation not met or run vacuous, 2 = log malformed. No JVM, nbb or babashka.
"""
import argparse
import re
import sys

PROCESS = re.compile(r"p(\d)\{domain=(\d+) checks=(\d+) xmm_events=(\d+) x87_events=(\d+) mxcsr_events=(\d+) "
                     r"bad_xmm0_lo=0x[0-9a-f]{16} bad_st0=0x[0-9a-f]{16} bad_cw=0x[0-9a-f]{16} "
                     r"bad_mxcsr=0x[0-9a-f]{16} tsc_gaps=(\d+) syscalls=(\d+)\}")
TAIL = re.compile(r"user_switches_during=(\d+) user_switches_total=(\d+) context_switches_total=(\d+)\s*$")


def parse(text):
    lines = [l for l in text.splitlines() if l.startswith("AIUEOS_FP_PROBE ")]
    if len(lines) != 1:
        raise ValueError("expected exactly one AIUEOS_FP_PROBE line, found %d" % len(lines))
    line = lines[0].rstrip("\r")
    procs = PROCESS.findall(line)
    tail = TAIL.search(line)
    if len(procs) != 2 or not tail or [p[0] for p in procs] != ["0", "1"]:
        raise ValueError("malformed AIUEOS_FP_PROBE line")
    keys = ("index", "domain", "checks", "xmm", "x87", "mxcsr", "gaps", "syscalls")
    rows = [dict(zip(keys, map(int, p))) for p in procs]
    if sorted(r["domain"] for r in rows) != [2, 3]:
        raise ValueError("probe domains are not 2 and 3")
    return rows, int(tail.group(1)), "AIUEOS_RING3_OK processes=2 preemptive" in text


def judge(text, expect):
    rows, switches, ring3 = parse(text)
    problems = []
    if not ring3:
        problems.append("AIUEOS_RING3_OK missing")
    for r in rows:
        if r["checks"] < 100000 or r["syscalls"] < 100 or r["gaps"] < 20:
            problems.append("vacuous: domain %d checks=%d syscalls=%d gaps=%d" %
                            (r["domain"], r["checks"], r["syscalls"], r["gaps"]))
    if switches < 400:
        problems.append("vacuous: only %d user task switches while probing" % switches)
    if expect == "preserved":
        for r in rows:
            if r["xmm"] or r["x87"] or r["mxcsr"]:
                problems.append("domain %d lost state: xmm=%d x87=%d mxcsr=%d" %
                                (r["domain"], r["xmm"], r["x87"], r["mxcsr"]))
    else:
        for r in rows:
            for k in ("xmm", "x87", "mxcsr"):
                if not r[k]:
                    problems.append("domain %d saw no %s event" % (r["domain"], k))
    return problems


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--serial", required=True)
    ap.add_argument("--expect", required=True, choices=("preserved", "clobbered"))
    args = ap.parse_args(argv)
    try:
        problems = judge(open(args.serial, encoding="utf-8", errors="replace").read(), args.expect)
    except ValueError as error:
        print("MALFORMED: %s" % error)
        return 2
    if problems:
        print("EXPECTATION NOT MET (%s):" % args.expect)
        for p in problems:
            print("  " + p)
        return 1
    print("FP_PROBE_%s_OK" % args.expect.upper())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
