# plugin-hermes — kotoba-lang tools for the Hermes agent

A Hermes **backend plugin** (`kind: backend`, toolset `kotoba`) that answers
the three questions an agent gets wrong from memory. Hermes lives in someone
else's repository (`NousResearch/hermes-agent`), so nothing here is committed
there; this repo is the reviewable original and installing means copying it
into that checkout's `plugins/kotoba/`.

```bash
cp -r . ~/.hermes/hermes-agent/plugins/kotoba
export KOTOBA_WORKSPACE=~/github/com-junkawasaki
```

| tool | question |
|---|---|
| `kotoba_surface_status` | Is this refusal **permanent**, or a backend that has not caught up? |
| `kotoba_capability_kits` | Which backends have **qualified** this capability? |
| `kotoba_check` | Did the compiler admit this guest? (and: admitted is not run). Memoised by the file's Merkle closure hash — see below |

## Why these three

They are the three places a `.kotoba` answer goes stale between one turn and
the next, and all three fail *fluently* — the wrong answer reads exactly like
the right one.

**A refusal does not say which kind it is.** A safety invariant and an
unfinished backend arrive as the same message. An agent that cannot tell them
apart writes a module in a self-imposed dialect, adds a comment explaining the
style, and that comment outlives the gap and gets copied. Only
`:disposition` in `lang/surface-status.edn` separates them.

**A readiness table cannot be quoted.** Every capability value in this
workspace that was copied into prose went stale, including in the repo-wide
`AGENTS.md` more than once. The tool reads the kits and returns each
`:qualification` map verbatim, with the key set the kit actually has — they
differ per kit, so a summary across kits is wrong by construction.

**`grep` truncates readiness tables silently.** Wrapped lines cut
`grep -A … | cut` output mid-map, and a truncated read of a qualification
table is indistinguishable from a complete one. The reader uses an EDN reader.

## Why the Python decides nothing

`read_authority.cljk` holds every judgement about what an authority file
means, beside the data and in the same language. `tools.py` turns arguments
into an argv and an exit code into a protocol answer.

A second reader in Python would be a second decider: two answers that agree
until the day they do not, with no test that would notice. That is the shape
`plugins/dashboard_auth/did` established here (ADR-2608197300 §3, §5) — the
plugin language is dictated by the host, and a file that holds no decision
costs nothing by being in it.

## The exit codes are the contract

```
0  answered                -> tool_result
1  answered: not present   -> tool_result, found=false
2  could not answer        -> tool_error
```

**1 and 2 must not collapse.** "this entry is not in the authority" is a
measurement; "I could not open the authority" is not. Collapsed, an unread
file reports as an absent feature — the failure class this workspace names in
ADR-2608136000, and the one the probe checks in both directions.

The answer also carries the authority's own `as-of`. A date that looks old
means *the checkout is behind*, not that the language stopped moving; the tool
says which, instead of quietly serving a stale file as current.

## Verifying an install

```bash
KOTOBA_WORKSPACE=~/github/com-junkawasaki python3 probe.py
```

Twelve checks in three pairs, each direction of each distinction. Changing the
absent-workspace exit from 2 to 1 turns two of them red, which is how the
pairing was checked.

## Configuration

| variable | |
|---|---|
| `KOTOBA_WORKSPACE` | the `com-junkawasaki` checkout holding `orgs/kotoba-lang/*` |
| `KOTOBA_NBB` | optional path to `nbb` |
| `KOTOBA_AMU` | optional path to `bin/amu` |

Without `KOTOBA_WORKSPACE` the plugin registers its tools but `available()`
refuses dispatch — a tool that answered "not found" from an unconfigured
machine would be reporting an unread authority as an absent feature.

## Not done

Read-only. Nothing here compiles for you, lands a change, or advances a pin;
`kotoba_check` runs `amu check` and says plainly that a passing check is not a
run. Making a proposal is a governed act, and it belongs to the bot's own
verifier, not to a tool the model can call.

## License

MIT.

## `kotoba_check` memo (2026-09-18)

`amu check` is pure, so its verdict is memoised (ADR-2608160200: an Execution
CID is a memo key exactly when the effect set is empty). The key is
`symbol-index closure <file>` — the Merkle hash of every definition in the
file with its dependencies' bodies folded in (names, local binding names,
comments, docstrings and whitespace are not part of it) — plus the amu
binary's identity. A comment edit is a hit; a body edit anywhere in the
closure is a miss. Measured (probe_memo.py): miss 26.7 s, hit 0.39 s.

- a served verdict always says so: `"memo": {"hit": true, "key": …}`;
  `fresh: true` re-runs amu
- when the closure cannot be computed (no index, no `symbol-index`), the check
  runs and is **not** memoised: `"memo": {"hit": false, "not_keyed": "<why>"}`
  — could-not-key never looks like keyed
- store: `~/.kotoba-cache/kotoba-check-memo.json` (`KOTOBA_CHECK_MEMO` overrides);
  `KOTOBA_SYMBOL_INDEX` points at a specific `symbol-index` (binary or `.cljk`)
- `amu check` itself already emits a per-definition CID
  (`kotoba.definition-identity/v1`, with `:dependencies`). The two are the
  same idea computed twice (compiler-side after admission, index-side before
  it and for every dialect); aligning them is open.

```bash
KOTOBA_SUPERPROJECT=~/github/com-junkawasaki python3 probe_memo.py   # 8 checks, both directions
```
