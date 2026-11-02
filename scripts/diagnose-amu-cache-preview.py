#!/usr/bin/env python3
"""Observe one fixed branch-scoped Amu cache across repositories.

This diagnostic is not a production cache, whole-compiler gate, or fallback.
The candidate artifact expires; it is not a source of current CI verdicts.
"""
import argparse
import os
import tempfile
from pathlib import Path

REPO = "kotoba-lang/amu"
REPO_ID = 1297097065
RUN_ID = 41425465587
ARTIFACT_ID = 13132351777
SHA = "a51cfd729c2b82db53700cc27589b7c7ee446824"
BRANCH = "codex/jun-358-attested-producer-20261102"
BUNDLE_SHA = "ef0f6d38c4f402ca9bc6a1c9d3850e783821533ca883be48b028b8c2ca8face2"
ZIP_SHA = "sha256:f58c57477d26e3fe057a0068b429815b521b05f3c831019e356409a28c33c8d8"
WORKFLOW = ".github/workflows/bounded-cache-preview.yml"


def main(amu, gh, output):
    import sys
    sys.path.insert(0, str((amu / "scripts/seed").resolve()))
    from bounded_cache_bundle import verified_extract
    from check_bounded_producer_attestation import GH_SHA256, exercise
    from fetch_bounded_cache import _call, _download, _unzip_exact
    from sealed_image import sealed_image
    from verified_attestation import AttestationPolicy

    output.mkdir(mode=0o700)
    output = output.resolve()
    os.chmod(output, 0o700)
    with tempfile.TemporaryDirectory(prefix="cross-cache-gh-", dir=output) as config:
        env = dict(PATH="/usr/bin:/bin", GH_HOST="github.com", GH_PROMPT_DISABLED="1",
                   HOME=config, GH_CONFIG_DIR=config, GH_TOKEN=os.environ["GH_TOKEN"])
        with sealed_image(gh, GH_SHA256) as (gh_fd, _):
            run = _call(gh_fd, env, f"repos/{REPO}/actions/runs/{RUN_ID}")
            if not (run.get("id") == RUN_ID and run.get("event") == "push" and
                    run.get("status") == "completed" and run.get("conclusion") == "success" and
                    run.get("head_branch") == BRANCH and run.get("head_sha") == SHA and
                    run.get("path") == WORKFLOW and run.get("repository", {}).get("id") == REPO_ID and
                    run.get("head_repository", {}).get("id") == REPO_ID):
                raise ValueError("preview run identity mismatch")
            artifact = _call(gh_fd, env, f"repos/{REPO}/actions/artifacts/{ARTIFACT_ID}")
            ref = artifact.get("workflow_run") or {}
            if not (artifact.get("id") == ARTIFACT_ID and artifact.get("name") == "experimental-preview-" + SHA and
                    artifact.get("expired") is False and artifact.get("digest") == ZIP_SHA and
                    type(artifact.get("size_in_bytes")) is int and 0 < artifact["size_in_bytes"] <= 128 * 1024 * 1024 and
                    ref.get("id") == RUN_ID and ref.get("repository_id") == REPO_ID and
                    ref.get("head_repository_id") == REPO_ID and ref.get("head_branch") == BRANCH and ref.get("head_sha") == SHA):
                raise ValueError("preview artifact identity mismatch")
            archive = output / "artifact.zip"
            _download(gh_fd, env, artifact, archive)
    bundle = output / "bounded-cache.tar"
    _unzip_exact(archive, bundle)
    policy = AttestationPolicy(REPO, str(REPO_ID), WORKFLOW, "refs/heads/" + BRANCH, SHA, SHA, "push")
    image, objects, image_digest, bundle_digest = verified_extract(bundle, gh, GH_SHA256, policy, output / "cache")
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
