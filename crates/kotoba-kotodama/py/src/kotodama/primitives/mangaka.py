"""
ADR-0057 — mangaka pipeline primitives for LangServer worker.

Implements 5 task types invoked by 00-contracts/bpmn/com/etzhayyim/mangaka/generateEpisode.bpmn:

  mangaka.panel.batchRender       — submit all panels to ComfyUI, poll, upload to PDS
  mangaka.balloon.batchOverlay    — Pillow speech-balloon overlay per panel
  mangaka.page.batchCompose       — Pillow grid layout, 3-7 panels per page, upload to PDS
  mangaka.records.batchInsertPages — insert work + 20 page rows into vertex_mangaka (Hyperdrive)
  mangaka.post.publish            — create app.bsky.feed.post (recordWithMedia + facets)

These are batch primitives (not per-panel multi-instance) — ADR-0056 v5 lesson:
multi-instance subprocess fan-out saturates worker slots. Single batch task per
phase keeps the worker pool at constant N regardless of panel count, and the
pod-side queue handles GPU serialization.

Process mining: each primitive emits OCEL 2.0 attributes (case_id, duration_ms,
status, object_refs) — the BPMN file then wraps each call with a generic.audit.emit
task that writes the trace event.

Env:
  COMFYUI_POD_URL    — RunPod ComfyUI proxy URL (default: same as shinshi worker)
  ATPROTO_BASE_URL   — PDS gateway (default: https://atproto.etzhayyim.com)
  PDS_INTERNAL_TOKEN — x-kotoba-kotodama-verified header value (default: "true")
  RW_URL             — RisingWave PG URL for direct INSERT (Hyperdrive in prod)
"""

from __future__ import annotations

import asyncio
import io
import json
import logging
import os
import time
from typing import Any

import aiohttp

LOG = logging.getLogger("zeebe_worker.mangaka")

POD_URL = os.environ.get("COMFYUI_POD_URL", "https://85q7hno6n60xxk-8188.proxy.runpod.net")
ATPROTO_BASE = os.environ.get("ATPROTO_BASE_URL", "https://atproto.etzhayyim.com")
PDS_TOKEN = os.environ.get("PDS_INTERNAL_TOKEN", "true")
RW_URL = os.environ.get("RW_URL", "")

PANEL_W, PANEL_H = 768, 1152
PAGE_W, PAGE_H = 1500, 2100
DEFAULT_CHECKPOINT = "wai-nsfw-illustrious-v60.safetensors"
NEG_PROMPT = "color, photo, photograph, realistic, blurry, low quality, jpeg artifacts, signature, watermark, multiple people, text, letters, words"


# ─── Helpers ────────────────────────────────────────────────────────────────

async def _pds_upload_blob(session: aiohttp.ClientSession, png_bytes: bytes) -> tuple[str, int]:
    """Upload raw PNG to PDS — returns (sha256-cid, size)."""
    async with session.post(
        f"{ATPROTO_BASE}/xrpc/com.atproto.repo.uploadBlob",
        data=png_bytes,
        headers={"Content-Type": "image/png", "x-kotoba-kotodama-verified": PDS_TOKEN},
        timeout=aiohttp.ClientTimeout(total=60),
    ) as resp:
        body = await resp.json()
        cid = body.get("blob", {}).get("ref", {}).get("$link", "")
        size = len(png_bytes)
        return cid, size


async def _pds_get_blob(session: aiohttp.ClientSession, cid: str, repo: str = "did:web:mangaka.etzhayyim.com") -> bytes:
    """Fetch blob bytes from PDS by CID."""
    async with session.get(
        f"{ATPROTO_BASE}/xrpc/com.atproto.sync.getBlob",
        params={"did": repo, "cid": cid},
        timeout=aiohttp.ClientTimeout(total=30),
    ) as resp:
        return await resp.read()


