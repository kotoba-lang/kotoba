"""ERC-8004 registration surface for the local artificial-organism agent."""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import logging
import os
import re
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib import error, request

from kotodama.agent_daemon_main import _now_iso
from kotodama.agent_status_main import load_status_report
from kotodama.local_agent_env import load_env_file, load_keychain_secret
from kotodama.primitives.active_inference import stable_hash

LOG = logging.getLogger("agent_erc8004")

ERC8004_SCHEMA = "https://etzhayyim.com/schemas/erc8004-agent-registration/v1.json"
DEFAULT_CHAIN_ID = 260425
DEFAULT_AGENT_REGISTRY = "0xcA3480edDAfa39c9377B83eEB18291286C8Cb865"
DEFAULT_IPFS_BASE = "https://ipfs.etzhayyim.com"
DEFAULT_RPC_URL = "https://geth.etzhayyim.com"
ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"

_HEX_ADDRESS_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")


def canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def registration_hash(payload: dict[str, Any]) -> str:
    return "sha256:" + stable_hash(json.loads(canonical_json(payload)))


def registration_bytes(payload: dict[str, Any]) -> bytes:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2, default=str)
    return (text + "\n").encode("utf-8")


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def build_agent_registration(
    *,
    agent_did: str,
    status_report: dict[str, Any],
    chain_id: int = DEFAULT_CHAIN_ID,
    agent_registry: str = DEFAULT_AGENT_REGISTRY,
    erc8004_agent_id: str = "TBD_AFTER_AGENT_REGISTRY_MINT",
    agent_uri: str = "ipfs://TBD_AGENT_REGISTRATION_CID",
    root_did: str = "",
    root_address: str = "",
    smart_account: str = "",
    policy_cid: str = "",
    runtime_policy_cid: str = "",
    public_status_url: str = "http://127.0.0.1:8765",
    mcp_endpoint: str = "",
    a2a_endpoint: str = "",
) -> dict[str, Any]:
    root = root_did or f"did:erc725:etzhayyim:{chain_id}:{root_address or ZERO_ADDRESS}"
    agent_registry_ref = f"eip155:{chain_id}:{agent_registry}"
    status_hash = registration_hash(status_report) if status_report else ""
    return {
        "schema": ERC8004_SCHEMA,
        "agent": {
            "agentRegistry": agent_registry_ref,
            "agentId": erc8004_agent_id,
            "agentURI": agent_uri,
        },
        "rootIdentity": {
            "kind": "erc725-root",
            "chainId": chain_id,
            "address": root_address or ZERO_ADDRESS,
            "rootDid": root,
            "facadeDids": [agent_did],
            "didPkh": f"did:pkh:eip155:{chain_id}:{smart_account}" if smart_account else "",
            "policyCid": policy_cid,
        },
        "protocols": [
            {
                "kind": "atproto-xrpc",
                "service": _env("AGENT_ATPROTO_SERVICE", "https://atproto.etzhayyim.com"),
                "pdsDid": _env("AGENT_PDS_DID", "did:web:atproto.etzhayyim.com"),
                "actorDid": agent_did,
                "facadeFor": root,
                "xrpc": {
                    "repoMethods": [
                        "com.atproto.repo.createRecord",
                        "com.atproto.repo.putRecord",
                        "com.atproto.repo.uploadBlob",
                    ],
                    "syncMethods": [
                        "com.atproto.sync.getLatestCommit",
                        "com.atproto.sync.subscribeRepos",
                    ],
                },
            },
            {
                "kind": "local-status",
                "endpoint": public_status_url.rstrip("/"),
                "api": public_status_url.rstrip("/") + "/api/status",
                "statusHash": status_hash,
                "organismState": status_report.get("organismState", "unknown"),
                "organismScore": status_report.get("organismScore", 0),
            },
            {
                "kind": "runtime",
                "runtimeKind": "local-llm-zeebe-active-inference",
                "processes": status_report.get("processes", {}),
                "homeostasis": status_report.get("homeostasis", {}),
                "runtimePolicyCid": runtime_policy_cid,
            },
            {
                "kind": "evm-runtime-receipt",
                "chainId": chain_id,
                "agentRegistry": agent_registry,
                "validationRegistry": _env("AGENT_ERC8004_VALIDATION_REGISTRY"),
                "reputationRegistry": _env("AGENT_ERC8004_REPUTATION_REGISTRY"),
                "latestCheckpoint": status_hash,
            },
        ],
        "registries": {
            "actorRegistryRow": f"actor_registry:{agent_did}",
            "mcpRegistryRow": f"mcp_registry:{mcp_endpoint}" if mcp_endpoint else "",
            "toolRegistryRows": [
                "tool_registry:agent.organism.status",
                "tool_registry:agent.organism.selfRepair",
                "tool_registry:agent.organism.dispatch",
            ],
        },
        "economy": {
            "mode": _env("AGENT_ECONOMY_MODE", "guarded-social"),
            "runtimeResourcePolicy": runtime_policy_cid,
            "slashPolicy": _env("AGENT_SLASH_POLICY_CID"),
        },
        "generatedAt": _now_iso(),
    }


