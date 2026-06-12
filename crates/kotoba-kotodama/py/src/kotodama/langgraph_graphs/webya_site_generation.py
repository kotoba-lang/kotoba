"""
webya.etzhayyim.com — サイト生成 LangGraph StateGraph (ADR-2605080600 + ADR-2605072000).

assistant_id: "webya_create_site"

Graph: WebsiteGenerationGraph
  START
    → intake_analyzer      (LLM tier=deep: intake 解析 + template_id 決定)
    → structure_planner    (LLM tier=deep: page 構成 + nav + カラー)
    → legal_disclosure_guard (rule-based: 法定開示 slot 検証・注入)
    → content_generator    (LLM tier=balanced: 1 ページずつ loop)
    → quality_reviewer     (LLM tier=fast: issue list)
    → [cond] revision_count < max_revisions → content_generator (loop)
    → [cond] resolved       → seo_optimizer
    → seo_optimizer        (LLM tier=fast: meta_desc × N + JSON-LD)
    → html_renderer        (Jinja2 rule-based)
    → publisher            (RW INSERT + job 更新)
    → END

revision subgraph: webya_site_revision (assistant_id: "webya_revise_site")
  START
    → revision_analyzer   (LLM tier=deep: 影響ページ特定)
    → content_generator   (affected pages only)
    → quality_reviewer
    → seo_optimizer
    → html_renderer
    → republisher
    → END

State: WebsiteGenerationState (Pydantic v2 BaseModelState per ADR-2605080200)
LLM: RunPod 6000 Ada (ADR-2605010000). Murakumo fallback 禁止.
"""

from __future__ import annotations
from kotodama.kotoba_datomic import get_kotoba_client

import json
import logging
import re
import time
import uuid
from typing import Annotated, Any, Literal, Optional

from langgraph.graph import END, START, StateGraph
from pydantic import Field

from kotodama.primitives.pydantic_job import BaseModelState
from kotodama import llm

LOG = logging.getLogger(__name__)

# ── Disclosure schema (rule-based, LLM non-authoritative) ─────────────────────

DISCLOSURE_SCHEMA: dict[str, dict] = {
    "law_firm": {
        "required_slots": [
            "bar_association", "bar_registration_number",
            "office_address", "representative_attorney",
        ],
        "footer_slots": ["bar_registration_number", "office_address"],
        "json_ld_type": "LegalService",
        "disclaimer": "弁護士法に基づき、法的助言は個別事案ごとに異なります。",
    },
    "accounting_firm": {
        "required_slots": [
            "tax_attorney_association",
            "tax_attorney_registration_number",
            "office_address",
        ],
        "footer_slots": ["tax_attorney_registration_number", "office_address"],
        "json_ld_type": "AccountingService",
    },
    "judicial_scrivener": {
        "required_slots": [
            "scrivener_association",
            "scrivener_registration_number",
            "office_address",
        ],
        "optional_slots": ["judicial_cert_number"],
        "json_ld_type": "LegalService",
    },
    "admin_scrivener": {
        "required_slots": [
            "gyosei_association",
            "gyosei_registration_number",
            "office_address",
        ],
        "json_ld_type": "LocalBusiness",
    },
    "general_company": {
        "required_slots": ["company_name", "address", "representative_name"],
        "optional_slots": ["corporate_number"],
        "json_ld_type": "Organization",
    },
}

TEMPLATE_ID_MAP: dict[str, str] = {
    "law_firm":          "template_law_firm_v1",
    "accounting_firm":   "template_accounting_firm_v1",
    "judicial_scrivener": "template_scrivener_v1",
    "admin_scrivener":    "template_scrivener_v1",
    "general_company":    "template_company_v1",
}

# ── State ──────────────────────────────────────────────────────────────────────

class ClientIntake(BaseModelState):
    client_name: str
    profession_kind: str
    representative_name: str
    address: str
    phone: str
    email: str = ""
    tagline: str = ""
    specialties: list[str] = Field(default_factory=list)
    tone: Literal["formal", "friendly", "professional"] = "professional"
    registration_number: str = ""
    association_name: str = ""
    corporate_number: str = ""
    custom_domain: str = ""


