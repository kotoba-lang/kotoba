# Standing update approval for host-managed apps: a design proposal

Status: **proposal**, 2026-11-21. It amends the shared architecture contract
([app-environment-contract.md](app-environment-contract.md)), so merging it is an **owner
decision**. Nothing in `src/kotoba-client-runtime.js` or in any Store changes with this document;
the implementation follows only after the owner approves the amendment.

Tracking: [AWAI-3652](https://linear.app/kotobalabs/issue/AWAI-3652). The request came from the
owner on 2026-11-21: "自動更新に対応させて" for apps in the Itonami Store, with Torihiki
(`network.itonami.torihiki`, `network.itonami.torihiki.bot`) as the example.

Written against kotoba `main` `5b9d7802` and network-awai/awai-os `main` (the Store at
`android/shared/src/network/awai/platform/HostActivity.java`, which today sets
`USER_ACTION_REQUIRED` on every install session).

## Problem

An update is two external operations: read the signed catalog, then download the new artifact.
Under the current contract each needs a fresh, operation-specific approval, and no code may persist
an approval. So an installed app is only updated when the person opens the Store, approves the
catalog read, approves the download and confirms Android's installer. In practice apps stay on old
versions, including versions with fixed bugs.

[Bounded batch consent](client-runtime-batch-consent-proposal.md) does not solve this. A batch is
held for at most 10 minutes inside one page; an update has to happen while nobody is looking.

## Proposal in one paragraph

The person may turn on **automatic updates** in the trusted host's own settings (the Store's
native layer, outside app control). That one choice is a **standing update approval** for exactly
one declared update service: read the signed catalog from one fixed origin and download, from the
same origin, the artifacts that catalog lists for apps **this host installed**. The host alone holds
it, shows it, logs every use, and drops it when the person turns it off or when it expires. An
update that would change anything beyond "the same app, from the same signer, with a higher
version and nothing new" is not covered and waits for an ordinary per-operation approval.

## Decision 1: what the standing approval covers

| Covered | Not covered (needs an ordinary fresh approval) |
| -- | -- |
| `GET` of the catalog pointer and envelope at the declared update origin and fixed paths | Any other origin, path, method or query |
| `GET` of an artifact listed in a verified catalog, at the declared origin, for an app this host installed | Installing an app the person has not installed |
| Installing that artifact as an update of the same package | Anything the updated app itself does after launch |

Data categories, all shown when the person turns it on: `request-ip`, `request-timing`, and
`installed-app-ids` (the artifact paths reveal which apps are installed). Nothing else is sent: no
account, no device identifier, no cookies.

## Decision 2: when an update is eligible

The host applies an update without asking only if **all** of these hold. If any fails, it shows
"update available, needs your approval" and does nothing else.

1. The catalog envelope verifies against a **pinned publisher key**, its revision is above the
   highest revision this host has admitted, and it has not expired.
2. The package id is unchanged, the APK's signing certificate equals the installed app's, and the
   version code is strictly higher. A downgrade or signer change is refused outright, as today.
3. The artifact's byte count and SHA-256 equal the catalog entry, checked before install.
4. The new APK requests **no Android permission** the installed version does not hold.
5. For a Kotoba app, its client-runtime descriptor declares **no new external operation, service,
   endpoint origin or data category** compared with the installed version. Fewer is allowed.
6. The download is within the host's byte budget per app (40 MiB in the Itonami Store today) and
   per day.
7. The network condition the person chose holds (default: unmetered networks only).

Conditions 4 and 5 are what make the approval narrow: an automatic update can fix and change an
app, but it cannot give the app a new way to reach the network or a new kind of data.

## Decision 3: compatibility with the contract

| Contract point | How a standing update approval keeps it |
| -- | -- |
| Fresh, operation-specific approval | The approval is for one declared update service and its two fixed operations, chosen by a direct trusted user choice in host UI that names the service, origin, operations and data categories. It is not "fresh" per request, which is the amendment. |
| One approval never authorizes another operation or endpoint | It covers only the update origin. It never covers the updated app's own operations, nor installing new apps. |
| App or bot code must not mint, persist or broaden approval | Unchanged for app and bot code. Only the trusted host may persist this one approval, in host-private storage; no app or bot can read, create or widen it. A Bot's tool approval cannot turn it on. |
| Denial sends nothing | Turning automatic updates off (the default) sends nothing in the background. |
| Pin an immutable revision and verify the digest | Each update is pinned by the signed catalog entry and its SHA-256; the pointer only says which signed catalog is newest. |

## Decision 4: how the person sees and stops it

- **Off by default.** It is turned on per host, after a screen that lists the origin, the
  operations, the data categories, the check frequency and the network condition. The Allow button
  is armed after the same 600 ms delay as the consent dialog.
- **Per app.** The person can exclude any app; Torihiki can be left on manual.
- **Visible.** Every automatic check, download and install is written to a host log the person can
  open: time, endpoint, bytes, SHA-256, old and new version, result. After an install the host
  shows a notification.
- **Revocable and expiring.** Turning it off takes effect at once and cancels a download in
  progress. The approval also expires after a fixed period (proposed: 90 days) and must be turned on
  again; the host says so in advance.
- **Recoverable.** The previous APK is kept, so the person can reinstall it (Android cannot
  downgrade in place without clearing data; the host says so).

## Decision 5: what the host needs that does not exist yet

- **A signed "newest catalog" pointer.** The Store pins one immutable catalog URL today
  (`android/online-pins.dev.json`). Automatic updates need a fixed pointer that names the newest
  signed catalog revision; its content is trusted only after the envelope verifies and its revision
  is above the floor.
- **A production publisher key** with rotation and revocation. Until it exists, the standing
  approval is limited to development builds that pin the development debug key, and the Store says
  "development key" on the settings screen.
- **Android silent install.** The Store asks for `UPDATE_PACKAGES_WITHOUT_USER_ACTION` and sets
  `USER_ACTION_NOT_REQUIRED` on eligible sessions. It must be the installer of record (true for apps
  it installed). If Android still asks, the update waits for the person; that is not a failure.
- **A background job** (Android `JobScheduler`) that runs the check at most once a day under the
  chosen network condition.

## Risks

- **A stolen publisher key ships a malicious update** without anyone looking. Conditions 4 and 5
  stop new permissions and new network operations, but not harmful code within the existing ones.
  This is the main reason a production key with revocation is required before anything outside
  development builds.
- **Privacy.** A daily background read tells the update origin the device's IP address, when it
  checks, and which apps it has. Bounded to that origin and listed when the person turns it on.
- **Surprise.** An app changes without the person opening the Store. The notification and the log
  address this; the per-app opt-out handles apps the person wants to keep on manual.

## Owner decisions pending

1. Whether to adopt the amendment at all (merging this PR adopts the contract text).
2. The expiry period (proposed 90 days) and the check frequency (proposed once a day).
3. Whether development builds may use it with the development debug key before a production key
   exists.
4. Whether condition 5 (no new external operations) should instead allow new operations that only
   reach origins the app already declares.

## Out of scope

OS updates (the Awai PC updater, AWAI-3064) have their own policy and are not covered. Web apps
served from a static origin are updated by reloading and are not covered. Bots and their fleets
are not covered.
