#!/usr/bin/env python3
"""steward_sweep.py - the deterministic merge job (no agent).

Runs the growth gate over every open bot/accountability-steward-* PR and merges
only those the gate ALLOWs. Silent when there is nothing to report is not
possible here: the gate always prints what it decided, so the cron log shows it.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import growth_gate  # noqa: E402

if __name__ == "__main__":
    growth_gate.cmd_sweep(merge=True)
