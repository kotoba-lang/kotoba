# ADR-0139: a prompt becomes token ids without leaving Kotoba

Status: accepted
Date: 2026-09-02

## Context

`kernel/qwen35_infer.c` can run a forward pass and cannot be given a prompt.
Its input is a single BOS id — `contracts/qwen38-qwen35-runtime-v1.edn`
`:execution :input-token {:kind :bos :id 248044}` — and the K16 image contains
no tokenizer, in C or anywhere else. The three GGUF admission objects
(ADR-0145) answer "is this the file", "what does it say it is" and "where is
every tensor" without ever reading a token *string*; the two arrays whose
coordinates `aiueos-qwen35-gguf-kv-scan` records into workspace slots 100–120
have never been read at all.

So this is not a port. There is no C function here to replace, and the honest
statement of what changed is that the image gained a capability rather than
that a boundary moved.

The arrays are large: `tokenizer.ggml.tokens` holds 248,320 length-prefixed
strings and `tokenizer.ggml.merges` 247,587, about 4.7 MB of text inside the
model mapping. The obvious shape — materialise them into C structures at boot
— is what the K16 pure-native profile (ADR-0131) exists to refuse, and it is
also unnecessary.

## Decision

Three Kotoba kernel objects, over the GGUF arrays where they lie.

| object | export | what it does |
|---|---|---|
| `aiueos-qwen35-vocab-index-build` | `kotoba_aiueos_qwen35_vocab_index_build` | one pass over each array, building a string→id table and a (left id, right id)→rank table into a caller-owned workspace |
| `aiueos-qwen35-tokenize` | `kotoba_aiueos_qwen35_tokenize` | UTF-8 bytes → token ids |
| `aiueos-qwen35-detokenize` | `kotoba_aiueos_qwen35_detokenize` | token ids → UTF-8 bytes |

Three rather than one for the reason kotoba-native's allowlist already gives:
one exported symbol per object, no cross-object calls (ADR-0030). The split
follows the cost — the index is built once per boot and walks 4.7 MB of
strings; the other two then run per prompt and per emitted token against
tables that are already there.

**Nothing is copied.** The index holds a four-byte file offset per id and the
token strings stay in the model mapping, so an object that needs the bytes of
token 173,092 reads them where the GGUF put them. For the admitted artifact
the whole index is 9,382,016 bytes, and every size in it is derived from the
workspace header rather than transcribed from the contract — which is why the
same code serves a seven-token test fixture.

All three take the same four arguments (a model window and a workspace) and
return a **reason code with zero as the success value**. Neither tokenize nor
detokenize returns a count: the id count goes to workspace slot 64 and the
byte count to slot 92, so that a caller cannot read a refusal as "three
tokens".

### The pre-tokenizer follows the reference implementation, not the metadata

`tokenizer.ggml.pre` = `"qwen35"` names the qwen2 regex, whose number rule is
`\p{N}` — one digit. But llama.cpp does not run that regex through a regex
engine: `unicode_regex_split` matches the pattern string against a table of
presets and dispatches the qwen2 one to `unicode_regex_split_custom_llama3`, a
hand-written splitter whose number rule is `\p{N}{1,3}`. The reference
therefore consumes **up to three digits**, and `"2026"` is `["202" "6"]` rather
than four tokens.

This object follows the reference implementation, because that is what
produced the ids the model was trained against. The divergence between the two
readings is stated in the object's header, in
`contracts/qwen35-tokenize-v1.edn` `:pre-tokenizer`, and here.

### Four refusals llama.cpp does not make

| code | object | what llama.cpp does instead |
|---|---|---|
| `-16` | index build | no bound; this refuses a model window above 16 MiB because its cost is **linear in the window it is handed** and no finite fuel bound would hold for the 10.9 GiB mapping |
| `-21` | tokenize | throws out of `unicode_cpt_to_utf8` for a codepoint above U+10FFFF, uncaught, aborting the process |
| `-24` | tokenize | no bound; the merge loop is quadratic in one pre-tokenizer chunk, so a finite fuel bound needs one, and 512 byte-symbols is it |
| `-25` | tokenize | looks each **byte** of an unresolvable symbol up as a one-character string and **silently drops** the ones that are not tokens — for a byte-level vocabulary those are exactly the continuation bytes, so its fallback emits nothing and the text disappears from the token stream |
| `-33` | detokenize | substitutes the literal text `[UNK_BYTE_0x..]`, which then flows to whoever reads the output |

