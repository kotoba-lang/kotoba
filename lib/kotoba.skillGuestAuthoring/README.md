# skill-guest-authoring

The agent-instruction package (role `:agent-instruction-package`, per
`manifest/repository-rules.edn` in the `com-junkawasaki/root` superproject) for
writing a `.kotoba` guest.

See [`SKILL.md`](SKILL.md). This repo has no runtime: it declares a procedure,
its inputs and its outputs, and points at the authorities that hold the
answers.

## Why it exists

`.kotoba` refuses two very different things with the same shape of message: a
**safety invariant**, which is permanent, and a **backend that has not caught
up**, which is not. Trying harder does not tell them apart — only the
`:disposition` in `lang/surface-status.edn` does.

The cost of confusing them is not a failed build. It is a module written in a
self-imposed dialect, with a comment explaining the style, that outlives the
gap and gets copied.

## Why it states no readiness values

Every capability number in this workspace that was copied into prose went
stale, including in the repo-wide `AGENTS.md`, more than once. So this package
carries *how to read* the authorities and never *what they said*. A skill that
quotes a qualification table is a skill that will one day be confidently wrong.

## Installing

It is a plain `SKILL.md`, so both agent hosts in use here read it as-is:

```bash
# Claude Code
ln -s "$PWD" ~/.claude/skills/guest-authoring

# Hermes (skills live under a category directory)
mkdir -p ~/.hermes/skills/software-development
cp -r "$PWD" ~/.hermes/skills/software-development/guest-authoring
```

## License

MIT.
