#!/usr/bin/env python3
"""Observe one fixed branch-scoped Amu cache across repositories.

This diagnostic is not a production cache, whole-compiler gate, or fallback.
The candidate artifact expires; it is not a source of current CI verdicts.
"""
import argparse
import os
from pathlib import Path

REPO = "kotoba-lang/amu"
REPO_ID = 1297097065
SHA = "a51cfd729c2b82db53700cc27589b7c7ee446824"
BRANCH = "codex/jun-358-attested-producer-20261102"
BUNDLE_SHA = "ef0f6d38c4f402ca9bc6a1c9d3850e783821533ca883be48b028b8c2ca8face2"
WORKFLOW = ".github/workflows/bounded-cache-preview.yml"


def main(amu, gh, output):
    import sys
    sys.path.insert(0, str((amu / "scripts/seed").resolve()))
    from check_bounded_producer_attestation import GH_SHA256, exercise
    from fetch_bounded_cache import _fetch_with_policy
    from verified_attestation import AttestationPolicy

    output.mkdir(mode=0o700)
    output = output.resolve()
    os.chmod(output, 0o700)
    policy = AttestationPolicy(REPO, str(REPO_ID), WORKFLOW, "refs/heads/" + BRANCH, SHA, SHA, "push")
    image, objects, image_digest, bundle_digest = _fetch_with_policy(policy, "experimental-preview-", gh,
                                                                     GH_SHA256, output / "cache")
    if bundle_digest != BUNDLE_SHA:
        raise ValueError("unexpected preview bundle")
    exercise(image, objects, image_digest, output)
    print("PASS_CROSS_REPOSITORY_SIGNED_BOUNDED_CACHE", SHA, bundle_digest, flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--amu", type=Path, required=True)
    parser.add_argument("--gh", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    main(args.amu.resolve(), args.gh.resolve(), args.output)
