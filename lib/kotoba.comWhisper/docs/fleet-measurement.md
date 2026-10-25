# STT on the fleet — measured 2026-08-15

`whisper.main` was a clean-room API surface with no engine. This records the
first measurement of a real one, so the numbers in it are values somebody
observed rather than values somebody expected.

## Setup

- **Node**: `levi` (Apple M4, 16 GB, macOS 26.2), Metal backend
- **Engine**: `brew install whisper-cpp` → `whisper-cli`
- **Models**: `ggml-large-v3-turbo` (1.6 GB), `ggml-small` (465 MB), in `~/.whisper/models/`
- **Invocation**: `whisper-cli -m <model> -f <wav> -l ja -nt -np -bs 5 -t 4`

## The audio went through the degradation a real call goes through

Measuring a studio-quality file would have produced a number that does not hold
on a telephone. Each utterance was synthesized at **carrier format** and then
converted to **engine format**, which is the path the media bridge will run:

```bash
say -v <voice> -o u.wav --data-format=ulaw@8000 --channels=1 "<utterance>"   # 8 kHz μ-law, what the carrier delivers
afconvert -f WAVE -d LEI16@16000 -c 1 u.wav s.wav                            # 16 kHz PCM, what whisper takes
```

The 8 kHz stage discards everything above 4 kHz and no upsampling returns it, so
the bandwidth loss is real.

**⚠ The acoustic conditions are not.** The corpus is macOS `say` output: no room,
no line noise, no accent, no hesitation, no two people talking. **These numbers
are an upper bound**, and the first real call is the measurement that counts.

## Results — 8 Japanese reservation utterances

| model | latency (steady state) | correct | notes |
|---|---|---|---|
| **large-v3-turbo** | **1.40–1.52 s** | **8 / 8** | first run 2.85 s (model load) |
| small | 0.41–0.61 s | 7 / 8 | 「六名で」→「むつなで」 |

Differences from the reference text were otherwise orthographic only —
`四人→4人`, `七時→7時`, `六時半→6時半`, plus punctuation. That direction is
**helpful**: the extractor downstream wants digits.

The hardest case came through exactly on both models:

```
expect  電話番号は090-1234-5678です
turbo   電話番号は090-1234-5678です
small   電話番号は090-1234-5678です
```

## Choice: large-v3-turbo

`small` is three times faster and loses the **party size** — the field that
decides which table. A wrong party size arrives looking exactly as confident as
a right one, and 1 second of latency is much cheaper than seating six people at
a table for two.

Latency budget for one turn, as measured:

| | |
|---|---|
| STT (turbo) | ~1.45 s |
| dialog LLM | **not measured** — `api.murakumo.cloud` needs a key this session did not issue |
| TTS (`say -v Kyoko`) | ~1.14 s |

That is **≥2.6 s of silence** before the caller hears anything, and real
receptionists are well under a second. Streaming — starting TTS on the first
clause, running STT on partials — is not implemented and is the next latency
work. The number is recorded rather than smoothed over.

## The failure that taught `parse` its shape

Midway through, `ggml-small.bin` was benchmarked while still downloading
(279 MB of 465 MB). `whisper-cli` **aborted with a stack trace and exited 0**,
printing nothing to stdout. The bench script discarded stderr, so:

```
s1.wav  0.16   (empty)
s2.wav  0.14   (empty)
...eight of them
```

Eight utterances came back as eight quiet callers, fast, with exit 0. In a
telephone dialog an empty transcript means *the caller said nothing*, and the
receptionist would have acted on it.

`whisper.engine/parse` had the same defect: it treated exit 0 + blank output as
silence. It now requires silence to be **stated** by the engine
(`[BLANK_AUDIO]`), reports bare-empty output as
`:engine-produced-no-transcript`, and carries stderr into `:whisper/detail`
instead of discarding it. `engine_test.cljc` contains the observed shape —
exit 0, empty stdout, `libsystem_c` on stderr — as a test.