class SiteStructure(BaseModelState):
    pages: list[str]
    nav_labels: dict[str, str]
    primary_color: str = "#1a3a5c"
    accent_color: str = "#c8a96e"
    font_pair: str = "Noto Serif JP / Noto Sans JP"


class PageContent(BaseModelState):
    slug: str
    title: str
    meta_description: str
    slots: dict[str, Any] = Field(default_factory=dict)
    json_ld: dict[str, Any] = Field(default_factory=dict)


class WebsiteGenerationState(BaseModelState):
    # Inputs
    site_id: str = ""
    client_id: str = ""
    intake: Optional[ClientIntake] = None
    template_id: str = ""
    # Planning
    site_structure: Optional[SiteStructure] = None
    # Generation loop
    pages: dict[str, PageContent] = Field(default_factory=dict)
    pages_to_generate: list[str] = Field(default_factory=list)
    current_page_idx: int = 0
    # Quality
    quality_issues: list[str] = Field(default_factory=list)
    revision_count: int = 0
    max_revisions: int = 2
    # Publish
    subdomain: str = ""
    custom_domain: str = ""
    published_urls: dict[str, str] = Field(default_factory=dict)
    # Control
    status: str = "intake"
    error: Optional[str] = None
    llm_calls: int = 0


# Revision state (shares most fields)
class SiteRevisionState(BaseModelState):
    site_id: str = ""
    instruction: str = ""
    target_pages: list[str] = Field(default_factory=list)
    # Loaded from RW
    intake: Optional[ClientIntake] = None
    template_id: str = ""
    existing_pages: dict[str, PageContent] = Field(default_factory=dict)
    # Revision output
    affected_pages: list[str] = Field(default_factory=list)
    pages: dict[str, PageContent] = Field(default_factory=dict)
    current_page_idx: int = 0
    quality_issues: list[str] = Field(default_factory=list)
    revision_count: int = 0
    job_id: str = ""
    status: str = "analyzing"
    error: Optional[str] = None
    llm_calls: int = 0


# ── Helpers ────────────────────────────────────────────────────────────────────

_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)
_THINK_OPEN_RE = re.compile(r"<think>.*$", re.DOTALL)


def _strip_think(text: str) -> str:
    return _THINK_OPEN_RE.sub("", _THINK_RE.sub("", text)).strip()


def _rw_query(sql_str: str, params: tuple = ()) -> list[Any]:
    try:
        if True:
            client = get_kotoba_client()
            _res = client.q(sql_str, params)
            return _res
    except Exception as exc:
        LOG.warning("rw_query failed: %s", exc)
        return []


def _rw_execute(sql_str: str, params: tuple = ()) -> None:
    if True:
        client = get_kotoba_client()
        _res = client.q(sql_str, params)


def _load_template_pages(template_id: str) -> list[str]:
    rows = _rw_query(
        "SELECT pages_json FROM vertex_webya_template WHERE template_id = %s AND active = TRUE LIMIT 1",
        (template_id,),
    )
    if rows:
        return json.loads(rows[0][0])
    return ["home", "about", "services", "access", "contact"]


def _load_slot_schema(template_id: str, slug: str) -> dict:
    rows = _rw_query(
        "SELECT slot_schema_json FROM vertex_webya_template WHERE template_id = %s AND active = TRUE LIMIT 1",
        (template_id,),
    )
    if not rows:
        return {}
    schema = json.loads(rows[0][0])
    return schema.get(slug, {})


# ── Node: intake_analyzer ─────────────────────────────────────────────────────

