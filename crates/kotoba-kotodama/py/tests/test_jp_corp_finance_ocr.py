from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

Image = pytest.importorskip("PIL.Image")

from kotodama.ingest.jp_corp_finance.ocr import (
    convert_image_to_webp,
    guess_kind,
    parse_ocr_json,
)
from kotodama.ingest.jp_corp_finance.zeebe_tasks import task_jp_corp_finance_webp_ocr


def test_guess_kind_pdf_by_extension() -> None:
    assert guess_kind("kanpo.pdf") == "pdf"


def test_guess_kind_pdf_by_content_type() -> None:
    assert guess_kind("download", "application/pdf") == "pdf"


def test_guess_kind_image_by_extension() -> None:
    assert guess_kind("page.webp") == "image"


def test_parse_ocr_json_plain_object() -> None:
    parsed = parse_ocr_json('{"pageText":"abc","tables":[]}')
    assert parsed["pageText"] == "abc"


def test_parse_ocr_json_code_fence() -> None:
    parsed = parse_ocr_json('```json\n{"pageText":"abc","tables":[]}\n```')
    assert parsed["tables"] == []


def test_convert_image_to_webp(tmp_path: Path) -> None:
    src = tmp_path / "source.png"
    dest = tmp_path / "page.webp"
    Image.new("RGB", (12, 10), color=(255, 255, 255)).save(src)
    page = convert_image_to_webp(src, dest, quality=80)
    assert page.path == dest
    assert page.byte_size > 0
    assert len(page.sha256) == 64


def test_webp_ocr_dry_run_image(tmp_path: Path) -> None:
    src = tmp_path / "source.png"
    Image.new("RGB", (12, 10), color=(255, 255, 255)).save(src)
    result = asyncio.run(task_jp_corp_finance_webp_ocr(sourcePath=str(src), dryRun=True))
    assert result["ok"] is True
    assert result["kind"] == "image"
    assert result["pages"][0]["byteSize"] > 0
    assert result["ocr"] == []


def test_webp_ocr_requires_source() -> None:
    result = asyncio.run(task_jp_corp_finance_webp_ocr())
    assert result["ok"] is False
    assert "sourcePath or contentB64 required" in result["error"]
