# Updates manager: UI document, declarations and host-side policy engine (JUN-813 F, epic JUN-805), 2026-11-07

Labels: **[ran]** I ran it and the output is here or in the PR; **[read]** from code or docs only; **[not done]** nobody has done it.
The kernel image is untouched: no `os/aiueos/native` file changed, no Amu image was built, no QEMU run.

## What this change is

| Piece | File | Runs where |
| -- | -- | -- |
| Updates UI document: installed version and floor read-outs, the four policy modes, last check, the admission legend (signature m-of-n, freshness verdict, version floor), and three buttons check / download / install | `resources/aiueos/session/apps/updates.kotoba` (built from the shared `ui-components`), rendered into `index.html` | Browser (hosted session page). Static text and `data-bind` names only. |
| Dapp record: `check-updates`, `download-update` (remote) and `install-update` (a new `localOperations` list: local ESP write, no request leaves the device), each `each-operation`, with service, endpoint, data categories; `endpointState` says no origin is registered | `distributions/awai/dapps/updates.json` | Read by the host-side checks only |
| Policy engine, a pure function: `next-actions` (mode, event, stage, endpoint, admitted) gives prompts and enabled buttons, `may-run` gives yes only for a fresh approval of exactly the requested operation, `image-admission` and `check-verdict` mirror the kernel result codes and the ADR-0286 Amendment 6 table | `os/aiueos/kotoba/aiueos/update_policy.kotoba` | Nothing yet. It is a source module that no entry file requires, so it is in no image and in no browser bundle. Run by the native test below. |
| Policy tests | `test/aiueos/update_policy_test.kotoba`: all 192 states, all 12288 (state, operation, approval, freshness) combinations, and fixed cases | Native (Amu), host-side |
| Cross-checks (stdlib Python) and their negative controls | `scripts/check-update-manager.py`, `scripts/check-update-manager-negative.py`, the new `localOperations` rule in `scripts/check-dapp-records.py` and one new control in `scripts/check-dapp-documents-negative.py`; two steps added to the `aiueos-dapp-documents` job | CI (Python 3 only) |
| Mutation gate for the engine | `scripts/check-update-policy-native.py AMU_HOME` | Native, local, one-shot; **not in CI** (needs an Amu build; the native lanes fetch theirs) |

### The rules the engine encodes (from `update-policy.json` and ADR-0286)

- A schedule tick (event 1) only raises a prompt: check in notify and above, download in auto-stage and above (a found, admitted update), install only at boot (event 2) in auto-install. Manual raises no prompt.
- `may-run` takes the mode as an input and ignores it: no mode skips approval. It needs a fresh approval, for exactly the requested operation, and the operation must be offered in the current state. An approval for check does not permit download; a used approval does not permit anything.
- Freshness (AIUEFRS1) only decides what `check` may say. It never authorizes or blocks an install (Amendment 6). Image admission is the signature rule (fewer than 2 distinct valid signers: 1), the floor (version not above: 9, floor unreadable: 10, fail closed).

## What ran [ran]

All on macOS arm64, 2026-11-07, from `lib/kotoba.aiueos` unless noted.

- `python3 -I scripts/check-dapp-records.py`: `AIUEOS_DAPP_RECORDS_OK apps=18 docks=1..18 update-modes=4 documents=18`.
- `python3 -I scripts/check-dapp-documents-negative.py`: 11 controls refused (10 existing, 1 new).
- `python3 -I scripts/session-page.py check-table`: OK. `session-page.py check` (renders `index.kotoba` with Amu and compares byte for byte with `index.html`): OK after `session-page.py build`. Before my edits the same Amu reproduced the committed `index.html` byte for byte, so the rebuilt page differs only in the Updates section and the install-update approval text (`git diff` of `index.html`).
- `python3 -I scripts/check-update-manager.py` and `check-update-manager-negative.py`: OK, 18 controls refused.
- `python3 -I scripts/check-update-policy-native.py <amu>`: the test prints `0` on the real policy, and prints a nonzero check code for each of the 14 mutants (`native-gate.out`): notify prompting a download, manual prompting a check, a tick prompting an install, an install prompt in auto-stage, a download button without an endpoint, an install button for an unadmitted image, `may-run` ignoring freshness / the approved operation / the offered state, floor equal to version admitted, unreadable floor as 0, one signer admitted, an expired record reported as fresh, a refused record reported as data.
- In the Browser pane (static file snapshot, no server): the three buttons carry `data-op` check-updates / download-update / install-update, clicking one opens the approval sheet, and approving install-update says nothing was executed. No network request was made.
- One-off Node 26 probe of the shared validator (`broker-probe.mjs`, `broker-probe.out.json`): see below. A measurement, not a gate.