def upsert_economy_profile_direct(
    *,
    agent_did: str,
    root_did: str,
    erc8004_agent_id: str,
    smart_account: str = "",
    policy_cid: str = "",
    runtime_policy_cid: str = "",
    slash_policy_cid: str = "",
    treasury_addr: str = "",
) -> dict[str, Any] | None:
    if not os.environ.get("RW_URL"):
        return None
    from kotodama.agent_daemon_main import insert_direct_row

    now = datetime.now(UTC).replace(tzinfo=None, microsecond=0)
    row = {
        "vertex_id": "agent-economy-profile-" + stable_hash({"agentDid": agent_did})[:24],
        "root_did": root_did,
        "agent_did": agent_did,
        "smart_account": smart_account or None,
        "erc8004_agent_id": erc8004_agent_id or None,
        "atproto_did": agent_did,
        "economy_mode": _env("AGENT_ECONOMY_MODE", "guarded-social"),
        "policy_cid": policy_cid or None,
        "runtime_policy_cid": runtime_policy_cid or None,
        "slash_policy_cid": slash_policy_cid or None,
        "treasury_addr": treasury_addr or None,
        "parent_root_did": None,
        "status": "active",
        "created_at": now,
        "updated_at": now,
        "actor_did": agent_did,
        "org_did": "anon",
        "org_id": agent_did,
        "user_id": agent_did,
        "sensitivity_ord": 1,
    }
    insert_direct_row("vertex_agent_economy_profile", row)
    return {"updated": 1, "vertexId": row["vertex_id"], "erc8004AgentId": erc8004_agent_id}


def render_registration_from_env(agent_did: str) -> dict[str, Any]:
    status_report = load_status_report(agent_did)
    chain_id = int(_env("AGENT_ERC8004_CHAIN_ID", str(DEFAULT_CHAIN_ID)))
    return build_agent_registration(
        agent_did=agent_did,
        status_report=status_report,
        chain_id=chain_id,
        agent_registry=_env("AGENT_ERC8004_AGENT_REGISTRY", DEFAULT_AGENT_REGISTRY),
        erc8004_agent_id=_env("AGENT_ERC8004_AGENT_ID", "TBD_AFTER_AGENT_REGISTRY_MINT"),
        agent_uri=_env("AGENT_ERC8004_AGENT_URI", "ipfs://TBD_AGENT_REGISTRATION_CID"),
        root_did=_env("AGENT_ERC725_ROOT_DID"),
        root_address=_env("AGENT_ERC725_ROOT_ADDRESS"),
        smart_account=_env("AGENT_SMART_ACCOUNT"),
        policy_cid=_env("AGENT_POLICY_CID"),
        runtime_policy_cid=_env("AGENT_RUNTIME_POLICY_CID"),
        public_status_url=_env("AGENT_STATUS_PUBLIC_URL", "http://127.0.0.1:8765"),
        mcp_endpoint=_env("AGENT_MCP_ENDPOINT"),
        a2a_endpoint=_env("AGENT_A2A_ENDPOINT"),
    )


def _is_placeholder(value: str) -> bool:
    upper = value.strip().upper()
    return not upper or "TBD" in upper or "PLACEHOLDER" in upper or upper == ZERO_ADDRESS.upper()


def _is_hex_address(value: str) -> bool:
    return bool(_HEX_ADDRESS_RE.match(value.strip()))


def validate_registration_for_chain(registration: dict[str, Any], agent_uri: str) -> list[str]:
    root = registration.get("rootIdentity", {})
    agent = registration.get("agent", {})
    root_did = str(root.get("rootDid", "")).strip()
    owner = str(root.get("address", "")).strip()
    registry_ref = str(agent.get("agentRegistry", "")).strip()
    registry = registry_ref.rsplit(":", 1)[-1] if registry_ref else ""
    errors: list[str] = []
    if _is_placeholder(agent_uri):
        errors.append("agent_uri is still a placeholder; publish the registration to IPFS first")
    if _is_placeholder(root_did):
        errors.append("rootIdentity.rootDid is missing or still a placeholder")
    if _is_placeholder(owner) or not _is_hex_address(owner):
        errors.append("rootIdentity.address must be a non-zero EVM owner address")
    if not _is_hex_address(registry):
        errors.append("agent.agentRegistry must end with a valid EVM registry address")
    return errors


