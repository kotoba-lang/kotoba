"Measurements for the whois-org-crawl bot.\n\nSame contract as company_evidence.py. Decision-free: syncs the worktree to\norigin/main and runs the wiki's own growth-evidence collector. REFUSED banner\non any failure so the bot is told it is blind, never that the wiki is complete.\n\n2026-09-13: collector moved to kbb cutover — scripts/wiki_growth_evidence.cljk\nis now run via `kbb --backend sci` with kotoba-lang/text on the classpath\n(nbb + the old .cljs path no longer exist on main).\n"
(import os)
(import subprocess)
(import sys)
(setv WORKTREE ((. os.environ get) "HYAKKA_BOT_WORKTREE" ((. os.path expanduser) "~/.itonami/worktrees/whois-org-crawl")))
(setv KBB ((. os.environ get) "HYAKKA_KBB" "/opt/homebrew/bin/kbb"))
(setv TEXT_SRC ((. os.environ get) "HYAKKA_TEXT_SRC" "~/github/com-junkawasaki/orgs/kotoba-lang/text/src"))
(setv DAYS ((. os.environ get) "HYAKKA_EVIDENCE_DAYS" "14"))
(defn refuse [why] (print "REFUSED — no evidence was gathered this run.") (print why) (print) (print "Do not propose anything. A growth proposal built on an unread tree is a proposal built on nothing. Report this refusal and stop.") (sys.exit 0))
(defn git [#* args] (return (subprocess.run (+ #("git" "-C" WORKTREE) args) :capture_output True :text True :timeout 300)))
(defn require-clean-worktree []
  (setv status (git "status" "--porcelain" "--untracked-files=all"))
  (when (!= status.returncode 0)
    (refuse f"could not inspect worktree status before checkout (git status exit {status.returncode})"))
  (when (. status.stdout strip)
    (refuse "worktree has local changes; refusing checkout to preserve tracked and untracked work")))

(defn main [] (when (not (or ((. os.path isdir) ((. os.path join) WORKTREE ".git")) ((. os.path exists) ((. os.path join) WORKTREE ".git")))) (refuse f"no git worktree at {WORKTREE}")) (setv fetch (git "fetch" "--quiet" "origin" "main")) (when (!= fetch.returncode 0) (refuse f"git fetch failed: {(cut ((. fetch.stderr strip)) 400)}")) (require-clean-worktree) (setv reset (git "checkout" "--quiet" "--detach" "FETCH_HEAD")) (when (!= reset.returncode 0) (refuse f"could not move to origin/main: {(cut ((. reset.stderr strip)) 400)}")) (setv head ((. (. (git "rev-parse" "--short" "HEAD") stdout) strip))) (setv collector ((. os.path join) WORKTREE "scripts" "wiki_growth_evidence.cljk")) (when (not ((. os.path exists) collector)) (refuse f"collector missing on main checkout: {collector}")) (when (not ((. os.path isdir) TEXT_SRC)) (refuse f"kotoba-lang/text src missing: {TEXT_SRC}")) (setv proc (subprocess.run [KBB "--backend" "sci" "--classpath" f"src:{TEXT_SRC}" collector "--summary" "--root" "." "--days" DAYS] :cwd WORKTREE :capture_output True :text True :timeout 600)) (when (= proc.returncode 2) (refuse (+ "the evidence collector refused:\n" (cut ((. proc.stderr strip)) 800)))) (when (!= proc.returncode 0) (refuse (+ f"the evidence collector exited {proc.returncode}:\n" (cut (or ((. proc.stderr strip)) ((. proc.stdout strip))) 800)))) (when (not-in "SCANNED\t" proc.stdout) (refuse "the collector produced no SCANNED line")) (print f"worktree\t{WORKTREE}") (print f"head\t{head}") (print ((. proc.stdout strip))))
(when (= __name__ "__main__") (main))
