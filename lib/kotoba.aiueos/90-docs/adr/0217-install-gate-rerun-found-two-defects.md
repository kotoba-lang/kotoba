# ADR-0217 — the install gate re-run found two defects the build green had hidden

- Status: accepted
- Date: 2026-09-15
- Owner direction for this tranche: the live installer keeps Node as its
  install-time mechanism (ADR-0099 decision 3) — the Node-free and
  JVM-free runtime premise is unchanged and untouched by this ADR.
  What this tranche measured was gate I3, which had been green about a
  tree that no longer exists.

## What was measured

`smoke-qemu-install.cljk` (gate I3+I5) had not been re-run since
2026-08-25. The contract itself said so — `:i3-qemu-install` carried a
STALE note naming aiueos ADR-0209. This session re-ran it on the
post-kbb-cutover tree (the checkout at 68408bc, release image rebuilt
2026-09-15, live UKI rebuilt the same day) with the result:

    AIUEOS_INSTALL_SMOKE_OK usb-live-install nvme-boot-twice
                            repeat-refused disk-untouched
                            sha256=862d1ca19343d30558e643e2dca468e71acf1c366224717b6f105560ea0bbc72

Four boots: install, boot from NVMe twice with the USB detached (58
aiueos markers each), re-insert and require the erase to be refused.

## The two defects — both red in boots that failed before a green boot succeeded

The first complete run died in boot1, not in a gate assert. That is the
gate doing its job: `install-bundle-test` was 34/34 and
`install-chain-test` 22/22 at the same moment, because both run scripts
from the repository where every dependency resolves. Only the boot runs
the medium.

1. **The pinned node needs libatomic.** The node binary moved to the
   v26.7.0 pin (installer README, 2026-09-10) and nothing re-measured
   its shared-library closure. Boot1 died rc=127:

       ./node-linux-x64: error while loading shared libraries:
       libatomic.so.1: cannot open shared object file

   Measured with `ldd` in the same linux/amd64 container the build uses:
   `libatomic.so.1 => not found`. Fix: `make-live-installer.py` ships
   `libatomic.so.1` in the initramfs lib list (installs `libatomic1`,
   copies from `/usr/lib/x86_64-linux-gnu`), with the measured failure
   named in the comment beside the list.

2. **The bundled nbb must be the org-babashka-nbb fork, not stock nbb.**
   The prerequisite was written as `npm install nbb --prefix
   build/aiueos/nbb-bundle`, which installs stock nbb 1.5.212. Stock nbb
   resolves `.cljs` / `.cljc` / `.clj` — no `.cljk`. After the 2026-09-11
   rename every bundled script is `.cljk`, so boot1 died with

       Could not find namespace: kotoba.lang.text

   — the ADR-0209 shape again, from a different cause. The fork
   (`orgs/kotoba-lang/org-babashka-nbb`, version `1.5.212-cljk.1`) carries
   the `.cljk` resolution (`.cljk`, `.cljs.cljk`, `.cljc.cljk`,
   `.clj.cljk`) and its `lib/` is committed prebuilt. `make-install-usb-image.py`
   already documented that the bundle's nbb "must be the org-babashka-nbb
   fork"; nothing checked it. Fix: the install-smoke prerequisite hint
   names the fork, and the bundle build now refuses an nbb tree whose
   `package.json` version does not carry the `-cljk` suffix — the same
   refuse-at-build-time shape as the missing-classpath-root refusal of
   ADR-0209.

The second fix landed as a refusal in `make_install_usb_bundle_guard`:
a bundle built against an nbb tree without the fork's version marker is
refused at build time. A USB that extracts and then cannot load a
namespace is the failure ADR-0209 exists over; the guard closes that
class at the point the mistake is made instead of on the machine.

## What was green for the right reason afterward

With both fixes in:

    install-bundle-test   34/34   (bundle entry points executed from the stick)
    installer-test        18/18
    install-chain-test    22/22   (fake devices)
    install-smoke         AIUEOS_INSTALL_SMOKE_OK  (four boots, I3+I5)

The contract `:i3-qemu-install` STALE note is replaced by this re-run's
receipt. I4 (headless sshd) and I7 (physical machine) stay red; nothing
here claims them.

## What this does not do

- No hardware: I6/I7 unchanged. QEMU evidence only.
- No step toward a Node-free installer decision layer: that is a
  separate tranche. The runtime premise (what boots as aiueos is
  JVM-free and C-free on the bare-metal profile) is untouched — Node
  rides the install USB as install-time mechanism, exactly as
  ADR-0099 decision 3 already decided.
- The `:node-installer-test` / node-USB path was not re-run here; its
  bundle already carried the fork's shape (it passes `--classpath
  /run/aiueos-node/cp` from its own `/init` branch), and no defect was
  reported against it in this session's measurements.
