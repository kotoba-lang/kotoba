#!/usr/bin/env python3 -I
"""Apply the etzhayyim rename map to ONE repository working tree (JUN-842, P1).

  etzhayyim-rename-apply.py <map.json> <owners.json> <repo-dir> <org> --layer inert|impact [--write]

  --layer inert   no rule: the pilot showed that nothing the map rewrites is inert (com-etzhayyim-* names turned out to be
                  deployed cell ids, `:legacy-cell "com-etzhayyim-isekai-craftItem"`). Prose wording is decided by hand.
  --layer impact  every rule with a target: name-com-prefix, nsid-*, wit, jsonld-context, vanity-url, npm-scope, purl.
  default is a DRY RUN that prints what would change; --write edits the files in place (nothing is committed).

<org> is the organisation directory of the repository (kotoba-lang | network-awai | cloud-itonami); it selects the
`targets` row. A lexicon NSID or a WIT package takes its target from the organisation that DEFINES it (owners.json: lexicon ids, and "wit:<ns>:<name>" keys),
falling back to <org> when no definition was found (reported). Tokens the map marks mint / decide / lookup / keep are never
touched and are counted in the summary, so what is left is visible. Only tracked text files are read.
"""
import collections, json, os, re, subprocess, sys

argv = sys.argv[1:]
if "--layer" not in argv or argv.index("--layer") + 1 >= len(argv):
    sys.exit(__doc__)
li = argv.index("--layer")
layer = argv[li + 1]
a = [x for i, x in enumerate(argv) if not x.startswith("--") and i != li + 1]
if len(a) != 4:
    sys.exit(__doc__)
mapfile, ownfile, repo, org = a[:4]
write = "--write" in sys.argv
spec = json.load(open(mapfile, encoding="utf-8"))
owners = json.load(open(ownfile, encoding="utf-8"))
targets = spec["targets"]
rules = [(r, re.compile(r["match"], re.I)) for r in spec["rules"]]
tokrx = re.compile(spec["token"], re.I)
LAYERS = {"inert": set(), "impact": {"name-com-prefix", "nsid-kotoba", "nsid-apps", "nsid-generic", "wit", "jsonld-context", "vanity-url", "npm-scope", "purl"}}
if layer not in LAYERS:
    sys.exit("layer must be inert or impact")
NSID = re.compile(r"(?:com|app)\.etzhayyim\.[A-Za-z0-9_.]+", re.I)


WITPKG = re.compile(r"^(etzhayyim:[a-z0-9-]+)", re.I)


def owner_for(tok):
    w = WITPKG.match(tok)
    if w and ("wit:" + w.group(1).lower()) in owners:
        return owners["wit:" + w.group(1).lower()], True
    m = NSID.search(tok)
    if m:
        t, best = m.group(0), None
        for lid, o in owners.items():
            if t == lid or t.startswith(lid + ".") or lid.startswith(t + "."):
                if best is None or len(lid) > len(best[0]):
                    best = (lid, o)
        if best:
            return best[1], True
    return org, False


def rewrite_token(tok, counts):
    for _ in range(4):
        hit = next(((r, rx) for r, rx in rules if rx.search(tok)), None)
        if not hit:
            return tok
        r, rx = hit
        if r["id"] not in LAYERS[layer]:
            counts["left:" + r["id"] + ":" + r["status"]] += 1
            return tok
        own, found = owner_for(tok) if (r["id"].startswith("nsid") or r["id"] == "wit") else (org, True)
        if (r["id"].startswith("nsid") or r["id"] == "wit") and not found:
            counts["owner-guess"] += 1
        t = targets.get(own) or {}
        to = r["to"]
        for k in ("nsid", "wit", "domain", "npm"):
            if "{" + k + "}" in to:
                if t.get(k) is None:
                    counts["undecided-target:" + r["id"] + ":" + own] += 1
                    return tok
                to = to.replace("{" + k + "}", t[k])
        new = rx.sub(to, tok, count=1)
        if new == tok:
            return tok
        counts["rewrote:" + r["id"]] += 1
        tok = new
    return tok


counts = collections.Counter()
files = subprocess.run(["git", "-C", repo, "ls-files", "-z"], capture_output=True).stdout.split(b"\0")
changed = 0
for f in files:
    if not f:
        continue
    path = os.path.join(repo, f.decode("utf-8", "replace"))
    try:
        raw = open(path, "rb").read()
    except OSError:
        continue
    if b"\0" in raw or b"etzhayyim" not in raw.lower():
        continue
    text = raw.decode("utf-8", "replace")
    new = tokrx.sub(lambda m: rewrite_token(m.group(0), counts), text)
    if new != text:
        changed += 1
        if write:
            open(path, "wb").write(new.encode("utf-8"))
        print(("wrote " if write else "would change ") + f.decode("utf-8", "replace"))
print("files changed:", changed, "(written)" if write else "(dry run)")
for k, v in sorted(counts.items()):
    print(f"  {k}: {v}")