def intake_analyzer(state: WebsiteGenerationState) -> WebsiteGenerationState:
    if not state.intake:
        state.status = "failed"
        state.error = "intake missing"
        return state

    state.template_id = TEMPLATE_ID_MAP.get(state.intake.profession_kind, "template_company_v1")
    state.pages_to_generate = _load_template_pages(state.template_id)
    state.status = "planning"

    prompt = f"""あなたはウェブデザイン専門家です。以下の顧客情報を分析し、サイトのコア訴求メッセージを JSON で返してください。

顧客名: {state.intake.client_name}
業種: {state.intake.profession_kind}
代表者: {state.intake.representative_name}
所在地: {state.intake.address}
専門分野: {', '.join(state.intake.specialties) if state.intake.specialties else '未指定'}
希望トーン: {state.intake.tone}
キャッチコピー候補: {state.intake.tagline or '（なし）'}

JSON形式で返答: {{"core_message": "...", "target_persona": "...", "key_differentiators": ["...", "..."]}}
JSON以外のテキストは含めないでください。"""

    try:
        result = llm.call_tier_json("deep", prompt, max_tokens=600)
        state.intake = state.intake.model_copy(update={
            "tagline": result.get("core_message", state.intake.tagline),
        })
        state.llm_calls += 1
        LOG.info("intake_analyzer ok site_id=%s profession=%s", state.site_id, state.intake.profession_kind)
    except Exception as exc:
        LOG.warning("intake_analyzer llm failed (non-fatal): %s", exc)

    return state


# ── Node: structure_planner ───────────────────────────────────────────────────

def structure_planner(state: WebsiteGenerationState) -> WebsiteGenerationState:
    if not state.intake:
        return state

    prompt = f"""ウェブサイトの構成を設計してください。

顧客: {state.intake.client_name} ({state.intake.profession_kind})
ページ一覧: {state.pages_to_generate}
トーン: {state.intake.tone}

以下のJSON形式で返答してください:
{{
  "nav_labels": {{"home": "ホーム", "about": "事務所紹介", ...}},
  "primary_color": "#1a3a5c",
  "accent_color": "#c8a96e",
  "font_pair": "Noto Serif JP / Noto Sans JP"
}}
JSON以外のテキストは含めないでください。"""

    try:
        result = llm.call_tier_json("deep", prompt, max_tokens=400)
        state.site_structure = SiteStructure(
            pages=state.pages_to_generate,
            nav_labels=result.get("nav_labels", {p: p for p in state.pages_to_generate}),
            primary_color=result.get("primary_color", "#1a3a5c"),
            accent_color=result.get("accent_color", "#c8a96e"),
            font_pair=result.get("font_pair", "Noto Serif JP / Noto Sans JP"),
        )
        state.llm_calls += 1
    except Exception as exc:
        LOG.warning("structure_planner fallback: %s", exc)
        state.site_structure = SiteStructure(
            pages=state.pages_to_generate,
            nav_labels={p: p for p in state.pages_to_generate},
        )

    state.status = "generating"
    return state


# ── Node: legal_disclosure_guard ──────────────────────────────────────────────

def legal_disclosure_guard(state: WebsiteGenerationState) -> WebsiteGenerationState:
    """Rule-based: 法定開示 slot の検証。不足時は failed。LLM 不使用。"""
    if not state.intake:
        return state

    schema = DISCLOSURE_SCHEMA.get(state.intake.profession_kind, {})
    required = schema.get("required_slots", [])
    intake_data = state.intake.model_dump()

    missing = []
    for slot in required:
        # マッピング: slot名 → intake フィールド名
        field_map = {
            "bar_association":              "association_name",
            "bar_registration_number":      "registration_number",
            "representative_attorney":      "representative_name",
            "office_address":               "address",
            "tax_attorney_association":     "association_name",
            "tax_attorney_registration_number": "registration_number",
            "scrivener_association":        "association_name",
            "scrivener_registration_number": "registration_number",
            "gyosei_association":           "association_name",
            "gyosei_registration_number":   "registration_number",
            "company_name":                 "client_name",
            "representative_name":          "representative_name",
        }
        field = field_map.get(slot, slot)
        if not intake_data.get(field):
            missing.append(slot)

    if missing:
        LOG.error("legal_disclosure_guard FAIL site_id=%s missing=%s", state.site_id, missing)
        state.status = "failed"
        state.error = f"法定開示 slot 不足: {missing}"

    return state