`-13`/`-14` are a different kind of refusal and the load-bearing ones. This
merge table is keyed by a **pair of token ids**; llama.cpp's `bpe_ranks` is
keyed by a **pair of strings**. The two agree exactly when every merge side is
itself a vocabulary token, because the string→id map is then injective on the
keys that matter. That is a property of the artifact and not of the format, so
the index build **checks** it rather than assuming it.

### The character classes are a declared subset, and the blind spot is measured

The pre-tokenizer needs three predicates — letter, number, whitespace — over
codepoints. llama.cpp generates its table from Python's `unicodedata` over all
of Unicode. This object carries a **122-range table over 24 declared blocks**,
generated from Java's `\p{L}` and `\p{N}` plus llama.cpp's explicit whitespace
set, searched by a balanced binary tree (seven comparisons, not 122).

Outside the declared blocks every codepoint is "other", which is the same
bucket as punctuation, symbols, marks and control characters — so the
divergence is confined to letters and digits of undeclared scripts, where it
changes where a chunk breaks and therefore which ids come out. The parity test
prints how many BMP codepoints that is (7,869 at the time of writing), so the
size of the blind spot is a number rather than a hope. The blocks cover Latin,
Greek, Cyrillic, Armenian, Hebrew, Arabic, Thai, the Latin/Greek extended
additions, super- and subscripts, number forms, enclosed alphanumerics, the
CJK radicals, Hiragana, Katakana, Bopomofo, Hangul, the enclosed and
compatibility CJK blocks, CJK Unified Ideographs and extensions A–F, the
compatibility ideographs, halfwidth and fullwidth forms, mathematical digits
and the emoji blocks.

### The workspace is the ABI

The kernel-object ABI admits five parameters and a probe step needs seven
values. Rather than packing four of them into one integer, the loop's own
frame lives in the caller-owned workspace, at header slots 96–124, where a
parity test can read it. The header also carries the coordinates
`aiueos-qwen35-gguf-kv-scan` recorded, so the two objects compose through
memory rather than through a call neither can make.

## Evidence

### The oracle, and what it is not

**The acceptance oracle for this family is llama.cpp, and it was not
available.** Measured 2026-09-02 on the workstation this ran on: no
`llama-tokenize` on PATH, no llama.cpp under Homebrew (`brew --prefix
llama.cpp` names a directory that does not exist), no `.gguf` over 10 MB
anywhere under `/Users` or `/Volumes`, and no ollama blobs. There are no
golden token ids from the reference implementation, for this or any other Qwen
vocabulary, and `test/aiueos/qwen35_tokenizer_parity_test.cljk` says so in its
first paragraph rather than presenting its own transcription as one.

The two portable tokenizers in this workspace were read and are **not** used:
`torch.tokenizer` and `kotodama.inference.tokenizer` both implement
SentencePiece-flavoured BPE — a `U+2581` word-boundary marker and `<0xHH>`
byte-fallback tokens — with no GPT-2 byte-to-unicode alphabet and no
pre-tokenizer split at all. Against a `gpt2` vocabulary they are a different
algorithm, not a second opinion.

What the parity test has instead, in descending order of independence:

1. **The pre-tokenizer against `java.util.regex`.** The byte state machine is
   checked against the qwen2 regex run through a real regex engine with real
   Unicode property support — a genuinely independent implementation of the
   hardest stage. 65 vectors, 0 disagreements.
2. **The character classes against `java.util.regex`**, at every codepoint
   where Java's answer changes inside the declared blocks, at the codepoint
   either side of it, and on a stride through each block.
