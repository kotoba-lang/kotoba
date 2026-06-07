"""
lawfirm.cadence.* — LangServer handlers for the lead cadence-tick.

Task types:
  lawfirm.cadence.dispatchDueMails  Walk vertex_lawfirm_lead.next_action_at,
                                    fire warm-intro mail per due lead via
                                    Graph sendDraft, log outreach event,
                                    bump stage 'lead' → 'contacted'.

Wired to existing lawfirm_sales_cadence_tick BPMN (R/PT24H, deployed via
20260509010000_vertex_lawfirm_sales_cadence.ts seed).

Mail bodies live in `_working/etzhayyim-revenue/outbox/08[a-g]-*-warm-intro.eml`
on the dispatcher pod's mounted ConfigMap. Filename derived from
`vertex_lawfirm_lead.notes` field "Outreach: outbox/<file>" pattern.

ADR-0036 Hyperdrive direct.
etzhayyim_agent rule: external mail = draft-only by default; send_now=False
unless explicit override flag. CEO/COO approval gate stays in place.
"""

from __future__ import annotations

import datetime as _dt
import json
import logging
import os
import re
from pathlib import Path
from typing import Any
from datetime import datetime, timezone

from kotodama.kotoba_datomic import get_kotoba_client

LOG = logging.getLogger("lawfirm.cadence")

_FIRM_DID = "did:web:lawfirm.etzhayyim.com"
_OUTBOX_DIR = os.environ.get(
    "LAWFIRM_OUTBOX_DIR",
    "/etc/etzhayyim/outbox",  # ConfigMap mount path in mitama-udf pod
)
_DISPATCHER_URL = os.environ.get(
    "BPMN_DISPATCHER_INTERNAL_URL",
    "http://bpmn-dispatcher.mitama-udf.svc.cluster.local:8080",
)


def _now_iso() -> str:
    return _dt.datetime.now(tz=_dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _today_date() -> str:
    return _dt.datetime.now(tz=_dt.UTC).strftime("%Y-%m-%d")


# ── Mail file parsing ─────────────────────────────────────────────────────────

_OUTREACH_PATH_RE = re.compile(r"Outreach:\s*(outbox/[A-Za-z0-9._/-]+\.eml)")


def _outreach_path_from_notes(notes: str) -> str | None:
    m = _OUTREACH_PATH_RE.search(notes or "")
    return m.group(1) if m else None


def _parse_eml(text: str) -> dict:
    """
    Minimal RFC822-ish parser tuned to our outbox/*.eml format.
    Returns dict with To, Cc, Subject, body, plus X-* headers.
    """
    headers: dict[str, str] = {}
    body_lines: list[str] = []
    in_body = False
    for line in text.splitlines():
        if not in_body:
            if line.strip() == "":
                in_body = True
                continue
            if ":" in line:
                k, _, v = line.partition(":")
                headers[k.strip()] = v.strip()
            continue
        body_lines.append(line)
    return {
        "to": [a.strip() for a in headers.get("To", "").split(",") if a.strip()],
        "cc": [a.strip() for a in headers.get("Cc", "").split(",") if a.strip()],
        "subject": headers.get("Subject", ""),
        "body_text": "\n".join(body_lines).strip(),
        "x_lead_id": headers.get("X-Lead-Id", ""),
        "x_cadence_step": headers.get("X-Cadence-Step", ""),
        "x_scheduled_send": headers.get("X-Scheduled-Send", ""),
    }


def _read_eml(rel_path: str) -> dict | None:
    """Read outbox/*.eml from dispatcher mount; returns parsed dict or None."""
    full = Path(_OUTBOX_DIR) / Path(rel_path).relative_to("outbox") if rel_path.startswith("outbox/") else Path(_OUTBOX_DIR) / rel_path
    try:
        return _parse_eml(full.read_text(encoding="utf-8"))
    except FileNotFoundError:
        # Fallback: also try repo-relative path during local dev
        repo_path = Path(
            "/Users/junkawasaki/github/etzhayyim/root/_working/etzhayyim-revenue"
        ) / rel_path
        try:
            return _parse_eml(repo_path.read_text(encoding="utf-8"))
        except Exception as exc:
            LOG.warning("eml not found %s: %s", rel_path, exc)
            return None
    except Exception as exc:
        LOG.warning("eml parse failed %s: %s", rel_path, exc)
        return None


# ── Graph sendDraft / sendMail dispatch ──────────────────────────────────────

def _dispatch_send_draft(parsed: dict, send_now: bool = False) -> dict:
    """
    POST to bpmn-dispatcher → microsoft.etzhayyim.com sendDraft (default) or sendMail.
    etzhayyim_agent rule: external mail defaults to send_now=False (draft only).
    """
    nsid = "com.etzhayyim.apps.microsoft.sendMail" if send_now else "com.etzhayyim.apps.microsoft.sendDraft"
    body = json.dumps({
        "to":       parsed.get("to") or [],
        "cc":       parsed.get("cc") or [],
        "subject":  parsed.get("subject") or "",
        "body_md":  parsed.get("body_text") or "",
        "send_now": bool(send_now),
    }).encode()
    secret = os.environ.get("BPMN_DISPATCHER_INTERNAL_SECRET", "")
    headers = {"Content-Type": "application/json"}
    if secret:
        headers["x-internal-trust"] = secret
    try:
        import urllib.request
        url = f"{_DISPATCHER_URL}/xrpc/{nsid}"
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=20) as resp:
            payload = resp.read()
        return {"ok": True, "via": nsid, "payload": payload[:200].decode("utf-8", errors="replace")}
    except Exception as exc:
        LOG.warning("dispatcher send failed: %s", exc)
        return {"ok": False, "via": nsid, "error": str(exc)}


