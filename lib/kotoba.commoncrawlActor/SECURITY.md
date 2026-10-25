# Security Policy

This project self-mints CACAO credentials and writes to a shared production
service (net-kotobase / kotobase.net). Treat vulnerabilities as potentially
high impact.

## Do Not Disclose Publicly

Report privately before opening public issues for:

- CACAO identity seed exposure (`.commoncrawl/identity.edn`)
- authorization bypass against net-kotobase's `web.ingest`/`web.search`
- Governor bypass (a domain outside the seed list, or over an exclude
  entry, actually being fetched/ingested)
- audit-ledger tampering
- fetch-budget bypass leading to excessive load against Common Crawl or
  net-kotobase

## Reporting

Use GitHub private vulnerability reporting when available for the
repository. If that is unavailable, contact the repository maintainers
through the kotoba-lang organization before publishing details.

Include:

- affected commit or version
- reproduction steps
- expected and actual behavior
- impact on net-kotobase data, policy enforcement, or audit logging
- suggested fix, if known

## Production Guidance

- Store the CACAO seed outside Git (`.commoncrawl/` is gitignored — keep it
  that way).
- Run the offline test suite before any change touching `commoncrawl.policy`
  or `commoncrawl.identity`.
- Review the ledger (`commoncrawl.store/ledger` /
  `commoncrawl.report/render-ledger`) after enabling a new seed domain.
- Use least privilege: the minted CACAO's resource scope
  (`commoncrawl.identity/kotobase-resources`) should stay limited to what
  `web.ingest`/`web.search` actually need.