# ── Node: content_generator ───────────────────────────────────────────────────

def content_generator(state: WebsiteGenerationState) -> WebsiteGenerationState:
    """1 ページ分のコンテンツを LLM で生成し、current_page_idx を進める。"""
    if state.current_page_idx >= len(state.pages_to_generate):
        return state

    slug = state.pages_to_generate[state.current_page_idx]
    slot_schema = _load_slot_schema(state.template_id, slug)
    disclosure = DISCLOSURE_SCHEMA.get(state.intake.profession_kind if state.intake else "", {})
    json_ld_type = disclosure.get("json_ld_type", "LocalBusiness")

    intake = state.intake
    prompt = f"""以下の情報をもとに、ウェブサイトの「{slug}」ページのコンテンツを生成してください。

【顧客情報】
- 名前: {intake.client_name}
- 業種: {intake.profession_kind}
- 代表者: {intake.representative_name}
- 所在地: {intake.address}
- 電話: {intake.phone}
- 専門: {', '.join(intake.specialties) if intake.specialties else '未指定'}
- トーン: {intake.tone}
{'- 登録番号: ' + intake.registration_number if intake.registration_number else ''}
{'- 所属会: ' + intake.association_name if intake.association_name else ''}

【必須 slot】: {slot_schema.get('required', [])}
【任意 slot】: {slot_schema.get('optional', [])}

以下のJSON形式で返答してください:
{{
  "title": "ページタイトル",
  "meta_description": "120文字以内のメタディスクリプション",
  "slots": {{"slot_name": "slot_value", ...}},
  "json_ld": {{"@context": "https://schema.org", "@type": "{json_ld_type}", ...}}
}}
JSON以外のテキストは含めないでください。日本語で生成してください。"""

    try:
        result = llm.call_tier_json("balanced", prompt, max_tokens=2000)
        result = {k: v for k, v in result.items() if not isinstance(v, str) or not v.startswith("<think>")}
        state.pages[slug] = PageContent(
            slug=slug,
            title=result.get("title", f"{intake.client_name} - {slug}"),
            meta_description=result.get("meta_description", "")[:120],
            slots=result.get("slots", {}),
            json_ld=result.get("json_ld", {}),
        )
        state.llm_calls += 1
        LOG.info("content_generator page=%s site_id=%s ok", slug, state.site_id)
    except Exception as exc:
        LOG.error("content_generator page=%s failed: %s", slug, exc)
        state.pages[slug] = PageContent(
            slug=slug,
            title=f"{intake.client_name} - {slug}",
            meta_description="",
            slots={},
        )

    state.current_page_idx += 1
    return state


# ── Node: quality_reviewer ────────────────────────────────────────────────────

def quality_reviewer(state: WebsiteGenerationState) -> WebsiteGenerationState:
    pages_summary = {
        slug: {"title": p.title, "slots_keys": list(p.slots.keys())}
        for slug, p in state.pages.items()
    }
    prompt = f"""ウェブサイトのコンテンツ品質をレビューしてください。

業種: {state.intake.profession_kind if state.intake else 'unknown'}
ページ: {json.dumps(pages_summary, ensure_ascii=False)}

品質上の問題点を JSON で返してください:
{{"issues": ["問題1", "問題2", ...], "severity": "ok|minor|major"}}
問題なければ issues=[] severity="ok"。JSON以外含めないでください。"""

    try:
        result = llm.call_tier_json("fast", prompt, max_tokens=400)
        state.quality_issues = result.get("issues", [])
        state.llm_calls += 1
        LOG.info(
            "quality_reviewer site_id=%s issues=%d severity=%s",
            state.site_id, len(state.quality_issues), result.get("severity")
        )
    except Exception as exc:
        LOG.warning("quality_reviewer failed (non-fatal): %s", exc)
        state.quality_issues = []

    return state