The Amu used (for `session-page.py` and the native gate) is an unpinned local build found in another agent's workspace (`workspaces/claude/jun-888-cli2`, `amu-cli.macho` sha256 `ee9a94e4…61ff0`, with its matching `amu-full-root.macho` `88623412…a229`). It is not the revision pinned in `scripts/native-ci-inputs.json` (ce982703). The checkout at `kotoba-lang/amu/bin/amu` cannot run `--source-lock`. Treat the native results as one local run, to be repeated with the pinned Amu.

## What is NOT verified [not done]

- Nothing here runs in an image or on a board. The engine is not called by any UI code: the hosted page does not import it, and the native update path (`native/update.kotoba`, `aiueos-provision-esp.py`) does not use it. There is no manager that applies the actions; the page shows static text and the existing approval sheet, which sends nothing.
- The page cannot show an installed version, a floor, a last check or any candidate: the browser cannot read the device's `OSMETA.BIN` journal, and no check has run. The read-outs say so ("未取得"); no value is invented. The `data-bind` names (`update-installed`, `update-last-check`, `update-admission`) are placeholders for a future host.
- The kernel result codes and the freshness table in the engine were copied by reading `native/update.kotoba` and ADR-0286; no gate compares the two.
- The CI job does not run the engine or the native mutation gate (no Amu in that job). It checks only text agreement between the record, the document, the policy file and the engine's thresholds.
- Not run: QEMU, any image build, the `session-page.py check` under the pinned Amu, the CI itself.

## Blockers

1. **No update origin.** The owner has not supplied hostnames. The record says "no update origin registered", the document says check and download are impossible until one is, and `check-update-manager.py` refuses any URL or host name in the record, document, policy file or engine. Nothing was invented, and no Cloudflare dependency was added. The endpoint paths, query names and the CSP `connect-src` that follow from them are blocked on this.
2. **Shared runtime integration is open.** The canonical module `lib/kotoba.wasmWebcomponent/src/kotoba-client-runtime.js` exists on main (966 lines). The session page does not import or copy it (its binder, `js-1` in `index.kotoba`, has its own approval template and makes no request), so the Updates app is **not** integrated with the broker and the broker's consent host is not what the user sees. No product-local consent logic was added; the existing template is unchanged except one message. Integration needs the hosts (1) and a builder that copies the exact module. Measured with the probe: the validator accepts a descriptor only with a concrete `https` origin per operation (`endpoint: 'user-selected'` is refused as `invalid-operation`, although line 429 of the module tests for it, so that branch looks dead), refuses `consent` other than `each-operation`, and accepts `operations: []`. So the manager's network operations cannot be declared validly until an origin exists; the probe's accepted descriptor uses the reserved name `update-origin.invalid` and appears only in the probe, not in any shipped file. Install is local and is not a broker operation.
3. **Signer set is verification-only.** Production mode pins the three-slot set kept on one Mac (ADR-0286 Amendment 7): no custody separation, not for deployment. The document says so ("検証専用の署名者集合").
4. **Consumers of the catalog and the freshness record, the signed device-key floor, the monotonic freshness rule** are still not implemented (ADR-0286 status). The floor is hash-checked, not signed (Amendment 4).
5. **Approval sheet wording.** The shared sheet in `index.kotoba` still says "送るデータ: 操作名のみ" for every operation. The true data categories are listed in the document's operations block; changing the sheet means changing the page binder and is left to the shared-runtime integration.

## Document versus code

`apps/updates.kotoba` before this change said "ポスト量子 ML-DSA-65 は未対応". `native/update.kotoba` verifies AIUEIMG2 with Ed25519 and ML-DSA-65 (2 of 3 pinned signers), so the statement was out of date; the document now follows the code. (ADR-0283's text still describes the update manager as proposed; not edited.)
