# skill-loop-system-dynamics

The agent-instruction package (role `:agent-instruction-package` per
[`kotoba-lang/loop-ux-kaizen`](https://github.com/kotoba-lang/loop-ux-kaizen)'s
`resources/repository-rules.edn` taxonomy) for
[`kotoba-lang/loop-system-dynamics`](https://github.com/kotoba-lang/loop-system-dynamics).

See [`SKILL.md`](SKILL.md) for the actual agent procedure. This repo has no
runtime of its own — it declares how to invoke `loop-system-dynamics`'s
real commands and interpret their real output, nothing more.

## Why this exists

`loop-system-dynamics`'s own README carried "a `skill-loop-system-dynamics`
(agent-instruction package) ... per the same taxonomy" as a documented,
not-yet-built "Next" item since its first cycle. Per `repository-rules.edn`:

```edn
{:prefix "skill-"
 :role :agent-instruction-package
 :must [:define-agent-procedure :declare-inputs :declare-outputs]
 :must-not [:require-resident-runner :own-ci-state]
 :examples ["skill-ux-kaizen"]}
```

This is the first real instance of the `skill-*` role anywhere in
`kotoba-lang` — even the taxonomy's own named example (`skill-ux-kaizen`)
does not exist as a repo yet.

## Composition

`repository-rules.edn`'s own composition rule: `loop-*` repos are the sole
authority for domain/scoring logic; `skill-*`/`action-*` are adapters only.
This repo never re-implements anything `loop-system-dynamics` (or the
`kotoba-lang/dynamics` library it depends on) already computes — it points
an agent at the real commands and tells it how to read the real output.

## License

MIT.
