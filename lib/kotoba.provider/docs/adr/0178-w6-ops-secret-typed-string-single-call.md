# ADR 0178: T8.3 typed-string single-call secret_name_ok (kotoba:typed host)

- Status: Accepted
- Date: 2026-07-31
- Depends: ADR 0173/0176 pure len+char gates; kotoba-compiler typed ABI; browser-host

## Context

Pure i64 gates (name-len, char-class) require a **host walk**. Full single-call
name policy needs a string value surface. Compiling
`(defn secret_name_ok [name :string] …)` emits a module that imports
`kotoba:typed` (externref typed ABI). That module is **not** a pure
import-free Component (`wasm-tools component new` fails without a typed world).

## Decision

### Ship typed-host-coupled compiler-AOT module

| piece | role |
|---|---|
| `src/secret_name_ok.kotoba` | single-call policy + `main` live vector |
| `secret-name-ok-v1.wasm` | kotoba-compiler wasm32 + provenance |

Exports:

- `secret_name_ok` — typed string → i64 (`0` ok, `-1` empty, `-2` >128, `-3` forbidden)
- `main` — host-parity style live vector → `-130`  
  (`ok=0`, `empty=-1`, `has/slash=-3`, `ok-name=0` → `0*1000-100-30+0`)

Forbidden code points match ADR 0176 / hand WAT: NUL, TAB, LF, space, `* / ? \`.

Registry `:secret-name-ok` with `:typed-host :kotoba.typed`,  
`:signed-content-addressed-package :pending` (no Component gate flip).

### Live proof

```sh
node --input-type=module -e '
import { readFileSync } from "fs";
import { instantiateKotoba } from "<compiler>/runtime/browser-host.mjs";
const h = await instantiateKotoba(readFileSync("…/secret-name-ok-v1.wasm"));
console.log(h.instance.exports.main()); // -130n
'
```

Provider suite records digest + export shape; optional live test when
`KOTOBA_BROWSER_HOST` points at `browser-host.mjs`.

### Honesty

- Not pure Component packaging; readiness `:signed-wasm` not further flipped
- `:wasm-aot` stays `:partial` (request/result EDN codec still open)
- Hand WAT ptr/len + pure gates remain

## Non-claims

- Not scoped-fs typed-string single-call path
- Not production signed Component claim
- Not full kit request/result codec AOT

## Evidence

- browser-host `main` → `-130n`
- digest match; exports `secret_name_ok` + `main`
- imports namespace `kotoba:typed`

## Related

- Reliability WBS T8.3
- ADR 0163, 0173, 0176, 0177
