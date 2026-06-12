"""Tests for kotoba_modal.

No network and no wasm toolchain: a fake transport stands in for the node. For
the component path, a *node simulator* transport decodes the ctx envelope and
runs the body through the real guest glue (`guest.handle_invoke`), so the full
client-encode ↔ guest-decode contract is exercised in pure CPython.
"""

import base64
import json
import math
import os
import shutil
import subprocess
import sys
import tomllib
import types
import zipfile

import pytest

import kotoba_modal as modal
from kotoba_modal import _cbor, _codec, guest
from kotoba_modal._client import INFER_RUN_NSID, INVOKE_RUN_NSID


# ── transports ──────────────────────────────────────────────────────────────

class FakeTransport:
    """Records (nsid, body, headers); returns a canned response."""

    def __init__(self, status=200, response=None):
        self.status = status
        self.response = response if response is not None else {"status": "ok"}
        self.calls = []

    def __call__(self, nsid, body, headers):
        self.calls.append((nsid, body, dict(headers)))
        text = self.response if isinstance(self.response, str) else json.dumps(self.response)
        return self.status, text


# A minimal valid bare DID (passes the node's validate_did) + dummy component.
TEST_DID = "did:key:zTestAgent"
DUMMY_WASM = b"\x00asm\x01\x00\x00\x00"


class NodeSim:
    """Simulates the real kotoba `invoke_run` handler closely enough to catch
    client-side contract bugs: requires wasm_b64 + a non-empty bare agent_did
    (mirroring `validate_did` / "wasm_b64 required for wasm programs"), then runs
    `fn` through the real guest glue and returns output_b64. infer.run echoes
    an uppercased reply."""

    def __init__(self, fn=None):
        self.fn = fn
        self.calls = []

    def __call__(self, nsid, body, headers):
        self.calls.append((nsid, body, dict(headers)))
        if nsid == INVOKE_RUN_NSID:
            did = body.get("agent_did", "")
            if not did or not did.startswith("did:") or did.count(":") < 2:
                return 400, "agent_did must be a bare DID"
            if not body.get("wasm_b64") and body.get("program_type") != "datalog":
                return 400, "wasm_b64 required for wasm programs"
            ctx = base64.b64decode(body["ctx_b64"])
            out = guest.handle_invoke(ctx, self.fn)  # the actual guest path
            return 200, json.dumps(
                {"status": "ok", "gas_used": 1, "output_b64": base64.b64encode(out).decode()}
            )
        if nsid == INFER_RUN_NSID:
            return 200, json.dumps({"status": "ok", "output": body["prompt"].upper()})
        return 404, "unknown nsid"


def make_app(transport, agent_did=TEST_DID, **kw):
    client = modal.KotobaNodeClient(
        "http://node.local", token="tok", internal_secret="sek", transport=transport, **kw
    )
    return modal.App("test", client=client, agent_did=agent_did)


# ── bundled CBOR + codec ────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "value",
    [None, True, False, 0, 1, 23, 24, 255, 256, 65535, 70000, -1, -24, -300,
     3.14, "hi", "日本語", b"\x00\x01\xff", [], [1, "a", [2]], {}, {"k": "v", "n": 5}],
)
def test_cbor_roundtrip(value):
    assert _cbor.loads(_cbor.dumps(value)) == value


def test_codec_ctx_roundtrip():
    blob = _codec.encode_ctx("fn", (1, "x"), {"k": [True, None]})
    name, args, kwargs = _codec.decode_ctx(blob)
    assert name == "fn" and args == [1, "x"] and kwargs == {"k": [True, None]}


def test_codec_result_roundtrip_and_error():
    assert _codec.decode_result(_codec.encode_result({"r": 42})) == {"r": 42}
    with pytest.raises(modal.RemoteError):
        _codec.decode_result(_codec.encode_error("boom"))


# ── guest glue: full client↔guest contract ──────────────────────────────────

def test_guest_handle_invoke_full_contract():
    def add(a, b):
        return {"sum": a + b}

    ctx = _codec.encode_ctx("add", (2, 3), {})
    out = guest.handle_invoke(ctx, add)          # what the node would run
    assert _codec.decode_result(out) == {"sum": 5}  # what the client would decode


