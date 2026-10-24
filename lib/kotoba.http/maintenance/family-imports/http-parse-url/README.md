# http-parse-url

`kotoba.http.parse-url/parse-url`

One definition. Reaches nothing else in this family.

## `kotoba.http.form-urlencoded` (2026-09-24)

`form-encode` / `form-decode`: application/x-www-form-urlencoded with exactly
the strings `java.net.URLEncoder/encode` and `java.net.URLDecoder/decode` give
for UTF-8 -- including lone surrogates (`?` -> `%3F`), the JDK's U+FFFD
replacement rules for malformed UTF-8, and the hex digits `Integer.parseInt`
accepts (`%+F`, `%-0`, non-ASCII Nd digits). Where the JDK throws
IllegalArgumentException these throw ex-info with the JDK's message and
`{:kotoba.http.form-urlencoded/error :illegal-hex | :negative-value | :incomplete-escape}`.

It lives here, beside URL parsing, because kotoba had no URL/percent codec;
it lets `.cljk` sources drop `java.net.URLEncoder` / `URLDecoder`
(root `scripts/migrate-java-net-urlencoder-to-kotoba-http-parse-url.cljk`).
Pure: reaches nothing, no host interop beyond reading a UTF-16 code unit.

Oracle: JDK 21 (Temurin 21.0.1). `test/kotoba/http/form_urlencoded_vectors.tsv`
(3,902 JDK-written cases) runs under `kbb -M:test`. A larger set of 429,472
cases (every BMP code unit encoded, every `%XY%ZW`, `%0c` / `%c0` for every BMP
char, 60,000 random escape runs, 20,000 random strings, 30,000 round trips and
mixtures) gave 0 mismatches on kbb and on the JVM.
