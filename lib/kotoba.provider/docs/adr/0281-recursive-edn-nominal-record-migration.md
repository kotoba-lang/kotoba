# ADR 0281: recursive EDN key/value nominal-record migration

- Status: Accepted
- Date: 2026-08-04
- Depends: provider ADR 0250–0255/0260/0265–0268; compiler ADR 0208/0209

## Context

Twelve recursive EDN packages still constructed and projected their two-field
key/value entries with raw record operations. The recursive `:edn/node` schema
must refer to that entry record before the later `defrecord` is elaborated, so
the migration also exercises compiler ADR 0209's exact schema forward
declaration rule.

## Decision

1. Give every package a domain-visible `EdnKeyValue` record with `k` and `v`
   string fields.
2. Forward-declare its exact generated descriptor in the namespace schema
   table so recursive variants remain closed and statically validated.
3. Replace raw construction and projection with `->EdnKeyValue` and keyword
   access while preserving every export, bound, capability wire, and oracle.
4. Reject incompatible same-name declarations in the compiler; compatibility
   is exact descriptor equality, not a widening or shadowing rule.
5. Keep `hetero-vector-at` projections explicit for now. Their descriptor-aware
   language surface is a separate design problem from nominal records.

## Evidence

- compiler PR: kotoba-lang/compiler#526
- compiler merge: `92b9bb87b80fa2242ec724099faa65f7ece217ad`
- all twelve independent KIR oracles pass:
  - entropy record/host: `-2504`, `-2510`
  - git record/host: `-2503`, `-2509`
  - HTTP host: `-2506`
  - process record/host: `-2502`, `-2508`
  - recursive record: `-2405`
  - scoped-fs record/host: `-2505`, `-2512`
  - secret record/host: `-2406`, `-2507`

| Package | Wasm SHA-256 | Source SHA-256 | Provenance seal |
| --- | --- | --- | --- |
| entropy-record-kv-edn | `4131cc31606f7b7be1dd3a5a27a9fecb9b890c09d3ca7ad025441946c7ac35ad` | `ae061e75b40f892714bec200249c1805039b711388d8d7f875a349044788193d` | `1e67783251aca714b6b8e8fa8d808029a6d223154029aed341eb3faa0fd7b05f` |
| entropy-w4-host-edn | `604fe3ff74003de8656d0726375c52b60bf5c9d52e4523a630801d8ac1f25fcb` | `f249f578b63f3d336a258fb5037fb95a1c4c4da1c05e66dabe13793776ba11dd` | `eccc6bd831db4dcbbfa63bf438a48e06d63fb6ccb215dc962ecd449ef4198366` |
| git-record-kv-edn | `390b086e373ac321857511dfa70b4866801c18cf2d56e5b7791eb12b9ffd4347` | `b3cf9f8802516415a79f5bde973160c94ee45e78b6d9cca3cfdf186b3d7e9678` | `04bfb120bd11a12980a6b9911c2a9916540f1e65d9c047f9025c9228c4e9079e` |
| git-w4-host-edn | `95152251cf0e5c7163fc831bf426da80ed2bc06ad48a19621308b207a25c1fa5` | `f01b0a6bd363dfea71e7ec81fc23a577af1a1cd4a303d6e54a7b447dd29966fd` | `2cc845d9745b1cf1efa2d6fbb85a0acbd90526273cf209d5366c899d77a10e5d` |
| http-w4-host-edn | `a558ce394b32d6e32887a35483114b95ed08516bdf85e357ab57edca582af8b0` | `16db89231f19988980682279ae8804fef9785de29aeade1ab6f886b8e65adafc` | `7df047f58d8e560d1fd0dff2b3293ee8df9eb6ea86623e5ff3f78b616c812fc1` |
| process-record-kv-edn | `501deb2d2466edb8a4f7da66d6c3c2a2b947184e0fefe55e3c4dbb290d98ebee` | `5fbed79046e9c9bf4cea5786cab8842fe3cd0ca07b5a85e209be592e2570de7e` | `7a49969af0085e2632e0f0e820c7b357cd1e9cdbfcc789027148bc0aa9599611` |
| process-w4-host-edn | `6054506551d860d92f73db49921a338f7a170d9363569162f1558f3acfe27eeb` | `5eac2ee061d4b80151f80cd82fbe1feeca2a1a4a10e4d632b18567d44c03b013` | `c5b0310f453e9bbe1aff7cff22fd931ddd95b2e97221b68365b4f0706cf77025` |
| recursive-record-kv-edn | `a6e24260014d50b8012c70706417a5341a49a65ebb42c31d31d660cc3bfb8143` | `9628af0efeb4e78d2711e7584883852915e63791b15f163836917e2e82250086` | `11a02d9b60ea7bcc57846da783261d0013e0f4c1d6877483edba075ce82ca8f6` |
| scoped-fs-record-kv-edn | `2a6b08309b73d1a826616c01fcd8ac444e5bd93f21d023f99bcaa924dda27670` | `6a9fc5db43cbeecf57ba9b61d250edc9945b141b649d1902cbd5fc382cf1b2f0` | `81bb212af7a8711eb88e7109497fccade8f88d819923f719b060909ce591be35` |
| scoped-fs-w4-host-edn | `b8339220a4e01f94e8bdc37466e9f3c9c8dfcd6931f8e8c3ffc2637c273126b9` | `fda6e2b8ce70b64b77bb4ef11355c8d63e8511424821fb62a0c95461762fb111` | `7ce97a5e613e3a5eb7fc7fbf5946d8d6fcf992d3ab72557f341b6ed0245c0670` |
| secret-record-kv-edn | `5fc25c7169a1f1fb58e9e8c010b21063fab0f4f753d4caf1c0ae0bc4498a9897` | `acb2452973e4d4a0d8a6137128b5aaefe7d389da396b7d02a1729936dbdccd9b` | `4e6efb873571be374ef86d2ed8e22b0af3f83510c59a38cade7dc38c1b130851` |
| secret-w4-host-edn | `3c637641f132b570f0504e85c238a711ee3f3b892875c7e8cf02edff66c11924` | `751a52c005a308f4cbb69141cb438a2bb31733b2ba710260de2790d8e47929f3` | `0b1696b61b49215e19bb9b0cc6d2cbe3fb10d3120ecb3178f03525fcf074086e` |

## Consequences

The authored provider surface loses its final 36 raw `record-new` and
`record-get` sites. Construction and access now state domain intent directly.
The only remaining low-level source family is 32 `hetero-vector-at`
projections; replacing those requires a descriptor-aware access design rather
than more record sugar.