def test_guest_handle_invoke_captures_body_exception():
    def boom(x):
        raise ValueError("nope")

    out = guest.handle_invoke(_codec.encode_ctx("boom", ("x",), {}), boom)
    with pytest.raises(modal.RemoteError) as ei:
        _codec.decode_result(out)
    assert "ValueError" in ei.value.body


# ── .remote() — py→wasm→kotoba via invoke.run ────────────────────────────────

def test_remote_dispatches_invoke_run_and_runs_body():
    def transform(text, suffix="!"):
        return f"{text.upper()}{suffix}"

    sim = NodeSim(fn=transform)
    app = make_app(sim)

    @app.function(wasm=DUMMY_WASM, program_cid="bafyMeta")
    def transform_fn(text, suffix="!"):
        return transform(text, suffix)  # same body the "node" runs

    assert transform_fn.remote("hi", suffix="?") == "HI?"
    nsid, body, headers = sim.calls[0]
    assert nsid == INVOKE_RUN_NSID
    assert body["program_type"] == "wasm-node"
    assert body["agent_did"] == TEST_DID
    assert body["wasm_b64"] == base64.b64encode(DUMMY_WASM).decode()
    assert headers["Authorization"] == "Bearer tok"
    assert headers["x-internal-trust"] == "sek"
    # ctx the node received decodes to the original call
    _name, args, kwargs = _codec.decode_ctx(base64.b64decode(body["ctx_b64"]))
    assert args == ["hi"] and kwargs == {"suffix": "?"}


def test_remote_wasm_path_works_without_toolchain(tmp_path):
    """The real 'works today' path: dispatch a pre-built .wasm (no build needed)."""
    wfile = tmp_path / "comp.wasm"
    wfile.write_bytes(DUMMY_WASM)
    sim = NodeSim(fn=lambda x: x[::-1])
    app = make_app(sim)

    @app.function(wasm_path=str(wfile))
    def rev(x):
        return x[::-1]

    assert rev.remote("abc") == "cba"
    assert sim.calls[0][1]["wasm_b64"] == base64.b64encode(DUMMY_WASM).decode()


def test_remote_map():
    sim = NodeSim(fn=lambda x: x * 2)
    app = make_app(sim)

    @app.function(wasm=DUMMY_WASM)
    def double(x):
        return x * 2

    assert double.map([1, 2, 3]) == [2, 4, 6]


def test_remote_without_toolchain_raises_toolchain_not_found(monkeypatch):
    monkeypatch.delenv("KOTOBA_PYWASM_BUILD", raising=False)
    monkeypatch.delenv("COMPONENTIZE_PY", raising=False)
    monkeypatch.setattr("shutil.which", lambda _name: None)  # componentize-py off PATH
    sim = NodeSim(fn=lambda x: x)
    app = make_app(sim)

    @app.function()  # no wasm, no wasm_path, no builder → must build → none
    def needs_build(x):
        return x

    with pytest.raises(modal.ToolchainNotFound) as ei:
        needs_build.remote("x")
    assert "toolchain" in str(ei.value).lower()
    assert sim.calls == []  # never dispatched


def test_remote_requires_agent_did(monkeypatch):
    monkeypatch.delenv("KOTOBA_AGENT_DID", raising=False)  # App falls back to env
    sim = NodeSim(fn=lambda x: x)
    app = make_app(sim, agent_did="")  # missing DID

    @app.function(wasm=DUMMY_WASM)
    def f(x):
        return x

    with pytest.raises(modal.ConfigError) as ei:
        f.remote("x")
    assert "agent_did" in str(ei.value)
    assert sim.calls == []  # guarded before dispatch


def test_remote_propagates_guest_error():
    def boom(x):
        raise RuntimeError("guest blew up")

    sim = NodeSim(fn=boom)
    app = make_app(sim)

    @app.function(wasm=DUMMY_WASM)
    def f(x):
        return boom(x)

    with pytest.raises(modal.RemoteError) as ei:
        f.remote("x")
    assert "guest blew up" in ei.value.body


# ── .local() — CPython body, llm → HTTP infer.run ────────────────────────────

def test_local_runs_body_with_http_llm():
    sim = NodeSim()
    app = make_app(sim)

    @app.function()
    def summarize(text):
        return modal.llm.invoke(f"Summarize:\n{text}")

    assert summarize.local("doc") == "SUMMARIZE:\nDOC"  # NodeSim infer = upper
    nsid, body, _ = sim.calls[0]
    assert nsid == INFER_RUN_NSID
    assert body["prompt"] == "Summarize:\ndoc"