# ── Node: seo_optimizer ───────────────────────────────────────────────────────

def seo_optimizer(state: WebsiteGenerationState) -> WebsiteGenerationState:
    for slug, page in state.pages.items():
        if page.meta_description and len(page.meta_description) >= 60:
            continue  # already adequate

        prompt = f"""{state.intake.client_name if state.intake else ''} の「{slug}」ページのメタディスクリプションを生成してください。
60〜120文字、日本語。JSON: {{"meta_description": "..."}}"""

        try:
            result = llm.call_tier_json("fast", prompt, max_tokens=200)
            updated_meta = result.get("meta_description", page.meta_description)[:120]
            state.pages[slug] = page.model_copy(update={"meta_description": updated_meta})
            state.llm_calls += 1
        except Exception as exc:
            LOG.warning("seo_optimizer slug=%s failed: %s", slug, exc)

    state.status = "rendering"
    return state


# ── Node: html_renderer ───────────────────────────────────────────────────────

def html_renderer(state: WebsiteGenerationState) -> WebsiteGenerationState:
    """Jinja2 でテンプレート + slot を HTML にレンダリング。LLM 不使用。"""
    try:
        from jinja2 import BaseLoader, Environment

        rows = _rw_query(
            "SELECT html_skeleton FROM vertex_webya_template WHERE template_id = %s AND active = TRUE LIMIT 1",
            (state.template_id,),
        )
        skeleton = rows[0][0] if rows else ""
        env = Environment(loader=BaseLoader())

        nav_items = []
        if state.site_structure:
            for slug in state.site_structure.pages:
                label = state.site_structure.nav_labels.get(slug, slug)
                nav_items.append((slug, label))

        intake = state.intake
        disclosure = DISCLOSURE_SCHEMA.get(intake.profession_kind if intake else "", {})

        for slug, page in state.pages.items():
            ctx: dict[str, Any] = {
                "title":        page.title,
                "meta_description": page.meta_description,
                "client_name":  intake.client_name if intake else "",
                "nav_items":    nav_items,
                "json_ld":      json.dumps(page.json_ld, ensure_ascii=False) if page.json_ld else "",
                "phone":        intake.phone if intake else "",
                "address":      intake.address if intake else "",
                "profession_kind": intake.profession_kind if intake else "",
                # Disclosure fields
                "bar_association":               intake.association_name if intake else "",
                "bar_registration_number":       intake.registration_number if intake else "",
                "tax_attorney_association":      intake.association_name if intake else "",
                "tax_attorney_registration_number": intake.registration_number if intake else "",
                "scrivener_association":         intake.association_name if intake else "",
                "scrivener_registration_number": intake.registration_number if intake else "",
                "corporate_number":              intake.corporate_number if intake else "",
                **page.slots,
            }
            # Page-specific content block
            content_html = _render_content_block(slug, page, ctx)
            ctx["content"] = content_html

            tmpl = env.from_string(skeleton)
            html = tmpl.render(**ctx)
            state.pages[slug] = page.model_copy(update={"html_content": html} if hasattr(page, "html_content") else {})

        LOG.info("html_renderer done site_id=%s pages=%d", state.site_id, len(state.pages))
    except Exception as exc:
        LOG.error("html_renderer failed: %s", exc)
        state.error = f"html_renderer: {exc}"

    return state


