import json
import os
from pathlib import Path

def test_organism_lifecycle_schema_valid():
    # Load the lexicon JSON
    repo_root = Path(__file__).resolve().parent.parent.parent.parent.parent.parent
    lexicon_path = repo_root / "00-contracts" / "lexicons" / "app" / "etzhayyim" / "organism" / "lifecycle.json"

    assert lexicon_path.exists(), f"Lexicon not found at {lexicon_path}"

    with open(lexicon_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["lexicon"] == 1
    assert data["id"] == "com.etzhayyim.organism.lifecycle"

    defs = data["defs"]
    assert "main" in defs
    assert "birth" in defs
    assert "clone" in defs
    assert "retire" in defs
    assert "excommunication" in defs

    # Check main properties
    main_props = defs["main"]["record"]["properties"]
    assert "actorDid" in main_props
    assert "createdAt" in main_props
    assert "event" in main_props

    # Check excommunication constraints
    excomm_req = defs["excommunication"]["required"]
    assert "councilAttestation" in excomm_req
    assert "chigiriProcedureRef" in excomm_req

if __name__ == "__main__":
    test_organism_lifecycle_schema_valid()
    print("Test Passed!")
