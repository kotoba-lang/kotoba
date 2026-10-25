"""CLI: python -m arxiv_submit --package submissions/sqrt-space-kv

Env:
  ARXIV_USER / ARXIV_PASSWORD   required (from 1Password)
  APPROVE_FINAL=1               allow public Submit click
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

from .flow import ArxivSubmitFlow
from .package import (
    load_package,
    load_status,
    resolve_abstract,
    resolve_archive,
    write_status,
)


def _repo_root() -> Path:
    # browser/arxiv_submit/__main__.py → arxiv repo root
    return Path(__file__).resolve().parents[2]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="arXiv browser submitter (kotoba-lang/arxiv actor runner)"
    )
    ap.add_argument(
        "--package",
        required=True,
        help="path to package dir or package.edn (e.g. submissions/sqrt-space-kv)",
    )
    ap.add_argument("--headed", action="store_true")
    ap.add_argument(
        "--stop-after",
        choices=[
            "login",
            "start-open",
            "start",
            "endorsement",
            "upload",
            "metadata",
            "final",
        ],
        default="final",
        help="stop pipeline after this stage (default: final, still gated)",
    )
    ap.add_argument(
        "--resume-draft",
        default=None,
        help="resume existing /submit/<id>/start instead of START NEW",
    )
    ap.add_argument(
        "--archive",
        default=None,
        help="override primary archive (default cs for cs.LG)",
    )
    ap.add_argument(
        "--subject-class",
        default=None,
        help="override subject class (default from package primary)",
    )
    args = ap.parse_args(argv)

    user = os.environ.get("ARXIV_USER") or os.environ.get("ARXIV_USERNAME")
    password = os.environ.get("ARXIV_PASSWORD")
    if not user or not password:
        print(
            "ERROR: set ARXIV_USER and ARXIV_PASSWORD "
            "(e.g. op item get 'Arxiv - N24' --vault Private --fields username,password --reveal)",
            file=sys.stderr,
        )
        return 2

    pkg_path = Path(args.package)
    if pkg_path.is_dir():
        package_edn = pkg_path / "package.edn"
        status_edn = pkg_path / "status.edn"
        pkg_root = pkg_path
    else:
        package_edn = pkg_path
        status_edn = pkg_path.parent / "status.edn"
        pkg_root = pkg_path.parent

    if not package_edn.exists():
        print(f"ERROR: package.edn not found at {package_edn}", file=sys.stderr)
        return 2

    repo = _repo_root()
    pkg = load_package(package_edn)
    status = load_status(status_edn)
    abstract = resolve_abstract(pkg)
    try:
        tar = resolve_archive(pkg, repo)
    except FileNotFoundError:
        # also try package-local build/
        tar = resolve_archive(pkg, pkg_root)

    primary = args.subject_class or pkg["primary"] or "cs.LG"
    # archive is first segment for cs.* 
    archive = args.archive or (primary.split(".")[0] if "." in primary else "cs")
    subject = primary if primary.startswith("cs.") else f"cs.{primary}" if archive == "cs" else primary

    resume = args.resume_draft or status.get("draft_id")
    approve = os.environ.get("APPROVE_FINAL") == "1"
    stop = None if args.stop_after == "final" else args.stop_after

    shot_dir = pkg_root / "build" / "screenshots"
    shot_dir.mkdir(parents=True, exist_ok=True)

    print(
        json.dumps(
            {
                "account": user,
                "package": str(package_edn),
                "tar": str(tar),
                "archive": archive,
                "subject": subject,
                "resume": resume,
                "approve_final": approve,
                "stop_after": args.stop_after,
            },
            indent=2,
        ),
        flush=True,
    )

    flow = ArxivSubmitFlow(
        user=user,
        password=password,
        title=pkg["title"] or "Untitled",
        abstract=abstract,
        archive=archive,
        subject_class=subject,
        comments=pkg.get("comments") or "",
        source_tar=tar,
        shot_dir=shot_dir,
        headed=args.headed,
        approve_final=approve,
        resume_draft_id=resume,
    )
    result = flow.run(stop_after=stop)

    out_json = pkg_root / "build" / "submit-result.json"
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(result.to_dict(), indent=2), encoding="utf-8")
    print(json.dumps(result.to_dict(), indent=2), flush=True)

    # persist status.edn for actor plan-submission
    state = result.status
    if state == "ok":
        if "pending-human-final-submit" in result.steps:
            state = "pending-human-final-submit"
        elif "upload-source" in result.steps:
            state = "uploaded"
        elif "start-ok" in result.steps:
            state = "start-complete"
        else:
            state = "draft"
    if state == "submitted":
        state = "submitted"
    if state == "pending-endorsement":
        state = "pending-endorsement"
    if state == "error":
        state = "draft"

    notes = [
        f"browser runner steps: {result.steps}",
        f"error: {result.error}" if result.error else "no error",
        f"source: {tar}",
        "final-submit requires APPROVE_FINAL=1 + human policy gate",
    ]
    if result.status == "pending-endorsement":
        notes.extend(
            [
                f"endorsement-help: {result.endorsement_help_url}",
                f"endorsement-request: {result.endorsement_url}",
                f"endorsement-category: {result.endorsement_category}",
                f"endorsement-code: {result.endorsement_code}",
                "Forward the arXiv endorsement email (with code) to a qualified endorser.",
                "Do not switch to an unrelated archive solely to bypass endorsement.",
            ]
        )

    write_status(
        status_edn,
        {
            "id": str(pkg.get("id") or "submission").lstrip(":"),
            "state": state,
            "draft_id": result.draft_id or resume,
            "url": result.url or "https://arxiv.org/user/",
            "account": user,
            "email": os.environ.get("ARXIV_EMAIL"),
            "primary": subject,
            "cross_lists": pkg.get("cross_lists") or [],
            "updated_at": date.today().isoformat(),
            "notes": notes,
        },
    )
    print(f"[wrote] {status_edn}", flush=True)
    print(f"[wrote] {out_json}", flush=True)

    # pending-* are successful stops of the runner (human/policy gates)
    if result.status == "error":
        return 1
    if result.status == "pending-endorsement":
        return 3  # distinct for scripts; still non-crash for status tracking
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
