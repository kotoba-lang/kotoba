
import json
import logging
import re
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from .proposal_to_pr_draft import kaizen_proposal_to_pr_draft

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

HUMAN_IN_LOOP_BOILERPLATE = """

---
**Human Review Required**

This PR was generated automatically by the Kaizen agent. As per ADR-2605266700 (Gate G5), it requires human review and approval before merging. If this proposal touches Charter §2(a)-(h) areas, a minimum of three attestations from Council Level 6+ members is required.
"""

class KaizenPrAgentAuthError(Exception):
    """Raised when GitHub CLI authentication fails."""
    pass

class KaizenPrAgent:
    """
    Consumes Kaizen proposals, creates branches, applies patches, and opens GitHub PRs.
    """
    def __init__(self, proposal_queue_path: Path, repo_root: Path, dry_run: bool = True):
        self.proposal_queue_path = proposal_queue_path
        self.repo_root = repo_root
        self.dry_run = dry_run
        self._verify_gh_auth()

    def _verify_gh_auth(self):
        """Verifies that the GitHub CLI is authenticated."""
        try:
            logging.info("Verifying GitHub CLI authentication status...")
            # Use --hostname github.com to be explici
            result = subprocess.run(
                ["gh", "auth", "status"],
                capture_output=True, text=True, check=True, cwd=self.repo_root
            )
            logging.info("GitHub CLI is authenticated.")
        except FileNotFoundError:
            raise KaizenPrAgentAuthError("`gh` command not found. Is the GitHub CLI installed and in your PATH?")
        except subprocess.CalledProcessError as e:
            logging.error("GitHub CLI authentication failed.")
            logging.error(f"Stderr: {e.stderr}")
            raise KaizenPrAgentAuthError(f"GitHub CLI authentication failed: {e.stderr}")

    def _apply_patch(self, proposal: Dict[str, Any]) -> List[Path]:
        """
        Applies the patch suggested in the proposal.
        For R1.0, this handles simple string replacement based on `patchHint`.
        """
        suggested_action = proposal.get("suggestedAction", {})
        target_files_str = suggested_action.get("targetFiles", [])
        patch_hint = suggested_action.get("patchHint", "")

        # Prefer structured, machine-applicable edits when present — they target
        # a file + selector unambiguously (no first-occurrence guessing, no hint
        # string parsing). Falls through to patch_hint only when absent.
        patch_edits = suggested_action.get("patchEdits") or []
        if patch_edits:
            return self._apply_structured_edits(patch_edits)

        if not target_files_str or not patch_hint:
            logging.warning("No target files or patch hint found in proposal. Skipping patch.")
            return []

        if "->" not in patch_hint:
            raise NotImplementedError(f"Simple patch format 'old -> new' not found in hint: '{patch_hint}'")

        parts = [p.strip() for p in patch_hint.split("->")]
        if len(parts) != 2:
            raise ValueError(f"Could not parse patch hint '{patch_hint}'. Expected 'old -> new'.")

        # This is a very basic interpretation for R1.0
        old_text, new_text = parts[0], parts[1]
        # remove surrounding quotes if present (accept both ' and ")
        def _unquote(s: str) -> str:
            if len(s) >= 2 and s[0] == s[-1] and s[0] in ("'", '"'):
                return s[1:-1]
            return s
        old_text = _unquote(old_text)
        new_text = _unquote(new_text)


        modified_paths = []
        for file_str in target_files_str:
            target_path = self.repo_root / file_str
            if not target_path.is_file():
                logging.error(f"Target file {target_path} does not exist.")
                continue

            logging.info(f"Applying patch to {target_path}...")
            content = target_path.read_text()
            if old_text not in content:
                logging.warning(f"Patch hint '{old_text}' not found in {target_path}. Skipping.")
                continue

            new_content = content.replace(old_text, new_text, 1) # Replace only first occurrence for safety
            target_path.write_text(new_content)
            modified_paths.append(target_path)

        return modified_paths

    def _apply_structured_edits(self, edits: List[Dict[str, str]]) -> List[Path]:
        """Apply structured, machine-applicable edits (preferred path).

        Each edit targets one file by an unambiguous selector:
          - env-set ``{"file", "var", "value"}`` — set a k8s env var's value via
            a named-var regex (no first-occurrence guessing across the file).
          - literal ``{"file", "old", "new"}`` — first-occurrence str replace.
        """
        modified_paths: List[Path] = []
        for edit in edits:
            file_str = edit.get("file")
            if not file_str:
                logging.warning("Structured edit missing 'file'; skipping: %s", edit)
                continue
            target_path = self.repo_root / file_str
            if not target_path.is_file():
                logging.error(f"Target file {target_path} does not exist.")
                continue
            content = target_path.read_text()

            if "var" in edit and "value" in edit:
                var, value = edit["var"], edit["value"]
                # Match `name: <VAR>` then the following `value: ...` line and
                # replace only that var's value, preserving quote style.
                pattern = re.compile(
                    r'(name:\s*["\']?' + re.escape(var) + r'["\']?\s*\n\s*value:\s*)'
                    r'(["\']?)[^"\'\n]*(["\']?)'
                )
                new_content, n = pattern.subn(rf'\g<1>\g<2>{value}\g<3>', content, count=1)
                if n == 0:
                    logging.warning(
                        "env var %s not found in %s; skipping edit.", var, target_path
                    )
                    continue
            elif "old" in edit and "new" in edit:
                old, new = edit["old"], edit["new"]
                if old not in content:
                    logging.warning("literal '%s' not found in %s; skipping.", old, target_path)
                    continue
                new_content = content.replace(old, new, 1)
            else:
                logging.warning("Unrecognized structured edit shape; skipping: %s", edit)
                continue

            logging.info("Applied structured edit to %s", target_path)
            target_path.write_text(new_content)
            modified_paths.append(target_path)
        return modified_paths

    def consume_one(self) -> Optional[str]:
        """
        Consumes a single proposal from the queue.
        Returns the URL of the created PR, or a message for a dry run.
        """
        if not self.proposal_queue_path.exists() or self.proposal_queue_path.stat().st_size == 0:
            logging.info("Proposal queue is empty.")
            return None

        lines = self.proposal_queue_path.read_text().splitlines()
        proposal_ndjson = lines[0]
        remaining_lines = lines[1:]

        try:
            proposal = json.loads(proposal_ndjson)
        except json.JSONDecodeError:
            logging.error(f"Invalid JSON in queue: {proposal_ndjson}")
            # Move malformed line to a quarantine file or just drop i
            self.proposal_queue_path.write_text("\n".join(remaining_lines) + "\n")
            return None

        # 1. Generate Branch Name
        pr_hint = proposal.get("prAgentHint", {})
        branch_prefix = pr_hint.get("branchPrefix", "kaizen/proposal-")
        branch_name = f"{branch_prefix}{int(time.time())}"

        # 2. Create and switch to the new branch
        original_branch = subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"], text=True, cwd=self.repo_root).strip()
        logging.info(f"Creating and switching to branch: {branch_name}")
        subprocess.run(["git", "checkout", "-b", branch_name], check=True, cwd=self.repo_root, capture_output=True)

        try:
            # 3. Apply the patch
            modified_files = self._apply_patch(proposal)
            if not modified_files:
                logging.warning("Patch application resulted in no modified files. Aborting PR.")
                subprocess.run(["git", "checkout", original_branch], check=True, cwd=self.repo_root)
                subprocess.run(["git", "branch", "-D", branch_name], check=True, cwd=self.repo_root)
                return None

            # 4. Add files to gi
            for f_path in modified_files:
                # git add requires relative path from repo roo
                relative_path = f_path.relative_to(self.repo_root)
                logging.info(f"Staging file: {relative_path}")
                subprocess.run(["git", "add", str(relative_path)], check=True, cwd=self.repo_root)

            # 5. Create PR
            pr_title = proposal.get("summary", "Kaizen Proposal")
            pr_body = kaizen_proposal_to_pr_draft(proposal_ndjson)
            pr_body += HUMAN_IN_LOOP_BOILERPLATE

            labels = pr_hint.get("labels", [])

            gh_command = ["gh", "pr", "create", "--title", pr_title, "--body", pr_body]
            for label in labels:
                gh_command.extend(["--label", label])

            if self.dry_run:
                gh_command.append("--dry-run")
                logging.info("Executing dry-run of 'gh pr create'.")
            else:
                logging.info("Creating GitHub PR.")

            result = subprocess.run(gh_command, check=True, cwd=self.repo_root, capture_output=True, text=True)

            pr_url = result.stdout.strip().splitlines()[-1] if not self.dry_run else "Dry run successful."
            logging.info(f"PR result: {pr_url}")

            # 6. Update queue file
            self.proposal_queue_path.write_text("\n".join(remaining_lines) + "\n" if remaining_lines else "")
            logging.info("Proposal consumed and queue updated.")

            # 7. Return to original branch
            subprocess.run(["git", "checkout", original_branch], check=True, cwd=self.repo_root)

            return pr_url

        except (Exception, subprocess.CalledProcessError) as e:
            logging.error(f"Failed to process proposal: {e}")
            # Clean up: return to original branch and delete the new one
            logging.info("Cleaning up failed PR attempt...")
            subprocess.run(["git", "checkout", original_branch], check=True, cwd=self.repo_root)
            subprocess.run(["git", "branch", "-D", branch_name], check=True, cwd=self.repo_root)
            # Do not remove the proposal from the queue, so it can be retried
            raise

    def consume_all(self) -> List[str]:
        """
        Consumes all proposals in the queue until it's empty.
        Returns a list of created PR URLs.
        """
        urls = []
        while True:
            url = self.consume_one()
            if url is None:
                break
            urls.append(url)
        logging.info(f"Consumed {len(urls)} proposals.")
        return urls

