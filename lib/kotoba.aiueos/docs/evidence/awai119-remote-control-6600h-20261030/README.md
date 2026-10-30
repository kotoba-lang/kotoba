# AWAI-119 remote control over the RTL8168 debug link (6600H, 2026-10-30)

The opt-in desktop debug entry now receives signed commands from the operator's Mac over the board's RTL8168.
Observed on the real 6600H board (`receipt.json`). The image was PXE-booted with `--netlog v1 --watchdog v1`.

- Boot nonce: KDBG `0xc000`. Commands go to UDP 7798; replies are KDBG `0xc001..0xc004` / refusals `0xc0ff`.
- Mac tool: `os/aiueos/scripts/aiueos-remote.py --key SEED ping|key N|type TEXT|shot OUT.png|reboot`.
- `itonami-aba-remote.png`: the screen sent back after the Mac pressed `2` and typed `aba` remotely.

Refusals were checked on the board: wrong key, repeated counter, previous boot's nonce, unknown command.
Ed25519 only (below the repository's post-quantum floor); debug entry only; not a product service.