def _multipart_form(filename: str, body: bytes) -> tuple[str, bytes]:
    boundary = "etzhayyim-agent-erc8004-" + stable_hash({"filename": filename, "body": hashlib.sha256(body).hexdigest()})[:24]
    lines = [
        f"--{boundary}\r\n".encode(),
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'.encode(),
        b"Content-Type: application/json\r\n\r\n",
        body,
        b"\r\n",
        f"--{boundary}--\r\n".encode(),
    ]
    return boundary, b"".join(lines)


def publish_registration_ipfs(
    *,
    registration: dict[str, Any],
    ipfs_base: str = DEFAULT_IPFS_BASE,
    filename: str = "agent-registration.json",
    dry_run: bool = True,
) -> dict[str, Any]:
    body = registration_bytes(registration)
    digest = hashlib.sha256(body).hexdigest()
    result: dict[str, Any] = {
        "ok": True,
        "dryRun": dry_run,
        "published": False,
        "bytes": len(body),
        "sha256": "0x" + digest,
        "ipfsBase": ipfs_base.rstrip("/"),
    }
    if dry_run:
        result["cid"] = "DRY_RUN_AGENT_REGISTRATION_CID"
        result["uri"] = "ipfs://DRY_RUN_AGENT_REGISTRATION_CID"
        return result

    hmac_key = load_keychain_secret(service="etzhayyim.cloudflare", account="IPFS_HMAC")
    if not hmac_key:
        raise RuntimeError("IPFS_HMAC missing in macOS Keychain service etzhayyim.cloudflare account IPFS_HMAC")
    boundary, form = _multipart_form(filename, body)
    signature = hmac.new(hmac_key.encode("utf-8"), form, hashlib.sha256).hexdigest()
    endpoint = ipfs_base.rstrip("/") + "/api/v0/add?pin=true&cid-version=1"
    req = request.Request(endpoint, data=form, method="POST")
    req.add_header("content-type", f"multipart/form-data; boundary={boundary}")
    req.add_header("x-etzhayyim-ipfs-auth", signature)
    req.add_header("user-agent", "etzhayyim-agent-erc8004/0.1")
    try:
        with request.urlopen(req, timeout=30) as resp:
            resp_body = resp.read(1024 * 1024)
    except error.HTTPError as exc:
        detail = exc.read(4096).decode("utf-8", errors="replace")
        raise RuntimeError(f"ipfs add HTTP {exc.code}: {detail}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"ipfs add failed: {exc}") from exc

    parsed = json.loads(resp_body.decode("utf-8"))
    cid = str(parsed.get("Hash") or parsed.get("Cid") or "").strip()
    if not cid:
        raise RuntimeError(f"ipfs add response missing CID: {parsed}")
    result.update({"published": True, "cid": cid, "uri": "ipfs://" + cid, "gatewayUrl": ipfs_base.rstrip("/") + "/ipfs/" + cid})
    return result


def run_chain_register(
    *,
    registration_path: Path,
    agent_uri: str,
    registry: str,
    rpc_url: str,
    chain_id: int,
    dry_run: bool,
) -> dict[str, Any]:
    cmd = [
        "etzhayyim",
        "agent-runtime",
        "register",
        "--registration",
        str(registration_path),
        "--agent-uri",
        agent_uri,
        "--registry",
        registry,
        "--rpc-url",
        rpc_url,
        "--chain-id",
        str(chain_id),
    ]
    if not dry_run:
        cmd.append("--dry-run=false")
    proc = subprocess.run(cmd, check=False, capture_output=True, text=True, timeout=90)
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout).strip()
        raise RuntimeError("etzhayyim agent-runtime register failed: " + detail[:1200])
    return json.loads(proc.stdout)


