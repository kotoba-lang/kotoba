# pattern

**A bounded pattern matcher, in Kotoba.** A program is inert data; the machine
that runs it is a Kotoba module with an **empty `requiredCapabilities`**; the
regex string that produces the program is compiled on the host, before
anything runs.

## Why

Counted 2026-09-09 across kotoba-lang's browser stack — **308 regex literals in
213 files**, 200 unique:

```
+   148   [class] 122   (capture) 102   \s  93   *  84   ?  74
\d  56   |        44   anchor     43   (?i) 38   (?:) 34   .  30
{n} 12   {n,m}     4    lookahead   3   \w   1   backreference 0
```

Kotoba has no regex head, so every port so far hand-rolls a scanner out of
`string-code-point-at` and `string-substring` — twelve modules do it today.
That, not size, is what blocks the browser stack: `htmldom` is 2114 lines with
**no atoms, no protocols, three interop sites**, and `loop`/`recur` is
admitted. It has eleven regexes. `cssom` has 115 in one file.

So: one scanner, in a library, driven by data.

## The two halves

| | |
|---|---|
| `kotoba/pattern_vm.kotoba` | the machine, over a program carried as a **string**: ~4,680 instructions |
| `kotoba/pattern_core.kotoba` | the same machine over a program carried as a `:document`: 32 instructions, kept as the oracle |
| `kotoba/pattern_emit.kotoba` | the compiler that emits the **string** program, with no tree on the way |
| `kotoba/pattern_compile.kotoba` | the earlier compiler, emitting a `:document` program (32 instructions), kept as an oracle |
| `src/pattern/compile.cljk` | the same compiler, kept as the parity **oracle** |

Both compilers are run over every unique regex literal in the browser stack and
their programs compared instruction for instruction (`test/compile_parity.cljk`).
The `.cljc` is no longer the implementation — it is what the port is checked
against.

The Kotoba compiler is written in the pure S-expression core: calls are
`(app (ref f) x)`, control is `if` and `let`, and the sugar (`cond`, `and`,
`or`, threading) is not used. Per the grammar's own measurement `(app (ref f) n)`
and `(f n)` produce the same HIR, the same KIR and the same bytes, so this is a
surface convention — one spelling per meaning, which is what DefCID is computed
over.

```clojure
(require '[pattern.compile :as pc])
(pc/compile-pattern "\\d{3}-\\d{4}")
;; => {:code [[1 0 0] [1 0 0] [1 0 0] [0 45] [1 0 0] [1 0 0] [1 0 0] [1 0 0] [6 0]]
;;     :classes [[48 57]] :fold false}
```

A program is EDN, so it can be printed into a `.kotoba` module as a literal,
shipped in a resource, or read at runtime with `document-edn-read`. The machine
never parses anything, which is why it cannot be made to reject its input.

## Why a Pike VM and not backtracking

A backtracking matcher is easier to write and has no bound worth the name:
`(a+)+b` against a page of a's is the standard denial of service, and this
workspace runs matchers over input it did not write. This is a Thompson/Pike
machine — the run carries a **list of live threads** instead of a stack of
choices, deduplicated by program counter, so each input position is visited
once and time is O(input × program).

Measured, at `--fuel 20000`: with the dedup removed the machine dies of
`doc-vector-too-large` from **eight** a's; with it, twenty-four a's answer.
The parity corpus carries those inputs on purpose — without them it passed
either way, which is a test that was not testing.

## The subset, and what is refused

Literals, `.`, classes with ranges and negation, `\d \D \s \S \w \W`, groups
(`( )` and `(?: )` compile the same — the machine does not extract text yet),
alternation, the greedy quantifiers `* + ? {n} {n,m}`, `^` and `$`, and a
leading `(?i)`.

**Refused by name, not by silence** — `compile-pattern` throws: lookahead and
lookbehind (3 uses in the corpus), back references (0), non-greedy
quantifiers, and inline flags other than a leading `(?i)`. A pattern this
cannot express must not compile to one that means something else.

Two differences from JS RegExp are deliberate and are asserted in the parity
test rather than left to be discovered:

* `.` matches a newline here.
* the machine is leftmost-**longest**; JS is leftmost-first. For `a|ab`
  against `"ab"` the machine answers 2 and JS answers 1.