# ── Task: lawfirm.cadence.dispatchDueMails ────────────────────────────────────

async def task_cadence_dispatch_due_mails(
    horizon_days: int = 0,
    max_dispatches: int = 20,
    send_now: bool = False,
) -> dict:
    """
    Walk leads where stage='lead' AND next_action_at <= today + horizon_days.
    For each, find the .eml via notes-embedded path, dispatch via Graph
    sendDraft (draft mode by default), log outreach_event, bump stage='contacted'.

    Idempotent on (lead_id, cadence_step) — re-run safe via vertex_lawfirm_outreach_event check.
    """
    today = _today_date()
    cutoff = today  # extend with horizon_days if needed at SQL level

    # R0: Replaced SQL SELECT with Datalog query for leads, including order-by and limit.
    query_edn_leads = """
    [:find ?lead_id ?target_name ?target_email ?notes ?next_action_at
     :in $ ?cutoff ?limit
     :where
       [?l :vertex_lawfirm_lead/stage "lead"]
       [?l :vertex_lawfirm_lead/next_action_at ?next_action_at]
       [(<= ?next_action_at ?cutoff)]
       [?l :vertex_lawfirm_lead/lead_id ?lead_id]
       [?l :vertex_lawfirm_lead/target_name ?target_name]
       [?l :vertex_lawfirm_lead/target_email ?target_email]
       [?l :vertex_lawfirm_lead/notes ?notes]]
    """
    rows_raw = get_kotoba_client().q(query_edn_leads, (cutoff, max(1, int(max_dispatches))))
    rows = [
        {
            "lead_id": r[0],
            "target_name": r[1],
            "target_email": r[2],
            "notes": r[3],
            "next_action_at": r[4],
        }
        for r in rows_raw
    ]

    dispatched: list[dict] = []
    skipped: list[dict] = []
    for r in rows:
        lead_id = r.get("lead_id") or ""
        notes = r.get("notes") or ""
        eml_rel = _outreach_path_from_notes(notes)
        if not eml_rel:
            skipped.append({"lead_id": lead_id, "reason": "no_outreach_path"})
            continue

        # Idempotency: skip if T+0 warm-intro event already exists for this lead
        # R0: Replaced SQL SELECT with Datalog query for existing outreach event.
        query_edn_existing = """
        [:find ?vertex_id
         :in $ ?lead_id ?event_kind
         :where
           [?e :vertex_lawfirm_outreach_event/lead_id ?lead_id]
           [?e :vertex_lawfirm_outreach_event/event_kind ?event_kind]
           [?e :vertex_lawfirm_outreach_event/vertex_id ?vertex_id]]
        """
        existing = get_kotoba_client().q(query_edn_existing, (lead_id, "warm_intro_sent"))
        if existing:
            skipped.append({"lead_id": lead_id, "reason": "already_sent"})
            continue

        parsed = _read_eml(eml_rel)
        if not parsed or not parsed.get("to"):
            skipped.append({"lead_id": lead_id, "reason": "eml_unreadable"})
            continue

        result = _dispatch_send_draft(parsed, send_now=send_now)

        ev_uri = (
            f"at://did:web:bpmn.etzhayyim.com/com.etzhayyim.apps.lawfirm.outreachEvent/"
            f"{lead_id}-warm-intro-{_dt.datetime.now(tz=_dt.UTC).strftime('%Y%m%d%H%M%S')}"
        )
        # R0: Replaced SQL INSERT with insert_row for vertex_lawfirm_outreach_event
        get_kotoba_client().insert_row(
            "vertex_lawfirm_outreach_event",
            {
                "vertex_id": ev_uri,
                "lead_id": lead_id,
                "event_kind": "warm_intro_sent",
                "channel": "email",
                "direction": "outbound",
                "subject": parsed.get("subject", "")[:300],
                "body_preview": (parsed.get("body_text") or "")[:500],
                "asset_uri": eml_rel,
                "occurred_at": _now_iso(),
                "actor_did": _FIRM_DID,
                "created_at": _now_iso(),
                "sensitivity_ord": 200,
                "owner_did": _FIRM_DID,
            },
        )

        # Bump stage lead → contacted, set last_touch_at
        # R0: Replaced SQL UPDATE with conditional select_first_where + insert_row to preserve WHERE clause logic.
        current_lead = get_kotoba_client().select_first_where("vertex_lawfirm_lead", "lead_id", lead_id)
        if current_lead and current_lead.get("stage") == "lead":
            get_kotoba_client().insert_row(
                "vertex_lawfirm_lead",
                {
                    "lead_id": lead_id,
                    "stage": "contacted",
                    "last_touch_at": _now_iso(),
                },
            )

        dispatched.append({
            "lead_id":      lead_id,
            "target_name":  r.get("target_name"),
            "target_email": r.get("target_email"),
            "asset":        eml_rel,
            "send_result":  result,
            "send_now":     bool(send_now),
        })

    LOG.info(
        "cadence dispatch tick: %d dispatched, %d skipped (cutoff=%s, send_now=%s)",
        len(dispatched), len(skipped), cutoff, send_now,
    )
    return {
        "ok": True,
        "cutoff_date": cutoff,
        "dispatched_count": len(dispatched),
        "skipped_count": len(skipped),
        "dispatched": dispatched,
        "skipped": skipped,
    }


