"""Validate every XML file in a directory against the pinned ISO 20022 XSDs.

Usage: python3 -I summarize.py <xml-dir> <xsd-dir> <summary.json>

The XSD is chosen from the document's default namespace. Files whose
namespace has no pinned XSD are counted as "no-xsd". Error lines are
grouped after removing the namespace and the offending value, so the
summary shows each kind of mismatch once with a count.
"""

from __future__ import annotations

import collections
import json
import pathlib
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

NS = re.compile(r"\{urn:iso:std:iso:20022:tech:xsd:[a-z0-9.]*\}")
VALUE = re.compile(r"'[^']*' is not (a valid value|accepted)", re.S)


def main(xml_dir: str, xsd_dir: str, out: str) -> int:
    xsd = pathlib.Path(xsd_dir)
    result: dict[str, dict] = {}
    for path in sorted(pathlib.Path(xml_dir).glob("*.xml")):
        try:
            root = ET.parse(path).getroot()
        except ET.ParseError:
            key = "unparseable"
            result.setdefault(key, {"files": 0, "valid": 0, "no-xsd": 0, "errors": collections.Counter()})
            result[key]["files"] += 1
            continue
        tag = root.tag
        message = tag[1:].split("}")[0].rsplit(":", 1)[-1] if tag.startswith("{") else tag
        entry = result.setdefault(message, {"files": 0, "valid": 0, "no-xsd": 0, "errors": collections.Counter()})
        entry["files"] += 1
        schema = xsd / f"{message}.xsd"
        if not schema.exists():
            entry["no-xsd"] += 1
            continue
        proc = subprocess.run(["xmllint", "--noout", "--schema", str(schema), str(path)],
                              capture_output=True, text=True)
        if proc.returncode == 0:
            entry["valid"] += 1
            continue
        for line in VALUE.sub(r"VALUE is not \1", proc.stderr).splitlines():
            if "validity error : " in line:
                entry["errors"][NS.sub("", line.split("validity error : ", 1)[1]).strip()] += 1
    summary = {
        message: {**{k: v for k, v in entry.items() if k != "errors"},
                  "errors": [{"count": c, "error": e} for e, c in entry["errors"].most_common()]}
        for message, entry in sorted(result.items())
    }
    pathlib.Path(out).write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for message, entry in summary.items():
        print(f"{message}: files={entry['files']} valid={entry['valid']} no-xsd={entry['no-xsd']}")
        for err in entry["errors"][:12]:
            print(f"  {err['count']:5d}  {err['error']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:4]))
