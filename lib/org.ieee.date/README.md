# kotoba-lang/org-ieee-date — POSIX `date` in UTC, as a Kotoba command binary

`date` from IEEE Std 1003.1, the UTC forms, written in `.kotoba` and compiled
to a standalone native executable.

```sh
./date -u                       # Wed Sep 16 10:51:46 UTC 2026
./date -u +%FT%TZ               # 2026-09-16T10:51:46Z
./date -u -r 1700000000 +%s     # a given epoch (BSD -r)
```

Conversions: `%Y %m %d %H %M %S %F %T %s %Z %z %a %b %e %j %u %w %y %I %p
%% %n`; anything else prints the character itself, as `/bin/date` does.

## Measured, 2026-09-16

1,451 invocations in 1,268,018 Bash calls across 558 agent transcripts
(superproject ADR-2609161710). The ones with arguments are UTC: `-u
+%H:%M:%SZ` 69, `-u` 57, `-u +%FT%TZ` 52, `-u +%Y-%m-%dT%H:%M:%SZ` 38, `-u
+%H:%MZ` 26, `-u +%s` 20 (and 49 GNU `-u -d`, which fails on this system
anyway). So this speaks UTC only.

## Measured against the system utility

`test/date_test.cljk` compiles the guest, packages it, **runs the binary**,
and compares stdout, stderr and exit status against `/bin/date`: 153 exact
cases — 9 epochs × (the default line + 16 formats) with `-r SECONDS` so both
answer the same instant — plus one live `-u` accepted when it equals the
system's read just before or just after. The epochs are the ones that
separate a right calendar from a wrong one: 0, the leap day 2000-02-29, the
day before 1970 (negative epoch, floor division), 2100-01-01 (a century that
is not a leap year), the last second of a day. All byte-identical. Six named
divergences (below).

## Where the time comes from

`:clock/now` (wire 7) in its **text form** — `"wall"` answers milliseconds
since 1970 as decimal text. That form was added to the loader for this
command (amu #1015): the clock-v1 record codec is admitted on the JVM route
and the typed Wasm route but not on the JVM-free native route a packaged
command is built by, so until then a command could not read a clock at all.

Seconds become a civil date with the inverse of days-from-civil (Howard
Hinnant's algorithm), so leap years fall out of the arithmetic rather than a
table. The first cut had the signs of two terms in `yoe` swapped and printed
Mar 1 for the leap day and `1971-01-71` for the day before 1970 — the suite
pins both.

## What this is not

- **Local time.** Bare `date` and `date +FMT` (no `-u`) need the zone
  database, which no capability supplies; refused with a message, exit 1,
  rather than answered in the wrong zone.
- **No `-d`, `-j`, `-v`, `-f`, `-I`, `-R`**, no setting the clock.
- Capabilities: `:cli/args` (38), `:clock/now` (7), `:io/write` (37),
  `:io/write-error` (39).
