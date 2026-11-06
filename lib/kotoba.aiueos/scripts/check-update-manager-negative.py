#!/usr/bin/env python3
"""Negative controls for check-update-manager.py (JUN-813).

Copies the files the check reads into a temporary directory, applies one deliberate mutation at a
time and requires the check to refuse it with the expected message. The unmutated copy must pass
first. Nothing in the repository is changed. Host-side, stdlib only.
"""
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
FILES = ("scripts/check-update-manager.py", "distributions/awai/update-policy.json", "distributions/awai/dapps/updates.json",
         "resources/aiueos/session/apps/updates.kotoba", "resources/aiueos/session/index.html",
         "os/aiueos/kotoba/aiueos/update_policy.kotoba")
DOC = "resources/aiueos/session/apps/updates.kotoba"
ENGINE = "os/aiueos/kotoba/aiueos/update_policy.kotoba"
POLICY = "distributions/awai/update-policy.json"
RECORD = "distributions/awai/dapps/updates.json"
PAGE = "resources/aiueos/session/index.html"


def edit(path, old, new):
    t = path.read_text(encoding="utf-8")
    assert old in t, (path, old)
    path.write_text(t.replace(old, new, 1), encoding="utf-8")


def edit_json(path, fn):
    d = json.loads(path.read_text(encoding="utf-8"))
    fn(d)
    path.write_text(json.dumps(d, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def policy_mode(d, i, key, value): d["modes"][i][key] = value


CONTROLS = [
    ("notify prompts a download in the engine", lambda t: edit(t / ENGINE, "(>= mode 2) (= stage 1) ok has-endpoint))", "(>= mode 1) (= stage 1) ok has-endpoint))"), "download prompt threshold"),
    ("manual prompts a check in the engine", lambda t: edit(t / ENGINE, "(= event 1) (>= mode 1) (= stage 0)", "(= event 1) (>= mode 0) (= stage 0)"), "check prompt threshold"),
    ("install prompt in auto-stage in the engine", lambda t: edit(t / ENGINE, "(= event 2) (= mode 3) (= stage 2) ok)", "(= event 2) (= mode 2) (= stage 2) ok)"), "install prompt threshold"),
    ("engine mode order changed", lambda t: edit(t / ENGINE, "0 manual, 1 notify", "0 notify, 1 manual"), "engine mode order"),
    ("policy file lets manual download after approval", lambda t: edit_json(t / POLICY, lambda d: policy_mode(d, 0, "download", "after-approval")), "download prompt threshold"),
    ("policy file default changes", lambda t: edit_json(t / POLICY, lambda d: d.__setitem__("default", "manual")), "default"),
    ("policy file consent weakened", lambda t: edit_json(t / POLICY, lambda d: d.__setitem__("consent", "once")), "consent must be each-operation"),
    ("record drops the install operation", lambda t: edit_json(t / RECORD, lambda d: d.pop("localOperations")), "record operations"),
    ("record operation consent weakened", lambda t: edit_json(t / RECORD, lambda d: d["remoteOperations"][0].__setitem__("consent", "once")), "consent must be each-operation"),
    ("record loses the unregistered-origin note", lambda t: edit_json(t / RECORD, lambda d: d["remoteOperations"][1].pop("endpointState")), "endpointState"),
    ("document loses a button", lambda t: edit(t / DOC, '"install-update" "この端末（ローカル書き込み）"', '"export-update" "この端末（ローカル書き込み）"'), "document request buttons"),
    ("document loses a policy radio", lambda t: edit(t / DOC, '(radio "auto-stage" "承認後に自動で取得")', ""), "document policy radios"),
    ("document loses the approval sentence", lambda t: edit(t / DOC, "確認・取得・適用は、それぞれ毎回承認します", "確認・取得・適用は、まとめて承認します"), "per-operation approval"),
    ("document names an origin", lambda t: edit(t / DOC, "更新元の接続先はまだ登録されていません", "更新元は https://updates.example.com です"), "URL or host name"),
    ("record names an origin", lambda t: edit_json(t / RECORD, lambda d: d["remoteOperations"][0].__setitem__("endpoint", "https://updates.example.net")), "URL or host name"),
    ("page lacks the install button", lambda t: edit(t / PAGE, 'data-op="install-update"', 'data-op="x-update"'), "does not carry the three operation buttons"),
    ("a kernel file requires the engine", lambda t: (t / "os/aiueos/native").mkdir(parents=True) or (t / "os/aiueos/native/x.kotoba").write_text("(ns x (:require [aiueos.update-policy :as p]))\n", encoding="utf-8"), "must stay out of the kernel images"),
    ("engine reads the kernel", lambda t: edit(t / ENGINE, "(defn b [x :bool] :i64 (if x 1 0))", "(defn b [x :bool] :i64 (if x (kernel-tsc) 0))"), "pure function"),
]


def run(tree):
    r = subprocess.run([sys.executable, "-I", str(tree / "scripts/check-update-manager.py"), str(tree)], capture_output=True, text=True)
    return r.returncode, (r.stdout + r.stderr).strip()


def main():
    with tempfile.TemporaryDirectory() as tmp:
        base = pathlib.Path(tmp) / "base"
        for rel in FILES:
            (base / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / rel, base / rel)
        code, out = run(base)
        if code != 0:
            sys.exit("NEGATIVE_CONTROL_FAIL unmutated copy is refused: " + out)
        bad = 0
        for i, (label, mutate, want) in enumerate(CONTROLS):
            tree = pathlib.Path(tmp) / ("c%d" % i)
            shutil.copytree(base, tree)
            mutate(tree)
            code, out = run(tree)
            ok = code != 0 and want in out
            bad += not ok
            print("%s %s: %s" % ("REFUSED" if ok else "NOT_REFUSED", label, out.splitlines()[-1] if out else "(no output)"))
        if bad:
            sys.exit("NEGATIVE_CONTROL_FAIL %d of %d not refused" % (bad, len(CONTROLS)))
        print("AIUEOS_UPDATE_MANAGER_NEGATIVE_OK controls=%d" % len(CONTROLS))


main()