def execute_publish_flow(
    *,
    registration: dict[str, Any],
    registration_path: Path | None,
    publish_ipfs: bool,
    submit_chain: bool,
    dry_run: bool,
    ipfs_base: str,
    rpc_url: str,
    chain_id: int,
    registry: str,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "ok": True,
        "dryRun": dry_run,
        "publishIpfs": publish_ipfs,
        "submitChain": submit_chain,
        "generatedAt": _now_iso(),
    }
    registration_bytes_value = registration_bytes(registration)
    planned_agent_uri = "ipfs://PENDING_AGENT_REGISTRATION_CID" if publish_ipfs else str(
        registration.get("agent", {}).get("agentURI", "")
    )
    initial_chain_errors = validate_registration_for_chain(registration, planned_agent_uri)
    if submit_chain and initial_chain_errors:
        result["ok"] = False
        result["agentRegistration"] = {
            "published": False,
            "uri": planned_agent_uri,
            "bytes": len(registration_bytes_value),
            "sha256": "0x" + hashlib.sha256(registration_bytes_value).hexdigest(),
        }
        result["preflight"] = {"chainErrors": initial_chain_errors}
        result["chain"] = {"submitted": False, "blocked": True, "errors": initial_chain_errors}
        return result
    if not publish_ipfs:
        agent_uri = str(registration.get("agent", {}).get("agentURI", ""))
        result["agentRegistration"] = {
            "published": False,
            "uri": agent_uri,
            "bytes": len(registration_bytes_value),
            "sha256": "0x" + hashlib.sha256(registration_bytes_value).hexdigest(),
        }
    else:
        ipfs_result = publish_registration_ipfs(registration=registration, ipfs_base=ipfs_base, dry_run=dry_run)
        result["agentRegistration"] = ipfs_result
        agent_uri = str(ipfs_result["uri"])

    chain_errors = validate_registration_for_chain(registration, agent_uri)
    result["preflight"] = {"chainErrors": chain_errors}
    if submit_chain:
        if chain_errors:
            result["ok"] = False
            result["chain"] = {"submitted": False, "blocked": True, "errors": chain_errors}
            return result
        if registration_path is None or not registration_path.exists():
            with tempfile.NamedTemporaryFile("wb", suffix="-agent-registration.json", delete=False) as tmp:
                tmp.write(registration_bytes_value)
                registration_path = Path(tmp.name)
        else:
            registration_path.write_bytes(registration_bytes_value)
        chain_result = run_chain_register(
            registration_path=registration_path,
            agent_uri=agent_uri,
            registry=registry,
            rpc_url=rpc_url,
            chain_id=chain_id,
            dry_run=dry_run,
        )
        result["chain"] = chain_result
    return result


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render local agent ERC-8004 registration JSON")
    parser.add_argument("--agent-did", default=os.environ.get("AGENT_DID", "did:etzhayyim:agent:local"))
    parser.add_argument("--out", default="")
    parser.add_argument("--upsert-profile", action="store_true")
    parser.add_argument("--publish-ipfs", action="store_true")
    parser.add_argument("--submit-chain", action="store_true")
    parser.add_argument("--dry-run", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--ipfs", default=os.environ.get("AGENT_IPFS_BASE", DEFAULT_IPFS_BASE))
    parser.add_argument("--rpc-url", default=os.environ.get("AGENT_ERC8004_RPC_URL", DEFAULT_RPC_URL))
    parser.add_argument("--publish-proof-out", default="")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    load_env_file()
    if not os.environ.get("RW_URL"):
        rw_url = load_keychain_secret(service="etzhayyim.rw", account="ROOT_URL")
        if rw_url:
            os.environ["RW_URL"] = rw_url
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    args = parse_args(argv)
    registration = render_registration_from_env(args.agent_did)
    chain_id = int(_env("AGENT_ERC8004_CHAIN_ID", str(DEFAULT_CHAIN_ID)))
    registry = _env("AGENT_ERC8004_AGENT_REGISTRY", DEFAULT_AGENT_REGISTRY)
    if args.upsert_profile:
        profile = upsert_economy_profile_direct(
            agent_did=args.agent_did,
            root_did=str(registration["rootIdentity"]["rootDid"]),
            erc8004_agent_id=str(registration["agent"]["agentId"]),
            smart_account=_env("AGENT_SMART_ACCOUNT"),
            policy_cid=_env("AGENT_POLICY_CID"),
            runtime_policy_cid=_env("AGENT_RUNTIME_POLICY_CID"),
            slash_policy_cid=_env("AGENT_SLASH_POLICY_CID"),
            treasury_addr=_env("AGENT_TREASURY_ADDR"),
        )
        registration["localProfileUpsert"] = profile
    proof: dict[str, Any] | None = None
    registration_path = Path(args.out) if args.out else None
    if args.publish_ipfs or args.submit_chain:
        proof = execute_publish_flow(
            registration=registration,
            registration_path=registration_path,
            publish_ipfs=args.publish_ipfs,
            submit_chain=args.submit_chain,
            dry_run=args.dry_run,
            ipfs_base=args.ipfs,
            rpc_url=args.rpc_url,
            chain_id=chain_id,
            registry=registry,
        )
        registration["publish"] = proof
    text = registration_bytes(registration).decode("utf-8").rstrip("\n")
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    if args.publish_proof_out and proof is not None:
        Path(args.publish_proof_out).write_text(json.dumps(proof, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(text)
    if proof is not None and not proof.get("ok", False):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
