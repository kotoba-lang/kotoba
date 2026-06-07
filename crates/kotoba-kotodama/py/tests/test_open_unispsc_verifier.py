from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def test_open_unispsc_verifier_writes_report(tmp_path: Path):
    root = Path(__file__).resolve().parents[1]
    report_path = tmp_path / "open-unispsc-mcp-verifier.json"
    env = dict(os.environ)
    env["PYTHONPATH"] = str(root / "src")

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/verify_open_unispsc_mcp.py",
            "--report-path",
            str(report_path),
        ],
        cwd=root,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    result = json.loads(report_path.read_text(encoding="utf-8"))
    assert result["ok"] is True
    assert result["coverage"]["toolCount"] == 20
    assert result["coverage"]["missing"] == []
    assert result["syncAllCommodityDids"]["segmentCount"] == 2
    assert result["syncAllCommodityDids"]["commandsPerSegment"] == 3
    assert result["segmentImport"]["importCommand"] == "import-unispsc-segment"
    assert result["segmentImport"]["transformTool"] == "com.etzhayyim.apps.openUnispsc.syncCatalogItem"
    assert result["catalogSync"]["catalogCollection"] == "com.etzhayyim.apps.okaimono.catalogItem"
    assert result["catalogSync"]["productId"] == "unispsc-43211501"
    assert result["purchasePlan"]["targetActorDid"] == "did:web:unispsc.etzhayyim.com:seg43"
    assert result["purchasePlan"]["mcpTool"] == "com.etzhayyim.apps.openUnispsc.itemGetSpec"
    assert set(result["workflowScenarios"]) == {"manualReview", "ready", "blocked"}
    assert result["workflowScenarios"]["manualReview"]["workflowStatus"] == "manual-review"
    assert result["workflowScenarios"]["ready"]["workflowStatus"] == "ready"
    assert result["workflowScenarios"]["blocked"]["workflowStatus"] == "blocked"
    assert result["workflow"]["validatedRows"] == 5
    assert result["applyPreview"]["statementCount"] == 5
