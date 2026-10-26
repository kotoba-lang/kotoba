# Grade A capability lifecycle

Each `open-session` creates an authority state scoped to that Wasm instance:

- `:active` is initialized only from imports admitted by `HostCaps`;
- every host-function invocation atomically rechecks active authority and
  increments its per-import use counter;
- `revoke-import!` removes authority immediately and records its reason;
- `drop-import!` voluntarily removes authority for the remaining session.

All fourteen `actor:host` implementations call the same `ensure-granted!`
chokepoint, so an already-linked Chicory function does not retain authority
after session revocation. Reinstantiation is not required.

Optional `kotoba.capability-lease/v1` descriptors narrow that admitted
authority further. They must exactly cover the requested imports, bind to the
same closed execution identity and component CID, remain live at admission and
at every call, and keep their mutable remaining-use count exclusively in the
host session. A descriptor is therefore auditable data, not a reusable bearer
token. Reaching zero atomically deactivates the import.

Authenticated Murakumo authority events independently feed the live epoch
source consulted at each Component provider call. A control-plane revocation
advances the epoch, so an already-running Component cannot continue using a
lease issued at the earlier epoch.

Verification:

```sh
kbb -M:test \
  -n kototama.tender-test \
  -n kototama.component-authority-test \
  -n kototama.component-provider-test
```

T-02 is complete. Qualification includes a table derived from the authoritative
`actor:host` surface that checks atomic use accounting and post-link revocation
for every import, runtime one-shot/expiry checks, and authenticated live-epoch
propagation into already-running Component provider sessions.
