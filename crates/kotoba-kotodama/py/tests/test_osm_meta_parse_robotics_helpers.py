"""Tests for uncovered pure helpers:
  primitives/os_messaging_open_channels._meta, _parse_messages
  primitives/robotics._manifest_items"""

from __future__ import annotations

import sys
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.primitives import os_messaging_open_channels as OSM  # noqa: E402
from kotodama.primitives import robotics as RB  # noqa: E402


# ─── os_messaging._meta ──────────────────────────────────────────────────────

def test_meta_extracts_og_title() -> None:
    html = '<meta property="og:title" content="My Channel Title">'
    assert OSM._meta(html, "og:title") == "My Channel Title"


def test_meta_extracts_og_description() -> None:
    html = '<meta property="og:description" content="Channel about crypto">'
    assert OSM._meta(html, "og:description") == "Channel about crypto"


def test_meta_extracts_name_attribute() -> None:
    html = '<meta name="description" content="Some description">'
    assert OSM._meta(html, "description") == "Some description"


def test_meta_returns_empty_when_not_found() -> None:
    html = "<html><body>no meta here</body></html>"
    assert OSM._meta(html, "og:title") == ""


def test_meta_empty_html_returns_empty() -> None:
    assert OSM._meta("", "og:title") == ""


def test_meta_strips_whitespace() -> None:
    html = '<meta property="og:title" content="  spaced  ">'
    assert OSM._meta(html, "og:title") == "spaced"


def test_meta_case_insensitive_tag() -> None:
    html = '<META property="og:title" content="Upper Case Tag">'
    assert OSM._meta(html, "og:title") == "Upper Case Tag"


def test_meta_single_quotes_content() -> None:
    html = "<meta property='og:title' content='Single Quotes'>"
    assert OSM._meta(html, "og:title") == "Single Quotes"


def test_meta_html_entity_unescaped() -> None:
    html = '<meta property="og:title" content="Hello &amp; World">'
    result = OSM._meta(html, "og:title")
    assert "&" in result


def test_meta_does_not_return_wrong_property() -> None:
    html = '<meta property="og:description" content="Description">'
    assert OSM._meta(html, "og:title") == ""


# ─── os_messaging._parse_messages ────────────────────────────────────────────

def test_parse_messages_non_telegram_returns_empty() -> None:
    assert OSM._parse_messages("line", "https://line.me/x", "<html/>") == []


def test_parse_messages_empty_html_returns_empty() -> None:
    assert OSM._parse_messages("telegram", "https://t.me/s/mychan", "") == []


def test_parse_messages_no_matching_blocks_returns_empty() -> None:
    html = "<html><body><p>Nothing here</p></body></html>"
    assert OSM._parse_messages("telegram", "https://t.me/s/mychan", html) == []


def test_parse_messages_extracts_message_id() -> None:
    html = (
        '<div class="tgme_widget_message" data-post="mychan/123">'
        '<div class="tgme_widget_message_text js-message_text">Hello world</div>'
        "</div></div>"
    )
    result = OSM._parse_messages("telegram", "https://t.me/s/mychan", html)
    if result:
        assert result[0]["message_id"] == "mychan-123"


def test_parse_messages_message_id_uses_dashes() -> None:
    html = (
        '<div class="tgme_widget_message" data-post="chan/456">'
        '<div class="tgme_widget_message_text">text</div>'
        "</div></div>"
    )
    result = OSM._parse_messages("telegram", "https://t.me/s/chan", html)
    if result:
        assert "/" not in result[0]["message_id"]


def test_parse_messages_caps_at_50() -> None:
    blocks = ""
    for i in range(60):
        blocks += (
            f'<div class="tgme_widget_message" data-post="ch/{i}">'
            f'<div class="tgme_widget_message_text">msg {i}</div>'
            "</div></div>"
        )
    result = OSM._parse_messages("telegram", "https://t.me/s/ch", blocks)
    assert len(result) <= 50


def test_parse_messages_has_required_keys() -> None:
    html = (
        '<div class="tgme_widget_message" data-post="ch/1">'
        '<div class="tgme_widget_message_text">Hello</div>'
        "</div></div>"
    )
    result = OSM._parse_messages("telegram", "https://t.me/s/ch", html)
    if result:
        assert "message_id" in result[0]
        assert "message_text" in result[0]
        assert "message_url" in result[0]
        assert "published_at" in result[0]