## The ceiling, and the two moves that lifted it

A `:document` is bounded: **depth 8, 256 nodes, 32 items per container**
(`osaho/src/kotoba/kir/value.cljc`). Everything else a guest can hold is
bounded near 32 as well -- typed map 31, typed set 32, record 32 fields,
heterogeneous vector 32 -- `[:vector T]` is a bounded TUPLE type, and no
backend has a sequence parameter type. **The one unbounded-ish value is a
`:string`, at 65536 bytes.**

So `kotoba/pattern_vm.kotoba` carries the program as a string:

```
header  "K" fold(1) nc(6 hex) nr(6 hex)          14 chars
code    nc x [ op(1) a(6) b(6) c(1) ]            14 chars each
ranges  nr x [ lo(6) hi(6) ]                     12 chars each
```

65536 / 14 is about **4,680 instructions, against 32**. Measured on the real
corpus: the IPv4 (88 instructions), the CSS length (82) and the 64-hex id (65)
now run; as documents they could not be handed to the matcher at all.

**Lifting one ceiling left the next one standing behind it.** The thread list
was a document too, and 32 simultaneously-live threads is real: the
257-instruction email pattern from `kiyaku` answered `doc-vector-too-large` on
`"a@b.co"`. The thread set is now one string as well -- a bitset of visited
program counters followed by the live list:

```
[ bits: ceil(nc/4) hex chars ][ pcs: 6 hex chars each ]
```

The bitset is not taste. With membership as a linear scan the same pattern
took **20.4 seconds** for one `match?` (correct, but the dedup that keeps a
Pike VM linear was itself quadratic in function entries, and fuel is charged
per entry). With the bit test it is **3.5 seconds**; the 88- and
65-instruction patterns are unchanged at 80 and 127 ms.

### What the string form cost to write

Three backend facts, each measured the hard way:

* **`bit-and` / `bit-or` are refused by the JS backend** -- "unsupported KIR
  operation" at the `:kotoba-script` phase, while `string-from-i64` compiles
  there. The bit test is arithmetic: for a hex digit `d` and a bit value `v`,
  the bit is set exactly when `(quot d v)` is odd.
* **`i64-shift-left` takes a LITERAL count** in [0,63], so a computed shift is
  a four-way branch.
* **`mod` is not a builtin** here.

## No tree, and no ceiling

`pattern_compile` parses to a `:document` AST and emits a `:document` program,
and 43 of the 200 corpus patterns exceed one of those bounds -- 32 of them by
DEPTH, because a tree is exactly the shape a document cannot hold.

`kotoba/pattern_emit.kotoba` builds no tree. Parse and emit are fused: each
function answers the code it emitted AS THE STRING plus the source index it
stopped at, and a quantifier does not need its operand as a value -- it needs
it EMITTED AGAIN at another program counter, so it remembers the operand's
SOURCE SPAN and re-runs the emitter over it. `a{3}` compiles the same three
characters three times, which costs scanning and buys the absence of the tree.

Measured over the same corpus, comparing the two compilers **through the
machine** rather than by bytes (the `.cljc` shares a class table between
identical classes and this one appends ranges where it meets them, so two
correct programs differ in bytes; what has to agree is what they ACCEPT):

| | |
|---|---|
| agreed through `pattern-vm` | **168** |
| both refused | 16 |
| over a document bound | **0** |
| disagreements | **0** |

