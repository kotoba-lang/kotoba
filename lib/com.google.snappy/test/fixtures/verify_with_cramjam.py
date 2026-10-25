"""Point the oracle both ways against a reference snappy implementation.

A round-trip inside this repo proves the compressor and the decompressor
agree, which two halves of one misunderstanding also do. Snappy makes that
failure quiet: a stream with a wrong copy offset still decodes, into different
bytes, and only a second implementation notices.

    python3 -m venv .venv && .venv/bin/pip install cramjam
    .venv/bin/python test/fixtures/verify_with_cramjam.py

Both directions are checked, because they fail independently:
  ours -> theirs   a malformed element we happen to read back correctly
  theirs -> ours   an element shape our encoder never emits and cannot read

Every case goes through ONE `kbb -M` invocation. Starting a JVM costs
about twenty seconds on this machine; per-case invocation turned a
thirty-second check into one that could not finish in ten minutes.
"""
import json
import pathlib
import random
import subprocess
import sys
import tempfile

import cramjam

REPO = pathlib.Path(__file__).resolve().parents[2]

random.seed(20260830)

CASES = {
    "empty": b"",
    "one-byte": b"x",
    "short": b"hello",
    "repeat": b"A" * 500,
    "text": b"the quick brown fox jumps over the lazy dog " * 40,
    # A run whose period is shorter than the match: the copy references bytes
    # it is still producing, which is the subtlety the namespace docstring names.
    "overlapping-run": b"ab" * 300,
    # Long enough to need a multi-byte literal length and copies over 64 bytes.
    "incompressible": bytes(random.randrange(256) for _ in range(5000)),
    "mixed": (b"header," * 20) + bytes(random.randrange(256) for _ in range(400)) + (b"footer," * 20),
    # Past the 65535 window: the encoder must either use the 4-byte copy form
    # or decline the match. Either is correct; this checks it does one of them.
    "far-match": (b"Z" * 70000) + b"the quick brown fox " * 10,
}


def run_ours(work: pathlib.Path) -> dict:
    cases_in = work / "in.edn"
    result = work / "out.edn"

    # EDN, not JSON. JSON's `"key": value` colon is not valid EDN -- the
    # reader takes the colon as the start of a keyword and fails. Writing EDN
    # here means neither side needs a JSON library or a syntax translation.
    def edn_bytes(bs) -> str:
        return "[" + " ".join(str(b) for b in bs) + "]"

    cases_in.write_text("{" + " ".join(
        f'"{k}" {{"raw" {edn_bytes(v)} '
        f'"theirs" {edn_bytes(bytes(cramjam.snappy.compress_raw(v)))}}}'
        for k, v in CASES.items()) + "}")

    # EDN in, JSON out. Each side writes the syntax the OTHER side reads
    # natively, so neither needs a library and there is no translation step to
    # get wrong -- the first two attempts here failed in exactly that step,
    # once in each direction.
    program = f"""
    (require '[snappy.core :as s] '[clojure.string :as str])
    (let [in (read-string (slurp "{cases_in}"))
          ints (fn [v] (str "[" (str/join "," v) "]"))]
      (spit "{result}"
        (str "{{"
             (str/join ","
               (map (fn [[k v]]
                      (str (pr-str k) ":{{"
                           "\\"ours\\":" (ints (s/compress (get v "raw"))) ","
                           "\\"back\\":" (ints (s/decompress (get v "theirs")))
                           "}}"))
                    in))
             "}}")))
    """
    r = subprocess.run(["kbb", "-M", "-e", program], cwd=REPO,
                       capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr[-2000:], file=sys.stderr)
        raise SystemExit("the clojure side failed; stderr above")

    return json.loads(result.read_text())


def main() -> int:
    failures = 0
    with tempfile.TemporaryDirectory() as tmp:
        got = run_ours(pathlib.Path(tmp))

    for name, data in CASES.items():
        entry = got.get(name)
        if entry is None:
            print(f"FAIL {name}: no result")
            failures += 1
            continue
        ours = bytes(entry["ours"])
        back = bytes(entry["back"])

        try:
            theirs_back = bytes(cramjam.snappy.decompress_raw(ours))
        except Exception as exc:
            print(f"FAIL {name}: cramjam refused our output: {type(exc).__name__}: {exc}")
            failures += 1
            continue
        if theirs_back != data:
            print(f"FAIL {name}: cramjam decoded ours to different bytes "
                  f"({len(theirs_back)} vs {len(data)})")
            failures += 1
            continue
        if back != data:
            print(f"FAIL {name}: we decoded cramjam's output to different bytes")
            failures += 1
            continue

        theirs = bytes(cramjam.snappy.compress_raw(data))
        ratio = len(ours) / len(data) if data else 0.0
        print(f"ok   {name:<16} in={len(data):<7} ours={len(ours):<7} "
              f"theirs={len(theirs):<7} ratio={ratio:.2f}")

    print("VERIFIED against cramjam" if not failures else f"{failures} FAILURES")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
