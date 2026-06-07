"""R1.2 — kotoba_vm client surface reservation.

The R2 wire shape is locked in today via a NotImplementedError that carries
the target POST URL + body fields so callers see exactly what will land.
"""

from __future__ import annotations

import pytest

from kotoba_murakumo.client import kotoba_vm
from kotoba_murakumo.client.kotoba_vm import InvokeRequest, InvokeResult
from kotoba_murakumo.exceptions import MurakumoCompatNotImplemented


def test_invoke_request_and_result_dataclasses_present() -> None:
    req = InvokeRequest(
        program_cid="bafyA",
        args_cid="bafyB",
        caller_did="did:web:caller.etzhayyim.com",
        gas_limit=42,
    )
    assert req.program_cid == "bafyA"
    assert req.args_cid == "bafyB"
    assert req.gas_limit == 42

    res = InvokeResult(result_cid="bafyC", gas_used=17, program_cid="bafyA")
    assert res.result_cid == "bafyC"
    assert res.gas_used == 17


def test_invoke_raises_with_r2_plan_in_message() -> None:
    req = InvokeRequest(
        program_cid="bafyA", args_cid="bafyB",
        caller_did="did:web:x.etzhayyim.com",
    )
    with pytest.raises(MurakumoCompatNotImplemented) as ei:
        kotoba_vm.invoke(server_url="http://judah.local:8088", request=req)
    msg = str(ei.value)
    # Target XRPC NSID is present so callers know exactly the R2 endpoint.
    assert "com.etzhayyim.kotoba.vm.invoke" in msg
    assert "judah.local:8088" in msg
    assert "bafyA" in msg


def test_invoke_async_signature_present() -> None:
    """Async sibling is importable + raises with R2 reason."""
    import asyncio

    async def run() -> None:
        req = InvokeRequest(
            program_cid="bafyA", args_cid="bafyB",
            caller_did="did:web:x.etzhayyim.com",
        )
        with pytest.raises(MurakumoCompatNotImplemented):
            await kotoba_vm.invoke_async(
                server_url="http://judah.local:8088", request=req,
            )

    asyncio.run(run())