def test_local_max_new_tokens_default_applied():
    t = FakeTransport(response={"status": "ok", "output": "x"})
    app = make_app(t)

    @app.function(max_new_tokens=77)
    def g(p):
        return modal.llm.invoke(p)

    g.local("hi")
    assert t.calls[0][1]["max_new_tokens"] == 77


def test_chat_message_list_flattened():
    t = FakeTransport(response={"status": "ok", "output": "ok"})
    app = make_app(t)

    @app.function()
    def chat(msgs):
        return modal.llm.invoke(msgs)

    chat.local([{"role": "user", "content": "hello"}, {"role": "user", "content": "world"}])
    assert t.calls[0][1]["prompt"] == "hello\nworld"


# ── auth / config / errors ───────────────────────────────────────────────────

def test_llm_invoke_without_active_app_raises():
    with pytest.raises(modal.NoActiveAppError):
        modal.llm.invoke("orphan")


def test_config_error_without_node(monkeypatch):
    monkeypatch.delenv("KOTOBA_NODE_URL", raising=False)
    with pytest.raises(modal.ConfigError):
        _ = modal.App("nope").client


def test_remote_error_on_non_2xx():
    t = FakeTransport(status=503, response="wasm runtime feature disabled")
    app = make_app(t)

    @app.function(wasm=DUMMY_WASM)
    def f(x):
        return x

    with pytest.raises(modal.RemoteError) as ei:
        f.remote("x")
    assert ei.value.status == 503
    assert ei.value.nsid == INVOKE_RUN_NSID


# ── edge / error paths (robustness) ──────────────────────────────────────────

def test_cbor_unsupported_type_raises():
    with pytest.raises(TypeError):
        _cbor.dumps(object())


def test_cbor_trailing_bytes_raises():
    blob = _cbor.dumps(1) + b"\xff"
    with pytest.raises(ValueError):
        _cbor.loads(blob)


@pytest.mark.parametrize("value", [0.0, -2.5, 1e308, float("inf")])
def test_cbor_float64_roundtrip(value):
    assert _cbor.loads(_cbor.dumps(value)) == value


def test_cbor_decodes_float32_and_float16():
    import struct

    # float32: major 7, info 26
    assert abs(_cbor.loads(b"\xfa" + struct.pack(">f", 1.5)) - 1.5) < 1e-6
    # float16 1.0 = 0x3C00
    assert _cbor.loads(b"\xf9\x3c\x00") == 1.0


def test_cbor_large_int_widths():
    for v in [0xFF, 0xFFFF, 0xFFFFFFFF, 0xFFFFFFFFFF, -0x1_0000_0000]:
        assert _cbor.loads(_cbor.dumps(v)) == v


def test_codec_decode_ctx_rejects_non_map():
    with pytest.raises(ValueError):
        _codec.decode_ctx(_cbor.dumps([1, 2, 3]))


def test_codec_decode_result_passthrough_non_envelope():
    # A guest that returns a bare value (not our envelope) is handed back as-is.
    assert _codec.decode_result(_cbor.dumps(42)) == 42


def test_guest_handles_malformed_ctx():
    out = guest.handle_invoke(b"\xff\xff not cbor", lambda: None)
    with pytest.raises(modal.RemoteError) as ei:
        _codec.decode_result(out)
    assert "ctx decode failed" in ei.value.body


def test_guest_handles_unencodable_result():
    out = guest.handle_invoke(_codec.encode_ctx("f", (), {}), lambda: object())
    with pytest.raises(modal.RemoteError) as ei:
        _codec.decode_result(out)
    assert "result encode failed" in ei.value.body


def test_guest_make_run_binds_fn():
    run = guest.make_run(lambda a, b: a - b)
    assert _codec.decode_result(run(_codec.encode_ctx("f", (5, 2), {}))) == 3


def test_remote_returns_none_on_empty_output():
    def sim(nsid, body, headers):
        return 200, json.dumps({"status": "ok", "output_b64": ""})

    app = make_app(sim)

    @app.function(wasm=DUMMY_WASM)
    def f(x):
        return x

    assert f.remote("x") is None


def test_client_non_json_response_wrapped():
    t = FakeTransport(response="plain text body")
    client = modal.KotobaNodeClient("http://n", transport=t)
    # _post wraps a non-JSON 2xx body as {"output": text}
    assert client.infer("hi") == "plain text body"


