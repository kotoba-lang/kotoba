from __future__ import annotations

import base64
import hashlib
import json
import mimetypes
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

DEFAULT_LLM_URL = "https://llm.etzhayyim.com/v1/chat/completions"
DEFAULT_MODEL = "gemma-4-e2b-it"
OCR_PROMPT = """\
OCR this Japanese corporate financial disclosure page.
Return ONLY valid JSON:
{
  "pageText": "<full OCR text preserving line breaks>",
  "tables": [
    {
      "title": "<table title or empty>",
      "rows": [["cell", "cell"]]
    }
  ],
  "companyName": "<company name if visible>",
  "periodEnd": "YYYY-MM-DD or empty",
  "warnings": ["<uncertainty>"]
}
Do not infer numbers that are not visible. Preserve Japanese labels exactly."""


@dataclass(frozen=True)
class WebpPage:
    page_index: int
    path: Path
    sha256: str
    byte_size: int
    cid: str = ""
    ipfs_url: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "pageIndex": self.page_index,
            "path": str(self.path),
            "sha256": self.sha256,
            "byteSize": self.byte_size,
            "cid": self.cid,
            "ipfsUrl": self.ipfs_url,
        }


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def guess_kind(path: str, content_type: str = "") -> str:
    lowered = path.lower()
    ctype = content_type.lower()
    if lowered.endswith(".pdf") or ctype == "application/pdf":
        return "pdf"
    if ctype.startswith("image/") or lowered.endswith((".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff")):
        return "image"
    guessed = mimetypes.guess_type(path)[0] or ""
    if guessed == "application/pdf":
        return "pdf"
    if guessed.startswith("image/"):
        return "image"
    return "unknown"


def available_pdf_renderer() -> str:
    for name in ("pdftoppm", "mutool", "magick"):
        if shutil.which(name):
            return name
    return ""


def convert_image_to_webp(source: Path, dest: Path, *, quality: int = 82) -> WebpPage:
    from PIL import Image

    with Image.open(source) as img:
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGB")
        img.save(dest, format="WEBP", quality=quality, method=6)
    data = dest.read_bytes()
    return WebpPage(page_index=0, path=dest, sha256=sha256_bytes(data), byte_size=len(data))