def _build_workflow(prompt: str, negative: str, seed: int, fname: str, checkpoint: str) -> dict:
    return {
        "prompt": {
            "3": {"class_type": "KSampler", "inputs": {"seed": seed, "steps": 22, "cfg": 5.0,
                "sampler_name": "euler_ancestral", "scheduler": "normal", "denoise": 1.0,
                "model": ["4", 0], "positive": ["6", 0], "negative": ["7", 0], "latent_image": ["5", 0]}},
            "4": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": checkpoint}},
            "5": {"class_type": "EmptyLatentImage", "inputs": {"width": PANEL_W, "height": PANEL_H, "batch_size": 1}},
            "6": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["4", 1]}},
            "7": {"class_type": "CLIPTextEncode", "inputs": {"text": negative, "clip": ["4", 1]}},
            "8": {"class_type": "VAEDecode", "inputs": {"samples": ["3", 0], "vae": ["4", 2]}},
            "9": {"class_type": "SaveImage", "inputs": {"images": ["8", 0], "filename_prefix": fname}},
        }
    }


# ─── Primitive 1: mangaka.panel.batchRender ────────────────────────────────

async def task_batch_render(script: dict | None = None, charSlug: str = "",
                            checkpoint: str = DEFAULT_CHECKPOINT) -> dict:
    """Submit all panel prompts to ComfyUI pod, poll until done, upload to PDS.

    Returns: { panelBlobKeys: list[str], panelCount: int, durationMs: int, status: str }
    panelBlobKeys are SHA-256 CIDs (content-addressed) — flat array indexed by
    panel order: pages[0].panels[0..N], pages[1].panels[0..M], ...
    """
    started = time.time()
    if not script or not isinstance(script, dict):
        return {"error": "script is required (dict)", "status": "error"}

    pages = script.get("pages", [])
    flat = [(p["pageNum"], pn["panelNum"], pn["prompt"])
            for p in pages for pn in p.get("panels", [])]
    if not flat:
        return {"error": "script has no panels", "status": "error"}

    ts = int(time.time())
    async with aiohttp.ClientSession() as session:
        # Submit all
        prompt_ids: list[str] = []
        for idx, (pg, pn, prompt) in enumerate(flat):
            seed = ts + idx * 7
            fname = f"manga-v3-{charSlug}-{ts}-pg{pg}-pn{pn}"
            wf = _build_workflow(prompt, NEG_PROMPT, seed, fname, checkpoint)
            try:
                async with session.post(f"{POD_URL}/prompt", json=wf,
                                        timeout=aiohttp.ClientTimeout(total=10)) as r:
                    body = await r.json()
                    prompt_ids.append(body.get("prompt_id", ""))
            except Exception as e:
                LOG.warning("submit failed for panel %d-%d: %s", pg, pn, e)
                prompt_ids.append("")
            if idx % 20 == 0 and idx > 0:
                await asyncio.sleep(0.3)

        # Poll until all done (max 12 min)
        target = sum(1 for pid in prompt_ids if pid)
        for tick in range(90):
            await asyncio.sleep(8)
            done = 0
            for pid in prompt_ids:
                if not pid:
                    continue
                try:
                    async with session.get(f"{POD_URL}/history/{pid}",
                                           timeout=aiohttp.ClientTimeout(total=5)) as r:
                        h = await r.json()
                        if any("outputs" in v for v in h.values()):
                            done += 1
                except Exception:
                    pass
            LOG.info("mangaka.batchRender tick %d: %d/%d", tick + 1, done, target)
            if done >= target:
                break

        # Download + upload to PDS
        panel_blobs: list[str] = []
        for pid in prompt_ids:
            if not pid:
                panel_blobs.append("")
                continue
            try:
                async with session.get(f"{POD_URL}/history/{pid}",
                                       timeout=aiohttp.ClientTimeout(total=10)) as r:
                    h = await r.json()
                    fn = ""
                    for v in h.values():
                        for o in v.get("outputs", {}).values():
                            for img in o.get("images", []):
                                fn = img.get("filename", "")
                                break
                            if fn:
                                break
                        if fn:
                            break
                if not fn:
                    panel_blobs.append("")
                    continue
                async with session.get(f"{POD_URL}/view",
                                       params={"filename": fn, "type": "output"},
                                       timeout=aiohttp.ClientTimeout(total=30)) as r:
                    png_bytes = await r.read()
                cid, _size = await _pds_upload_blob(session, png_bytes)
                panel_blobs.append(cid)
            except Exception as e:
                LOG.warning("download/upload failed: %s", e)
                panel_blobs.append("")

    duration_ms = int((time.time() - started) * 1000)
    success = sum(1 for b in panel_blobs if b)
    return {
        "panelBlobKeys": panel_blobs,
        "panelCount": len(panel_blobs),
        "panelSuccess": success,
        "durationMs": duration_ms,
        "status": "ok" if success >= len(panel_blobs) * 0.95 else "partial",
    }