def _render_content_block(slug: str, page: PageContent, ctx: dict) -> str:
    """slug に応じた簡易コンテンツブロック HTML を生成。"""
    slots = page.slots
    lines: list[str] = [f"<section class='page-{slug}'>"]

    if slug == "home":
        lines += [
            f"<h1>{slots.get('hero_headline', page.title)}</h1>",
            f"<p class='sub'>{slots.get('hero_sub', '')}</p>",
            f"<a class='cta' href='/contact'>{slots.get('cta_label', 'お問い合わせ')}</a>",
        ]
    elif slug in ("about", "practice_areas", "services"):
        lines.append(f"<h2>{page.title}</h2>")
        for k, v in slots.items():
            if isinstance(v, list):
                lines.append("<ul>" + "".join(f"<li>{item}</li>" for item in v) + "</ul>")
            elif isinstance(v, str) and v:
                lines.append(f"<p>{v}</p>")
    elif slug == "contact":
        lines += [
            f"<h2>{page.title}</h2>",
            f"<p>TEL: {ctx.get('phone', '')}</p>",
            f"<p>Email: {ctx.get('email', '')}</p>",
        ]
    else:
        lines.append(f"<h2>{page.title}</h2>")
        for v in slots.values():
            if isinstance(v, str) and v:
                lines.append(f"<p>{v}</p>")

    lines.append("</section>")
    return "\n".join(lines)


# ── Node: publisher ───────────────────────────────────────────────────────────

def publisher(state: WebsiteGenerationState) -> WebsiteGenerationState:
    """RisingWave に pages を INSERT + job status を更新。"""
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    site_id = state.site_id

    try:
        for slug, page in state.pages.items():
            page_id = f"{site_id}-{slug}"
            vertex_id = f"at://did:web:webya.etzhayyim.com/com.etzhayyim.apps.webya.page/{page_id}"
            html_content = getattr(page, "html_content", "")
            json_ld_str = json.dumps(page.json_ld, ensure_ascii=False) if page.json_ld else ""

            _rw_execute(
                """
                INSERT INTO vertex_webya_page
                  (vertex_id, page_id, site_id, slug, title,
                   meta_description, slots_json, html_content, json_ld, status, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'published', %s)
                """,
                (
                    vertex_id, page_id, site_id, slug, page.title,
                    page.meta_description,
                    json.dumps(page.slots, ensure_ascii=False),
                    html_content, json_ld_str, now,
                ),
            )
            # edge: site → page
            edge_vid = f"at://did:web:webya.etzhayyim.com/com.etzhayyim.apps.webya.edge/site-page-{page_id}"
            site_vid = f"at://did:web:webya.etzhayyim.com/com.etzhayyim.apps.webya.site/{site_id}"
            _rw_execute(
                "INSERT INTO edge_webya_site_page (vertex_id, src, dst, slug, created_at) VALUES (%s, %s, %s, %s, %s)",
                (edge_vid, site_vid, vertex_id, slug, now),
            )

        # Update site status
        _rw_execute(
            "UPDATE vertex_webya_site SET status = 'published', published_at = %s WHERE site_id = %s",
            (now, site_id),
        )

        state.status = "done"
        LOG.info("publisher done site_id=%s pages=%d", site_id, len(state.pages))
    except Exception as exc:
        LOG.error("publisher failed site_id=%s: %s", site_id, exc)
        state.error = f"publisher: {exc}"
        state.status = "failed"

    return state


# ── Conditional edges ──────────────────────────────────────────────────────────

def route_disclosure_guard(state: WebsiteGenerationState) -> str:
    if state.status == "failed":
        return END
    return "content_generator"


def route_content_loop(state: WebsiteGenerationState) -> str:
    if state.current_page_idx < len(state.pages_to_generate):
        return "content_generator"
    return "quality_reviewer"


def route_quality(state: WebsiteGenerationState) -> str:
    if state.quality_issues and state.revision_count < state.max_revisions:
        state.revision_count += 1
        state.current_page_idx = 0  # re-generate all pages
        return "content_generator"
    return "seo_optimizer"


def route_error(state: WebsiteGenerationState) -> str:
    if state.status == "failed":
        return END
    return "structure_planner"


# ── Build graphs ───────────────────────────────────────────────────────────────

