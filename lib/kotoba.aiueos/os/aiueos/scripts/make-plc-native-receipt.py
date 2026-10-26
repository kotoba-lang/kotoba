#!/usr/bin/env python3
"""Create an honest build or deployment receipt for an AIUEOS PLC program."""

import argparse
import hashlib
import importlib.util
import json
import pathlib
import re
import struct
import sys


SHA256 = re.compile(r"^[0-9a-f]{64}$")
GIT_SHA1 = re.compile(r"^[0-9a-f]{40}$")
P256_P = 0xFFFFFFFF00000001000000000000000000000000FFFFFFFFFFFFFFFFFFFFFFFF
P256_A = P256_P - 3
P256_B = 0x5AC635D8AA3A93E7B3EBBD55769886BC651D06B0CC53B0F63BCE3C3E27D2604B
P256_N = 0xFFFFFFFF00000000FFFFFFFFFFFFFFFFBCE6FAADA7179E84F3B9CAC2FC632551
P256_G = (
    0x6B17D1F2E12C4247F8BCE6E563A440F277037D812DEB33A0F4A13945D898C296,
    0x4FE342E2FE1A7F9B8EE7EB4A7C0F9E162BCE33576B315ECECBB6406837BF51F5,
)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def p256_add(left, right):
    if left is None:
        return right
    if right is None:
        return left
    x1, y1 = left
    x2, y2 = right
    if x1 == x2 and (y1 + y2) % P256_P == 0:
        return None
    if left == right:
        slope = ((3 * x1 * x1 + P256_A) * pow(2 * y1, -1, P256_P)) % P256_P
    else:
        slope = ((y2 - y1) * pow(x2 - x1, -1, P256_P)) % P256_P
    x3 = (slope * slope - x1 - x2) % P256_P
    return x3, (slope * (x1 - x3) - y1) % P256_P


def p256_multiply(scalar, point):
    result = None
    while scalar:
        if scalar & 1:
            result = p256_add(result, point)
        point = p256_add(point, point)
        scalar >>= 1
    return result


def ecdsa_p256_sha256_valid(signature, public_key, digest_bytes):
    if len(signature) != 64 or len(public_key) != 64 or len(digest_bytes) != 32:
        return False
    r = int.from_bytes(signature[:32], "big")
    s = int.from_bytes(signature[32:], "big")
    x = int.from_bytes(public_key[:32], "big")
    y = int.from_bytes(public_key[32:], "big")
    if not (0 < r < P256_N and 0 < s < P256_N and 0 <= x < P256_P and 0 <= y < P256_P):
        return False
    public = (x, y)
    if (y * y - (x * x * x + P256_A * x + P256_B)) % P256_P:
        return False
    inverse = pow(s, -1, P256_N)
    z = int.from_bytes(digest_bytes, "big")
    candidate = p256_add(p256_multiply((z * inverse) % P256_N, P256_G),
                         p256_multiply((r * inverse) % P256_N, public))
    return candidate is not None and candidate[0] % P256_N == r


def validate_elf(path):
    blob = path.read_bytes()
    if len(blob) < 64 or blob[:6] != b"\x7fELF\x02\x01":
        raise ValueError("invalid ELF identity")
    etype, machine, version = struct.unpack_from("<HHI", blob, 16)
    entry, phoff = struct.unpack_from("<QQ", blob, 24)
    ehsize, phentsize, phnum = struct.unpack_from("<HHH", blob, 52)
    if (etype, machine, version, entry, ehsize, phentsize, phnum) != (
            2, 0x3E, 1, 0x1E1000, 64, 56, 2):
        raise ValueError("unsupported AIUEOS user ELF contract")
    segments = []
    data_segment = None
    for index in range(phnum):
        offset = phoff + index * phentsize
        if offset + phentsize > len(blob):
            raise ValueError("truncated program headers")
        ptype, flags, file_offset, va, _, filesz, memsz, align = struct.unpack_from(
            "<IIQQQQQQ", blob, offset)
        if (ptype != 1 or filesz > memsz or memsz > 4096 or
                file_offset + filesz > len(blob)):
            raise ValueError("invalid static segment")
        segments.append((flags, va, align))
        if va == 0x1E2000:
            data_segment = (file_offset, filesz)
    if segments != [(5, 0x1E1000, 4096), (6, 0x1E2000, 4096)]:
        raise ValueError("ELF is not canonical RX/RW-NX")
    if data_segment is None or data_segment[1] != 88:
        raise ValueError("unsupported PLC runtime context")
    context = blob[data_segment[0]:data_segment[0] + 88]
    words = struct.unpack_from("<11Q", context)
    if (words[0] != 0 or words[1] != 512 or words[2] != 0xF0000 or
            any(words[3:6]) or words[6] != 0x1E1020 or any(words[7:])):
        raise ValueError("PLC capability/runtime context changed")
    trampoline = bytes([0xB8, 5, 0, 0, 0, 0x48, 0x8B, 0x7F, 0x50, 0x0F, 5, 0xC3])
    if blob[0x1020:0x102c] != trampoline:
        raise ValueError("invalid AIUEOS syscall trampoline")


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_frontend(path):
    return load_module("compile_plc_st", path)


