(ns kotoba.device
  "Assembled from one repo per definition.

  This namespace holds no implementation. It re-exports the definitions
  that each live in their own repo, so a call site can require one name
  and a library can require only the definitions it actually uses.

  AN IMPLEMENTATION BUILT AGAINST kotoba.lang.device IS NOT ACCEPTED HERE.
  kotoba.lang.device still declares IDevice, and a protocol split into its own
  repo is a DIFFERENT protocol from the one the source namespace declares
  (ADR-2609091900). Measured 2026-09-09 on kotoba.lang.fs: a filesystem
  reified against the source protocol answers through the source namespace
  and fails through this one -- No implementation of method: :exists?.
  Build the implementation against the repo that declares the protocol here,
  or call through kotoba.lang.device.

  NOT re-exported here, on purpose: IDevice. A protocol's identity is what extend-type and reify dispatch on,
  and a copy would make an implementation silently extend nothing, so the
  protocol name stays in the one repo that declares it. Requiring that repo
  is a compile error away; a copy would not be.

  Value vars are not re-exported either: denied, sensing-host-driver-refs, surface-effects. `(def x other/x)` copies, which is harmless for a function and makes
  with-redefs through this namespace a SILENT no-op for a value -- measured
  on kotoba.lang.edn, where three assertions passed against nothing at all.
  Require the repo that defines the value.
"
  (:require [kotoba.device.device :as idevice-ns]
            [kotoba.device.call :as call-ns]
            [kotoba.device.describe :as describe-ns]
            [kotoba.device.discover :as discover-ns]
            [kotoba.device.make-device-manager :as make-device-manager-ns]
            [kotoba.device.mock-device :as mock-device-ns]
            [kotoba.device.sensing-host-driver-ref :as sensing-host-driver-ref-ns]
            [kotoba.device.surface-cap :as surface-cap-ns]
            [kotoba.device.surfaces :as surfaces-ns]))

(def call "See kotoba.device.call/call." call-ns/call)
(def describe "See kotoba.device.describe/describe." describe-ns/describe)
(def discover "See kotoba.device.discover/discover." discover-ns/discover)
(def make-device-manager "See kotoba.device.make-device-manager/make-device-manager." make-device-manager-ns/make-device-manager)
(def mock-device "See kotoba.device.mock-device/mock-device." mock-device-ns/mock-device)
(def read-dev "See kotoba.device.device/read-dev." idevice-ns/read-dev)
(def scan "See kotoba.device.device/scan." idevice-ns/scan)
(def sensing-host-driver-ref "See kotoba.device.sensing-host-driver-ref/sensing-host-driver-ref." sensing-host-driver-ref-ns/sensing-host-driver-ref)
(def subscribe "See kotoba.device.device/subscribe." idevice-ns/subscribe)
(def surface-cap "See kotoba.device.surface-cap/surface-cap." surface-cap-ns/surface-cap)
(def surfaces "See kotoba.device.surfaces/surfaces." surfaces-ns/surfaces)
(def write-dev "See kotoba.device.device/write-dev." idevice-ns/write-dev)
