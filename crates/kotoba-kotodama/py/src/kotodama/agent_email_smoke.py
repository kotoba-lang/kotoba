from __future__ import annotations

import argparse
import json
import os
from typing import Any

from kotodama.primitives import active_inference


def build_autonomous_email_plan(
    *,
    agent_did: str,
    to: str,
    subject: str,
    text: str,
    authority_ref: str,
    policy_ref: str,
) -> dict[str, Any]:
    payload = {"to": to, "subject": subject, "text": text}
    classified = active_inference.classify_real_world_effect(
        channel="email",
        effect_class="private_send",
        payload=payload,
        agent_did=agent_did,
        target_ref=f"mailto:{to}",
        autonomous_authority_ref=authority_ref,
        summary=subject,
    )
    return active_inference.plan_real_world_dispatch(
        real_world_effect=classified["realWorldEffect"],
        payload=payload,
        policy_ref=policy_ref,
    )


def send_if_requested(plan: dict[str, Any], *, live: bool) -> dict[str, Any]:
    if not live:
        return {"live": False, "dispatchPlan": plan}
    if not plan.get("dispatchAllowed"):
        return {"live": True, "error": "dispatch_not_allowed", "dispatchPlan": plan}
    from kotodama.ingest import mailer

    return {
        "live": True,
        "dispatchPlan": plan,
        "sendResult": mailer.send_email(**plan.get("channelPayload", {})),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke-test autonomous email dispatch planning")
    parser.add_argument("--agent-did", default=os.environ.get("AGENT_DID", "did:web:local.etzhayyim.com"))
    parser.add_argument("--to", required=True)
    parser.add_argument("--subject", default="etzhayyim autonomous email smoke")
    parser.add_argument("--text", default="hello from autonomous active-inference smoke")
    parser.add_argument(
        "--authority-ref",
        default=os.environ.get(
            "AGENT_EMAIL_AUTHORITY_REF",
            "capability://agent/email/outbound/smoke",
        ),
    )
    parser.add_argument(
        "--policy-ref",
        default=os.environ.get("AGENT_DEFAULT_POLICY_REF", "policy://agent/autonomous-email-v1"),
    )
    parser.add_argument("--live", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    plan = build_autonomous_email_plan(
        agent_did=args.agent_did,
        to=args.to,
        subject=args.subject,
        text=args.text,
        authority_ref=args.authority_ref,
        policy_ref=args.policy_ref,
    )
    result = send_if_requested(plan, live=bool(args.live))
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
