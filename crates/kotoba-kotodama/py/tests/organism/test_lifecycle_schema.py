import json
import os
from pathlib import Path

def test_organism_lifecycle_schema_valid():
    # The lexicon lives under the monorepo root's 00-contracts/ (canonical
    # namespace com.etzhayyim.organism.lifecycle), which is several parents
    # above the kotoba submodule. Walk up to find it so the test is robust
    # to both the monorepo and a standalone kotoba checkout.
    rel = Path("00-contracts") / "lexicons" / "com" / "etzhayyim" / "organism" / "lifecycle.json"
    here = Path(__file__).resolve()
    lexicon_path = next(
        (p / rel for p in here.parents if (p / rel).is_file()),
        here.parents[5] / rel,
    )

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
