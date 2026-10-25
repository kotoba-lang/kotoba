from __future__ import annotations

import cbor2

from etzhayyim_sdk import cursor


def test_checkpoint_roundtrip(tmp_path):
    path = tmp_path / "cursor.edn"
    cursor._store(path, 42)
    assert path.read_text() == "{:cursor/seq 42}\n"
    assert cursor._load(path) == 42


def test_decode_commit_frame():
    frame = cbor2.dumps({"op": 1, "t": "#commit"}) + cbor2.dumps({"seq": 7, "repo": "did:plc:test"})
    assert cursor._decode_frame(frame) == {"seq": 7, "repo": "did:plc:test"}


def test_invalid_checkpoint_is_rejected(tmp_path):
    path = tmp_path / "cursor.edn"
    path.write_text('{"seq": 42}\n')
    try:
        cursor._load(path)
    except ValueError:
        return
    raise AssertionError("JSON checkpoint must not be accepted as canonical state")
