# Repository Issues

This repository keeps GitHub issue source material in-repo so architecture
review findings can be reviewed, versioned, and synchronized.

## Layout

- `docs/issues/*.md`: human-readable issue body, suitable for `gh issue create`
  or `gh issue edit --body-file`.
- `.issues/issues.edn`: mapping from local issue body to GitHub issue URL,
  finding id, and current tracking state.

## Sync

GitHub is still the live collaboration surface. The repo copy is the audit and
review copy.

Create from a local issue body:

```sh
gh issue create --repo kotoba-lang/kotoba \
  --title "<title>" \
  --body-file docs/issues/<file>.md
```

Refresh a GitHub issue body from the repo copy:

```sh
gh issue edit <number> --repo kotoba-lang/kotoba \
  --body-file docs/issues/<file>.md
```

Do not close the GitHub issue just because the repo copy exists. Close it only
when the acceptance criteria in the body are implemented and verified.