def test_client_invoke_forwards_optional_fields():
    t = FakeTransport(response={"status": "ok", "output_b64": ""})
    client = modal.KotobaNodeClient("http://n", transport=t)
    client.invoke("cid", "ctx", agent_did="did:key:z", wasm_b64="V0FTTQ==", graph_cid="bafyGraph")
    body = t.calls[0][1]
    assert body["graph_cid"] == "bafyGraph"
    assert body["wasm_b64"] == "V0FTTQ=="


def test_llm_flattens_message_objects_with_content_attr():
    class Msg:
        def __init__(self, content):
            self.content = content

    t = FakeTransport(response={"status": "ok", "output": "ok"})
    app = make_app(t)

    @app.function()
    def chat(msgs):
        return modal.llm.invoke(msgs)

    chat.local([Msg("alpha"), Msg("beta")])
    assert t.calls[0][1]["prompt"] == "alpha\nbeta"


def test_build_have_builder_false_without_config(monkeypatch):
    from kotoba_modal import _build

    monkeypatch.delenv("KOTOBA_PYWASM_BUILD", raising=False)
    monkeypatch.delenv("COMPONENTIZE_PY", raising=False)
    monkeypatch.delenv("BB_BIN", raising=False)
    monkeypatch.setattr("shutil.which", lambda _name: None)
    assert _build.have_builder() is False
    assert _build.have_builder("/no/such/script.bb") is False


def test_build_bundled_assets_present():
    """The toolchain is bundled: WIT + build script ship with the package."""
    from kotoba_modal import _build

    assert os.path.isfile(_build.BUNDLED_WIT)
    assert os.path.isfile(_build.BUNDLED_SCRIPT)
    assert os.access(_build.BUNDLED_SCRIPT, os.X_OK)
    package_root = os.path.dirname(os.path.abspath(modal.__file__))
    assert os.path.commonpath([package_root, _build.BUNDLED_WIT]) == package_root
    assert os.path.commonpath([package_root, _build.BUNDLED_SCRIPT]) == package_root


def test_build_package_metadata_includes_babashka_builder():
    """Packaging metadata must ship the Babashka builder and never the old sh."""
    pkg_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(pkg_root, "pyproject.toml"), "rb") as f:
        project = tomllib.load(f)
    package_data = project["tool"]["setuptools"]["package-data"]["kotoba_modal"]
    assert "scripts/build-pywasm.bb" in package_data
    assert "scripts/build-pywasm.sh" not in package_data

    with open(os.path.join(pkg_root, "MANIFEST.in"), encoding="utf-8") as f:
        manifest = f.read()
    assert "include scripts/build-pywasm.bb" in manifest
    assert "include kotoba_modal/scripts/build-pywasm.bb" in manifest
    assert "build-pywasm.sh" not in manifest


def test_build_wheel_includes_babashka_builder(tmp_path):
    """The built wheel must contain the bundled bb builder, not the old sh."""
    pkg_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    build_dir = os.path.join(pkg_root, "build")
    egg_info = os.path.join(pkg_root, "kotoba_modal.egg-info")
    shutil.rmtree(build_dir, ignore_errors=True)
    shutil.rmtree(egg_info, ignore_errors=True)
    try:
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "wheel",
                ".",
                "--no-deps",
                "--no-build-isolation",
                "--no-index",
                "-w",
                str(tmp_path),
            ],
            cwd=pkg_root,
            check=True,
            timeout=120,
        )
        wheels = list(tmp_path.glob("kotoba_modal-*.whl"))
        assert len(wheels) == 1
        with zipfile.ZipFile(wheels[0]) as wheel:
            names = set(wheel.namelist())
        assert "kotoba_modal/scripts/build-pywasm.bb" in names
        assert "kotoba_modal/scripts/build-pywasm.sh" not in names
    finally:
        shutil.rmtree(build_dir, ignore_errors=True)
        shutil.rmtree(egg_info, ignore_errors=True)


def test_build_resolves_explicit_builder(monkeypatch, tmp_path):
    from kotoba_modal import _build

    script = tmp_path / "b.bb"
    script.write_text("#!/usr/bin/env bb\n")
    monkeypatch.setenv("KOTOBA_PYWASM_BUILD", str(script))
    assert _build.resolve_builder() == str(script)


