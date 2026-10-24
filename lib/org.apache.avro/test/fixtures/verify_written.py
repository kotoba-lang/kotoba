"""Verify that files THIS REPO WRITES are accepted by the reference implementation.

`generate.py` points the oracle one way: fastavro writes, `avro.file/records`
reads, and the fixtures prove the decoder understands real Avro. This points it
the other way, and the asymmetry matters -- a round-trip test inside this repo
proves the writer and reader agree with each other, which two halves of one
misunderstanding also do. Only fastavro can say whether the bytes are Avro.

It runs the writer itself, so there is no checked-in fixture to go stale:

    python3 -m venv .venv && .venv/bin/pip install fastavro
    .venv/bin/python test/fixtures/verify_written.py

Exits non-zero on the first disagreement. Every type the encoder supports is
in the sample, including the ones whose failure is silent rather than loud:
a full-width 64-bit long (past 2^53, where a rounding writer still produces a
readable file), an empty array and map (whose block framing is a zero this
writer must emit and not omit), and a nullable union (where picking the wrong
branch yields a file that decodes without error into the wrong type).
"""
import json
import pathlib
import subprocess
import sys
import tempfile

import fastavro

REPO = pathlib.Path(__file__).resolve().parents[2]

SCHEMA = {
    "type": "record",
    "name": "Everything",
    "fields": [
        {"name": "i", "type": "int"},
        {"name": "l", "type": "long"},
        {"name": "f", "type": "float"},
        {"name": "d", "type": "double"},
        {"name": "b", "type": "boolean"},
        {"name": "s", "type": "string"},
        {"name": "by", "type": "bytes"},
        {"name": "fx", "type": {"type": "fixed", "name": "Md5", "size": 4}},
        {"name": "en", "type": {"type": "enum", "name": "Col",
                                "symbols": ["RED", "GREEN"]}},
        {"name": "arr", "type": {"type": "array", "items": "long"}},
        {"name": "mp", "type": {"type": "map", "values": "string"}},
        {"name": "nu", "type": ["null", "string"]},
        {"name": "sub", "type": {"type": "record", "name": "Sub",
                                 "fields": [{"name": "x", "type": "long"}]}},
    ],
}

EXPECTED = [
    {"i": 42, "l": 9007199254740993, "f": 1.5, "d": -2.25, "b": True,
     "s": "日本語", "by": b"\x01\x02\xff", "fx": b"\xde\xad\xbe\xef",
     "en": "GREEN", "arr": [1, -2, 3], "mp": {"k": "v", "k2": "v2"},
     "nu": None, "sub": {"x": 7}},
    {"i": -1, "l": -9007199254740993, "f": 0.0, "d": 0.0, "b": False,
     "s": "", "by": b"", "fx": b"\x00\x00\x00\x00",
     "en": "RED", "arr": [], "mp": {}, "nu": "here", "sub": {"x": -1}},
]

# The same records as Clojure literals. Bytes and fixed are vectors of
# unsigned bytes, which is the shape avro.datum decodes them into.
RECORDS_EDN = """
[{"i" 42 "l" 9007199254740993 "f" 1.5 "d" -2.25 "b" true "s" "日本語"
  "by" [1 2 255] "fx" [222 173 190 239] "en" "GREEN" "arr" [1 -2 3]
  "mp" {"k" "v" "k2" "v2"} "nu" nil "sub" {"x" 7}}
 {"i" -1 "l" -9007199254740993 "f" 0.0 "d" 0.0 "b" false "s" ""
  "by" [] "fx" [0 0 0 0] "en" "RED" "arr" [] "mp" {} "nu" "here"
  "sub" {"x" -1}}]
"""


def write_with_this_repo(out_dir: pathlib.Path, codec: str) -> pathlib.Path:
    """Drive avro.file/write on the JVM and return the file it produced."""
    path = out_dir / f"written-{codec}.avro"
    program = f"""
    (require '[avro.file :as f] '[clojure.java.io :as io])
    (let [bs (f/write {{:schema {json.dumps(json.dumps(SCHEMA))}
                        :records {RECORDS_EDN}
                        :codec "{codec}"
                        :records-per-block 1}})]
      (with-open [o (io/output-stream "{path}")]
        (.write o (byte-array (map unchecked-byte bs)))))
    """
    subprocess.run(["kbb", "-M", "-e", program], cwd=REPO, check=True,
                   stdout=subprocess.DEVNULL)
    return path


def main() -> int:
    failures = 0
    with tempfile.TemporaryDirectory() as tmp:
        out = pathlib.Path(tmp)
        # zstandard is omitted on purpose: org-ietf-zstd writes conformant
        # frames of RAW blocks, so this would test the frame header and
        # nothing about compression, while costing a dependency fastavro
        # only has optionally.
        for codec in ("null", "deflate"):
            path = write_with_this_repo(out, codec)
            try:
                with open(path, "rb") as fh:
                    reader = fastavro.reader(fh)
                    schema = reader.writer_schema
                    rows = list(reader)
            except Exception as exc:
                # A malformed file makes fastavro raise rather than return,
                # and an uncaught traceback reads like the harness broke
                # instead of the writer. Report it as the verdict it is.
                print(f"FAIL {codec}: fastavro refused the file: "
                      f"{type(exc).__name__}: {exc}")
                failures += 1
                continue

            if schema["name"] != SCHEMA["name"]:
                print(f"FAIL {codec}: schema name {schema['name']!r}")
                failures += 1
            if rows != EXPECTED:
                print(f"FAIL {codec}: records differ")
                for got, want in zip(rows, EXPECTED):
                    for k in want:
                        if got.get(k) != want[k]:
                            print(f"  {k}: got {got.get(k)!r} want {want[k]!r}")
                failures += 1
            else:
                print(f"ok   {codec}: fastavro read {len(rows)} records, all fields equal")

    print("VERIFIED against fastavro" if not failures else f"{failures} FAILURES")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
