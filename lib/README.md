# Bundled Kotoba libraries

The standard-library pilot lives in this repository:

| Canonical ID | Source | Legacy namespace APIs |
|---|---|---|
| `kotoba.coll` | `kotoba.coll/src` | `kotoba.coll`, `kotoba.lang.coll` |
| `kotoba.spec` | `kotoba.spec/src` | `kotoba.spec`, `kotoba.lang.spec` |
| `kotoba.json` | `kotoba.json/src` | `kotoba.json`, `kotoba.lang.json`, `json.*` |

`catalog.edn` declares exact aliases for old repository/coordinate names.
`kotoba.*` is a project namespace and requires no DNS ownership. Each package
includes its complete same-family per-definition source closure; those small
repos are no longer needed to load these namespaces from this source checkout.
External support dependencies remain explicitly pinned in each `deps.edn`.

Run from repository root:

```sh
node scripts/check-libraries.mjs
node scripts/test-libraries.mjs
node scripts/test-libraries.mjs --check-design

KBB_NO_STDLIB=1 kbb --backend sci --config lib/nbb.edn --classpath src \
  scripts/library-catalog.cljk resolve kotoba-lang/json
KBB_NO_STDLIB=1 kbb --backend sci --config lib/nbb.edn --classpath src \
  scripts/library-catalog.cljk classpath kotoba.coll kotoba.spec kotoba.json
```

The test driver uses the installed `.cljk` SCI engine (`KBB_ENGINE` can select
it), the existing native `bin/kbb_deps.cljk` resolver, the declared immutable
text bootstrap, and the dependency graph of `lib/deps.edn`. No implicit sibling
classpath or JVM resolver is used. Missing declared dependencies fail the run.
The driver refuses Java/Clojure/bb subprocesses. The standalone libraries'
older runner files are retained as import provenance; use the driver above to
execute all portable suites, including the definition facades. The only
excluded suite is `kotoba.json/test/json/core_test.cljk`, whose origin is `.clj`.

`imports.json` preserves source commit/tree, original-to-local file paths,
per-file digests, licenses, and executable modes. Imported definition sources
use `.cljk` here; `cljk-origin.edn` records their original extensions without
changing their code bytes. `local-changes.json` explicitly records build metadata
adjustments and removal of inherited empty lines at EOF. Source comments,
changelogs, and READMEs inside
the imports describe their original standalone repositories. This page and
the [implementation ADR](../docs/ADR-kotoba-library-monorepo-and-lexicon-events.md)
describe the current integration.

This is source consolidation and portable compatibility coverage. It is not
signed release publication, full Kotoba source conversion, native qualification,
or an implementation of event publish/subscribe. Amu and the other execution
and contract owners stay separate. Existing external pins keep working from
the old repositories until their consumers migrate.

`lib/kbb/` remains the existing guest script library; it is not moved by this pilot.
