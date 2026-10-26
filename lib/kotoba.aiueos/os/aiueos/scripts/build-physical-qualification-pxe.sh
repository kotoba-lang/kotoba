#!/bin/sh
set -eu

repo=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
aiueos="$repo/os/aiueos"
out=${AIUEOS_OUT:-"$repo/build/aiueos-physical-qualification-pxe"}
core_out="$out/core"
efi="$out/aiueos-k16-native-pxe.efi"
receipt="$out/aiueos-k16-native-pxe-receipt.json"

source_commit=$(git -C "$repo" rev-parse HEAD)
source_version=$(tr -d '\r\n' < "$aiueos/VERSION")
source_dirty=false
if [ -n "$(git -C "$repo" status --porcelain --untracked-files=no)" ]; then
  source_dirty=true
fi
if [ "$source_dirty" = true ] &&
   [ "${AIUEOS_ALLOW_DIRTY_QUALIFICATION_BUILD:-0}" != 1 ]; then
  echo "error: qualification release must be built from a clean tracked tree" >&2
  exit 1
fi

mkdir -p "$out"
AIUEOS_OUT="$core_out" \
AIUEOS_PHYSICAL_QUALIFICATION=1 \
AIUEOS_PHYSICAL_NETWORK_QUALIFICATION=${AIUEOS_PHYSICAL_NETWORK_QUALIFICATION:-0} \
AIUEOS_PHYSICAL_DIRECT_HTTPS_QUALIFICATION=${AIUEOS_PHYSICAL_DIRECT_HTTPS_QUALIFICATION:-0} \
AIUEOS_MURAKUMO_DEVICE_RESULT=${AIUEOS_MURAKUMO_DEVICE_RESULT:-0} \
AIUEOS_QWEN38_MODEL_HANDOFF=${AIUEOS_QWEN38_MODEL_HANDOFF:-0} \
AIUEOS_QWEN35_SMP=${AIUEOS_QWEN35_SMP:-1} \
AIUEOS_QWEN35_AVX2=${AIUEOS_QWEN35_AVX2:-1} \
AIUEOS_PERSISTENT_BOOT=${AIUEOS_PERSISTENT_BOOT:-0} \
AIUEOS_SSH_LISTEN=${AIUEOS_SSH_LISTEN:-0} \
AIUEOS_SSH_AUTHORIZED_KEY_HEX=${AIUEOS_SSH_AUTHORIZED_KEY_HEX:-} \
AIUEOS_QUALIFICATION_LOADER_WATCHDOG_SECONDS=${AIUEOS_QUALIFICATION_LOADER_WATCHDOG_SECONDS:-} \
AIUEOS_EMBEDDED_RELEASE=1 \
AIUEOS_NETBOOT_QUALIFICATION=1 \
SOURCE_DATE_EPOCH=${SOURCE_DATE_EPOCH:-0} \
  "$aiueos/scripts/build-uefi.sh" >/dev/null
cp "$core_out/esp/EFI/BOOT/BOOTX64.EFI" "$efi"

AIUEOS_SOURCE_COMMIT="$source_commit" AIUEOS_SOURCE_VERSION="$source_version" \
AIUEOS_SOURCE_DIRTY="$source_dirty" \
AIUEOS_PERSISTENT_BOOT=${AIUEOS_PERSISTENT_BOOT:-0} \
AIUEOS_QUALIFICATION_LOADER_WATCHDOG_SECONDS=${AIUEOS_QUALIFICATION_LOADER_WATCHDOG_SECONDS:-90} \
AIUEOS_PHYSICAL_DIRECT_HTTPS_QUALIFICATION=${AIUEOS_PHYSICAL_DIRECT_HTTPS_QUALIFICATION:-0} \
AIUEOS_MURAKUMO_DEVICE_RESULT=${AIUEOS_MURAKUMO_DEVICE_RESULT:-0} \
AIUEOS_QWEN38_MODEL_HANDOFF=${AIUEOS_QWEN38_MODEL_HANDOFF:-0} \
AIUEOS_MODEL_NVME_SLOTS=${AIUEOS_MODEL_NVME_SLOTS:-0} \
AIUEOS_SSH_LISTEN=${AIUEOS_SSH_LISTEN:-0} \
AIUEOS_SSH_AUTHORIZED_KEY_FINGERPRINT=${AIUEOS_SSH_AUTHORIZED_KEY_FINGERPRINT:-} \
python3 - \
  "$efi" "$core_out/esp/EFI/AIUEOS/KERNEL.ELF" \
  "$core_out/esp/EFI/AIUEOS/INITRD.IMG" "$receipt" <<'PY'
import hashlib
import json
import os
from pathlib import Path
import sys

efi, kernel, initramfs, receipt = map(Path, sys.argv[1:])