def test_build_falls_back_to_bundled_when_componentize_present(monkeypatch):
    from kotoba_modal import _build

    monkeypatch.delenv("KOTOBA_PYWASM_BUILD", raising=False)
    monkeypatch.setenv("COMPONENTIZE_PY", "/usr/bin/componentize-py")
    monkeypatch.setenv("BB_BIN", "/usr/local/bin/bb")
    assert _build.resolve_builder() == _build.BUNDLED_SCRIPT


def test_build_rejects_empty_toolchain_env(monkeypatch):
    from kotoba_modal import _build

    monkeypatch.delenv("KOTOBA_PYWASM_BUILD", raising=False)
    monkeypatch.setenv("COMPONENTIZE_PY", "")
    monkeypatch.setenv("BB_BIN", "")
    monkeypatch.setattr("shutil.which", lambda _name: None)
    assert _build.resolve_builder() is None
    assert _build.have_builder() is False


def test_build_rejects_empty_explicit_builder(monkeypatch):
    from kotoba_modal import _build

    monkeypatch.setenv("KOTOBA_PYWASM_BUILD", "")
    monkeypatch.setenv("COMPONENTIZE_PY", "/usr/bin/componentize-py")
    monkeypatch.setenv("BB_BIN", "/usr/local/bin/bb")
    assert _build.resolve_builder() is None
    assert _build.have_builder() is False
    assert _build.resolve_builder(builder="   ") is None
    assert _build.have_builder(builder="   ") is False


# Integration: actually compile the sample guest to a real WASM component.
# Skipped unless componentize-py and Babashka are installed.
@pytest.mark.skipif(
    (
        not __import__("shutil").which("componentize-py")
        and not __import__("os").environ.get("COMPONENTIZE_PY")
    )
    or (
        not __import__("shutil").which("bb")
        and not __import__("os").environ.get("BB_BIN")
    ),
    reason="componentize-py or Babashka bb not available",
)
def test_build_sample_component_compiles(tmp_path):
    import os
    import subprocess

    pkg_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    entry = os.path.join(pkg_root, "examples", "guest_component.py")
    out = tmp_path / "generate.wasm"
    script = os.path.join(pkg_root, "scripts", "build-pywasm.bb")
    bb = os.environ.get("BB_BIN") or "bb"
    subprocess.run([bb, script, entry, "-o", str(out)], check=True, timeout=900)
    data = out.read_bytes()
    assert data[:4] == b"\x00asm"  # WASM magic
    assert len(data) > 1000


# ── default urllib transport ─────────────────────────────────────────────────

def test_urllib_transport_success(monkeypatch):
    import urllib.request

    class FakeResp:
        status = 200

        def read(self):
            return b'{"status":"ok","output":"hi"}'

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=None: FakeResp())
    client = modal.KotobaNodeClient("http://n", token="t", internal_secret="s")
    assert client.infer("x") == "hi"


def test_urllib_transport_http_error(monkeypatch):
    import io
    import urllib.error
    import urllib.request

    def boom(req, timeout=None):
        raise urllib.error.HTTPError("http://n", 500, "err", {}, io.BytesIO(b"bad"))

    monkeypatch.setattr(urllib.request, "urlopen", boom)
    client = modal.KotobaNodeClient("http://n")
    with pytest.raises(modal.RemoteError) as ei:
        client.infer("x")
    assert ei.value.status == 500


# ── llm WIT in-component seam (injected fake bindings) ───────────────────────

def test_llm_uses_wit_import_when_in_component(monkeypatch):
    llmmod = types.SimpleNamespace(infer=lambda mc, pb: b"WIT:" + pb)
    impmod = types.ModuleType("wit_world.imports")
    impmod.llm = llmmod
    witmod = types.ModuleType("wit_world")
    witmod.imports = impmod
    monkeypatch.setitem(sys.modules, "wit_world", witmod)
    monkeypatch.setitem(sys.modules, "wit_world.imports", impmod)
    monkeypatch.setitem(sys.modules, "wit_world.imports.llm", llmmod)
    # No active App needed — the WIT branch short-circuits before active_app().
    assert modal.llm.invoke("hi") == "WIT:hi"


