
import copy
import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

from kotodama.organism.kaizen.pr_agent import KaizenPrAgent, KaizenPrAgentAuthError, HUMAN_IN_LOOP_BOILERPLATE
from kotodama.organism.kaizen.proposal_to_pr_draft import kaizen_proposal_to_pr_draft


FAKE_PROPOSAL = {
  "v": 1,
  "ts": 1748131234567,
  "kind": "kaizen-proposal",
  "ruleId": "test-rule-001",
  "category": "refactor",
  "severity": "warn",
  "summary": "Refactor core logic to improve performance",
  "detail": "The main loop is inefficient and can be optimized.",
  "suggestedAction": {
    "kind": "code-change",
    "description": "Replace old_function with new_function.",
    "targetFiles": ["src/main.py"],
    "patchHint": "'old_function()' -> 'new_function()'",
    "testPlan": ["Run unit tests", "Run performance benchmark"]
  },
  "prAgentHint": {
    "branchPrefix": "kaizen/refactor-main-",
    "labels": ["kaizen", "performance", "refactor"],
  }
}

@pytest.fixture
def repo_root(tmp_path: Path) -> Path:
    """Creates a fake git repository and returns its root path."""
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    (repo_path / ".git").mkdir() # Simplified git check
    subprocess.run(["git", "init"], cwd=repo_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_path)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_path)

    # Create initial file and commi
    src_dir = repo_path / "src"
    src_dir.mkdir()
    (src_dir / "main.py").write_text("def old_function(): pass\n")
    subprocess.run(["git", "add", "."], cwd=repo_path)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo_path, capture_output=True)
    return repo_path

@pytest.fixture
def proposal_queue(tmp_path: Path) -> Path:
    """Creates a fake proposal queue file."""
    queue_path = tmp_path / "proposals.ndjson"
    queue_path.write_text(json.dumps(FAKE_PROPOSAL) + "\n")
    return queue_path

@pytest.fixture
def empty_proposal_queue(tmp_path: Path) -> Path:
    """Creates an empty fake proposal queue file."""
    queue_path = tmp_path / "proposals.ndjson"
    queue_path.touch()
    return queue_path

# ===================================
# Initialization and Auth Tests
# ===================================

@patch('subprocess.run')
def test_auth_success(mock_run, repo_root, proposal_queue):
    """Test successful authentication."""
    mock_run.return_value = MagicMock(check_returncode=lambda: None, stderr="")
    agent = KaizenPrAgent(proposal_queue, repo_root)
    mock_run.assert_called_once_with(
        ["gh", "auth", "status"],
        capture_output=True, text=True, check=True, cwd=repo_root
    )

@patch('subprocess.run', side_effect=FileNotFoundError("gh not found"))
def test_auth_failure_gh_not_found(mock_run, repo_root, proposal_queue):
    """Test auth failure when `gh` command is not found."""
    with pytest.raises(KaizenPrAgentAuthError, match="`gh` command not found"):
        KaizenPrAgent(proposal_queue, repo_root)

@patch('subprocess.run', side_effect=subprocess.CalledProcessError(1, "gh auth status", stderr="Authentication failed"))
def test_auth_failure_gh_error(mock_run, repo_root, proposal_queue):
    """Test auth failure when `gh` returns an error."""
    with pytest.raises(KaizenPrAgentAuthError, match="Authentication failed"):
        KaizenPrAgent(proposal_queue, repo_root)

# ===================================
# Consumption Tests
# ===================================

def test_empty_queue_returns_none(repo_root, empty_proposal_queue):
    """Test that consume_one returns None for an empty queue."""
    with patch('subprocess.run') as mock_run:
        mock_run.return_value = MagicMock(check_returncode=lambda: None)
        agent = KaizenPrAgent(empty_proposal_queue, repo_root)
        result = agent.consume_one()
        assert result is None