Two bugs surfaced in one probe run while this landed, and both are the kind
that reads as a plausible answer: re-emitting an operand's span looked at the
character AT the span's end -- the quantifier itself -- and recursed forever
(`a*`, `a+`, `a?`, `a{1,3}`, `a{2,}` all answered "Maximum call stack size
exceeded" while a bare `a` was fine); and `{n}` took its hi from a field that
the answer-builder fills with a STRING, which the i64 reader reads as 0, so
`a{3}` was `a{3,0}` and refused itself.

## The bug the corpus was hiding

`^(px|em)$` answered **false** for `"px"`. So did `^[-+]?[0-9]+$` for `"12"`.
`^a$` for `"a"` was right, which is why it survived: the anchor is reached
before any step.

The `eol` flag handed to a step was the one for the position the threads LEFT,
not the one they land on, so every thread that stepped onto a `$` was dropped.
Both machines had it. **216 parity checks agreed with JavaScript without
touching it, because the corpus contained no pattern ending in `$`.** It has
four now, and both suites are green at 252 and 270 checks.

## The 200-pattern compiler corpus

Measured over the 200-pattern corpus, with the AST and program as documents:

| | |
|---|---|
| identical programs | **140** |
| both compilers refused | **17** |
| over a document bound | **43** (32 depth, 10 vector size, 1 node count) |
| semantic disagreements | **0** |

Every pattern that *fits* compiles to the identical program. What is left is a
value-shape ceiling, not a difference of meaning — and it is a real ceiling for
this library's purpose: **a program of more than 32 instructions cannot be a
guest document at all.**

There is no large homogeneous sequence in the guest to escape into —
`[:vector T]` is a heterogeneous TUPLE type, bounded, and no backend has a
sequence parameter type. The way out is to carry the program as a **`:string`**
(the value limit is 65536 bytes) and index into it, which lifts the ceiling by
about 300× and is the next slice. `test/compile_parity.cljk` holds 43 as a
RATCHET: it fails if a semantic disagreement appears and it fails if that
number moves either way.

## How much of the real corpus this admits

Measured 2026-09-09 by compiling every unique regex literal in `htmldom`,
`cssom`, `browser`, `html`, `css` and `kiyaku` through `compile-pattern`:

| | |
|---|---|
| unique literals scraped | 200 |
| **admitted** | **183** |
| refused: inline flags `(?m)` `(?s)` `(?is)` | 5 |
| refused: non-greedy `.*?` | 3 |
| refused: lookahead / lookbehind | 2 |
| not patterns at all (multi-line scrape artifacts) | 7 |

So 183 of the 193 real ones, and the ten that are left name themselves:
`(?s)` and `(?m)` first (5), then non-greedy (3), then lookahead (2). None of
them is a reason to hand-roll another scanner.

## Fuel

The default per-instance budget is **512** — a plain countdown returns at
n=510 — and a matcher spends fuel per function entry, so **the default cannot
finish a six-character search**. Measured: `--fuel 5000` runs a 40-character
search of `[0-9]+`. The knob is the host's, which is the point of it:

```bash
kotoba -M compile "$PWD/kotoba/pattern_core.kotoba" --target js --fuel 200000 --output pattern.mjs
```

## Tests

```bash
# the string-program machine against the host's own RegExp: 270 checks,
# including four real patterns whose programs are far past 32 instructions
kbb --backend sci --classpath src test/vm_parity.cljk

# the document-program machine, same corpus minus the big ones: 252 checks
kbb --backend sci --classpath src test/pattern_parity.cljk

# the string emitter's own tests, through the artifact (-M test's fuel is fixed)
kbb --backend sci test/emit_selfcheck.cljk

# the two compilers compared THROUGH the machine, over the browser-stack corpus
kbb --backend sci --classpath "src:$HOME/github/com-junkawasaki/orgs/kotoba-lang/text/src" \
    test/emit_parity.cljk

# the document-program compiler against the .cljc oracle, by bytes
kbb --backend sci --classpath src test/compile_parity.cljk

# the compiler's own tests. 8/8 on :jvm-kir; five trap on :js and :wasm under
# the runner's fixed fuel, which --fuel does not change (measured)
kotoba -M test "$PWD/kotoba/pattern_compile.kotoba"

# the upstream limitation this library works around, so nobody has to remember
kbb --backend sci test/entry_probe.cljk
```

`kotoba -M test` is **not** used here, and that is the one thing this repo
cannot do: a `main` that calls the machine — and any `test-*` the runner would
evaluate — makes the compiler refuse the module at the `:value` phase with
`"value is not a boolean"`, while the same module compiles for the JS backend
and answers correctly. `test/entry_probe.cljk` rebuilds that failing form from
the current source and **goes red the day the compiler stops refusing it**.

## Not done

No captures. 102 of the 308 literals use a group, and many of those are
grouping rather than capturing; the ones that need the matched text are the
next slice, and the instruction set reserves opcode 5 (`save`) for it. Until
then `search` answers *where*, not *what*.

The compiler is host-side. Moving it into Kotoba would let a guest accept a
pattern at runtime; nothing needs that yet.