def validate_io_map(document, declared_inputs, declared_outputs, qualified=False):
    if document.get("format") != "aiueos-plc-io-map/v1":
        raise ValueError("invalid PLC I/O map format")
    inputs = document.get("inputs")
    outputs = document.get("outputs")
    if not isinstance(inputs, list) or not isinstance(outputs, list):
        raise ValueError("PLC I/O map arrays are required")
    input_count = declared_inputs if isinstance(declared_inputs, int) else len(declared_inputs)
    output_count = declared_outputs if isinstance(declared_outputs, int) else len(declared_outputs)
    if [item.get("index") for item in inputs if isinstance(item, dict)] != list(range(input_count)):
        raise ValueError("PLC input map does not match ST declarations")
    if [item.get("index") for item in outputs if isinstance(item, dict)] != list(range(output_count)):
        raise ValueError("PLC output map does not match ST declarations")
    if not isinstance(declared_inputs, int):
        for item, variable in zip(inputs, declared_inputs):
            if ("plc-v-" + str(item.get("name", "")).lower() != variable.name or
                    item.get("type") != variable.type):
                raise ValueError("PLC input name/type does not match ST declaration")
        sources = [item.get("source") for item in inputs]
        if (not all(isinstance(source, str) and source for source in sources) or
                len(set(sources)) != len(sources)):
            raise ValueError("PLC input sources must be nonempty and unique")
    if not isinstance(declared_outputs, int):
        for item, variable in zip(outputs, declared_outputs):
            if ("plc-v-" + str(item.get("name", "")).lower() != variable.name or
                    item.get("type") != variable.type):
                raise ValueError("PLC output name/type does not match ST declaration")
        sinks = [item.get("sink") for item in outputs]
        if (not all(isinstance(sink, str) and sink for sink in sinks) or
                len(set(sinks)) != len(sinks)):
            raise ValueError("PLC output sinks must be nonempty and unique")
    for index, item in enumerate(outputs):
        safe = item.get("safe_value")
        if not isinstance(safe, int) or not -2147483648 <= safe <= 2147483647:
            raise ValueError("every PLC output requires a 32-bit safe value")
        if (not isinstance(declared_outputs, int) and
                declared_outputs[index].type == "BOOL" and safe not in (0, 1)):
            raise ValueError("BOOL safe value must be zero or one")
    if qualified:
        driver = document.get("qualified_driver", {})
        for key in ("artifact_sha256", "qualification_receipt_sha256"):
            if not SHA256.fullmatch(str(driver.get(key, ""))):
                raise ValueError("qualified physical I/O driver digest is required")
        if driver.get("physical_hardware") is not True or \
                driver.get("safe_state_write_verified") is not True:
            raise ValueError("physical I/O safe-state qualification is required")
        for key in ("max_input_latch_us", "max_output_commit_us"):
            if not isinstance(driver.get(key), (int, float)) or driver[key] <= 0:
                raise ValueError("bounded physical I/O latency is required")