3. **The merge loop and the id lookup against a transcription** of
   `llm_tokenizer_bpe` in Clojure. It shares no code with the objects, but it
   does share an author, so it catches a coding mistake and not a misreading.
4. **Round trip.** `detokenize(tokenize(s)) = s` for every vector, which needs
   no oracle at all and is the property a chat loop depends on.

### JVM-free vectors

Three contracts through `os/aiueos/scripts/verify-admissions.cljk`, in nbb,
with no JVM in the run:

```
CONTRACT :aiueos.qwen35-vocab-index-build/v1 vectors=16 memory=7  ms=12034
CONTRACT :aiueos.qwen35-tokenize/v1          vectors=19 memory=9  ms=48188
CONTRACT :aiueos.qwen35-detokenize/v1        vectors=16 memory=7  ms=19343
```

51 vectors, 23 memory assertions, every reachable reason code observed
(`:every-reachable-reason-observed true` in all three), and four codes
declared `:unreachable-by-construction` with the argument for each.

The runner gained one thing to make this possible: a **`:prelude`**, another
object's call run against the same page before each vector. Tokenize and
detokenize read tables the index build writes, and a kernel object cannot call
another, so without it the only way to give those two a workspace would have
been to transcribe the built tables into the contract as hex — a constant
where a derivation belongs. A vector opts out with `:prelude? false`, which is
how the "no index in the workspace" refusal is reached.

**Red and green, with the reason literal pinned.** `best-scan` was changed to
take the leftmost ranked pair instead of the lowest-ranked one — the one
semantic difference between a BPE merge loop and a left-to-right one — and the
vector written for exactly that went red:

```
FAILED: memory mismatch
  {:vector :a-leading-space-joins-the-word-and-the-lower-rank-wins,
   :region :ids, :expected [3 0 0 0 4 0 0 0], :actual [5 0 0 0 1 0 0 0]}
```

The object was restored byte-for-byte (md5 checked) and the contract is green
unchanged.

### Fuel

Measured through the KIR interpreter by bisection, at load average ~200:

| input | traps at | completes at | wall clock |
|---|---|---|---|
| 1 KiB of prose | 222,208 | **225,280** | 66 s / 85 s |
| 4 KiB of prose | — | 900,000 | 303 s |
| 32 KiB of prose | 2,097,152 | **8,600,000** | 598 s / 1,863 s |

~220 fuel per input byte, and it does not move with the length of the input:
the merge loop's quadratic term is in one CHUNK, and prose chunks are words.
The tier kotoba-native gives `aiueos-qwen35-tokenize` is 250,000,000, which is
29x the measured 32 KiB cost and ~4x the worst case the object's own bounds
allow (512 symbols per chunk, 98,304 symbols total when invalid UTF-8 triples
the byte count).

The committed test asserts the 1 KiB BRACKET and projects the rest, because
one 32 KiB run costs half an hour in this interpreter on this workstation at
load ~200 and that is not a per-suite price. The 4 KiB and 32 KiB figures above
were measured once, outside the suite.

**A probe that fails burns its entire budget before trapping**, which is why
the search is bisection from a hint and why the committed test asserts a
bracket rather than repeating it.

## What is NOT done

- **No llama.cpp golden vectors, and no run against the real 248,320-entry
  vocabulary.** Both need a GGUF this machine does not have. Every table size
  is derived from the workspace header rather than from the contract's counts,
  so the same code serves both — but that is a property of the source, stated
  as such, and not a measurement.
- **Nothing calls these objects.** They are linked into the K16 image
  (`build-uefi.sh`, under `# tokenizer:` comments, with the same per-object
  export/relocation/sha256 check every other Kotoba object gets) and no C
  references their symbols. Wiring the prompt path is a change to the C that
  would call them, and belongs with the Murakumo v3 prompt job.
- **The emitted x86-64 has never executed.** This workstation is aarch64.
  `kotoba.kir` models the same window checks the backends emit, so the oracle
  covers the bounds as well as the arithmetic, but it is not the machine.