def _render_pdf_page_to_png(pdf_path: Path, out_png: Path, page_index: int, dpi: int) -> None:
    renderer = available_pdf_renderer()
    page_no = page_index + 1
    if renderer == "pdftoppm":
        prefix = out_png.with_suffix("")
        subprocess.run(
            [
                "pdftoppm",
                "-f",
                str(page_no),
                "-l",
                str(page_no),
                "-r",
                str(dpi),
                "-png",
                str(pdf_path),
                str(prefix),
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        generated = Path(f"{prefix}-{page_no}.png")
        if not generated.exists():
            generated = Path(f"{prefix}-1.png")
        generated.replace(out_png)
        return
    if renderer == "mutool":
        subprocess.run(
            ["mutool", "draw", "-r", str(dpi), "-o", str(out_png), str(pdf_path), str(page_no)],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return
    if renderer == "magick":
        subprocess.run(
            ["magick", "-density", str(dpi), f"{pdf_path}[{page_index}]", str(out_png)],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return
    raise RuntimeError("no PDF renderer found; install pdftoppm, mutool, or ImageMagick")


def convert_pdf_to_webp_pages(
    pdf_path: Path,
    out_dir: Path,
    *,
    max_pages: int = 3,
    dpi: int = 180,
    quality: int = 82,
) -> list[WebpPage]:
    max_pages = max(1, min(int(max_pages or 1), 20))
    out_dir.mkdir(parents=True, exist_ok=True)
    pages: list[WebpPage] = []
    for page_index in range(max_pages):
        png_path = out_dir / f"page-{page_index + 1:04d}.png"
        webp_path = out_dir / f"page-{page_index + 1:04d}.webp"
        try:
            _render_pdf_page_to_png(pdf_path, png_path, page_index, dpi)
        except subprocess.CalledProcessError as exc:
            if page_index == 0:
                stderr = exc.stderr.decode("utf-8", errors="replace") if exc.stderr else str(exc)
                raise RuntimeError(f"PDF render failed: {stderr[:500]}") from exc
            break
        if not png_path.exists() or png_path.stat().st_size == 0:
            if page_index == 0:
                raise RuntimeError("PDF render produced no page image")
            break
        page = convert_image_to_webp(png_path, webp_path, quality=quality)
        pages.append(WebpPage(page_index=page_index, path=page.path, sha256=page.sha256, byte_size=page.byte_size))
        png_path.unlink(missing_ok=True)
    return pages


async def upload_webp_pages_to_ipfs(pages: list[WebpPage], *, filename_prefix: str = "page") -> list[WebpPage]:
    from kotodama.primitives.ipfs_ingest import add_content

    uploaded: list[WebpPage] = []
    for page in pages:
        filename = f"{filename_prefix}-{page.page_index + 1:04d}.webp"
        cid = await add_content(page.path.read_bytes(), filename)
        uploaded.append(
            WebpPage(
                page_index=page.page_index,
                path=page.path,
                sha256=page.sha256,
                byte_size=page.byte_size,
                cid=cid,
                ipfs_url=f"https://ipfs.etzhayyim.com/ipfs/{cid}",
            )
        )
    return uploaded


async def call_gemma4_ocr(
    page: WebpPage,
    *,
    model: str = "",
    prompt: str = OCR_PROMPT,
    llm_url: str = "",
) -> dict[str, Any]:
    if not page.ipfs_url:
        raise ValueError("page.ipfs_url required before OCR")
    payload = {
        "model": model or os.environ.get("JP_CORP_FINANCE_OCR_MODEL", DEFAULT_MODEL),
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": page.ipfs_url}},
                ],
            }
        ],
        "temperature": 0.0,
        "max_tokens": 4000,
    }
    headers = {"Content-Type": "application/json", "x-kotoba-kotodama-verified": "true"}
    token = os.environ.get("LLM_etzhayyim_BEARER", "")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    async with httpx.AsyncClient(timeout=180, follow_redirects=True) as client:
        res = await client.post(
            llm_url or os.environ.get("LLM_CHAT_COMPLETIONS_URL", DEFAULT_LLM_URL),
            json=payload,
            headers=headers,
        )
    res.raise_for_status()
    data = res.json()
    choice = (data.get("choices") or [{}])[0]
    finish_reason = str(choice.get("finish_reason") or "")
    content = str((choice.get("message") or {}).get("content") or "")
    if finish_reason.startswith("error:") or (not content and finish_reason):
        raise RuntimeError(f"OCR LLM failed: finish_reason={finish_reason} content={content[:500]}")
    return parse_ocr_json(content)


def parse_ocr_json(content: str) -> dict[str, Any]:
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        text = text[start : end + 1]
    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        raise ValueError("OCR response JSON was not an object")
    return parsed


async def convert_upload_ocr(
    source_path: str,
    *,
    content_type: str = "",
    max_pages: int = 3,
    quality: int = 82,
    dry_run: bool = False,
) -> dict[str, Any]:
    path = Path(source_path)
    if not path.exists():
        raise FileNotFoundError(source_path)
    kind = guess_kind(str(path), content_type)
    with tempfile.TemporaryDirectory(prefix="jp-corp-finance-ocr-") as tmp:
        out_dir = Path(tmp)
        if kind == "pdf":
            pages = convert_pdf_to_webp_pages(path, out_dir, max_pages=max_pages, quality=quality)
        elif kind == "image":
            pages = [convert_image_to_webp(path, out_dir / "page-0001.webp", quality=quality)]
        else:
            raise ValueError(f"unsupported OCR source kind: {kind}")
        if dry_run:
            return {"ok": True, "kind": kind, "pages": [p.to_dict() for p in pages], "ocr": []}
        uploaded = await upload_webp_pages_to_ipfs(pages, filename_prefix=path.stem or "page")
        ocr = []
        for page in uploaded:
            ocr.append({"pageIndex": page.page_index, "result": await call_gemma4_ocr(page)})
        return {"ok": True, "kind": kind, "pages": [p.to_dict() for p in uploaded], "ocr": ocr}


def content_b64_to_temp_file(content_b64: str, suffix: str) -> Path:
    raw = base64.b64decode(content_b64.split(",", 1)[-1])
    tmp = tempfile.NamedTemporaryFile(prefix="jp-corp-finance-source-", suffix=suffix, delete=False)
    path = Path(tmp.name)
    with tmp:
        tmp.write(raw)
    return path