def validate_admission(document, qualified=False):
    if document.get("format") != "aiueos-plc-admission/v1":
        raise ValueError("invalid PLC admission format")
    priority = document.get("priority")
    cycle = document.get("cycle_us")
    deadline = document.get("deadline_us")
    budget = document.get("budget_us")
    wcet = document.get("wcet_us")
    if not isinstance(priority, int) or not 1 <= priority <= 255:
        raise ValueError("PLC priority must be in 1..255")
    if not all(isinstance(value, int) for value in (cycle, deadline, budget, wcet)):
        raise ValueError("PLC timing values must be integer microseconds")
    if not 0 < wcet <= budget <= deadline <= cycle:
        raise ValueError("PLC timing must satisfy WCET <= budget <= deadline <= cycle")
    result = {"priority": priority, "cycle_us": cycle, "deadline_us": deadline,
              "budget_us": budget, "wcet_us": wcet}
    if qualified:
        response = document.get("response_time_us")
        blocking = document.get("blocking_us")
        interference = document.get("interference_us")
        if not all(isinstance(value, (int, float)) and value >= 0
                   for value in (response, blocking, interference)) or \
                response <= 0 or wcet + blocking + interference > response or \
                response > deadline:
            raise ValueError("qualified response-time analysis is required")
        for key in ("task_set_sha256", "analysis_tool_sha256", "measurement_run_sha256"):
            if not SHA256.fullmatch(str(document.get(key, ""))):
                raise ValueError("response-time analysis evidence digest is required")
        if document.get("physical_hardware") is not True or \
                not isinstance(document.get("sample_count"), int) or \
                document["sample_count"] < 10000:
            raise ValueError("physical WCET measurement evidence is required")
        result.update({"response_time_us": response, "blocking_us": blocking,
                       "interference_us": interference,
                       "sample_count": document["sample_count"]})
    return result


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=pathlib.Path)
    parser.add_argument("generated", type=pathlib.Path)
    parser.add_argument("elf", type=pathlib.Path)
    parser.add_argument("compiler_commit")
    parser.add_argument("output", type=pathlib.Path)
    parser.add_argument("--rt-kernel-receipt", type=pathlib.Path)
    parser.add_argument("--io-map", type=pathlib.Path)
    parser.add_argument("--admission", type=pathlib.Path)
    parser.add_argument("--signature", type=pathlib.Path)
    parser.add_argument("--public-key", type=pathlib.Path)
    args = parser.parse_args(argv)

    if not GIT_SHA1.fullmatch(args.compiler_commit):
        raise SystemExit("error: compiler commit must be a complete Git SHA-1")
    frontend = load_frontend(pathlib.Path(__file__).with_name("compile-plc-st.py"))
    source_text = args.source.read_text(encoding="utf-8")
    generated_text = args.generated.read_text(encoding="utf-8")
    _, inputs, outputs, _ = frontend.Parser(source_text).parse()
    if frontend.compile_source(source_text) != generated_text:
        raise SystemExit("error: generated Kotoba does not match ST source")
    expected_calls = {16, 17, 18, 19}
    actual_calls = {int(value) for value in re.findall(r"\(cap-call ([0-9]+) ", generated_text)}
    if actual_calls != expected_calls:
        raise SystemExit("error: PLC program capability surface changed")
    validate_elf(args.elf)

    binding_paths = (args.rt_kernel_receipt, args.io_map, args.admission,
                     args.signature, args.public_key)
    if any(binding_paths) and not all(binding_paths):
        raise SystemExit("error: deployment binding requires RT receipt, I/O map, "
                         "admission, signature and public key")
    deployment_ready = bool(all(binding_paths))
    rt_receipt_sha = rt_kernel_sha = io_map_sha = admission_sha = None
    timing = None
    if deployment_ready:
        rt_receipt = json.loads(args.rt_kernel_receipt.read_text(encoding="ascii"))
        rt_verifier = load_module(
            "verify_rt_kernel_receipt",
            pathlib.Path(__file__).with_name("verify-rt-kernel-receipt.py"))
        rt_failures = rt_verifier.violations(rt_receipt)
        if rt_failures:
            raise SystemExit("error: PLC deployment requires a qualified RT kernel receipt: " +
                             ", ".join(rt_failures))
        rt_receipt_sha = digest(args.rt_kernel_receipt)
        rt_kernel_sha = rt_receipt.get("artifact_sha256")
        if not SHA256.fullmatch(str(rt_kernel_sha or "")):
            raise SystemExit("error: RT kernel receipt has no artifact digest")
        io_map = json.loads(args.io_map.read_text(encoding="utf-8"))
        admission = json.loads(args.admission.read_text(encoding="utf-8"))
        try:
            validate_io_map(io_map, inputs, outputs, qualified=True)
            timing = validate_admission(admission, qualified=True)
        except ValueError as error:
            raise SystemExit("error: " + str(error)) from error
        signature = args.signature.read_bytes()
        public_key = args.public_key.read_bytes()
        elf_digest = bytes.fromhex(digest(args.elf))
        if not ecdsa_p256_sha256_valid(signature, public_key, elf_digest):
            raise SystemExit("error: PLC ELF signature is invalid")
        io_map_sha = digest(args.io_map)
        admission_sha = digest(args.admission)

    receipt = {
        "format": "aiueos-plc-native-receipt/v1",
        "profile": "aiueos-plc-v1",
        "target": "x86_64-aiueos-user-v1",
        "source_language": "iec-61131-3-structured-text-subset-v1",
        "runtime_linux": False,
        "runtime_jvm": False,
        "runtime_gc": False,
        "dynamic_allocation": False,
        "capabilities": [16, 17, 18, 19],
        "scan": {
            "input_snapshot": True,
            "shadow_outputs": True,
            "atomic_commit": True,
            "safe_state_on_failure": True,
        },
        "st_source_sha256": digest(args.source),
        "generated_kotoba_sha256": digest(args.generated),
        "native_elf_sha256": digest(args.elf),
        "signature_scheme": "ecdsa-p256-sha256" if deployment_ready else None,
        "signature_sha256": digest(args.signature) if deployment_ready else None,
        "signer_public_key_sha256": digest(args.public_key) if deployment_ready else None,
        "compiler_commit": args.compiler_commit,
        "rt_kernel_receipt_sha256": rt_receipt_sha,
        "rt_kernel_artifact_sha256": rt_kernel_sha,
        "io_map_sha256": io_map_sha,
        "admission_analysis_sha256": admission_sha,
        "timing": timing,
        "deployment_ready": deployment_ready,
    }
    args.output.write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n",
                           encoding="ascii")
    print("AIUEOS_PLC_NATIVE_RECEIPT_OK deployment_ready=" +
          ("1" if deployment_ready else "0"))


if __name__ == "__main__":
    main()