- **`provenance.edn` records `:compiler {:sha nil :recipe :unrecorded}`** for
  all three. They were compiled by an amu worktree at `origin/main` with
  kotoba-native bumped to the merge that carries their symbol rows, which is
  not the revision `reproduce-kotoba-kernel-object.sh` pins. Same gap the TLS
  objects have (ADR-0132), same reason.
- **The class table is a snapshot of one JDK's Unicode.** The parity test
  admits a disagreement only where the running JDK calls the codepoint
  UNASSIGNED — measured 2026-09-02, JDK 26 and JDK 24 differ on 18 CJK
  extension codepoints — and fails in the other direction, which means "the
  table predates this JDK's Unicode; regenerate it".
- **`-24` refuses input llama.cpp would tokenize.** A chunk of more than 512
  byte-symbols with no space, digit or punctuation in it — about 170 unbroken
  kana or kanji — is refused rather than tokenized. The bound exists because
  the merge loop is quadratic in one chunk and a fuel bound must be finite.

## Addendum, 2026-09-02: the objects were rebuilt at newer pins

The three `.o` files first landed (aiueos#234, merge `58d910b`) were produced
by amu `25907a65` with kotoba-native at `eff87fcc` -- the merge that carries
their three `kernel-object-entries` rows. Two kotoba-native changes landed
after that and before this addendum:

- **#120 `279fbc3`**: a bounded store now answers with the STORED OPERAND. It
  previously left an undefined register on native.
- **MEMWIDTH**: `kernel-load/store-u{8,16,32,64}` at 512 / 4k / 16k / **64k**
  windows.

Neither changes what these objects mean. No code path here reads a store's
value -- every `kernel-store-*` sits in a non-final position of a `do`, and
that was checked one call site at a time rather than assumed -- and the objects
narrow with `kernel-subregion` to four bytes or one before every access, so a
wider window primitive is an opportunity and not a correction.

They were rebuilt anyway, at amu `ca869d79` with kotoba-native `c010fd9`,
because shipping an artifact from a compiler with a known register defect is
worse than rebuilding. **The bytes moved**: tokenize 27,904 -> 27,912,
detokenize 8,016 -> 8,024, index-build 10,904 -> 10,904 with a different
digest. The three contracts are unchanged and still green (51 vectors), which
is what says the rebuild changed the artifact and not the object.

The `let` multi-form body defect (kotoba-sema #29, kotoba-kir #67) is also
fixed upstream. It changes nothing here: every `let` and `fn` body in these
three objects was written as a single form while the defect was live, and they
are left that way rather than rewritten for a compiler feature that landed
after the code did.

### A conflict marker was on `main`, in the build script

Measured while rebuilding: `os/aiueos/scripts/build-uefi.sh` carried **three
unresolved conflict regions** and `os/aiueos/kernel/main.c` one, so `sh -n`
refused the build script and no image could be built from `main` at all.

They arrived at **`4afe0fb`** ("Merge #233: the Qwen3.5 forward pass gets its
first three Kotoba objects") and were on `main` from then; `3c541d5`,
`df7abf3` and `58d910b` each carry them forward, and `4515f3e` -- the commit
this ADR describes -- has none. Two streams had added object declarations at
the same three places and the merge was committed unresolved.

Fixed on `main` by aiueos#236 (`ff44e588`), keeping BOTH sides, because the
additions are unrelated: the Qwen3.5 forward-pass tranche and the
device-worker canonical object. That resolution is what this branch merged;
the sha256 pins for these three objects were re-applied on top of it rather
than on top of a second, competing resolution.

The cheap guard, run here after every merge from now on:

```
git grep -n -E '^(<<<<<<< |=======$|>>>>>>> )' -- .
sh -n os/aiueos/scripts/build-uefi.sh
```

Both are clean on this branch. The second one matters more than it looks: a
marker removal that eats a line break leaves `... \  "$next_object"`, a
backslash escaping a space rather than continuing a line, which `sh -n`
accepts and a linker does not.