# ─── Primitive 2: mangaka.balloon.batchOverlay ─────────────────────────────

def _overlay_balloons(png_bytes: bytes, dialogues: list[dict]) -> bytes:
    """Apply speech balloons / narration boxes / SFX to a panel PNG."""
    from PIL import Image, ImageDraw, ImageFont

    FONT_NORMAL = "/System/Library/Fonts/ヒラギノ角ゴシック W8.ttc"
    FONT_BOLD = "/System/Library/Fonts/ヒラギノ角ゴシック W9.ttc"
    # Linux fallback (deployment env)
    LINUX_FONT = "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc"

    def _font(size: int):
        for path in (FONT_NORMAL, LINUX_FONT, "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"):
            try:
                return ImageFont.truetype(path, size)
            except (OSError, IOError):
                continue
        return ImageFont.load_default()

    img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    W, H = img.size
    draw = ImageDraw.Draw(img)
    font_size = max(20, W // 32)
    font = _font(font_size)

    def _wrap(text: str, max_chars: int):
        return [text[i:i + max_chars] for i in range(0, len(text), max_chars)]

    positions = [(W * 0.05, H * 0.05), (W * 0.55, H * 0.05),
                 (W * 0.05, H * 0.55), (W * 0.55, H * 0.55)]
    placed = 0

    for d in dialogues:
        text = (d.get("text") or "").strip()
        if not text:
            continue
        btype = d.get("balloonType", "normal")
        speaker = d.get("speaker", "")

        if btype == "narration" or speaker == "narration":
            lines = _wrap(text, max(8, W // (font_size // 2)))
            x, y = int(W * 0.05), int(H * 0.04)
            tw = max(draw.textbbox((0, 0), ln, font=font)[2] for ln in lines)
            th = sum(draw.textbbox((0, 0), ln, font=font)[3] for ln in lines) + (len(lines) - 1) * 4
            draw.rectangle([x - 12, y - 10, x + tw + 12, y + th + 10],
                           fill="white", outline="black", width=2)
            cy = y
            for ln in lines:
                draw.text((x, cy), ln, font=font, fill="black")
                cy += draw.textbbox((0, 0), ln, font=font)[3] + 4
        elif btype == "sfx" or speaker == "sfx":
            sfx_size = font_size * 2
            sfx_font = _font(sfx_size)
            x, y = int(W * 0.4), int(H * 0.3)
            for dx in (-2, -1, 0, 1, 2):
                for dy in (-2, -1, 0, 1, 2):
                    if dx == 0 and dy == 0:
                        continue
                    draw.text((x + dx, y + dy), text, font=sfx_font, fill="white")
            draw.text((x, y), text, font=sfx_font, fill="black")
        else:
            if placed >= len(positions):
                continue
            px, py = positions[placed]
            placed += 1
            lines = _wrap(text, max(8, W // (font_size + 4)))
            tw = max(draw.textbbox((0, 0), ln, font=font)[2] for ln in lines)
            th = sum(draw.textbbox((0, 0), ln, font=font)[3] for ln in lines) + (len(lines) - 1) * 4
            draw.ellipse([int(px) - 16, int(py) - 12, int(px) + tw + 16, int(py) + th + 12],
                         fill="white", outline="black", width=3)
            cy = int(py)
            for ln in lines:
                draw.text((int(px), cy), ln, font=font, fill="black")
                cy += draw.textbbox((0, 0), ln, font=font)[3] + 4

    out = io.BytesIO()
    img.save(out, "PNG", optimize=True)
    return out.getvalue()


async def task_batch_overlay(script: dict | None = None,
                              panelBlobKeys: list[str] | None = None) -> dict:
    """Apply Pillow speech-balloon overlay to every panel.

    Returns: { overlayBlobKeys: list[str], durationMs: int, status: str }
    """
    started = time.time()
    if not script or not panelBlobKeys:
        return {"error": "script + panelBlobKeys required", "status": "error"}

    pages = script.get("pages", [])
    dialogues_flat: list[list[dict]] = []
    for p in pages:
        for pn in p.get("panels", []):
            dialogues_flat.append(pn.get("dialogue", []))

    if len(dialogues_flat) != len(panelBlobKeys):
        LOG.warning("mismatch dialogues=%d panels=%d", len(dialogues_flat), len(panelBlobKeys))

    overlay_blobs: list[str] = []
    async with aiohttp.ClientSession() as session:
        for idx, cid in enumerate(panelBlobKeys):
            if not cid:
                overlay_blobs.append("")
                continue
            try:
                png = await _pds_get_blob(session, cid)
                dialogues = dialogues_flat[idx] if idx < len(dialogues_flat) else []
                if dialogues:
                    overlaid = _overlay_balloons(png, dialogues)
                else:
                    overlaid = png
                new_cid, _size = await _pds_upload_blob(session, overlaid)
                overlay_blobs.append(new_cid)
            except Exception as e:
                LOG.warning("overlay failed idx=%d: %s", idx, e)
                overlay_blobs.append(cid)  # fall back to original

    duration_ms = int((time.time() - started) * 1000)
    return {
        "overlayBlobKeys": overlay_blobs,
        "durationMs": duration_ms,
        "status": "ok",
    }


# ─── Primitive 3: mangaka.page.batchCompose ────────────────────────────────

LAYOUTS = {
    3: [(0.0, 0.00, 1.00, 0.40), (0.0, 0.42, 0.50, 0.58), (0.52, 0.42, 0.48, 0.58)],
    4: [(0.0, 0.00, 1.00, 0.30), (0.0, 0.32, 0.50, 0.34), (0.52, 0.32, 0.48, 0.34), (0.0, 0.68, 1.00, 0.32)],
    5: [(0.0, 0.00, 1.00, 0.26), (0.0, 0.28, 0.50, 0.34), (0.52, 0.28, 0.48, 0.34),
        (0.0, 0.64, 0.45, 0.36), (0.47, 0.64, 0.53, 0.36)],
    6: [(0.0, 0.00, 0.50, 0.32), (0.52, 0.00, 0.48, 0.32), (0.0, 0.34, 1.00, 0.32),
        (0.0, 0.68, 0.32, 0.32), (0.34, 0.68, 0.32, 0.32), (0.68, 0.68, 0.32, 0.32)],
    7: [(0.0, 0.00, 0.50, 0.28), (0.52, 0.00, 0.48, 0.28), (0.0, 0.30, 1.00, 0.30),
        (0.0, 0.62, 0.32, 0.38), (0.34, 0.62, 0.32, 0.38), (0.68, 0.62, 0.32, 0.18), (0.68, 0.82, 0.32, 0.18)],
}


def _compose_page(panel_pngs: list[bytes]) -> bytes:
    from PIL import Image, ImageDraw

    n = len(panel_pngs)
    n = max(3, min(7, n))
    panel_pngs = panel_pngs[:n]
    while len(panel_pngs) < n:
        panel_pngs.append(panel_pngs[-1])

    layout = LAYOUTS[n]
    page = Image.new("RGB", (PAGE_W, PAGE_H), "white")
    draw = ImageDraw.Draw(page)
    MARGIN = 30
    GUTTER = 18
    BORDER = 4
    inner_w = PAGE_W - 2 * MARGIN
    inner_h = PAGE_H - 2 * MARGIN

    for png, (xf, yf, wf, hf) in zip(panel_pngs, layout):
        x = MARGIN + int(xf * inner_w) + (GUTTER // 2 if xf > 0 else 0)
        y = MARGIN + int(yf * inner_h) + (GUTTER // 2 if yf > 0 else 0)
        w = int(wf * inner_w) - (GUTTER if 0 < xf < 1 - wf else GUTTER // 2)
        h = int(hf * inner_h) - (GUTTER if 0 < yf < 1 - hf else GUTTER // 2)

        panel = Image.open(io.BytesIO(png)).convert("RGB")
        pw, ph = panel.size
        panel_aspect = pw / ph
        target_aspect = w / h
        if panel_aspect > target_aspect:
            new_h = h
            new_w = int(new_h * panel_aspect)
            panel = panel.resize((new_w, new_h), Image.LANCZOS)
            crop_x = (new_w - w) // 2
            panel = panel.crop((crop_x, 0, crop_x + w, h))
        else:
            new_w = w
            new_h = int(new_w / panel_aspect)
            panel = panel.resize((new_w, new_h), Image.LANCZOS)
            crop_y = (new_h - h) // 2
            panel = panel.crop((0, crop_y, w, crop_y + h))
        page.paste(panel, (x, y))
        draw.rectangle([x, y, x + w, y + h], outline="black", width=BORDER)

    out = io.BytesIO()
    page.save(out, "PNG", optimize=True)
    return out.getvalue()


async def task_batch_compose(script: dict | None = None,
                              overlayBlobKeys: list[str] | None = None) -> dict:
    """Compose 20 pages from overlay panels.

    Returns: { pageBlobKeys: list[str], pageSizes: list[int], coverCid: str, status: str }
    """
    started = time.time()
    if not script or not overlayBlobKeys:
        return {"error": "script + overlayBlobKeys required", "status": "error"}

    pages = script.get("pages", [])
    page_blobs: list[str] = []
    page_sizes: list[int] = []

    async with aiohttp.ClientSession() as session:
        # Build flat panel index → page mapping
        panel_idx = 0
        for page_def in pages:
            page_panel_count = len(page_def.get("panels", []))
            page_panel_blobs = overlayBlobKeys[panel_idx:panel_idx + page_panel_count]
            panel_idx += page_panel_count

            try:
                pngs: list[bytes] = []
                for cid in page_panel_blobs:
                    if not cid:
                        continue
                    pngs.append(await _pds_get_blob(session, cid))
                if not pngs:
                    page_blobs.append("")
                    page_sizes.append(0)
                    continue
                page_png = _compose_page(pngs)
                cid, size = await _pds_upload_blob(session, page_png)
                page_blobs.append(cid)
                page_sizes.append(size)
            except Exception as e:
                LOG.warning("compose page failed: %s", e)
                page_blobs.append("")
                page_sizes.append(0)

    duration_ms = int((time.time() - started) * 1000)
    cover_cid = page_blobs[0] if page_blobs else ""
    return {
        "pageBlobKeys": page_blobs,
        "pageSizes": page_sizes,
        "coverCid": cover_cid,
        "durationMs": duration_ms,
        "status": "ok" if page_blobs and all(page_blobs) else "partial",
    }


# ─── Primitive 4: mangaka.records.batchInsertPages ─────────────────────────

async def task_batch_insert_pages(charSlug: str = "", script: dict | None = None,
                                  pageBlobKeys: list[str] | None = None,
                                  pageSizes: list[int] | None = None) -> dict:
    """Insert work + 20 page rows into vertex_mangaka via direct PG INSERT.

    Returns: { workVertexId: str, pageVertexIds: list[str], status: str }
    """
    started = time.time()
    if not script or not pageBlobKeys:
        return {"error": "script + pageBlobKeys required", "status": "error"}

    if not RW_URL:
        LOG.warning("RW_URL not set — skipping DB write (vertex_mangaka)")
        # Still return synthetic IDs so downstream tasks have something
        ts = int(time.time())
        work_vertex_id = f"at://did:web:mangaka.etzhayyim.com/com.etzhayyim.apps.mangaka.work/{charSlug}-{ts}"
        page_vertex_ids = [
            f"at://did:web:mangaka.etzhayyim.com/com.etzhayyim.apps.mangaka.page/{charSlug}-{ts}-p{i+1:02d}"
            for i in range(len(pageBlobKeys))
        ]
        return {"workVertexId": work_vertex_id, "pageVertexIds": page_vertex_ids,
                "durationMs": int((time.time() - started) * 1000), "status": "ok-skipped-db"}

    # Direct PG INSERT (Hyperdrive in prod, asyncpg locally)
    try:
        import asyncpg
    except ImportError:
        return {"error": "asyncpg not installed", "status": "error"}

    ts = int(time.time())
    title = script.get("title", f"{charSlug} 編")
    setting = script.get("setting", "")
    genre = script.get("genre", "shonen")
    panel_count = sum(len(p.get("panels", [])) for p in script.get("pages", []))

    conn = await asyncpg.connect(RW_URL)
    try:
        work_vertex_id = f"at://did:web:mangaka.etzhayyim.com/com.etzhayyim.apps.mangaka.work/{charSlug}-{ts}"
        await conn.execute(
            """INSERT INTO vertex_mangaka (vertex_id, owner_did, repo, did, collection, rkey,
                kind, title, description, stage, sensitivity_ord, page_id, panel_id, work_id, chapter_id)
               VALUES ($1, $2, $2, $3, $4, $5, $6, $7, $8, $9, $10, NULL, NULL, $11, NULL)
               ON CONFLICT (vertex_id) DO NOTHING""",
            work_vertex_id, "did:web:mangaka.etzhayyim.com",
            f"did:web:mangaka.etzhayyim.com:work:{charSlug}",
            "com.etzhayyim.apps.mangaka.work", f"{charSlug}-{ts}",
            "work", title, setting, "published", 10, f"{charSlug}-{ts}",
        )
        page_vertex_ids: list[str] = []
        pages = script.get("pages", [])
        for i, (page_def, blob, size) in enumerate(zip(pages, pageBlobKeys, pageSizes or [])):
            pg_num = i + 1
            page_vertex_id = f"at://did:web:mangaka.etzhayyim.com/com.etzhayyim.apps.mangaka.page/{charSlug}-{ts}-p{pg_num:02d}"
            await conn.execute(
                """INSERT INTO vertex_mangaka (vertex_id, owner_did, repo, did, collection, rkey,
                    kind, title, description, stage, sensitivity_ord, page_id, work_id, chapter_id)
                   VALUES ($1, $2, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, NULL)
                   ON CONFLICT (vertex_id) DO NOTHING""",
                page_vertex_id, "did:web:mangaka.etzhayyim.com",
                f"did:web:mangaka.etzhayyim.com:page:{charSlug}-{pg_num:02d}",
                "com.etzhayyim.apps.mangaka.page", f"{charSlug}-{ts}-p{pg_num:02d}",
                "page", f"Page {pg_num}", page_def.get("act", ""), "published", 10,
                f"{charSlug}-{ts}-p{pg_num:02d}", f"{charSlug}-{ts}",
            )
            page_vertex_ids.append(page_vertex_id)
    finally:
        await conn.close()

    duration_ms = int((time.time() - started) * 1000)
    return {
        "workVertexId": work_vertex_id,
        "pageVertexIds": page_vertex_ids,
        "panelCount": panel_count,
        "durationMs": duration_ms,
        "status": "ok",
    }


# ─── Primitive 5: mangaka.post.publish ─────────────────────────────────────

async def task_post_publish(workUri: str = "", charName: str = "", charSlug: str = "",
                            genre: str = "shonen", setting: str = "",
                            pageBlobKeys: list[str] | None = None,
                            pageSizes: list[int] | None = None,
                            panelCount: int = 0) -> dict:
    """Publish app.bsky.feed.post (recordWithMedia + facets pointing to work).

    Returns: { postUri: str, postCid: str, status: str }
    """
    started = time.time()
    if not workUri or not pageBlobKeys:
        return {"error": "workUri + pageBlobKeys required", "status": "error"}

    # work URI looks like: at://did:web:mangaka.etzhayyim.com/com.etzhayyim.apps.mangaka.work/{rkey}
    work_rkey = workUri.rsplit("/", 1)[-1]
    slug_flat = charSlug.replace("-", "")
    link_text = f"mangaka.etzhayyim.com/at/did:web:mangaka.etzhayyim.com/com.etzhayyim.apps.mangaka.work/{work_rkey}"
    text = (f"📕 {charName} 編 ({genre}) — 20 ページ完結\n\n"
            f"設定: {setting}\nコマ数: {panelCount}\n\n"
            f"#manga #{genre} #shinshi #{slug_flat} {link_text}")
    text_bytes = text.encode("utf-8")

    def _byte_range(needle: str):
        idx = text_bytes.find(needle.encode("utf-8"))
        return None if idx < 0 else [idx, idx + len(needle.encode("utf-8"))]

    facets = []
    for tag in ("manga", genre, "shinshi", slug_flat):
        r = _byte_range("#" + tag)
        if r:
            facets.append({"index": {"byteStart": r[0], "byteEnd": r[1]},
                           "features": [{"$type": "app.bsky.richtext.facet#tag", "tag": tag}]})
    r = _byte_range(link_text)
    if r:
        facets.append({"index": {"byteStart": r[0], "byteEnd": r[1]},
                       "features": [{"$type": "app.bsky.richtext.facet#link",
                                      "uri": "https://" + link_text}]})

    # Use first 4 page covers as the embedded carousel
    images = []
    for i, (cid, size) in enumerate(zip(pageBlobKeys[:4], (pageSizes or [0, 0, 0, 0])[:4])):
        if not cid:
            continue
        alt = f"ページ{i+1}"
        if i == 0:
            alt += f" - {charName} in {setting}"
        images.append({"image": {"$type": "blob", "ref": {"$link": cid},
                                  "mimeType": "image/png", "size": int(size)}, "alt": alt})

    record = {
        "repo": "did:web:mangaka.etzhayyim.com",
        "collection": "app.bsky.feed.post",
        "record": {
            "$type": "app.bsky.feed.post",
            "text": text,
            "facets": facets,
            "createdAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "embed": {
                "$type": "app.bsky.embed.recordWithMedia",
                "record": {"$type": "app.bsky.embed.record",
                            "record": {"uri": workUri, "cid": work_rkey}},
                "media": {"$type": "app.bsky.embed.images", "images": images},
            },
        },
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{ATPROTO_BASE}/xrpc/com.atproto.repo.createRecord",
            json=record,
            headers={"Content-Type": "application/json", "x-kotoba-kotodama-verified": PDS_TOKEN},
            timeout=aiohttp.ClientTimeout(total=60),
        ) as resp:
            body = await resp.json()

    duration_ms = int((time.time() - started) * 1000)
    return {
        "postUri": body.get("uri", ""),
        "postCid": body.get("cid", ""),
        "facetCount": len(facets),
        "imageCount": len(images),
        "durationMs": duration_ms,
        "status": "ok" if body.get("uri") else "error",
    }


# ─── Registration helper ────────────────────────────────────────────────────

def register(worker, timeout_ms: int = 600_000) -> None:
    """Register all 5 mangaka primitives with the LangServer worker.

    Call from zeebe_worker_main.py after generic.* primitives:

        from kotodama.primitives import mangaka
        mangaka.register(worker)
    """
    worker.task(task_type="mangaka.panel.batchRender",       single_value=False, timeout_ms=timeout_ms)(task_batch_render)
    worker.task(task_type="mangaka.balloon.batchOverlay",    single_value=False, timeout_ms=timeout_ms)(task_batch_overlay)
    worker.task(task_type="mangaka.page.batchCompose",       single_value=False, timeout_ms=timeout_ms)(task_batch_compose)
    worker.task(task_type="mangaka.records.batchInsertPages", single_value=False, timeout_ms=timeout_ms)(task_batch_insert_pages)
    worker.task(task_type="mangaka.post.publish",            single_value=False, timeout_ms=timeout_ms)(task_post_publish)
