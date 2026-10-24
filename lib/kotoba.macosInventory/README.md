# macos-inventory

Read-only inventory of what a Mac is running and what it is permitted to do.

```clojure
(require '[macos-inventory.host :as inv])
(inv/inventory {})
;; => {:launchd [...] :login-items [...] :config-profiles [...]
;;     :system-extensions [...] :kexts [...] :browser-extensions [...]
;;     :tcc-grants [...] :listening [...] :installed-apps [...]
;;     :gatekeeper {...} :xprotect {...} :coverage {...}}
```

```sh
npm run dump          # human summary + per-surface coverage
npm run dump -- --edn # the whole inventory as EDN
```

## Two rules hold everywhere

**1. No probe may raise an authorisation or consent dialog.** A tool that fires
prompts as it starts teaches the user to click through them. Measured on
macOS 26: `sfltool dumpbtm` requests `system.privilege.admin` and raises an auth
sheet, so it is **not called at all** — login items are read best-effort from the
BackgroundTaskManagement store instead.

**2. A probe that cannot see says so.** Every surface reports `:complete`,
`:partial`, `:denied` or `:not-attempted` with a reason. "Nothing found" and
"could not look" must never render the same, so `combine-status` degrades rather
than overwrites and **a denial can never be masked by a success elsewhere**.

Worked example from a real machine — zero is not always zero:

```
login-items [denied] BackgroundTaskManagement store is a keyed archive whose
  identifiers are inside base64 <data> blobs — none could be extracted, which is
  NOT the same as none being registered.
tcc-grants [denied] user TCC.db unreadable — grant Full Disk Access …;
  system TCC.db unreadable — …
kexts [complete] 0 third-party of 238 loaded kexts
```

## Surfaces

| surface | source | notes |
|---|---|---|
| launchd | `~/Library/LaunchAgents`, `/Library/Launch{Agents,Daemons}` | plists with no `Program` **and** no `ProgramArguments` run nothing and are skipped — uninstallers leave such stubs, and scoring them as unsigned root daemons is how a tool teaches people to ignore it |
| login items | BTM store (best effort) | never `sfltool` — it prompts |
| config profiles | `profiles -L -o stdout-xml` | `:removable? false` is a materially different fact |
| system extensions | `systemextensionsctl list` | |
| kexts | `kmutil showloaded` | third-party separated from Apple's |
| browser extensions | Chromium-family profile dirs | manifest v2 **and** v3; `:risky-permissions` flags broad observation (`<all_urls>`, `webRequest`, `cookies`, …) |
| TCC grants | **both** TCC databases | Full Disk Access, Screen Recording, Accessibility and Input Monitoring live only in the *system* db — a user-only probe reports `:complete` while omitting exactly these |
| listening sockets | `lsof` + `ps` | the pid is resolved to a real executable path, because lsof's truncated command name cannot be code-signed |
| installed apps | app bundle `Info.plist` | version, `:app-store?`, `:sparkle-feed` — enough to *detect* updates; this library never installs anything |
| Gatekeeper / XProtect | `spctl --status`, XProtect bundle | Apple's own blocklist version matters more than any list a third party ships |

## Signature verdicts

`codesign -dv` writes its entire report to **stderr** and exits 0. Reading only
stdout makes every verdict `:unknown` — which reported a fleet of properly signed
daemons as unverifiable on the machine this was found on. `sh` uses `spawnSync`
so a successful command's stderr survives.

Developer ID says *who* signed something; only `spctl` says Apple **notarized**
it, so those are separate states. And `:unknown` is never treated as evidence of
wrongdoing — not knowing is not a finding.

## Layout

```
src/macos_inventory/core.cljk   pure: vocabularies + every parser
src/macos_inventory/host.cljk   nbb: the probes
src/macos_inventory/cli.cljk    nbb: dump
```

Parsers live in `core` and are tested against **verbatim captured command
output**, because `lsof`, `profiles`, `systemextensionsctl` and `kmutil` all emit
shapes that are easy to almost-parse — and a verdict derived from a misread line
is reported with exactly the same confidence as a correct one.

## Tests

```sh
npm test      # 19 tests / 52 assertions — parsers against real captured output
kbb -M:test   # the .cljc core on the JVM
```

## Provenance

Grown out of `gftdcojp/ai-gftd-misogi` (ADR-260726 in `com-junkawasaki/root`).
`com-macos-darwin` is a different thing — a clean-room protocol-compat actor, not
a system inventory.
