# Explicit JVM compatibility gates

`cljk_loader.cljk` is a byte-identical copy of
`kotoba-lang/kotoba-lang` commit `b77db77494bbd14b52fef97bb16b3ffe965755dc`,
`src/kotoba/lang/cljk_loader.cljk`. It preserves CLJK namespace loading and
reader-conditionals for the repository's explicitly declared JVM launcher
and compatibility tests. It is not a native Amu target or an automatic
fallback from a refused native/SCI operation.

The static analyzer and pinned security inventory do not recognize CLJK.
`node scripts/prepare-jvm-analysis.mjs` produces checked byte-identical
`.cljc` analysis inputs in `.jvm-analysis`, including exact copies of the
adoption and dependency declarations. Runtime tests continue to load the
actual CLJK source through the loader; analysis copies are not runtime
artifacts or edited historical origins. The original security checks still
compare all discovered import/sensitive-operation edges against declarations.

Exception type reader-conditionals preserve the SCI exception class variable
and use the JVM class literal required by its compiler. Test fixtures that
represent forbidden Babashka input retain their intentional `bb` text; their
contents must not be migrated along with production entrypoints.
