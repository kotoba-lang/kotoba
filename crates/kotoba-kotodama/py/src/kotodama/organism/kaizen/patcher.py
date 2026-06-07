
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Literal

from kotodama.organism.sensors.charter_rider import scan_with_normalization

log = logging.getLogger(__name__)


class KaizenPatchError(Exception):
    """Raised when a patch cannot be applied."""


class KaizenCharterViolationError(Exception):
    """Raised when a patch introduces a Charter §2 violation."""

    def __init__(self, message: str, scan_result: dict):
        super().__init__(message)
        self.scan_result = scan_result


PatchKind = Literal["string_replace", "line_insert", "line_delete", "append"]


class KaizenPatcher:
    """Applies a declarative patch to a file, with safety checks."""

    def apply_patch(self, target_file: Path, patch_hint: dict[str, Any]) -> bool:
        """
        Applies a patch to a target file based on a patch hint.

        The patch is applied atomically: if a Charter §2 violation is detected
        after patching, the file is reverted to its original state.

        Args:
            target_file: The path to the file to be patched.
            patch_hint: A dictionary describing the patch to be applied.
                        Expected format varies by `kind`.

        Returns:
            True if the patch was applied successfully.
            False if the patch was a no-op (e.g., old string not found).

        Raises:
            KaizenPatchError: If the file cannot be read/written or the
                              patch hint is malformed for the given kind.
            KaizenCharterViolationError: If the applied patch introduces a
                                         Charter §2 violation.
            ValueError: If the patch_hint format is invalid.
        """
        kind = patch_hint.get("kind")
        if not kind:
            raise ValueError("Patch hint must have a 'kind' field.")

        if not target_file.is_file():
            raise KaizenPatchError(f"Target file not found or is not a file: {target_file}")

        try:
            original_content = target_file.read_text(encoding="utf-8")
        except OSError as e:
            raise KaizenPatchError(f"Error reading target file {target_file}: {e}") from e

        new_content = self._compute_new_content(original_content, patch_hint)

        if new_content == original_content:
            return False

        # After applying the patch, check for charter violations
        scan_result = scan_with_normalization(new_content)
        if not scan_result.get("passed", True):
            # The file has not been written yet, so no revert is needed.
            raise KaizenCharterViolationError(
                f"Patch for {target_file} introduced a Charter §2 violation.",
                scan_result=scan_result,
            )

        try:
            target_file.write_text(new_content, encoding="utf-8")
            log.info(f"Successfully applied patch to {target_file}")
        except OSError as e:
            # Attempt to revert
            log.warning(f"Failed to write patch to {target_file}, attempting to revert.")
            try:
                target_file.write_text(original_content, encoding="utf-8")
            except OSError as revert_e:
                raise KaizenPatchError(
                    f"Failed to apply patch and also failed to revert {target_file}. "
                    f"Original error: {e}. Revert error: {revert_e}"
                ) from revert_e
            raise KaizenPatchError(f"Error writing patched file {target_file}: {e}") from e

        return True

    def _compute_new_content(self, original_content: str, patch_hint: dict[str, Any]) -> str:
        """Computes the new file content based on the patch hint."""
        kind = patch_hint.get("kind")

        if kind == "string_replace":
            old_string = patch_hint.get("old_string")
            new_string = patch_hint.get("new_string")
            if old_string is None or new_string is None:
                raise ValueError("string_replace requires 'old_string' and 'new_string'.")
            return original_content.replace(old_string, new_string)

        elif kind == "append":
            new_string = patch_hint.get("new_string")
            if new_string is None:
                raise ValueError("append requires 'new_string'.")
            return original_content + new_string

        elif kind == "line_insert":
            anchor = patch_hint.get("anchor")
            new_string = patch_hint.get("new_string")
            if anchor is None or new_string is None:
                raise ValueError("line_insert requires 'anchor' and 'new_string'.")
            lines = original_content.splitlines(True)
            try:
                idx = next(i for i, line in enumerate(lines) if anchor in line)
                lines.insert(idx + 1, new_string + "\n")
                return "".join(lines)
            except StopIteration:
                return original_content  # Anchor not found, no-op

        elif kind == "line_delete":
            line_number = patch_hint.get("line_number")
            if line_number is None:
                raise ValueError("line_delete requires 'line_number'.")
            if not isinstance(line_number, int) or line_number <= 0:
                raise ValueError("'line_number' must be a positive integer.")
            lines = original_content.splitlines(True)
            if line_number > len(lines):
                return original_content  # Line number out of bounds, no-op
            del lines[line_number - 1]
            return "".join(lines)

        else:
            raise ValueError(f"Unknown patch kind: {kind}")
