#!/usr/bin/env python3
"""Check the Updates manager's record, UI document, policy file and policy engine against each other (JUN-813).

Host-side, stdlib only, reads text and JSON: no Amu, JVM, nbb, Node, babashka or GraalVM. It does NOT run the
policy engine (scripts/check-update-policy-native.py does, with Amu). It refuses when:
  - the engine's mode order or its prompt thresholds differ from distributions/awai/update-policy.json
    (check "scheduled-prompt" -> the first mode that lets a tick prompt a check; download/install
    "after-approval" / "after-approval-at-next-boot" -> the first mode that prompts them);
  - the record's operations are not exactly check-updates, download-update, install-update, each with
    consent each-operation, a service, an endpoint and data categories;
  - the UI document does not carry exactly those three request buttons, or a policy radio per mode id;
  - any of the record, the document, the policy file or the engine contains a URL or host name
    (no update origin is registered: a placeholder must not look like one);
  - the engine is required by any file under os/ (it must stay out of every kernel image);
  - the engine takes a clock, a network or a storage primitive.

usage: check-update-manager.py [ROOT]   ROOT defaults to the lib/kotoba.aiueos this script is in.
"""
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else pathlib.Path(__file__).resolve().parent.parent
RECORD = ROOT / "distributions/awai/dapps/updates.json"
POLICY = ROOT / "distributions/awai/update-policy.json"
DOC = ROOT / "resources/aiueos/session/apps/updates.kotoba"
PAGE = ROOT / "resources/aiueos/session/index.html"
ENGINE = ROOT / "os/aiueos/kotoba/aiueos/update_policy.kotoba"
OPS = ["check-updates", "download-update", "install-update"]
URL = re.compile(r"(?i)\b(?:https?|wss?|ftp)://|\b[a-z0-9-]+(?:\.[a-z0-9-]+)*\.(?:com|net|org|io|app|dev|jp|invalid|example|test|local)\b")
FORBIDDEN_PRIMITIVES = re.compile(r"\((?:kernel-[a-z0-9-]+|rtc-now|tsc-[a-z0-9-]+|http-[a-z0-9-]+|fetch|open|read-file|write-file)[\s)]")


def fail(msg):
    print("AIUEOS_UPDATE_MANAGER_FAIL " + msg)
    sys.exit(1)


def read(path):
    if not path.is_file():
        fail("missing %s" % path.relative_to(ROOT))
    return path.read_text(encoding="utf-8")


def main():
    policy = json.loads(read(POLICY))
    record = json.loads(read(RECORD))
    doc = read(DOC)
    engine = read(ENGINE)
    modes = [m["id"] for m in policy["modes"]]
    by_id = {m["id"]: m for m in policy["modes"]}

    # 1. engine mode order and thresholds against the policy file
    m = re.search(r"mode: 0 (\S+) 1 (\S+) \(default\) 2 (\S+) 3 (\S+)\n", engine.replace(",", ""))
    if not m or list(m.groups()) != modes:
        fail("engine mode order %s differs from update-policy.json %s" % (list(m.groups()) if m else None, modes))
    if policy["default"] != modes[1]:
        fail("engine documents notify (1) as the default; update-policy.json default is %r" % policy["default"])

    def first(pred):
        for i, mid in enumerate(modes):
            if pred(by_id[mid]):
                return i
        return None

    want_check = first(lambda x: x["check"] == "scheduled-prompt")
    want_download = first(lambda x: x["download"] == "after-approval")
    want_install = first(lambda x: x["install"] == "after-approval-at-next-boot")
    for what, want, pattern in (
        ("check prompt", want_check, r"prompt-check \(b \(and \(= event 1\) \(>= mode (\d)\)"),
        ("download prompt", want_download, r"prompt-download \(b \(and .*?\(>= mode (\d)\)"),
        ("install prompt", want_install, r"prompt-install \(b \(and \(= event 2\) \(= mode (\d)\)"),
    ):
        g = re.search(pattern, engine)
        if want is None or not g or int(g.group(1)) != want:
            fail("%s threshold: engine %s, update-policy.json says mode index %s" % (what, g and g.group(1), want))
    # user-starts everywhere: the manual mode must have no prompt at all, in the file and in the engine
    manual = by_id[modes[0]]
    if (manual["check"], manual["download"], manual["install"]) != ("user-starts",) * 3:
        fail("update-policy.json: the first mode must be user-starts for all three operations")
    if policy.get("consent") != "each-operation":
        fail("update-policy.json: consent must be each-operation")
    if "only raise a prompt" not in policy.get("background", ""):
        fail("update-policy.json: background no longer says a schedule may only raise a prompt")

    # 2. record operations
    ops = [o for key in ("remoteOperations", "localOperations") for o in record.get(key, [])]
    names = [o["operation"] for o in ops]
    if names != OPS:
        fail("record operations are %s, want %s (remote then local)" % (names, OPS))
    for o in ops:
        for key in ("service", "endpoint", "data", "consent", "state"):
            if not o.get(key):
                fail("%s lacks %s" % (o["operation"], key))
        if o["consent"] != "each-operation":
            fail("%s consent must be each-operation" % o["operation"])
    for o in record["remoteOperations"]:
        if "endpointState" not in o or "no update origin registered" not in o["endpointState"]:
            fail("%s: endpointState must say no update origin is registered" % o["operation"])

    # 3. UI document: three request buttons, one radio per mode id, the per-operation approval sentence
    buttons = re.findall(r'\(u/request-button "[^"]+" "([a-z-]+)" "[^"]+"\)', doc)
    if buttons != OPS:
        fail("document request buttons are %s, want %s" % (buttons, OPS))
    radios = re.findall(r'\(radio "([a-z-]+)" "', doc)
    if radios != modes:
        fail("document policy radios are %s, want %s" % (radios, modes))
    if "確認・取得・適用は、それぞれ毎回承認します" not in doc or "予定が出すのは確認のプロンプトだけ" not in doc:
        fail("document lost the per-operation approval or schedule-prompt sentence")
    if not PAGE.is_file() or any(('data-op="%s"' % op) not in PAGE.read_text(encoding="utf-8") for op in OPS):
        fail("index.html does not carry the three operation buttons (rebuild: session-page.py build)")

    # 4. no URL or host name anywhere an origin could hide
    for label, text in (("record", json.dumps(record)), ("document", doc), ("update-policy.json", json.dumps(policy)), ("engine", engine)):
        hit = URL.search(text)
        if hit:
            fail("%s contains a URL or host name (%r): no update origin is registered" % (label, hit.group(0)))

    # 5. the engine stays out of every image and takes no clock, network or storage
    required = []
    for path in sorted((ROOT / "os").rglob("*.kotoba")):
        if path != ENGINE and "aiueos.update-policy" in path.read_text(encoding="utf-8", errors="replace"):
            required.append(str(path.relative_to(ROOT)))
    if required:
        fail("os/ files mention aiueos.update-policy (the engine must stay out of the kernel images): %s" % required)
    body = "\n".join(l for l in engine.splitlines() if not l.lstrip().startswith(";;"))
    prim = FORBIDDEN_PRIMITIVES.search(body)
    if prim:
        fail("engine uses %s: it must be a pure function" % prim.group(0))
    print("AIUEOS_UPDATE_MANAGER_OK modes=%d operations=%d" % (len(modes), len(OPS)))


main()