def artifact(path):
    payload = path.read_bytes()
    return {"bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}

document = {
    "schema": "aiueos.physical-qualification-pxe-receipt.v1",
    "source": {
        "version": os.environ["AIUEOS_SOURCE_VERSION"],
        "commit": os.environ["AIUEOS_SOURCE_COMMIT"],
        "dirty": os.environ["AIUEOS_SOURCE_DIRTY"] == "true",
    },
    "artifact": artifact(efi),
    "embedded": {
        "kernel": artifact(kernel),
        "initramfs": artifact(initramfs),
    },
    "return": {
        "bootnext": ("current-pxe-persistent" if
                     os.environ["AIUEOS_PERSISTENT_BOOT"] == "1" else
                     "current-pxe-one-shot"),
        "result": "uefi-nvram-16-bytes",
        "watchdog": ("disabled" if
                     os.environ["AIUEOS_PERSISTENT_BOOT"] == "1" else
                     (os.environ["AIUEOS_QUALIFICATION_LOADER_WATCHDOG_SECONDS"] +
                      "-second-recovery")),
    },
    "qualification": ({
        "profile": ("qwen38-murakumo-persistent-worker" if
                    os.environ["AIUEOS_PERSISTENT_BOOT"] == "1" else
                    "qwen38-murakumo-device-result"),
        "authority": "https://api.murakumo.cloud",
        "path": (["/infer/nodes/device-p256-result",
                  "/infer/nodes/device-p256-worker"] if
                 os.environ["AIUEOS_PERSISTENT_BOOT"] == "1" else
                 "/infer/nodes/device-p256-result"),
        "auth": "device-p256",
        "device_result_protocol": "aiueos-k16-result-v2",
        "worker_protocol": ("aiueos-k16-worker-v2" if
                            os.environ["AIUEOS_PERSISTENT_BOOT"] == "1" else
                            None),
        "device_key": "uefi-nvram-p256",
        "model": "Qwen3.8-27B-UD-IQ3_XXS.gguf",
        "model_sha256": "c0b7c3038681ed2e3040456c1dd45f9858b6c2290bed172c70388a94874f3eee",
        "admission": "community-pending",
        "ready": ("server-observed-device-heartbeat" if
                  os.environ["AIUEOS_PERSISTENT_BOOT"] == "1" else False),
        "worker": ({
            "heartbeat": "signed-poll",
            "poll": "bounded-qwen38-greedy-8",
            "claim": "server-atomic-target-did",
            "result": "signed-device-p256-v2-decode-metrics",
            "measurement": {
                "generated_tokens": 8,
                "decode_tokens": 7,
                "first_token_excluded_from_decode_rate": True,
            },
            "retry": "persistent-with-bounded-backoff",
            "control": {
                "actions": ["restart-runtime", "reboot-pxe"],
                "delivery": "signed-poll",
                "ack": "signed-device-p256-before-action",
                "runtime_restart": "kototama-only-kernel-network-preserved",
                "pxe_reset": "uefi-runtime-cold",
            },
        } if os.environ["AIUEOS_PERSISTENT_BOOT"] == "1" else None),
        "cacao": False,
        "passkey_bound": False,
        "post_quantum": False,
        "biscuit": False,
        "physical_k16": "unverified",
        "mac_application_termination": False,
        "mac_opaque_l4_forwarder": True,
        "device_dns_port": 1053,
        "device_tls_port": 8443,
        "upstream_tls_port": 443,
    } if os.environ["AIUEOS_MURAKUMO_DEVICE_RESULT"] == "1" else {
        "profile": "rtl8125-direct-https",
        "authority": "https://api.murakumo.cloud",
        "path": "/infer/queue",
        "trust": "transport-only",
        "physical_k16": "unverified",
        "secrets": "none",
        "mac_application_termination": False,
        "mac_opaque_l4_forwarder": True,
        "device_dns_port": 1053,
        "device_tls_port": 8443,
        "upstream_tls_port": 443,
    } if os.environ["AIUEOS_PHYSICAL_DIRECT_HTTPS_QUALIFICATION"] == "1" else {
        "profile": "native-core",
    }),
    "safety": {
        "internal-disk-writes": ("dedicated-anchored-model-partition-only" if
                                 os.environ["AIUEOS_MODEL_NVME_SLOTS"] == "1" else
                                 False),
        "boot-order-writes": False,
        "ssd-install": False,
    },
    "management": ({
        "transport": "ssh-2.0-over-rtl8125",
        "listen": "10.77.0.10:22",
        "host_key": "per-device-uefi-nvram-p256",
        "authorized_key": "build-pinned-public-p256",
        "authorized_key_fingerprint":
            (os.environ["AIUEOS_SSH_AUTHORIZED_KEY_FINGERPRINT"] or None),
        "principal": "runtime",
        "commands": ["runtime status", "runtime restart", "system reboot-pxe"],
        "shell": False,
        "kernel_reboot": "uefi-runtime-reset-after-authenticated-ack",
        "physical_k16": "unverified",
    } if os.environ["AIUEOS_SSH_LISTEN"] == "1" else None),
}
receipt.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n",
                   encoding="ascii")
PY

printf '%s\n' "$efi"