def test_llm_uses_kotoba_kais_fallback(monkeypatch):
    llmmod = types.SimpleNamespace(infer=lambda mc, pb: b"KAIS:" + pb)
    impmod = types.ModuleType("kotoba_kais.imports")
    impmod.llm = llmmod
    kmod = types.ModuleType("kotoba_kais")
    kmod.imports = impmod
    monkeypatch.setitem(sys.modules, "wit_world", None)  # force primary import fail
    monkeypatch.setitem(sys.modules, "kotoba_kais", kmod)
    monkeypatch.setitem(sys.modules, "kotoba_kais.imports", impmod)
    monkeypatch.setitem(sys.modules, "kotoba_kais.imports.llm", llmmod)
    assert modal.llm.invoke("yo") == "KAIS:yo"


# ── build-then-dispatch + source-location guard ──────────────────────────────

def test_remote_builds_when_no_prebuilt(monkeypatch):
    monkeypatch.setattr("kotoba_modal._build.have_builder", lambda builder=None: True)
    monkeypatch.setattr(
        "kotoba_modal._build.build_component",
        lambda entry, out, builder=None, timeout=900: DUMMY_WASM,
    )
    sim = NodeSim(fn=lambda x: x.upper())
    app = make_app(sim)

    @app.function()  # no wasm/wasm_path → triggers the build path
    def f(x):
        return x.upper()

    assert f.remote("hi") == "HI"
    assert sim.calls[0][1]["wasm_b64"] == base64.b64encode(DUMMY_WASM).decode()


def test_remote_build_cannot_locate_source(monkeypatch):
    monkeypatch.setattr("kotoba_modal._build.have_builder", lambda builder=None: True)
    sim = NodeSim(fn=lambda x: x)
    app = make_app(sim)

    @app.function()
    def f(x):
        return x

    f._fn.__module__ = "no.such.module.xyz"  # not in sys.modules → no __file__
    with pytest.raises(modal.ToolchainNotFound) as ei:
        f.remote("x")
    assert "cannot locate source" in str(ei.value)
    assert sim.calls == []


# ── misc surface ─────────────────────────────────────────────────────────────

def test_function_callable_form_is_local():
    t = FakeTransport(response={"status": "ok", "output": "X"})
    app = make_app(t)

    @app.function()
    def g(p):
        return modal.llm.invoke(p)

    assert g("hi") == "X"  # __call__ → local → infer.run
    assert t.calls[0][0] == INFER_RUN_NSID


def test_app_run_local_context():
    t = FakeTransport(response={"status": "ok", "output": "R"})
    app = make_app(t)
    with app.run_local():
        assert modal.llm.invoke("hi") == "R"
    assert t.calls[0][0] == INFER_RUN_NSID


def test_cbor_reserved_additional_info_raises():
    with pytest.raises(ValueError):
        _cbor.loads(b"\x1c")  # major 0, additional-info 28 (reserved)


def test_cbor_float16_subnormal_inf_nan():
    assert _cbor.loads(b"\xf9\x00\x01") > 0          # smallest subnormal
    assert _cbor.loads(b"\xf9\x7c\x00") == float("inf")
    assert math.isnan(_cbor.loads(b"\xf9\x7e\x00"))


def test_build_component_invokes_script_and_reads_output(monkeypatch, tmp_path):
    """Cover build_component's shell-out + read without needing componentize-py."""
    from kotoba_modal import _build

    script = tmp_path / "b.bb"
    script.write_text("#!/usr/bin/env bb\n")
    out = tmp_path / "o.wasm"
    seen = []

    def fake_run(cmd, check, timeout):
        seen.append(cmd)
        out.write_bytes(b"\x00asm\x01\x00\x00\x00")

    monkeypatch.setenv("BB_BIN", "/usr/local/bin/bb")
    monkeypatch.setattr("kotoba_modal._build.subprocess.run", fake_run)
    data = _build.build_component("entry.py", str(out), builder=str(script))
    assert data[:4] == b"\x00asm"
    assert seen[0] == ["/usr/local/bin/bb", str(script), "entry.py", "-o", str(out)]


def test_build_component_raises_without_builder(monkeypatch, tmp_path):
    from kotoba_modal import _build

    monkeypatch.delenv("KOTOBA_PYWASM_BUILD", raising=False)
    monkeypatch.delenv("COMPONENTIZE_PY", raising=False)
    monkeypatch.delenv("BB_BIN", raising=False)
    monkeypatch.setattr("shutil.which", lambda _name: None)
    with pytest.raises(modal.ToolchainNotFound):
        _build.build_component("e.py", str(tmp_path / "o.wasm"))