def build_website_generation_graph() -> StateGraph:
    g = StateGraph(WebsiteGenerationState)

    g.add_node("intake_analyzer",       intake_analyzer)
    g.add_node("structure_planner",     structure_planner)
    g.add_node("legal_disclosure_guard", legal_disclosure_guard)
    g.add_node("content_generator",     content_generator)
    g.add_node("quality_reviewer",      quality_reviewer)
    g.add_node("seo_optimizer",         seo_optimizer)
    g.add_node("html_renderer",         html_renderer)
    g.add_node("publisher",             publisher)

    g.add_edge(START, "intake_analyzer")
    g.add_conditional_edges("intake_analyzer", route_error, {
        "structure_planner": "structure_planner",
        END: END,
    })
    g.add_edge("structure_planner", "legal_disclosure_guard")
    g.add_conditional_edges("legal_disclosure_guard", route_disclosure_guard, {
        "content_generator": "content_generator",
        END: END,
    })
    g.add_conditional_edges("content_generator", route_content_loop, {
        "content_generator": "content_generator",
        "quality_reviewer":  "quality_reviewer",
    })
    g.add_conditional_edges("quality_reviewer", route_quality, {
        "content_generator": "content_generator",
        "seo_optimizer":     "seo_optimizer",
    })
    g.add_edge("seo_optimizer",  "html_renderer")
    g.add_edge("html_renderer",  "publisher")
    g.add_edge("publisher",      END)

    return g.compile()


# ── Revision subgraph ──────────────────────────────────────────────────────────

def revision_analyzer(state: SiteRevisionState) -> SiteRevisionState:
    if not state.instruction:
        state.error = "instruction missing"
        state.status = "failed"
        return state

    # Load existing site data from RW
    rows = _rw_query(
        "SELECT s.template_id FROM vertex_webya_site s WHERE s.site_id = %s LIMIT 1",
        (state.site_id,),
    )
    if rows:
        state.template_id = rows[0][0]

    prompt = f"""以下の修正指示を分析し、変更が必要なページの slug 一覧を JSON で返してください。

指示: {state.instruction}
全ページ: {state.target_pages or _load_template_pages(state.template_id)}

JSON: {{"affected_pages": ["slug1", "slug2", ...], "reason": "..."}}
JSON以外含めないでください。"""

    try:
        result = llm.call_tier_json("deep", prompt, max_tokens=300)
        state.affected_pages = result.get("affected_pages", state.target_pages)
        state.llm_calls += 1
    except Exception as exc:
        LOG.warning("revision_analyzer fallback: %s", exc)
        state.affected_pages = state.target_pages or _load_template_pages(state.template_id)

    state.pages_to_generate = state.affected_pages  # type: ignore[attr-defined]
    state.current_page_idx = 0
    return state


def build_site_revision_graph() -> StateGraph:
    g = StateGraph(SiteRevisionState)

    g.add_node("revision_analyzer", revision_analyzer)
    g.add_node("content_generator", content_generator)   # reuse
    g.add_node("quality_reviewer",  quality_reviewer)
    g.add_node("seo_optimizer",     seo_optimizer)
    g.add_node("html_renderer",     html_renderer)
    g.add_node("publisher",         publisher)

    g.add_edge(START, "revision_analyzer")
    g.add_conditional_edges("revision_analyzer", lambda s: END if s.status == "failed" else "content_generator", {
        "content_generator": "content_generator",
        END: END,
    })
    g.add_conditional_edges("content_generator", route_content_loop, {
        "content_generator": "content_generator",
        "quality_reviewer":  "quality_reviewer",
    })
    g.add_conditional_edges("quality_reviewer", route_quality, {
        "content_generator": "content_generator",
        "seo_optimizer":     "seo_optimizer",
    })
    g.add_edge("seo_optimizer", "html_renderer")
    g.add_edge("html_renderer", "publisher")
    g.add_edge("publisher",     END)

    return g.compile()


# ── Register on import ─────────────────────────────────────────────────────────

def register(server_app: Any) -> None:
    """LangGraph Server app に両グラフを登録する。"""
    from kotodama.langgraph_server_app import register_graph
    register_graph("webya_create_site", build_website_generation_graph())
    register_graph("webya_revise_site",  build_site_revision_graph())
    LOG.info("webya graphs registered: webya_create_site, webya_revise_site")
