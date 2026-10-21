#!/usr/bin/env python3
"""Measurements for the server-operator-crawl bot.

Same contract as company_evidence.py. Decision-free: syncs the worktree to
origin/main and runs the wiki's own growth-evidence collector. REFUSED banner
on any failure so the bot is told it is blind, never that the wiki is complete.

2026-09-13: collector moved to kbb cutover — scripts/wiki_growth_evidence.cljk
is now run via `kbb --backend sci` with kotoba-lang/text on the classpath
(nbb + the old .cljs path no longer exist on main).
"""
import os
import subprocess
import sys

WORKTREE = os.environ.get(
    "HYAKKA_BOT_WORKTREE",
    os.path.expanduser("~/.gftd/worktrees/server-operator-crawl"))
KBB = os.environ.get("HYAKKA_KBB", "/opt/homebrew/bin/kbb")
TEXT_SRC = os.environ.get(
    "HYAKKA_TEXT_SRC",
    "~/github/com-junkawasaki/orgs/kotoba-lang/text/src")
DAYS = os.environ.get("HYAKKA_EVIDENCE_DAYS", "14")


def refuse(why):
    print("REFUSED — no evidence was gathered this run.")
    print(why)
    print()
    print("Do not propose anything. A growth proposal built on an unread tree "
          "is a proposal built on nothing. Report this refusal and stop.")
    sys.exit(0)


def git(*args):
    return subprocess.run(("git", "-C", WORKTREE) + args,
                          capture_output=True, text=True, timeout=300)


def main():
    if not (os.path.isdir(os.path.join(WORKTREE, ".git"))
            or os.path.exists(os.path.join(WORKTREE, ".git"))):
        refuse(f"no git worktree at {WORKTREE}")
    fetch = git("fetch", "--quiet", "origin")
    if fetch.returncode != 0:
        refuse(f"git fetch failed: {fetch.stderr.strip()[:400]}")
    reset = git("checkout", "--quiet", "--detach", "origin/main")
    if reset.returncode != 0:
        refuse(f"could not move to origin/main: {reset.stderr.strip()[:400]}")
    head = git("rev-parse", "--short", "HEAD").stdout.strip()
    collector = os.path.join(WORKTREE, "scripts", "wiki_growth_evidence.cljk")
    if not os.path.exists(collector):
        refuse(f"collector missing on main checkout: {collector}")
    if not os.path.isdir(TEXT_SRC):
        refuse(f"kotoba-lang/text src missing: {TEXT_SRC}")
    proc = subprocess.run(
        [KBB, "--backend", "sci", "--classpath", f"src:{TEXT_SRC}",
         collector, "--root", ".", "--days", DAYS],
        cwd=WORKTREE, capture_output=True, text=True, timeout=600)
    if proc.returncode == 2:
        refuse("the evidence collector refused:\n" + proc.stderr.strip()[:800])
    if proc.returncode != 0:
        refuse(f"the evidence collector exited {proc.returncode}:\n"
               + (proc.stderr.strip() or proc.stdout.strip())[:800])
    if "SCANNED\t" not in proc.stdout:
        refuse("the collector produced no SCANNED line")
    print(f"worktree\t{WORKTREE}")
    print(f"head\t{head}")
    print(proc.stdout.strip())


if __name__ == "__main__":
    main()