# ─── robotics._manifest_items ────────────────────────────────────────────────

def test_manifest_items_empty_dict_returns_empty() -> None:
    assert RB._manifest_items({}) == []


def test_manifest_items_none_returns_empty() -> None:
    assert RB._manifest_items(None) == []


def test_manifest_items_string_returns_empty() -> None:
    assert RB._manifest_items("not-a-dict") == []


def test_manifest_items_list_of_dicts() -> None:
    result = RB._manifest_items([{"path": "model.step", "kind": "cad"}])
    assert len(result) == 1
    assert result[0]["path"] == "model.step"
    assert result[0]["kind"] == "cad"


def test_manifest_items_dict_files_key() -> None:
    result = RB._manifest_items({"files": [{"path": "part.stl"}]})
    assert len(result) == 1


def test_manifest_items_dict_items_key() -> None:
    result = RB._manifest_items({"items": [{"path": "bom.csv"}]})
    assert result[0]["kind"] == "bom"


def test_manifest_items_dict_artifacts_key() -> None:
    result = RB._manifest_items({"artifacts": [{"path": "plan.gcode"}]})
    assert result[0]["kind"] == "cam"


def test_manifest_items_infers_cad_from_step() -> None:
    result = RB._manifest_items([{"path": "assembly.step"}])
    assert result[0]["kind"] == "cad"


def test_manifest_items_infers_cad_from_stp() -> None:
    result = RB._manifest_items([{"path": "part.stp"}])
    assert result[0]["kind"] == "cad"


def test_manifest_items_infers_mesh_from_stl() -> None:
    result = RB._manifest_items([{"path": "mesh.stl"}])
    assert result[0]["kind"] == "mesh"


def test_manifest_items_infers_mesh_from_obj() -> None:
    result = RB._manifest_items([{"path": "model.obj"}])
    assert result[0]["kind"] == "mesh"


def test_manifest_items_infers_cam_from_gcode() -> None:
    result = RB._manifest_items([{"path": "program.gcode"}])
    assert result[0]["kind"] == "cam"


def test_manifest_items_infers_bom_from_csv() -> None:
    result = RB._manifest_items([{"path": "bom.csv"}])
    assert result[0]["kind"] == "bom"


def test_manifest_items_infers_bom_from_xlsx() -> None:
    result = RB._manifest_items([{"path": "bom.xlsx"}])
    assert result[0]["kind"] == "bom"


def test_manifest_items_infers_drawing_from_pdf() -> None:
    result = RB._manifest_items([{"path": "drawing.pdf"}])
    assert result[0]["kind"] == "drawing"


def test_manifest_items_infers_drawing_from_png() -> None:
    result = RB._manifest_items([{"path": "photo.png"}])
    assert result[0]["kind"] == "drawing"


def test_manifest_items_unknown_extension_is_artifact() -> None:
    result = RB._manifest_items([{"path": "data.xyz"}])
    assert result[0]["kind"] == "artifact"


def test_manifest_items_explicit_kind_not_overridden() -> None:
    result = RB._manifest_items([{"path": "model.step", "kind": "mesh"}])
    assert result[0]["kind"] == "mesh"


def test_manifest_items_name_alias_for_path() -> None:
    result = RB._manifest_items([{"name": "assembly.iges"}])
    assert result[0]["path"] == "assembly.iges"
    assert result[0]["kind"] == "cad"


def test_manifest_items_uri_alias_for_path() -> None:
    result = RB._manifest_items([{"uri": "s3://bucket/part.nc"}])
    assert result[0]["path"] == "s3://bucket/part.nc"
    assert result[0]["kind"] == "cam"


def test_manifest_items_string_in_list_uses_as_path() -> None:
    result = RB._manifest_items(["model.step"])
    assert result[0]["path"] == "model.step"
    assert result[0]["kind"] == "cad"


def test_manifest_items_default_path_for_empty_dict() -> None:
    result = RB._manifest_items([{}])
    assert "artifact-1" in result[0]["path"]


def test_manifest_items_multiple_items() -> None:
    items = [{"path": "a.step"}, {"path": "b.csv"}, {"path": "c.pdf"}]
    result = RB._manifest_items(items)
    assert len(result) == 3
    kinds = {r["kind"] for r in result}
    assert "cad" in kinds and "bom" in kinds and "drawing" in kinds
