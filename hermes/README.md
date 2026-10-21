# hermes/ — the resident bots that act for this repository

This directory is the **source of truth** for the Hermes profiles listed below
(ADR-2609241200). The host's `~/.hermes/profiles/<profile>` is materialized
from `hermes/profiles/<profile>/` and checked against it:

```
kbb --backend sci scripts/hermes-profile-repo.cljk materialize <profile>   # repo -> host
kbb --backend sci scripts/hermes-profile-repo.cljk check <profile>         # 0 agree / 1 drift / 2 could not compare
kbb --backend sci scripts/hermes-profile-repo.cljk export <profile>        # host -> repo, then commit
```

(run from the com-junkawasaki/root superproject; registry
`manifest/agent-registry.edn` (canonical source-home registry).)

Each profile directory holds SOUL.md, profile.yaml, config.yaml (host-local
blocks removed), cron/jobs.json (definitions only), scripts/ and the skills the
profile owns. **Never here:** `.env` or any secret value, workspace/ledgers,
sessions, memories, logs, caches, run state.

## Profiles

| profile | description |
|---|---|
| `jv-migration` | JVM→kotoba 移行専任。org 内に残る JVM (clojure CLI/JVM-only) 依存を kotoba(nbb/amu |
| `kbb-migrator` |  |
| `sec-audit` | セキュリティ監査担当。kotoba-lang org と com-junkawasaki 配下の脆弱性評価、GitHub セキュリティ設定(secret |
| `sec-sentinel` |  |
| `server-operator-crawl` | Preserved text-library profile source |
| `whois-org-crawl` | Preserved text-library profile source |
| `wiki-standards-crawl` | Standards-body crawl profile source |

The three text-library profile trees moved from `kotoba-lang/text` without
changing their contents. `lib/profile-homes.json` binds every copied file to
the imported default snapshot. Library import adds only library source paths;
it does not load these profiles. This migration does not materialize host
profiles or start cron jobs. Amu and other execution infrastructure remain
in separate repositories.
