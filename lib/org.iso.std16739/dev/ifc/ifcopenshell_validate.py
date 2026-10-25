"""Strict IfcOpenShell schema/WHERE-rule gate for generated IFC files."""

import json
import re
import sys
from collections import Counter

import ifcopenshell.validate


def validate(path: str) -> list[dict]:
    logger = ifcopenshell.validate.json_logger()
    ifcopenshell.validate.validate(path, logger, express_rules=True)
    return [statement for statement in logger.statements if statement.get("level") == "error"]


def error_signature(error: dict) -> tuple[str, str, str]:
    """Stable validator signature independent of regenerated STEP ids."""
    message = str(error.get("message", ""))
    if "IfcGloballyUniqueId base64 validation" in message:
        reason = "invalid-global-id"
    elif "Attribute not optional" in message:
        reason = "required-attribute"
    elif "Not valid" in message:
        reason = "invalid-value"
    else:
        rule = re.search(r"(?:Rule |Violated by:\s*\n\s*)([^\n]+)", message)
        reason = re.sub(r"#\d+", "#", rule.group(1) if rule else message.splitlines()[0])
    return (str(error.get("type", "unknown")), str(error.get("attribute", "")), reason)


def compare(baseline_path: str, candidate_path: str) -> list[dict]:
    baseline = validate(baseline_path)
    candidate = validate(candidate_path)
    baseline_counts = Counter(error_signature(error) for error in baseline)
    remaining = baseline_counts.copy()
    new_errors = []
    for error in candidate:
        signature = error_signature(error)
        if remaining[signature]:
            remaining[signature] -= 1
        else:
            new_errors.append(error)
    print(json.dumps({"baseline": baseline_path, "candidate": candidate_path,
                      "baseline_errors": len(baseline),
                      "candidate_errors": len(candidate),
                      "new_errors": len(new_errors)}, ensure_ascii=False))
    return new_errors


def main(paths: list[str]) -> int:
    failures = []
    if paths and paths[0] == "--pairs":
        pair_paths = paths[1:]
        if len(pair_paths) % 2:
            raise SystemExit("--pairs requires baseline/candidate path pairs")
        for baseline, candidate in zip(pair_paths[::2], pair_paths[1::2]):
            errors = compare(baseline, candidate)
            failures.extend({"file": candidate, **error} for error in errors)
        if failures:
            print(json.dumps({"failures": failures}, ensure_ascii=False, default=str))
            return 1
        return 0
    for path in paths:
        errors = validate(path)
        print(json.dumps({"file": path, "errors": len(errors)}, ensure_ascii=False))
        failures.extend({"file": path, **error} for error in errors)
    if failures:
        print(json.dumps({"failures": failures}, ensure_ascii=False, default=str))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