@patch('subprocess.check_output', return_value="main\n")
@patch('subprocess.run')
def test_consume_one_dry_run(mock_run, mock_check_output, repo_root, proposal_queue):
    """Test the full dry-run consumption of a single proposal."""
    # Auth call is separate, let's mock all subprocess calls
    mock_run.return_value = MagicMock(
        check_returncode=lambda: None,
        stdout="Running in dry-run mode",
        text=True
    )

    agent = KaizenPrAgent(proposal_queue, repo_root, dry_run=True)
    result = agent.consume_one()

    assert result == "Dry run successful."
    assert not proposal_queue.read_text() # Queue should be empty

    # Verify file content was patched
    patched_file = repo_root / "src" / "main.py"
    assert patched_file.read_text() == "def new_function(): pass\n"

    # Verify subprocess calls
    assert mock_check_output.call_count == 1

    calls = mock_run.call_args_list
    # 1. gh auth status (in __init__)
    # 2. git checkout -b <branch>
    # 3. git add src/main.py
    # 4. gh pr create ... --dry-run
    # 5. git checkout main
    assert len(calls) == 5

    # Check git branch creation
    assert call(["git", "checkout", "-b", mock_run.call_args_list[1].args[0][3]], check=True, cwd=repo_root, capture_output=True) in calls
    # Check git add
    assert call(["git", "add", "src/main.py"], check=True, cwd=repo_root) in calls

    # Check gh pr create call
    gh_call = calls[3]
    assert gh_call.args[0][0:4] == ["gh", "pr", "create", "--title"]
    assert gh_call.args[0][4] == FAKE_PROPOSAL["summary"]

    expected_body = kaizen_proposal_to_pr_draft(json.dumps(FAKE_PROPOSAL)) + HUMAN_IN_LOOP_BOILERPLATE
    assert gh_call.args[0][6] == expected_body
    assert "--label" in gh_call.args[0]
    assert "kaizen" in gh_call.args[0]
    assert "--dry-run" in gh_call.args[0]

    # Check git checkout main
    assert call(["git", "checkout", "main"], check=True, cwd=repo_root) in calls

@patch('subprocess.check_output', return_value="main\n")
@patch('subprocess.run')
def test_consume_one_real_run(mock_run, mock_check_output, repo_root, proposal_queue):
    """Test the real-run consumption of a single proposal."""
    pr_url = "https://github.com/etzhayyim/root/pull/123"
    mock_run.return_value = MagicMock(
        check_returncode=lambda: None,
        stdout=pr_url,
        text=True
    )

    agent = KaizenPrAgent(proposal_queue, repo_root, dry_run=False)
    result = agent.consume_one()

    assert result == pr_url
    gh_call = mock_run.call_args_list[3]
    assert "--dry-run" not in gh_call.args[0]

@patch('subprocess.check_output', return_value="main\n")
@patch('subprocess.run')
def test_consume_all(mock_run, mock_check_output, repo_root, tmp_path):
    """Test that consume_all drains the queue."""
    proposal_2 = copy.deepcopy(FAKE_PROPOSAL)
    proposal_2["summary"] = "Second proposal"
    # proposal 1 rewrites old_function -> new_function; proposal 2 targets the
    # post-patch text so both proposals apply against the shared repo fixture.
    proposal_2["suggestedAction"]["patchHint"] = "'new_function()' -> 'final_function()'"
    queue_content = json.dumps(FAKE_PROPOSAL) + "\n" + json.dumps(proposal_2) + "\n"
    queue_path = tmp_path / "multi_proposals.ndjson"
    queue_path.write_text(queue_content)

    mock_run.return_value = MagicMock(check_returncode=lambda: None, stdout="Dry run successful.")

    agent = KaizenPrAgent(queue_path, repo_root, dry_run=True)
    results = agent.consume_all()

    assert len(results) == 2
    assert not queue_path.read_text()
    # 1 auth, 2x (checkout, add, pr create, checkout) = 9 calls
    assert mock_run.call_count == 1 + (4 * 2)

@patch('subprocess.check_output', return_value="main\n")
@patch('subprocess.run')
def test_patch_fail_aborts_pr(mock_run, mock_check_output, repo_root, tmp_path):
    """Test that a failed patch cleans up and aborts the PR."""
    bad_proposal = copy.deepcopy(FAKE_PROPOSAL)
    bad_proposal["suggestedAction"]["patchHint"] = "'non_existent_string' -> 'wont_work'"
    queue_path = tmp_path / "bad_proposal.ndjson"
    queue_path.write_text(json.dumps(bad_proposal) + "\n")

    mock_run.return_value = MagicMock(check_returncode=lambda: None)

    agent = KaizenPrAgent(queue_path, repo_root, dry_run=True)
    result = agent.consume_one()

    assert result is None
    assert queue_path.read_text() # Queue should NOT be empty

    # Check that the temp branch was deleted
    calls = mock_run.call_args_list
    # 1. auth
    # 2. git checkout -b <branch>
    # 3. git checkout main
    # 4. git branch -D <branch>
    assert len(calls) == 4
    branch_name = calls[1].args[0][3]
    assert call(["git", "branch", "-D", branch_name], check=True, cwd=repo_root) in calls

    # Check that gh pr create was NOT called
    for c in calls:
        if "gh" in c.args[0]:
            assert c.args[0][1] == 'auth' # only auth call, no pr create
