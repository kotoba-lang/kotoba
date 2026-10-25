# kotoba-lang/loop-render-fidelity

**A local loop that measures what the PDF renderer actually does to real
documents, and ratchets.**

```sh
bin/run-fidelity-loop ~/Documents            # 48 documents, ./evidence
bin/run-fidelity-loop ~/Documents 96 ./ev    # more, elsewhere
```

Exits non-zero when this run is worse than the last one over the same
corpus, so a shell loop or a pre-commit hook can use it without parsing
anything.

```text
find corpus → render → witness → ratchet → append evidence → name the next target
```

## Why local, and why that is the point

The corpus is whatever PDFs are on this machine — contracts, invoices,
papers, scans. They cannot be committed and should not be: they are
somebody's documents. But **a renderer only ever tested against fixtures is
a renderer only ever right about fixtures**, and every defect worth finding
in this stack came from real files: a Shift-JIS legal contract, a poster
that reported itself as having no text, an audit report with a space between
every pair of letters.

So what is committed is the **metric**, not the corpus, and the ledger
records which root produced each row. Two machines will not have the same
numbers and comparing them would mean nothing — the ratchet compares a
machine with itself.

`scripts/fleet-ci` runs on tailnet nodes with no local documents, so this
cannot be a fleet gate however much it resembles one.

## The witness is a second implementation

`pdf.core/extract-text` collects the strings between `BT` and `ET` with no
matrices and no state machine. It is useless for placing anything — which is
why `hanmen` exists — and that uselessness is what makes it a good witness:
it shares no code with the interpreter, so the two agreeing about *which
characters* are on a page is evidence.

Compared with all whitespace removed, on pages whose fonts are all simple
(the witness cannot read a composite font at all, so demanding agreement
there would be demanding `hanmen` be as wrong as the witness).

**Losing characters is reported. Inventing them fails the run, at a count of
one, however large the corpus.** The two are not symmetric: a renderer may
legitimately fail to decode a font, and may never add characters nobody
wrote. That asymmetry is the whole reason this exists — a coalescer once put
a space between every pair of letters and **6,289 characters nobody wrote**
went into 45 documents while every rate still looked healthy.

## A ratchet, not a threshold

There is no *correct* number of undrawn regions. What is knowable is whether
today's run has more than yesterday's over the same corpus. Rates are
compared, not counts, because a local corpus moves — a file syncs, a
placeholder evicts — and a gate that calls that a regression is a gate
people switch off within a week.

Metrics are counts of things, never scores. Every field is something a
person can go and look at: marks by kind, undrawn regions by reason, pages
where the two readers disagree. A score would hide which of those moved.

## What it found on its first run

31 documents measured of 40 seen:

- **5 of 6 comparable pages agree** with the witness; 1 page loses a
  character.
- **6 undrawn regions**, all `:font/no-tounicode`.
- **9 documents could not be measured at all**, in three distinct
  signatures — `For input string: "/M" under radix 16` (4),
  `zlib: stream ends before its Adler-32 trailer` (2), and
  `"/A" under radix 16` (2). Eight documents throwing one message is a
  decoder to write; eight throwing eight is a corpus. These are three.

Those are the next iteration's targets, and they came out of the loop rather
than out of anybody's judgement.

## Two bugs this loop had, both found by running it

**An empty run recorded a perfect baseline.** A rate over a zero denominator
returned 1.0, so the first run — with no documents — set a bar the first
real run was reported as failing. Rates are nil when nothing was measured
now, and a previous run with no documents is not a baseline.

**`unix:blocks` is not an attribute on this platform.** The first version
detected cloud placeholders by comparing allocated blocks against length and
found zero documents in a directory full of them. "The bytes are here" is
now defined as *reading is instant*, which is what the property actually is.

## Test

```sh
kbb -M:test
kbb -M:lint
```

9 tests / 19 assertions, over the ratchet — the only part with an opinion.