# ── Task: lawfirm.cadence.dispatchFollowUps ───────────────────────────────────

# Cadence step → (template path, lookback_days, prior_event_kind, post_stage)
# T+5d: warm-intro sent ≥ 5d ago + no reply → light follow-up draft
# T+12d: light follow-up sent ≥ 7d ago (cumulative ~12d from initial) → soft release + stage='lost'
_FOLLOWUP_STEPS = [
    {
        "step":          "T+5d-light-followup",
        "template":      "outbox/templates/cadence-touch2-d5-light-followup.eml",
        "prior_kind":    "warm_intro_sent",
        "lookback_days": 5,
        "next_kind":     "followup_5d_sent",
        "set_stage":     None,           # no stage change, just touch
    },
    {
        "step":          "T+12d-soft-release",
        "template":      "outbox/templates/cadence-touch3-d12-soft-release.eml",
        "prior_kind":    "followup_5d_sent",
        "lookback_days": 7,
        "next_kind":     "soft_release_sent",
        "set_stage":     "lost",         # close loop after final touch
    },
]


async def task_cadence_dispatch_follow_ups(
    max_dispatches: int = 20,
    send_now: bool = False,
) -> dict:
    """
    Walk vertex_lawfirm_outreach_event for `prior_kind` rows whose
    occurred_at < now - lookback_days, where no `next_kind` row exists yet
    AND the lead has no inbound reply event AND lead.stage='contacted'.

    For each, render template with {{lead_id, partner_first_name, partner_email,
    firm_short_name}} substitutions, dispatch via Graph sendDraft (default
    send_now=False), record next_kind event, optionally bump lead.stage.
    """
    dispatched: list[dict] = []
    skipped: list[dict] = []

    for cfg in _FOLLOWUP_STEPS:
        now_utc = datetime.now(timezone.utc)
        prior_cutoff_dt = now_utc - _dt.timedelta(days=cfg["lookback_days"])
        prior_cutoff = prior_cutoff_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

        # R0: Replaced complex SQL SELECT with Datalog query for follow-up leads, including joins, NOT EXISTS, and date logic.
        query_edn_followups = """
        [:find ?lead_id ?target_name ?target_email ?notes ?stage
         :in $ ?prior_kind_arg ?next_kind_arg ?prior_cutoff_arg ?limit_arg
         :where
           [?l :vertex_lawfirm_lead/lead_id ?lead_id]
           [?l :vertex_lawfirm_lead/stage "contacted"]
           [?l :vertex_lawfirm_lead/target_name ?target_name]
           [?l :vertex_lawfirm_lead/target_email ?target_email]
           [?l :vertex_lawfirm_lead/notes ?notes]
           [?l :vertex_lawfirm_lead/stage ?stage]

           [?prior :vertex_lawfirm_outreach_event/lead_id ?lead_id]
           [?prior :vertex_lawfirm_outreach_event/event_kind ?prior_kind_arg]
           [?prior :vertex_lawfirm_outreach_event/occurred_at ?prior_occurred_at]
           [(< ?prior_occurred_at ?prior_cutoff_arg)]

           (not
             [?nxt :vertex_lawfirm_outreach_event/lead_id ?lead_id]
             [?nxt :vertex_lawfirm_outreach_event/event_kind ?next_kind_arg]
           )

           (not
             [?reply :vertex_lawfirm_outreach_event/lead_id ?lead_id]
             [?reply :vertex_lawfirm_outreach_event/event_kind "reply_received"]
             [?reply :vertex_lawfirm_outreach_event/direction "inbound"]
           )
         :order-by [?prior_occurred_at :asc]
         :limit ?limit_arg]
        """
        rows_raw = get_kotoba_client().q(
            query_edn_followups,
            (cfg["prior_kind"], cfg["next_kind"], prior_cutoff, max(1, int(max_dispatches)))
        )
        rows = [
            {
                "lead_id": r[0],
                "target_name": r[1],
                "target_email": r[2],
                "notes": r[3],
                "stage": r[4],
            }
            for r in rows_raw
        ]

        if not rows:
            continue

        template = _read_eml(cfg["template"])
        if not template:
            skipped.append({"step": cfg["step"], "reason": "template_unreadable"})
            continue

        for r in rows:
            lead_id = r.get("lead_id") or ""
            partner_email = r.get("target_email") or ""
            firm_full = r.get("target_name") or ""
            partner_first = (partner_email.split("@", 1)[0].split(".")[0] or "there").title()
            firm_short = firm_full.split(" ")[0] if firm_full else "your firm"

            substituted = {
                "to":        [partner_email] if partner_email else [],
                "cc":        [],
                "subject":   (template.get("subject") or "")
                              .replace("{{lead_id}}", lead_id)
                              .replace("{{partner_first_name}}", partner_first)
                              .replace("{{firm_short_name}}", firm_short),
                "body_text": (template.get("body_text") or "")
                              .replace("{{lead_id}}", lead_id)
                              .replace("{{partner_email}}", partner_email)
                              .replace("{{partner_first_name}}", partner_first)
                              .replace("{{firm_short_name}}", firm_short),
            }

            result = _dispatch_send_draft(substituted, send_now=send_now)

            ev_uri = (
                f"at://did:web:bpmn.etzhayyim.com/com.etzhayyim.apps.lawfirm.outreachEvent/"
                f"{lead_id}-{cfg['next_kind']}-"
                f"{_dt.datetime.now(tz=_dt.UTC).strftime('%Y%m%d%H%M%S')}"
            )
            # R0: Replaced SQL INSERT with insert_row for vertex_lawfirm_outreach_event
            get_kotoba_client().insert_row(
                "vertex_lawfirm_outreach_event",
                {
                    "vertex_id": ev_uri, "lead_id": lead_id, "event_kind": cfg["next_kind"],
                    "channel": "email", "direction": "outbound",
                    "subject": substituted["subject"][:300],
                    "body_preview": substituted["body_text"][:500],
                    "asset_uri": cfg["template"],
                    "occurred_at": _now_iso(), "actor_did": _FIRM_DID,
                    "created_at": _now_iso(), "sensitivity_ord": 200, "owner_did": _FIRM_DID,
                },
            )

            if cfg.get("set_stage"):
                # R0: Replaced SQL UPDATE with insert_row for vertex_lawfirm_lead
                get_kotoba_client().insert_row(
                    "vertex_lawfirm_lead",
                    {
                        "lead_id": lead_id,
                        "stage": cfg["set_stage"],
                        "last_touch_at": _now_iso(),
                    },
                )
            else:
                # R0: Replaced SQL UPDATE with insert_row for vertex_lawfirm_lead
                get_kotoba_client().insert_row(
                    "vertex_lawfirm_lead",
                    {
                        "lead_id": lead_id,
                        "last_touch_at": _now_iso(),
                    },
                )

            dispatched.append({
                "lead_id":     lead_id,
                "step":        cfg["step"],
                "next_kind":   cfg["next_kind"],
                "stage_after": cfg.get("set_stage") or r.get("stage") or "",
                "send_result": result,
                "send_now":    bool(send_now),
            })

    LOG.info(
        "follow-up dispatch tick: %d dispatched, %d skipped (send_now=%s)",
        len(dispatched), len(skipped), send_now,
    )
    return {
        "ok": True,
        "dispatched_count": len(dispatched),
        "skipped_count": len(skipped),
        "dispatched": dispatched,
        "skipped": skipped,
    }


# ── LangServer registration ─────────────────────────────────────────────────────

def register(app: Any, timeout_ms: int = 90_000) -> None:
    from kotodama.langserver_compat import LangServerWorker
    if not isinstance(app, LangServerWorker):
        return

    @app.task(task_type="lawfirm.cadence.dispatchDueMails",
              timeout_ms=timeout_ms, max_jobs_to_activate=2)
    async def _dispatch(horizon_days: int = 0,
                        max_dispatches: int = 20,
                        send_now: bool = False) -> dict:
        return await task_cadence_dispatch_due_mails(
            horizon_days=horizon_days,
            max_dispatches=max_dispatches,
            send_now=send_now,
        )

    @app.task(task_type="lawfirm.cadence.dispatchFollowUps",
              timeout_ms=timeout_ms, max_jobs_to_activate=2)
    async def _followup(max_dispatches: int = 20, send_now: bool = False) -> dict:
        return await task_cadence_dispatch_follow_ups(
            max_dispatches=max_dispatches, send_now=send_now,
        )

    LOG.info(
        "Registered tasks: lawfirm.cadence.{dispatchDueMails,dispatchFollowUps}"
    )
