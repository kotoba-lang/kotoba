# Generated dapp UI: oracle run (JUN-808 / JUN-809)

Date: 2026-11-04. A one-shot local reference run, not CI, not a gate and not a build step; the CDCI rule (no
JVM/nbb in CI/CD) is unchanged. It shows what the `kotoba-lang/html` and `kotoba-lang/css` libraries emit for the
documents in `ui.cljk`. It does not show that a native build renders them (JUN-810).

Command (from `lib/kotoba.aiueos`, sibling checkouts of the libraries):

    kbb --backend sci \
      --classpath <kotoba-lang/html>/src:<kotoba-lang/css>/src:<kotoba/lib/kotoba.json>/src \
      distributions/awai/dapps/ui/ui.cljk distributions/awai/dapps/ui/generated

Inputs: kotoba-lang/html f8f2e0c, kotoba-lang/css f9d9658, kotoba.json from kotoba ffc5ebee2 (`lib/kotoba.json`),
`kbb` = `/opt/homebrew/bin/kbb` (no `--version` option). Source hash (`scripts/dapp-ui.py`):
`f2927da3271e96a6b9079f70075fd4369cd7ddafa06a1258d21b923965fc51a0`.

Outputs (sha256): dapp-ui.css `d721da53…`, dock.html `3d8d97b0…`, tiles.html `3e829908…`, windows.html `ee00bfcd…`.

Then `python3 -I scripts/dapp-ui.py splice` copies them into `resources/aiueos/session/index.html`, and
`scripts/dapp-ui.py check` refuses a page that differs from `generated/` or a `generated/` older than the sources
(both refusals exercised). Browser check on a local server: 17 launcher tiles, dock pins, Itonami Apps pin and
approval flow, Updates mode and denial, Tokei/Wi-Fi binds; no network request.

The reference run is evidence of the reference implementation's behavior, not proof that a native implementation is
correct; any difference found later is reported, not matched.
