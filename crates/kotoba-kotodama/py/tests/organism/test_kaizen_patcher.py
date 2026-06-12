
from __future__ import annotations

import pytest
from pathlib import Path
import sys

# Add src to path to allow imports
_py_src = Path(__file__).resolve().parents[2] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.organism.kaizen.patcher import (
    KaizenPatcher,
    KaizenPatchError,
    KaizenCharterViolationError,
)

INITIAL_CONTENT = """Line 1: Hello
Line 2: This is the original content.
Line 3: Goodbye
"""


@pytest.fixture
def patcher() -> KaizenPatcher:
    return KaizenPatcher()


@pytest.fixture
def temp_file(tmp_path: Path) -> Path:
    file_path = tmp_path / "test_file.txt"
    file_path.write_text(INITIAL_CONTENT, encoding="utf-8")
    return file_path


class TestKaizenPatcher:
    def test_apply_patch_string_replace_success(self, patcher: KaizenPatcher, temp_file: Path):
        patch_hint = {
            "kind": "string_replace",
            "old_string": "original content",
            "new_string": "modified content",
        }
        result = patcher.apply_patch(temp_file, patch_hint)
        assert result is True
        content = temp_file.read_text(encoding="utf-8")
        assert "modified content" in content
        assert "original content" not in content

    def test_apply_patch_string_replace_no_op(self, patcher: KaizenPatcher, temp_file: Path):
        patch_hint = {
            "kind": "string_replace",
            "old_string": "non-existent string",
            "new_string": "some string",
        }
        result = patcher.apply_patch(temp_file, patch_hint)
        assert result is False
        content = temp_file.read_text(encoding="utf-8")
        assert content == INITIAL_CONTENT

    def test_apply_patch_line_insert_success(self, patcher: KaizenPatcher, temp_file: Path):
        patch_hint = {
            "kind": "line_insert",
            "anchor": "Line 2",
            "new_string": "Line 2.5: Inserted line",
        }
        result = patcher.apply_patch(temp_file, patch_hint)
        assert result is True
        content = temp_file.read_text(encoding="utf-8")
        assert "Line 2.5: Inserted line" in content
        lines = content.splitlines()
        assert lines[0] == "Line 1: Hello"
        assert lines[1] == "Line 2: This is the original content."
        assert lines[2] == "Line 2.5: Inserted line"
        assert lines[3] == "Line 3: Goodbye"


    def test_apply_patch_line_delete_success(self, patcher: KaizenPatcher, temp_file: Path):
        patch_hint = {"kind": "line_delete", "line_number": 2}
        result = patcher.apply_patch(temp_file, patch_hint)
        assert result is True
        content = temp_file.read_text(encoding="utf-8")
        assert "original content" not in content
        lines = content.splitlines()
        assert len(lines) == 2
        assert lines[0] == "Line 1: Hello"
        assert lines[1] == "Line 3: Goodbye"

    def test_apply_patch_append_success(self, patcher: KaizenPatcher, temp_file: Path):
        patch_hint = {"kind": "append", "new_string": "\nLine 4: Appended"}
        result = patcher.apply_patch(temp_file, patch_hint)
        assert result is True
        content = temp_file.read_text(encoding="utf-8")
        assert content.endswith("Line 4: Appended")

    def test_charter_violation_raises_and_does_not_modify(
        self, patcher: KaizenPatcher, temp_file: Path
    ):
        # This patch introduces a "WEAPONS AND MILITARY" keyword
        patch_hint = {
            "kind": "string_replace",
            "old_string": "original content",
            "new_string": "new assault rifle",
        }
        with pytest.raises(KaizenCharterViolationError) as excinfo:
            patcher.apply_patch(temp_file, patch_hint)

        assert "introduced a Charter §2 violation" in str(excinfo.value)
        assert excinfo.value.scan_result["passed"] is False

        # Verify the file was not modified
        content = temp_file.read_text(encoding="utf-8")
        assert content == INITIAL_CONTENT

    def test_invalid_patch_kind_raises_value_error(self, patcher: KaizenPatcher, temp_file: Path):
        patch_hint = {"kind": "invalid_kind"}
        with pytest.raises(ValueError, match="Unknown patch kind: invalid_kind"):
            patcher.apply_patch(temp_file, patch_hint)

    @pytest.mark.parametrize(
        "patch_hint",
        [
            {"kind": "string_replace", "old_string": "foo"},
            {"kind": "append"},
            {"kind": "line_insert", "anchor": "foo"},
            {"kind": "line_delete"},
            {"kind": "line_delete", "line_number": "foo"},
        ],
    )
    def test_missing_keys_in_patch_hint_raises_value_error(
        self, patcher: KaizenPatcher, temp_file: Path, patch_hint: dict
    ):
        with pytest.raises(ValueError):
            patcher.apply_patch(temp_file, patch_hint)

    def test_file_not_found_raises_patch_error(self, patcher: KaizenPatcher, tmp_path: Path):
        non_existent_file = tmp_path / "no.txt"
        with pytest.raises(KaizenPatchError, match="Target file not found"):
            patcher.apply_patch(non_existent_file, {"kind": "append", "new_string": "foo"})
