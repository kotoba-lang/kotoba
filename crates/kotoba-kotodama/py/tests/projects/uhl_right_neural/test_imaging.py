"""V03 ImagingActor tests."""
from __future__ import annotations

import pytest

from kotodama.projects.uhl_right_neural.actors.imaging import (
    CnFiberRead,
    IacAplasiaCall,
    ImagingActor,
    ImagingInput,
    ImagingResult,
)


def test_aplastic_call_forces_zero_count() -> None:
    read = CnFiberRead(
        ear="right",
        cn_fiber_strands=2,  # contradictory; radiologist call wins
        fn_fiber_strands=3,
        radiologist_call=IacAplasiaCall.APLASTIC,
    )
    result = ImagingActor._fuse(read)
    assert result.cn_fiber_count == 0
    assert any("overriding" in n for n in result.notes)


def test_cn_fn_ratio_hypoplasia_flag() -> None:
    read = CnFiberRead(
        ear="right",
        cn_fiber_strands=1,
        fn_fiber_strands=3,
    )
    result = ImagingActor._fuse(read)
    assert result.cn_fn_ratio == pytest.approx(0.333, abs=1e-3)
    assert result.cn_hypoplastic_by_ratio is True


def test_normal_ratio_no_hypoplasia_flag() -> None:
    read = CnFiberRead(
        ear="right",
        cn_fiber_strands=3,
        fn_fiber_strands=3,
        radiologist_call=IacAplasiaCall.NORMAL,
    )
    result = ImagingActor._fuse(read)
    assert result.cn_fiber_count == 3
    assert result.cn_hypoplastic_by_ratio is False


def test_compute_emits_substrate_evidence_delta() -> None:
    state = {
        "imaging_input": {
            "read": {
                "ear": "right",
                "cn_fiber_strands": 0,
                "radiologist_call": "aplastic",
                "fn_fiber_strands": 3,
            }
        },
        "substrate_evidence": {"eabr_present": True},
    }
    delta = ImagingActor.compute(state)
    assert delta["substrate_evidence"]["cn_fiber_count"] == 0
    # prior keys preserved
    assert delta["substrate_evidence"]["eabr_present"] is True
    assert delta["requires_human_review"] is True


def test_compute_no_input_emits_absent_marker() -> None:
    delta = ImagingActor.compute({})
    assert delta["imaging_result"] == {"_absent": True}


def test_iac_stenosis_flag_propagates() -> None:
    state = {
        "imaging_input": {
            "read": {
                "ear": "right",
                "cn_fiber_strands": 2,
                "fn_fiber_strands": 3,
                "iac_stenosis": True,
            }
        }
    }
    delta = ImagingActor.compute(state)
    assert delta["imaging_result"]["iac_stenosis"] is True
    assert any("stenosis" in n for n in delta["imaging_result"]["notes"])
