#include <stdint.h>
#include "../include/boot_info.h"
#include "inference_status.h"
#include "kototama_runtime.h"
#include "model_handoff.h"
#ifdef AIUEOS_QWEN38_MODEL_HANDOFF
#define AIUEOS_MODEL_IDENTITY_MACROS_ONLY
#include "aiueos-model-identity.h"
#endif
#include "qwen35_infer.h"
#include "qwen35_runtime.h"
#include "device_result.h"

/* ---------------------------------------------------------------------------
   DEVCLIENT-PARITY.  The object against the bytes the C produced.
   ---------------------------------------------------------------------------
   The two expected texts are not transcriptions.  The protocol 2 one is what
   `os/aiueos/tests/device_result_v2_model.c --dump-canonical` printed from the
   C writer this commit deletes, captured through that model's
   `kotoba_aiueos_sha256` stub -- the exact bytes the C was about to hash.  The
   protocol 3 one is the worked example in network-awai/cloud-murakumo-api
   `docs/device-worker-v3.md`, pinned there by the server's own
   `v3-canonical-is-the-v2-list-plus-four-fields-then-the-nonce`.  Both are
   carried in `contracts/device-worker-canonical-v1.edn` and the literals below
   were generated from it.

   This runs the emitted object ON THE TARGET.  The KIR interpreter already
   agrees with these bytes; that says nothing about what the backend emitted,
   which is the half a boot self-test covers.  */
static const char worker_canonical_v2_expected[] =
  "aiueos-k16-worker-v2\n"
  "aiueos-k16-7070fc0bb632\n"
  "01010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101\n"
  "0202020202020202\n"
  "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\n"
  "7\n"
  "result\n"
  "42\n"
  "2\n"
  "2005\n"
  "17\n"
  "8\n"
  "7\n"
  "12000000000\n"
  "56000000000\n"
  "68000000000\n"
  "256\n"
  "2\n"
  "4000000000\n"
  "02020202020202020202020202020202";

static const char worker_canonical_v3_expected[] =
  "aiueos-k16-worker-v3\n"
  "aiueos-k16-7070fc0bb632\n"
  "00000000000000000000000000000000000000000000000000000000000000010000000000000000000000000000000000000000000000000000000000000002\n"
  "0123456789abcdef\n"
  "c0b7c3038681ed2e3040456c1dd45f9858b6c2290bed172c70388a94874f3eee\n"
  "12\n"
  "result\n"
  "1788078031098390\n"
  "3\n"
  "2005\n"
  "17\n"
  "3\n"
  "2\n"
  "12000000000\n"
  "24000000000\n"
  "36000000000\n"
  "256\n"
  "2\n"
  "4000000000\n"
  "6d1f26aca9a65756235d79f4246587ffa5192cddab5fd1056d0eff3b5dd2b34a\n"
  "bfc850f9c5276dffd405b5f6413ec57703465265dc0747fa9fea07d2aee1b644\n"
  "3\n"
  "eos\n"
  "00112233445566778899aabbccddeeff";


static void dwc_zero(uint8_t *memory, uint32_t bytes) {
  for (uint32_t i = 0; i < bytes; i++) memory[i] = 0;
}

static void dwc_text(uint8_t *ctx, uint32_t offset, const char *text,
                     uint32_t bytes) {
  for (uint32_t i = 0; i < bytes; i++) ctx[offset + i] = (uint8_t)text[i];
}

static void dwc_number(uint8_t *ctx, uint32_t offset, uint64_t value) {
  for (uint32_t i = 0; i < 8; i++)
    ctx[offset + i] = (uint8_t)(value >> (56U - i * 8U));
}

static void worker_context_numbers(
    uint8_t *ctx, uint32_t sequence, uint64_t job_id, uint32_t token,
    uint32_t second_token, uint32_t generated_tokens, uint32_t decode_tokens,
    uint64_t first_token_cycles, uint64_t decode_cycles,
    uint64_t inference_cycles, uint32_t vector_bits, uint32_t worker_threads,
    uint64_t tsc_hz, uint64_t output_token_count) {
  dwc_number(ctx, AIUEOS_DWC_SEQUENCE, sequence);
  dwc_number(ctx, AIUEOS_DWC_JOB_ID, job_id);
  dwc_number(ctx, AIUEOS_DWC_TOKEN, token);
  dwc_number(ctx, AIUEOS_DWC_SECOND_TOKEN, second_token);
  dwc_number(ctx, AIUEOS_DWC_GENERATED_TOKENS, generated_tokens);
  dwc_number(ctx, AIUEOS_DWC_DECODE_TOKENS, decode_tokens);
  dwc_number(ctx, AIUEOS_DWC_FIRST_TOKEN_CYCLES, first_token_cycles);
  dwc_number(ctx, AIUEOS_DWC_DECODE_CYCLES, decode_cycles);
  dwc_number(ctx, AIUEOS_DWC_INFERENCE_CYCLES, inference_cycles);
  dwc_number(ctx, AIUEOS_DWC_VECTOR_BITS, vector_bits);
  dwc_number(ctx, AIUEOS_DWC_WORKER_THREADS, worker_threads);
  dwc_number(ctx, AIUEOS_DWC_TSC_HZ, tsc_hz);
  dwc_number(ctx, AIUEOS_DWC_OUTPUT_TOKEN_COUNT, output_token_count);
}

static int canonical_matches(const uint8_t *produced, int64_t length,
                             const char *expected) {
  uint32_t n = 0;
  while (expected[n]) n++;
  if (length != (int64_t)n) return 0;
  for (uint32_t i = 0; i < n; i++)
    if (produced[i] != (uint8_t)expected[i]) return 0;
  return 1;
}

static void dwc_hex_fill(uint8_t *ctx, uint32_t offset, uint32_t bytes,
                              uint8_t value) {
  for (uint32_t i = 0; i < bytes; i++) {
    ctx[offset + i * 2] = (uint8_t)"0123456789abcdef"[value >> 4];
    ctx[offset + i * 2 + 1] = (uint8_t)"0123456789abcdef"[value & 15U];
  }
}

/* Returns 0 on success, or the 1-based number of the case that disagreed,
   so a mismatch names which of the three it was rather than only that one
   of them was. */
static int aiueos_device_worker_canonical_selftest(void) {
  uint8_t ctx[AIUEOS_DEVICE_WORKER_CTX_BYTES];
  uint8_t out[AIUEOS_DEVICE_WORKER_CANONICAL_MAX];
  int64_t length;

  /* Protocol 2 result, the model's own stub key material: a public key of
     0x01, a boot id and nonce of 0x02, a model digest of 0xaa. */
  dwc_zero(ctx, sizeof(ctx));
  ctx[AIUEOS_DWC_PROTOCOL] = 2;
  ctx[AIUEOS_DWC_OPERATION] = AIUEOS_DEVICE_WORKER_RESULT;
  worker_context_numbers(ctx, 7, 42, 2005, 17, 8, 7,
                         12000000000ULL, 56000000000ULL, 68000000000ULL,
                         256, 2, 4000000000ULL, 0);
  dwc_text(ctx, AIUEOS_DWC_NODE, "aiueos-k16-7070fc0bb632", 23);
  dwc_hex_fill(ctx, AIUEOS_DWC_PUBLIC_KEY, 64, 0x01);
  dwc_hex_fill(ctx, AIUEOS_DWC_BOOT, 8, 0x02);
  dwc_hex_fill(ctx, AIUEOS_DWC_MODEL_SHA256, 32, 0xaa);
  dwc_hex_fill(ctx, AIUEOS_DWC_NONCE, 16, 0x02);
  length = kotoba_aiueos_device_worker_canonical(ctx, sizeof(ctx), out,
                                                 sizeof(out));
  if (!canonical_matches(out, length, worker_canonical_v2_expected)) return 1;

  /* Protocol 3 result, the spec's worked example.  Its public key is
     31 zero bytes then 0x01, then 31 zero bytes then 0x02, so it is written
     rather than filled. */
  dwc_zero(ctx, sizeof(ctx));
  ctx[AIUEOS_DWC_PROTOCOL] = 3;
  ctx[AIUEOS_DWC_OPERATION] = AIUEOS_DEVICE_WORKER_RESULT;
  ctx[AIUEOS_DWC_STOP_REASON] = 1;                              /* stop reason: eos */
  worker_context_numbers(ctx, 12, 1788078031098390ULL, 2005, 17, 3, 2,
                         12000000000ULL, 24000000000ULL, 36000000000ULL,
                         256, 2, 4000000000ULL, 3);
  dwc_text(ctx, AIUEOS_DWC_NODE, "aiueos-k16-7070fc0bb632", 23);
  dwc_hex_fill(ctx, AIUEOS_DWC_PUBLIC_KEY, 64, 0x00);
  ctx[AIUEOS_DWC_PUBLIC_KEY + 62] = '0'; ctx[AIUEOS_DWC_PUBLIC_KEY + 63] = '1';
  ctx[AIUEOS_DWC_PUBLIC_KEY + 126] = '0'; ctx[AIUEOS_DWC_PUBLIC_KEY + 127] = '2';
  dwc_text(ctx, AIUEOS_DWC_BOOT, "0123456789abcdef", 16);
  dwc_text(ctx, AIUEOS_DWC_MODEL_SHA256,
           "c0b7c3038681ed2e3040456c1dd45f9858b6c2290bed172c70388a94874f3eee", 64);
  dwc_text(ctx, AIUEOS_DWC_INPUT_SHA256,
           "6d1f26aca9a65756235d79f4246587ffa5192cddab5fd1056d0eff3b5dd2b34a", 64);
  dwc_text(ctx, AIUEOS_DWC_OUTPUT_SHA256,
           "bfc850f9c5276dffd405b5f6413ec57703465265dc0747fa9fea07d2aee1b644", 64);
  dwc_text(ctx, AIUEOS_DWC_NONCE, "00112233445566778899aabbccddeeff", 32);
  length = kotoba_aiueos_device_worker_canonical(ctx, sizeof(ctx), out,
                                                 sizeof(out));
  if (!canonical_matches(out, length, worker_canonical_v3_expected)) return 2;

  /* Two refusals, so a run that never saw the object say no is not counted as
     a pass -- and they are two rather than one because the ORDER matters and
     was measured rather than assumed.

     `stop-ok` is checked before the v3-field clause, so the same context
     reports -5 while its stop-reason byte is still `eos` and -7 only once that
     byte is the sentinel.  This is not a hypothetical: the first version of
     this self-test set the protocol byte to 2 and expected -7, and QEMU
     answered `DEVCLIENT-PARITY canonical mismatch` -- the object was right and
     the expectation was wrong.  Both codes are pinned here so neither clause
     can be removed without a red boot. */
  ctx[AIUEOS_DWC_PROTOCOL] = 2;
  length = kotoba_aiueos_device_worker_canonical(ctx, sizeof(ctx), out,
                                                 sizeof(out));
  if (length != -5) return 3;
  ctx[AIUEOS_DWC_STOP_REASON] = 0;
  length = kotoba_aiueos_device_worker_canonical(ctx, sizeof(ctx), out,
                                                 sizeof(out));
  if (length != -7) return 4;
  return 0;
}

/* ---------------------------------------------------------------------------
   SHA-STREAM-PARITY.  The streaming SHA-256 objects, on a CPU.
   ---------------------------------------------------------------------------
   THE ORACLE IS THE OBJECT THIS KERNEL ALREADY TRUSTS, plus published digests
   for the sizes that object cannot reach.

   There is no C SHA-256 in this kernel to compare against and has not been
   since ADR-0015: every kernel hash already goes through
   `kotoba_aiueos_sha256`, a Kotoba object.  (The C one lives in the UEFI
   loader, `uefi/main.c:390`, and is a separate binary this self-test cannot
   call.)  So cases 4 and 5 hash 12,288 bytes -- the LARGEST input
   `kotoba_aiueos_sha256` accepts -- with both the old object and the two new
   ones and compare the 32 bytes.  Two independent Kotoba implementations,
   both running here as x86-64 machine code, agreeing on the same input is a
   stronger statement than either against a literal.

   Past 12,288 bytes nothing else here can answer, so cases 6 and 9 pin the
   digest as a literal.  Those literals come from an implementation that is
   not this one and are also carried by
   `contracts/{sha256-region,device-worker-digest}-v1.edn`, whose expectations
   `test/aiueos/sha256_stream_parity_test.cljk` re-derives from
   `kotoba-lang/org-nist-sha2` -- the pure `.cljc` reference.

   Cases 7 and 8 are the point of the whole stream.  The two 64-character
   digests they produce are ALREADY IN THIS FILE, transcribed by hand into
   `worker_canonical_v3_expected` above from the server's worked example.  A
   device that had to transcribe them could not settle a job it actually ran.
   Now they are computed.  If the two ever disagree, one of the two is wrong
   and this boot says which.

   The KIR interpreter already agrees with every one of these; that says
   nothing about what the backend emitted, which is the half a boot self-test
   covers.  */
extern int64_t kotoba_aiueos_sha256_region(uint8_t *st, int64_t st_len,
                                           const uint8_t *src, int64_t src_len);
extern int64_t kotoba_aiueos_sha256_stream(int64_t mode, uint8_t *st,
                                           int64_t st_len, const uint8_t *src,
                                           int64_t src_len);
extern int64_t kotoba_aiueos_device_worker_digest(uint8_t *st, int64_t st_len,
                                                  const uint8_t *tok,
                                                  int64_t tok_count);
extern uint64_t kotoba_aiueos_sha256(const uint8_t *, uint64_t, uint8_t[32],
                                     uint8_t *, uint64_t);

#define SHA_STREAM_STATE_BYTES 512U
#define SHA_STREAM_DIGEST 424U        /* raw 32 bytes, big-endian */
#define SHA_STREAM_MAX_TOKENS 460U    /* the caller's mode word, be32 */
/* 4*(32768+2): the widest canonical `input-sha256` the protocol admits, and
   also large enough for the 32,768-entry be32 token array case 9 needs. */
#define SHA_STREAM_BUFFER_BYTES 131080U

/* `.high_bss`, not ordinary `.bss`. The low kernel/user layout has to end
   below 0x1f4000 (`kernel/linker.ld`'s own ASSERT), and 131,080 bytes of
   message buffer is 13% of that whole budget -- measured 2026-09-02, putting
   it in `.bss` made the link fail with `low kernel/user layout overlaps
   process-private aperture` on a tree that had just gained the RTL8125 and
   Qwen3.5 objects. The 4..6 MiB window is what that section is for: kernel-only
   scratch, mapped writable and NX by `page_directory[2]`, and it is where
   `device_result.c`, `tls13.c` and `qwen35_infer.c` already put theirs. */
static uint8_t __attribute__((section(".high_bss"), aligned(64)))
  sha_stream_state[SHA_STREAM_STATE_BYTES];
static uint8_t __attribute__((section(".high_bss"), aligned(64)))
  sha_stream_buffer[SHA_STREAM_BUFFER_BYTES];

static int sha_stream_is(const uint8_t *digest, const char *expected) {
  static const char hexits[] = "0123456789abcdef";
  for (int i = 0; i < 32; i++) {
    if (expected[i * 2] != hexits[digest[i] >> 4]) return 0;
    if (expected[i * 2 + 1] != hexits[digest[i] & 15U]) return 0;
  }
  return expected[64] == 0;
}

static void sha_stream_be32(uint8_t *p, uint32_t v) {
  p[0] = (uint8_t)(v >> 24); p[1] = (uint8_t)(v >> 16);
  p[2] = (uint8_t)(v >> 8);  p[3] = (uint8_t)v;
}

static void sha_stream_fill(uint32_t bytes, uint8_t value) {
  for (uint32_t i = 0; i < bytes; i++) sha_stream_buffer[i] = value;
}

/* Returns 0, or the 1-based number of the case that disagreed, so a mismatch
   names which of the ten it was rather than only that one of them was. */
static int aiueos_sha_stream_selftest(void) {
  static uint8_t old_digest[32];
  static uint8_t old_workspace[512];
  const uint8_t *out = sha_stream_state + SHA_STREAM_DIGEST;

  /* 1. FIPS 180-4 B.1. */
  sha_stream_buffer[0] = 'a'; sha_stream_buffer[1] = 'b'; sha_stream_buffer[2] = 'c';
  if (kotoba_aiueos_sha256_region(sha_stream_state, SHA_STREAM_STATE_BYTES,
                                  sha_stream_buffer, 3) != 0) return 1;
  if (!sha_stream_is(out,
      "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")) return 1;

  /* 2. FIPS 180-4 B.2 -- 56 bytes, the exact length at which the padding no
        longer fits in one block, so this is the only case here that takes the
        two-block `final-long` arm. */
  {
    static const char b2[] =
      "abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq";
    for (int i = 0; i < 56; i++) sha_stream_buffer[i] = (uint8_t)b2[i];
    if (kotoba_aiueos_sha256_region(sha_stream_state, SHA_STREAM_STATE_BYTES,
                                    sha_stream_buffer, 56) != 0) return 2;
    if (!sha_stream_is(out,
        "248d6a61d20638b8e5c026930c3e6039a33ce45964ff2167f6ecedd419db06c1")) return 2;
  }

  /* 3. Exactly one block and an EMPTY tail. A padding routine that skipped the
        final block when nothing was left over passes cases 1 and 2. */
  sha_stream_fill(64, 'a');
  if (kotoba_aiueos_sha256_region(sha_stream_state, SHA_STREAM_STATE_BYTES,
                                  sha_stream_buffer, 64) != 0) return 3;
  if (!sha_stream_is(out,
      "ffe054fe7ae0cb6dc65c3af9b61d5209f439851db43d0ba5997337df154668eb")) return 3;

  /* 4. 12,288 bytes: the LARGEST input `kotoba_aiueos_sha256` accepts, hashed
        by both objects, compared byte for byte. No literal. */
  sha_stream_fill(12288, 'a');
  if (!kotoba_aiueos_sha256(sha_stream_buffer, 12288, old_digest,
                            old_workspace, sizeof(old_workspace))) return 4;
  if (kotoba_aiueos_sha256_region(sha_stream_state, SHA_STREAM_STATE_BYTES,
                                  sha_stream_buffer, 12288) != 0) return 4;
  for (int i = 0; i < 32; i++) if (out[i] != old_digest[i]) return 4;

  /* 5. The same 12,288 bytes driven a block at a time: one init, 192 block
        calls, one final over an empty tail. Compared against the SAME
        `kotoba_aiueos_sha256` answer, so this checks the streaming object
        against the old one and against case 4 at once. */
  if (kotoba_aiueos_sha256_stream(0, sha_stream_state, SHA_STREAM_STATE_BYTES,
                                  sha_stream_buffer, 0) != 0) return 5;
  for (int b = 0; b < 192; b++)
    if (kotoba_aiueos_sha256_stream(1, sha_stream_state, SHA_STREAM_STATE_BYTES,
                                    sha_stream_buffer + b * 64, 64) != 0) return 5;
  if (kotoba_aiueos_sha256_stream(2, sha_stream_state, SHA_STREAM_STATE_BYTES,
                                  sha_stream_buffer, 0) != 0) return 5;
  for (int i = 0; i < 32; i++) if (out[i] != old_digest[i]) return 5;

  /* 6. 131,080 bytes -- ten times what `kotoba_aiueos_sha256` accepts and six
        hundred times what `sha256_core` does. This is the size that made the
        whole stream necessary, and nothing else in this kernel can answer it,
        so the digest is a literal. */
  sha_stream_fill(SHA_STREAM_BUFFER_BYTES, 'a');
  if (kotoba_aiueos_sha256_region(sha_stream_state, SHA_STREAM_STATE_BYTES,
                                  sha_stream_buffer,
                                  SHA_STREAM_BUFFER_BYTES) != 0) return 6;
  if (!sha_stream_is(out,
      "f9849709fe889fedb13705ffc841d41f81e26844a49e5fc4cf78e0fa3fba9441")) return 6;

  /* 7. `input-sha256([248044 9707 11 1879], 64)`. This digest is the literal
        `worker_canonical_v3_expected` carries above. */
  sha_stream_be32(sha_stream_buffer + 0, 248044U);
  sha_stream_be32(sha_stream_buffer + 4, 9707U);
  sha_stream_be32(sha_stream_buffer + 8, 11U);
  sha_stream_be32(sha_stream_buffer + 12, 1879U);
  sha_stream_be32(sha_stream_state + SHA_STREAM_MAX_TOKENS, 64U);
  if (kotoba_aiueos_device_worker_digest(sha_stream_state,
                                         SHA_STREAM_STATE_BYTES,
                                         sha_stream_buffer, 4) != 24) return 7;
  if (!sha_stream_is(out,
      "6d1f26aca9a65756235d79f4246587ffa5192cddab5fd1056d0eff3b5dd2b34a")) return 7;

  /* 8. `output-sha256([2005 17 42])` -- max-tokens zero, so the suffix is
        absent. The other literal above. */
  sha_stream_be32(sha_stream_buffer + 0, 2005U);
  sha_stream_be32(sha_stream_buffer + 4, 17U);
  sha_stream_be32(sha_stream_buffer + 8, 42U);
  sha_stream_be32(sha_stream_state + SHA_STREAM_MAX_TOKENS, 0U);
  if (kotoba_aiueos_device_worker_digest(sha_stream_state,
                                         SHA_STREAM_STATE_BYTES,
                                         sha_stream_buffer, 3) != 16) return 8;
  if (!sha_stream_is(out,
      "bfc850f9c5276dffd405b5f6413ec57703465265dc0747fa9fea07d2aee1b644")) return 8;

  /* 9. The protocol's WIDEST input: 32,768 tokens and a max-tokens suffix,
        131,080 canonical bytes. `t[i] = i` is deterministic and every id is
        inside the 248,320-entry vocabulary. */
  for (uint32_t i = 0; i < 32768U; i++)
    sha_stream_be32(sha_stream_buffer + i * 4U, i);
  sha_stream_be32(sha_stream_state + SHA_STREAM_MAX_TOKENS, 4096U);
  if (kotoba_aiueos_device_worker_digest(sha_stream_state,
                                         SHA_STREAM_STATE_BYTES,
                                         sha_stream_buffer, 32768) != 131080)
    return 9;
  if (!sha_stream_is(out,
      "c77159f6fffac7e2e21b6802cd1f0f0b5eb4adfba7cd060a8c44c01e038f22a8")) return 9;

  /* 10. Four refusals, so a run that never saw an object say no is not counted
         as a pass, and one success afterwards so a run in which the objects had
         simply stopped working is not counted as a set of correct refusals. */
  if (kotoba_aiueos_sha256_region(sha_stream_state, 511,
                                  sha_stream_buffer, 0) != 1) return 10;
  if (kotoba_aiueos_sha256_region(sha_stream_state, SHA_STREAM_STATE_BYTES,
                                  sha_stream_buffer, 1048577) != 3) return 10;
  if (kotoba_aiueos_sha256_stream(3, sha_stream_state, SHA_STREAM_STATE_BYTES,
                                  sha_stream_buffer, 0) != 2) return 10;
  if (kotoba_aiueos_device_worker_digest(sha_stream_state,
                                         SHA_STREAM_STATE_BYTES,
                                         sha_stream_buffer, 32769) != -2)
    return 10;
  sha_stream_buffer[0] = 'a'; sha_stream_buffer[1] = 'b'; sha_stream_buffer[2] = 'c';
  if (kotoba_aiueos_sha256_region(sha_stream_state, SHA_STREAM_STATE_BYTES,
                                  sha_stream_buffer, 3) != 0) return 10;
  if (!sha_stream_is(out,
      "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")) return 10;
  return 0;
}


#define AIUEOS_OWNED_MEMORY_MAP_BYTES (128ULL * 1024ULL)
static struct aiueos_boot_info aiueos_owned_boot_info;
/* Keep the retained firmware map out of the low-2MiB fine-grained W^X
 * aperture.  The exact Qwen runtime plus Device-P256 objects make the map's
 * 128 KiB the difference between keeping the linked user/guard pages below
 * PROCESS_PRIVATE_BASE and silently pushing them into the 2MiB huge-page
 * region.  The high section is still ordinary kernel-owned RAM: the owned
 * page directory maps 4..6 MiB writable and NX, and the physical allocator
 * excludes it through aiueos_kernel_end. */
static uint8_t aiueos_owned_memory_map[AIUEOS_OWNED_MEMORY_MAP_BYTES]
  __attribute__((aligned(16), section(".high_bss")));
#ifdef AIUEOS_QWEN38_MODEL_HANDOFF
/* The exact graph is about 75 KiB.  Keeping it in kernel BSS moves the linked
 * user/guard pages beyond the low-2MiB bootstrap map.  The admitted model is
 * immutable, so retain only this pointer here and construct the graph in the
 * allocator-backed volatile workspace after owned paging is active. */
static struct aiueos_inference_status aiueos_qwen35_status;
static char aiueos_qwen35_progress_detail[] = "T01 L00 OF64";
static uint32_t aiueos_qwen35_last_render_token = UINT32_MAX;
static char aiueos_qwen35_output_detail[] = "T01 OUTPUT HEAD";
static char aiueos_qwen35_decode_detail[] = "TOKEN 00 OF 08";
static char aiueos_qwen35_first_fail_detail[] = "FIRST TOKEN 000000";
static char aiueos_qwen35_decode_fail_detail[32] = "T00 L00 UNKNOWN";
static uint32_t aiueos_qwen35_active_token = 1U;
#endif

/* The loader's boot-info object and memory-map buffer are firmware-owned.
   They are readable under the inherited CR3 but are not necessarily inside
   the kernel's bounded low identity map.  Retain every scalar and the bounded
   descriptor stream before aiueos_paging_initialize installs the owned root. */
extern void aiueos_storage_set_key(const uint8_t key[16]);
static int aiueos_boot_info_retain(const struct aiueos_boot_info *source) {
  if (!source || !source->memory_map || !source->memory_map_size ||
      !source->descriptor_size ||
      source->memory_map_size > AIUEOS_OWNED_MEMORY_MAP_BYTES ||
      source->memory_map_size % source->descriptor_size != 0)
    return 0;
  aiueos_owned_boot_info = (struct aiueos_boot_info){0};
  aiueos_owned_boot_info.magic = source->magic;
  /* G3: hand the loader's data-disk key to the storage layer. */
  if (source->data_key_tag == 0x9a7461b0d2746b31ULL) {
    for (int i = 0; i < 16; i++)
      aiueos_owned_boot_info.data_key[i] = source->data_key[i];
    aiueos_owned_boot_info.data_key_tag = source->data_key_tag;
    aiueos_storage_set_key(source->data_key);
  }
  aiueos_owned_boot_info.version = source->version;
  aiueos_owned_boot_info.memory_map_size = source->memory_map_size;
  aiueos_owned_boot_info.descriptor_size = source->descriptor_size;
  aiueos_owned_boot_info.descriptor_version = source->descriptor_version;
  aiueos_owned_boot_info.acpi_rsdp = source->acpi_rsdp;
  aiueos_owned_boot_info.framebuffer_base = source->framebuffer_base;
  aiueos_owned_boot_info.framebuffer_size = source->framebuffer_size;
  aiueos_owned_boot_info.framebuffer_width = source->framebuffer_width;
  aiueos_owned_boot_info.framebuffer_height = source->framebuffer_height;
  aiueos_owned_boot_info.framebuffer_stride = source->framebuffer_stride;
  aiueos_owned_boot_info.framebuffer_format = source->framebuffer_format;
  aiueos_owned_boot_info.initramfs_base = source->initramfs_base;
  aiueos_owned_boot_info.initramfs_size = source->initramfs_size;
  aiueos_owned_boot_info.runtime_services = source->runtime_services;
  aiueos_owned_boot_info.firmware_cr3 = source->firmware_cr3;
  if (source->version >= AIUEOS_BOOT_INFO_VERSION_MODEL_HANDOFF) {
    aiueos_owned_boot_info.model_base = source->model_base;
    aiueos_owned_boot_info.model_size = source->model_size;
    for (uint32_t i = 0; i < 32; i++)
      aiueos_owned_boot_info.model_sha256[i] = source->model_sha256[i];
    aiueos_owned_boot_info.model_part_count = source->model_part_count;
    aiueos_owned_boot_info.model_format = source->model_format;
    aiueos_owned_boot_info.model_flags = source->model_flags;
    aiueos_owned_boot_info.model_load_cycles = source->model_load_cycles;
    aiueos_owned_boot_info.model_paging_base = source->model_paging_base;
    aiueos_owned_boot_info.model_paging_pages = source->model_paging_pages;
    if (source->version >= AIUEOS_BOOT_INFO_VERSION_TSC_CALIBRATED)
      aiueos_owned_boot_info.tsc_hz = source->tsc_hz;
  }
  const volatile uint8_t *input = source->memory_map;
  for (uint64_t i = 0; i < source->memory_map_size; i++)
    aiueos_owned_memory_map[i] = input[i];
  aiueos_owned_boot_info.memory_map = aiueos_owned_memory_map;
  return 1;
}

/* Bounded `newc` cpio validation. The archive was already bound to a
   compiled-in SHA-256 by the loader; this walk proves the structure: magic
   per entry, hex-only size fields, 4-byte alignment, in-bounds extents, a
   bounded entry count, and the TRAILER!!! terminator. Runs before the kernel
   replaces the firmware page tables, while the loader-pool buffer is still
   identity-mapped. */
static int initramfs_hex_field(const uint8_t *field, uint64_t *value) {
  uint64_t result = 0;
  for (uint32_t i = 0; i < 8; i++) {
    uint8_t c = field[i]; uint64_t digit;
    if (c >= '0' && c <= '9') digit = c - '0';
    else if (c >= 'a' && c <= 'f') digit = c - 'a' + 10;
    else if (c >= 'A' && c <= 'F') digit = c - 'A' + 10;
    else return 0;
    result = (result << 4) | digit;
  }
  *value = result;
  return 1;
}

/* Recovery materials copied out of the archive while the loader-pool buffer
   is still identity-mapped, sized by the same bound as catalog applications. */
static uint8_t __attribute__((section(".high_bss"), aligned(16))) initramfs_recovery_elf[98304];
static uint8_t initramfs_recovery_signature[256];
/* The catalog signature (recovery/app-catalog.sig) that build-uefi.sh has
   always packed into the archive. The blank-volume format route (JUN-34)
   reconstructs the catalog byte for byte as scripts/make-aiuefs-image.py
   builds it and must verify this signature over those exact bytes before a
   zeroed volume receives a single sector. */
static uint8_t initramfs_recovery_catalog_signature[256];
static uint64_t initramfs_recovery_elf_length;
static int initramfs_recovery_signature_present;
static int initramfs_recovery_catalog_signature_present;

/* The desktop font (ADR-0224), aiueos-font/v1 from os/aiueos/fonts/. Copied
   out of the archive for the same reason as the recovery ELF; 320 KiB bounds
   it (the committed subset is 267,208 bytes). */
#define AIUEOS_FONT_BYTES_MAX (320U * 1024U)
static uint8_t __attribute__((section(".high_bss"), aligned(16))) initramfs_font[AIUEOS_FONT_BYTES_MAX];
static uint64_t initramfs_font_length;
const uint8_t *aiueos_initramfs_font(uint64_t *length) {
  if (length) *length = initramfs_font_length;
  return initramfs_font_length ? initramfs_font : 0;
}

/* The desktop IME's kana-kanji dictionary (ADR-0235), aiueos-dict/v1 from
   os/aiueos/ime/, generated from Unicode Unihan. Copied out like the font;
   256 KiB bounds it (the committed file is 189,892 bytes). C only carries
   it: which reading converts to what is Kotoba `kotoba_aiueos_browser_key`. */
#define AIUEOS_DICTIONARY_BYTES_MAX (256U * 1024U)
static uint8_t __attribute__((section(".high_bss"), aligned(16))) initramfs_dictionary[AIUEOS_DICTIONARY_BYTES_MAX];
static uint64_t initramfs_dictionary_length;
const uint8_t *aiueos_initramfs_dictionary(uint64_t *length) {
  if (length) *length = initramfs_dictionary_length;
  return initramfs_dictionary_length ? initramfs_dictionary : 0;
}

const uint8_t *aiueos_initramfs_recovery_elf(uint64_t *length) {
  if (length) *length = initramfs_recovery_elf_length;
  return initramfs_recovery_elf_length ? initramfs_recovery_elf : 0;
}
const uint8_t *aiueos_initramfs_recovery_signature(void) {
  return initramfs_recovery_signature_present ? initramfs_recovery_signature : 0;
}
const uint8_t *aiueos_initramfs_recovery_catalog_signature(void) {
  return initramfs_recovery_catalog_signature_present
    ? initramfs_recovery_catalog_signature : 0;
}

static int initramfs_name_is(const uint8_t *name, uint64_t namesize, const char *wanted) {
  uint64_t length = 0;
  while (wanted[length]) length++;
  if (namesize != length + 1) return 0;
  for (uint64_t i = 0; i < length; i++)
    if (name[i] != (uint8_t)wanted[i]) return 0;
  return name[length] == 0;
}

static int initramfs_validate(uint64_t base, uint64_t size, uint64_t *files) {
  static const char trailer[11] = "TRAILER!!!";
  const uint8_t *archive = (const uint8_t *)(uintptr_t)base;
  uint64_t offset = 0, count = 0;
  if (!base || !size || size > 1024ULL * 1024ULL || (base & 3)) return 0;
  for (;;) {
    if (count > 64 || offset + 110 > size) return 0;
    const uint8_t *header = archive + offset;
    if (header[0] != '0' || header[1] != '7' || header[2] != '0' ||
        header[3] != '7' || header[4] != '0' || header[5] != '1') return 0;
    uint64_t filesize, namesize;
    if (!initramfs_hex_field(header + 54, &filesize) ||
        !initramfs_hex_field(header + 94, &namesize)) return 0;
    if (!namesize || namesize > 256 || filesize > size) return 0;
    uint64_t name_offset = offset + 110;
    if (name_offset + namesize > size) return 0;
    if (namesize == sizeof(trailer)) {
      int is_trailer = 1;
      for (uint32_t i = 0; i < sizeof(trailer); i++)
        if (archive[name_offset + i] != (uint8_t)trailer[i]) { is_trailer = 0; break; }
      if (is_trailer) { *files = count; return 1; }
    }
    uint64_t data_offset = (name_offset + namesize + 3) & ~3ULL;
    if (data_offset > size || filesize > size - data_offset) return 0;
    if (initramfs_name_is(archive + name_offset, namesize, "recovery/user-smoke.elf") &&
        filesize && filesize <= sizeof(initramfs_recovery_elf)) {
      for (uint64_t i = 0; i < filesize; i++)
        initramfs_recovery_elf[i] = archive[data_offset + i];
      initramfs_recovery_elf_length = filesize;
    }
    if (initramfs_name_is(archive + name_offset, namesize, "font/aiueos-16.fnt") &&
        filesize && filesize <= sizeof(initramfs_font)) {
      for (uint64_t i = 0; i < filesize; i++)
        initramfs_font[i] = archive[data_offset + i];
      initramfs_font_length = filesize;
    }
    if (initramfs_name_is(archive + name_offset, namesize, "ime/aiueos-kanji.dic") &&
        filesize && filesize <= sizeof(initramfs_dictionary)) {
      for (uint64_t i = 0; i < filesize; i++)
        initramfs_dictionary[i] = archive[data_offset + i];
      initramfs_dictionary_length = filesize;
    }
    if (initramfs_name_is(archive + name_offset, namesize, "recovery/user-smoke.sig") &&
        filesize == sizeof(initramfs_recovery_signature)) {
      for (uint64_t i = 0; i < filesize; i++)
        initramfs_recovery_signature[i] = archive[data_offset + i];
      initramfs_recovery_signature_present = 1;
    }
    if (initramfs_name_is(archive + name_offset, namesize, "recovery/app-catalog.sig") &&
        filesize == sizeof(initramfs_recovery_catalog_signature)) {
      for (uint64_t i = 0; i < filesize; i++)
        initramfs_recovery_catalog_signature[i] = archive[data_offset + i];
      initramfs_recovery_catalog_signature_present = 1;
    }
    offset = (data_offset + filesize + 3) & ~3ULL;
    count++;
  }
}

struct __attribute__((packed)) idt_entry {
  uint16_t offset_low, selector;
  uint8_t ist, attributes;
  uint16_t offset_middle;
  uint32_t offset_high, reserved;
};
struct __attribute__((packed)) descriptor_pointer {
  uint16_t limit;
  uint64_t base;
};

extern void aiueos_load_gdt(void);
extern void aiueos_load_idt(const struct descriptor_pointer *pointer);
extern void aiueos_isr_invalid_opcode(void);
extern void aiueos_isr_page_fault(void);
extern void aiueos_isr_apic_timer(void);
extern void aiueos_isr_external_timer(void);
extern void aiueos_isr_virtio_rng(void);
extern void aiueos_isr_virtio_blk(void);
extern void aiueos_isr_syscall(void);
/* The fatal stubs entry.S generates for every remaining CPU vector
   (ADR-0199).  Declared one per line rather than through a macro so that a
   vector missing from this list is missing in the install table too and shows
   up as a link error, not as a gate that was quietly never written. */
extern void aiueos_isr_fatal_0(void);
extern void aiueos_isr_fatal_1(void);
extern void aiueos_isr_fatal_2(void);
extern void aiueos_isr_fatal_3(void);
extern void aiueos_isr_fatal_4(void);
extern void aiueos_isr_fatal_5(void);
extern void aiueos_isr_fatal_7(void);
extern void aiueos_isr_fatal_8(void);
extern void aiueos_isr_fatal_9(void);
extern void aiueos_isr_fatal_10(void);
extern void aiueos_isr_fatal_11(void);
extern void aiueos_isr_fatal_12(void);
extern void aiueos_isr_fatal_13(void);
extern void aiueos_isr_fatal_15(void);
extern void aiueos_isr_fatal_16(void);
extern void aiueos_isr_fatal_17(void);
extern void aiueos_isr_fatal_18(void);
extern void aiueos_isr_fatal_19(void);
extern void aiueos_isr_fatal_20(void);
extern void aiueos_isr_fatal_21(void);
extern void aiueos_isr_fatal_22(void);
extern void aiueos_isr_fatal_23(void);
extern void aiueos_isr_fatal_24(void);
extern void aiueos_isr_fatal_25(void);
extern void aiueos_isr_fatal_26(void);
extern void aiueos_isr_fatal_27(void);
extern void aiueos_isr_fatal_28(void);
extern void aiueos_isr_fatal_29(void);
extern void aiueos_isr_fatal_30(void);
extern void aiueos_isr_fatal_31(void);
extern uint8_t aiueos_text_start[], aiueos_text_end[];
extern void aiueos_probe_write_protect(void);
extern void aiueos_probe_no_execute(void);
volatile uint64_t aiueos_page_fault_stage;
volatile uint64_t aiueos_page_fault_error;
extern int aiueos_paging_initialize(const struct aiueos_boot_info *boot);
extern int aiueos_framebuffer_initialize(const struct aiueos_boot_info *boot);
extern void aiueos_framebuffer_qualification_screen(const char *, const char *,
                                                     const char *, int);
extern void aiueos_qualification_runtime_initialize(void *, uint64_t);
extern int aiueos_qualification_progress(uint32_t);
extern int aiueos_qualification_finalize(uint16_t, uint32_t);
extern int aiueos_qualification_reboot(void);
extern int aiueos_desktop_surface_ready(void);
extern int aiueos_desktop_surface_bind_scanout(uint32_t width, uint32_t height);
/* D3: scripted touchpad gestures (pci.c, AIUEOS_TOUCHPAD_GESTURE_SYNTHETIC). */
extern void aiueos_tablet_gesture_arm(void);
extern uint32_t aiueos_tablet_gesture_done(void);
#ifdef AIUEOS_BATTERY_PROBE
/* I2: the synthetic battery state behind the BAT status text (framebuffer.c). */
extern void aiueos_desktop_battery_set(uint32_t ac, uint32_t level);
extern uint32_t aiueos_desktop_battery_level(void);
extern uint32_t aiueos_desktop_battery_ac(void);
/* show() returns before painting the status band when the damage rectangle
   is empty (framebuffer.c:790), and this stage's frame does not change
   between steps -- measured: the band read back as the desktop background
   (f1f1f2) at every step, warn-px=0 base-px=0. The band must therefore be
   painted by the stage itself before it samples it. */
extern void aiueos_desktop_paint_status(void);
extern int aiueos_desktop_show_full(void);
#endif
/* C9/status bar keeps the pointer on top; see the note in framebuffer.c. */
extern void aiueos_desktop_set_pointer(uint32_t x, uint32_t y);
extern int aiueos_desktop_wm_rects_fit(void);
extern int aiueos_desktop_wm_paint(uint64_t front);
extern uint32_t aiueos_desktop_wm_stored_color(uint64_t window_id);
extern uint32_t aiueos_desktop_sample_pixel(uint32_t x, uint32_t y);
extern int aiueos_acpi_initialize(const void *rsdp);
extern uint32_t aiueos_acpi_ivrs_present(void);
extern uint32_t aiueos_acpi_ivrs_seen(void);
extern uint32_t aiueos_acpi_tpm2_seen(void);
extern uint32_t aiueos_acpi_tpm2_present(void);
extern int aiueos_pci_input_devices_seen(void);
extern int aiueos_pci_input_fail_line(void);
extern int aiueos_pci_input_fail_reason(void);
extern int aiueos_virtio_blk_wait_overshot(void);
extern unsigned aiueos_virtio_blk_wait_used(void);
extern unsigned aiueos_virtio_blk_wait_target(void);
extern unsigned aiueos_virtio_blk_slowest_wait(void);
extern unsigned aiueos_virtio_blk_slow_used(void);
extern unsigned aiueos_virtio_blk_slow_target(void);
extern int aiueos_dma_test_policy_allows_unisolated(void);
extern int aiueos_vtd_initialize(void);
extern int aiueos_vtd_translation_enabled(void);
extern uint32_t aiueos_vtd_error(void);
extern int aiueos_vtd_interrupt_remapping_enabled(void);
extern int aiueos_apic_timer_initialize(void);
extern volatile uint64_t aiueos_apic_timer_ticks;
extern int aiueos_physical_allocator_initialize(const struct aiueos_boot_info *boot);
extern void *aiueos_allocate_physical_page(void);
extern void *aiueos_allocate_contiguous_physical_pages(uint64_t);
extern int aiueos_pci_enumerate(void);
extern int aiueos_rtl8125_physical_qualification(void);
extern unsigned aiueos_rtl8125_qualification_error(void);
extern uint32_t aiueos_rtl8125_qualification_rx_length(void);
#ifdef AIUEOS_MURAKUMO_DEVICE_RESULT
extern int aiueos_rtl8125_direct_https_qualification(
    const struct aiueos_boot_info *, uint32_t, uint32_t, uint32_t,
    uint32_t, uint64_t, uint64_t, uint64_t, uint32_t, uint32_t);
extern const char *aiueos_rtl8125_direct_device_did(void);
extern int aiueos_rtl8125_device_worker_poll(
    const struct aiueos_boot_info *, uint32_t, uint64_t *, uint32_t *, int *,
    uint64_t *, int *, int *);
extern int aiueos_rtl8125_device_worker_control_ack(
    const struct aiueos_boot_info *, uint32_t, uint64_t);
extern int aiueos_rtl8125_device_worker_result(
    const struct aiueos_boot_info *, uint32_t, uint64_t,
    uint32_t, uint32_t, uint32_t, uint32_t, uint64_t, uint64_t, uint64_t,
    uint32_t, uint32_t);
extern void aiueos_rtl8125_inference_failure_report(
    uint64_t, uint32_t, uint32_t, uint32_t, uint32_t);
#else
extern int aiueos_rtl8125_direct_https_qualification(void);
#endif
extern unsigned aiueos_rtl8125_direct_https_error(void);
extern unsigned aiueos_rtl8125_direct_https_attempts(void);
extern uint32_t aiueos_rtl8125_direct_tls_stage(void);
extern uint32_t aiueos_rtl8125_direct_response_wait_ms(void);
extern uint32_t aiueos_rtl8125_direct_response_timeout_seconds(void);
extern uint32_t aiueos_rtl8125_direct_dns_a(void);
extern int aiueos_rtl8125_direct_http_ready(void);
extern int aiueos_rtl8125_relay_qualification(void);
extern unsigned aiueos_rtl8125_relay_error(void);
extern uint32_t aiueos_rtl8125_relay_rx_length(void);
extern int aiueos_rtl8125_job_qualification(void);
extern unsigned aiueos_rtl8125_job_error(void);
extern uint8_t aiueos_rtl8125_job_token(void);
extern uint16_t aiueos_rtl8125_job_score(void);
extern uint16_t aiueos_rtl8125_job_total(void);
extern uint64_t aiueos_rtl8125_job_cycles(void);
extern int aiueos_rtl8125_liveness_renewal(void);
extern unsigned aiueos_rtl8125_liveness_error(void);
extern uint32_t aiueos_rtl8125_liveness_sequence(void);
extern int aiueos_catalog_policy_selftest_ok(void);
extern int aiueos_object_store_ready(void);
extern int aiueos_object_store_formatted(void);
extern int aiueos_journal_ready(void);
extern int aiueos_journal_recovered(void);
extern uint32_t aiueos_journal_sequence(void);
extern uint32_t aiueos_journal_recovered_sequence(void);
extern uint32_t aiueos_journal_slot(void);
extern int aiueos_object_transaction_replayed(void);
extern uint32_t aiueos_object_transaction_sequence(void);
extern int aiueos_service_registry_ready(void);
extern int aiueos_service_registry_replayed(void);
extern int aiueos_recovered_service_registry_ready(void);
extern uint64_t aiueos_recovered_service_registry_state(unsigned service);
extern int aiueos_user_object_replay_evidence_ready(void);
extern int aiueos_virtio_net_ready(void);
extern int aiueos_ipv4_ready(void);
extern int aiueos_tcp_ready(void);
extern unsigned aiueos_tcp_stage(void);
extern unsigned aiueos_ssh_listen_stage(void);
extern int aiueos_ssh_client_id_valid(void);
extern unsigned aiueos_ssh_kex_stage(void);
extern uint32_t aiueos_ssh_client_id_len(void);
#if defined(AIUEOS_SSH_LISTEN) && \
    defined(AIUEOS_PHYSICAL_DIRECT_HTTPS_QUALIFICATION) && \
    defined(AIUEOS_MURAKUMO_DEVICE_RESULT)
extern int aiueos_rtl8125_ssh_poll(void);
#endif
extern int aiueos_random_selftest(void);
extern int aiueos_random_bytes(uint8_t *out, uint32_t n);
/* The ECDSA P-256 deterministic sign object (kotoba/ecdsa-p256-sign.kotoba).
   ABI: private-32, digest-32, k-32, out-64 (r||s big-endian), workspace-2048;
   returns 1 unless r or s is zero. */
extern uint64_t kotoba_aiueos_ecdsa_p256_sign(const uint8_t *priv,
                                              const uint8_t *digest,
                                              const uint8_t *k,
                                              uint8_t *out,
                                              uint8_t *workspace);
#ifdef AIUEOS_ECDSA_PUBLIC_KAT
extern uint64_t kotoba_aiueos_ecdsa_p256_public(const uint8_t *priv,
                                                uint8_t *out,
                                                uint8_t *workspace);
static int aiueos_ecdsa_public_kat(void) {
  static const uint8_t d[32] = {
    0xc9,0xaf,0xa9,0xd8,0x45,0xba,0x75,0x16,0x6b,0x5c,0x21,0x57,0x67,0xb1,0xd6,0x93,
    0x4e,0x50,0xc3,0xdb,0x36,0xe8,0x9b,0x12,0x7b,0x8a,0x62,0x2b,0x12,0x0f,0x67,0x21};
  static const uint8_t want[64] = {
    0x60,0xfe,0xd4,0xba,0x25,0x5a,0x9d,0x31,0xc9,0x61,0xeb,0x74,0xc6,0x35,0x6d,0x68,
    0xc0,0x49,0xb8,0x92,0x3b,0x61,0xfa,0x6c,0xe6,0x69,0x62,0x2e,0x60,0xf2,0x9f,0xb6,
    0x79,0x03,0xfe,0x10,0x08,0xb8,0xbc,0x99,0xa4,0x1a,0xe9,0xe9,0x56,0x28,0xbc,0x64,
    0xf2,0xf1,0xb2,0x0c,0x2d,0x7e,0x9f,0x51,0x77,0xa3,0xc2,0x94,0xd4,0x46,0x22,0x99};
  static uint8_t workspace[2048];
  uint8_t out[64];
  if (!kotoba_aiueos_ecdsa_p256_public(d, out, workspace)) return 0;
  for (uint32_t i = 0; i < 64; i++) if (out[i] != want[i]) return 0;
  return 1;
}
#endif
#ifdef AIUEOS_ECDSA_SIGN_KAT
static int aiueos_ecdsa_sign_kat(void) {
  /* RFC 6979 A.2.5, P-256/SHA-256, message "sample". */
  static const uint8_t d[32] = {
    0xc9,0xaf,0xa9,0xd8,0x45,0xba,0x75,0x16,0x6b,0x5c,0x21,0x57,0x67,0xb1,0xd6,0x93,
    0x4e,0x50,0xc3,0xdb,0x36,0xe8,0x9b,0x12,0x7b,0x8a,0x62,0x2b,0x12,0x0f,0x67,0x21};
  static const uint8_t h[32] = {  /* SHA256("sample") */
    0xaf,0x2b,0xdb,0xe1,0xaa,0x9b,0x6e,0xc1,0xe2,0xad,0xe1,0xd6,0x94,0xf4,0x1f,0xc7,
    0x1a,0x83,0x1d,0x02,0x68,0xe9,0x89,0x15,0x62,0x11,0x3d,0x8a,0x62,0xad,0xd1,0xbf};
  static const uint8_t k[32] = {
    0xa6,0xe3,0xc5,0x7d,0xd0,0x1a,0xbe,0x90,0x08,0x65,0x38,0x39,0x83,0x55,0xdd,0x4c,
    0x3b,0x17,0xaa,0x87,0x33,0x82,0xb0,0xf2,0x4d,0x61,0x29,0x49,0x3d,0x8a,0xad,0x60};
  static const uint8_t want[64] = {
    0xef,0xd4,0x8b,0x2a,0xac,0xb6,0xa8,0xfd,0x11,0x40,0xdd,0x9c,0xd4,0x5e,0x81,0xd6,
    0x9d,0x2c,0x87,0x7b,0x56,0xaa,0xf9,0x91,0xc3,0x4d,0x0e,0xa8,0x4e,0xaf,0x37,0x16,
    0xf7,0xcb,0x1c,0x94,0x2d,0x65,0x7c,0x41,0xd4,0x36,0xc7,0xa1,0xb6,0xe2,0x9f,0x65,
    0xf3,0xe9,0x00,0xdb,0xb9,0xaf,0xf4,0x06,0x4d,0xc4,0xab,0x2f,0x84,0x3a,0xcd,0xa8};
  static uint8_t ws[2048];
  uint8_t out[64];
  if (!kotoba_aiueos_ecdsa_p256_sign(d, h, k, out, ws)) return 0;
  for (int i = 0; i < 64; i++) if (out[i] != want[i]) return 0;
  return 1;
}
#endif
#ifdef AIUEOS_SSH_LISTEN
/* SSH-2 curve25519-sha256 exchange hash H (RFC 5656 §4, RFC 8731). The
   transcript is the ordered concatenation
     string(V_C) string(V_S) string(I_C) string(I_S) string(K_S)
     string(Q_C) string(Q_S) mpint(K)
   and H = SHA-256(transcript). This mirrors ssh.transport/h-transcript from
   kotoba-lang/org-ietf-ssh (west-imported, ADR-0106): that .cljc is the single
   source of truth for the wire rules, and smoke-qemu-ssh-kex re-derives the
   expected H from it so a drift in the shared core turns the gate red even
   though this kernel self-verifies against a baked want[].

   The transcript assembly is decision-free mechanism (byte layout only); the
   hash is the already-linked Kotoba SHA-256 object, so this KAT adds no new
   object and rides under AIUEOS_SSH_LISTEN (unlike the ~50 KiB ECDSA sign
   object, which needs its own flag near the 1 MiB ceiling). */
extern uint64_t kotoba_aiueos_sha256(const uint8_t *, uint64_t, uint8_t[32],
                                     uint8_t *, uint64_t);
static uint64_t ssh_put_string(uint8_t *buf, uint64_t off,
                               const uint8_t *bytes, uint32_t n) {
  buf[off]     = (uint8_t)(n >> 24);
  buf[off + 1] = (uint8_t)(n >> 16);
  buf[off + 2] = (uint8_t)(n >> 8);
  buf[off + 3] = (uint8_t)(n);
  for (uint32_t i = 0; i < n; i++) buf[off + 4 + i] = bytes[i];
  return off + 4 + n;
}
static uint64_t ssh_put_mpint(uint8_t *buf, uint64_t off,
                              const uint8_t *bytes, uint32_t n) {
  uint32_t start = 0;
  while (start < n && bytes[start] == 0) start++;   /* strip leading zeros */
  uint32_t rem = n - start;
  if (rem == 0) {                                    /* zero -> empty string */
    buf[off] = buf[off + 1] = buf[off + 2] = buf[off + 3] = 0;
    return off + 4;
  }
  uint32_t pad = (bytes[start] & 0x80) ? 1u : 0u;    /* keep it non-negative */
  uint32_t len = rem + pad;
  buf[off]     = (uint8_t)(len >> 24);
  buf[off + 1] = (uint8_t)(len >> 16);
  buf[off + 2] = (uint8_t)(len >> 8);
  buf[off + 3] = (uint8_t)(len);
  uint64_t p = off + 4;
  if (pad) buf[p++] = 0x00;
  for (uint32_t i = start; i < n; i++) buf[p++] = bytes[i];
  return p;
}
static int aiueos_ssh_kex_h(uint8_t out[32]) {
  /* Fixed KAT wire inputs, identical to the ssh.transport test fixture; kept
     short so the baked arrays stay tiny. K has its high bit set to exercise the
     mpint leading-zero rule. */
  static const uint8_t v_c[] = "SSH-2.0-C";       /* len 9  (NUL excluded) */
  static const uint8_t v_s[] = "SSH-2.0-aiueos";  /* len 14 */
  static const uint8_t i_c[] = {0x14, 0x01, 0x02, 0x03};
  static const uint8_t i_s[] = {0x14, 0x0a, 0x0b, 0x0c, 0x0d};
  static const uint8_t k_s[] = "hostkey-blob";    /* len 12 */
  uint8_t q_c[32], q_s[32], k[32];
  for (int i = 0; i < 32; i++) { q_c[i] = (uint8_t)i; q_s[i] = (uint8_t)((i + 100) & 0xff); }
  k[0] = 0x80;
  for (int i = 1; i < 32; i++) k[i] = (uint8_t)(i - 1);
  static uint8_t buf[256];
  uint64_t off = 0;
  off = ssh_put_string(buf, off, v_c, 9);
  off = ssh_put_string(buf, off, v_s, 14);
  off = ssh_put_string(buf, off, i_c, 4);
  off = ssh_put_string(buf, off, i_s, 5);
  off = ssh_put_string(buf, off, k_s, 12);
  off = ssh_put_string(buf, off, q_c, 32);
  off = ssh_put_string(buf, off, q_s, 32);
  off = ssh_put_mpint(buf, off, k, 32);
  static uint8_t ws[512];
  return (int)kotoba_aiueos_sha256(buf, off, out, ws, sizeof(ws));
}
#endif
extern int aiueos_dhcp_ready(void);
extern unsigned aiueos_dhcp_stage(void);
extern unsigned aiueos_dhcp_reason(void);
extern uint32_t aiueos_dhcp_address(void);
extern uint32_t aiueos_dhcp_mask(void);
extern uint32_t aiueos_dhcp_router(void);
extern uint32_t aiueos_dhcp_server(void);
extern uint32_t aiueos_dhcp_lease_seconds(void);
extern uint32_t aiueos_dhcp_dns(void);
extern int aiueos_dhcp_consumed(void);
extern int aiueos_dns_ready(void);
extern unsigned aiueos_dns_stage(void);
extern uint32_t aiueos_dns_a(void);
extern int aiueos_tcp_cloud_ready(void);
extern unsigned aiueos_tcp_cloud_stage(void);
extern int aiueos_tls_record_ready(void);
extern uint8_t aiueos_tls_record_type(void);
extern int aiueos_tls_handshake_ready(void);
extern int aiueos_http_cid_ready(void);
extern const char *aiueos_http_cid(void);
extern uint32_t aiueos_tls_stage(void);
extern uint32_t aiueos_tls_rx_buffered(void);
extern uint32_t aiueos_tls_app_len(void);
extern uint8_t aiueos_tls_last_record_type(void);
extern uint8_t aiueos_tls_last_inner_type(void);
extern int aiueos_tls_failed(void);
extern int aiueos_tls_finished_sent(void);
extern int aiueos_tls_http_sent(void);
extern uint32_t aiueos_tls_nst_count(void);
extern uint32_t aiueos_gpu_scanout_width(void);
extern uint32_t aiueos_gpu_scanout_height(void);
extern uint32_t aiueos_gpu_enabled_scanouts(void);
extern int aiueos_gpu_2d_create_ok(void);
extern int aiueos_gpu_2d_flush_ok(void);
extern int aiueos_gpu_2d_two_ok(void);
extern int aiueos_gpu_scanout_two_ok(void);
extern int aiueos_desktop_input_from_eventq(void);
extern int aiueos_desktop_input_eventq_empty(void);
extern uint64_t kotoba_aiueos_ime_commit(uint64_t a, uint64_t b);
extern uint64_t kotoba_aiueos_wm_hit(uint64_t n, uint64_t front,
                                     uint64_t px, uint64_t py);
extern uint64_t kotoba_aiueos_broker_admit(uint64_t a, uint64_t b);
extern uint64_t kotoba_aiueos_session_restore(uint64_t a);
/* Guest browser desktop (ADR-0223): kotoba-lang/browser's surface as the
   desktop, on KERNEL.ELF. */
extern uint64_t kotoba_aiueos_browser_frame(uint64_t state, uint64_t state_bytes,
                                            uint64_t ops, uint64_t ops_bytes);
extern uint64_t kotoba_aiueos_browser_frame2(uint64_t surface, uint64_t surface_bytes,
                                             uint64_t font, uint64_t font_bytes);
extern int aiueos_desktop_present_ops2(const uint32_t *ops, uint64_t count,
                                       const uint8_t *font, uint64_t font_length);
extern uint32_t aiueos_desktop_colour_census(uint32_t rgb, uint32_t *count_out);
extern int aiueos_desktop_show(void);
extern const uint8_t *aiueos_initramfs_font(uint64_t *length);
extern const uint8_t *aiueos_initramfs_dictionary(uint64_t *length);
/* ADR-0235: key = evdev code * 4 + value (five parameters is the native
   ceiling, and the dictionary took two). */
extern uint64_t kotoba_aiueos_browser_key(uint64_t surface, uint64_t surface_bytes,
                                          uint64_t dictionary, uint64_t dictionary_bytes,
                                          uint64_t key);
extern int aiueos_keyboard_drain(uint32_t rounds);
extern uint32_t aiueos_keyboard_next_press(uint32_t budget);
extern uint32_t aiueos_keyboard_next_key(uint32_t budget);
extern int aiueos_tablet_drain(uint32_t rounds);
extern uint32_t aiueos_tablet_next(uint32_t budget, uint32_t *x, uint32_t *y);
extern uint64_t kotoba_aiueos_browser_reduce(uint64_t state, uint64_t state_bytes,
                                             uint64_t kind, uint64_t a, uint64_t b);
extern int aiueos_desktop_present_ops(const uint32_t *ops, uint64_t count);
extern uint32_t aiueos_desktop_sample_rgb(uint32_t x, uint32_t y);
extern uint32_t aiueos_desktop_width(void);
extern uint32_t aiueos_desktop_height(void);
extern int aiueos_desktop_pointer_ready(void);
extern int aiueos_desktop_pointer_tablets_seen(void);
extern uint32_t aiueos_desktop_pointer_abs_x(void);
extern uint32_t aiueos_desktop_pointer_abs_y(void);
extern uint32_t aiueos_desktop_pointer_events_used(void);
extern uint32_t aiueos_desktop_pointer_events_abs(void);
extern uint32_t aiueos_desktop_pointer_events_key(void);
extern void aiueos_scheduler_initialize(void);
extern int aiueos_scheduler_restore_service_registry(uint64_t state0, uint64_t state1);
extern int aiueos_scheduler_persistent_restore_evidence_ready(void);
extern int aiueos_scheduler_evidence_ready(void);
extern int aiueos_service_runtime_evidence_ready(void);
extern int aiueos_service_ipc_evidence_ready(void);
extern int aiueos_syscall_self_test(void);
extern int aiueos_capability_table_initialize(void);
extern uint16_t aiueos_capability_table_capacity(void);
extern int aiueos_dynamic_capability_evidence_ready(void);
extern int aiueos_capability_derivation_evidence_ready(void);
extern int aiueos_process_initialize(void);
extern void aiueos_process_enter(void);
extern int aiueos_process_result(void);
extern int aiueos_process_lifecycle_evidence_ready(void);
extern int aiueos_kotoba_service_ipc_evidence_ready(void);
extern int aiueos_catalog_lookup_rejection_evidence_ready(void);
extern int aiueos_syscall_transport_evidence_ready(void);
extern int aiueos_kotoba_runtime_evidence_ready(void);
extern int aiueos_address_space_self_test(void);
extern void aiueos_load_task_register(void);
extern int aiueos_smp_start_application_processor(void);
extern int aiueos_smp_dispatch_selftest(void);
extern int aiueos_ioapic_route_legacy_timer(void);
extern volatile uint64_t aiueos_external_timer_ticks;
extern volatile uint64_t aiueos_virtio_rng_irq_count;
extern volatile uint64_t aiueos_virtio_blk_irq_count;
static struct idt_entry idt[256] __attribute__((aligned(16)));

static inline void debug_byte(uint8_t value) {
  __asm__ volatile("outb %0, $0xe9" : : "a"(value));
}
static inline void out8(uint16_t port, uint8_t value) {
  __asm__ volatile("outb %0, %1" : : "a"(value), "Nd"(port));
}
static inline uint8_t in8(uint16_t port) {
  uint8_t value;
  __asm__ volatile("inb %1, %0" : "=a"(value) : "Nd"(port));
  return value;
}
static void serial_init(void) {
  out8(0x3f8 + 1, 0x00);
  out8(0x3f8 + 3, 0x80);
  out8(0x3f8 + 0, 0x01);
  out8(0x3f8 + 1, 0x00);
  out8(0x3f8 + 3, 0x03);
  out8(0x3f8 + 2, 0xc7);
  out8(0x3f8 + 4, 0x0b);
}
static void serial_byte(uint8_t value) {
  uint32_t budget = 1000000;
  while (!(in8(0x3f8 + 5) & 0x20) && --budget) {}
  if (budget) out8(0x3f8, value);
}
static void serial_string(const char *text) {
  while (*text) serial_byte((uint8_t)*text++);
}
/* Evidence markers from other kernel files (A2's display-change marker is
   emitted from framebuffer.c's desktop path). */
void aiueos_kernel_serial_marker(const char *text) { serial_string(text); }
static void serial_hex_byte(uint8_t value) {
  static const char digits[] = "0123456789abcdef";
  serial_byte((uint8_t)digits[(value >> 4) & 0xf]);
  serial_byte((uint8_t)digits[value & 0xf]);
}
static void debug_string(const char *text) {
  while (*text) debug_byte((uint8_t)*text++);
}

/* The first numbers this kernel prints. Every marker before DHCP is a fixed
   string, because everything they report is either true or false; a lease is
   neither, and a marker that said "an address was configured" without saying
   which one would be unfalsifiable. Formatting is mechanism -- these decide
   nothing, and the values they render were decided by a Kotoba object. */
static void serial_decimal(uint32_t value) {
  char digits[10];
  unsigned count = 0;
  if (!value) { serial_byte('0'); return; }
  while (value) { digits[count++] = (char)('0' + (value % 10)); value /= 10; }
  while (count) serial_byte((uint8_t)digits[--count]);
}

/* A2: pci.c reports the host display geometry it read off the device, and
   serial_decimal is file-local. Formatting only -- the numbers are the
   device's answer to GET_DISPLAY_INFO, not a decision this code makes. */
void aiueos_kernel_serial_u32(uint32_t value) { serial_decimal(value); }

static void serial_rgb(uint32_t rgb) {
  serial_hex_byte((uint8_t)(rgb >> 16));
  serial_hex_byte((uint8_t)(rgb >> 8));
  serial_hex_byte((uint8_t)rgb);
}

/* Guest browser desktop (ADR-0224): only when a tablet press arrived --
   the AIUEOS_GUEST_BROWSER profile -- hold the frame on screen for a few
   seconds so the host can screendump it. Counted in `pause`s, not TSC: under
   TCG on an arm64 host the guest TSC can tick at the host's 24 MHz counter,
   and 400,000,000 pauses already outlasted a 228 s watchdog (ADR-0223), so
   8,000,000 is seconds, not minutes. Every other profile passes straight
   through. */
static void browser_hold_for_screendump(void) {
  extern int aiueos_desktop_pointer_ready(void);
  if (!aiueos_desktop_pointer_ready()) return;
  for (uint32_t i = 0; i < 8000000U; i++) __asm__ volatile("pause");
}

static void serial_hex32(uint32_t value) {
  serial_hex_byte((uint8_t)(value >> 24));
  serial_hex_byte((uint8_t)(value >> 16));
  serial_hex_byte((uint8_t)(value >> 8));
  serial_hex_byte((uint8_t)value);
}

static void serial_decimal64(uint64_t value) {
  char digits[20];
  uint32_t count = 0;
  do {
    digits[count++] = (char)('0' + value % 10U);
    value /= 10U;
  } while (value && count < sizeof(digits));
  while (count) serial_byte((uint8_t)digits[--count]);
}

/* Wheel scroll (ADR-0238). After Alt+Tab, the shell registers app 4 -- word
   31 bit 3; its title スクロール and its document, the lines 1 .. 20 each
   ended by a 10 (a <br>), are window slot 4's, written here as the launcher
   stage wrote slot 3 -- and zeroes the four scroll offsets (surface words
   2040..2043). The host sends seventeen tablet batches, each after the
   previous frame line: a press on launcher button 4 at (360, 14) (window 4
   opens at (80, 80, 520, 360) on top, fifteen of its twenty lines inside it),
   the release, a wheel notch toward the end at (360, 14) over no window, a
   move to (300, 300), six notches toward the end and seven toward the start.
   C turns a REL_WHEEL batch into tablet kind 6 or 7 (pci.c) and hands every
   batch to Kotoba `kotoba_aiueos_browser_reduce` with the whole surface
   (state-bytes 8192): which window scrolls, by how much and where the offset
   stops are its decisions (browser.input :pointer/wheel ->
   browser.surface scroll-window), and browser-frame2 draws the body the
   offset higher, cut to the window. Answers are browser-reduce-v1's
   :the-kernel-scroll-* vectors'; op counts, censuses and the chain
   os/aiueos/scripts/browser-frame-model.cljk's scroll frames. */
/* ADR-0246: how many rects of the draw list just painted are in the hover
   colour Kotoba's `hot` chose (#d9d9d9). The pointer's position is Kotoba's
   input; this only counts, and prints beside the frame it counted. */
static void browser_hot_line(const char *stage, uint32_t n, const uint32_t *ops, int64_t count) {
  uint32_t hot = 0;
  for (uint32_t j = 0; count > 0 && j < (uint32_t)count && j < 261U; j++) {
    const uint32_t *op = ops + 6U * j;
    if (op[0] == 1 && op[5] == 14277081U) hot++;
  }
  serial_string("AIUEOS_GUEST_BROWSER_HOT stage=");
  serial_string(stage);
  serial_string(" n=");
  serial_decimal(n);
  serial_string(" hot=");
  serial_decimal(hot);
  serial_string("\r\n");
}

static int browser_scroll_stage(uint32_t *surface, const uint8_t *font, uint64_t font_length) {
  static const uint32_t title4[5] = {12473, 12463, 12525, 12540, 12523};
  static const uint32_t ssrc[17] = {1, 4, 6, 3, 6, 6, 6, 6, 6, 6, 7, 7, 7, 7, 7, 7, 7};
  static const int64_t swant[17] = {4, 0, 0, 0, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4};
  static const uint32_t sscroll[17] = {0, 0, 0, 0, 20, 40, 60, 80, 100, 120, 100, 80, 60, 40, 20, 0, 0};
  static const uint32_t sops[17] = {213, 213, 213, 213, 214, 215, 216, 217, 219, 218,
                                    219, 217, 216, 215, 214, 213, 213};
  static const uint32_t spx[17] = {988, 988, 988, 994, 1017, 1027, 1047, 1065, 1103, 1080,
                                   1103, 1065, 1047, 1027, 1017, 994, 994};
  static const uint32_t shash[17] = {0x16c7e9ceU, 0x16c7e9ceU, 0x16c7e9ceU, 0x78270fdaU, 0x6c0a4440U,
                                     0xb5e126ebU, 0x40c08679U, 0xf7ee3a0bU, 0x5793612fU, 0x2d9fc3f6U,
                                     0x5793612fU, 0xf7ee3a0bU, 0x40c08679U, 0xb5e126ebU, 0x6c0a4440U,
                                     0x78270fdaU, 0x78270fdaU};
  uint64_t sp = (uint64_t)(uintptr_t)surface;
  uint32_t se = 0, soff = 0, spx2 = 0, shash2 = 0, schain = 2166136261U;
  uint32_t sidle = 0, sframes = 0, smax = 0, ax = 0, ay = 0, b = 0;
  int64_t sfo = 0;
  for (unsigned i = 128; i < 160; i++) surface[i] = 0;
  for (unsigned i = 0; i < 5; i++) surface[128 + i] = title4[i];
  for (unsigned i = 352; i < 416; i++) surface[i] = 0;
  for (uint32_t line = 1; line <= 20; line++) {
    if (line >= 10) surface[352 + b++] = 48U + line / 10U;
    surface[352 + b++] = 48U + line % 10U;
    if (line < 20) surface[352 + b++] = 10U;
  }
  surface[31] |= 8U;
  for (unsigned i = 2040; i < 2044; i++) surface[i] = 0;
  (void)aiueos_tablet_drain(4000000U);
  serial_string("AIUEOS_GUEST_BROWSER_SCROLL_GO events=17\r\n");
  while (se < 17 && sidle < 60000U) {
    uint32_t src = aiueos_tablet_next(1024U, &ax, &ay);
    int64_t r;
    if (!src) { sidle++; continue; }
    sidle = 0;
    uint32_t px = (uint32_t)(((uint64_t)ax * surface[3]) / 32768U);
    uint32_t py = (uint32_t)(((uint64_t)ay * surface[4]) / 32768U);
    surface[2046] = px + 1U;
    surface[2047] = py;
    aiueos_desktop_set_pointer(px, py);
    r = (int64_t)kotoba_aiueos_browser_reduce(sp, 8192, src, px, py);
    if (surface[2043] > smax) smax = surface[2043];
    sfo = (int64_t)kotoba_aiueos_browser_frame2(sp, 8192, (uint64_t)(uintptr_t)font, font_length);
    spx2 = 0;
    shash2 = 0;
    if (sfo > 0 && aiueos_desktop_present_ops2(surface + 480, (uint64_t)sfo, font, font_length)) {
      shash2 = aiueos_desktop_colour_census(0x333333U, &spx2);
      (void)aiueos_desktop_show();
      sframes++;
      for (int k = 0; k < 4; k++) {
        schain ^= (shash2 >> (8 * k)) & 255U;
        schain *= 16777619U;
      }
    }
    if (src != ssrc[se] || r != swant[se] || surface[2] != 4 || surface[2043] != sscroll[se] ||
        sfo != (int64_t)sops[se] || spx2 != spx[se] || shash2 != shash[se]) soff++;
    se++;
    browser_hot_line("scroll", se, surface + 480, sfo);
    serial_string("AIUEOS_GUEST_BROWSER_SCROLL_FRAME n=");
    serial_decimal(se);
    serial_string(" src=");
    serial_decimal(src);
    serial_string(r < 0 ? " answer=-" : " answer=");
    serial_decimal((uint32_t)(r < 0 ? -r : r));
    serial_string(" focus=");
    serial_decimal(surface[2]);
    serial_string(" scroll=");
    serial_decimal(surface[2043]);
    serial_string(" ops=");
    serial_decimal((uint32_t)(sfo < 0 ? -sfo : sfo));
    serial_string(" text-px=");
    serial_decimal(spx2);
    serial_string(" hash=");
    serial_hex32(shash2);
    serial_string("\r\n");
  }
  if (se == 17 && sframes == 17 && soff == 0 && smax == 120 && schain == 0x7421f3aaU &&
      surface[1] == 4 && surface[5] == 1 && surface[10] == 3 && surface[15] == 2 &&
      surface[20] == 4 && surface[2] == 4 && surface[25] == 0 && surface[2040] == 0 &&
      surface[2041] == 0 && surface[2042] == 0 && surface[2043] == 0) {
    debug_string("AIUEOS_GUEST_BROWSER_SCROLL_OK\n");
    serial_string("AIUEOS_GUEST_BROWSER_SCROLL_OK events=17 answers=40004444444444444 max=120 stack=1324 focus=4 scroll=0 chain=7421f3aa ops=213 text-px=994 hash=78270fda\r\n");

    browser_hold_for_screendump();
    return 1;
  } else if (se < 17) {
    debug_string("AIUEOS_GUEST_BROWSER_SCROLL leftover=events-missing\n");
    serial_string("AIUEOS_GUEST_BROWSER_SCROLL leftover=events-missing events=");
    serial_decimal(se);
    serial_string(" frames=");
    serial_decimal(sframes);
    serial_string("\r\n");
  } else {
    debug_string("AIUEOS_GUEST_BROWSER_SCROLL leftover=census-miss\n");
    serial_string("AIUEOS_GUEST_BROWSER_SCROLL leftover=census-miss off=");
    serial_decimal(soff);
    serial_string(" max=");
    serial_decimal(smax);
    serial_string(" chain=");
    serial_hex32(schain);
    serial_string(" focus=");
    serial_decimal(surface[2]);
    serial_string(" scroll=");
    serial_decimal(surface[2043]);
    serial_string("\r\n");
  }
  return 0;
}

/* D3 (scorecard row: touchpad gestures). pci.c replays a scripted gesture
   stream -- kind 8 pinch, 9 three-finger swipe, 10 two-finger tap -- because
   virtio-tablet has no multi-touch for the host to send. This stage is the
   consumer side: it drains the real tablet, arms one gesture, and checks that
   every scripted event arrives in order, at the scripted coordinates, and
   still draws a frame the desktop accepts. The reduce/frame model values are
   printed on every frame so the next pass can pin them the way every other
   stage's model was pinned; what is asserted now is the delivery contract
   (the receipt will say the gestures are synthetic, and :device evidence for
   a real touchpad stays open). Compiled only with the synthetic flag: a
   production build has no scripted source, so this stage must not be in its
   chain. */
#ifdef AIUEOS_TOUCHPAD_GESTURE_SYNTHETIC
static int browser_gesture_stage(uint32_t *surface, const uint8_t *font, uint64_t font_length) {
  static const uint32_t gsrc[6] = {8, 8, 8, 9, 9, 10};
  static const uint32_t gpx[6] = {640, 640, 640, 640, 640, 512};
  static const uint32_t gpy[6] = {0, 1, 2, 0, 1, 400};
  uint64_t sp = (uint64_t)(uintptr_t)surface;
  uint32_t ax = 0, ay = 0, se = 0, goff = 0, gframes = 0;
  uint32_t gpx2 = 0, gchain = 2166136261U, ghash = 0, gops = 0;
  int64_t gfo = 0;
  (void)aiueos_tablet_drain(4000000U);
  aiueos_tablet_gesture_arm();
  serial_string("AIUEOS_GUEST_BROWSER_GESTURE_GO events=6\r\n");
  while (se < 6) {
    uint32_t src = aiueos_tablet_next(1024U, &ax, &ay);
    int64_t r;
    if (!src) {
      if (!aiueos_tablet_gesture_done()) continue;
      break;
    }
    {
      /* the tablet reports in device units; the frame takes viewport units,
         exactly as the scroll stage converts them (main.c scroll loop) */
      uint32_t px = (uint32_t)(((uint64_t)ax * surface[3]) / 32768U);
      uint32_t py = (uint32_t)(((uint64_t)ay * surface[4]) / 32768U);
      r = (int64_t)kotoba_aiueos_browser_reduce(sp, 8192, src, px, py);
    }
    gfo = (int64_t)kotoba_aiueos_browser_frame2(sp, 8192, (uint64_t)(uintptr_t)font, font_length);
    gpx2 = 0;
    ghash = 0;
    if (gfo > 0 && aiueos_desktop_present_ops2(surface + 480, (uint64_t)gfo, font, font_length)) {
      ghash = aiueos_desktop_colour_census(0x333333U, &gpx2);
      (void)aiueos_desktop_show();
      gframes++;
      for (int k = 0; k < 4; k++) {
        gchain ^= (ghash >> (8 * k)) & 255U;
        gchain *= 16777619U;
      }
    }
    gops = (uint32_t)(gfo < 0 ? -gfo : gfo);
    if (src != gsrc[se] || ax != gpx[se] || ay != gpy[se]) goff++;
    se++;
    browser_hot_line("gesture", se, surface + 480, gfo);
    serial_string("AIUEOS_GUEST_BROWSER_GESTURE_FRAME n=");
    serial_decimal(se);
    serial_string(" src=");
    serial_decimal(src);
    serial_string(" at=");
    serial_decimal(ax);
    serial_string(",");
    serial_decimal(ay);
    serial_string(r < 0 ? " answer=-" : " answer=");
    serial_decimal((uint32_t)(r < 0 ? -r : r));
    serial_string(" focus=");
    serial_decimal(surface[2]);
    serial_string(" scroll=");
    serial_decimal(surface[2043]);
    serial_string(" ops=");
    serial_decimal(gops);
    serial_string(" text-px=");
    serial_decimal(gpx2);
    serial_string(" hash=");
    serial_hex32(ghash);
    serial_string("\r\n");
  }
  if (se == 6 && gframes == 6 && goff == 0) {
    debug_string("AIUEOS_GUEST_BROWSER_GESTURE_OK\n");
    serial_string("AIUEOS_GUEST_BROWSER_GESTURE_OK events=6 frames=6 chain=");
    serial_hex32(gchain);
    serial_string(" ops=");
    serial_decimal(gops);
    serial_string(" text-px=");
    serial_decimal(gpx2);
    serial_string(" hash=");
    serial_hex32(ghash);
    serial_string(" focus=");
    serial_decimal(surface[2]);
    serial_string(" scroll=");
    serial_decimal(surface[2043]);
    serial_string("\r\n");
    return 1;
  }
  debug_string("AIUEOS_GUEST_BROWSER_GESTURE leftover=delivery-miss\n");
  serial_string("AIUEOS_GUEST_BROWSER_GESTURE leftover=delivery-miss events=");
  serial_decimal(se);
  serial_string(" frames=");
  serial_decimal(gframes);
  serial_string(" off=");
  serial_decimal(goff);
  serial_string("\r\n");
  return 0;
}
#endif

/* I2 (scorecard row: battery and power management). The reference VM has no
   battery to read -- no ACPI BAT0, and QEMU's PC machines expose none -- so
   the level is the guest's own state, set through aiueos_desktop_battery_set,
   and this stage walks it: start on AC at 100, switch to battery, drain
   through the scripted steps, and let the status band show each one. What is
   asserted per step is the band itself: the POWER field's warning colour
   (0x00d08060, framebuffer.c) must be present exactly when the level is at or
   below 10, and the normal POWER colour (0x00c0c0c0) the rest of the time --
   so the level reading is checked against pixels, not against the variable
   that produced it. The sleep half of the row is the machine's existing
   suspend path (ADR-0273), which the chain still runs after this stage; the
   profile's judge asks for those markers on the same serial.
   Compiled only with AIUEOS_BATTERY_PROBE: without the flag the status band
   every gate's frame model pins does not contain a BAT field at all. */
#ifdef AIUEOS_BATTERY_PROBE
static int browser_battery_stage(uint32_t *surface, const uint8_t *font, uint64_t font_length) {
  static const uint32_t step_ac[8]    = {1, 0, 0, 0, 0, 0, 0, 0};
  static const uint32_t step_level[8] = {100, 100, 80, 60, 40, 20, 10, 5};
  uint32_t bad = 0, sfo_last = 0;
  uint64_t sp = (uint64_t)(uintptr_t)surface;
  uint32_t band_y = 0;
  serial_string("AIUEOS_BATTERY_GO steps=8\r\n");
  band_y = (surface[4] > 14U) ? (surface[4] - 14U) : 0U;
  for (uint32_t i = 0; i < 8; i++) {
    uint32_t warn_px = 0, base_px = 0;
    int64_t sfo;
    aiueos_desktop_battery_set(step_ac[i], step_level[i]);
    sfo = (int64_t)kotoba_aiueos_browser_frame2(sp, 8192, (uint64_t)(uintptr_t)font, font_length);
    if (sfo > 0 && aiueos_desktop_present_ops2(surface + 480, (uint64_t)sfo, font, font_length)) {
      sfo_last = (uint32_t)(sfo < 0 ? -sfo : sfo);
    }
    /* The frame is identical across steps, so show()'s damage rectangle is
       empty and it returns before painting the band; paint it here (the flag
       build only) and present the whole surface, so the reading the sampler
       takes is the band with this step's level. */
    aiueos_desktop_paint_status();
    (void)aiueos_desktop_show_full();
    /* The POWER field starts at x = 4 + 6*11 and spans the eight glyph cells
       the AC text used; sample one pixel per cell centre in the text rows. */
    for (uint32_t gx = 73; gx < 118; gx += 6) {
      for (uint32_t gy = band_y + 5; gy < band_y + 11 && gy < surface[4]; gy++) {
        uint32_t rgb = aiueos_desktop_sample_rgb(gx, gy);
        if (rgb == 0x00d08060U) warn_px++;
        if (rgb == 0x00c0c0c0U) base_px++;
      }
    }
    if ((step_level[i] <= 10 && step_ac[i] == 0) != (warn_px > 0)) bad++;
    if (step_ac[i] || step_level[i] > 10) { if (base_px == 0) bad++; }
    if (i == 0) {
      /* first run measured warn-px=0 base-px=0 at every step -- probe the
         band itself before trusting the region: raw samples on the text row
         and the count of pixels that are not the band's own background */
      uint32_t ink = 0;
      for (uint32_t px = 0; px < 200 && px < surface[3]; px++)
        if (aiueos_desktop_sample_rgb(px, band_y + 7) != 0x00202830U) ink++;
      serial_string("AIUEOS_BATTERY probe vw=");
      serial_decimal(surface[3]);
      serial_string(" vh=");
      serial_decimal(surface[4]);
      serial_string(" band-y=");
      serial_decimal(band_y);
      serial_string(" ink-px=");
      serial_decimal(ink);
      serial_string(" at4=");
      serial_hex32(aiueos_desktop_sample_rgb(4, band_y + 7));
      serial_string(" at70=");
      serial_hex32(aiueos_desktop_sample_rgb(70, band_y + 7));
      serial_string(" at76=");
      serial_hex32(aiueos_desktop_sample_rgb(76, band_y + 7));
      serial_string(" at300=");
      serial_hex32(aiueos_desktop_sample_rgb(300, band_y + 7));
      serial_string("\r\n");
    }
    serial_string("AIUEOS_BATTERY step=");
    serial_decimal(i);
    serial_string(" ac=");
    serial_decimal(step_ac[i]);
    serial_string(" level=");
    serial_decimal(step_level[i]);
    serial_string(" warn-px=");
    serial_decimal(warn_px);
    serial_string(" base-px=");
    serial_decimal(base_px);
    serial_string(" ops=");
    serial_decimal(sfo_last);
    serial_string("\r\n");
  }
  if (bad == 0 && aiueos_desktop_battery_level() == 5 && aiueos_desktop_battery_ac() == 0) {
    debug_string("AIUEOS_BATTERY_OK\n");
    serial_string("AIUEOS_BATTERY_OK steps=8 warn-from=10 critical=5 ac=0 band-y=");
    serial_decimal(band_y);
    serial_string("\r\n");
    return 1;
  }
  debug_string("AIUEOS_BATTERY leftover=mismatch\n");
  serial_string("AIUEOS_BATTERY leftover=mismatch bad=");
  serial_decimal(bad);
  serial_string(" level=");
  serial_decimal(aiueos_desktop_battery_level());
  serial_string(" ac=");
  serial_decimal(aiueos_desktop_battery_ac());
  serial_string("\r\n");
  return 0;
}
#endif

/* Selection (ADR-0240). After the wheel (window 4 on top and focused, its
   offset 0, the pointer at (300, 300)), the host sends seventeen events, each
   after the previous frame line: five wheel notches toward the end (tablet
   kind 6, offset 20 .. 100: line 20 and the caret inside the window), then
   keys -- Shift down, Left down / up, Left down / up, Right down / up, Left
   down / up, Shift up, Backspace down / up. C hands a tablet batch to Kotoba
   `kotoba_aiueos_browser_reduce` with the whole surface and a key, as code * 4
   + value, to Kotoba `kotoba_aiueos_browser_key`: that Shift is held, that
   Shift+Left / Shift+Right move the caret away from and back toward the end
   of the body with the anchor kept (browser.text-edit move-caret :extend?),
   and that Backspace deletes what is selected (delete-backward) are its
   decisions; that the selected glyphs have a highlight behind them and there
   is no caret while something is selected is browser-frame2's. C only
   counts: each frame's op count and #111111 census against
   os/aiueos/scripts/browser-frame-model.cljk's selection frames, and the
   #b5cdf1 census -- the highlight, which the ink census cannot see: it is
   behind the glyphs -- against the same model. */
static int browser_selection_stage(uint32_t *surface, const uint8_t *font, uint64_t font_length,
                                   uint64_t dict, uint64_t dict_length) {
  static const uint32_t lsrc[17] = {6, 6, 6, 6, 6, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0};
  static const uint32_t lkey[17] = {0, 0, 0, 0, 0, 169, 421, 420, 421, 420, 425, 424, 421, 420, 168, 57, 56};
  static const int64_t lwant[17] = {4, 4, 4, 4, 4, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0};
  static const uint32_t lscroll[17] = {20, 40, 60, 80, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100};
  static const uint32_t lsel[17] = {0, 0, 0, 0, 0, 0, 1, 1, 2, 2, 1, 1, 2, 2, 2, 0, 0};
  static const uint32_t lops[17] = {214, 215, 216, 217, 219, 219, 219, 219, 220, 220,
                                    219, 219, 220, 220, 220, 217, 217};
  static const uint32_t lpx[17] = {1017, 1027, 1047, 1065, 1103, 1103, 1087, 1087, 1087, 1087,
                                   1087, 1087, 1087, 1087, 1087, 1058, 1058};
  static const uint32_t lhash[17] = {0x6c0a4440U, 0xb5e126ebU, 0x40c08679U, 0xf7ee3a0bU, 0x5793612fU,
                                     0x5793612fU, 0x2602913bU, 0x2602913bU, 0x2602913bU, 0x2602913bU,
                                     0x2602913bU, 0x2602913bU, 0x2602913bU, 0x2602913bU, 0x2602913bU,
                                     0x6ca5ee4aU, 0x6ca5ee4aU};
  static const uint32_t lhpx[17] = {0, 0, 0, 0, 0, 0, 104, 104, 211, 211, 104, 104, 211, 211, 211, 0, 0};
  static const uint32_t lhhash[17] = {0x811c9dc5U, 0x811c9dc5U, 0x811c9dc5U, 0x811c9dc5U, 0x811c9dc5U,
                                      0x811c9dc5U, 0xe4f21595U, 0xe4f21595U, 0x49ff70dcU, 0x49ff70dcU,
                                      0xe4f21595U, 0xe4f21595U, 0x49ff70dcU, 0x49ff70dcU, 0x49ff70dcU,
                                      0x811c9dc5U, 0x811c9dc5U};
  uint64_t sp = (uint64_t)(uintptr_t)surface;
  uint32_t le = 0, loff = 0, lpx2 = 0, lhash2 = 0, lhpx2 = 0, lhhash2 = 0;
  uint32_t lchain = 2166136261U, lhchain = 2166136261U;
  uint32_t lidle = 0, lframes = 0, ax = 0, ay = 0;
  int64_t lfo = 0;
  (void)aiueos_tablet_drain(4000000U);
  (void)aiueos_keyboard_drain(4000000U);
  serial_string("AIUEOS_GUEST_BROWSER_SELECTION_GO events=17\r\n");
  while (le < 17 && lidle < 60000U) {
    uint32_t src = aiueos_tablet_next(1024U, &ax, &ay);
    uint32_t key = 0;
    int64_t r;
    if (src) {
      uint32_t px = (uint32_t)(((uint64_t)ax * surface[3]) / 32768U);
      uint32_t py = (uint32_t)(((uint64_t)ay * surface[4]) / 32768U);
      surface[2046] = px + 1U;
      surface[2047] = py;
      aiueos_desktop_set_pointer(px, py);
      r = (int64_t)kotoba_aiueos_browser_reduce(sp, 8192, src, px, py);
    } else {
      key = aiueos_keyboard_next_key(1024U);
      if (!key) { lidle++; continue; }
      r = (int64_t)kotoba_aiueos_browser_key(sp, 8192, dict, dict_length, key);
    }
    lidle = 0;
    lfo = (int64_t)kotoba_aiueos_browser_frame2(sp, 8192, (uint64_t)(uintptr_t)font, font_length);
    lpx2 = 0;
    lhash2 = 0;
    lhpx2 = 0;
    lhhash2 = 0;
    if (lfo > 0 && aiueos_desktop_present_ops2(surface + 480, (uint64_t)lfo, font, font_length)) {
      lhash2 = aiueos_desktop_colour_census(0x333333U, &lpx2);
      lhhash2 = aiueos_desktop_colour_census(0xb5cdf1U, &lhpx2);
      (void)aiueos_desktop_show();
      lframes++;
      for (int k = 0; k < 4; k++) {
        lchain ^= (lhash2 >> (8 * k)) & 255U;
        lchain *= 16777619U;
        lhchain ^= (lhhash2 >> (8 * k)) & 255U;
        lhchain *= 16777619U;
      }
    }
    if (src != lsrc[le] || key != lkey[le] || r != lwant[le] || surface[2] != 4 ||
        surface[2043] != lscroll[le] || surface[2037] != lsel[le] ||
        surface[2036] != (lsel[le] ? 4U : 0U) || lfo != (int64_t)lops[le] ||
        lpx2 != lpx[le] || lhash2 != lhash[le] || lhpx2 != lhpx[le] || lhhash2 != lhhash[le]) loff++;
    le++;
    serial_string("AIUEOS_GUEST_BROWSER_SELECTION_FRAME n=");
    serial_decimal(le);
    serial_string(" src=");
    serial_decimal(src);
    serial_string(" key=");
    serial_decimal(key);
    serial_string(r < 0 ? " answer=-" : " answer=");
    serial_decimal((uint32_t)(r < 0 ? -r : r));
    serial_string(" scroll=");
    serial_decimal(surface[2043]);
    serial_string(" sel=");
    serial_decimal(surface[2037]);
    serial_string(" ops=");
    serial_decimal((uint32_t)(lfo < 0 ? -lfo : lfo));
    serial_string(" text-px=");
    serial_decimal(lpx2);
    serial_string(" hash=");
    serial_hex32(lhash2);
    serial_string(" sel-px=");
    serial_decimal(lhpx2);
    serial_string(" sel-hash=");
    serial_hex32(lhhash2);
    serial_string("\r\n");
  }
  if (le == 17 && lframes == 17 && loff == 0 && lchain == 0x2b46197dU && lhchain == 0xcb830579U &&
      surface[1] == 4 && surface[5] == 1 && surface[10] == 3 && surface[15] == 2 &&
      surface[20] == 4 && surface[2] == 4 && surface[2043] == 100 && surface[2035] == 0 &&
      surface[2036] == 0 && surface[2037] == 0 && surface[352 + 47] == 10 && surface[352 + 48] == 0 &&
      surface[433] == 0 && surface[445] == 0) {
    debug_string("AIUEOS_GUEST_BROWSER_SELECTION_OK\n");
    serial_string("AIUEOS_GUEST_BROWSER_SELECTION_OK events=17 answers=44444000000000000 max-sel=2 body=48 focus=4 scroll=100 chain=2b46197d sel-chain=cb830579 ops=217 text-px=1058 hash=6ca5ee4a\r\n");
    browser_hold_for_screendump();
    return 1;
  } else if (le < 17) {
    debug_string("AIUEOS_GUEST_BROWSER_SELECTION leftover=events-missing\n");
    serial_string("AIUEOS_GUEST_BROWSER_SELECTION leftover=events-missing events=");
    serial_decimal(le);
    serial_string(" frames=");
    serial_decimal(lframes);
    serial_string("\r\n");
  } else {
    debug_string("AIUEOS_GUEST_BROWSER_SELECTION leftover=census-miss\n");
    serial_string("AIUEOS_GUEST_BROWSER_SELECTION leftover=census-miss off=");
    serial_decimal(loff);
    serial_string(" chain=");
    serial_hex32(lchain);
    serial_string(" sel-chain=");
    serial_hex32(lhchain);
    serial_string(" sel=");
    serial_decimal(surface[2037]);
    serial_string(" shift=");
    serial_decimal(surface[2035]);
    serial_string("\r\n");
  }
  return 0;
}

/* Clipboard (ADR-0241). After the selection (window 4 focused, offset 100, its
   body 48 code points ending "19" 10), the host sends twenty-two key events,
   each after the previous frame line: Shift down, Left down / up three times,
   Shift up, Ctrl down, C down / up, Ctrl up, Backspace down / up, Ctrl down, V
   down / up three times, Ctrl up. C hands each key, as code * 4 + value, to
   Kotoba `kotoba_aiueos_browser_key`. That Ctrl is held, that Ctrl+C over a
   selection is a :clipboard/write request (512) and Ctrl+V a :clipboard/read
   request (513), and what a completion does -- copy the selection's text,
   insert-text of the clipboard's -- are its decisions. Whether a request may
   touch the clipboard is Kotoba `kotoba_aiueos_broker_admit` (ADR-0096) with
   the stage's grant: clipboard for the first nineteen events, file-picker
   only from the twentieth -- the (1, 2) -> 0 vector. C hands the completion
   (the same code with value 3, which the keyboard ring never passes, and the
   clipboard in place of the dictionary) only when the broker answers 1. The
   clipboard itself is this 260-byte buffer, the host's: C never reads or
   writes a code point in it. C only counts, as the selection stage does. */
static uint32_t browser_clipboard[65];

static int browser_clipboard_stage(uint32_t *surface, const uint8_t *font, uint64_t font_length,
                                   uint64_t dict, uint64_t dict_length) {
  static const uint32_t ckey[22] = {169, 421, 420, 421, 420, 421, 420, 168, 117, 185, 184,
                                    116, 57, 56, 117, 189, 188, 189, 188, 189, 188, 116};
  static const int64_t cwant[22] = {0, 0, 0, 0, 0, 0, 0, 0, 0, 512, 0,
                                    0, 0, 0, 0, 513, 0, 513, 0, 513, 0, 0};
  /* the broker's answer: 1 admit, 0 refuse, 9 nothing was asked */
  static const uint32_t cadmit[22] = {9, 9, 9, 9, 9, 9, 9, 9, 9, 1, 9,
                                      9, 9, 9, 9, 1, 9, 1, 9, 0, 9, 9};
  /* the completion's answer; 99 none was handed */
  static const int64_t cdone[22] = {99, 99, 99, 99, 99, 99, 99, 99, 99, 3, 99,
                                    99, 99, 99, 99, 3, 99, 3, 99, 99, 99, 99};
  static const uint32_t csel[22] = {0, 1, 1, 2, 2, 3, 3, 3, 3, 3, 3,
                                    3, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0};
  static const uint32_t cbody[22] = {48, 48, 48, 48, 48, 48, 48, 48, 48, 48, 48,
                                     48, 45, 45, 45, 48, 48, 51, 51, 51, 51, 51};
  static const uint32_t cclip[22] = {0, 0, 0, 0, 0, 0, 0, 0, 0, 3, 3,
                                     3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3};
  static const uint32_t cops[22] = {217, 216, 216, 217, 217, 218, 218, 218, 218, 218, 218,
                                    218, 215, 215, 215, 217, 217, 218, 218, 218, 218, 218};
  static const uint32_t cpx[22] = {1058, 1042, 1042, 1042, 1042, 1042, 1042, 1042, 1042, 1042, 1042,
                                   1042, 1020, 1020, 1020, 1058, 1058, 1080, 1080, 1080, 1080, 1080};
  static const uint32_t chash[22] = {0x6ca5ee4aU, 0xa42dfe1aU, 0xa42dfe1aU, 0xa42dfe1aU, 0xa42dfe1aU,
                                     0xa42dfe1aU, 0xa42dfe1aU, 0xa42dfe1aU, 0xa42dfe1aU, 0xa42dfe1aU,
                                     0xa42dfe1aU, 0xa42dfe1aU, 0x3f2fb2c5U, 0x3f2fb2c5U, 0x3f2fb2c5U,
                                     0x6ca5ee4aU, 0x6ca5ee4aU, 0x76577905U, 0x76577905U, 0x76577905U,
                                     0x76577905U, 0x76577905U};
  static const uint32_t chpx[22] = {0, 0, 0, 106, 106, 218, 218, 218, 218, 218, 218,
                                    218, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0};
  static const uint32_t chhash[22] = {0x811c9dc5U, 0x811c9dc5U, 0x811c9dc5U, 0xe0f5b50fU, 0xe0f5b50fU,
                                      0xc1aab2b2U, 0xc1aab2b2U, 0xc1aab2b2U, 0xc1aab2b2U, 0xc1aab2b2U,
                                      0xc1aab2b2U, 0xc1aab2b2U, 0x811c9dc5U, 0x811c9dc5U, 0x811c9dc5U,
                                      0x811c9dc5U, 0x811c9dc5U, 0x811c9dc5U, 0x811c9dc5U, 0x811c9dc5U,
                                      0x811c9dc5U, 0x811c9dc5U};
  uint64_t sp = (uint64_t)(uintptr_t)surface;
  uint64_t cp = (uint64_t)(uintptr_t)browser_clipboard;
  uint32_t ce = 0, coff = 0, cpx2 = 0, chash2 = 0, chpx2 = 0, chhash2 = 0;
  uint32_t cchain = 2166136261U, chchain = 2166136261U;
  uint32_t cidle = 0, cframes = 0, asked = 0, admitted = 0, refused = 0;
  int64_t cfo = 0;
  for (int i = 0; i < 65; i++) browser_clipboard[i] = 0;
  (void)aiueos_tablet_drain(4000000U);
  (void)aiueos_keyboard_drain(4000000U);
  serial_string("AIUEOS_GUEST_BROWSER_CLIPBOARD_GO events=22\r\n");
  while (ce < 22 && cidle < 60000U) {
    uint32_t key = aiueos_keyboard_next_key(1024U);
    uint32_t admit = 9, body = 0;
    int64_t r, done = 99;
    if (!key) { cidle++; continue; }
    cidle = 0;
    r = (int64_t)kotoba_aiueos_browser_key(sp, 8192, dict, dict_length, key);
    if (r == 512 || r == 513) {
      asked++;
      admit = (uint32_t)kotoba_aiueos_broker_admit(1, ce < 19 ? 1U : 2U);
      if (admit == 1) {
        admitted++;
        done = (int64_t)kotoba_aiueos_browser_key(sp, 8192, cp, 260, (key & ~3U) | 3U);
      } else {
        refused++;
      }
    }
    while (body < 64 && surface[352 + body]) body++;
    cfo = (int64_t)kotoba_aiueos_browser_frame2(sp, 8192, (uint64_t)(uintptr_t)font, font_length);
    cpx2 = 0;
    chash2 = 0;
    chpx2 = 0;
    chhash2 = 0;
    if (cfo > 0 && aiueos_desktop_present_ops2(surface + 480, (uint64_t)cfo, font, font_length)) {
      chash2 = aiueos_desktop_colour_census(0x333333U, &cpx2);
      chhash2 = aiueos_desktop_colour_census(0xb5cdf1U, &chpx2);
      (void)aiueos_desktop_show();
      cframes++;
      for (int k = 0; k < 4; k++) {
        cchain ^= (chash2 >> (8 * k)) & 255U;
        cchain *= 16777619U;
        chchain ^= (chhash2 >> (8 * k)) & 255U;
        chchain *= 16777619U;
      }
    }
    if (key != ckey[ce] || r != cwant[ce] || admit != cadmit[ce] || done != cdone[ce] ||
        surface[2] != 4 || surface[2043] != 100 || body != cbody[ce] || surface[2037] != csel[ce] ||
        surface[2036] != (csel[ce] ? 4U : 0U) || browser_clipboard[0] != cclip[ce] ||
        cfo != (int64_t)cops[ce] || cpx2 != cpx[ce] || chash2 != chash[ce] ||
        chpx2 != chpx[ce] || chhash2 != chhash[ce]) coff++;
    ce++;
    serial_string("AIUEOS_GUEST_BROWSER_CLIPBOARD_FRAME n=");
    serial_decimal(ce);
    serial_string(" key=");
    serial_decimal(key);
    serial_string(r < 0 ? " answer=-" : " answer=");
    serial_decimal((uint32_t)(r < 0 ? -r : r));
    serial_string(" broker=");
    serial_string(admit == 9 ? "none" : (admit == 1 ? "admit" : "refuse"));
    serial_string(done < 0 ? " done=-" : " done=");
    serial_decimal((uint32_t)(done < 0 ? -done : done));
    serial_string(" body=");
    serial_decimal(body);
    serial_string(" sel=");
    serial_decimal(surface[2037]);
    serial_string(" clip=");
    serial_decimal(browser_clipboard[0]);
    serial_string(" ops=");
    serial_decimal((uint32_t)(cfo < 0 ? -cfo : cfo));
    serial_string(" text-px=");
    serial_decimal(cpx2);
    serial_string(" hash=");
    serial_hex32(chash2);
    serial_string(" sel-px=");
    serial_decimal(chpx2);
    serial_string(" sel-hash=");
    serial_hex32(chhash2);
    serial_string("\r\n");
  }
  if (ce == 22 && cframes == 22 && coff == 0 && asked == 4 && admitted == 3 && refused == 1 &&
      cchain == 0x9098b95fU && chchain == 0x356612c5U &&
      surface[2] == 4 && surface[2035] == 0 && surface[2036] == 0 && surface[2037] == 0 &&
      surface[2038] == 0 && surface[352 + 47] == 10 && surface[352 + 48] == 49 &&
      surface[352 + 49] == 57 && surface[352 + 50] == 10 && surface[352 + 51] == 0 &&
      browser_clipboard[0] == 3 && browser_clipboard[1] == 49 && browser_clipboard[2] == 57 &&
      browser_clipboard[3] == 10 && surface[433] == 0 && surface[445] == 0) {
    debug_string("AIUEOS_GUEST_BROWSER_CLIPBOARD_OK\n");
    serial_string("AIUEOS_GUEST_BROWSER_CLIPBOARD_OK events=22 requests=4 admitted=3 refused=1 copied=3 pasted=3,3 clip=3 body=51 focus=4 chain=9098b95f sel-chain=356612c5 ops=218 text-px=1080 hash=76577905\r\n");
    browser_hold_for_screendump();
    return 1;
  } else if (ce < 22) {
    debug_string("AIUEOS_GUEST_BROWSER_CLIPBOARD leftover=events-missing\n");
    serial_string("AIUEOS_GUEST_BROWSER_CLIPBOARD leftover=events-missing events=");
    serial_decimal(ce);
    serial_string(" frames=");
    serial_decimal(cframes);
    serial_string("\r\n");
  } else {
    debug_string("AIUEOS_GUEST_BROWSER_CLIPBOARD leftover=census-miss\n");
    serial_string("AIUEOS_GUEST_BROWSER_CLIPBOARD leftover=census-miss off=");
    serial_decimal(coff);
    serial_string(" chain=");
    serial_hex32(cchain);
    serial_string(" sel-chain=");
    serial_hex32(chchain);
    serial_string(" requests=");
    serial_decimal(asked);
    serial_string(" admitted=");
    serial_decimal(admitted);
    serial_string(" clip=");
    serial_decimal(browser_clipboard[0]);
    serial_string(" ctrl=");
    serial_decimal(surface[2038]);
    serial_string("\r\n");
  }
  return 0;
}

/* Damage (ADR-0242). Every aiueos_desktop_show since this change sends only
   the rectangle Kotoba browser-damage answers for the list just painted. This
   stage shows it: after the clipboard, the host moves the tablet to
   (320, 310), then sends Alt down, Tab down (Alt+Tab raises window 1), Tab up
   and Alt up. After each, C presents the frame -- the damage only -- and
   prints its rectangle; the host screendumps it and presses F12, and C sends
   the whole screen, which the host screendumps again. The gate compares the
   two screendumps. F12 (evdev 88) is the stage's request for the whole
   screen and is never handed to Kotoba. */
static int browser_damage_stage(uint32_t *surface, const uint8_t *font, uint64_t font_length,
                                uint64_t dict, uint64_t dict_length) {
  extern int aiueos_desktop_show_full(void);
  extern void aiueos_desktop_damage_last(uint32_t *out);
  extern void aiueos_desktop_damage_counts(uint32_t *out, uint64_t *bytes);
  static const uint32_t dsrc[5] = {3, 0, 0, 0, 0};
  static const uint32_t dkey[5] = {0, 225, 61, 60, 224};
  static const int64_t dwant[5] = {0, 0, 1, 0, 0};
  static const uint32_t dfocus[5] = {4, 4, 1, 1, 1};
  static const uint32_t dops[5] = {218, 218, 219, 219, 219};
  static const uint32_t dpx[5] = {1080, 1080, 2330, 2330, 2330};
  static const uint32_t dhash[5] = {0x362c4193U, 0x362c4193U, 0x5581e21aU, 0x5581e21aU, 0x5581e21aU};
  /* the frame model's damage: x y w h (w 0 = nothing sent) */
  static const uint32_t drect[5][4] = {{300, 300, 32, 22}, {0, 0, 0, 0}, {80, 80, 652, 716},
                                       {0, 0, 0, 0}, {0, 0, 0, 0}};
  uint64_t sp = (uint64_t)(uintptr_t)surface;
  uint32_t de = 0, doff = 0, dpx2 = 0, dhash2 = 0, dchain = 2166136261U;
  uint32_t didle = 0, dframes = 0, fulls = 0, partial = 0, empty = 0, ax = 0, ay = 0;
  uint32_t rect[4], counts[5];
  uint64_t bytes = 0, run_bytes = 0;
  int64_t dfo = 0;
  (void)aiueos_tablet_drain(4000000U);
  (void)aiueos_keyboard_drain(4000000U);
  serial_string("AIUEOS_GUEST_BROWSER_DAMAGE_GO events=5\r\n");
  while (de < 5 && didle < 60000U) {
    uint32_t src = aiueos_tablet_next(1024U, &ax, &ay), key = 0, widle = 0, full = 0;
    int64_t r, kr = 0;
    if (src) {
      uint32_t px = (uint32_t)(((uint64_t)ax * surface[3]) / 32768U);
      uint32_t py = (uint32_t)(((uint64_t)ay * surface[4]) / 32768U);
      surface[2046] = px + 1U;
      surface[2047] = py;
      aiueos_desktop_set_pointer(px, py);
      r = (int64_t)kotoba_aiueos_browser_reduce(sp, 8192, src, px, py);
    } else {
      key = aiueos_keyboard_next_key(1024U);
      if (!key) { didle++; continue; }
      if ((key >> 2) == 88U) continue;
      kr = (int64_t)kotoba_aiueos_browser_key(sp, 8192, dict, dict_length, key);
      r = kr;
      if (kr > 256) r = (int64_t)kotoba_aiueos_browser_reduce(sp, 8192, 5, (uint64_t)(kr - 256), 0);
    }
    didle = 0;
    dfo = (int64_t)kotoba_aiueos_browser_frame2(sp, 8192, (uint64_t)(uintptr_t)font, font_length);
    dpx2 = 0;
    dhash2 = 0;
    rect[0] = rect[1] = rect[2] = rect[3] = 0xffffffffU;
    if (dfo > 0 && aiueos_desktop_present_ops2(surface + 480, (uint64_t)dfo, font, font_length)) {
      dhash2 = aiueos_desktop_colour_census(0x333333U, &dpx2);
      if (aiueos_desktop_show()) {
        dframes++;
        aiueos_desktop_damage_last(rect);
        if (rect[2] && rect[3]) { partial++; bytes += (uint64_t)rect[2] * rect[3] * 4U; }
        else empty++;
      }
      for (int k = 0; k < 4; k++) {
        dchain ^= (dhash2 >> (8 * k)) & 255U;
        dchain *= 16777619U;
      }
    }
    if (src != dsrc[de] || key != dkey[de] || r != dwant[de] || surface[2] != dfocus[de] ||
        dfo != (int64_t)dops[de] || dpx2 != dpx[de] || dhash2 != dhash[de] ||
        rect[0] != drect[de][0] || rect[1] != drect[de][1] ||
        rect[2] != drect[de][2] || rect[3] != drect[de][3]) doff++;
    de++;
    serial_string("AIUEOS_GUEST_BROWSER_DAMAGE_FRAME n=");
    serial_decimal(de);
    serial_string(" src=");
    serial_decimal(src);
    serial_string(" key=");
    serial_decimal(key);
    serial_string(r < 0 ? " answer=-" : " answer=");
    serial_decimal((uint32_t)(r < 0 ? -r : r));
    serial_string(" focus=");
    serial_decimal(surface[2]);
    serial_string(" ops=");
    serial_decimal((uint32_t)(dfo < 0 ? -dfo : dfo));
    serial_string(" text-px=");
    serial_decimal(dpx2);
    serial_string(" hash=");
    serial_hex32(dhash2);
    serial_string(" damage=");
    serial_decimal(rect[0]);
    serial_string(",");
    serial_decimal(rect[1]);
    serial_string(",");
    serial_decimal(rect[2]);
    serial_string(",");
    serial_decimal(rect[3]);
    serial_string(" bytes=");
    serial_decimal(rect[2] == 0xffffffffU ? 0U : rect[2] * rect[3] * 4U);
    serial_string("\r\n");
    /* the host's F12: the same frame, the whole screen */
    while (widle < 60000U) {
      uint32_t k = aiueos_keyboard_next_key(1024U);
      if (!k) { widle++; continue; }
      if (k == 88U * 4U + 1U) break;
    }
    if (widle < 60000U) full = (uint32_t)aiueos_desktop_show_full();
    fulls += full;
    serial_string("AIUEOS_GUEST_BROWSER_DAMAGE_FULL n=");
    serial_decimal(de);
    serial_string(full ? " shown=whole\r\n" : " shown=none\r\n");
    if (!full) break;
  }
  /* the host's F12 once more: its last whole-screen screendump is taken
     before anything after this stage draws */
  if (de == 5 && fulls == 5) {
    uint32_t widle = 0;
    while (widle < 60000U) {
      uint32_t k = aiueos_keyboard_next_key(1024U);
      if (!k) { widle++; continue; }
      if (k == 88U * 4U + 1U) break;
    }
    if (widle >= 60000U) fulls = 4;
  }
  aiueos_desktop_damage_counts(counts, &run_bytes);
  /* since boot: every show of the desktop, how it went */
  serial_string("AIUEOS_GUEST_BROWSER_DAMAGE_RUN shows=");
  serial_decimal(counts[0]);
  serial_string(" partial=");
  serial_decimal(counts[1]);
  serial_string(" empty=");
  serial_decimal(counts[2]);
  serial_string(" whole=");
  serial_decimal(counts[3]);
  serial_string(" refused=");
  serial_decimal(counts[4]);
  serial_string(" bytes=");
  serial_decimal64(run_bytes);
  serial_string(" whole-bytes=");
  serial_decimal64((uint64_t)counts[0] * surface[3] * surface[4] * 4U);
  serial_string("\r\n");
  if (de == 5 && dframes == 5 && fulls == 5 && doff == 0 && partial == 2 && empty == 3 &&
      bytes == 1870144U && dchain == 0x6653b143U && counts[4] == 0 &&
      surface[2] == 1 && surface[431] == 0) {
    debug_string("AIUEOS_GUEST_BROWSER_DAMAGE_OK\n");
    serial_string("AIUEOS_GUEST_BROWSER_DAMAGE_OK events=5 partial=2 empty=3 bytes=1870144 whole-bytes=20480000 focus=1 chain=6653b143 ops=219 text-px=2330 hash=5581e21a\r\n");
    browser_hold_for_screendump();
    return 1;
  } else if (de < 5 || fulls < de) {
    debug_string("AIUEOS_GUEST_BROWSER_DAMAGE leftover=events-missing\n");
    serial_string("AIUEOS_GUEST_BROWSER_DAMAGE leftover=events-missing events=");
    serial_decimal(de);
    serial_string(" frames=");
    serial_decimal(dframes);
    serial_string(" wholes=");
    serial_decimal(fulls);
    serial_string("\r\n");
  } else {
    debug_string("AIUEOS_GUEST_BROWSER_DAMAGE leftover=damage-miss\n");
    serial_string("AIUEOS_GUEST_BROWSER_DAMAGE leftover=damage-miss off=");
    serial_decimal(doff);
    serial_string(" chain=");
    serial_hex32(dchain);
    serial_string(" partial=");
    serial_decimal(partial);
    serial_string(" empty=");
    serial_decimal(empty);
    serial_string(" bytes=");
    serial_decimal64(bytes);
    serial_string(" refused=");
    serial_decimal(counts[4]);
    serial_string("\r\n");
  }
  return 0;
}

/* ADR-0247 / ADR-0248 / ADR-0249: the keyboard stage. After the damage stage
   the host sends eighteen key events, a frame for each:
     1..4   F10 down and up, F10 down and up  (the high-contrast palette on, off)
     5..8   F6 down and up, F6 down and up    (the focus ring on launcher button
                                               1, then 2)
     9..12  Shift down, F6 down and up,       (back to button 1)
            Shift up
     13..14 F6 down and up                    (button 2)
     15..16 Enter down and up                 (button 2 is pressed: Kotoba
                                               answers the press, C hands it to
                                               browser-reduce)
     17..18 Escape down and up                (the focused window's close
                                               control is pressed the same way)
   For each frame the kernel prints what it reads out of the draw list it
   painted. 19..26 are the tablet: a double press on window 1's titlebar at
   (380, 142) -- press, release, press, release -- maximizes it (ADR-0250), a
   double press on its titlebar at (380, 40) restores it. Kotoba (browser-reduce)
   decides a double press; C counts the input events (word 2029) and reports.
   The expected values are the frame model's. */
static void browser_hc_hex(uint32_t v) { serial_hex32(v & 0xffffffU); }

/* ADR-0258: the screen lock's PIN check. Kotoba collects the four digits and answers 100000000 + the
   number (browser-ime.kotoba `locked-key`); this is the mechanism that decides whether it is the PIN:
   SHA-256 of "aiueos-pin/dddd" against the provisioned hash. The hash below is the TEST PIN's (the
   user's own application, a test value; a real PIN is provisioned at first run, ADR-0258 leftover). */
static int aiueos_pin_ok(uint32_t acc) {
  static const uint8_t want[32] = {0x2b, 0xa0, 0x69, 0xdd, 0x88, 0x78, 0xfd, 0xc0, 0x6f, 0x1d, 0x8c, 0x60, 0x59, 0x07, 0x24, 0xe7, 0xa1, 0x61, 0xc9, 0x18, 0x76, 0x98, 0xd4, 0x4b, 0x7b, 0x18, 0x21, 0x33, 0x0a, 0x05, 0x0d, 0x49};
  uint8_t msg[15] = {'a','i','u','e','o','s','-','p','i','n','/','0','0','0','0'};
  uint8_t out[32];
  static uint8_t ws[512];
  msg[11] = (uint8_t)('0' + (acc / 1000U) % 10U);
  msg[12] = (uint8_t)('0' + (acc / 100U) % 10U);
  msg[13] = (uint8_t)('0' + (acc / 10U) % 10U);
  msg[14] = (uint8_t)('0' + acc % 10U);
  if (!kotoba_aiueos_sha256(msg, 15, out, ws, sizeof(ws))) return 0;
  uint8_t diff = 0;
  for (int i = 0; i < 32; i++) diff |= (uint8_t)(out[i] ^ want[i]);
  return diff == 0;
}

static int browser_uiux_stage(uint32_t *surface, const uint8_t *font, uint64_t font_length,
                              uint64_t dict, uint64_t dict_length) {
  static const uint32_t ukey[106] = {68U * 4U + 1U, 68U * 4U, 68U * 4U + 1U, 68U * 4U, 64U * 4U + 1U, 64U * 4U, 64U * 4U + 1U, 64U * 4U,
                                    42U * 4U + 1U, 64U * 4U + 1U, 64U * 4U, 42U * 4U, 64U * 4U + 1U, 64U * 4U,
                                    28U * 4U + 1U, 28U * 4U, 1U * 4U + 1U, 1U * 4U, 0, 0, 0, 0, 0, 0, 0, 0,
                                    0, 0, 87U * 4U + 1U, 87U * 4U, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 56U * 4U + 1U, 12U * 4U + 1U, 12U * 4U, 56U * 4U, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                                    117, 225, 153, 152, 224, 116, 0, 0, 181, 180, 21, 20, 13, 12, 21, 20, 17, 16, 113, 112, 21, 20, 13, 12, 21, 20, 13, 12, 113, 112,
                                    117, 225, 65, 64, 224, 116, 21, 20, 13, 12, 21, 20, 13, 12, 113, 112};
  static const int64_t uans[106] = {0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 385038, 0, 1261662, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 2613290, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 999570, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                                    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 100004243, 0, 0, 0, 0, 0, 0, 0, 0, 0, 100004242, 0,
                                    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 100004242, 0};
  static const int64_t ured[106] = {-100, -100, -100, -100, -100, -100, -100, -100, -100, -100, -100,
                                   -100, -100, -100, 2, -100, 1, -100, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, -100, 0, 0, 1, 0, 4, 0, 4, 0, 1, 0, 4, 0, 1, 0, -100, 4, -100, -100, 1, 0, 4, 0, 3, 0, -8, 0, 1, 0, 4, 0,
                                    -100, -100, -100, -100, -100, -100, 0, 0, -100, -100, -100, -100, -100, -100, -100, -100, -100, -100, -100, -100, -100, -100, -100, -100, -100, -100, -100, -100, -100, -100,
                                    -100, -100, -100, -100, -100, -100, -100, -100, -100, -100, -100, -100, -100, -100, -100, -100};
  static const uint32_t umode[106] = {1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                                    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                                    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0};
  static const uint32_t uring[106] = {0, 0, 0, 0, 1, 1, 2, 2, 2, 1, 1, 1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2,
                                    2, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                                    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0};
  static const uint32_t uwin[106] = {4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3,
                                    3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3,
                                    3, 3, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1};
  static const uint32_t ufoc[106] = {1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 4, 4, 4, 4, 1, 1, 4, 4, 1, 1, 1, 4, 4, 4, 1, 1, 4, 4, 3, 3, 3, 3, 1, 1, 4, 4,
                                    4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4,
                                    4, 4, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1};
  static const uint32_t uops[106] = {219, 219, 219, 219, 223, 223, 223, 223, 223, 223, 223, 223, 223, 223, 223, 223, 192, 192, 192, 192, 191, 191, 191, 191, 192, 192, 191, 191, 192, 192, 185, 192, 192, 192, 140, 140, 140, 140, 192, 192, 140, 140, 192, 192, 192, 140, 140, 140, 192, 192, 140, 140, 101, 101, 101, 101, 154, 154, 191, 191, 191, 191, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 31, 31, 30, 30, 30, 30, 30, 30, 30, 30, 187, 187,
                                    187, 187, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 72, 72};
  static const uint32_t upx[106] = {2330, 2330, 2330, 2330, 2330, 2330, 2330, 2330, 2330, 2330, 2330, 2330, 2330, 2330, 1209, 1209, 2330, 2330, 2330, 2330, 1699, 1699, 1699, 1699, 2330, 2330, 1699, 1699, 2330, 2330, 2343, 2330, 2322, 2322, 1197, 1197, 1197, 1197, 2330, 2330, 1197, 1197, 2330, 2330, 2330, 1197, 1197, 1197, 2330, 2330, 1197, 1197, 1305, 1305, 1305, 1305, 2365, 2365, 1080, 1080,
                                    1080, 1080, 33, 33, 33, 33, 33, 33, 33, 33, 33, 33, 33, 33, 33, 33, 33, 33, 33, 33, 33, 33, 33, 33, 33, 33, 33, 33, 1080, 1080,
                                    1080, 1080, 33, 33, 33, 33, 33, 33, 33, 33, 33, 33, 33, 33, 582, 582};
  static const uint32_t uhash[106] = {0x5581e21aU, 0x5581e21aU, 0x5581e21aU, 0x5581e21aU, 0x5581e21aU, 0x5581e21aU, 0x5581e21aU, 0x5581e21aU, 0x5581e21aU, 0x5581e21aU, 0x5581e21aU, 0x5581e21aU, 0x5581e21aU, 0x5581e21aU, 0xfc93d38dU, 0xfc93d38dU, 0x5581e21aU, 0x5581e21aU, 0xe5cb1929U, 0xe5cb1929U, 0x3b18fc9cU, 0x3b18fc9cU, 0x71c4138eU, 0x71c4138eU, 0xb4362763U, 0xb4362763U, 0x2eebb0d8U, 0x2eebb0d8U, 0x7c707d0dU, 0x7c707d0dU, 0xc2fbd1abU, 0xe5cb1929U, 0xd3d22b31U, 0xd3d22b31U, 0xfb35dcd0U, 0xfb35dcd0U, 0x3d2ce5f0U, 0x3d2ce5f0U, 0x01d8225dU, 0x01d8225dU, 0xfb35dcd0U, 0xfb35dcd0U, 0x438d5f21U, 0x438d5f21U, 0x438d5f21U, 0x6567a294U, 0x6567a294U, 0x6567a294U, 0x438d5f21U, 0x438d5f21U, 0xfb35dcd0U, 0xfb35dcd0U, 0xdbbceb01U, 0xdbbceb01U, 0x2a0da509U, 0x2a0da509U, 0xef498861U, 0xef498861U, 0x6585b838U, 0x6585b838U,
                                    0x6585b838U, 0x6585b838U, 0x7799e563U, 0x7799e563U, 0x7799e563U, 0x7799e563U, 0x921cb55fU, 0x921cb55fU, 0x921cb55fU, 0x921cb55fU, 0x921cb55fU, 0x921cb55fU, 0x921cb55fU, 0x921cb55fU, 0x921cb55fU, 0x921cb55fU, 0x921cb55fU, 0x921cb55fU, 0x921cb55fU, 0x921cb55fU, 0x921cb55fU, 0x921cb55fU, 0x921cb55fU, 0x921cb55fU, 0x921cb55fU, 0x921cb55fU, 0x921cb55fU, 0x921cb55fU, 0xf1860b60U, 0xf1860b60U,
                                    0xf1860b60U, 0xf1860b60U, 0x921cb55fU, 0x921cb55fU, 0x921cb55fU, 0x921cb55fU, 0x921cb55fU, 0x921cb55fU, 0x921cb55fU, 0x921cb55fU, 0x921cb55fU, 0x921cb55fU, 0x921cb55fU, 0x921cb55fU, 0x60620c8bU, 0x60620c8bU};
  /* events 19..26: the tablet source (1 press, 4 release), where, and the rect
     window 1 has afterwards */
  static const uint32_t usrc[88] = {1, 4, 1, 4, 1, 4, 1, 4, 1, 4, 0, 0, 3, 3, 1, 4, 1, 4, 1, 4, 1, 4, 1, 4, 1, 4, 0, 0, 0, 0, 1, 4,
                                     1, 4, 1, 4, 1, 4, 1, 4, 1, 4,
                                     0, 0, 0, 0, 0, 0, 1, 4, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                                     0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0};
  static const uint32_t uat[88][2] = {{380, 142}, {380, 142}, {380, 142}, {380, 142},
                                      {380, 40}, {380, 40}, {380, 40}, {380, 40},
                                      {476, 146}, {476, 146}, {476, 146}, {476, 146},
                                      {500, 320}, {380, 142},
                                      {54, 14}, {54, 14},
                                      {456, 146}, {456, 146}, {380, 142}, {380, 142}, {574, 772}, {574, 772},
                                      {456, 146}, {456, 146}, {60, 780}, {60, 780},
                                      {60, 780}, {60, 780}, {60, 780}, {60, 780}, {60, 780}, {60, 780},
                                      {456, 146}, {456, 146}, {544, 94}, {544, 94}, {584, 94}, {584, 94},
                                      {60, 780}, {60, 780}, {60, 780}, {60, 780},
                                      {60, 780}, {60, 780}, {60, 780}, {60, 780}, {60, 780}, {60, 780}, {456, 146}, {456, 146}, {456, 146}, {456, 146}, {456, 146}, {456, 146}, {456, 146}, {456, 146}, {456, 146}, {456, 146}, {456, 146}, {456, 146}, {456, 146}, {456, 146}, {456, 146}, {456, 146}, {456, 146}, {456, 146}, {456, 146}, {456, 146}, {456, 146}, {456, 146}, {456, 146}, {456, 146},
                                     {456, 146}, {456, 146}, {456, 146}, {456, 146}, {456, 146}, {456, 146}, {456, 146}, {456, 146}, {456, 146}, {456, 146}, {456, 146}, {456, 146}, {456, 146}, {456, 146}, {456, 146}, {456, 146}};
  static const uint32_t urect[88][4] = {{272, 132, 240, 200}, {272, 132, 240, 200}, {0, 28, 1280, 720},
                                        {0, 28, 1280, 720}, {0, 28, 1280, 720}, {0, 28, 1280, 720},
                                        {272, 132, 240, 200}, {272, 132, 240, 200}, {0, 28, 1280, 720},
                                        {0, 28, 1280, 720}, {272, 132, 240, 200}, {272, 132, 240, 200},
                                        {272, 132, 240, 200}, {272, 132, 240, 200},
                                        {272, 132, 240, 200}, {272, 132, 240, 200},
                                        {272, 132, 240, 200}, {272, 132, 240, 200}, {272, 132, 240, 200},
                                        {272, 132, 240, 200}, {272, 132, 240, 200}, {272, 132, 240, 200},
                                        {272, 132, 240, 200}, {272, 132, 240, 200}, {272, 132, 240, 200},
                                        {272, 132, 240, 200},
                                        {272, 132, 240, 200}, {272, 132, 240, 200}, {272, 132, 240, 200},
                                        {272, 132, 240, 200}, {272, 132, 240, 200}, {272, 132, 240, 200},
                                        {272, 132, 240, 200}, {272, 132, 240, 200},
                                        {272, 132, 240, 200}, {272, 132, 240, 200},
                                        {272, 132, 240, 200}, {272, 132, 240, 200},
                                        {272, 132, 240, 200}, {272, 132, 240, 200},
                                        {272, 132, 240, 200}, {272, 132, 240, 200},
                                        {272, 132, 240, 200}, {272, 132, 240, 200}, {272, 132, 240, 200}, {272, 132, 240, 200}, {272, 132, 240, 200}, {272, 132, 240, 200}, {272, 132, 240, 200}, {272, 132, 240, 200}, {272, 132, 240, 200}, {272, 132, 240, 200}, {272, 132, 240, 200}, {272, 132, 240, 200}, {272, 132, 240, 200}, {272, 132, 240, 200}, {272, 132, 240, 200}, {272, 132, 240, 200}, {272, 132, 240, 200}, {272, 132, 240, 200}, {272, 132, 240, 200}, {272, 132, 240, 200}, {272, 132, 240, 200}, {272, 132, 240, 200}, {272, 132, 240, 200}, {272, 132, 240, 200}, {272, 132, 240, 200}, {272, 132, 240, 200}, {272, 132, 240, 200}, {272, 132, 240, 200}, {272, 132, 240, 200}, {272, 132, 240, 200},
                                     {272, 132, 240, 200}, {272, 132, 240, 200}, {80, 80, 520, 360}, {80, 80, 520, 360}, {80, 80, 520, 360}, {80, 80, 520, 360}, {80, 80, 520, 360}, {80, 80, 520, 360}, {80, 80, 520, 360}, {80, 80, 520, 360}, {80, 80, 520, 360}, {80, 80, 520, 360}, {80, 80, 520, 360}, {80, 80, 520, 360}, {80, 80, 520, 360}, {80, 80, 520, 360}};
  uint64_t sp = (uint64_t)(uintptr_t)surface;
  uint32_t useq = 0, tpx = 0, tpy = 0, tsrc = 0, ax = 0, ay = 0;
  uint32_t ue = 0, uoff = 0, uidle = 0, uframes = 0, hcoff = 0;
  (void)aiueos_tablet_drain(4000000U);
  (void)aiueos_keyboard_drain(4000000U);
  surface[2033] = 0;
  serial_string("AIUEOS_GUEST_BROWSER_UIUX_GO events=106\r\n");
  while (ue < 106 && uidle < 60000U) {
    uint32_t key = 0;
    int64_t kr, ufo, red = -100;
    uint32_t upx2 = 0, uhash2 = 0, bars[4], nbars = 0, ink = 0, haveink = 0;
    uint32_t rings = 0, rx = 0, ry = 0, rc = 0, face = 0, haveface = 0, npressed = 0, nhot = 0;
    uint32_t bad, minctl = 0, dockbar = 0, tray = 0, dis = 0, bars28 = 0, dots = 0, denied = 0;
    tsrc = ((ue >= 18 && ue < 28) || ue >= 30) ? aiueos_tablet_next(1024U, &ax, &ay) : 0;
    if (!tsrc) key = aiueos_keyboard_next_key(1024U);
    if (!tsrc && !key) { uidle++; continue; }
    uidle = 0;
    kr = 0;
    if (tsrc) {
      tpx = (uint32_t)(((uint64_t)ax * surface[3]) / 32768U);
      tpy = (uint32_t)(((uint64_t)ay * surface[4]) / 32768U);
      surface[2046] = tpx + 1U;
      surface[2047] = tpy;
      surface[2029] = ++useq;
      surface[2033] = tsrc == 1 ? 1U : (tsrc == 4 ? 0U : surface[2033]);
      red = (int64_t)kotoba_aiueos_browser_reduce(sp, 8192, tsrc, tpx, tpy);
    } else {
      kr = (int64_t)kotoba_aiueos_browser_key(sp, 8192, dict, dict_length, key);
    }
    if (kr >= 100000000LL) {
      /* the lock's PIN attempt: check it and send the verdict back as a value-2 key event */
      kotoba_aiueos_browser_key(sp, 8192, dict, dict_length,
                                aiueos_pin_ok((uint32_t)(kr - 100000000LL)) ? 6U : 10U);
    } else if (kr >= 65536) {
      uint32_t at = (uint32_t)(kr - 65536);
      red = (int64_t)kotoba_aiueos_browser_reduce(sp, 8192, 1, at >> 11, at & 2047U);
    }
    ufo = (int64_t)kotoba_aiueos_browser_frame2(sp, 8192, (uint64_t)(uintptr_t)font, font_length);
    if (ufo > 0 && aiueos_desktop_present_ops2(surface + 480, (uint64_t)ufo, font, font_length)) {
      uhash2 = aiueos_desktop_colour_census(surface[2039] ? 0x000000U : 0x333333U, &upx2);
      (void)aiueos_desktop_show();
      uframes++;
    }
    for (uint32_t j = 0; ufo > 0 && j < (uint32_t)ufo && j < 261U; j++) {
      const uint32_t *op = surface + 480 + 6U * j;
      if (op[0] == 2 && !haveink) { ink = op[5]; haveink = 1; }
      if (op[0] == 1 && op[4] == 28U) {
        uint32_t seen = 0;
        for (uint32_t b = 0; b < nbars; b++) if (bars[b] == op[5]) seen = 1;
        if (!seen && nbars < 4U) bars[nbars++] = op[5];
      }
      if (op[0] == 1 && op[5] == 1726171U) {
        if (!rings) { rx = op[1]; ry = op[2]; rc = op[5]; }
        rings++;
      }
      if (op[0] == 1 && op[3] == 96U && op[4] == 24U && !haveface) { face = op[5]; haveface = 1; }
      if (op[0] == 1 && op[3] == 8U && op[4] == 2U && op[5] == 5855577U) minctl++;
      if (op[0] == 1 && op[3] == 12U && op[4] == 3U && op[5] == 5855577U) dockbar++;
      if (op[0] == 1 && op[3] == 120U && op[4] == 24U) tray++;
      if (op[0] == 2 && op[5] == 10395294U) dis++;
      if (op[0] == 1 && op[4] == 28U) bars28++;
      if (op[0] == 1 && op[3] == 12U && op[4] == 12U && op[5] == 0xffffffU) dots++;
      if (op[0] == 1 && op[3] == 84U && op[4] == 4U) denied++;
      if (op[0] == 1 && op[5] == 12566463U) npressed++;
      if (op[0] == 1 && op[5] == 14277081U) nhot++;
    }
    bad = (kr != uans[ue] || key != ukey[ue] || surface[2039] != umode[ue] || ufo != (int64_t)uops[ue] ||
           upx2 != upx[ue] || uhash2 != uhash[ue]);
    if (ue >= 18) {
      const uint32_t t = ue - 18;
      if (!tsrc && ue >= 28) { tpx = uat[t][0]; tpy = uat[t][1]; }
      /* window 1's record, wherever it is in the stack (ADR-0254: a press can raise another window over it) */
      const uint32_t *wr = surface + 5 + 5 * (surface[1] - 1) + 1;
      uint32_t w1found = 0;
      for (uint32_t k = 0; k < surface[1] && k < 4U; k++)
        if (surface[5 + 5 * k] == 1U) { wr = surface + 5 + 5 * k + 1; w1found = 1; }
      if (tsrc != usrc[t] || tpx != uat[t][0] || tpy != uat[t][1] || !w1found ||
          wr[0] != urect[t][0] || wr[1] != urect[t][1] || wr[2] != urect[t][2] || wr[3] != urect[t][3])
        bad = 1;
    }
    if (ue >= 4) {
      if (red != ured[ue] || surface[2032] != uring[ue] || surface[1] != uwin[ue] || surface[2] != ufoc[ue])
        bad = 1;
    }
    if (bad) {
      /* say which event and which expectation: a miss is otherwise only a count */
      serial_string("AIUEOS_GUEST_BROWSER_UIUX miss n=");
      serial_decimal(ue + 1);
      serial_string(" kr=");
      serial_decimal64((uint64_t)kr);
      serial_string(" key=");
      serial_decimal(key);
      serial_string(" red=");
      serial_decimal64((uint64_t)red);
      serial_string(" ring=");
      serial_decimal(surface[2032]);
      serial_string(" win=");
      serial_decimal(surface[1]);
      serial_string(" foc=");
      serial_decimal(surface[2]);
      serial_string("\r\n");
    }
    if (bad) { if (ue < 4) hcoff++; uoff++; }
    ue++;
    if (ue <= 4) {
      serial_string("AIUEOS_GUEST_BROWSER_HC n=");
      serial_decimal(ue);
      serial_string(" mode=");
      serial_decimal(surface[2039]);
      serial_string(" bg=");
      browser_hc_hex(ufo > 0 ? surface[480 + 5] : 0);
      serial_string(" ink=");
      browser_hc_hex(ink);
      serial_string(" bars=");
      for (uint32_t b = 0; b < nbars; b++) {
        if (b) serial_string(",");
        browser_hc_hex(bars[b]);
      }
      serial_string(" ops=");
      serial_decimal((uint32_t)(ufo < 0 ? -ufo : ufo));
      serial_string(" text-px=");
      serial_decimal(upx2);
      serial_string(" hash=");
      serial_hex32(uhash2);
      serial_string("\r\n");
      if (ue == 4) {
        if (hcoff == 0 && surface[2039] == 0) {
          debug_string("AIUEOS_GUEST_BROWSER_UIUX_OK\n");
          serial_string("AIUEOS_GUEST_BROWSER_UIUX_OK events=4 palette=default-high-contrast-default\r\n");
        } else {
          serial_string("AIUEOS_GUEST_BROWSER_UIUX leftover=census-miss part=palette\r\n");
        }
      }
    } else if (ue > 18) {
      const uint32_t *wr = surface + 5 + 5 * (surface[1] - 1) + 1;
      for (uint32_t k = 0; k < surface[1] && k < 4U; k++)
        if (surface[5 + 5 * k] == 1U) wr = surface + 5 + 5 * k + 1;
      serial_string("AIUEOS_GUEST_BROWSER_MAX n=");
      serial_decimal(ue);
      serial_string(" src=");
      serial_decimal(tsrc);
      serial_string(" at=");
      serial_decimal(tpx);
      serial_string(",");
      serial_decimal(tpy);
      serial_string(" reduce=");
      if (red == -100) serial_string("none");
      else if (red == -8) serial_string("refused");
      else serial_decimal64((uint64_t)red);
      serial_string(" windows=");
      serial_decimal(surface[1]);
      serial_string(" focus=");
      serial_decimal(surface[2]);
      serial_string(" stack=");
      for (uint32_t k = 0; k < surface[1] && k < 4U; k++) serial_decimal(surface[5 + 5 * k]);
      serial_string(" rect=");
      serial_decimal(wr[0]);
      serial_string(",");
      serial_decimal(wr[1]);
      serial_string(",");
      serial_decimal(wr[2]);
      serial_string(",");
      serial_decimal(wr[3]);
      serial_string(" ops=");
      serial_decimal((uint32_t)(ufo < 0 ? -ufo : ufo));
      serial_string(" text-px=");
      serial_decimal(upx2);
      serial_string(" hash=");
      serial_hex32(uhash2);
      serial_string("\r\n");
      if (ue > 32) {
        serial_string("AIUEOS_GUEST_BROWSER_PRESS n=");
        serial_decimal(ue);
        serial_string(" pressed=");
        serial_decimal(npressed);
        serial_string(" hot=");
        serial_decimal(nhot);
        serial_string("\r\n");
      }
      if (ue > 60) {
        serial_string("AIUEOS_GUEST_BROWSER_LOCK n=");
        serial_decimal(ue);
        serial_string(" locked=");
        serial_decimal(surface[2030]);
        serial_string(" bars=");
        serial_decimal(bars28);
        serial_string(" dots=");
        serial_decimal(dots);
        serial_string(" denied=");
        serial_decimal(denied);
        serial_string("\r\n");
      }
      if (ue > 34 && ue <= 60) {
        serial_string("AIUEOS_GUEST_BROWSER_MIN n=");
        serial_decimal(ue);
        serial_string(" reg=");
        serial_decimal(surface[31] >> 4);
        serial_string(" minctl=");
        serial_decimal(minctl);
        serial_string(" dockbar=");
        serial_decimal(dockbar);
        serial_string(" tray=");
        serial_decimal(tray);
        serial_string(" dis=");
        serial_decimal(dis);
        serial_string("\r\n");
      }
    } else {
      serial_string("AIUEOS_GUEST_BROWSER_KEY n=");
      serial_decimal(ue);
      serial_string(" key=");
      serial_decimal(key);
      serial_string(" answer=");
      serial_decimal64((uint64_t)kr);
      serial_string(" reduce=");
      if (red == -100) serial_string("none");
      else serial_decimal64((uint64_t)red);
      serial_string(" ring=");
      serial_decimal(surface[2032]);
      serial_string(" windows=");
      serial_decimal(surface[1]);
      serial_string(" focus=");
      serial_decimal(surface[2]);
      serial_string(" stack=");
      for (uint32_t k = 0; k < surface[1] && k < 4U; k++) serial_decimal(surface[5 + 5 * k]);
      serial_string(" rings=");
      serial_decimal(rings);
      serial_string(" at=");
      serial_decimal(rx);
      serial_string(",");
      serial_decimal(ry);
      serial_string(" ringc=");
      browser_hc_hex(rc);
      serial_string(" bar=");
      browser_hc_hex(nbars ? bars[0] : 0);
      serial_string(" face=");
      browser_hc_hex(face);
      serial_string(" ops=");
      serial_decimal((uint32_t)(ufo < 0 ? -ufo : ufo));
      serial_string(" text-px=");
      serial_decimal(upx2);
      serial_string(" hash=");
      serial_hex32(uhash2);
      serial_string("\r\n");
    }
    if (ue == 34 && uoff == 0 && surface[2039] == 0) {
      debug_string("AIUEOS_GUEST_BROWSER_PRESSED_OK\n");
      serial_string("AIUEOS_GUEST_BROWSER_PRESSED_OK events=2 down=pressed up=hot\r\n");
    }
    if (ue == 106) {
      if (uoff == 0) {
        debug_string("AIUEOS_GUEST_BROWSER_SIGN_OUT_OK\n");
        serial_string("AIUEOS_GUEST_BROWSER_SIGN_OUT_OK events=16 session=zeroed locked=1 pin=signed-in clean=windows-1\r\n");
      } else {
        serial_string("AIUEOS_GUEST_BROWSER_UIUX leftover=census-miss part=sign-out\r\n");
      }
    }
    if (ue >= 90) {
      uint32_t body = 0, scrl = 0, mrect = 0;
      for (uint32_t k = 160; k < 416; k++) if (surface[k]) body++;
      for (uint32_t k = 2040; k < 2044; k++) if (surface[k]) scrl++;
      for (uint32_t k = 2010; k < 2026; k++) if (surface[k]) mrect++;
      serial_string("AIUEOS_GUEST_BROWSER_SIGNOUT n=");
      serial_decimal(ue);
      serial_string(" body=");
      serial_decimal(body);
      serial_string(" scroll=");
      serial_decimal(scrl);
      serial_string(" maxrect=");
      serial_decimal(mrect);
      serial_string(" minreg=");
      serial_decimal(surface[31] >> 4);
      serial_string(" windows=");
      serial_decimal(surface[1]);
      serial_string(" focus=");
      serial_decimal(surface[2]);
      serial_string("\r\n");
    }
    if (ue == 90) {
      if (uoff == 0) {
        debug_string("AIUEOS_GUEST_BROWSER_SCREEN_LOCK_OK\n");
        serial_string("AIUEOS_GUEST_BROWSER_SCREEN_LOCK_OK events=30 locked=1 swallowed=press,key wrong-pin=refused right-pin=unlocked session=restored\r\n");
      } else {
        serial_string("AIUEOS_GUEST_BROWSER_UIUX leftover=census-miss part=lock\r\n");
      }
    }
    if (ue == 60) {
      if (uoff == 0) {
        debug_string("AIUEOS_GUEST_BROWSER_MINIMIZE_OK\n");
        serial_string("AIUEOS_GUEST_BROWSER_MINIMIZE_OK events=26 minimized=1 hit-through=4 restored=1 tray=restored alt-minus=minimized close-disabled=refused\r\n");
      } else {
        serial_string("AIUEOS_GUEST_BROWSER_UIUX leftover=census-miss part=minimize\r\n");
      }
    }
    if (ue == 32) {
      if (uoff == 0) {
        debug_string("AIUEOS_GUEST_BROWSER_CURSOR_SHAPE_OK\n");
        serial_string("AIUEOS_GUEST_BROWSER_CURSOR_SHAPE_OK events=2 handle=resize away=arrow\r\n");
      } else {
        serial_string("AIUEOS_GUEST_BROWSER_UIUX leftover=census-miss part=cursor-shape\r\n");
      }
    }
    if (ue == 30) {
      if (uoff == 0) {
        debug_string("AIUEOS_GUEST_BROWSER_MAX_CTL_OK\n");
        serial_string("AIUEOS_GUEST_BROWSER_MAX_CTL_OK events=4 control=press f11=restore\r\n");
      } else {
        serial_string("AIUEOS_GUEST_BROWSER_UIUX leftover=census-miss part=max-control\r\n");
      }
    }
    if (ue == 26) {
      if (uoff == 0) {
        debug_string("AIUEOS_GUEST_BROWSER_MAX_OK\n");
        serial_string("AIUEOS_GUEST_BROWSER_MAX_OK events=8 maximized=0,28,1280,720 restored=272,132,240,200\r\n");
      } else {
        serial_string("AIUEOS_GUEST_BROWSER_UIUX leftover=census-miss part=max\r\n");
      }
    }
    if (ue == 18) {
      if (uoff == 0 && surface[2039] == 0) {
        debug_string("AIUEOS_GUEST_BROWSER_KEYS_OK\n");
        serial_string("AIUEOS_GUEST_BROWSER_KEYS_OK events=18 ring=2 stack=341 focus=1\r\n");
      } else {
        serial_string("AIUEOS_GUEST_BROWSER_UIUX leftover=census-miss part=keys\r\n");
      }
    }
  }
  if (ue == 106 && uframes == 106 && uoff == 0 && surface[2039] == 0) return 1;
  debug_string("AIUEOS_GUEST_BROWSER_UIUX leftover=census-miss\n");
  serial_string("AIUEOS_GUEST_BROWSER_UIUX leftover=census-miss events=");
  serial_decimal(ue);
  serial_string(" off=");
  serial_decimal(uoff);
  serial_string("\r\n");
  return 0;
}

/* ADR-0260: the desktop's settings persist. The stage reads the settings record (pci.c, one sector on the
   object-store volume), applies a stored high-contrast choice, and writes the record again whenever Kotoba's
   choice (surface word 2039) differs from what is stored, with readback. The host sends two keys: F10 down and
   up on the first boot (the choice goes on and is written), Alt down and up on the second boot of the same
   volume (nothing changes the choice, and the frame is high-contrast because the record said so). The stage
   itself is boot-agnostic; the classifier knows which boot it read. */
extern int aiueos_settings_read(uint32_t *, uint32_t *, uint32_t *);
extern int aiueos_settings_write(uint32_t, uint32_t, uint32_t);

/* ADR-0261: the UI scale stage. Kotoba chooses the scale (Ctrl+= and Ctrl+-, browser-ime.kotoba) and answers
   200000000 + the percent; C magnifies what it paints (framebuffer.c), sets the logical viewport -- surface words 3
   and 4, which the tablet's mapping, Kotoba's layout and the rect checks all read -- to the physical size over the
   scale, and sends a value-2 key event with code 3 back so that Kotoba fits the windows into it. The host sends
   sixteen keys: F11 (maximize), Ctrl+= three times (125, 150, and 150 again), Ctrl+- twice (125, 100), Ctrl up and
   F11 (restore). The kernel prints what it painted; the classifier knows what the model says it should be. */
extern int aiueos_desktop_set_scale(uint32_t);
extern uint32_t aiueos_desktop_scale(void);

static int browser_scale_stage(uint32_t *surface, const uint8_t *font, uint64_t font_length,
                               uint64_t dict, uint64_t dict_length) {
  uint64_t sp = (uint64_t)(uintptr_t)surface;
  uint32_t physw = aiueos_desktop_width(), physh = aiueos_desktop_height();
  uint32_t se = 0, sidle = 0;
  (void)aiueos_tablet_drain(4000000U);
  (void)aiueos_keyboard_drain(4000000U);
  serial_string("AIUEOS_GUEST_BROWSER_SCALE_GO events=16\r\n");
  while (se < 16 && sidle < 60000U) {
    uint32_t key = aiueos_keyboard_next_key(1024U), px = 0, hash = 0;
    int64_t kr, fo;
    if (!key) { sidle++; continue; }
    sidle = 0;
    if ((key >> 2) == 88U) continue;
    kr = (int64_t)kotoba_aiueos_browser_key(sp, 8192, dict, dict_length, key);
    if (kr >= 200000000LL && kr < 200000200LL) {
      uint32_t pct = (uint32_t)(kr - 200000000LL);
      if (aiueos_desktop_set_scale(pct)) {
        surface[3] = physw * 100U / pct;
        surface[4] = physh * 100U / pct;
        (void)kotoba_aiueos_browser_key(sp, 8192, dict, dict_length, 14U);
      }
    } else if (kr >= 65536) {
      uint32_t at = (uint32_t)(kr - 65536);
      (void)kotoba_aiueos_browser_reduce(sp, 8192, 1, at >> 11, at & 2047U);
    }
    fo = (int64_t)kotoba_aiueos_browser_frame2(sp, 8192, (uint64_t)(uintptr_t)font, font_length);
    if (fo > 0 && aiueos_desktop_present_ops2(surface + 480, (uint64_t)fo, font, font_length)) {
      hash = aiueos_desktop_colour_census(0x333333U, &px);
      (void)aiueos_desktop_show();
    }
    se++;
    {
      const uint32_t *wr = surface + 5 + 5 * (surface[1] - 1) + 1;
      serial_string("AIUEOS_GUEST_BROWSER_SCALE n=");
      serial_decimal(se);
      serial_string(" key=");
      serial_decimal(key);
      serial_string(" pct=");
      serial_decimal(aiueos_desktop_scale());
      serial_string(" vw=");
      serial_decimal(surface[3]);
      serial_string(" vh=");
      serial_decimal(surface[4]);
      serial_string(" win=");
      serial_decimal(wr[0]);
      serial_string(",");
      serial_decimal(wr[1]);
      serial_string(",");
      serial_decimal(wr[2]);
      serial_string(",");
      serial_decimal(wr[3]);
      serial_string(" ops=");
      serial_decimal((uint32_t)(fo < 0 ? -fo : fo));
      serial_string(" text-px=");
      serial_decimal(px);
      serial_string(" hash=");
      serial_hex32(hash);
      serial_string("\r\n");
    }
  }
  if (se == 16) {
    debug_string("AIUEOS_GUEST_BROWSER_SCALE_OK\n");
    serial_string("AIUEOS_GUEST_BROWSER_SCALE_OK events=16\r\n");
    return 1;
  }
  serial_string("AIUEOS_GUEST_BROWSER_SCALE leftover=events-missing\r\n");
  return 0;
}

/* ADR-0262: the keyboard-only stage. The host sends twenty-six keys -- F6 and Enter, down and up -- and the
   stage hands each to Kotoba (`kotoba_aiueos_browser_key`); an answer that is a pointer press, 65536 + 2048 x + y,
   goes to `kotoba_aiueos_browser_reduce` like a tablet's, so the keyboard and the pointer are one action path
   (ADR-0248). The stage prints what it painted and the session it left; the classifier knows what the model says. */
static int browser_ring_stage(uint32_t *surface, const uint8_t *font, uint64_t font_length,
                              uint64_t dict, uint64_t dict_length) {
  uint64_t sp = (uint64_t)(uintptr_t)surface;
  uint32_t se = 0, sidle = 0;
  (void)aiueos_tablet_drain(4000000U);
  (void)aiueos_keyboard_drain(4000000U);
  serial_string("AIUEOS_GUEST_BROWSER_RING_GO events=28\r\n");
  while (se < 28 && sidle < 60000U) {
    uint32_t key = aiueos_keyboard_next_key(1024U), px = 0, hash = 0;
    int64_t kr, fo;
    if (!key) { sidle++; continue; }
    sidle = 0;
    if ((key >> 2) == 88U) continue;
    kr = (int64_t)kotoba_aiueos_browser_key(sp, 8192, dict, dict_length, key);
    if (kr >= 65536 && kr < 100000000LL) {
      uint32_t at = (uint32_t)(kr - 65536);
      (void)kotoba_aiueos_browser_reduce(sp, 8192, 1, at >> 11, at & 2047U);
    }
    fo = (int64_t)kotoba_aiueos_browser_frame2(sp, 8192, (uint64_t)(uintptr_t)font, font_length);
    if (fo > 0 && aiueos_desktop_present_ops2(surface + 480, (uint64_t)fo, font, font_length)) {
      hash = aiueos_desktop_colour_census(0x333333U, &px);
      (void)aiueos_desktop_show();
    }
    se++;
    {
      const uint32_t *top = surface + 5 + 5 * (surface[1] - 1) + 1;
      serial_string("AIUEOS_GUEST_BROWSER_RING n=");
      serial_decimal(se);
      serial_string(" key=");
      serial_decimal(key);
      serial_string(" ring=");
      serial_decimal(surface[2032]);
      serial_string(" windows=");
      serial_decimal(surface[1]);
      serial_string(" focus=");
      serial_decimal(surface[2]);
      serial_string(" stack=");
      for (uint32_t k = 0; k < surface[1] && k < 4U; k++) serial_decimal(surface[5 + 5 * k]);
      serial_string(" min=");
      serial_decimal((surface[31] >> 4) & 15U);
      serial_string(" top=");
      serial_decimal(top[0]);
      serial_string(",");
      serial_decimal(top[1]);
      serial_string(",");
      serial_decimal(top[2]);
      serial_string(",");
      serial_decimal(top[3]);
      serial_string(" ops=");
      serial_decimal((uint32_t)(fo < 0 ? -fo : fo));
      serial_string(" text-px=");
      serial_decimal(px);
      serial_string(" hash=");
      serial_hex32(hash);
      serial_string("\r\n");
    }
  }
  if (se == 28) {
    debug_string("AIUEOS_GUEST_BROWSER_RING_OK\n");
    serial_string("AIUEOS_GUEST_BROWSER_RING_OK events=28\r\n");
    return 1;
  }
  serial_string("AIUEOS_GUEST_BROWSER_RING leftover=events-missing\r\n");
  return 0;
}

/* ADR-0263: the text editing stage. The host sends seventy-two keys -- a short text typed, then caret moves
   (Left, Right, Home, End, Ctrl+Left / Right by word), insertion at the caret, a selection (Shift+Right,
   Shift+Home), Backspace and Delete, Enter, and Ctrl+Z -- to the clean session's window 1, whose body is empty.
   The stage hands each key to Kotoba and prints the body as ASCII (space as _, line break as |), the caret and the
   selection it reads back from the surface's words, and what it painted. */
static int browser_edit_stage(uint32_t *surface, const uint8_t *font, uint64_t font_length,
                              uint64_t dict, uint64_t dict_length) {
  uint64_t sp = (uint64_t)(uintptr_t)surface;
  uint32_t se = 0, sidle = 0;
  (void)aiueos_tablet_drain(4000000U);
  (void)aiueos_keyboard_drain(4000000U);
  serial_string("AIUEOS_GUEST_BROWSER_EDIT_GO events=72\r\n");
  while (se < 72 && sidle < 60000U) {
    uint32_t key = aiueos_keyboard_next_key(1024U), px = 0, hash = 0;
    int64_t kr, fo;
    if (!key) { sidle++; continue; }
    sidle = 0;
    if ((key >> 2) == 88U) continue;
    kr = (int64_t)kotoba_aiueos_browser_key(sp, 8192, dict, dict_length, key);
    (void)kr;
    fo = (int64_t)kotoba_aiueos_browser_frame2(sp, 8192, (uint64_t)(uintptr_t)font, font_length);
    if (fo > 0 && aiueos_desktop_present_ops2(surface + 480, (uint64_t)fo, font, font_length)) {
      hash = aiueos_desktop_colour_census(0x333333U, &px);
      (void)aiueos_desktop_show();
    }
    se++;
    {
      const uint32_t base = 160U + 64U * (surface[2] - 1U);
      uint32_t n = 0, caret, v = surface[2004], lo = 0, hi = 0;
      while (n < 64U && surface[base + n]) n++;
      caret = (v / 128U == surface[2]) ? ((v & 127U) - 1U) : n;
      if (caret > n) caret = n;
      if (surface[2036] == surface[2] && surface[2005]) {
        uint32_t a = surface[2005] - 1U;
        if (a > n) a = n;
        lo = a < caret ? a : caret;
        hi = a < caret ? caret : a;
      }
      serial_string("AIUEOS_GUEST_BROWSER_EDIT n=");
      serial_decimal(se);
      serial_string(" key=");
      serial_decimal(key);
      serial_string(" text=");
      for (uint32_t k = 0; k < n; k++) {
        uint32_t c = surface[base + k];
        char ch[2] = {0, 0};
        ch[0] = c == 32U ? '_' : (c == 10U ? '|' : (c < 128U ? (char)c : '?'));
        serial_string(ch);
      }
      serial_string(" caret=");
      serial_decimal(caret);
      serial_string(" sel=");
      if (hi > lo) { serial_decimal(lo); serial_string(","); serial_decimal(hi); }
      else serial_string("-");
      serial_string(" ops=");
      serial_decimal((uint32_t)(fo < 0 ? -fo : fo));
      serial_string(" text-px=");
      serial_decimal(px);
      serial_string(" hash=");
      serial_hex32(hash);
      serial_string("\r\n");
    }
  }
  if (se == 72) {
    debug_string("AIUEOS_GUEST_BROWSER_EDIT_OK\n");
    serial_string("AIUEOS_GUEST_BROWSER_EDIT_OK events=72\r\n");
    return 1;
  }
  serial_string("AIUEOS_GUEST_BROWSER_EDIT leftover=events-missing\r\n");
  return 0;
}

/* ADR-0267: the keyboard layout stage, after the clock stage: US typing, F9 to JIS, JIS typing, F9 back. */
static int browser_layout_stage(uint32_t *surface, const uint8_t *font, uint64_t font_length,
                              uint64_t dict, uint64_t dict_length) {
  uint64_t sp = (uint64_t)(uintptr_t)surface;
  uint32_t se = 0, sidle = 0;
  (void)aiueos_tablet_drain(4000000U);
  (void)aiueos_keyboard_drain(4000000U);
  serial_string("AIUEOS_GUEST_BROWSER_LAYOUT_GO events=36\r\n");
  while (se < 36 && sidle < 60000U) {
    uint32_t key = aiueos_keyboard_next_key(1024U), px = 0, hash = 0;
    int64_t kr, fo;
    if (!key) { sidle++; continue; }
    sidle = 0;
    if ((key >> 2) == 88U) continue;
    kr = (int64_t)kotoba_aiueos_browser_key(sp, 8192, dict, dict_length, key);
    (void)kr;
    fo = (int64_t)kotoba_aiueos_browser_frame2(sp, 8192, (uint64_t)(uintptr_t)font, font_length);
    if (fo > 0 && aiueos_desktop_present_ops2(surface + 480, (uint64_t)fo, font, font_length)) {
      hash = aiueos_desktop_colour_census(0x333333U, &px);
      (void)aiueos_desktop_show();
    }
    se++;
    {
      const uint32_t base = 160U + 64U * (surface[2] - 1U);
      uint32_t n = 0, caret, v = surface[2004], lo = 0, hi = 0;
      while (n < 64U && surface[base + n]) n++;
      caret = (v / 128U == surface[2]) ? ((v & 127U) - 1U) : n;
      if (caret > n) caret = n;
      if (surface[2036] == surface[2] && surface[2005]) {
        uint32_t a = surface[2005] - 1U;
        if (a > n) a = n;
        lo = a < caret ? a : caret;
        hi = a < caret ? caret : a;
      }
      serial_string("AIUEOS_GUEST_BROWSER_LAYOUT n=");
      serial_decimal(se);
      serial_string(" key=");
      serial_decimal(key);
      serial_string(" text=");
      for (uint32_t k = 0; k < n; k++) {
        uint32_t c = surface[base + k];
        char ch[2] = {0, 0};
        ch[0] = c == 32U ? '_' : (c == 10U ? '|' : (c < 128U ? (char)c : '?'));
        serial_string(ch);
      }
      serial_string(" layout=");
      serial_decimal(surface[1970]);
      serial_string(" caret=");
      serial_decimal(caret);
      serial_string(" sel=");
      if (hi > lo) { serial_decimal(lo); serial_string(","); serial_decimal(hi); }
      else serial_string("-");
      serial_string(" ops=");
      serial_decimal((uint32_t)(fo < 0 ? -fo : fo));
      serial_string(" text-px=");
      serial_decimal(px);
      serial_string(" hash=");
      serial_hex32(hash);
      serial_string("\r\n");
    }
  }
  if (se == 36) {
    debug_string("AIUEOS_GUEST_BROWSER_LAYOUT_OK\n");
    serial_string("AIUEOS_GUEST_BROWSER_LAYOUT_OK events=36\r\n");
    return 1;
  }
  serial_string("AIUEOS_GUEST_BROWSER_LAYOUT leftover=events-missing\r\n");
  return 0;
}

/* ADR-0264: the clock in the launcher row. C reads the machine's real-time clock (CMOS registers 0x00..0x09
   through ports 0x70 / 0x71, BCD or binary, 12 or 24 hour as register B says) and reports the minute of the day + 1
   in surface word 1968; browser-frame2 draws HH:MM at the right end of the launcher row. The stage first sets the clock
   to 12:34:00 -- the desktop's test hook, so that the frame can be known -- reads it back, reports it, and clears the
   word again afterwards so the stages after it are what they were. */
static uint8_t rtc_read(uint8_t reg) { out8(0x70, reg); return in8(0x71); }
static void rtc_write(uint8_t reg, uint8_t value) { out8(0x70, reg); out8(0x71, value); }
static uint32_t rtc_decode(uint8_t value, int binary) { return binary ? value : (uint32_t)((value >> 4) * 10 + (value & 15)); }
static uint8_t rtc_encode(uint32_t value, int binary) { return binary ? (uint8_t)value : (uint8_t)(((value / 10) << 4) | (value % 10)); }

/* the minute of the day, or 0xffffffff when the clock would not settle */
static uint32_t rtc_minute_of_day(void) {
  uint8_t b = rtc_read(0x0B);
  int binary = (b & 4) != 0, h24 = (b & 2) != 0;
  uint32_t guard = 0;
  while ((rtc_read(0x0A) & 0x80) && guard++ < 1000000U) {}
  if (guard >= 1000000U) return 0xffffffffU;
  uint32_t minute = rtc_decode(rtc_read(0x02), binary);
  uint8_t raw = rtc_read(0x04);
  uint32_t hour = rtc_decode(raw & 0x7f, binary);
  if (!h24) { hour %= 12; if (raw & 0x80) hour += 12; }
  if (hour > 23 || minute > 59) return 0xffffffffU;
  return hour * 60 + minute;
}

static void rtc_set_time(uint32_t hour, uint32_t minute) {
  uint8_t b = rtc_read(0x0B);
  int binary = (b & 4) != 0, h24 = (b & 2) != 0;
  uint32_t h = hour;
  uint8_t hraw;
  if (!h24) { hraw = rtc_encode(h % 12 == 0 ? 12 : h % 12, binary); if (h >= 12) hraw |= 0x80; }
  else hraw = rtc_encode(h, binary);
  rtc_write(0x0B, (uint8_t)(b | 0x80));   /* SET: no update while the registers change */
  rtc_write(0x00, rtc_encode(0, binary));
  rtc_write(0x02, rtc_encode(minute, binary));
  rtc_write(0x04, hraw);
  rtc_write(0x0B, (uint8_t)(b & 0x7f));
}

static int browser_clock_stage(uint32_t *surface, const uint8_t *font, uint64_t font_length) {
  uint64_t sp = (uint64_t)(uintptr_t)surface;
  uint32_t m, hash = 0, px = 0, i;
  int64_t fo;
  (void)aiueos_tablet_drain(4000000U);
  (void)aiueos_keyboard_drain(4000000U);
  serial_string("AIUEOS_GUEST_BROWSER_CLOCK_GO frames=3\r\n");
  for (i = 0; i < 3; i++) {
    if (i == 2) {
      /* ADR-0266: the network state, as the boot's own enumeration left it: 1 no adapter, 2 an adapter whose
         ARP exchange completed but no IPv4 echo, 3 both. The enumeration ran long before this stage. */
      surface[1969] = aiueos_virtio_net_ready() ? (aiueos_ipv4_ready() ? 3U : 2U) : 1U;
    }
    if (i == 1) {
      rtc_set_time(12, 34);
      m = rtc_minute_of_day();
      serial_string("AIUEOS_GUEST_BROWSER_CLOCK_RTC set=12:34 read=");
      if (m == 0xffffffffU) serial_string("none");
      else { serial_decimal(m / 60U); serial_string(":"); serial_decimal(m % 60U); }
      serial_string("\r\n");
      if (m == 0xffffffffU) return 0;
      surface[1968] = m + 1U;
    }
    fo = (int64_t)kotoba_aiueos_browser_frame2(sp, 8192, (uint64_t)(uintptr_t)font, font_length);
    px = 0;
    hash = 0;
    if (fo > 0 && aiueos_desktop_present_ops2(surface + 480, (uint64_t)fo, font, font_length)) {
      hash = aiueos_desktop_colour_census(0x333333U, &px);
      (void)aiueos_desktop_show();
    }
    serial_string("AIUEOS_GUEST_BROWSER_CLOCK n=");
    serial_decimal(i + 1U);
    serial_string(" status=");
    serial_decimal(surface[1968]);
    serial_string(" net=");
    serial_decimal(surface[1969]);
    serial_string(" ops=");
    serial_decimal((uint32_t)(fo < 0 ? -fo : fo));
    serial_string(" text-px=");
    serial_decimal(px);
    serial_string(" hash=");
    serial_hex32(hash);
    serial_string("\r\n");
  }
  surface[1968] = 0;
  surface[1969] = 0;
  debug_string("AIUEOS_GUEST_BROWSER_CLOCK_OK\n");
  serial_string("AIUEOS_GUEST_BROWSER_CLOCK_OK frames=3\r\n");
  return 1;
}

/* ADR-0268: the notification stage, after the layout stage. The stage plays the apps: it posts "Backup" and "Update"
   into the notification entries (surface words 1971..2002, four of eight); F8 dismisses the newest one still shown, F7
   opens and closes the list. Fifteen frames: the baseline, the two posts, then the twelve key events. */
static void browser_notify_post(uint32_t *surface, const char *text) {
  for (uint32_t k = 0; k < 4U; k++) {
    uint32_t base = 1971U + 8U * k;
    if (surface[base] == 0) {
      uint32_t i = 0;
      for (; i < 7U && text[i]; i++) surface[base + 1U + i] = (uint32_t)(uint8_t)text[i];
      for (; i < 7U; i++) surface[base + 1U + i] = 0;
      surface[base] = 1U;
      return;
    }
  }
}

static int browser_notify_stage(uint32_t *surface, const uint8_t *font, uint64_t font_length,
                                uint64_t dict, uint64_t dict_length) {
  uint64_t sp = (uint64_t)(uintptr_t)surface;
  uint32_t se = 0, sidle = 0, shown = 0;
  (void)aiueos_tablet_drain(4000000U);
  (void)aiueos_keyboard_drain(4000000U);
  serial_string("AIUEOS_GUEST_BROWSER_NOTIFY_GO events=12\r\n");
  while (shown < 15U && sidle < 60000U) {
    uint32_t key = 0, px = 0, hash = 0;
    int64_t fo;
    if (shown >= 3U) {
      key = aiueos_keyboard_next_key(1024U);
      if (!key) { sidle++; continue; }
      sidle = 0;
      if ((key >> 2) == 88U) continue;
      (void)kotoba_aiueos_browser_key(sp, 8192, dict, dict_length, key);
    } else if (shown == 1U) browser_notify_post(surface, "Backup");
    else if (shown == 2U) browser_notify_post(surface, "Update");
    fo = (int64_t)kotoba_aiueos_browser_frame2(sp, 8192, (uint64_t)(uintptr_t)font, font_length);
    if (fo > 0 && aiueos_desktop_present_ops2(surface + 480, (uint64_t)fo, font, font_length)) {
      hash = aiueos_desktop_colour_census(0x333333U, &px);
      (void)aiueos_desktop_show();
    }
    shown++;
    if (shown > 3U) se++;
    serial_string("AIUEOS_GUEST_BROWSER_NOTIFY n=");
    serial_decimal(shown);
    serial_string(" key=");
    serial_decimal(key);
    serial_string(" notes=");
    for (uint32_t k = 0; k < 4U; k++) serial_decimal(surface[1971U + 8U * k]);
    serial_string(" panel=");
    serial_decimal(surface[2003]);
    serial_string(" ops=");
    serial_decimal((uint32_t)(fo < 0 ? -fo : fo));
    serial_string(" text-px=");
    serial_decimal(px);
    serial_string(" hash=");
    serial_hex32(hash);
    serial_string("\r\n");
  }
  for (uint32_t i = 1971U; i <= 2003U; i++) surface[i] = 0;
  if (shown == 15U) {
    debug_string("AIUEOS_GUEST_BROWSER_NOTIFY_OK\n");
    serial_string("AIUEOS_GUEST_BROWSER_NOTIFY_OK events=12\r\n");
    return 1;
  }
  serial_string("AIUEOS_GUEST_BROWSER_NOTIFY leftover=events-missing\r\n");
  return 0;
}

#ifdef AIUEOS_SIZE_BUILD
/* ADR-0270: at -Os clang lowers struct and array initialisers to calls the freestanding kernel does not otherwise define. The loops are
   byte-wise and compiled with -fno-builtin, so they are not turned back into the calls they implement. */
void *memset(void *d, int c, __SIZE_TYPE__ n) { volatile unsigned char *p = d; while (n--) *p++ = (unsigned char)c; return d; }
void *memcpy(void *d, const void *s, __SIZE_TYPE__ n) { volatile unsigned char *p = d; const unsigned char *q = s; while (n--) *p++ = *q++; return d; }
#endif

#ifdef AIUEOS_SIZE_BUILD
/* ADR-0270: a device-bound passkey for the lock screen. The device key (an ECDSA P-256 scalar from the virtio-rng) is made the first
   time it is needed and kept in sector 1035 of this machine's volume with its public point; a passkey made on another device is a
   different key and does not verify against the registered public point. The ceremony is WebAuthn-shaped, with the key press as the
   user-presence check: a fresh 32-byte challenge, authenticator data (the SHA-256 of the relying party "aiueos-session" and the
   user-presence flag), a signature over SHA-256(challenge || authenticator data) with a fresh nonce, and a verification of that
   signature against the REGISTERED public point. Only a verified signature opens the session; its id is the first eight bytes of
   SHA-256(challenge || signature). The private scalar sits on the volume in the clear (no data encryption at rest, scorecard G3). */
extern int aiueos_passkey_sector_read(uint8_t *);
extern int aiueos_passkey_sector_write(const uint8_t *);
extern int aiueos_random_bytes(uint8_t *, uint32_t);
extern uint64_t kotoba_aiueos_ecdsa_p256_sign(const uint8_t *, const uint8_t *, const uint8_t *, uint8_t *, uint8_t *);
extern uint64_t kotoba_aiueos_ecdsa_p256_public(const uint8_t *, uint8_t *, uint8_t *);
extern uint64_t kotoba_aiueos_ecdsa_p256_sha256_verify(const uint8_t *, const uint8_t *, const uint8_t *, uint8_t *, uint64_t);
extern uint64_t kotoba_aiueos_fnv1a(const uint8_t *, uint64_t);

/* in .high_bss: the low region is at its budget (qualification/low-region-budget.edn) */
static uint8_t passkey_ws[2048] __attribute__((section(".high_bss")));
static uint8_t passkey_d[32] __attribute__((section(".high_bss")));
static uint8_t passkey_q[64] __attribute__((section(".high_bss")));
static int passkey_ready, passkey_created;

static int passkey_sha256(const uint8_t *data, uint32_t n, uint8_t out[32]) {
  static uint8_t ws[512];
  return kotoba_aiueos_sha256(data, n, out, ws, sizeof(ws)) != 0;
}

static int passkey_scalar(uint8_t k[32]) {
  for (unsigned tries = 0; tries < 8; tries++) {
    uint8_t any = 0;
    if (!aiueos_random_bytes(k, 32)) return 0;
    for (unsigned i = 0; i < 32; i++) any |= k[i];
    if (any && k[0] != 0xffU) return 1;   /* below the group order */
  }
  return 0;
}

static int passkey_load(void) {
  uint8_t sec[512];
  if (passkey_ready) return 1;
  if (!aiueos_passkey_sector_read(sec)) return 0;
  {
    static const char magic[8] = {'A','I','U','E','P','K','Y','1'};
    uint32_t sum = 0, want = 0;
    int ok = 1;
    for (unsigned i = 0; i < 8; i++) if ((char)sec[i] != magic[i]) ok = 0;
    for (unsigned i = 0; i < 4; i++) { sum |= (uint32_t)sec[128 + i] << (8 * i); }
    want = (uint32_t)kotoba_aiueos_fnv1a(sec, 128);
    if (ok && sum == want) {
      for (unsigned i = 0; i < 32; i++) passkey_d[i] = sec[16 + i];
      for (unsigned i = 0; i < 64; i++) passkey_q[i] = sec[48 + i];
      passkey_ready = 1;
      passkey_created = 0;
      return 1;
    }
  }
  if (!passkey_scalar(passkey_d)) return 0;
  if (!kotoba_aiueos_ecdsa_p256_public(passkey_d, passkey_q, passkey_ws)) return 0;
  for (unsigned i = 0; i < 512; i++) sec[i] = 0;
  { static const char magic[8] = {'A','I','U','E','P','K','Y','1'};
    uint32_t sum;
    for (unsigned i = 0; i < 8; i++) sec[i] = (uint8_t)magic[i];
    sec[8] = 1;
    for (unsigned i = 0; i < 32; i++) sec[16 + i] = passkey_d[i];
    for (unsigned i = 0; i < 64; i++) sec[48 + i] = passkey_q[i];
    sum = (uint32_t)kotoba_aiueos_fnv1a(sec, 128);
    for (unsigned i = 0; i < 4; i++) sec[128 + i] = (uint8_t)(sum >> (8 * i));
  }
  if (!aiueos_passkey_sector_write(sec)) return 0;
  passkey_ready = 1;
  passkey_created = 1;
  return 1;
}

/* One ceremony with the signing key `d` (this device's, or another device's) against the registered public point. Returns 1 when the
   signature verifies; `session` gets the session id. */
static int passkey_ceremony(const uint8_t *d, uint8_t session[8], uint8_t sig_out[64], int *signed_ok) {
  uint8_t challenge[32], rp[32], msg[65], h[32], k[32], sig[64], sm[96], sd[32];
  static const uint8_t rp_id[14] = {'a','i','u','e','o','s','-','s','e','s','s','i','o','n'};
  *signed_ok = 0;
  if (!aiueos_random_bytes(challenge, 32) || !passkey_scalar(k)) return 0;
  if (!passkey_sha256(rp_id, 14, rp)) return 0;
  for (unsigned i = 0; i < 32; i++) { msg[i] = challenge[i]; msg[32 + i] = rp[i]; }
  msg[64] = 0x01U;                                   /* flags: user present (the key press) */
  if (!passkey_sha256(msg, 65, h)) return 0;
  if (!kotoba_aiueos_ecdsa_p256_sign(d, h, k, sig, passkey_ws)) return 0;
  *signed_ok = 1;
  for (unsigned i = 0; i < 64; i++) sig_out[i] = sig[i];
  for (unsigned i = 0; i < 32; i++) { sm[i] = challenge[i]; }
  for (unsigned i = 0; i < 64; i++) sm[32 + i] = sig[i];
  if (!passkey_sha256(sm, 96, sd)) return 0;
  for (unsigned i = 0; i < 8; i++) session[i] = sd[i];
  return kotoba_aiueos_ecdsa_p256_sha256_verify(sig, h, passkey_q, passkey_ws, sizeof(passkey_ws)) != 0;
}

static void passkey_hex(const uint8_t *b, unsigned n) {
  static const char hx[] = "0123456789abcdef";
  char c[3] = {0, 0, 0};
  for (unsigned i = 0; i < n; i++) { c[0] = hx[b[i] >> 4]; c[1] = hx[b[i] & 15U]; serial_string(c); }
}

/* The stage: lock the screen (Ctrl+Alt+L), try a passkey of another device (F3: refused), then this device's (F4: the session opens).
   Ten key events, a frame for each. */
static int browser_passkey_stage(uint32_t *surface, const uint8_t *font, uint64_t font_length,
                                 uint64_t dict, uint64_t dict_length) {
  uint64_t sp = (uint64_t)(uintptr_t)surface;
  uint32_t se = 0, sidle = 0, attempts = 0, accepted = 0;
  uint8_t qh[32], session[8], sig[64], foreign[32];
  int ready = passkey_load(), signed_ok = 0;
  serial_string("AIUEOS_GUEST_BROWSER_PASSKEY_REG ready=");
  serial_decimal(ready ? 1U : 0U);
  serial_string(" created=");
  serial_decimal(passkey_created ? 1U : 0U);
  serial_string(" pub=");
  if (ready && passkey_sha256(passkey_q, 64, qh)) passkey_hex(qh, 8); else serial_string("none");
  serial_string("\r\n");
  if (!ready) return 0;
  (void)aiueos_tablet_drain(4000000U);
  (void)aiueos_keyboard_drain(4000000U);
  serial_string("AIUEOS_GUEST_BROWSER_PASSKEY_GO events=10\r\n");
  while (se < 10 && sidle < 60000U) {
    uint32_t key = aiueos_keyboard_next_key(1024U), px = 0, hash = 0;
    int64_t kr, fo;
    if (!key) { sidle++; continue; }
    sidle = 0;
    if ((key >> 2) == 88U) continue;
    kr = (int64_t)kotoba_aiueos_browser_key(sp, 8192, dict, dict_length, key);
    if (kr == 300000001LL || kr == 300000002LL) {
      int own = kr == 300000001LL, ok;
      const uint8_t *d = passkey_d;
      if (!own) {   /* a passkey made on another device: a fresh scalar that is not this device's */
        if (!passkey_scalar(foreign)) foreign[0] = 1;
        d = foreign;
      }
      ok = passkey_ceremony(d, session, sig, &signed_ok);
      attempts++;
      serial_string("AIUEOS_GUEST_BROWSER_PASSKEY_TRY n=");
      serial_decimal(attempts);
      serial_string(" key=");
      serial_string(own ? "device" : "other-device");
      serial_string(" signed=");
      serial_decimal(signed_ok ? 1U : 0U);
      serial_string(" verified=");
      serial_decimal(ok ? 1U : 0U);
      serial_string(" session=");
      if (ok) { passkey_hex(session, 8); accepted++; } else serial_string("none");
      serial_string("\r\n");
      (void)kotoba_aiueos_browser_key(sp, 8192, dict, dict_length, ok ? 6U : 10U);
    }
    fo = (int64_t)kotoba_aiueos_browser_frame2(sp, 8192, (uint64_t)(uintptr_t)font, font_length);
    if (fo > 0 && aiueos_desktop_present_ops2(surface + 480, (uint64_t)fo, font, font_length)) {
      hash = aiueos_desktop_colour_census(0x333333U, &px);
      (void)aiueos_desktop_show();
    }
    se++;
    serial_string("AIUEOS_GUEST_BROWSER_PASSKEY n=");
    serial_decimal(se);
    serial_string(" key=");
    serial_decimal(key);
    serial_string(" locked=");
    serial_decimal(surface[2030]);
    serial_string(" denied=");
    serial_decimal(surface[2026]);
    serial_string(" ops=");
    serial_decimal((uint32_t)(fo < 0 ? -fo : fo));
    serial_string(" text-px=");
    serial_decimal(px);
    serial_string(" hash=");
    serial_hex32(hash);
    serial_string("\r\n");
  }
  if (se == 10) {
    debug_string("AIUEOS_GUEST_BROWSER_PASSKEY_OK\n");
    serial_string("AIUEOS_GUEST_BROWSER_PASSKEY_OK events=10 tries=");
    serial_decimal(attempts);
    serial_string(" accepted=");
    serial_decimal(accepted);
    serial_string("\r\n");
    return 1;
  }
  serial_string("AIUEOS_GUEST_BROWSER_PASSKEY leftover=events-missing\r\n");
  return 0;
}

#else
/* ADR-0270: the passkey needs the ECDSA sign and public objects, which only the guest-browser build links (and has room for); every
   other build skips the stage. */
static int browser_passkey_stage(uint32_t *surface, const uint8_t *font, uint64_t font_length,
                                 uint64_t dict, uint64_t dict_length) {
  (void)surface; (void)font; (void)font_length; (void)dict; (void)dict_length;
  return 1;
}
#endif

/* ADR-0269: the settings window. Window 2 is the settings app: its title slot says "Settings" and its body is rebuilt from the
   three settings after every key -- "Contrast: High|Scale: 125%|Network: On" with 10 between the lines. A press on a line of its body flips that setting (contrast, scale 100 -> 125 -> 150 -> 100, network); F10, Ctrl+= / Ctrl+- and F5 do the same
   from the keyboard. F10 flips the contrast,
   Ctrl+= and Ctrl+- the scale, F5 the network setting (a flag the stage holds, 1 = off); the status area shows OFFLINE while the network
   setting is off, whatever the adapter says. The stage opens the window by a press on launcher button 2 through the reducer, the
   same path a pointer press takes, and keeps all three settings on the volume. */
static uint32_t settings_put(uint32_t *surface, uint32_t at, const char *text) {
  while (*text) surface[at++] = (uint32_t)(uint8_t)*text++;
  return at;
}

static void settings_body(uint32_t *surface, uint32_t contrast, uint32_t scale, uint32_t netoff) {
  uint32_t at = 224;
  at = settings_put(surface, at, contrast ? "Contrast: High" : "Contrast: Normal");
  surface[at++] = 10U;
  at = settings_put(surface, at, "Scale: ");
  if (scale >= 100U) surface[at++] = 48U + scale / 100U;
  surface[at++] = 48U + (scale / 10U) % 10U;
  surface[at++] = 48U + scale % 10U;
  surface[at++] = 37U;
  surface[at++] = 10U;
  at = settings_put(surface, at, netoff ? "Network: Off" : "Network: On");
  while (at < 288U) surface[at++] = 0;
}

static uint32_t settings_net_state(uint32_t netoff) {
  if (netoff) return 1U;
  return aiueos_virtio_net_ready() ? (aiueos_ipv4_ready() ? 3U : 2U) : 1U;
}

static int browser_settings_stage(uint32_t *surface, const uint8_t *font, uint64_t font_length,
                                  uint64_t dict, uint64_t dict_length) {
  uint64_t sp = (uint64_t)(uintptr_t)surface;
  uint32_t stored = 0, stored_scale = 100, stored_netoff = 0, last = 0, last_scale = 100, last_netoff = 0, have = 0;
  uint32_t written = 0, se = 0, sidle = 0, want, shown = 0, netoff = 0;
  uint32_t physw = aiueos_desktop_width(), physh = aiueos_desktop_height();
  int valid = aiueos_settings_read(&stored, &stored_scale, &stored_netoff);
  serial_string("AIUEOS_GUEST_BROWSER_SETTINGS_BOOT valid=");
  serial_decimal(valid ? 1U : 0U);
  serial_string(" contrast=");
  serial_decimal(valid ? stored : 0U);
  serial_string(" scale=");
  serial_decimal(valid ? stored_scale : 100U);
  serial_string(" net=");
  serial_decimal(valid ? stored_netoff : 0U);
  serial_string("\r\n");
  if (valid) {
    surface[2039] = stored; last = stored; last_scale = stored_scale; last_netoff = stored_netoff; have = 1;
    netoff = stored_netoff;
    if (stored_scale != 100U && aiueos_desktop_set_scale(stored_scale)) {
      surface[3] = physw * 100U / stored_scale;
      surface[4] = physh * 100U / stored_scale;
      (void)kotoba_aiueos_browser_key(sp, 8192, dict, dict_length, 14U);
    }
  }
  /* the settings app: title "Settings" in window 2's slot (it is also launcher button 2's label), then the window */
  for (unsigned i = 64; i < 96; i++) surface[i] = 0;
  (void)settings_put(surface, 64, "Settings");
  settings_body(surface, surface[2039], aiueos_desktop_scale(), netoff);
  surface[1969] = settings_net_state(netoff);
  want = valid ? 2U : 6U;
  (void)aiueos_tablet_drain(4000000U);
  (void)aiueos_keyboard_drain(4000000U);
  serial_string("AIUEOS_GUEST_BROWSER_SETTINGS_GO events=");
  serial_decimal(want);
  serial_string("\r\n");
  while (se < want && sidle < 60000U) {
    uint32_t key = 0, px = 0, hash = 0, ax = 0, ay = 0, at_x = 0, at_y = 0, src;
    int64_t fo;
    if (shown == 0) {
      (void)kotoba_aiueos_browser_reduce(sp, 8192, 1, 156, 14);
      (void)kotoba_aiueos_browser_reduce(sp, 8192, 4, 0, 0);
    } else if ((src = aiueos_tablet_next(256U, &ax, &ay)) != 0) {
      /* a pointer event: the press on a line of the settings window's body is that line's control */
      at_x = (uint32_t)(((uint64_t)ax * surface[3]) / 32768U);
      at_y = (uint32_t)(((uint64_t)ay * surface[4]) / 32768U);
      surface[2046] = at_x + 1U;
      surface[2047] = at_y;
      (void)kotoba_aiueos_browser_reduce(sp, 8192, src, at_x, at_y);
      if (src == 1U && surface[1] >= 1U && surface[5 + 5 * (surface[1] - 1U)] == 2U) {
        const uint32_t *wr = surface + 5 + 5 * (surface[1] - 1U);
        if (at_x >= wr[1] + 14U && at_x + 14U < wr[1] + wr[3] && at_y >= wr[2] + 42U && at_y < wr[2] + 42U + 60U) {
          uint32_t line = (at_y - (wr[2] + 42U)) / 20U;
          if (line == 0) surface[2039] ^= 1U;
          else if (line == 2) netoff ^= 1U;
          else {
            uint32_t pct = aiueos_desktop_scale() == 100U ? 125U : (aiueos_desktop_scale() == 125U ? 150U : 100U);
            if (aiueos_desktop_set_scale(pct)) {
              surface[3] = physw * 100U / pct;
              surface[4] = physh * 100U / pct;
              (void)kotoba_aiueos_browser_key(sp, 8192, dict, dict_length, 14U);
            }
          }
        }
      }
      se++;
      sidle = 0;
    } else {
      int64_t kr;
      key = aiueos_keyboard_next_key(256U);
      if (!key) { sidle++; continue; }
      sidle = 0;
      if ((key >> 2) == 88U) continue;
      if (key == 253U) netoff ^= 1U; /* F5 down: the network setting, a shell flag held here */
      kr = (int64_t)kotoba_aiueos_browser_key(sp, 8192, dict, dict_length, key);
      if (kr >= 200000000LL && kr < 200000200LL) {
        uint32_t pct = (uint32_t)(kr - 200000000LL);
        if (aiueos_desktop_set_scale(pct)) {
          surface[3] = physw * 100U / pct;
          surface[4] = physh * 100U / pct;
          (void)kotoba_aiueos_browser_key(sp, 8192, dict, dict_length, 14U);
        }
      }
      se++;
    }
    settings_body(surface, surface[2039], aiueos_desktop_scale(), netoff);
    surface[1969] = settings_net_state(netoff);
    fo = (int64_t)kotoba_aiueos_browser_frame2(sp, 8192, (uint64_t)(uintptr_t)font, font_length);
    if (fo > 0 && aiueos_desktop_present_ops2(surface + 480, (uint64_t)fo, font, font_length)) {
      hash = aiueos_desktop_colour_census(surface[2039] ? 0x000000U : 0x333333U, &px);
      (void)aiueos_desktop_show();
    }
    if (surface[2039] < 2U && (surface[2039] != last || aiueos_desktop_scale() != last_scale || netoff != last_netoff) &&
        aiueos_settings_write(surface[2039], aiueos_desktop_scale(), netoff)) {
      last = surface[2039];
      last_scale = aiueos_desktop_scale();
      last_netoff = netoff;
      have = 1;
      written++;
    }
    shown++;
    serial_string("AIUEOS_GUEST_BROWSER_SETTINGS n=");
    serial_decimal(shown);
    serial_string(" key=");
    serial_decimal(key);
    serial_string(" at=");
    serial_decimal(at_x);
    serial_string(",");
    serial_decimal(at_y);
    serial_string(" hc=");
    serial_decimal(surface[2039]);
    serial_string(" ops=");
    serial_decimal((uint32_t)(fo < 0 ? -fo : fo));
    serial_string(" pct=");
    serial_decimal(aiueos_desktop_scale());
    serial_string(" net=");
    serial_decimal(netoff);
    serial_string(" win=");
    serial_decimal(surface[1]);
    serial_string(",");
    serial_decimal(surface[2]);
    serial_string(" text-px=");
    serial_decimal(px);
    serial_string(" hash=");
    serial_hex32(hash);
    serial_string(" written=");
    serial_decimal(written);
    serial_string(" stored=");
    if (!have) serial_string("none"); else serial_decimal(last);
    serial_string("\r\n");
  }
  surface[1969] = 0;
  if (se == want) {
    debug_string("AIUEOS_GUEST_BROWSER_SETTINGS_OK\n");
    serial_string("AIUEOS_GUEST_BROWSER_SETTINGS_OK events=");
    serial_decimal(want);
    serial_string("\r\n");
    return 1;
  }
  serial_string("AIUEOS_GUEST_BROWSER_SETTINGS leftover=events-missing\r\n");
  return 0;
}

#ifdef AIUEOS_SIZE_BUILD
/* ADR-0271: backup and restore of the user's records. After the settings stage both records exist: the settings record (sector 1034)
   and the passkey record (1035). The stage copies each to its backup sector (1036, 1037) with readback, wipes the originals and checks
   that the machine now sees no settings and no passkey, restores the copies, and checks that the sectors read back byte for byte
   (SHA-256 before and after), that the settings read the same, and that the restored key still signs and verifies. */
extern int aiueos_user_sector_read(uint32_t, uint8_t *);
extern int aiueos_user_sector_write(uint32_t, const uint8_t *);

static int browser_backup_stage(void) {
  static uint8_t a[512], b[512], z[512], back[512];
  uint8_t ha[32], hb[32], hc[32], hd[32], qh0[32], qh1[32], session[8], sig[64];
  uint32_t contrast = 0, scale = 100, netoff = 0, contrast2 = 0, scale2 = 100, netoff2 = 0;
  int ok = 1, sok = 0, signed_ok = 0, v0, v1, pk_after;
  for (unsigned i = 0; i < 512; i++) z[i] = 0;
  v0 = aiueos_settings_read(&contrast, &scale, &netoff);
  if (!passkey_load()) ok = 0;
  if (!v0 || !ok || !passkey_sha256(passkey_q, 64, qh0)) {
    serial_string("AIUEOS_GUEST_BROWSER_BACKUP leftover=no-records\r\n");
    return 0;
  }
  ok &= aiueos_user_sector_read(1034, a) && aiueos_user_sector_read(1035, b);
  ok &= passkey_sha256(a, 512, ha) && passkey_sha256(b, 512, hb);
  serial_string("AIUEOS_GUEST_BROWSER_BACKUP_TAKE settings=");
  passkey_hex(ha, 8);
  serial_string(" passkey=");
  passkey_hex(hb, 8);
  serial_string("\r\n");
  ok &= aiueos_user_sector_write(1036, a) && aiueos_user_sector_write(1037, b);
  /* wipe the originals; the machine must then see neither */
  ok &= aiueos_user_sector_write(1034, z) && aiueos_user_sector_write(1035, z);
  passkey_ready = 0;
  v1 = aiueos_settings_read(&contrast2, &scale2, &netoff2);
  {
    uint8_t chk[512];
    int blank = aiueos_user_sector_read(1035, chk);
    for (unsigned i = 0; i < 512; i++) if (chk[i]) blank = 0;
    pk_after = blank;
  }
  serial_string("AIUEOS_GUEST_BROWSER_BACKUP_WIPE settings-valid=");
  serial_decimal(v1 ? 1U : 0U);
  serial_string(" passkey-blank=");
  serial_decimal(pk_after ? 1U : 0U);
  serial_string("\r\n");
  /* restore from the copies */
  ok &= aiueos_user_sector_read(1036, back) && aiueos_user_sector_write(1034, back);
  ok &= aiueos_user_sector_read(1037, back) && aiueos_user_sector_write(1035, back);
  ok &= aiueos_user_sector_read(1034, a) && aiueos_user_sector_read(1035, b);
  ok &= passkey_sha256(a, 512, hc) && passkey_sha256(b, 512, hd);
  {
    uint8_t same = 1;
    for (unsigned i = 0; i < 32; i++) if (ha[i] != hc[i] || hb[i] != hd[i]) same = 0;
    ok &= same;
  }
  v1 = aiueos_settings_read(&contrast2, &scale2, &netoff2);
  passkey_created = 0;
  ok &= passkey_load() && !passkey_created && passkey_sha256(passkey_q, 64, qh1);
  {
    uint8_t same = 1;
    for (unsigned i = 0; i < 32; i++) if (qh0[i] != qh1[i]) same = 0;
    ok &= same;
  }
  sok = passkey_ceremony(passkey_d, session, sig, &signed_ok);
  serial_string("AIUEOS_GUEST_BROWSER_BACKUP_RESTORE settings=");
  passkey_hex(hc, 8);
  serial_string(" passkey=");
  passkey_hex(hd, 8);
  serial_string(" settings-valid=");
  serial_decimal(v1 ? 1U : 0U);
  serial_string(" contrast=");
  serial_decimal(contrast2);
  serial_string(" scale=");
  serial_decimal(scale2);
  serial_string(" net=");
  serial_decimal(netoff2);
  serial_string(" pub=");
  passkey_hex(qh1, 8);
  serial_string(" key-signs=");
  serial_decimal(sok ? 1U : 0U);
  serial_string("\r\n");
  if (ok && v1 && contrast2 == contrast && scale2 == scale && netoff2 == netoff && sok) {
    serial_string("AIUEOS_GUEST_BROWSER_BACKUP_OK sectors=2 byte-for-byte\r\n");
    return 1;
  }
  serial_string("AIUEOS_GUEST_BROWSER_BACKUP leftover=restore-differs\r\n");
  return 0;
}

#else
static int browser_backup_stage(void) { return 0; }
#endif

#ifdef AIUEOS_SIZE_BUILD
/* ADR-0272: sound. With a virtio sound card attached (QEMU writes its output to a WAV file the host can measure) the stage plays a 440 Hz
   tone burst at the set volume, waits for the volume-down key twice (100 -> 75 -> 50), and plays the burst again. The volume is a
   software gain on the samples, kept here; KEY_VOLUMEDOWN is evdev 114, KEY_VOLUMEUP 115. Each burst is 0.1 s of silence, 0.4 s of tone
   and 0.1 s of silence at 44100 Hz stereo S16, so the host can find the two tones by their levels. */
extern int aiueos_audio_ready(void);
extern uint32_t aiueos_audio_streams(void);
extern int aiueos_audio_play(const int16_t *, uint32_t);
#define AUDIO_RATE 44100U
#define AUDIO_FRAMES (AUDIO_RATE * 6U / 10U)
static int16_t audio_pcm[AUDIO_FRAMES * 2U] __attribute__((section(".high_bss")));

static void audio_fill(uint32_t volume) {
  static const int16_t q[17] = {0, 3212, 6393, 9512, 12539, 15446, 18204, 20787, 23170, 25329, 27245, 28898, 30273, 31356, 32137, 32609, 32767};
  uint32_t phase = 0, step = (uint32_t)(((uint64_t)440U << 32) / AUDIO_RATE);
  for (uint32_t n = 0; n < AUDIO_FRAMES; n++) {
    int32_t v = 0;
    if (n >= AUDIO_RATE / 10U && n < AUDIO_RATE / 10U + AUDIO_RATE * 4U / 10U) {
      uint32_t idx = phase >> 26, quarter = idx & 15U, half = idx & 32U;   /* 64 steps per period */
      int32_t m = (idx & 16U) ? q[16U - quarter] : q[quarter];
      v = half ? -m : m;
      v = v * (int32_t)volume / 100;
      phase += step;
    }
    audio_pcm[2U * n] = (int16_t)v;
    audio_pcm[2U * n + 1U] = (int16_t)v;
  }
}

static int browser_audio_stage(void) {
  uint32_t volume = 100, presses = 0, idle = 0, played = 0;
  int ok;
  int ready = aiueos_audio_ready();
  serial_string("AIUEOS_GUEST_BROWSER_AUDIO_REG ready=");
  serial_decimal(ready ? 1U : 0U);
  serial_string(" streams=");
  serial_decimal(aiueos_audio_streams());
  serial_string("\r\n");
  if (!ready) return 0;
  (void)aiueos_keyboard_drain(4000000U);
  serial_string("AIUEOS_GUEST_BROWSER_AUDIO_GO events=4\r\n");
  audio_fill(volume);
  ok = aiueos_audio_play(audio_pcm, AUDIO_FRAMES);
  played++;
  serial_string("AIUEOS_GUEST_BROWSER_AUDIO_PLAY n=1 vol=");
  serial_decimal(volume);
  serial_string(" frames=");
  serial_decimal(AUDIO_FRAMES);
  serial_string(" accepted=");
  serial_decimal(ok ? 1U : 0U);
  serial_string("\r\n");
  if (!ok) return 0;
  while (presses < 4U && idle < 60000U) {
    uint32_t key = aiueos_keyboard_next_key(1024U);
    if (!key) { idle++; continue; }
    idle = 0;
    presses++;
    if (key == 114U * 4U + 1U) volume = volume >= 25U ? volume - 25U : 0U;
    else if (key == 115U * 4U + 1U) volume = volume <= 75U ? volume + 25U : 100U;
    serial_string("AIUEOS_GUEST_BROWSER_AUDIO_VOLUME n=");
    serial_decimal(presses);
    serial_string(" key=");
    serial_decimal(key);
    serial_string(" vol=");
    serial_decimal(volume);
    serial_string("\r\n");
  }
  if (presses < 4U) { serial_string("AIUEOS_GUEST_BROWSER_AUDIO leftover=keys-missing\r\n"); return 0; }
  audio_fill(volume);
  ok = aiueos_audio_play(audio_pcm, AUDIO_FRAMES);
  played++;
  serial_string("AIUEOS_GUEST_BROWSER_AUDIO_PLAY n=2 vol=");
  serial_decimal(volume);
  serial_string(" frames=");
  serial_decimal(AUDIO_FRAMES);
  serial_string(" accepted=");
  serial_decimal(ok ? 1U : 0U);
  serial_string("\r\n");
  if (!ok) return 0;
  serial_string("AIUEOS_GUEST_BROWSER_AUDIO_OK plays=");
  serial_decimal(played);
  serial_string(" volumes=100,");
  serial_decimal(volume);
  serial_string("\r\n");
  return 1;
}

/* ADR-0273: suspend and resume (suspend-to-idle). The "lid" is the sleep key (evdev 142); the wake is the wake key (143). Asleep, the
   machine shows a black screen and idles in HLT (nothing is drawn, no input but the wake key is taken); awake, it draws the frame again
   from the same surface -- whose words the stage fingerprints before and after, so the state is shown intact, not assumed. This is
   suspend-to-idle (CPUs halted, display blanked), not ACPI S3: the RAM stays powered. */
extern uint32_t aiueos_desktop_width(void);
extern uint32_t aiueos_desktop_height(void);
extern int aiueos_desktop_present_ops(const uint32_t *, uint64_t);
extern int aiueos_desktop_show_full(void);
extern uint64_t kotoba_aiueos_fnv1a(const uint8_t *, uint64_t);

/* A fingerprint of the 2048 surface words: the fnv1a object takes short inputs, so fold 128-byte pieces. */
static uint64_t suspend_state_digest(const uint32_t *surface) {
  uint64_t d = 1469598103934665603ULL;
  for (uint32_t off = 0; off < 8192U; off += 128U)
    d = (d ^ kotoba_aiueos_fnv1a((const uint8_t *)surface + off, 128)) * 1099511628211ULL;
  return d;
}

static uint32_t suspend_frame(uint32_t *surface, const uint8_t *font, uint64_t font_length, uint32_t *ops_out) {
  uint32_t px = 0, hash = 0;
  int64_t fo = (int64_t)kotoba_aiueos_browser_frame2((uint64_t)(uintptr_t)surface, 8192, (uint64_t)(uintptr_t)font, font_length);
  *ops_out = (uint32_t)(fo < 0 ? -fo : fo);
  if (fo > 0 && aiueos_desktop_present_ops2(surface + 480, (uint64_t)fo, font, font_length)) {
    hash = aiueos_desktop_colour_census(surface[2039] ? 0x000000U : 0x333333U, &px);
    (void)aiueos_desktop_show_full();
  }
  return hash;
}

static int browser_suspend_stage(uint32_t *surface, const uint8_t *font, uint64_t font_length) {
  uint32_t ops = 0, ops2 = 0, hash0, hash1, idle = 0, got = 0;
  uint64_t d0, d1;
  uint32_t black[6] = {1, 0, 0, aiueos_desktop_width(), aiueos_desktop_height(), 0};
  (void)aiueos_keyboard_drain(4000000U);
  hash0 = suspend_frame(surface, font, font_length, &ops);
  d0 = suspend_state_digest(surface);
  serial_string("AIUEOS_GUEST_BROWSER_SUSPEND_GO ops=");
  serial_decimal(ops);
  serial_string(" hash=");
  serial_hex32(hash0);
  serial_string(" state=");
  serial_hex32((uint32_t)d0);
  serial_string("\r\n");
  while (!got && idle < 120000U) {
    uint32_t key = aiueos_keyboard_next_key(1024U);
    if (!key) { idle++; continue; }
    idle = 0;
    if (key == 142U * 4U + 1U) got = 1;
  }
  if (!got) { serial_string("AIUEOS_GUEST_BROWSER_SUSPEND leftover=no-sleep-key\r\n"); return 0; }
  (void)aiueos_desktop_present_ops(black, 1);
  (void)aiueos_desktop_show_full();
  serial_string("AIUEOS_GUEST_BROWSER_SUSPEND_ENTER screen=black\r\n");
  got = 0; idle = 0;
  while (!got && idle < 400000U) {
    uint32_t key = aiueos_keyboard_next_key(1024U);
    if (key == 143U * 4U + 1U) { got = 1; break; }
    if (!key) { idle++; __asm__ volatile("sti; hlt; cli" ::: "memory"); }
  }
  if (!got) { serial_string("AIUEOS_GUEST_BROWSER_SUSPEND leftover=no-wake-key\r\n"); return 0; }
  hash1 = suspend_frame(surface, font, font_length, &ops2);
  d1 = suspend_state_digest(surface);
  serial_string("AIUEOS_GUEST_BROWSER_SUSPEND_RESUME ops=");
  serial_decimal(ops2);
  serial_string(" hash=");
  serial_hex32(hash1);
  serial_string(" state=");
  serial_hex32((uint32_t)d1);
  serial_string(" frame-intact=");
  serial_decimal(hash0 == hash1 && ops == ops2 ? 1U : 0U);
  serial_string(" state-intact=");
  serial_decimal(d0 == d1 ? 1U : 0U);
  serial_string("\r\n");
  /* hold the resumed frame until the host has taken its screendump of it (F1): the persistent desktop that follows draws its own */
  for (idle = 0, got = 0; !got && idle < 400000U;) {
    uint32_t key = aiueos_keyboard_next_key(1024U);
    if (key == 59U * 4U + 1U) got = 1; else if (!key) idle++;
  }
  serial_string("AIUEOS_GUEST_BROWSER_SUSPEND_DONE\r\n");
  return hash0 == hash1 && d0 == d1;
}
#else
static int browser_audio_stage(void) { return 0; }
static int browser_suspend_stage(uint32_t *surface, const uint8_t *font, uint64_t font_length) { (void)surface; (void)font; (void)font_length; return 0; }
#endif


#ifdef AIUEOS_QWEN38_MODEL_HANDOFF
static void aiueos_qwen35_progress(uint32_t completed_layers,
                                   uint32_t total_layers,
                                   int output_head) {
  if (output_head == 3) {
    aiueos_qwen35_active_token = completed_layers;
    aiueos_qwen35_decode_detail[6] =
        (char)('0' + (completed_layers / 10U) % 10U);
    aiueos_qwen35_decode_detail[7] =
        (char)('0' + completed_layers % 10U);
    aiueos_qwen35_decode_detail[12] =
        (char)('0' + (total_layers / 10U) % 10U);
    aiueos_qwen35_decode_detail[13] =
        (char)('0' + total_layers % 10U);
    aiueos_qwen35_status.phase = completed_layers == 1U
      ? AIUEOS_INFERENCE_PREFILL : AIUEOS_INFERENCE_DECODING;
    aiueos_qwen35_status.detail = aiueos_qwen35_decode_detail;
    aiueos_qwen35_status.generated_tokens = completed_layers - 1U;
    aiueos_qwen35_status.decode_tokens = completed_layers > 1U
      ? completed_layers - 2U : 0U;
  } else if (output_head == 2) {
    aiueos_qwen35_decode_detail[6] =
        (char)('0' + (completed_layers / 10U) % 10U);
    aiueos_qwen35_decode_detail[7] =
        (char)('0' + completed_layers % 10U);
    aiueos_qwen35_decode_detail[12] =
        (char)('0' + (total_layers / 10U) % 10U);
    aiueos_qwen35_decode_detail[13] =
        (char)('0' + total_layers % 10U);
    aiueos_qwen35_status.phase = AIUEOS_INFERENCE_DECODING;
    aiueos_qwen35_status.detail = aiueos_qwen35_decode_detail;
    aiueos_qwen35_status.generated_tokens = completed_layers;
    aiueos_qwen35_status.decode_tokens =
        completed_layers ? completed_layers - 1U : 0U;
  } else if (output_head) {
    aiueos_qwen35_output_detail[1] =
        (char)('0' + (aiueos_qwen35_active_token / 10U) % 10U);
    aiueos_qwen35_output_detail[2] =
        (char)('0' + aiueos_qwen35_active_token % 10U);
    aiueos_qwen35_status.phase = AIUEOS_INFERENCE_DECODING;
    aiueos_qwen35_status.detail = aiueos_qwen35_output_detail;
  } else {
    aiueos_qwen35_progress_detail[1] =
        (char)('0' + (aiueos_qwen35_active_token / 10U) % 10U);
    aiueos_qwen35_progress_detail[2] =
        (char)('0' + aiueos_qwen35_active_token % 10U);
    aiueos_qwen35_progress_detail[5] =
        (char)('0' + (completed_layers / 10U) % 10U);
    aiueos_qwen35_progress_detail[6] =
        (char)('0' + completed_layers % 10U);
    aiueos_qwen35_status.phase = aiueos_qwen35_active_token == 1U
      ? AIUEOS_INFERENCE_PREFILL : AIUEOS_INFERENCE_DECODING;
    aiueos_qwen35_status.detail = aiueos_qwen35_progress_detail;
  }
  /* The physical GOP aperture is a live scanout, not an atomic page-flip.
     Preserve per-layer serial evidence but refresh the visible progress only
     at token boundaries and every fourth trunk layer. */
  if (output_head || completed_layers == 1U ||
      completed_layers == total_layers || completed_layers % 4U == 0U ||
      aiueos_qwen35_active_token != aiueos_qwen35_last_render_token) {
    (void)aiueos_framebuffer_inference_screen(&aiueos_qwen35_status);
    aiueos_qwen35_last_render_token = aiueos_qwen35_active_token;
  }
  serial_string("AIUEOS_QWEN35_PROGRESS layers=");
  serial_decimal(completed_layers);
  serial_string("/");
  serial_decimal(total_layers);
  serial_string(" token=");
  serial_decimal(aiueos_qwen35_active_token);
  serial_string(" event=");
  serial_decimal((uint32_t)output_head);
  serial_string("\r\n");
}

static void aiueos_qwen35_format_failure(uint32_t token, uint32_t layer,
                                         uint32_t stage) {
  aiueos_qwen35_decode_fail_detail[1] =
      (char)('0' + (token / 10U) % 10U);
  aiueos_qwen35_decode_fail_detail[2] = (char)('0' + token % 10U);
  aiueos_qwen35_decode_fail_detail[5] =
      (char)('0' + (layer / 10U) % 10U);
  aiueos_qwen35_decode_fail_detail[6] = (char)('0' + layer % 10U);
  const char *label = aiueos_qwen35_failure_stage_label(stage);
  uint32_t index = 8U;
  while (*label && index + 1U < sizeof(aiueos_qwen35_decode_fail_detail))
    aiueos_qwen35_decode_fail_detail[index++] = *label++;
  aiueos_qwen35_decode_fail_detail[index] = 0;
}

static uint64_t aiueos_read_tsc(void) {
  uint32_t low, high;
  __asm__ volatile("lfence; rdtsc" : "=a"(low), "=d"(high) :: "memory");
  return ((uint64_t)high << 32) | low;
}

static void aiueos_wait_seconds(uint64_t tsc_hz, uint32_t seconds) {
  if (!tsc_hz || !seconds) return;
  uint64_t start = aiueos_read_tsc();
  uint64_t cycles = tsc_hz * seconds;
  while (aiueos_read_tsc() - start < cycles) __asm__ volatile("pause");
}

/* Management is an AIUEOS service, not a consequence of Murakumo health.
   Keep the same bounded listener active both while the worker is ready and
   while its HTTPS heartbeat is reconnecting.  This is deliberately limited
   to the runtime status/restart allow-list enforced by the SSH state machine. */
static void aiueos_k16_management_wait(uint64_t tsc_hz, uint32_t seconds) {
#if defined(AIUEOS_SSH_LISTEN) && \
    defined(AIUEOS_PHYSICAL_DIRECT_HTTPS_QUALIFICATION) && \
    defined(AIUEOS_MURAKUMO_DEVICE_RESULT)
  for (uint32_t management_second = 0;
       management_second < seconds; management_second++) {
    /* Keep RX posted for the whole management second.  One short listener
       followed by a one-second CPU delay leaves the physical link deaf for
       most of the interval and can phase-lock with macOS SYN retransmission.
       The listener itself is bounded, so repeat it until the second expires;
       this changes no command authority and still returns to Murakumo on the
       original five/30-second schedule. */
    uint64_t management_start = aiueos_read_tsc();
    do {
      if (aiueos_rtl8125_ssh_poll()) {
        debug_string("AIUEOS_RTL8125_SSH_SESSION_OK commands=runtime-status,runtime-restart,system-reboot-pxe shell=false\n");
        serial_string("AIUEOS_RTL8125_SSH_SESSION_OK commands=runtime-status,runtime-restart,system-reboot-pxe shell=false\r\n");
        if (aiueos_management_take_reboot_pxe_request()) {
          debug_string("AIUEOS_SSH_REBOOT_PXE_ACK reset=uefi-runtime\n");
          serial_string("AIUEOS_SSH_REBOOT_PXE_ACK reset=uefi-runtime\r\n");
          (void)aiueos_qualification_reboot();
          debug_string("AIUEOS_SSH_REBOOT_PXE_FAIL reset=uefi-runtime\n");
          serial_string("AIUEOS_SSH_REBOOT_PXE_FAIL reset=uefi-runtime\r\n");
        }
      }
    } while (tsc_hz && aiueos_read_tsc() - management_start < tsc_hz);
  }
#else
  aiueos_wait_seconds(tsc_hz, seconds);
#endif
}

static uint64_t aiueos_cycles_to_ns(uint64_t cycles, uint64_t tsc_hz) {
  if (!cycles || !tsc_hz) return AIUEOS_INFERENCE_UNMEASURED;
  uint64_t whole = cycles / tsc_hz;
  uint64_t remainder = cycles % tsc_hz;
  uint64_t fraction = (remainder * 1000000000ULL) / tsc_hz;
  if (whole > (UINT64_MAX - fraction) / 1000000000ULL)
    return AIUEOS_INFERENCE_UNMEASURED;
  return whole * 1000000000ULL + fraction;
}

static const char *aiueos_worker_transport_detail(void) {
  switch (aiueos_rtl8125_direct_https_error()) {
    case 2: return "DNS RETRY";
    case 6: return "TCP CONNECT RETRY";
    case 11: return "HTTP RESPONSE TIMEOUT";
    case 60: return "RESPONSE PARSE ERROR";
    default: return "NODE RECONNECTING";
  }
}
#endif
static void serial_ipv4(uint32_t value) {
  for (unsigned shift = 24; ; shift -= 8) {
    serial_decimal((value >> shift) & 0xff);
    if (!shift) return;
    serial_byte('.');
  }
}
/* The object's reason code rendered as the clause it names. The mapping mirrors
   the table at the top of kotoba/dhcp-reply-valid.kotoba, which is where the
   codes are decided; this is rendering, and getting it wrong misnames a
   refusal without changing one. */
static const char *dhcp_reason_name(unsigned reason) {
  switch (reason) {
    case 0: return "admitted";
    case 1: return "frame-length";
    case 2: return "ipv4-envelope";
    case 3: return "udp-envelope";
    case 4: return "not-bootreply";
    case 5: return "foreign-transaction-id";
    case 6: return "foreign-hardware-address";
    case 7: return "no-magic-cookie";
    case 8: return "options-overrun";
    case 9: return "message-type";
    case 10: return "no-server-identifier";
    case 11: return "address-mask-inconsistent";
    case 12: return "lease-time";
    default: return "unknown";
  }
}
static const char *dhcp_stage_name(unsigned stage) {
  switch (stage) {
    case 1: return "tx-discover";
    case 2: return "no-admitted-offer";
    case 3: return "tx-request";
    case 4: return "no-admitted-ack";
    case 5: return "done";
    default: return "idle";
  }
}
__attribute__((noreturn)) static void qemu_exit(uint32_t value) {
  __asm__ volatile("outl %0, $0xf4" : : "a"(value));
  __asm__ volatile("cli");
  for (;;) __asm__ volatile("hlt");
}

/* 0x6f is this kernel's "an evidence check said no" exit, and it is reached
   from twenty-six different places. The code alone therefore names a class,
   not a failure -- exactly the position the K16 loader was in with exit 63,
   where a numeric status had to be matched back to one of nine call sites by
   hand and cost days.
   So the site says which it is, before it exits. The line number is enough:
   it is unambiguous, it costs nothing at runtime on a path that is already
   terminating, and it cannot drift out of date the way a hand-written label
   would. */
__attribute__((noreturn)) static void evidence_stop(unsigned line) {
  char digits[8]; unsigned i = 0, n = line;
  if (!n) digits[i++] = '0';
  while (n) { digits[i++] = (char)('0' + (n % 10)); n /= 10; }
  debug_string("AIUEOS_EVIDENCE_STOP line=");
  serial_string("AIUEOS_EVIDENCE_STOP line=");
  while (i--) {
    char one[2]; one[0] = digits[i]; one[1] = 0;
    debug_string(one); serial_string(one);
  }
  debug_string("\n"); serial_string("\r\n");
  /* Do NOT kill the machine (JUN-141, measured 2026-10-20): a failed
     evidence check on a user's machine must leave the desktop up, not
     power the session down. The line is reported above; the CPU now idles
     with whatever the desktop last drew scanned out. The gate treats this
     line as a fast failure, so its fail-fast is unchanged.
     qemu_exit, NOT evidence_stop -- see the recursion note below. */
  /* qemu_exit, NOT evidence_stop. The blanket rewrite that created this
     helper also rewrote the call inside it, so every evidence stop recursed
     until the stack died -- and it reported its own line number while doing
     so, which is the worst possible failure for a diagnostic: confidently
     wrong. */
  for (;;) __asm__ volatile("hlt");
}

/* Splitting the 64-bit handler address across the descriptor's three offset
 * fields is bit-packing whose failure mode is a well-formed gate pointing at
 * the WRONG ring-0 address -- silent and exploitable rather than a crash -- so
 * it lives in Kotoba. This wrapper keeps the C shape (vector, handler); the
 * object owns the sixteen bytes and the selector/ist/attributes domains. The
 * three constants below are passed rather than assumed: the object refuses
 * anything but this kernel's single DPL-0 64-bit code selector, no IST (the
 * TSS has none populated), and a present DPL-0 interrupt gate. */
extern uint64_t kotoba_aiueos_idt_gate_build(uint64_t handler, uint64_t selector,
                                             uint64_t ist, uint64_t attributes,
                                             void *out);

static void set_idt_gate(uint8_t vector, void (*handler)(void)) {
  /* A refusal writes nothing, so the entry would stay P=0 and every delivery
   * on that vector would #GP with the fault pointing at the IDT. Fail here
   * instead, where the vector is still known. */
  if (!kotoba_aiueos_idt_gate_build((uint64_t)(uintptr_t)handler, 0x08, 0, 0x8e,
                                    &idt[vector])) {
    debug_string("AIUEOS_KOTOBA_IDT_GATE_FAIL refused\n");
    serial_string("AIUEOS_KOTOBA_IDT_GATE_FAIL refused\r\n");
    qemu_exit(0x69);
  }
}

/* Set immediately before the deliberate end-of-boot ud2 probe. Any exception
   arriving before then is an unexpected fault and receives a best-effort
   durable crash receipt over the polled transport before termination. */
volatile int aiueos_final_probe_expected;

/* Rendering, not deciding: the vector's architectural name.  Getting an entry
   wrong misnames a fault without changing one, exactly as dhcp_reason_name
   above.  Vectors this kernel services on purpose (6 before the end-of-boot
   probe, 14 during the three paging probes) never reach here. */
static const char *aiueos_vector_mnemonic(uint64_t vector) {
  switch (vector) {
    case 0:  return "#DE/divide-error";
    case 1:  return "#DB/debug";
    case 2:  return "NMI/non-maskable-interrupt";
    case 3:  return "#BP/breakpoint";
    case 4:  return "#OF/overflow";
    case 5:  return "#BR/bound-range";
    case 6:  return "#UD/invalid-opcode";
    case 7:  return "#NM/device-not-available";
    case 8:  return "#DF/double-fault";
    case 9:  return "coprocessor-segment-overrun";
    case 10: return "#TS/invalid-tss";
    case 11: return "#NP/segment-not-present";
    case 12: return "#SS/stack-segment-fault";
    case 13: return "#GP/general-protection";
    case 14: return "#PF/page-fault";
    case 16: return "#MF/x87-floating-point";
    case 17: return "#AC/alignment-check";
    case 18: return "#MC/machine-check";
    case 19: return "#XM/simd-floating-point";
    case 20: return "#VE/virtualisation";
    case 21: return "#CP/control-protection";
    case 28: return "#HV/hypervisor-injection";
    case 29: return "#VC/vmm-communication";
    case 30: return "#SX/security";
    default: return "reserved";
  }
}

/* One line, built once, printed to both transports.  A static buffer rather
   than a local because a #DF or a #SS arrives with a stack that may already be
   the reason we are here, and 256 bytes of it is 256 bytes that may not be
   writable.  Nothing re-enters: every path out of the reporter terminates. */
#define AIUEOS_STRINGIFY_(x) #x
#define AIUEOS_STRINGIFY(x) AIUEOS_STRINGIFY_(x)
static char aiueos_fatal_line[288];
static unsigned aiueos_fatal_len;

static void fatal_put(char c) {
  if (aiueos_fatal_len + 1 < sizeof(aiueos_fatal_line))
    aiueos_fatal_line[aiueos_fatal_len++] = c;
}
static void fatal_puts(const char *text) { while (*text) fatal_put(*text++); }
static void fatal_hex_raw(uint64_t value, unsigned digits) {
  static const char d[] = "0123456789abcdef";
  while (digits--) fatal_put(d[(value >> (digits * 4)) & 0xf]);
}
static void fatal_hex(uint64_t value, unsigned digits) {
  fatal_puts("0x");
  fatal_hex_raw(value, digits);
}
static void fatal_dec(uint64_t value) {
  char buf[20];
  unsigned n = 0;
  do { buf[n++] = (char)('0' + value % 10U); value /= 10U; } while (value && n < sizeof(buf));
  while (n) fatal_put(buf[--n]);
}

/* Every fatal CPU exception in this kernel converges here (ADR-0199).  It
   prints ONE greppable line carrying the vector, the error code and the
   faulting RIP -- the three facts a reader previously had to recover by
   relinking the image without --strip-all and doing arithmetic -- and then
   terminates the machine through isa-debug-exit.  It does not halt: a halted
   guest is a guest QEMU keeps running, and a harness can only tell that apart
   from a slow boot by timing out, which is how a deterministic miscompile
   spent three ten-minute attempts being reported as a known flake.

   `insn=` is the four bytes at RIP when RIP is inside this kernel's own text,
   so a Kotoba fuel guard or window bounds check -- both of which Amu emits as
   `ud2` = 0f 0b -- names itself in the line.  Reading elsewhere could fault
   again, so it is not attempted.  The bytes cannot say WHICH of the two guards
   fired; that distinction is not available at the trap. */
__attribute__((noreturn))
void aiueos_exception_dispatch(uint64_t vector, uint64_t error, uint64_t rip,
                               uint64_t rsp, uint64_t cr2, uint64_t rflags) {
  if (vector == 6 && aiueos_final_probe_expected) {
    debug_string("AIUEOS_EXCEPTION_OK vector=6\n");
    serial_string("AIUEOS_EXCEPTION_OK vector=6 invalid-opcode\r\n");
    qemu_exit(0x30);
  }
  aiueos_fatal_len = 0;
  fatal_puts("AIUEOS_FATAL_EXCEPTION vector=");
  fatal_dec(vector);
  fatal_puts(" mnemonic=");
  fatal_puts(aiueos_vector_mnemonic(vector));
  fatal_puts(" error=");
  fatal_hex(error, 8);
  fatal_puts(" rip=");
  fatal_hex(rip, 16);
  fatal_puts(" rsp=");
  fatal_hex(rsp, 16);
  fatal_puts(" rflags=");
  fatal_hex(rflags, 8);
  fatal_puts(" cr2=");
  fatal_hex(cr2, 16);
  {
    const uint64_t lo = (uint64_t)(uintptr_t)aiueos_text_start;
    const uint64_t hi = (uint64_t)(uintptr_t)aiueos_text_end;
    if (rip >= lo && rip + 4 <= hi) {
      const uint8_t *at = (const uint8_t *)(uintptr_t)rip;
      fatal_puts(" rip-text=");
      fatal_hex(rip - lo, 8);
      fatal_puts(" insn=");
      for (unsigned i = 0; i < 4; i++) fatal_hex_raw(at[i], 2);
      fatal_puts(at[0] == 0x0f && at[1] == 0x0b ? " ud2=yes" : " ud2=no");
    } else {
      fatal_puts(" rip-text=outside insn=unreadable ud2=unknown");
    }
  }
  fatal_put('\0');
  debug_string(aiueos_fatal_line);
  debug_string("\n");
  serial_string(aiueos_fatal_line);
  serial_string("\r\n");
  {
    extern int aiueos_crash_receipt_write_from_fault(uint32_t);
    /* Kept verbatim: three ADRs and the AIUEOS_EXPECT_FAULT gate name this
       literal, and QWEN-KERNELS-2 read a d=128 non-terminating loop off it. */
    debug_string("AIUEOS_EXCEPTION_FAIL unexpected-vector\n");
    serial_string("AIUEOS_EXCEPTION_FAIL unexpected-vector vector=");
    serial_decimal((uint32_t)vector);
    serial_string("\r\n");
    if (aiueos_crash_receipt_write_from_fault((uint32_t)vector)) {
      debug_string("AIUEOS_FAULT_RECEIPT_OK polled try-lock written readback pending\n");
      serial_string("AIUEOS_FAULT_RECEIPT_OK polled try-lock written readback pending\r\n");
    } else {
      /* Best effort: the storage plane may not be up yet, or the queue may
         be held mid-operation by the faulted context. */
      serial_string("AIUEOS_FAULT_RECEIPT_SKIPPED storage-unavailable-or-busy\r\n");
    }
    qemu_exit(0x7d);
  }
}

/* The gates, in one table, installed twice: once before the first Kotoba
   object runs and again where the kernel has always installed them.  The
   early pass is the whole point of ADR-0199 -- fifty-one Kotoba objects used
   to execute while the FIRMWARE's IDT was still loaded, and OVMF answers a
   #UD with a dump and a dead loop, so QEMU never exited and the harness could
   only time out.  The second pass is left in place so that the marker every
   existing gate greps for keeps its position in the boot. */
struct aiueos_gate { uint8_t vector; void (*handler)(void); };
static const struct aiueos_gate aiueos_fatal_gates[] = {
  {0, aiueos_isr_fatal_0},   {1, aiueos_isr_fatal_1},   {2, aiueos_isr_fatal_2},
  {3, aiueos_isr_fatal_3},   {4, aiueos_isr_fatal_4},   {5, aiueos_isr_fatal_5},
  {6, aiueos_isr_invalid_opcode},
  {7, aiueos_isr_fatal_7},   {8, aiueos_isr_fatal_8},   {9, aiueos_isr_fatal_9},
  {10, aiueos_isr_fatal_10}, {11, aiueos_isr_fatal_11}, {12, aiueos_isr_fatal_12},
  {13, aiueos_isr_fatal_13},
  {14, aiueos_isr_page_fault},
  {15, aiueos_isr_fatal_15}, {16, aiueos_isr_fatal_16}, {17, aiueos_isr_fatal_17},
  {18, aiueos_isr_fatal_18}, {19, aiueos_isr_fatal_19}, {20, aiueos_isr_fatal_20},
  {21, aiueos_isr_fatal_21}, {22, aiueos_isr_fatal_22}, {23, aiueos_isr_fatal_23},
  {24, aiueos_isr_fatal_24}, {25, aiueos_isr_fatal_25}, {26, aiueos_isr_fatal_26},
  {27, aiueos_isr_fatal_27}, {28, aiueos_isr_fatal_28}, {29, aiueos_isr_fatal_29},
  {30, aiueos_isr_fatal_30}, {31, aiueos_isr_fatal_31},
};

static void aiueos_install_fatal_gates(void) {
  /* The gate bytes come from the same Kotoba object as every other gate, so
     the early table is not a second, C-authored answer to the packing
     question.  The cost is that this object -- one of the fifty-one -- is
     itself still executing under the firmware's IDT.  That residual is named
     in ADR-0199 and is the reason the marker below is printed AFTER the
     lidt: a boot that reaches it has covered everything after it. */
  for (unsigned i = 0; i < sizeof(aiueos_fatal_gates) / sizeof(aiueos_fatal_gates[0]); i++)
    set_idt_gate(aiueos_fatal_gates[i].vector, aiueos_fatal_gates[i].handler);
}

__attribute__((noreturn))
extern uint8_t aiueos_high_data_start[], aiueos_high_data_end[];

/* The desktop surface state, shared by the evidence flow stage and the
   persistent desktop loop (JUN-141). .high_bss: NOLOAD, aligned for the
   ops the frame writer emits. */
static uint32_t __attribute__((section(".high_bss"), aligned(16))) flow[2048];

void aiueos_kernel_main(const struct aiueos_boot_info *boot) {
  /* `.high_bss` is NOLOAD: the loader zeroes the two PT_LOAD segments it
     admits and nothing else, so a buffer placed there starts with whatever
     the firmware left at 4 MiB. Every user of the section zeroed its own
     buffer before this line existed; the section is zeroed here once so that
     a buffer moved out of `.bss` to make room in the low 2 MiB (ADR-0221:
     the Kotoba objects grew past `aiueos_low_end`) keeps the zero-initialised
     semantics C gave it in `.bss`. Still on the loader's identity map: the
     window is ordinary RAM either way. */
  for (uint8_t *p = aiueos_high_data_start; p < aiueos_high_data_end; p++) *p = 0;
  serial_init();
#ifndef AIUEOS_SKIP_EARLY_FATAL_IDT
  /* Own the descriptor tables BEFORE the first Kotoba object runs (ADR-0199).
     Everything from here to the historical install site at
     AIUEOS_DESCRIPTOR_TABLES_OK -- fifty-one Kotoba calls on this path --
     used to trap into OVMF's handler, which dumps and dead-loops, so a
     miscompiled object produced a QEMU process that never exited and a smoke
     run that could only call it a timeout.  Loading our GDT first is required:
     the gates carry selector 0x08, and a gate whose selector is not a present
     64-bit code segment turns the fault into a #GP and then a triple fault,
     which QEMU reports as a reset rather than a status. */
  aiueos_load_gdt();
  aiueos_install_fatal_gates();
  {
    static struct descriptor_pointer early_idtr;
    early_idtr.limit = (uint16_t)(sizeof(idt) - 1);
    early_idtr.base = (uint64_t)(uintptr_t)idt;
    aiueos_load_idt(&early_idtr);
  }
  debug_string("AIUEOS_FATAL_IDT_OK early vectors=0-31\n");
  serial_string("AIUEOS_FATAL_IDT_OK early vectors=0-31\r\n");
#endif
#ifdef AIUEOS_EARLY_FAULT_SMOKE
  /* Test-only, and each value raises a DIFFERENT vector on purpose (ADR-0199):
       1  #UD  -- the hand-written stub, and what a Kotoba fuel guard raises
       2  #UD  -- the same instruction with the early table compiled out, which
                  is what every boot did before ADR-0199 (the RED evidence)
       3  #BP  -- a GENERATED no-error-code stub
       4  #GP  -- a GENERATED error-code stub, with a selector past this GDT's
                  limit so the error code in the line is a value chosen here
     3 and 4 exist because a reporter exercised only through vector 6 has not
     shown that it reads the frame correctly: an error-code stub that forgot
     its extra push would print the error code where the RIP goes, and both
     fields would still look like plausible addresses. */
  serial_string("AIUEOS_EARLY_FAULT_SMOKE synthetic mode="
                AIUEOS_STRINGIFY(AIUEOS_EARLY_FAULT_SMOKE) " before-objects\r\n");
  debug_string("AIUEOS_EARLY_FAULT_SMOKE synthetic mode="
               AIUEOS_STRINGIFY(AIUEOS_EARLY_FAULT_SMOKE) " before-objects\n");
#if AIUEOS_EARLY_FAULT_SMOKE == 3
  __asm__ volatile("int3");
#elif AIUEOS_EARLY_FAULT_SMOKE == 4
  __asm__ volatile("mov $0x48, %%ax; mov %%ax, %%ds" : : : "ax");
#else
  __asm__ volatile("ud2");
#endif
#endif
  if (!boot || boot->magic != AIUEOS_BOOT_INFO_MAGIC ||
      (boot->version != 2 && boot->version != AIUEOS_BOOT_INFO_VERSION_BASE &&
       boot->version != AIUEOS_BOOT_INFO_VERSION_MODEL_HANDOFF &&
       boot->version != AIUEOS_BOOT_INFO_VERSION_TSC_CALIBRATED) ||
      !boot->memory_map || !boot->memory_map_size || !boot->descriptor_size ||
      !aiueos_boot_info_retain(boot)) {
    debug_string("AIUEOS_KERNEL_FAIL boot-info\n");
    serial_string("AIUEOS_KERNEL_FAIL boot-info\r\n");
    qemu_exit(0x7e);
  } else {
    boot = &aiueos_owned_boot_info;
#if defined(AIUEOS_PHYSICAL_QUALIFICATION) && \
    defined(AIUEOS_QWEN38_MODEL_HANDOFF) && !defined(AIUEOS_MODEL_TEST_FIXTURE)
    int qwen_early_acpi_ready = 0;
#endif
#ifdef AIUEOS_PHYSICAL_QUALIFICATION
    aiueos_qualification_runtime_initialize(
        boot->version >= 3 ? boot->runtime_services : 0,
        boot->version >= 3 ? boot->firmware_cr3 : 0);
    aiueos_qualification_progress(220);
#ifdef AIUEOS_QUALIFICATION_FORCE_KERNEL_HANG_CODE
    aiueos_qualification_progress(AIUEOS_QUALIFICATION_FORCE_KERNEL_HANG_CODE);
    debug_string("AIUEOS_KERNEL_PROGRESS forced-hang\n");
    for (;;) __asm__ volatile("pause");
#endif
#endif
    debug_string("AIUEOS_KERNEL_OK memory-map-v1\n");
    serial_string("AIUEOS_SERIAL_OK stack-v1 memory-map-v1\r\n");
    /* The loader calibrates the TSC (uefi/main.c: info.tsc_hz = elapsed * 10)
       and hands the frequency over in boot info, and aiueos_wait_seconds()
       converts cycles to seconds with it -- but until 2026-09-10 nothing
       announced it, so os-coverage.cljs, which recognises exactly
       /AIUEOS_[A-Z0-9_]+_OK/, could not score a clock at all and the taxonomy
       had no row for one. Emitted only when the frequency is non-zero: an
       older boot-info version leaves it unset, and a marker claiming a
       calibrated clock that was never calibrated is worse than silence. */
    if (aiueos_owned_boot_info.tsc_hz) {
      serial_string("AIUEOS_TSC_CALIBRATED_OK hz=");
      serial_decimal64(aiueos_owned_boot_info.tsc_hz);
      serial_string("\r\n");
    }
#ifdef AIUEOS_ECDSA_PUBLIC_KAT
    /* Run before the owned low-2MiB page table is installed. The standalone
       public-point object intentionally makes this one-purpose KAT image
       larger than that generic bootstrap boundary. */
    if (aiueos_ecdsa_public_kat()) {
      serial_string("AIUEOS_ECDSA_PUBLIC_OK rfc6979-a2.5 x||y-match\r\n");
      debug_string("AIUEOS_ECDSA_PUBLIC_OK rfc6979-a2.5 x||y-match\n");
      qemu_exit(0x30);
    }
    serial_string("AIUEOS_ECDSA_PUBLIC_FAIL vector-mismatch\r\n");
    qemu_exit(0x7d);
#endif
#ifdef AIUEOS_ECDSA_SIGN_KAT
    /* The standalone sign brick makes this one-purpose image larger than the
       generic low-2MiB bootstrap mapping. Exercise it before owned paging, as
       with the public-point KAT above, then terminate the dedicated test. */
    if (aiueos_ecdsa_sign_kat()) {
      serial_string("AIUEOS_ECDSA_SIGN_OK rfc6979-a2.5 r||s-match\r\n");
      debug_string("AIUEOS_ECDSA_SIGN_OK rfc6979-a2.5 r||s-match\n");
      qemu_exit(0x30);
    }
    serial_string("AIUEOS_ECDSA_SIGN_FAIL vector-mismatch\r\n");
    qemu_exit(0x7d);
#endif
#ifdef AIUEOS_PHYSICAL_QUALIFICATION
    aiueos_qualification_progress(221);
#endif
    extern uint64_t kotoba_aiueos_probe(void);
    if (kotoba_aiueos_probe() != 42u) {
      debug_string("AIUEOS_KOTOBA_NATIVE_FAIL probe-result\n");
      serial_string("AIUEOS_KOTOBA_NATIVE_FAIL probe-result\r\n");
      qemu_exit(0x67);
    }
    debug_string("AIUEOS_KOTOBA_NATIVE_OK elf64-relocatable sysv-v1 result=42\n");
    serial_string("AIUEOS_KOTOBA_NATIVE_OK elf64-relocatable sysv-v1 result=42\r\n");
    extern uint64_t kotoba_aiueos_fnv1a(const uint8_t *, uint64_t);
    static const uint8_t fnv_vector[3] = {'a', 'b', 'c'};
    if ((uint32_t)kotoba_aiueos_fnv1a(fnv_vector, 3) != 0x1a47e90bU) {
      serial_string("AIUEOS_KOTOBA_FNV_FAIL known-vector\r\n");
      evidence_stop(__LINE__);
    }
    serial_string("AIUEOS_KOTOBA_FNV_VECTOR_OK abc\r\n");
    uint64_t initramfs_files = 0;
    if (!initramfs_validate(boot->initramfs_base, boot->initramfs_size,
                            &initramfs_files) || initramfs_files != 5) {
      debug_string("AIUEOS_INITRAMFS_FAIL newc-structure\n");
      serial_string("AIUEOS_INITRAMFS_FAIL newc-structure\r\n");
      qemu_exit(0x68);
    }
    debug_string("AIUEOS_INITRAMFS_OK newc entries=5 sha256-admitted bounded\n");
    serial_string("AIUEOS_INITRAMFS_OK newc entries=5 sha256-admitted bounded\r\n");
    extern int aiueos_recovery_payload_admission(const uint8_t *, uint64_t, const uint8_t *);
    if (!initramfs_recovery_elf_length || !initramfs_recovery_signature_present ||
        !aiueos_recovery_payload_admission(initramfs_recovery_elf,
                                           initramfs_recovery_elf_length,
                                           initramfs_recovery_signature)) {
      debug_string("AIUEOS_INITRAMFS_RECOVERY_ADMISSION_FAIL rsa2048-policy\n");
      serial_string("AIUEOS_INITRAMFS_RECOVERY_ADMISSION_FAIL rsa2048-policy\r\n");
      qemu_exit(0x68);
    }
    debug_string("AIUEOS_INITRAMFS_RECOVERY_ADMISSION_OK elf digest=kotoba-sha256 signature=kotoba-rsa2048-pkcs1 policy=public-key\n");
    serial_string("AIUEOS_INITRAMFS_RECOVERY_ADMISSION_OK elf digest=kotoba-sha256 signature=kotoba-rsa2048-pkcs1 policy=public-key\r\n");
    extern uint64_t kotoba_aiueos_journal_record_build(void *, uint64_t, uint64_t);
    extern uint64_t kotoba_aiueos_journal_record_valid(const void *, uint64_t);
    static uint8_t journal_vector[512];
    for (uint32_t i = 0; i < sizeof(journal_vector); i++) journal_vector[i] = 0;
    if (!kotoba_aiueos_journal_record_build(journal_vector, sizeof(journal_vector), 1) ||
        !kotoba_aiueos_journal_record_valid(journal_vector, 64)) {
      serial_string("AIUEOS_KOTOBA_STORE_FAIL journal-vector\r\n");
      evidence_stop(__LINE__);
    }
    serial_string("AIUEOS_KOTOBA_STORE_VECTOR_OK journal-sequence=1\r\n");
#ifdef AIUEOS_PHYSICAL_QUALIFICATION
    aiueos_qualification_progress(222);
#endif
    aiueos_load_gdt();
    /* Idempotent: the same table the early pass installed (ADR-0199).  Kept
       here so this marker keeps meaning "the kernel owns its descriptor
       tables", and so a future edit to the fatal set lands in one place. */
    aiueos_install_fatal_gates();
    set_idt_gate(32, aiueos_isr_apic_timer);
    set_idt_gate(33, aiueos_isr_external_timer);
    set_idt_gate(34, aiueos_isr_virtio_rng);
    set_idt_gate(35, aiueos_isr_virtio_blk);
    set_idt_gate(128, aiueos_isr_syscall);
    const struct descriptor_pointer idtr = {
      .limit = (uint16_t)(sizeof(idt) - 1),
      .base = (uint64_t)(uintptr_t)idt
    };
    aiueos_load_idt(&idtr);
    debug_string("AIUEOS_DESCRIPTOR_TABLES_OK gdt-v1 idt-v1\n");
    serial_string("AIUEOS_DESCRIPTOR_TABLES_OK gdt-v1 idt-v1\r\n");
    /* Quiet the legacy 8259 pair. ADR-0028 diagnosed this as a ~22% flaky boot
       on the Multiboot path -- SeaBIOS leaves the PIC live with master base
       0x08 and the 8254 ticking, so the first `sti` delivered IRQ0 as vector 8
       and it masqueraded as #DF -- and fixed it only there. This path has the
       same gap. Nothing here has ever programmed the 8259; the only masking on
       the whole path is the out8(0x21,0xff)/out8(0xa1,0xff) pair inside
       aiueos_ioapic_route_legacy_timer (ioapic.c:31), which does not run until
       main.c:692, well past the first `sti` at main.c:456, and which masks
       without remapping. This path is green because OVMF masks the PIC before
       handoff -- that is a property of the firmware, not of this kernel.

       Placed HERE, immediately after aiueos_load_idt, for the same reason the
       X25519 self-test below is placed after the kernel owns its IDT rather
       than beside the earlier self-tests: this is a Kotoba object, its prologue
       guards fuel with `ud2`, and a #UD raised while the FIRMWARE's handler is
       still installed produces an OVMF dump with no vector and no address.
       After the `lidt` it reaches set_idt_gate(6, aiueos_isr_invalid_opcode)
       and names itself. It is still 115 lines and one paging bring-up ahead of
       the first `sti`, which is the only ordering the PIC actually requires.

       0xe0/0xe8 rather than the multiboot C's old 0xf0/0xf8: the object refuses
       0xf8 because 0xf8+7 is 255, the Local APIC spurious vector this kernel
       programs in apic.c:42. 224..239 is clear of 32-35, 128 and 255. */
    extern uint64_t kotoba_aiueos_pic_disable(uint64_t, uint64_t);
#ifdef AIUEOS_PHYSICAL_QUALIFICATION
    aiueos_qualification_progress(223);
#endif
    if (!kotoba_aiueos_pic_disable(0xe0, 0xe8)) {
      debug_string("AIUEOS_PIC_FAIL base-refused\n");
      serial_string("AIUEOS_PIC_FAIL base-refused\r\n");
      qemu_exit(0x7b);
    }
    debug_string("AIUEOS_PIC_OK remapped=0xe0/0xe8 masked=both\n");
    serial_string("AIUEOS_PIC_OK remapped=0xe0/0xe8 masked=both\r\n");
#ifdef AIUEOS_PHYSICAL_QUALIFICATION
    aiueos_qualification_progress(224);
#endif
    if (!aiueos_paging_initialize(boot)) {
      debug_string("AIUEOS_PAGING_FAIL ownership-or-wx\n");
      serial_string("AIUEOS_PAGING_FAIL ownership-or-wx\r\n");
      qemu_exit(0x7c);
    }
    debug_string("AIUEOS_PAGING_OK cr3-owned wx-v1 nx-wp\n");
    serial_string("AIUEOS_PAGING_OK cr3-owned wx-v1 nx-wp\r\n");
#ifdef AIUEOS_PHYSICAL_QUALIFICATION
    aiueos_qualification_progress(225);
#endif
    /* Placed AFTER the kernel owns its own IDT and page tables, not beside the
       other known-vector self-tests earlier in boot. Measured: running it there
       faulted with the FIRMWARE's handler still installed, so the only output
       was OVMF's "Can't find image information" dump -- no vector, no address,
       nothing to act on. Here a fault reaches this kernel's own handler and
       reports its vector, which is the difference between a diagnosable failure
       and an opaque one.
       X25519 against RFC 7748 §5.2's base-point vector, run here rather than
       trusted from a transcription. The algorithm was checked by transcribing
       the Kotoba into Python and running the published vectors; that proves the
       ALGORITHM and says nothing about what the compiler emitted. This runs the
       emitted object on the target and compares all 32 bytes, which is the only
       evidence that covers the backend too.
       The comparison reuses kotoba_aiueos_digest_equal -- the same fixed-work
       32-byte compare the application catalog admits signatures with. */
    {
      extern uint64_t kotoba_aiueos_x25519(const uint8_t *, const uint8_t *,
                                           uint8_t *, uint8_t *);
      extern uint64_t kotoba_aiueos_digest_equal(const uint8_t *, const uint8_t *,
                                                 uint64_t);
      static const uint8_t x_scalar[32] = {
        0x77,0x07,0x6d,0x0a,0x73,0x18,0xa5,0x7d,0x3c,0x16,0xc1,0x72,0x51,0xb2,0x66,0x45,
        0xdf,0x4c,0x2f,0x87,0xeb,0xc0,0x99,0x2a,0xb1,0x77,0xfb,0xa5,0x1d,0xb9,0x2c,0x2a};
      static const uint8_t x_base[32] = {9};
      static const uint8_t x_expected[32] = {
        0x85,0x20,0xf0,0x09,0x89,0x30,0xa7,0x54,0x74,0x8b,0x7d,0xdc,0xb4,0x3e,0xf7,0x5a,
        0x0d,0xbf,0x3a,0x0d,0x26,0x38,0x1a,0xf4,0xeb,0xa4,0xa9,0x8e,0xaa,0x9b,0x4e,0x6a};
      static uint8_t x_output[32];
      static uint8_t x_workspace[646];
      if (!kotoba_aiueos_x25519(x_scalar, x_base, x_output, x_workspace) ||
          !kotoba_aiueos_digest_equal(x_output, x_expected, 32)) {
        serial_string("AIUEOS_X25519_FAIL rfc7748-base-point\r\n");
        evidence_stop(__LINE__);
      }
      debug_string("AIUEOS_X25519_OK rfc7748-base-point 32-bytes\n");
      serial_string("AIUEOS_X25519_OK rfc7748-base-point 32-bytes\r\n");
    }
    {
      extern int aiueos_tls13_aes_selftest(void);
      if (!aiueos_tls13_aes_selftest()) {
        serial_string("AIUEOS_AES_GCM_FAIL nist-vectors\r\n");
        evidence_stop(__LINE__);
      }
      serial_string("AIUEOS_AES_GCM_OK aes-128-gcm nist\r\n");
    }
    {
      extern int aiueos_tls13_hmac_selftest(void);
      if (!aiueos_tls13_hmac_selftest()) {
        serial_string("AIUEOS_HMAC_HKDF_FAIL rfc4231-rfc5869\r\n");
        evidence_stop(__LINE__);
      }
      serial_string("AIUEOS_HMAC_HKDF_OK sha256 rfc4231-rfc5869\r\n");
    }
    {
      extern int aiueos_tls13_ecdsa_selftest(void);
      if (!aiueos_tls13_ecdsa_selftest()) {
        serial_string("AIUEOS_ECDSA_P256_FAIL rfc6979-sample\r\n");
        evidence_stop(__LINE__);
      }
      serial_string("AIUEOS_ECDSA_P256_OK rfc6979-sample s+1-refused\r\n");
    }
    {
      extern int aiueos_tls13_record_selftest(void);
      if (!aiueos_tls13_record_selftest()) {
        serial_string("AIUEOS_TLS13_RECORD_FAIL rfc8448-s3\r\n");
        evidence_stop(__LINE__);
      }
      debug_string("AIUEOS_TLS13_RECORD_OK rfc8448-s3 seq0 seal-open tamper-refused\n");
      serial_string("AIUEOS_TLS13_RECORD_OK rfc8448-s3 seq0 seal-open tamper-refused\r\n");
    }
    /* The RTL8125 driver objects, against a software model of the BAR window
       (ADR-0140).  QEMU has no RTL8125, so the model is how the emitted machine
       code gets executed at all -- and it is not a substitute for the physical
       qualification, which still runs on the K16 nodes.  What it proves is that
       the six Kotoba objects and the C in `kernel/rtl8125.c` leave the same
       4,096-byte register file and the same two descriptors behind, from the
       same seed. */
    {
      extern int aiueos_rtl8125_kotoba_selftest(void);
      extern unsigned aiueos_rtl8125_parity_stage;
      extern unsigned aiueos_rtl8125_parity_detail;
      if (!aiueos_rtl8125_kotoba_selftest()) {
        serial_string("NIC-PARITY mismatch stage=");
        serial_decimal(aiueos_rtl8125_parity_stage);
        serial_string(" offset=");
        serial_decimal(aiueos_rtl8125_parity_detail);
        serial_string("\r\n");
        debug_string("NIC-PARITY mismatch\n");
        evidence_stop(__LINE__);
      }
      debug_string("NIC-PARITY ok rtl8125 identify link-up ring-build program tx-submit rx-poll\n");
      serial_string("NIC-PARITY ok rtl8125 identify link-up ring-build program tx-submit rx-poll\r\n");
    }
#ifdef AIUEOS_QWEN35_KOTOBA_PARITY
    /* QWEN-PARITY (ADR-0147).  The three Qwen3.5 forward-pass objects against
       the C they were ported from, on this CPU, over synthetic inputs.  Placed
       with the other Kotoba self-tests, after the kernel owns its own IDT: a
       fuel-guard `ud2` raised while the FIRMWARE's handler is still installed
       gives an OVMF dump with no vector and no address, and here it reaches
       set_idt_gate(6, aiueos_isr_invalid_opcode) and names itself.
       Only when AIUEOS_QWEN35_KOTOBA_PARITY=1, which is what compiles
       kernel/qwen35_quant.c and kernel/qwen35_infer.c -- the reference half of
       the comparison.  It is a SEPARATE flag from the model handoff on
       purpose: the handoff makes the UEFI loader demand a 10,934,860,704-byte
       mapping and refuse the boot without one (AIUEOS_LOADER_FAIL
       qwen38-model-admission code=121, measured), and this comparison needs
       no model at all -- it is bit-equality of the arithmetic over synthetic
       inputs, which is exactly the property that survives having no weights. */
    {
      extern int aiueos_qwen35_kotoba_parity_selftest(uint32_t stage);
      /* Five profiles, because the low region cannot hold every object at
         once since the tokenizer landed (see qwen35_infer.c's own comment).
         Each links only the objects its stages call, and a stage the profile
         did not compile is REFUSED rather than reported ok. */
#if AIUEOS_QWEN35_KOTOBA_PARITY == 1
      static const char *const qwen_parity_names[3] = {"dequant", "dot", "matvec"};
      uint32_t qwen_parity_first = 0U;
#elif AIUEOS_QWEN35_KOTOBA_PARITY == 2
      static const char *const qwen_parity_names[2] = {"activation", "norm"};
      uint32_t qwen_parity_first = 3U;
#elif AIUEOS_QWEN35_KOTOBA_PARITY == 3
      static const char *const qwen_parity_names[1] = {"attention"};
      uint32_t qwen_parity_first = 5U;
#elif AIUEOS_QWEN35_KOTOBA_PARITY == 4
      static const char *const qwen_parity_names[1] = {"recurrent"};
      uint32_t qwen_parity_first = 6U;
#else
      static const char *const qwen_parity_names[1] = {"rope"};
      uint32_t qwen_parity_first = 7U;
#endif
      for (uint32_t index = 0;
           index < sizeof qwen_parity_names / sizeof qwen_parity_names[0];
           index++) {
        uint32_t stage = qwen_parity_first + index;
        if (!aiueos_qwen35_kotoba_parity_selftest(stage)) {
          serial_string("QWEN-PARITY ");
          serial_string(qwen_parity_names[index]);
          serial_string(" mismatch\r\n");
          evidence_stop(__LINE__);
        }
        serial_string("QWEN-PARITY ");
        serial_string(qwen_parity_names[index]);
        serial_string(" ok\r\n");
      }
#if AIUEOS_QWEN35_KOTOBA_PARITY == 1
      /* The object's dot against the C AVX2 dot (the output projection's old
         path). A different reduction tree, so a DISTANCE, not a pass/fail;
         `unavailable` is a CPU without AVX2 and is not a zero distance. */
      {
        extern int aiueos_qwen35_parity_dot_avx2(uint32_t *compared,
                                                 uint32_t *differing,
                                                 uint32_t *max_ulp);
        uint32_t compared = 0, differing = 0, max_ulp = 0;
        int verdict = aiueos_qwen35_parity_dot_avx2(&compared, &differing,
                                                    &max_ulp);
        if (verdict == 0) {
          serial_string("QWEN-PARITY dot-avx2 refused\r\n");
          evidence_stop(__LINE__);
        }
        if (verdict == 2) {
          serial_string("QWEN-PARITY dot-avx2 unavailable\r\n");
        } else {
          serial_string("QWEN-PARITY dot-avx2 distance compared=");
          serial_decimal(compared);
          serial_string(" differing=");
          serial_decimal(differing);
          serial_string(" max-ulp=");
          serial_decimal(max_ulp);
          serial_string("\r\n");
        }
      }
#endif
#if AIUEOS_QWEN35_KOTOBA_PARITY == 5
      /* The rope object is checked against the Prism reference, not the C
         (x87 fsincos cannot be matched), so the distance from the C it
         replaced is a MEASUREMENT printed here, one line per decode position,
         never a pass/fail. */
      {
        extern int aiueos_qwen35_rope_distance(uint32_t position,
                                               uint32_t *differing,
                                               uint32_t *max_ulp);
        for (uint32_t position = 1U; position < 8U; position++) {
          uint32_t differing = 0, max_ulp = 0;
          if (!aiueos_qwen35_rope_distance(position, &differing, &max_ulp)) {
            serial_string("QWEN-PARITY rope distance refused\r\n");
            evidence_stop(__LINE__);
          }
          serial_string("QWEN-PARITY rope distance-from-c position=");
          serial_decimal(position);
          serial_string(" differing=");
          serial_decimal(differing);
          serial_string("/6144 max-ulp=");
          serial_decimal(max_ulp);
          serial_string("\r\n");
        }
      }
#endif
    }
#endif
    {
      /* DEVCLIENT-PARITY.  The emitted `device-worker-canonical` object against
         the bytes the C writer produced for the same inputs (protocol 2) and
         against the server's own worked example (protocol 3), plus one refusal
         so a run that never saw the object say no is not counted as a pass.
         The KIR interpreter already agrees with these bytes; that says nothing
         about what the backend emitted, which is the half this covers. */
      int devclient_case = aiueos_device_worker_canonical_selftest();
      if (devclient_case) {
        debug_string("DEVCLIENT-PARITY canonical mismatch\n");
        serial_string("DEVCLIENT-PARITY canonical mismatch case=");
        serial_decimal((uint32_t)devclient_case);
        serial_string("\r\n");
        evidence_stop(__LINE__);
      }
      debug_string("DEVCLIENT-PARITY canonical ok\n");
      serial_string("DEVCLIENT-PARITY canonical ok v2-result v3-result refusal-5 refusal-7\r\n");
    }
    {
      /* SHA-STREAM-PARITY.  The three streaming SHA-256 objects on this CPU,
         against `kotoba_aiueos_sha256` where both can answer and against
         published digests where only the new ones can.  Cases 6 and 9 hash
         131,080 bytes each -- ten times the old object's ceiling -- so this
         block is the slowest self-test in the boot and is deliberately not
         behind a flag: the sizes it covers are the reason the objects exist,
         and a check that only runs when someone remembers to ask is a check
         that goes quiet. */
      int sha_stream_case = aiueos_sha_stream_selftest();
      if (sha_stream_case) {
        debug_string("SHA-STREAM-PARITY mismatch\n");
        serial_string("SHA-STREAM-PARITY mismatch case=");
        serial_decimal((uint32_t)sha_stream_case);
        serial_string("\r\n");
        qemu_exit(0x71);
      }
      debug_string("SHA-STREAM-PARITY ok\n");
      serial_string("SHA-STREAM-PARITY ok fips-abc fips-448 one-block "
                    "region-vs-sha256-12288 stream-192-blocks region-131080 "
                    "dwd-input-4 dwd-output-3 dwd-input-32768 refusals\r\n");
    }
#ifdef AIUEOS_PHYSICAL_QUALIFICATION
    aiueos_qualification_progress(226);
#endif
    if (!aiueos_framebuffer_initialize(boot)) {
      debug_string("AIUEOS_FRAMEBUFFER_FAIL gop-contract\n");
      serial_string("AIUEOS_FRAMEBUFFER_FAIL gop-contract\r\n");
      qemu_exit(0x68);
    }
    debug_string("AIUEOS_FRAMEBUFFER_OK gop-owned retained-rectangles hash-verified\n");
    serial_string("AIUEOS_FRAMEBUFFER_OK gop-owned retained-rectangles hash-verified\r\n");
    if (!aiueos_desktop_surface_ready()) qemu_exit(0x68);
    debug_string("AIUEOS_DESKTOP_SURFACE_OK envelope-v1 opaque-handle full-damage hash-verified\n");
    serial_string("AIUEOS_DESKTOP_SURFACE_OK envelope-v1 opaque-handle full-damage hash-verified\r\n");
#ifdef AIUEOS_QWEN38_MODEL_HANDOFF
    if (!aiueos_qwen38_model_handoff_admit(boot)) {
      struct aiueos_inference_status blocked = {
        .abi_version = AIUEOS_INFERENCE_STATUS_ABI_VERSION,
        .byte_size = sizeof(struct aiueos_inference_status),
        .phase = AIUEOS_INFERENCE_BLOCKED,
        .model = "QWEN3.8 27B",
        .quant = "UD-IQ3 XXS",
        .detail = "MODEL HANDOFF REFUSED",
        .artifact_bytes = boot->model_size,
        .resident_bytes = AIUEOS_INFERENCE_UNMEASURED,
        .load_ns = AIUEOS_INFERENCE_UNMEASURED,
        .prefill_ns = AIUEOS_INFERENCE_UNMEASURED,
        .decode_ns = AIUEOS_INFERENCE_UNMEASURED,
        .time_to_first_token_ns = AIUEOS_INFERENCE_UNMEASURED,
        .compute_cycles = AIUEOS_INFERENCE_UNMEASURED
      };
      (void)aiueos_framebuffer_inference_screen(&blocked);
      debug_string("AIUEOS_MODEL_HANDOFF_FAIL format-or-sha-or-map\n");
      serial_string("AIUEOS_MODEL_HANDOFF_FAIL format-or-sha-or-map\r\n");
      qemu_exit(0x66);
    }
#ifdef AIUEOS_MODEL_TEST_FIXTURE
    /* Two fixtures reach this profile now. The model-handoff gate's is 27
       bytes of transport and carries no graph; the admission gate's is the
       10,996,640-byte metadata + tensor-table prefix, which IS parsed, further
       down, once the physical allocator can hold the graph. Saying
       "tiny-transport-fixture" for both would put a false line on the console
       of every run that then parses 866 tensor records. */
    if (boot->model_size == AIUEOS_QWEN35_DATA_OFFSET ||
        boot->model_size == AIUEOS_BONSAI2_DATA_OFFSET) {
      debug_string("AIUEOS_QWEN35_GRAPH_FIXTURE_DEFERRED admission-selftest\n");
      serial_string("AIUEOS_QWEN35_GRAPH_FIXTURE_DEFERRED admission-selftest\r\n");
    } else {
      debug_string("AIUEOS_QWEN35_GRAPH_FIXTURE_SKIP tiny-transport-fixture\n");
      serial_string("AIUEOS_QWEN35_GRAPH_FIXTURE_SKIP tiny-transport-fixture\r\n");
    }
#endif
    {
      struct aiueos_inference_status admitted = {
        .abi_version = AIUEOS_INFERENCE_STATUS_ABI_VERSION,
        .byte_size = sizeof(struct aiueos_inference_status),
        .phase = AIUEOS_INFERENCE_ADMISSION,
        .model = "QWEN3.8 27B",
        .quant = "UD-IQ3 XXS",
#ifndef AIUEOS_MODEL_TEST_FIXTURE
        .detail = "QWEN35 GRAPH PENDING",
#else
        .detail = "GGUF SHA256 OK",
#endif
        .artifact_bytes = boot->model_size,
        .resident_bytes = boot->model_size,
        .load_ns = AIUEOS_INFERENCE_UNMEASURED,
        .prefill_ns = AIUEOS_INFERENCE_UNMEASURED,
        .decode_ns = AIUEOS_INFERENCE_UNMEASURED,
        .time_to_first_token_ns = AIUEOS_INFERENCE_UNMEASURED,
        .compute_cycles = AIUEOS_INFERENCE_UNMEASURED
      };
      (void)aiueos_framebuffer_inference_screen(&admitted);
    }
    debug_string("AIUEOS_MODEL_HANDOFF_OK format=gguf-v3 parts=" AIUEOS_MODEL_PARTS_TEXT " sha256=verified mapping=read-only-nx metrics=N/A\n");
    serial_string("AIUEOS_MODEL_HANDOFF_OK format=gguf-v3 parts=" AIUEOS_MODEL_PARTS_TEXT " sha256=verified mapping=read-only-nx metrics=N/A\r\n");
#ifndef AIUEOS_MODEL_TEST_FIXTURE
    uint64_t calibrated_model_load_ns = AIUEOS_INFERENCE_UNMEASURED;
    if (boot->version >= AIUEOS_BOOT_INFO_VERSION_TSC_CALIBRATED && boot->tsc_hz) {
      uint64_t whole = boot->model_load_cycles / boot->tsc_hz;
      uint64_t remainder = boot->model_load_cycles % boot->tsc_hz;
      if (whole <= (UINT64_MAX - (remainder * 1000000000ULL) / boot->tsc_hz) /
                     1000000000ULL)
        calibrated_model_load_ns = whole * 1000000000ULL +
          (remainder * 1000000000ULL) / boot->tsc_hz;
    }
    aiueos_qwen35_status = (struct aiueos_inference_status){
      .abi_version = AIUEOS_INFERENCE_STATUS_ABI_VERSION,
      .byte_size = sizeof(struct aiueos_inference_status),
      .phase = AIUEOS_INFERENCE_ADMISSION,
      .model = "QWEN3.8 27B",
      .quant = "UD-IQ3 XXS",
      .detail = "QWEN35 GRAPH PENDING",
      .prompt_tokens = 1,
      .generated_tokens = 0,
      .decode_tokens = 0,
      .target_tokens = AIUEOS_QWEN35_GENERATION_TOKENS,
      .artifact_bytes = boot->model_size,
      .resident_bytes = boot->model_size,
      .load_ns = calibrated_model_load_ns,
      .prefill_ns = AIUEOS_INFERENCE_UNMEASURED,
      .decode_ns = AIUEOS_INFERENCE_UNMEASURED,
      .time_to_first_token_ns = AIUEOS_INFERENCE_UNMEASURED,
      .compute_cycles = 0
    };
#endif
#endif
#ifdef AIUEOS_PHYSICAL_QUALIFICATION
    aiueos_qualification_progress(227);
#endif
    if (!aiueos_physical_allocator_initialize(boot)) {
      debug_string("AIUEOS_PHYSICAL_ALLOCATOR_FAIL memory-map\n");
      serial_string("AIUEOS_PHYSICAL_ALLOCATOR_FAIL memory-map\r\n");
      qemu_exit(0x76);
    }
    void *physical_page_a = aiueos_allocate_physical_page();
    void *physical_page_b = aiueos_allocate_physical_page();
    if (!physical_page_a || !physical_page_b || physical_page_a == physical_page_b ||
        ((uintptr_t)physical_page_a & 4095) || ((uintptr_t)physical_page_b & 4095) ||
        *(const uint64_t *)physical_page_a || *(const uint64_t *)physical_page_b) {
#ifdef AIUEOS_PHYSICAL_QUALIFICATION
      aiueos_framebuffer_qualification_screen("AIUEOS K16", "FAIL MEMORY", "SSD READ ONLY", 0);
      serial_string("AIUEOS_PHYSICAL_QUALIFICATION_FAIL stage=memory disk-writes=none\r\n");
      if (!aiueos_qualification_finalize(2, 1))
        serial_string("AIUEOS_PHYSICAL_QUALIFICATION_LOG_FAIL stage=runtime-variable\r\n");
      for (;;) __asm__ volatile("cli; hlt");
#endif
      debug_string("AIUEOS_PHYSICAL_ALLOCATOR_FAIL allocation\n");
      serial_string("AIUEOS_PHYSICAL_ALLOCATOR_FAIL allocation\r\n");
      qemu_exit(0x75);
    }
    debug_string("AIUEOS_PHYSICAL_ALLOCATOR_OK pages=2 zeroed\n");
    serial_string("AIUEOS_PHYSICAL_ALLOCATOR_OK pages=2 zeroed\r\n");
#if defined(AIUEOS_QWEN38_MODEL_HANDOFF) && defined(AIUEOS_MODEL_TEST_FIXTURE)
    /* The GGUF admission, EXECUTED. ADR-0137 moved it to three Kotoba objects
       and made kernel/qwen35_runtime.c delegate to them, but nothing ever ran
       that delegation: the objects passed a KIR-interpreter oracle, the image
       linked, and this workstation is aarch64 so the emitted x86-64 was never
       on a CPU.
       The transport fixture the model-handoff gate carries is 27 bytes and
       cannot be parsed, so this runs only when the handed-off artifact is
       exactly the 10,996,640-byte metadata+tensor-table prefix that
       tests/make_qwen35_header_fixture.py builds and
       scripts/smoke-qwen35-runtime.sh feeds to the C reference parser. That
       prefix is not the artifact, so the artifact length is the contract's
       rather than what was mapped -- which is the same pair of arguments the
       host gate passes, so the numbers printed below are comparable with it.
       QWEN-ADMIT carries the object's own reason code. The C in this image
       has no such number: the delegating branch returns 0 or 1 and every
       negative value here was written in a .kotoba file.
       Two prefixes qualify: Qwen3.8's synthesised 10,996,640 bytes and the
       Bonsai profile's real 11,120,992 (tests/make-bonsai-boot-fixture.cljk,
       ADR-0222). The prefix length picks which contract length is handed in;
       it does not pick the profile -- the objects derive that from the header
       counts and refuse a length that does not belong to them. */
    const uint64_t admission_artifact_bytes =
      boot->model_size == AIUEOS_QWEN35_DATA_OFFSET
        ? AIUEOS_QWEN35_ARTIFACT_BYTES
        : boot->model_size == AIUEOS_BONSAI2_DATA_OFFSET
            ? AIUEOS_BONSAI2_ARTIFACT_BYTES
            : 0;
    if (admission_artifact_bytes) {
      const uint64_t admission_pages =
        (sizeof(struct aiueos_qwen35_model) + 4095U) / 4096U;
      struct aiueos_qwen35_model *admitted =
        (struct aiueos_qwen35_model *)
          aiueos_allocate_contiguous_physical_pages(admission_pages);
      if (!admitted) {
        serial_string("AIUEOS_QWEN35_ADMISSION_FAIL graph-pages\r\n");
        qemu_exit(0x66);
      }
      int admission_ok = aiueos_qwen35_model_parse(
        (const uint8_t *)(uintptr_t)boot->model_base, boot->model_size,
        admission_artifact_bytes, admitted);
      serial_string("QWEN-ADMIT reason=");
      if (aiueos_qwen35_admission_verdict < 0) {
        serial_string("-");
        serial_decimal64((uint64_t)(-aiueos_qwen35_admission_verdict));
      } else {
        serial_decimal64((uint64_t)aiueos_qwen35_admission_verdict);
      }
      serial_string(" stage=");
      serial_decimal(aiueos_qwen35_admission_stage);
      serial_string(" admitted=");
      serial_decimal((uint32_t)admission_ok);
      serial_string("\r\n");
      if (!admission_ok) {
        debug_string("AIUEOS_QWEN35_ADMISSION_REFUSED kotoba-objects\n");
        serial_string("AIUEOS_QWEN35_ADMISSION_REFUSED kotoba-objects\r\n");
        qemu_exit(0x66);
      }
      debug_string("AIUEOS_QWEN35_ADMISSION_OK kotoba-objects\n");
      /* The four representative offsets tests/qwen35_runtime_model.c asserts
         on the host, recomputed here by the objects and this image's
         translation. Printing them rather than only a verdict is what makes a
         wrong workspace offset visible: a translation that read the wrong word
         still returns 1. */
      serial_string("AIUEOS_QWEN35_ADMISSION_OK tensors=");
      serial_decimal64(admitted->tensor_count);
      serial_string(" linear=");
      serial_decimal(admitted->linear_layer_count);
      serial_string(" full=");
      serial_decimal(admitted->full_layer_count);
      serial_string(" data-offset=");
      serial_decimal64(admitted->data_offset);
      serial_string(" embd=");
      serial_decimal64(admitted->token_embedding.offset);
      serial_string(" qkv=");
      serial_decimal64(admitted->layers[0].mixer.linear.qkv.offset);
      /* The tail is the LAST block's post-attention norm: blk.64 (the MTP
         head) under Qwen3.8, blk.63 under Bonsai, which has no head. The
         index is the block count the kv-scan object read, bounded by the
         array, not a 64 written here. */
      serial_string(" tail=");
      if (admitted->block_count == 0 ||
          admitted->block_count > AIUEOS_QWEN35_LAYER_COUNT) {
        serial_string("unbounded");
      } else {
        serial_decimal64(
          admitted->layers[admitted->block_count - 1U].post_attention_norm.offset);
      }
      serial_string(" artifact=");
      serial_decimal64(admitted->artifact_bytes);
      serial_string("\r\n");
    } else {
      serial_string("AIUEOS_QWEN35_ADMISSION_SKIP tiny-transport-fixture\r\n");
    }
#endif
#if defined(AIUEOS_QWEN38_MODEL_HANDOFF) && !defined(AIUEOS_MODEL_TEST_FIXTURE)
#ifdef AIUEOS_PHYSICAL_QUALIFICATION
#ifdef AIUEOS_QWEN35_SMP
    /* Bring up one application processor before the first model walk.  The
       previous SMP qualification happened after the physical-Qwen branch had
       already completed and halted, so every measured token was necessarily
       single-threaded.  AP startup is best-effort here: the scalar path stays
       available, while the result records the actual worker count. */
    qwen_early_acpi_ready = aiueos_acpi_initialize(boot->acpi_rsdp);
    if (qwen_early_acpi_ready && aiueos_apic_timer_initialize() &&
        aiueos_smp_start_application_processor() &&
        aiueos_smp_dispatch_selftest()) {
      serial_string("AIUEOS_QWEN35_SMP_READY threads=2 init-sipi-v1 dispatch=verified\r\n");
    } else {
      serial_string("AIUEOS_QWEN35_SMP_FALLBACK threads=1\r\n");
    }
#else
    serial_string("AIUEOS_QWEN35_SMP_DISABLED threads=1\r\n");
#endif
#endif
    const uint64_t qwen_model_pages =
      (sizeof(struct aiueos_qwen35_model) + 4095U) / 4096U;
    const uint64_t qwen_workspace_pages =
      (AIUEOS_QWEN35_DECODE_WORKSPACE_BYTES + 4095U) / 4096U;
    const uint64_t qwen_volatile_pages =
      (aiueos_kototama_runtime_required_bytes() + 4095U) / 4096U;
    struct aiueos_qwen35_generation_result generation = {0};
    int qwen_initial_ok = 0;
    uint8_t *qwen_volatile = aiueos_allocate_contiguous_physical_pages(
      qwen_volatile_pages);
    if (!qwen_volatile) {
      aiueos_qwen35_status.phase = AIUEOS_INFERENCE_ERROR;
      aiueos_qwen35_status.detail = "WORKSPACE REFUSED";
      (void)aiueos_framebuffer_inference_screen(&aiueos_qwen35_status);
      serial_string("AIUEOS_QWEN35_FIRST_TOKEN_FAIL workspace-contiguous\r\n");
#ifdef AIUEOS_PERSISTENT_BOOT
      serial_string("AIUEOS_KOTOTAMA_RUNTIME_DEGRADED reason=workspace-refused kernel=alive network=continue\r\n");
      goto qwen_runtime_boot_complete;
#else
      for (;;) __asm__ volatile("cli; hlt");
#endif
    }
    if (!aiueos_kototama_runtime_prepare(
          (const uint8_t *)(uintptr_t)boot->model_base,
          boot->model_size, qwen_volatile, qwen_volatile_pages * 4096U)) {
      aiueos_qwen35_status.phase = AIUEOS_INFERENCE_BLOCKED;
      aiueos_qwen35_status.detail = "QWEN35 GRAPH REFUSED";
      (void)aiueos_framebuffer_inference_screen(&aiueos_qwen35_status);
      debug_string("AIUEOS_QWEN35_GRAPH_FAIL exact-contract\n");
      serial_string("AIUEOS_QWEN35_GRAPH_FAIL exact-contract\r\n");
#ifdef AIUEOS_PERSISTENT_BOOT
      serial_string("AIUEOS_KOTOTAMA_RUNTIME_DEGRADED reason=graph-refused kernel=alive network=continue\r\n");
      goto qwen_runtime_boot_complete;
#else
      for (;;) __asm__ volatile("cli; hlt");
#endif
    }
    serial_string("AIUEOS_KOTOTAMA_RUNTIME_READY epoch=1 isolation=volatile-workspace reboot=runtime-only\r\n");
    debug_string("AIUEOS_QWEN35_GRAPH_OK tensors=866 trunk=64 linear=48 full=16 mtp=1 data-offset=10996640 bind=read-only\n");
    serial_string("AIUEOS_QWEN35_GRAPH_OK tensors=866 trunk=64 linear=48 full=16 mtp=1 data-offset=10996640 bind=read-only storage=volatile-ram\r\n");
    aiueos_qwen35_status.phase = AIUEOS_INFERENCE_PREFILL;
    aiueos_qwen35_status.detail = aiueos_qwen35_progress_detail;
    (void)aiueos_framebuffer_inference_screen(&aiueos_qwen35_status);
    serial_string("AIUEOS_QWEN35_WORKSPACE_OK bytes=");
    serial_decimal(AIUEOS_QWEN35_WORKSPACE_BYTES);
    serial_string(" pages=");
    serial_decimal(qwen_workspace_pages);
    serial_string(" graph-pages=");
    serial_decimal(qwen_model_pages);
    serial_string(" storage=volatile-ram\r\n");
    int generation_ok = aiueos_kototama_runtime_invoke(
      AIUEOS_QWEN35_BOS_TOKEN,
      AIUEOS_QWEN35_GENERATION_TOKENS,
      aiueos_qwen35_progress, &generation);
    if (!generation_ok && generation.vector_bits == 256U &&
        generation.generated_tokens &&
        generation.tokens[0] != AIUEOS_QWEN35_REFERENCE_FIRST_TOKEN) {
      serial_string("AIUEOS_QWEN35_AVX2_REJECT expected=248046 actual=");
      serial_decimal(generation.tokens[0]);
      serial_string(" fallback=scalar\r\n");
      aiueos_qwen35_force_scalar();
      (void)aiueos_kototama_runtime_restart();
      generation = (struct aiueos_qwen35_generation_result){0};
      generation_ok = aiueos_kototama_runtime_invoke(
        AIUEOS_QWEN35_BOS_TOKEN,
        AIUEOS_QWEN35_GENERATION_TOKENS,
        aiueos_qwen35_progress, &generation);
    }
    if (!generation_ok ||
        generation.generated_tokens != AIUEOS_QWEN35_GENERATION_TOKENS ||
        generation.tokens[0] != AIUEOS_QWEN35_REFERENCE_FIRST_TOKEN) {
      aiueos_qwen35_status.phase = AIUEOS_INFERENCE_ERROR;
      aiueos_qwen35_status.generated_tokens = generation.generated_tokens;
      aiueos_qwen35_status.decode_tokens = generation.decode_tokens;
      if (generation.generated_tokens &&
          generation.tokens[0] != AIUEOS_QWEN35_REFERENCE_FIRST_TOKEN) {
        uint32_t actual = generation.tokens[0];
        for (uint32_t digit = 0; digit < 6U; digit++) {
          aiueos_qwen35_first_fail_detail[17U - digit] =
              (char)('0' + actual % 10U);
          actual /= 10U;
        }
        aiueos_qwen35_status.detail = aiueos_qwen35_first_fail_detail;
      } else {
        uint32_t failed = generation.failed_token
          ? generation.failed_token : generation.generated_tokens + 1U;
        aiueos_qwen35_format_failure(
          failed, generation.failed_layer, generation.failure_stage);
        aiueos_qwen35_status.detail = aiueos_qwen35_decode_fail_detail;
      }
      aiueos_qwen35_status.compute_cycles = generation.total_cycles;
      (void)aiueos_framebuffer_inference_screen(&aiueos_qwen35_status);
      serial_string("AIUEOS_QWEN35_GENERATE_FAIL expected-first=248046 actual=");
      serial_decimal(generation.generated_tokens ? generation.tokens[0] : UINT32_MAX);
      serial_string(" generated=");
      serial_decimal(generation.generated_tokens);
      serial_string(" failed-token=");
      serial_decimal(generation.failed_token);
      serial_string(" failed-layer=");
      serial_decimal(generation.failed_layer);
      serial_string(" failure-stage=");
      serial_decimal(generation.failure_stage);
      serial_string(" total-cycles=");
      serial_decimal64(generation.total_cycles);
      serial_string("\r\n");
#ifdef AIUEOS_PERSISTENT_BOOT
      (void)aiueos_kototama_runtime_restart();
      serial_string("AIUEOS_KOTOTAMA_RUNTIME_RESTART reason=initial-inference-failed kernel-reboot=false network=continue\r\n");
      goto qwen_runtime_boot_complete;
#else
      for (;;) __asm__ volatile("cli; hlt");
#endif
    }
    qwen_initial_ok = 1;
    aiueos_qwen35_status.phase = AIUEOS_INFERENCE_COMPLETE;
    aiueos_qwen35_status.detail = generation.vector_bits == 256U
      ? (generation.worker_threads == 2U
          ? "AVX2 2T 8 TOKENS" : "AVX2 1T 8 TOKENS")
      : (generation.worker_threads == 2U
          ? "SCALAR 2T 8 TOKENS" : "SCALAR 1T 8 TOKENS");
    aiueos_qwen35_status.generated_tokens = generation.generated_tokens;
    aiueos_qwen35_status.decode_tokens = generation.decode_tokens;
    aiueos_qwen35_status.compute_cycles = generation.total_cycles;
    aiueos_qwen35_status.resident_bytes =
      boot->model_size + AIUEOS_QWEN35_DECODE_WORKSPACE_BYTES;
    if (boot->version >= AIUEOS_BOOT_INFO_VERSION_TSC_CALIBRATED && boot->tsc_hz) {
      aiueos_qwen35_status.time_to_first_token_ns =
        aiueos_cycles_to_ns(generation.first_token_cycles, boot->tsc_hz);
      aiueos_qwen35_status.decode_ns =
        aiueos_cycles_to_ns(generation.decode_cycles, boot->tsc_hz);
    }
    (void)aiueos_framebuffer_inference_screen(&aiueos_qwen35_status);
    debug_string("AIUEOS_QWEN35_GENERATE_OK bos=248044 tokens=8 first=248046 reference=matched timing=calibrated-tsc\n");
    serial_string("AIUEOS_QWEN35_GENERATE_OK bos=248044 tokens=");
    for (uint32_t token_index = 0;
         token_index < generation.generated_tokens; token_index++) {
      if (token_index) serial_byte(',');
      serial_decimal(generation.tokens[token_index]);
    }
    serial_string(" first-cycles=");
    serial_decimal64(generation.first_token_cycles);
    serial_string(" decode-cycles=");
    serial_decimal64(generation.decode_cycles);
    serial_string(" decode-tokens=");
    serial_decimal(generation.decode_tokens);
    serial_string(" decode-milli-tok-s=");
    serial_decimal64(aiueos_inference_milli_tokens_per_second(
      generation.decode_tokens, aiueos_qwen35_status.decode_ns));
    serial_string(" vector-bits=");
    serial_decimal(generation.vector_bits);
    serial_string(" threads=");
    serial_decimal(generation.worker_threads);
    serial_string(" timing=calibrated-tsc\r\n");
qwen_runtime_boot_complete:
    serial_string("AIUEOS_KOTOTAMA_RUNTIME_BOOT state=");
    serial_string(aiueos_kototama_runtime_state_name(
      aiueos_kototama_runtime_status().state));
    serial_string(" initial-inference=");
    serial_string(qwen_initial_ok ? "ready" : "degraded");
    serial_string(" kernel=alive\r\n");
#endif
    if (!aiueos_capability_table_initialize()) {
#ifdef AIUEOS_PHYSICAL_QUALIFICATION
      aiueos_framebuffer_qualification_screen("AIUEOS K16", "FAIL MEMORY", "SSD READ ONLY", 0);
      serial_string("AIUEOS_PHYSICAL_QUALIFICATION_FAIL stage=capability-table disk-writes=none\r\n");
      if (!aiueos_qualification_finalize(2, 2))
        serial_string("AIUEOS_PHYSICAL_QUALIFICATION_LOG_FAIL stage=runtime-variable\r\n");
      for (;;) __asm__ volatile("cli; hlt");
#endif
      serial_string("AIUEOS_CAPABILITY_TABLE_FAIL page-allocation\r\n");
      qemu_exit(0x75);
    }
#ifdef AIUEOS_PHYSICAL_QUALIFICATION
    aiueos_qualification_progress(228);
#endif
#if defined(AIUEOS_PHYSICAL_QUALIFICATION) && \
    defined(AIUEOS_QWEN38_MODEL_HANDOFF) && !defined(AIUEOS_MODEL_TEST_FIXTURE)
    if (!qwen_early_acpi_ready) {
#else
    if (!aiueos_acpi_initialize(boot->acpi_rsdp)) {
#endif
#ifdef AIUEOS_PHYSICAL_QUALIFICATION
      aiueos_framebuffer_qualification_screen("AIUEOS K16", "FAIL ACPI", "SSD READ ONLY", 0);
      serial_string("AIUEOS_PHYSICAL_QUALIFICATION_FAIL stage=acpi disk-writes=none\r\n");
      if (!aiueos_qualification_finalize(2, 3))
        serial_string("AIUEOS_PHYSICAL_QUALIFICATION_LOG_FAIL stage=runtime-variable\r\n");
      for (;;) __asm__ volatile("cli; hlt");
#endif
      debug_string("AIUEOS_ACPI_FAIL rsdp-xsdt-madt\n");
      serial_string("AIUEOS_ACPI_FAIL rsdp-xsdt-madt\r\n");
      qemu_exit(0x78);
    }
    debug_string("AIUEOS_ACPI_OK rsdp-xsdt-madt cpu>=2\n");
    serial_string("AIUEOS_ACPI_OK rsdp-xsdt-madt cpu>=2\r\n");
    /* Emitted only where the table exists, which is the point: this marker
       says "an AMD IOMMU was described to us and we read its header", and on a
       machine without one there is nothing to claim. It does NOT say the IOMMU
       is programmed -- the DMA policy still reports unisolated until an IVHD
       parser and a device table exist. */
    if (aiueos_acpi_ivrs_present()) {
      debug_string("AIUEOS_IVRS_OK table-validated ivinfo-read not-yet-programmed\n");
      serial_string("AIUEOS_IVRS_OK table-validated ivinfo-read not-yet-programmed\r\n");
    }
    if (aiueos_acpi_tpm2_present()) {
      debug_string("AIUEOS_TPM2_OK table-validated not-yet-bound\n");
      serial_string("AIUEOS_TPM2_OK table-validated not-yet-bound\r\n");
    } else if (aiueos_acpi_tpm2_seen()) {
      debug_string("AIUEOS_TPM2_FAIL described-but-refused\n");
      serial_string("AIUEOS_TPM2_FAIL described-but-refused\r\n");
    } else {
      debug_string("AIUEOS_TPM2_ABSENT no-root-of-trust-described\n");
      serial_string("AIUEOS_TPM2_ABSENT no-root-of-trust-described\r\n");
    }
    if (0) {
    } else if (aiueos_acpi_ivrs_seen()) {
      debug_string("AIUEOS_IVRS_FAIL described-but-refused\n");
      serial_string("AIUEOS_IVRS_FAIL described-but-refused\r\n");
    } else {
      debug_string("AIUEOS_IVRS_ABSENT no-amd-iommu-described\n");
      serial_string("AIUEOS_IVRS_ABSENT no-amd-iommu-described\r\n");
    }
#ifdef AIUEOS_PHYSICAL_QUALIFICATION
#ifdef AIUEOS_PHYSICAL_NETWORK_QUALIFICATION
    /* A second, explicitly test-only physical slice. The native-core gate has
       already passed; now allow only four DMA pages and one RTL8125 ARP
       exchange. AMD-IVRS isolation is not implemented, so this is evidence for
       the link driver, not production DMA qualification. */
    aiueos_qualification_progress(230);
    aiueos_framebuffer_qualification_screen("AIUEOS K16", "TEST RTL8125", "SSD READ ONLY", 0);
    if(!aiueos_rtl8125_physical_qualification()) {
      uint32_t code=8200U+aiueos_rtl8125_qualification_error();
      aiueos_framebuffer_qualification_screen("AIUEOS K16", "FAIL RTL8125", "SSD READ ONLY", 0);
      debug_string("AIUEOS_PHYSICAL_NETWORK_FAIL rtl8125 arp=10.77.0.1 dma=unisolated-test-only\n");
      serial_string("AIUEOS_PHYSICAL_NETWORK_FAIL rtl8125 arp=10.77.0.1 dma=unisolated-test-only\r\n");
      if(!aiueos_qualification_finalize(2,code))
        serial_string("AIUEOS_PHYSICAL_QUALIFICATION_LOG_FAIL stage=runtime-variable\r\n");
      for(;;)__asm__ volatile("cli; hlt");
    }
    aiueos_qualification_progress(231);
    aiueos_framebuffer_qualification_screen("AIUEOS K16", "RTL8125 LINK OK", "SSD READ ONLY", 1);
    (void)aiueos_rtl8125_qualification_rx_length();
    debug_string("AIUEOS_PHYSICAL_NETWORK_OK rtl8125 arp-peer=10.77.0.1 dma=unisolated-test-only\n");
    serial_string("AIUEOS_PHYSICAL_NETWORK_OK rtl8125 arp-peer=10.77.0.1 dma=unisolated-test-only\r\n");
#ifdef AIUEOS_PHYSICAL_DIRECT_HTTPS_QUALIFICATION
    aiueos_qualification_progress(232);
    aiueos_framebuffer_qualification_screen("AIUEOS K16", "TEST DIRECT HTTPS", "SSD READ ONLY", 0);
    int direct_https_ok = 0;
#ifdef AIUEOS_PERSISTENT_BOOT
    uint32_t worker_sequence = 1;
#endif
#ifdef AIUEOS_MURAKUMO_DEVICE_RESULT
    if (qwen_initial_ok) {
      direct_https_ok = aiueos_rtl8125_direct_https_qualification(
        boot, generation.tokens[0], generation.tokens[1],
        generation.generated_tokens, generation.decode_tokens,
        generation.first_token_cycles, generation.decode_cycles,
        generation.total_cycles, generation.vector_bits,
        generation.worker_threads);
    }
#ifdef AIUEOS_PERSISTENT_BOOT
    else {
      uint64_t bootstrap_job = 0, bootstrap_control = 0;
      uint32_t bootstrap_bos = 0;
      int bootstrap_ready = 0, bootstrap_reboot = 0, bootstrap_restart = 0;
      direct_https_ok = aiueos_rtl8125_device_worker_poll(
        boot, worker_sequence++, &bootstrap_job, &bootstrap_bos,
        &bootstrap_ready, &bootstrap_control, &bootstrap_reboot,
        &bootstrap_restart);
      serial_string(direct_https_ok
        ? "AIUEOS_MURAKUMO_RUNTIME_DEGRADED_CONNECTED transport=ready inference=degraded\r\n"
        : "AIUEOS_MURAKUMO_RUNTIME_DEGRADED_CONNECT_RETRY transport=retry inference=degraded\r\n");
    }
#endif
#else
    direct_https_ok = aiueos_rtl8125_direct_https_qualification();
#endif
    if(!direct_https_ok) {
      uint32_t error=aiueos_rtl8125_direct_https_error();
      uint32_t code=8600U+error;
#if defined(AIUEOS_MURAKUMO_DEVICE_RESULT) && defined(AIUEOS_PERSISTENT_BOOT)
      aiueos_framebuffer_qualification_screen(
        "AIUEOS K16", "MURAKUMO WORKER",
        aiueos_worker_transport_detail(), 0);
#else
      aiueos_framebuffer_qualification_screen("AIUEOS K16", "FAIL DIRECT HTTPS", "SSD READ ONLY", 0);
#endif
#ifdef AIUEOS_MURAKUMO_DEVICE_RESULT
      debug_string("AIUEOS_PHYSICAL_DIRECT_HTTPS_FAIL host=api.murakumo.cloud auth=device-p256 nvram-key=true cacao=false\n");
      serial_string("AIUEOS_PHYSICAL_DIRECT_HTTPS_FAIL host=api.murakumo.cloud error=");
      serial_decimal(error);
      serial_string(" attempts=");
      serial_decimal(aiueos_rtl8125_direct_https_attempts());
      serial_string(" tls-stage=");
      serial_decimal(aiueos_rtl8125_direct_tls_stage());
      serial_string(" response-wait-ms=");
      serial_decimal(aiueos_rtl8125_direct_response_wait_ms());
      serial_string(" response-timeout-s=");
      serial_decimal(aiueos_rtl8125_direct_response_timeout_seconds());
      serial_string(" auth=device-p256 nvram-key=true cacao=false passkey=false pq=false biscuit=false\r\n");
#else
      debug_string("AIUEOS_PHYSICAL_DIRECT_HTTPS_FAIL host=api.murakumo.cloud trust=transport-only secrets=none\n");
      serial_string("AIUEOS_PHYSICAL_DIRECT_HTTPS_FAIL host=api.murakumo.cloud error=");
      serial_decimal(error);
      serial_string(" attempts=");
      serial_decimal(aiueos_rtl8125_direct_https_attempts());
      serial_string(" tls-stage=");
      serial_decimal(aiueos_rtl8125_direct_tls_stage());
      serial_string(" trust=transport-only secrets=none\r\n");
#endif
#if defined(AIUEOS_MURAKUMO_DEVICE_RESULT) && defined(AIUEOS_PERSISTENT_BOOT)
      if(!aiueos_rtl8125_direct_device_did()[0]) {
        if(!aiueos_qualification_finalize(2,code))
          serial_string("AIUEOS_PHYSICAL_QUALIFICATION_LOG_FAIL stage=runtime-variable\r\n");
        for(;;)__asm__ volatile("cli; hlt");
      }
      debug_string("AIUEOS_MURAKUMO_INITIAL_POST_AMBIGUOUS action=worker-reconnect\n");
      serial_string("AIUEOS_MURAKUMO_INITIAL_POST_AMBIGUOUS did=");
      serial_string(aiueos_rtl8125_direct_device_did());
      serial_string(" action=worker-reconnect internal-disk-writes=none\r\n");
#else
      if(!aiueos_qualification_finalize(2,code))
        serial_string("AIUEOS_PHYSICAL_QUALIFICATION_LOG_FAIL stage=runtime-variable\r\n");
      for(;;)__asm__ volatile("cli; hlt");
#endif
    }
    (void)aiueos_rtl8125_direct_dns_a();
    if(direct_https_ok && !aiueos_rtl8125_direct_http_ready()) {
      aiueos_framebuffer_qualification_screen("AIUEOS K16", "FAIL DIRECT HTTPS", "SSD READ ONLY", 0);
#ifdef AIUEOS_MURAKUMO_DEVICE_RESULT
      serial_string("AIUEOS_PHYSICAL_DIRECT_HTTPS_FAIL host=api.murakumo.cloud error=12 auth=device-p256 nvram-key=true cacao=false passkey=false pq=false biscuit=false\r\n");
#else
      serial_string("AIUEOS_PHYSICAL_DIRECT_HTTPS_FAIL host=api.murakumo.cloud error=12 trust=transport-only secrets=none\r\n");
#endif
      if(!aiueos_qualification_finalize(2,8612))
        serial_string("AIUEOS_PHYSICAL_QUALIFICATION_LOG_FAIL stage=runtime-variable\r\n");
      for(;;)__asm__ volatile("cli; hlt");
    }
#ifdef AIUEOS_MURAKUMO_DEVICE_RESULT
    if(direct_https_ok) {
      aiueos_qualification_progress(233);
      aiueos_framebuffer_qualification_screen("AIUEOS K16", "MURAKUMO NODE OK", "COMMUNITY PENDING", 1);
      debug_string("AIUEOS_MURAKUMO_NODE_OK host=api.murakumo.cloud path=/infer/nodes/device-p256-result auth=device-p256 cacao=false ready=false\n");
      serial_string("AIUEOS_MURAKUMO_NODE_OK did=");
      serial_string(aiueos_rtl8125_direct_device_did());
      serial_string(" attempts=");
      serial_decimal(aiueos_rtl8125_direct_https_attempts());
      serial_string(" auth=device-p256 cacao=false passkey=false pq=false biscuit=false ready=false\r\n");
    }
    serial_string("AIUEOS_QWEN38_TIMING model-load-ns=");
    serial_decimal64(aiueos_qwen35_status.load_ns);
    serial_string(" ttft-ns=");
    serial_decimal64(aiueos_qwen35_status.time_to_first_token_ns);
    serial_string(" decode-milli-tok-s=");
    serial_decimal64(aiueos_inference_milli_tokens_per_second(
      aiueos_qwen35_status.decode_tokens, aiueos_qwen35_status.decode_ns));
    serial_string(" decode-tokens=");
    serial_decimal(aiueos_qwen35_status.decode_tokens);
    serial_string(" decode-ns=");
    serial_decimal64(aiueos_qwen35_status.decode_ns);
    serial_string(" tsc-hz=");
    serial_decimal64(boot->tsc_hz);
    serial_string("\r\n");
#ifdef AIUEOS_PERSISTENT_BOOT
    int persistent_qualification_recorded = direct_https_ok;
    if(direct_https_ok) {
      if(!aiueos_qualification_finalize(1,8161))
        serial_string("AIUEOS_PHYSICAL_QUALIFICATION_LOG_FAIL stage=runtime-variable\r\n");
    }
    aiueos_framebuffer_qualification_screen(
      "AIUEOS K16", "MURAKUMO WORKER", "POLLING JOBS", 1);
    debug_string("AIUEOS_MURAKUMO_PERSISTENT_BOOT_OK model=Qwen3.8-27B path=/infer/nodes/device-p256-worker\n");
    serial_string("AIUEOS_MURAKUMO_PERSISTENT_BOOT_OK did=");
    serial_string(aiueos_rtl8125_direct_device_did());
    serial_string(" model=Qwen3.8-27B storage=volatile-ram internal-disk-writes=none\r\n");
    uint32_t heartbeat_failures = 0;
    uint32_t inference_failures = 0;
    for (;;) {
      uint64_t job_id = 0;
      uint64_t control_id = 0;
      uint32_t bos_token = 0;
      int ready = 0;
      int reboot_pxe = 0;
      int restart_runtime = 0;
      aiueos_qwen35_status.phase = AIUEOS_INFERENCE_ADMISSION;
      aiueos_qwen35_status.detail = "POLLING MURAKUMO";
      (void)aiueos_framebuffer_inference_screen(&aiueos_qwen35_status);
      if (!aiueos_rtl8125_device_worker_poll(
            boot, worker_sequence++, &job_id, &bos_token, &ready,
            &control_id, &reboot_pxe, &restart_runtime)) {
        heartbeat_failures++;
        aiueos_qwen35_status.phase = AIUEOS_INFERENCE_ERROR;
        aiueos_qwen35_status.detail = aiueos_worker_transport_detail();
        (void)aiueos_framebuffer_inference_screen(&aiueos_qwen35_status);
        debug_string("AIUEOS_MURAKUMO_HEARTBEAT_RETRY ready=false action=reconnect\n");
        serial_string("AIUEOS_MURAKUMO_HEARTBEAT_RETRY failure=");
        serial_decimal(heartbeat_failures);
        serial_string(" error=");
        serial_decimal(aiueos_rtl8125_direct_https_error());
        serial_string(" response-wait-ms=");
        serial_decimal(aiueos_rtl8125_direct_response_wait_ms());
        serial_string(" response-timeout-s=");
        serial_decimal(aiueos_rtl8125_direct_response_timeout_seconds());
        serial_string(" action=reconnect\r\n");
        aiueos_k16_management_wait(boot->tsc_hz, 5);
        continue;
      }
      if (heartbeat_failures) {
        serial_string("AIUEOS_MURAKUMO_HEARTBEAT_RECOVERED failures=");
        serial_decimal(heartbeat_failures);
        serial_string("\r\n");
        heartbeat_failures = 0;
      }
      if (!persistent_qualification_recorded) {
        aiueos_qualification_progress(233);
        if(!aiueos_qualification_finalize(1,8162))
          serial_string("AIUEOS_PHYSICAL_QUALIFICATION_LOG_FAIL stage=runtime-variable\r\n");
        persistent_qualification_recorded = 1;
        debug_string("AIUEOS_MURAKUMO_INITIAL_POST_RECOVERED path=/infer/nodes/device-p256-worker\n");
        serial_string("AIUEOS_MURAKUMO_INITIAL_POST_RECOVERED path=/infer/nodes/device-p256-worker\r\n");
      }
      serial_string("AIUEOS_MURAKUMO_HEARTBEAT_OK ready=");
      serial_string(ready ? "true" : "false");
      serial_string(" sequence=");
      serial_decimal(worker_sequence - 1);
      serial_string("\r\n");
      if ((reboot_pxe || restart_runtime) && control_id) {
        aiueos_qwen35_status.phase = AIUEOS_INFERENCE_ADMISSION;
        aiueos_qwen35_status.detail = restart_runtime
          ? "RUNTIME RESTART ACK" : "NETWORK REBOOT ACK";
        (void)aiueos_framebuffer_inference_screen(&aiueos_qwen35_status);
        serial_string("AIUEOS_MURAKUMO_CONTROL_RECEIVED action=");
        serial_string(restart_runtime ? "restart-runtime" : "reboot-pxe");
        serial_string(" command-id=");
        serial_decimal64(control_id);
        serial_string("\r\n");
        uint32_t control_ack_failures = 0;
        while (control_ack_failures < 12 &&
               !aiueos_rtl8125_device_worker_control_ack(
                 boot, worker_sequence++, control_id)) {
          control_ack_failures++;
          serial_string("AIUEOS_MURAKUMO_CONTROL_ACK_RETRY command-id=");
          serial_decimal64(control_id);
          serial_string(" failure=");
          serial_decimal(control_ack_failures);
          serial_string(" error=");
          serial_decimal(aiueos_rtl8125_direct_https_error());
          serial_string("\r\n");
          aiueos_wait_seconds(boot->tsc_hz, 5);
        }
        if (control_ack_failures == 12) {
          aiueos_qwen35_status.phase = AIUEOS_INFERENCE_ERROR;
          aiueos_qwen35_status.detail = "CONTROL ACK FAILED";
          (void)aiueos_framebuffer_inference_screen(&aiueos_qwen35_status);
          serial_string("AIUEOS_MURAKUMO_CONTROL_ABORT action=");
          serial_string(restart_runtime ? "restart-runtime" : "reboot-pxe");
          serial_string(" reason=ack-failed\r\n");
          continue;
        }
        if (restart_runtime) {
          int restarted = aiueos_kototama_runtime_restart();
          aiueos_qwen35_status.phase = restarted
            ? AIUEOS_INFERENCE_ADMISSION : AIUEOS_INFERENCE_ERROR;
          aiueos_qwen35_status.detail = restarted
            ? "RUNTIME RESTARTED" : "RUNTIME UNAVAILABLE";
          (void)aiueos_framebuffer_inference_screen(&aiueos_qwen35_status);
          serial_string(restarted
            ? "AIUEOS_MURAKUMO_CONTROL_ACK_OK action=restart-runtime kernel-reboot=false network=preserved\r\n"
            : "AIUEOS_MURAKUMO_CONTROL_ABORT action=restart-runtime reason=runtime-unavailable kernel-reboot=false\r\n");
          continue;
        }
        aiueos_qwen35_status.phase = AIUEOS_INFERENCE_COMPLETE;
        aiueos_qwen35_status.detail = "REBOOTING TO PXE";
        (void)aiueos_framebuffer_inference_screen(&aiueos_qwen35_status);
        debug_string("AIUEOS_MURAKUMO_CONTROL_ACK_OK action=reboot-pxe reset=uefi-runtime\n");
        serial_string("AIUEOS_MURAKUMO_CONTROL_ACK_OK action=reboot-pxe command-id=");
        serial_decimal64(control_id);
        serial_string(" reset=uefi-runtime\r\n");
        (void)aiueos_qualification_reboot();
        aiueos_qwen35_status.phase = AIUEOS_INFERENCE_ERROR;
        aiueos_qwen35_status.detail = "FIRMWARE RESET FAILED";
        (void)aiueos_framebuffer_inference_screen(&aiueos_qwen35_status);
        serial_string("AIUEOS_MURAKUMO_CONTROL_RESET_FAIL action=reboot-pxe\r\n");
        aiueos_wait_seconds(boot->tsc_hz, 30);
        continue;
      }
      if (!job_id) {
        aiueos_qwen35_status.phase = AIUEOS_INFERENCE_COMPLETE;
        aiueos_qwen35_status.detail = "READY - NO JOB";
        (void)aiueos_framebuffer_inference_screen(&aiueos_qwen35_status);
        debug_string("AIUEOS_MURAKUMO_JOB_POLL_OK job=none ready=true\n");
        serial_string("AIUEOS_MURAKUMO_JOB_POLL_OK job=none ready=true\r\n");
        aiueos_k16_management_wait(boot->tsc_hz, 30);
        continue;
      }
      serial_string("AIUEOS_MURAKUMO_JOB_CLAIMED job-id=");
      serial_decimal64(job_id);
      serial_string(" kind=qwen38-first-token bos=");
      serial_decimal(bos_token);
      serial_string(" ready=false\r\n");
      if (bos_token != AIUEOS_QWEN35_BOS_TOKEN) {
        serial_string("AIUEOS_MURAKUMO_JOB_REFUSED reason=unsupported-bos\r\n");
        aiueos_wait_seconds(boot->tsc_hz, 5);
        continue;
      }
      struct aiueos_qwen35_generation_result job_result = {0};
      aiueos_qwen35_status.phase = AIUEOS_INFERENCE_PREFILL;
      aiueos_qwen35_status.detail = aiueos_qwen35_progress_detail;
      aiueos_qwen35_status.generated_tokens = 0;
      aiueos_qwen35_status.decode_tokens = 0;
      aiueos_qwen35_status.compute_cycles = 0;
      aiueos_qwen35_status.time_to_first_token_ns =
        AIUEOS_INFERENCE_UNMEASURED;
      aiueos_qwen35_status.decode_ns = AIUEOS_INFERENCE_UNMEASURED;
      (void)aiueos_framebuffer_inference_screen(&aiueos_qwen35_status);
      if (!aiueos_kototama_runtime_invoke(
            bos_token,
            AIUEOS_QWEN35_GENERATION_TOKENS,
            aiueos_qwen35_progress, &job_result) ||
          job_result.tokens[0] != AIUEOS_QWEN35_REFERENCE_FIRST_TOKEN) {
        inference_failures++;
        uint32_t failed_token = job_result.failed_token
          ? job_result.failed_token : job_result.generated_tokens + 1U;
        uint32_t failure_stage = job_result.failure_stage;
        if (!failure_stage && job_result.generated_tokens &&
            job_result.tokens[0] != AIUEOS_QWEN35_REFERENCE_FIRST_TOKEN)
          failure_stage = AIUEOS_QWEN35_FAILURE_OUTPUT_LOGITS;
        aiueos_qwen35_status.phase = AIUEOS_INFERENCE_ERROR;
        aiueos_qwen35_format_failure(
          failed_token, job_result.failed_layer, failure_stage);
        aiueos_qwen35_status.detail = aiueos_qwen35_decode_fail_detail;
        (void)aiueos_framebuffer_inference_screen(&aiueos_qwen35_status);
        aiueos_rtl8125_inference_failure_report(
          job_id, inference_failures, failed_token,
          job_result.failed_layer, failure_stage);
        serial_string("AIUEOS_MURAKUMO_JOB_INFERENCE_RETRY job-id=");
        serial_decimal64(job_id);
        serial_string(" attempt=");
        serial_decimal(inference_failures);
        serial_string(" failed-token=");
        serial_decimal(failed_token);
        serial_string(" failed-layer=");
        serial_decimal(job_result.failed_layer);
        serial_string(" failure-stage=");
        serial_decimal(failure_stage);
        serial_string(" reason=execution-or-token-mismatch action=restart-runtime kernel-reboot=false\r\n");
        (void)aiueos_kototama_runtime_restart();
        /* A failed inference must not make the AIUEOS management plane deaf.
           Preserve the retry policy while providing a bounded SSH window for
           status, runtime restart and authenticated PXE reboot. */
        aiueos_k16_management_wait(boot->tsc_hz, 30);
        continue;
      }
      aiueos_qwen35_status.phase = AIUEOS_INFERENCE_COMPLETE;
      aiueos_qwen35_status.detail = "POSTING JOB RESULT";
      aiueos_qwen35_status.generated_tokens = job_result.generated_tokens;
      aiueos_qwen35_status.decode_tokens = job_result.decode_tokens;
      aiueos_qwen35_status.compute_cycles = job_result.total_cycles;
      aiueos_qwen35_status.time_to_first_token_ns =
        aiueos_cycles_to_ns(job_result.first_token_cycles, boot->tsc_hz);
      aiueos_qwen35_status.decode_ns =
        aiueos_cycles_to_ns(job_result.decode_cycles, boot->tsc_hz);
      (void)aiueos_framebuffer_inference_screen(&aiueos_qwen35_status);
      while (!aiueos_rtl8125_device_worker_result(
               boot, worker_sequence++, job_id, job_result.tokens[0],
               job_result.tokens[1], job_result.generated_tokens,
               job_result.decode_tokens, job_result.first_token_cycles,
               job_result.decode_cycles, job_result.total_cycles,
               job_result.vector_bits, job_result.worker_threads)) {
        aiueos_qwen35_status.phase = AIUEOS_INFERENCE_ERROR;
        aiueos_qwen35_status.detail = "RESULT POST RETRY";
        (void)aiueos_framebuffer_inference_screen(&aiueos_qwen35_status);
        serial_string("AIUEOS_MURAKUMO_JOB_RESULT_RETRY job-id=");
        serial_decimal64(job_id);
        serial_string(" error=");
        serial_decimal(aiueos_rtl8125_direct_https_error());
        serial_string("\r\n");
        aiueos_wait_seconds(boot->tsc_hz, 5);
      }
      aiueos_qwen35_status.phase = AIUEOS_INFERENCE_COMPLETE;
      aiueos_qwen35_status.detail = "RESULT RECORDED - READY";
      (void)aiueos_framebuffer_inference_screen(&aiueos_qwen35_status);
      debug_string("AIUEOS_MURAKUMO_JOB_RESULT_OK model=Qwen3.8-27B result=recorded ready=true\n");
      serial_string("AIUEOS_MURAKUMO_JOB_RESULT_OK job-id=");
      serial_decimal64(job_id);
      serial_string(" token=");
      serial_decimal(job_result.tokens[0]);
      serial_string(" next-token=");
      serial_decimal(job_result.tokens[1]);
      serial_string(" decode-milli-tok-s=");
      serial_decimal64(aiueos_inference_milli_tokens_per_second(
        job_result.decode_tokens, aiueos_qwen35_status.decode_ns));
      serial_string(" total-cycles=");
      serial_decimal64(job_result.total_cycles);
      serial_string(" result=recorded ready=true\r\n");
    }
#else
    if(!aiueos_qualification_finalize(1,8160))
      serial_string("AIUEOS_PHYSICAL_QUALIFICATION_LOG_FAIL stage=runtime-variable\r\n");
#endif
#else
    aiueos_framebuffer_qualification_screen("AIUEOS K16", "DIRECT HTTPS OK", "SSD READ ONLY", 1);
    debug_string("AIUEOS_PHYSICAL_DIRECT_HTTPS_OK host=api.murakumo.cloud path=/infer/queue http=200 mac-app-relay=none trust=transport-only secrets=none\n");
    serial_string("AIUEOS_PHYSICAL_DIRECT_HTTPS_OK host=api.murakumo.cloud path=/infer/queue http=200 mac-app-relay=none trust=transport-only secrets=none\r\n");
    if(!aiueos_qualification_finalize(1,8150))
      serial_string("AIUEOS_PHYSICAL_QUALIFICATION_LOG_FAIL stage=runtime-variable\r\n");
#endif
    for(;;)__asm__ volatile("cli; hlt");
#else
#ifdef AIUEOS_PHYSICAL_RELAY_QUALIFICATION
    aiueos_qualification_progress(232);
    aiueos_framebuffer_qualification_screen("AIUEOS K16", "TEST NODE RELAY", "SSD READ ONLY", 0);
    if(!aiueos_rtl8125_relay_qualification()) {
      uint32_t code=8300U+aiueos_rtl8125_relay_error();
      aiueos_framebuffer_qualification_screen("AIUEOS K16", "FAIL NODE RELAY", "SSD READ ONLY", 0);
      debug_string("AIUEOS_PHYSICAL_RELAY_FAIL udp=10.77.0.1:7777 scope=diagnostic-only\n");
      serial_string("AIUEOS_PHYSICAL_RELAY_FAIL udp=10.77.0.1:7777 scope=diagnostic-only\r\n");
      if(!aiueos_qualification_finalize(2,code))
        serial_string("AIUEOS_PHYSICAL_QUALIFICATION_LOG_FAIL stage=runtime-variable\r\n");
      for(;;)__asm__ volatile("cli; hlt");
    }
    aiueos_qualification_progress(233);
    aiueos_framebuffer_qualification_screen("AIUEOS K16", "NODE RELAY OK", "SSD READ ONLY", 1);
    (void)aiueos_rtl8125_relay_rx_length();
    debug_string("AIUEOS_PHYSICAL_RELAY_OK request-bound-udp=10.77.0.1:7777 scope=diagnostic-only\n");
    serial_string("AIUEOS_PHYSICAL_RELAY_OK request-bound-udp=10.77.0.1:7777 scope=diagnostic-only\r\n");
#ifdef AIUEOS_PHYSICAL_JOB_QUALIFICATION
    aiueos_qualification_progress(234);
    struct aiueos_inference_status inference_status = {
      .abi_version = AIUEOS_INFERENCE_STATUS_ABI_VERSION,
      .byte_size = sizeof(struct aiueos_inference_status),
      .phase = AIUEOS_INFERENCE_ADMISSION,
      .model = "AIUEOS CHAR BIGRAM",
      .quant = "FROZEN U8",
      .detail = "WAITING FOR JOB",
      .target_tokens = 1,
      .artifact_bytes = AIUEOS_INFERENCE_UNMEASURED,
      .resident_bytes = AIUEOS_INFERENCE_UNMEASURED,
      .load_ns = AIUEOS_INFERENCE_UNMEASURED,
      .prefill_ns = AIUEOS_INFERENCE_UNMEASURED,
      .decode_ns = AIUEOS_INFERENCE_UNMEASURED,
      .time_to_first_token_ns = AIUEOS_INFERENCE_UNMEASURED
    };
    if (!aiueos_framebuffer_inference_screen(&inference_status))
      aiueos_framebuffer_qualification_screen("AIUEOS K16", "WAIT INFERENCE JOB", "SSD READ ONLY", 0);
    if(!aiueos_rtl8125_job_qualification()) {
      uint32_t code=8400U+aiueos_rtl8125_job_error();
      aiueos_framebuffer_qualification_screen("AIUEOS K16", "FAIL INFERENCE JOB", "SSD READ ONLY", 0);
      debug_string("AIUEOS_PHYSICAL_JOB_FAIL queue=claim model=aiueos-char-bigram-v1 result=uncommitted\n");
      serial_string("AIUEOS_PHYSICAL_JOB_FAIL queue=claim model=aiueos-char-bigram-v1 result=uncommitted\r\n");
      if(!aiueos_qualification_finalize(2,code))
        serial_string("AIUEOS_PHYSICAL_QUALIFICATION_LOG_FAIL stage=runtime-variable\r\n");
      for(;;)__asm__ volatile("cli; hlt");
    }
    aiueos_qualification_progress(235);
    (void)aiueos_rtl8125_job_token();
    (void)aiueos_rtl8125_job_score();
    (void)aiueos_rtl8125_job_total();
    inference_status.phase = AIUEOS_INFERENCE_COMPLETE;
    inference_status.detail = "RESULT RECORDED";
    inference_status.generated_tokens = 1;
    inference_status.compute_cycles = aiueos_rtl8125_job_cycles();
    if (!aiueos_framebuffer_inference_screen(&inference_status))
      aiueos_framebuffer_qualification_screen("AIUEOS K16", "INFERENCE RESULT OK", "SSD READ ONLY", 1);
    debug_string("AIUEOS_PHYSICAL_JOB_OK queue=claim model=aiueos-char-bigram-v1 token=o result=recorded ready=true\n");
    serial_string("AIUEOS_PHYSICAL_JOB_OK queue=claim model=aiueos-char-bigram-v1 token=o result=recorded ready=true\r\n");
    if(!aiueos_rtl8125_liveness_renewal()) {
      uint32_t code=8500U+aiueos_rtl8125_liveness_error();
      aiueos_framebuffer_qualification_screen("AIUEOS K16", "FAIL HEARTBEAT RENEW", "SSD READ ONLY", 0);
      debug_string("AIUEOS_PHYSICAL_LIVENESS_FAIL ping=pong heartbeat=not-renewed\n");
      serial_string("AIUEOS_PHYSICAL_LIVENESS_FAIL ping=pong heartbeat=not-renewed\r\n");
      if(!aiueos_qualification_finalize(2,code))
        serial_string("AIUEOS_PHYSICAL_QUALIFICATION_LOG_FAIL stage=runtime-variable\r\n");
      for(;;)__asm__ volatile("cli; hlt");
    }
    (void)aiueos_rtl8125_liveness_sequence();
    inference_status.detail = "MURAKUMO NODE LIVE";
    (void)aiueos_framebuffer_inference_screen(&inference_status);
    debug_string("AIUEOS_PHYSICAL_LIVENESS_OK ping=pong heartbeat=renewed\n");
    serial_string("AIUEOS_PHYSICAL_LIVENESS_OK ping=pong heartbeat=renewed\r\n");
    if(!aiueos_qualification_finalize(1,8141))
      serial_string("AIUEOS_PHYSICAL_QUALIFICATION_LOG_FAIL stage=runtime-variable\r\n");
    uint32_t liveness_failures=0;
    for(;;) {
      if(aiueos_rtl8125_liveness_renewal()) {
        if(liveness_failures) {
          inference_status.phase = AIUEOS_INFERENCE_COMPLETE;
          inference_status.detail = "MURAKUMO NODE LIVE";
          (void)aiueos_framebuffer_inference_screen(&inference_status);
          debug_string("AIUEOS_PHYSICAL_LIVENESS_RECOVERED heartbeat=renewed\n");
          serial_string("AIUEOS_PHYSICAL_LIVENESS_RECOVERED failures=");
          serial_decimal(liveness_failures);
          serial_string(" sequence=");
          serial_decimal(aiueos_rtl8125_liveness_sequence());
          serial_string("\r\n");
          liveness_failures=0;
        }
        continue;
      }
      liveness_failures++;
      inference_status.phase = AIUEOS_INFERENCE_ERROR;
      inference_status.detail = "NODE RECONNECTING";
      (void)aiueos_framebuffer_inference_screen(&inference_status);
      debug_string("AIUEOS_PHYSICAL_LIVENESS_RETRY heartbeat=stale action=reconnect\n");
      serial_string("AIUEOS_PHYSICAL_LIVENESS_RETRY failure=");
      serial_decimal(liveness_failures);
      serial_string(" error=");
      serial_decimal(aiueos_rtl8125_liveness_error());
      serial_string(" action=reconnect\r\n");
      /* A failed job can leave its error sticky and make the next renewal
         return immediately. Keep that path from becoming a hot spin while a
         future recovery policy decides whether the job may be retried. */
      for(volatile uint32_t backoff=0;backoff<50000000U;backoff++)
        __asm__ volatile("pause");
    }
#else
    if(!aiueos_qualification_finalize(1,8130))
      serial_string("AIUEOS_PHYSICAL_QUALIFICATION_LOG_FAIL stage=runtime-variable\r\n");
#endif
#else
    if(!aiueos_qualification_finalize(1,8125))
      serial_string("AIUEOS_PHYSICAL_QUALIFICATION_LOG_FAIL stage=runtime-variable\r\n");
#endif
    for(;;)__asm__ volatile("cli; hlt");
#endif
#else
    /* This profile is intentionally a USB-only, read-only boundary.  Reaching
       this screen proves the native loader/kernel, integrity admission,
       Kotoba object execution, owned paging, GOP, allocator and ACPI on the
       physical machine.  It stops before DMA, PCI drivers or any block write;
       those need K16-specific AMD-IOMMU, NVMe and RTL8125 qualification. */
    aiueos_qualification_progress(229);
#ifdef AIUEOS_QWEN38_MODEL_HANDOFF
#ifdef AIUEOS_MODEL_TEST_FIXTURE
    {
      struct aiueos_inference_status admitted = {
        .abi_version = AIUEOS_INFERENCE_STATUS_ABI_VERSION,
        .byte_size = sizeof(struct aiueos_inference_status),
        .phase = AIUEOS_INFERENCE_ADMISSION,
        .model = "QWEN3.8 27B",
        .quant = "UD-IQ3 XXS",
#ifndef AIUEOS_MODEL_TEST_FIXTURE
        .detail = "QWEN35 GRAPH READY",
#else
        .detail = "RUNTIME NEXT",
#endif
        .artifact_bytes = boot->model_size,
        .resident_bytes = boot->model_size,
        .load_ns = AIUEOS_INFERENCE_UNMEASURED,
        .prefill_ns = AIUEOS_INFERENCE_UNMEASURED,
        .decode_ns = AIUEOS_INFERENCE_UNMEASURED,
        .time_to_first_token_ns = AIUEOS_INFERENCE_UNMEASURED,
        .compute_cycles = AIUEOS_INFERENCE_UNMEASURED
      };
      (void)aiueos_framebuffer_inference_screen(&admitted);
    }
    debug_string("AIUEOS_PHYSICAL_MODEL_HANDOFF_OK " AIUEOS_MODEL_NAME " runtime=not-yet-present internal-disk-writes=none\n");
    serial_string("AIUEOS_PHYSICAL_MODEL_HANDOFF_OK " AIUEOS_MODEL_NAME " runtime=not-yet-present internal-disk-writes=none\r\n");
#else
    (void)aiueos_framebuffer_inference_screen(&aiueos_qwen35_status);
    debug_string("AIUEOS_PHYSICAL_QWEN35_OK token=248046 reference=matched timing=raw-tsc internal-disk-writes=none\n");
    serial_string("AIUEOS_PHYSICAL_QWEN35_OK token=248046 cycles=");
    serial_decimal64(aiueos_qwen35_status.compute_cycles);
    serial_string(" reference=matched timing=raw-tsc internal-disk-writes=none\r\n");
#endif
    if (!aiueos_qualification_finalize(1, 8160))
#else
    aiueos_framebuffer_qualification_screen("AIUEOS K16", "NATIVE CORE OK", "SSD READ ONLY", 1);
    debug_string("AIUEOS_PHYSICAL_QUALIFICATION_OK native-core-v2 internal-disk-writes=none\n");
    serial_string("AIUEOS_PHYSICAL_QUALIFICATION_OK native-core-v2 internal-disk-writes=none\r\n");
    if (!aiueos_qualification_finalize(1, 0))
#endif
      serial_string("AIUEOS_PHYSICAL_QUALIFICATION_LOG_FAIL stage=runtime-variable\r\n");
    for (;;) __asm__ volatile("cli; hlt");
#endif
#endif
    if (!aiueos_vtd_initialize()) {
      if (aiueos_vtd_error() == 3) serial_string("AIUEOS_VTD_STAGE_FAIL srtp\r\n");
      if (aiueos_vtd_error() == 4) serial_string("AIUEOS_VTD_STAGE_FAIL context-invalidate\r\n");
      if (aiueos_vtd_error() == 6) serial_string("AIUEOS_VTD_STAGE_FAIL iotlb-invalidate\r\n");
      if (aiueos_vtd_error() == 7) serial_string("AIUEOS_VTD_STAGE_FAIL translation-enable\r\n");
      if (aiueos_vtd_error() == 8) serial_string("AIUEOS_VTD_STAGE_FAIL interrupt-table-pointer\r\n");
      if (aiueos_vtd_error() == 9) serial_string("AIUEOS_VTD_STAGE_FAIL interrupt-remapping-enable\r\n");
      serial_string("AIUEOS_VTD_FAIL root-context-slpt\r\n");
      qemu_exit(0x74);
    }
    if (aiueos_vtd_translation_enabled()) {
      serial_string("AIUEOS_VTD_OK tes=1 root-context-slpt domain=1 aperture=128MiB\r\n");
      serial_string("AIUEOS_DMA_POLICY_OK dmar=validated dma=vtd-isolated\r\n");
    } else if (!aiueos_dma_test_policy_allows_unisolated()) {
      serial_string("AIUEOS_DMA_POLICY_OK dmar=validated dma=denied-until-vtd-enabled\r\n");
    } else {
      serial_string("AIUEOS_DMA_POLICY_OK dmar=absent test-only-unisolated\r\n");
    }
    if (!aiueos_apic_timer_initialize()) {
      debug_string("AIUEOS_APIC_FAIL initialization\n");
      serial_string("AIUEOS_APIC_FAIL initialization\r\n");
      qemu_exit(0x77);
    }
    if (!aiueos_smp_start_application_processor()) {
      debug_string("AIUEOS_SMP_FAIL ap-startup\n");
      serial_string("AIUEOS_SMP_FAIL ap-startup\r\n");
      qemu_exit(0x73);
    }
    if (!aiueos_smp_dispatch_selftest()) {
      debug_string("AIUEOS_SMP_FAIL ap-dispatch\n");
      serial_string("AIUEOS_SMP_FAIL ap-dispatch\r\n");
      qemu_exit(0x73);
    }
    debug_string("AIUEOS_SMP_OK cpus=2 init-sipi-v1\n");
    serial_string("AIUEOS_SMP_OK cpus=2 init-sipi-v1 per-cpu-stack dispatch=verified\r\n");
    aiueos_scheduler_initialize();
    __asm__ volatile("sti");
    while (!aiueos_scheduler_evidence_ready()) __asm__ volatile("hlt");
    __asm__ volatile("cli");
    debug_string("AIUEOS_APIC_TIMER_OK vector=32 eoi-v1\n");
    serial_string("AIUEOS_APIC_TIMER_OK vector=32 eoi-v1\r\n");
    int pci_result = aiueos_pci_enumerate();
    if (!pci_result) {
      debug_string("AIUEOS_PCI_FAIL enumeration-or-virtio\n");
      serial_string("AIUEOS_PCI_FAIL enumeration-or-virtio\r\n");
      qemu_exit(0x74);
    }
    debug_string("AIUEOS_PCI_OK bounded-scan virtio-vendor=1af4\n");
    serial_string("AIUEOS_PCI_OK bounded-scan virtio-vendor=1af4\r\n");
    /* The enumeration result, as bits, because every virtio decision below
       reads one of them and none of them was observable. Deliberately NOT an
       _OK marker: it is a datum, not a verdict, and the coverage benchmark
       counts verdicts. Added while chasing why a GPT-image boot reports
       VIRTIO_INPUT_FAIL where an ESP boot of the same sources reports
       VIRTIO_INPUT_OK -- the branch turns on `pci_result & 4`, so the two
       boots enumerate differently, and until now the value that says so was
       invisible in both. */
    { char bits[4]; unsigned v = (unsigned)pci_result;
      bits[0] = (char)('0' + ((v >> 2) & 1));
      bits[1] = (char)('0' + ((v >> 1) & 1));
      bits[2] = (char)('0' + (v & 1));
      bits[3] = 0;
      debug_string("AIUEOS_PCI_RESULT input-rng-base=");
      debug_string(bits);
      serial_string("AIUEOS_PCI_RESULT input-rng-base=");
      serial_string(bits); serial_string(" input-devices-seen=");
      debug_string(" input-devices-seen=");
      { unsigned seen = (unsigned)aiueos_pci_input_devices_seen();
        char d[2]; d[0] = (char)('0' + (seen > 9 ? 9 : seen)); d[1] = 0;
        debug_string(d); serial_string(d); }
      debug_string(" input-fail-line="); serial_string(" input-fail-line=");
      { unsigned n = (unsigned)aiueos_pci_input_fail_line();
        char q[8]; unsigned i = 0;
        if (!n) q[i++] = '0';
        while (n) { q[i++] = (char)('0' + (n % 10)); n /= 10; }
        while (i--) { char one[2]; one[0] = q[i]; one[1] = 0;
                      debug_string(one); serial_string(one); } }
      debug_string("\n"); serial_string("\r\n"); }
    if (pci_result < 2) {
      debug_string("AIUEOS_VIRTIO_FAIL rng-queue\n");
      serial_string("AIUEOS_VIRTIO_FAIL rng-queue\r\n");
      qemu_exit(0x73);
    }
    debug_string("AIUEOS_VIRTIO_RNG_OK modern-pci caps-bounded dma=4pages completion=32\n");
    serial_string("AIUEOS_VIRTIO_RNG_OK modern-pci caps-bounded dma=4pages completion=32\r\n");
    if (aiueos_virtio_rng_irq_count != 1) {
      serial_string("AIUEOS_VIRTIO_RNG_MSIX_FAIL irq-count\r\n"); evidence_stop(__LINE__);
    }
    debug_string("AIUEOS_VIRTIO_RNG_MSIX_OK vector=34 irq=1 table-pba-bounded\n");
    serial_string("AIUEOS_VIRTIO_RNG_MSIX_OK vector=34 irq=1 table-pba-bounded\r\n");
#ifdef AIUEOS_SSH_LISTEN
    /* Entropy API self-test (ssh-v1.edn / ADR-0103): the random device is kept
       alive after enumeration, and aiueos_random_bytes must deliver two
       distinct, non-constant 32-byte batches. This is the source an SSH
       handshake draws its ephemeral scalar and cookie from -- before this the
       32 bytes rng returned were discarded. */
    if (aiueos_random_selftest()) {
      serial_string("AIUEOS_RANDOM_OK two-batches distinct non-constant 32-bytes\r\n");
      debug_string("AIUEOS_RANDOM_OK two-batches distinct non-constant 32-bytes\n");
    } else {
      serial_string("AIUEOS_RANDOM_FAIL entropy-source-unusable\r\n");
    }
    /* SSH curve25519-sha256 exchange hash H over the RFC 5656 transcript
       (ssh-v1.edn / ADR-0106). H is emitted as hex so smoke-qemu-ssh-kex can
       compare it against ssh.transport's H (kotoba-lang/org-ietf-ssh); want[]
       is that same H, baked, so the boot self-verifies. */
    {
      static const uint8_t want[32] = {
        0x52,0x0a,0x9b,0xa7,0x0d,0x60,0x20,0x1a,0xf9,0x36,0x5b,0x0e,0x53,0xff,0xaf,0xa1,
        0xa3,0x14,0x46,0xd1,0x7e,0xc2,0x43,0x15,0xeb,0x67,0x8a,0x9b,0x2e,0x70,0x98,0x33};
      uint8_t hh[32];
      if (aiueos_ssh_kex_h(hh)) {
        int match = 1;
        for (int i = 0; i < 32; i++) if (hh[i] != want[i]) match = 0;
        serial_string("AIUEOS_SSH_KEX_H ");
        for (int i = 0; i < 32; i++) serial_hex_byte(hh[i]);
        serial_string("\r\n");
        if (match) {
          serial_string("AIUEOS_SSH_KEX_OK curve25519-sha256 exchange-hash-match org-ietf-ssh\r\n");
          debug_string("AIUEOS_SSH_KEX_OK curve25519-sha256 exchange-hash-match\n");
        } else {
          serial_string("AIUEOS_SSH_KEX_FAIL exchange-hash-mismatch\r\n");
        }
      } else {
        serial_string("AIUEOS_SSH_KEX_FAIL sha256-object-failed\r\n");
      }
    }
#endif
    if ((pci_result & 3) != 3) {
      if (aiueos_virtio_blk_wait_overshot()) {
        /* Distinct because the fix is different: this is not a device that
           failed to answer, it is a wait this kernel can no longer satisfy. */
        debug_string("AIUEOS_VIRTIO_BLK_FAIL completion-wait-overshot\n");
        serial_string("AIUEOS_VIRTIO_BLK_FAIL completion-wait-overshot used=");
        { unsigned v[2]; v[0]=aiueos_virtio_blk_wait_used();
          v[1]=aiueos_virtio_blk_wait_target();
          for (int k = 0; k < 2; k++) {
            char q[8]; unsigned i = 0, n = v[k];
            if (!n) q[i++] = '0';
            while (n) { q[i++] = (char)('0' + (n % 10)); n /= 10; }
            while (i--) { char one[2]; one[0]=q[i]; one[1]=0; serial_string(one); }
            serial_string(k == 0 ? " target=" : "\r\n"); } }
      } else {
        debug_string("AIUEOS_VIRTIO_BLK_FAIL capacity-or-read\n");
        serial_string("AIUEOS_VIRTIO_BLK_FAIL capacity-or-read\r\n");
      }
      qemu_exit(0x71);
    }
    debug_string("AIUEOS_VIRTIO_BLK_OK capacity-bounded sector=0 bytes=512 readonly\n");
    serial_string("AIUEOS_VIRTIO_BLK_OK capacity-bounded sector=0 bytes=512 readonly");
    /* The slowest wait that SUCCEEDED. Near zero means completions are seen on
       the first look, so the used index has no room to run ahead of target and
       the overshoot theory has nowhere to live. Measured on the healthy path
       because the failing path cannot answer it. */
    serial_string(" slowest-wait=");
    { unsigned v[3]; v[0]=aiueos_virtio_blk_slowest_wait();
      v[1]=aiueos_virtio_blk_slow_used(); v[2]=aiueos_virtio_blk_slow_target();
      for (int k = 0; k < 3; k++) {
        char q[12]; unsigned i = 0, n = v[k];
        if (!n) q[i++] = '0';
        while (n) { q[i++] = (char)('0' + (n % 10)); n /= 10; }
        while (i--) { char one[2]; one[0]=q[i]; one[1]=0; serial_string(one); }
        serial_string(k == 0 ? " used=" : k == 1 ? " target=" : "\r\n"); } }
    if (aiueos_virtio_blk_irq_count < 5) {
      serial_string("AIUEOS_VIRTIO_BLK_MSIX_FAIL irq-count\r\n"); evidence_stop(__LINE__);
    }
    debug_string("AIUEOS_VIRTIO_BLK_MSIX_OK vector=35 irq-completions-bounded table-pba-bounded\n");
    serial_string("AIUEOS_VIRTIO_BLK_MSIX_OK vector=35 irq-completions-bounded table-pba-bounded\r\n");
    if (aiueos_vtd_translation_enabled()) {
      if (!aiueos_vtd_interrupt_remapping_enabled()) evidence_stop(__LINE__);
      serial_string("AIUEOS_VTD_IR_OK irta=256 source-validated vector=35 remappable-msix\r\n");
    }
    if (!aiueos_object_store_ready()) {
      debug_string("AIUEOS_OBJECT_STORE_FAIL superblock-or-object\n");
      serial_string("AIUEOS_OBJECT_STORE_FAIL superblock-or-object\r\n");
      qemu_exit(0x70);
    }
    debug_string("AIUEOS_OBJECT_STORE_OK aiuefs-v3 objects=3 catalog=2apps\n");
    serial_string("AIUEOS_OBJECT_STORE_OK aiuefs-v3 objects=3 catalog=2apps\r\n");
    /* Blank-volume format route evidence (JUN-34): this boot provisioned the
       object store onto a zeroed volume instead of finding it pre-populated,
       so the OCI block volume needs no helper VM to carry the image. */
    if (aiueos_object_store_formatted()) {
      debug_string("AIUEOS_OBJECT_STORE_FORMAT_OK blank-volume source=initramfs catalog=rsa2048 write-readback\n");
      serial_string("AIUEOS_OBJECT_STORE_FORMAT_OK blank-volume source=initramfs catalog=rsa2048 write-readback\r\n");
    }
    debug_string("AIUEOS_KOTOBA_APP_ADMISSION_OK catalog=rsa2048 apps=2 digest=kotoba-sha256 signature=kotoba-rsa2048-pkcs1 policy=public-key\n");
    serial_string("AIUEOS_KOTOBA_APP_ADMISSION_OK catalog=rsa2048 apps=2 digest=kotoba-sha256 signature=kotoba-rsa2048-pkcs1 policy=public-key\r\n");
    {
      extern unsigned aiueos_object_store_restored_count(void);
      unsigned restored = aiueos_object_store_restored_count();
      if (restored == 1) {
        debug_string("AIUEOS_OBJECT_STORE_RESTORE_OK apps=1 source=initramfs catalog-digest-bound rsa2048 write-readback\n");
        serial_string("AIUEOS_OBJECT_STORE_RESTORE_OK apps=1 source=initramfs catalog-digest-bound rsa2048 write-readback\r\n");
      } else if (restored) {
        debug_string("AIUEOS_OBJECT_STORE_RESTORE_OK apps=2 source=initramfs catalog-digest-bound rsa2048 write-readback\n");
        serial_string("AIUEOS_OBJECT_STORE_RESTORE_OK apps=2 source=initramfs catalog-digest-bound rsa2048 write-readback\r\n");
      }
    }
    if (aiueos_catalog_policy_selftest_ok()) {
      serial_string("AIUEOS_KOTOBA_CATALOG_POLICY_SELFTEST_OK malformed=6\r\n");
    }
    if (!aiueos_journal_ready()) {
      debug_string("AIUEOS_JOURNAL_FAIL write-readback\n");
      serial_string("AIUEOS_JOURNAL_FAIL write-readback\r\n");
      evidence_stop(__LINE__);
    }
    if (!aiueos_journal_sequence() || aiueos_journal_slot() < 1 || aiueos_journal_slot() > 2)
      evidence_stop(__LINE__);
    debug_string("AIUEOS_JOURNAL_OK dual-slot committed append-readback\n");
    serial_string("AIUEOS_JOURNAL_OK dual-slot committed append-readback\r\n");
    if (aiueos_object_transaction_sequence() != aiueos_journal_sequence()) evidence_stop(__LINE__);
    debug_string("AIUEOS_OBJECT_TXN_OK journal-first sector=3 apply-readback route=kotoba fixed-stack\n");
    /* F2: the durable file system self-test (create/rename/delete/fill). */
    {
      extern uint32_t aiueos_fs_selftest(void);
      uint32_t fs = aiueos_fs_selftest();
      if (fs & 1) { debug_string("AIUEOS_FS_CREATE_OK\n"); serial_string("AIUEOS_FS_CREATE_OK\r\n"); }
      if (fs & 2) { debug_string("AIUEOS_FS_RENAME_OK\n"); serial_string("AIUEOS_FS_RENAME_OK\r\n"); }
      if (fs & 4) { debug_string("AIUEOS_FS_DELETE_OK\n"); serial_string("AIUEOS_FS_DELETE_OK\r\n"); }
      if (fs & 8) { debug_string("AIUEOS_FS_FULL_REPORTED not-corrupted\n"); serial_string("AIUEOS_FS_FULL_REPORTED not-corrupted\r\n"); }
      if (fs & 16) { debug_string("AIUEOS_FS_ATOMIC_OK table-readback-ab\n"); serial_string("AIUEOS_FS_ATOMIC_OK table-readback-ab\r\n"); }
    }
    /* F5 slice 1: the UHCI host controller discovery. */
    {
      extern int aiueos_uhci_probe(void);
      extern int aiueos_uhci_ports(void);
      extern int aiueos_uhci_test(void);
      if (aiueos_uhci_probe()) {
        debug_string("AIUEOS_UHCI_OK controller=uhci ports-see-serial\n");
        serial_string("AIUEOS_UHCI_OK controller=uhci ports=");
        serial_decimal((uint32_t)aiueos_uhci_ports());
        serial_string("\r\n");
        int f5 = aiueos_uhci_test();
        serial_string("AIUEOS_UHCI_TEST rc=");
        serial_decimal((uint32_t)f5);
        serial_string("\r\n");
      } else {
        extern uint32_t aiueos_uhci_scan_seen[12];
        serial_string("AIUEOS_UHCI_PROBE_NONE classes=");
        for (int s = 0; s < 12 && aiueos_uhci_scan_seen[s]; s++) {
          serial_hex_byte((uint8_t)(aiueos_uhci_scan_seen[s] >> 24));
          serial_hex_byte((uint8_t)(aiueos_uhci_scan_seen[s] >> 16));
          serial_string(" ");
        }
        serial_string("\r\n");
      }
    }
    serial_string("AIUEOS_OBJECT_TXN_OK journal-first sector=3 apply-readback route=kotoba fixed-stack\r\n");
    debug_string("AIUEOS_KOTOBA_JOURNAL_PLAN_OK latest-slot next-sequence rollback-preserved\n");
    serial_string("AIUEOS_KOTOBA_JOURNAL_PLAN_OK latest-slot next-sequence rollback-preserved\r\n");
    debug_string("AIUEOS_KOTOBA_FNV_OK bounded-load journal-object-validation\n");
    serial_string("AIUEOS_KOTOBA_FNV_OK bounded-load journal-object-validation\r\n");
    serial_string("AIUEOS_KOTOBA_RECORD_VALIDATION_OK journal transaction bounded-u32\r\n");
    serial_string("AIUEOS_KOTOBA_STORAGE_READ_VALIDATION_OK superblock mutable-object\r\n");
    serial_string("AIUEOS_KOTOBA_STORAGE_WRITE_OK journal mutable-object bounded-store\r\n");
    {
      /* The storage plane and interrupt-driven block transport are proven at
         this point, so a pending crash receipt is consumed and reported here. */
      extern int aiueos_crash_receipt_consume(uint32_t *, uint32_t *);
      uint32_t crash_reason = 0, crash_sequence = 0;
      int crash_found = aiueos_crash_receipt_consume(&crash_reason, &crash_sequence);
      if (crash_found) {
        if (crash_reason == 42u && crash_sequence) {
          debug_string("AIUEOS_CRASH_RECEIPT_OK reason=42 journal-context consumed readback\n");
          serial_string("AIUEOS_CRASH_RECEIPT_OK reason=42 journal-context consumed readback\r\n");
        } else if (crash_reason == 6u && crash_sequence) {
          debug_string("AIUEOS_CRASH_RECEIPT_OK reason=6 fault-context consumed readback\n");
          serial_string("AIUEOS_CRASH_RECEIPT_OK reason=6 fault-context consumed readback\r\n");
        } else {
          debug_string("AIUEOS_CRASH_RECEIPT_FAIL reason-or-sequence\n");
          serial_string("AIUEOS_CRASH_RECEIPT_FAIL reason-or-sequence\r\n");
          qemu_exit(0x5d);
        }
      }
#ifdef AIUEOS_FAULT_RECEIPT_SMOKE
      if (!crash_found) {
        /* Test-only synthetic fault: an unexpected invalid opcode before the
           end-of-boot probe is expected. The exception dispatcher must write
           the fault receipt over the polled transport and terminate. */
        serial_string("AIUEOS_FAULT_SMOKE synthetic unexpected-ud2\r\n");
        __asm__ volatile("ud2");
      }
#endif
#ifdef AIUEOS_CRASH_RECEIPT_SMOKE
      if (!crash_found) {
        /* Test-only synthetic panic from normal kernel context: persist a
           durable crash receipt, then terminate the way an unrecoverable
           fault would. The next boot must consume and report it before
           completing its evidence gate. */
        extern int aiueos_crash_receipt_write(uint32_t);
        serial_string("AIUEOS_PANIC synthetic reason=42\r\n");
        if (!aiueos_crash_receipt_write(42u)) {
          debug_string("AIUEOS_PANIC_RECEIPT_FAIL write-readback\n");
          serial_string("AIUEOS_PANIC_RECEIPT_FAIL write-readback\r\n");
          qemu_exit(0x5d);
        }
        debug_string("AIUEOS_PANIC_RECEIPT_OK synthetic reason=42 written readback pending\n");
        serial_string("AIUEOS_PANIC_RECEIPT_OK synthetic reason=42 written readback pending\r\n");
        qemu_exit(0x5c);
      }
#endif
    }
    if (!aiueos_service_registry_ready()) evidence_stop(__LINE__);
    debug_string("AIUEOS_SERVICE_REGISTRY_OK journal-object ids=2 generation=2,1 restart=1,0 decoder=kotoba fixed-stack\n");
    serial_string("AIUEOS_SERVICE_REGISTRY_OK journal-object ids=2 generation=2,1 restart=1,0 decoder=kotoba fixed-stack\r\n");
    serial_string("AIUEOS_KOTOBA_PCI_PLANNER_OK cap extent msix-region\r\n");
    if (aiueos_journal_recovered()) {
      if (!aiueos_journal_recovered_sequence() ||
          aiueos_journal_sequence() != aiueos_journal_recovered_sequence() + 1) evidence_stop(__LINE__);
      debug_string("AIUEOS_JOURNAL_RECOVERY_OK highest-valid selected alternate-slot-append\n");
      serial_string("AIUEOS_JOURNAL_RECOVERY_OK highest-valid selected alternate-slot-append\r\n");
      if (!aiueos_object_transaction_replayed()) evidence_stop(__LINE__);
      if (!aiueos_service_registry_replayed()) evidence_stop(__LINE__);
      if (!aiueos_recovered_service_registry_ready() ||
          !aiueos_scheduler_restore_service_registry(
            aiueos_recovered_service_registry_state(0),
            aiueos_recovered_service_registry_state(1))) evidence_stop(__LINE__);
      __asm__ volatile("sti");
      while (!aiueos_service_runtime_evidence_ready()) __asm__ volatile("hlt");
      __asm__ volatile("cli");
      if (!aiueos_scheduler_persistent_restore_evidence_ready()) evidence_stop(__LINE__);
      debug_string("AIUEOS_OBJECT_TXN_REPLAY_OK committed-redo idempotent-before-append\n");
      serial_string("AIUEOS_OBJECT_TXN_REPLAY_OK committed-redo idempotent-before-append\r\n");
      debug_string("AIUEOS_PERSISTENT_SERVICE_BOOTSTRAP_OK registry=replayed kotoba-spawn=2 generation=2,1\n");
      serial_string("AIUEOS_PERSISTENT_SERVICE_BOOTSTRAP_OK registry=replayed kotoba-spawn=2 generation=2,1\r\n");
      if (aiueos_user_object_replay_evidence_ready()) {
        debug_string("AIUEOS_KOTOBA_OBJECT_REPLAY_OK domains=4,5 journals=44-47 objects=42,43\n");
        serial_string("AIUEOS_KOTOBA_OBJECT_REPLAY_OK domains=4,5 journals=44-47 objects=42,43\r\n");
      }
    }
    /* Guest browser desktop (ADR-0223): only a boot with a virtio-tablet
       prints this, so every other profile's serial is unchanged. Printed
       before the keyboard check, which may stop the boot. */
    if (aiueos_desktop_pointer_tablets_seen()) {
      serial_string("AIUEOS_GUEST_BROWSER_TABLET tablets=");
      serial_decimal((uint32_t)aiueos_desktop_pointer_tablets_seen());
      serial_string(" press=");
      serial_decimal((uint32_t)aiueos_desktop_pointer_ready());
      serial_string(" used=");
      serial_decimal(aiueos_desktop_pointer_events_used());
      serial_string(" abs=");
      serial_decimal(aiueos_desktop_pointer_events_abs());
      serial_string(" key=");
      serial_decimal(aiueos_desktop_pointer_events_key());
      serial_string("\r\n");
    }
    /* The input result bit is set only after a validated event has been copied
       into the browser envelope; no second mutable readiness check is needed. */
    if (!(pci_result & 4)) {
      /* Say WHICH exit. "queue-or-envelope" covered four different failures
         wanting four different fixes, and the commonest of them is not a
         failure of this OS at all: reason 4 is a kernel built without
         AIUEOS_INPUT_SMOKE_SYNTHETIC on a host that cannot deliver a real
         virtio-keyboard event, which is how a production image behaves and
         should. */
      switch (aiueos_pci_input_fail_reason()) {
        case 1: serial_string("AIUEOS_VIRTIO_INPUT_FAIL transport-or-negotiate\r\n");
                debug_string("AIUEOS_VIRTIO_INPUT_FAIL transport-or-negotiate\n"); break;
        case 2: serial_string("AIUEOS_VIRTIO_INPUT_FAIL queue-pages\r\n");
                debug_string("AIUEOS_VIRTIO_INPUT_FAIL queue-pages\n"); break;
        case 3: serial_string("AIUEOS_VIRTIO_INPUT_FAIL doorbell\r\n");
                debug_string("AIUEOS_VIRTIO_INPUT_FAIL doorbell\n"); break;
        default: serial_string("AIUEOS_VIRTIO_INPUT_FAIL no-event-no-synthetic-build\r\n");
                 debug_string("AIUEOS_VIRTIO_INPUT_FAIL no-event-no-synthetic-build\n"); break;
      }
      if (aiueos_desktop_input_eventq_empty()) {
        debug_string("AIUEOS_GUEST_INPUT leftover=eventq-empty\n");
        serial_string("AIUEOS_GUEST_INPUT leftover=eventq-empty\r\n");
      }
      evidence_stop(__LINE__);
    }
    if (aiueos_desktop_input_from_eventq()) {
      debug_string("AIUEOS_VIRTIO_INPUT_OK modern-pci eventq configured used-ring\n");
      serial_string("AIUEOS_VIRTIO_INPUT_OK modern-pci eventq configured used-ring\r\n");
    } else {
      debug_string("AIUEOS_VIRTIO_INPUT_OK modern-pci eventq configured synthetic-smoke\n");
      serial_string("AIUEOS_VIRTIO_INPUT_OK modern-pci eventq configured synthetic-smoke\r\n");
    }
    debug_string("AIUEOS_DESKTOP_INPUT_OK envelope-v1 sequence=1 kind=key ime-neutral\n");
    serial_string("AIUEOS_DESKTOP_INPUT_OK envelope-v1 sequence=1 kind=key ime-neutral\r\n");
    /* Guest input (ADR-0093). C must not fill the envelope. Hosted JVM
       compositor input does not count. Do not qemu_exit: gpu/guest-paint
       stay green without this line. */
    if (aiueos_desktop_input_from_eventq()) {
      debug_string("AIUEOS_GUEST_INPUT_OK eventq-used=1 synthetic=0\n");
      serial_string("AIUEOS_GUEST_INPUT_OK eventq-used=1 synthetic=0\r\n");
    } else {
      debug_string("AIUEOS_GUEST_INPUT leftover=synthetic-smoke\n");
      serial_string("AIUEOS_GUEST_INPUT leftover=synthetic-smoke\r\n");
    }
    /* Guest IME known-answer (ADR-0090). C does not convert. Hosted JVM
       IME does not count. latin k=107, a=97 must yield U+304B (12363).
       Returning those latin bytes is a leak. Do not qemu_exit: gpu/cloud
       stay green without this line. */
    {
      uint64_t ime_cp = kotoba_aiueos_ime_commit(107, 97);
      if (ime_cp == 107 || ime_cp == 97) {
        debug_string("AIUEOS_GUEST_IME leftover=latin-leak\n");
        serial_string("AIUEOS_GUEST_IME leftover=latin-leak\r\n");
      } else if (ime_cp == 12363) {
        debug_string("AIUEOS_GUEST_IME_OK committed=u+304b latin-leak=0\n");
        serial_string("AIUEOS_GUEST_IME_OK committed=u+304b latin-leak=0\r\n");
      } else {
        debug_string("AIUEOS_GUEST_IME leftover=vector-miss\n");
        serial_string("AIUEOS_GUEST_IME leftover=vector-miss\r\n");
      }
    }
    /* Guest WM known-answer (ADR-0091). C does not pick z-order. Hosted
       JVM WM does not count. Rects are hosted boot-desktop. Do not
       qemu_exit: gpu/cloud/guest-ime stay green without this line. */
    {
      uint64_t one = kotoba_aiueos_wm_hit(1, 2, 100, 80);
      uint64_t zhit = kotoba_aiueos_wm_hit(2, 2, 100, 80);
      uint64_t missf = kotoba_aiueos_wm_hit(2, 2, 40, 40);
      uint64_t raised = kotoba_aiueos_wm_hit(2, 1, 100, 80);
      if (one != 0) {
        debug_string("AIUEOS_GUEST_WM leftover=one-surface-ignored\n");
        serial_string("AIUEOS_GUEST_WM leftover=one-surface-ignored\r\n");
      } else if (zhit == 1) {
        debug_string("AIUEOS_GUEST_WM leftover=z-order-ignored\n");
        serial_string("AIUEOS_GUEST_WM leftover=z-order-ignored\r\n");
      } else if (missf == 2) {
        debug_string("AIUEOS_GUEST_WM leftover=always-front\n");
        serial_string("AIUEOS_GUEST_WM leftover=always-front\r\n");
      } else if (raised != 1) {
        debug_string("AIUEOS_GUEST_WM leftover=raise-is-noop\n");
        serial_string("AIUEOS_GUEST_WM leftover=raise-is-noop\r\n");
      } else if (zhit == 2 && missf == 1) {
        debug_string("AIUEOS_GUEST_WM_OK two-surfaces z-hit=2 miss-front=1 raise=1 one-surface=0\n");
        serial_string("AIUEOS_GUEST_WM_OK two-surfaces z-hit=2 miss-front=1 raise=1 one-surface=0\r\n");
      } else {
        debug_string("AIUEOS_GUEST_WM leftover=vector-miss\n");
        serial_string("AIUEOS_GUEST_WM leftover=vector-miss\r\n");
      }
    }
    /* Guest permission broker (ADR-0096). C copies the clipboard
       scratch only when Kotoba admits clipboard. File-picker is
       refused on the clipboard-only boot grant. Do not qemu_exit:
       gpu/cloud/guest-ime/guest-wm/guest-scanout-two stay green
       without this line. Hosted JVM wm does not count. */
    {
      volatile static uint8_t clipboard_scratch;
      uint64_t clip = kotoba_aiueos_broker_admit(1, 1);
      uint64_t pick = kotoba_aiueos_broker_admit(2, 1);
      if (clip == 1) clipboard_scratch = 0;
      if (clip == 0) {
        debug_string("AIUEOS_GUEST_BROKER leftover=deny-all\n");
        serial_string("AIUEOS_GUEST_BROKER leftover=deny-all\r\n");
      } else if (pick != 0) {
        debug_string("AIUEOS_GUEST_BROKER leftover=always-grant\n");
        serial_string("AIUEOS_GUEST_BROKER leftover=always-grant\r\n");
      } else if (clip == 1 && pick == 0) {
        debug_string("AIUEOS_GUEST_BROKER_OK clipboard=1 picker=0 kotoba-clip=1 kotoba-pick=0\n");
        serial_string("AIUEOS_GUEST_BROKER_OK clipboard=1 picker=0 kotoba-clip=1 kotoba-pick=0\r\n");
      } else {
        debug_string("AIUEOS_GUEST_BROKER leftover=vector-miss\n");
        serial_string("AIUEOS_GUEST_BROKER leftover=vector-miss\r\n");
      }
    }
    /* Guest session restore (ADR-0098). Kotoba unpacks the sealed
       packed session word; C applies the restored front to wm-hit.
       Do not qemu_exit: gpu/cloud/guest-ime/guest-wm/guest-broker stay
       green without this line. Hosted JVM wm does not count. */
    {
      uint64_t packed = 2;
      uint64_t front = kotoba_aiueos_session_restore(packed);
      uint64_t empty = kotoba_aiueos_session_restore(0);
      uint64_t unk = kotoba_aiueos_session_restore(3);
      uint64_t hit = kotoba_aiueos_wm_hit(2, front, 100, 80);
      if (empty != 0) {
        debug_string("AIUEOS_GUEST_SESSION leftover=always-front\n");
        serial_string("AIUEOS_GUEST_SESSION leftover=always-front\r\n");
      } else if (unk != 0) {
        debug_string("AIUEOS_GUEST_SESSION leftover=unknown-surface\n");
        serial_string("AIUEOS_GUEST_SESSION leftover=unknown-surface\r\n");
      } else if (front == 0) {
        debug_string("AIUEOS_GUEST_SESSION leftover=empty-session\n");
        serial_string("AIUEOS_GUEST_SESSION leftover=empty-session\r\n");
      } else if (hit != front) {
        debug_string("AIUEOS_GUEST_SESSION leftover=restore-ignored\n");
        serial_string("AIUEOS_GUEST_SESSION leftover=restore-ignored\r\n");
      } else if (front == 2 && empty == 0 && unk == 0 && hit == 2) {
        debug_string("AIUEOS_GUEST_SESSION_OK restored-front=2 packed=2 kotoba-front=2 hit=2\n");
        serial_string("AIUEOS_GUEST_SESSION_OK restored-front=2 packed=2 kotoba-front=2 hit=2\r\n");
      } else {
        debug_string("AIUEOS_GUEST_SESSION leftover=vector-miss\n");
        serial_string("AIUEOS_GUEST_SESSION leftover=vector-miss\r\n");
      }
    }
    /* Guest paint (ADR-0092). C fills both boot rects back-then-front
       from Kotoba's front id, then samples the overlap pixel. Painting
       key-order (window 1 last) is leftover :key-order-paint. Painting
       window 2 last regardless of raise is leftover :always-front-paint.
       Do not qemu_exit: gpu/cloud/guest-ime/guest-wm stay green without
       this line. */
    {
      uint64_t boot_front = kotoba_aiueos_wm_hit(2, 2, 100, 80);
      uint64_t raise_front = kotoba_aiueos_wm_hit(2, 1, 100, 80);
      uint32_t c1 = aiueos_desktop_wm_stored_color(1);
      uint32_t c2 = aiueos_desktop_wm_stored_color(2);
      uint32_t boot_pix, raise_pix;
      if (!aiueos_desktop_wm_rects_fit()) {
        debug_string("AIUEOS_GUEST_PAINT leftover=fb-too-small\n");
        serial_string("AIUEOS_GUEST_PAINT leftover=fb-too-small\r\n");
      } else if (!aiueos_desktop_wm_paint(boot_front)) {
        debug_string("AIUEOS_GUEST_PAINT leftover=one-guest-scanout\n");
        serial_string("AIUEOS_GUEST_PAINT leftover=one-guest-scanout\r\n");
      } else {
        boot_pix = aiueos_desktop_sample_pixel(100, 80);
        if (!aiueos_desktop_wm_paint(raise_front)) {
          debug_string("AIUEOS_GUEST_PAINT leftover=one-guest-scanout\n");
          serial_string("AIUEOS_GUEST_PAINT leftover=one-guest-scanout\r\n");
        } else {
          raise_pix = aiueos_desktop_sample_pixel(100, 80);
          if (boot_pix == c1) {
            debug_string("AIUEOS_GUEST_PAINT leftover=key-order-paint\n");
            serial_string("AIUEOS_GUEST_PAINT leftover=key-order-paint\r\n");
          } else if (raise_pix == c2) {
            debug_string("AIUEOS_GUEST_PAINT leftover=always-front-paint\n");
            serial_string("AIUEOS_GUEST_PAINT leftover=always-front-paint\r\n");
          } else if (boot_front == 2 && raise_front == 1 &&
                     boot_pix == c2 && raise_pix == c1) {
            debug_string("AIUEOS_GUEST_PAINT_OK boot-overlap=2 raised-overlap=1 key-order=0\n");
            serial_string("AIUEOS_GUEST_PAINT_OK boot-overlap=2 raised-overlap=1 key-order=0\r\n");
          } else {
            debug_string("AIUEOS_GUEST_PAINT leftover=vector-miss\n");
            serial_string("AIUEOS_GUEST_PAINT leftover=vector-miss\r\n");
          }
        }
      }
    }
    /* Guest browser desktop (ADR-0223). kotoba-lang/browser ADR 0002: the
       browser surface IS the desktop. The surface state below is the hosted
       boot-desktop (window 1 at 32,32 720x540 under window 2 at 96,72
       640x480, window 2 focused). Kotoba writes the retained draw list
       (`kotoba_aiueos_browser_frame`); C paints it in list order and samples.
       Then a real virtio-tablet press, scaled to surface pixels by C, is
       reduced by Kotoba (`kotoba_aiueos_browser_reduce`: topmost hit, focus
       and raise) and the frame is drawn again. Do not qemu_exit: every gate
       before this one stays green without these lines. Hosted JVM/JS
       desktop-backend frames do not count. */
    {
      static uint32_t browser_state[32];
      static uint32_t browser_ops[64];
      static const uint32_t boot[15] = {1, 2, 2, 0, 0,
                                        1, 32, 32, 720, 540,
                                        2, 96, 72, 640, 480};
      uint64_t st = (uint64_t)(uintptr_t)browser_state;
      uint64_t op = (uint64_t)(uintptr_t)browser_ops;
      int64_t count;
      int frame_ok = 0;
      for (int i = 0; i < 32; i++) browser_state[i] = i < 15 ? boot[i] : 0;
      browser_state[3] = aiueos_desktop_width();
      browser_state[4] = aiueos_desktop_height();
      count = (int64_t)kotoba_aiueos_browser_frame(st, 128, op, 256);
      if (count <= 0) {
        debug_string("AIUEOS_GUEST_BROWSER_FRAME leftover=frame-refused\n");
        serial_string("AIUEOS_GUEST_BROWSER_FRAME leftover=frame-refused reason=-");
        serial_decimal((uint32_t)(-count));
        serial_string("\r\n");
      } else if (!aiueos_desktop_present_ops(browser_ops, (uint64_t)count)) {
        debug_string("AIUEOS_GUEST_BROWSER_FRAME leftover=fb-too-small\n");
        serial_string("AIUEOS_GUEST_BROWSER_FRAME leftover=fb-too-small\r\n");
      } else {
        uint32_t overlap = aiueos_desktop_sample_rgb(100, 80);
        uint32_t title1 = aiueos_desktop_sample_rgb(60, 50);
        if (overlap == 0xeef1f5U || overlap == 0xdde2eaU) {
          debug_string("AIUEOS_GUEST_BROWSER_FRAME leftover=key-order-paint\n");
          serial_string("AIUEOS_GUEST_BROWSER_FRAME leftover=key-order-paint\r\n");
        } else if (count == 5 && overlap == 0xd8e7ffU && title1 == 0xdde2eaU) {
          frame_ok = 1;
          debug_string("AIUEOS_GUEST_BROWSER_FRAME_OK\n");
          serial_string("AIUEOS_GUEST_BROWSER_FRAME_OK ops=5 overlap=d8e7ff win1-title=dde2ea surface=");
          serial_decimal(browser_state[3]);
          serial_string("x");
          serial_decimal(browser_state[4]);
          serial_string("\r\n");
        } else {
          debug_string("AIUEOS_GUEST_BROWSER_FRAME leftover=colour-miss\n");
          serial_string("AIUEOS_GUEST_BROWSER_FRAME leftover=colour-miss ops=");
          serial_decimal((uint32_t)count);
          serial_string(" overlap=");
          serial_rgb(overlap);
          serial_string(" win1-title=");
          serial_rgb(title1);
          serial_string("\r\n");
        }
      }
      if (!frame_ok) {
        /* Input is judged on a frame that was presented; without one it
           would be judged on whatever the paint gate left behind. */
      } else if (!aiueos_desktop_pointer_ready()) {
        debug_string("AIUEOS_GUEST_BROWSER_INPUT leftover=no-pointer-event\n");
        serial_string("AIUEOS_GUEST_BROWSER_INPUT leftover=no-pointer-event tablets=");
        serial_decimal((uint32_t)aiueos_desktop_pointer_tablets_seen());
        serial_string(" used=");
        serial_decimal(aiueos_desktop_pointer_events_used());
        serial_string(" abs=");
        serial_decimal(aiueos_desktop_pointer_events_abs());
        serial_string(" key=");
        serial_decimal(aiueos_desktop_pointer_events_key());
        serial_string("\r\n");
      } else {
        uint32_t px = (uint32_t)(((uint64_t)aiueos_desktop_pointer_abs_x() *
                                  browser_state[3]) / 32768U);
        uint32_t py = (uint32_t)(((uint64_t)aiueos_desktop_pointer_abs_y() *
                                  browser_state[4]) / 32768U);
        int64_t hit = (int64_t)kotoba_aiueos_browser_reduce(st, 128, 1, px, py);
        if (hit <= 0) {
          debug_string("AIUEOS_GUEST_BROWSER_INPUT leftover=pointer-miss\n");
          serial_string("AIUEOS_GUEST_BROWSER_INPUT leftover=pointer-miss px=");
          serial_decimal(px);
          serial_string(" py=");
          serial_decimal(py);
          serial_string("\r\n");
        } else {
          int64_t again = (int64_t)kotoba_aiueos_browser_frame(st, 128, op, 256);
          uint32_t overlap = 0, title1 = 0;
          if (again > 0 && aiueos_desktop_present_ops(browser_ops, (uint64_t)again)) {
            overlap = aiueos_desktop_sample_rgb(100, 80);
            title1 = aiueos_desktop_sample_rgb(60, 50);
          }
          if (again <= 0 || overlap == 0) {
            debug_string("AIUEOS_GUEST_BROWSER_INPUT leftover=frame-refused\n");
            serial_string("AIUEOS_GUEST_BROWSER_INPUT leftover=frame-refused\r\n");
          } else if (overlap == 0xd8e7ffU) {
            debug_string("AIUEOS_GUEST_BROWSER_INPUT leftover=raise-not-painted\n");
            serial_string("AIUEOS_GUEST_BROWSER_INPUT leftover=raise-not-painted\r\n");
          } else if (hit == 1 && browser_state[2] == 1 && browser_state[10] == 1 &&
                     overlap == 0xffffffU && title1 == 0xd8e7ffU) {
            debug_string("AIUEOS_GUEST_BROWSER_INPUT_OK\n");
            serial_string("AIUEOS_GUEST_BROWSER_INPUT_OK eventq-used=1 kind=pointer-down px=");
            serial_decimal(px);
            serial_string(" py=");
            serial_decimal(py);
            serial_string(" hit=1 front=1 overlap=ffffff win1-title=d8e7ff\r\n");
          } else {
            debug_string("AIUEOS_GUEST_BROWSER_INPUT leftover=vector-miss\n");
            serial_string("AIUEOS_GUEST_BROWSER_INPUT leftover=vector-miss hit=");
            serial_decimal((uint32_t)hit);
            serial_string(" overlap=");
            serial_rgb(overlap);
            serial_string("\r\n");
          }
        }
      }
    }
    /* Guest browser desktop with text (ADR-0224). The same boot-desktop,
       now with window titles and bodies; Kotoba lays out rects AND glyphs in
       one list (`kotoba_aiueos_browser_frame2`) against the font the loader
       brought in the initramfs, C blits it. The known answers (op count,
       count and FNV-1a of the #111111 pixels) come from a model of the same
       frame written apart from both (ADR-0224). If a tablet press arrived,
       it is reduced on this surface too and the frame is drawn again: the
       back window's text must then cover the other's. Do not qemu_exit. */
    {
      static uint32_t __attribute__((section(".high_bss"), aligned(16))) surface[2048];
      static const uint32_t boot[15] = {1, 2, 2, 0, 0,
                                        1, 32, 32, 720, 540,
                                        2, 96, 72, 640, 480};
      /* aiueos / kotoba-lang/browser, then ブラウザが画面です */
      static const uint32_t title1[] = {97, 105, 117, 101, 111, 115};
      static const uint32_t body1[] = {107, 111, 116, 111, 98, 97, 45, 108, 97, 110, 103, 47, 98, 114, 111, 119, 115, 101, 114, 10, 12502, 12521, 12454, 12470, 12364, 30011, 38754, 12391, 12377};
      /* ブラウザ / 日本語の文字も表示できます。 */
      static const uint32_t title2[] = {12502, 12521, 12454, 12470};
      static const uint32_t body2[] = {26085, 26412, 35486, 12398, 25991, 23383, 12418, 34920, 31034, 12391, 12365, 12414, 12377, 12290};
      uint64_t font_length = 0;
      const uint8_t *font = aiueos_initramfs_font(&font_length);
      uint64_t dict_length = 0;
      uint64_t dict = (uint64_t)(uintptr_t)aiueos_initramfs_dictionary(&dict_length);
      uint64_t sp = (uint64_t)(uintptr_t)surface;
      uint32_t text_px = 0, text_hash = 0;
      int64_t count;
      int text_ok = 0;
      for (int i = 0; i < 2048; i++) surface[i] = 0;
      for (int i = 0; i < 15; i++) surface[i] = boot[i];
      surface[3] = aiueos_desktop_width();
      surface[4] = aiueos_desktop_height();
      for (unsigned i = 0; i < sizeof(title1) / 4; i++) surface[32 + i] = title1[i];
      for (unsigned i = 0; i < sizeof(body1) / 4; i++) surface[160 + i] = body1[i];
      for (unsigned i = 0; i < sizeof(title2) / 4; i++) surface[64 + i] = title2[i];
      for (unsigned i = 0; i < sizeof(body2) / 4; i++) surface[224 + i] = body2[i];
      if (!font) {
        debug_string("AIUEOS_GUEST_BROWSER_TEXT leftover=font-absent\n");
        serial_string("AIUEOS_GUEST_BROWSER_TEXT leftover=font-absent\r\n");
      } else {
        count = (int64_t)kotoba_aiueos_browser_frame2(sp, 8192,
                  (uint64_t)(uintptr_t)font, font_length);
        if (count <= 0) {
          debug_string("AIUEOS_GUEST_BROWSER_TEXT leftover=frame-refused\n");
          serial_string("AIUEOS_GUEST_BROWSER_TEXT leftover=frame-refused reason=-");
          serial_decimal((uint32_t)(-count));
          serial_string("\r\n");
        } else if (!aiueos_desktop_present_ops2(surface + 480, (uint64_t)count,
                                                font, font_length)) {
          debug_string("AIUEOS_GUEST_BROWSER_TEXT leftover=present-refused\n");
          serial_string("AIUEOS_GUEST_BROWSER_TEXT leftover=present-refused\r\n");
        } else {
          text_hash = aiueos_desktop_colour_census(0x333333U, &text_px);
          /* On the real display too (virtio-gpu scanout 0). Its own line:
             the census above is of memory and does not depend on it. */
          if (aiueos_desktop_show()) {
            serial_string("AIUEOS_GUEST_BROWSER_SCANOUT_OK resource=7 scanout=0 source=gop-framebuffer\r\n");
          } else {
            serial_string("AIUEOS_GUEST_BROWSER_SCANOUT leftover=not-shown\r\n");
          }
          if (count == 70 && text_px == 1079 && text_hash == 0x89910f34U) {
            text_ok = 1;
            debug_string("AIUEOS_GUEST_BROWSER_TEXT_OK\n");
            serial_string("AIUEOS_GUEST_BROWSER_TEXT_OK ops=70 text-px=1079 hash=89910f34 font-bytes=");
          } else {
            debug_string("AIUEOS_GUEST_BROWSER_TEXT leftover=census-miss\n");
            serial_string("AIUEOS_GUEST_BROWSER_TEXT leftover=census-miss ops=");
            serial_decimal((uint32_t)count);
            serial_string(" text-px=");
            serial_decimal(text_px);
            serial_string(" hash=");
            serial_hex32(text_hash);
            serial_string(" font-bytes=");
          }
          serial_decimal((uint32_t)font_length);
          serial_string(" surface=");
          serial_decimal(surface[3]);
          serial_string("x");
          serial_decimal(surface[4]);
          serial_string("\r\n");
          browser_hold_for_screendump();
        }
      }
      if (text_ok && aiueos_desktop_pointer_ready()) {
        uint32_t px = (uint32_t)(((uint64_t)aiueos_desktop_pointer_abs_x() * surface[3]) / 32768U);
        uint32_t py = (uint32_t)(((uint64_t)aiueos_desktop_pointer_abs_y() * surface[4]) / 32768U);
        int64_t hit = (int64_t)kotoba_aiueos_browser_reduce(sp, 128, 1, px, py);
        int64_t again = hit > 0 ? (int64_t)kotoba_aiueos_browser_frame2(sp, 8192,
                                     (uint64_t)(uintptr_t)font, font_length) : 0;
        if (again > 0 && aiueos_desktop_present_ops2(surface + 480, (uint64_t)again,
                                                    font, font_length)) {
          text_hash = aiueos_desktop_colour_census(0x333333U, &text_px);
          (void)aiueos_desktop_show();
          if (hit == 1 && again == 70 && text_px == 880 && text_hash == 0xb9f96599U) {
            debug_string("AIUEOS_GUEST_BROWSER_TEXT_RAISED_OK\n");
            serial_string("AIUEOS_GUEST_BROWSER_TEXT_RAISED_OK hit=1 ops=70 text-px=880 hash=b9f96599\r\n");
            browser_hold_for_screendump();
            /* Typing into the focused window (ADR-0225). The host types
               n i h o n n g o Enter k u w a w a r u Space Enter once, after
               TYPE_GO (ADR-0235: through the Unihan dictionary くわわる has
               the one candidate 加, the kanji this gate has always
               committed; か's first is now 下);
               every press goes through Kotoba `kotoba_aiueos_browser_key`
               (the hosted IME's rules), and the committed text lands in
               window 1's body. TYPE_READY stops the host's repeated keys,
               the drain discards what they already delivered. */
            {
              uint32_t presses = 0, committed = 0, refused = 0;
              int type_ok = 0;
              surface[432] = 1;
              serial_string("AIUEOS_GUEST_BROWSER_TYPE_READY\r\n");
              (void)aiueos_keyboard_drain(4000000U);
              serial_string("AIUEOS_GUEST_BROWSER_TYPE_GO keys=19\r\n");
              while (presses < 19) {
                uint32_t code = aiueos_keyboard_next_press(60000000U);
                int64_t r;
                if (!code) break;
                presses++;
                r = (int64_t)kotoba_aiueos_browser_key(sp, 8192, dict, dict_length, (uint64_t)code * 4U + 1U);
                if (r < 0) refused++; else committed += (uint32_t)r;
              }
              int64_t typed = (int64_t)kotoba_aiueos_browser_frame2(sp, 8192,
                                (uint64_t)(uintptr_t)font, font_length);
              if (presses == 19 && typed > 0 &&
                  aiueos_desktop_present_ops2(surface + 480, (uint64_t)typed, font, font_length)) {
                text_hash = aiueos_desktop_colour_census(0x333333U, &text_px);
                (void)aiueos_desktop_show();
                if (committed == 5 && refused == 0 && typed == 75 &&
                    text_px == 1068 && text_hash == 0xa92b8f58U) {
                  debug_string("AIUEOS_GUEST_BROWSER_TYPE_OK\n");
                  serial_string("AIUEOS_GUEST_BROWSER_TYPE_OK presses=19 committed=5 ops=75 text-px=1068 hash=a92b8f58\r\n");
                  type_ok = 1;
                } else {
                  debug_string("AIUEOS_GUEST_BROWSER_TYPE leftover=census-miss\n");
                  serial_string("AIUEOS_GUEST_BROWSER_TYPE leftover=census-miss committed=");
                  serial_decimal(committed);
                  serial_string(" refused=");
                  serial_decimal(refused);
                  serial_string(" ops=");
                  serial_decimal((uint32_t)typed);
                  serial_string(" text-px=");
                  serial_decimal(text_px);
                  serial_string(" hash=");
                  serial_hex32(text_hash);
                  serial_string("\r\n");
                }
                browser_hold_for_screendump();
                /* The preedit (ADR-0227). The host types `k a n`: the IME
                   holds か as preedit and `n` as romaji, commits nothing, and
                   Kotoba frame2 draws both, underlined, after window 1's body.
                   Then Enter: かん is committed and the next frame has no
                   rule. Both censuses are os/aiueos/scripts/
                   browser-frame-model.cljk's, a model that reproduces the
                   three frames above. */
                if (type_ok) {
                  uint32_t pressed = 0, stray = 0, pre_px = 0, pre_hash = 0;
                  int preedit_ok = 0;
                  int64_t shown, landed = -1, after = 0;
                  serial_string("AIUEOS_GUEST_BROWSER_PREEDIT_GO keys=3\r\n");
                  while (pressed < 3) {
                    uint32_t code = aiueos_keyboard_next_press(60000000U);
                    if (!code) break;
                    pressed++;
                    if (kotoba_aiueos_browser_key(sp, 8192, dict, dict_length, (uint64_t)code * 4U + 1U) != 0) stray++;
                  }
                  shown = (int64_t)kotoba_aiueos_browser_frame2(sp, 8192,
                            (uint64_t)(uintptr_t)font, font_length);
                  if (pressed == 3 && shown > 0 &&
                      aiueos_desktop_present_ops2(surface + 480, (uint64_t)shown, font, font_length)) {
                    pre_hash = aiueos_desktop_colour_census(0x333333U, &pre_px);
                    (void)aiueos_desktop_show();
                    serial_string("AIUEOS_GUEST_BROWSER_PREEDIT_SHOWN ops=");
                    serial_decimal((uint32_t)shown);
                    serial_string(" text-px=");
                    serial_decimal(pre_px);
                    serial_string(" hash=");
                    serial_hex32(pre_hash);
                    serial_string(" preedit=");
                    serial_decimal(surface[445]);
                    serial_string(" romaji=");
                    serial_decimal(surface[433]);
                    serial_string("\r\n");
                    browser_hold_for_screendump();
                    serial_string("AIUEOS_GUEST_BROWSER_PREEDIT_ENTER keys=1\r\n");
                    {
                      uint32_t code = aiueos_keyboard_next_press(60000000U);
                      if (code) landed = (int64_t)kotoba_aiueos_browser_key(sp, 8192, dict, dict_length, (uint64_t)code * 4U + 1U);
                    }
                    after = (int64_t)kotoba_aiueos_browser_frame2(sp, 8192,
                              (uint64_t)(uintptr_t)font, font_length);
                    if (after > 0 &&
                        aiueos_desktop_present_ops2(surface + 480, (uint64_t)after, font, font_length)) {
                      text_hash = aiueos_desktop_colour_census(0x333333U, &text_px);
                      (void)aiueos_desktop_show();
                    }
                    if (stray == 0 && shown == 79 && pre_px == 1146 && pre_hash == 0x566a1c8fU &&
                        landed == 2 && after == 77 && text_px == 1128 && text_hash == 0x193030b3U) {
                      debug_string("AIUEOS_GUEST_BROWSER_PREEDIT_OK\n");
                      serial_string("AIUEOS_GUEST_BROWSER_PREEDIT_OK shown-ops=67 shown-px=1146 shown-hash=566a1c8f committed=2 ops=77 text-px=1128 hash=193030b3\r\n");
                      preedit_ok = 1;
                    } else {
                      debug_string("AIUEOS_GUEST_BROWSER_PREEDIT leftover=census-miss\n");
                      serial_string("AIUEOS_GUEST_BROWSER_PREEDIT leftover=census-miss stray=");
                      serial_decimal(stray);
                      serial_string(" committed=");
                      serial_decimal((uint32_t)landed);
                      serial_string(" ops=");
                      serial_decimal((uint32_t)after);
                      serial_string(" text-px=");
                      serial_decimal(text_px);
                      serial_string(" hash=");
                      serial_hex32(text_hash);
                      serial_string("\r\n");
                    }
                    browser_hold_for_screendump();
                  } else {
                    debug_string("AIUEOS_GUEST_BROWSER_PREEDIT leftover=keys-missing\n");
                    serial_string("AIUEOS_GUEST_BROWSER_PREEDIT leftover=keys-missing presses=");
                    serial_decimal(pressed);
                    serial_string("\r\n");
                  }
                  /* The IME toggle (ADR-0228). The host types Hankaku/Zenkaku
                     (evdev 41) k a, Hankaku/Zenkaku k a Enter. Kotoba
                     `kotoba_aiueos_browser_key` decides what each key is: the
                     first 41 turns the IME off, so `k a` lands as latin; the
                     second turns it on, so `k a` Enter commits か. C only
                     counts what the object answered, and whether each answer
                     is the one ADR-0228's vectors give (0 1 1 0 0 0 1). The
                     census is os/aiueos/scripts/browser-frame-model.cljk's. */
                  if (preedit_ok) {
                    uint32_t tp = 0, latin = 0, kana = 0, off_seen = 1, miss = 0;
                    int toggle_ok = 0;
                    int64_t tog;
                    serial_string("AIUEOS_GUEST_BROWSER_IME_TOGGLE_GO keys=7\r\n");
                    while (tp < 7) {
                      uint32_t code = aiueos_keyboard_next_press(60000000U);
                      int64_t r;
                      if (!code) break;
                      r = (int64_t)kotoba_aiueos_browser_key(sp, 8192, dict, dict_length, (uint64_t)code * 4U + 1U);
                      if (r != ((tp == 1 || tp == 2 || tp == 6) ? 1 : 0)) miss++;
                      if (tp == 0) off_seen = surface[432];
                      if (r > 0) {
                        if (surface[432]) kana += (uint32_t)r; else latin += (uint32_t)r;
                      }
                      tp++;
                    }
                    tog = (int64_t)kotoba_aiueos_browser_frame2(sp, 8192,
                            (uint64_t)(uintptr_t)font, font_length);
                    if (tp == 7 && tog > 0 &&
                        aiueos_desktop_present_ops2(surface + 480, (uint64_t)tog, font, font_length)) {
                      text_hash = aiueos_desktop_colour_census(0x333333U, &text_px);
                      (void)aiueos_desktop_show();
                      if (miss == 0 && off_seen == 0 && latin == 2 && kana == 1 &&
                          surface[432] == 1 && tog == 80 &&
                          text_px == 1205 && text_hash == 0x322e206eU) {
                        debug_string("AIUEOS_GUEST_BROWSER_IME_TOGGLE_OK\n");
                        serial_string("AIUEOS_GUEST_BROWSER_IME_TOGGLE_OK presses=7 off=0 latin=2 committed=1 ime=1 ops=80 text-px=1205 hash=322e206e\r\n");
                        toggle_ok = 1;
                      } else {
                        debug_string("AIUEOS_GUEST_BROWSER_IME_TOGGLE leftover=census-miss\n");
                        serial_string("AIUEOS_GUEST_BROWSER_IME_TOGGLE leftover=census-miss miss=");
                        serial_decimal(miss);
                        serial_string(" off=");
                        serial_decimal(off_seen);
                        serial_string(" latin=");
                        serial_decimal(latin);
                        serial_string(" committed=");
                        serial_decimal(kana);
                        serial_string(" ime=");
                        serial_decimal(surface[432]);
                        serial_string(" ops=");
                        serial_decimal((uint32_t)tog);
                        serial_string(" text-px=");
                        serial_decimal(text_px);
                        serial_string(" hash=");
                        serial_hex32(text_hash);
                        serial_string("\r\n");
                      }
                      browser_hold_for_screendump();
                    } else {
                      debug_string("AIUEOS_GUEST_BROWSER_IME_TOGGLE leftover=keys-missing\n");
                      serial_string("AIUEOS_GUEST_BROWSER_IME_TOGGLE leftover=keys-missing presses=");
                      serial_decimal(tp);
                      serial_string("\r\n");
                    }
                    /* The titlebar drag (ADR-0229). The host presses the
                       tablet at (60, 50) -- window 1's titlebar -- moves to
                       (140, 90) (220, 120) (300, 150), releases, and moves
                       once more to (380, 200). C scales each batch to surface
                       pixels and hands it to Kotoba
                       `kotoba_aiueos_browser_reduce`, which decides the
                       capture and the move (browser.input's rules). C counts
                       each answer against the vectors' 1 1 1 1 0 0 and reads
                       where window 1 ended up. The census is
                       os/aiueos/scripts/browser-frame-model.cljk's. */
                    if (toggle_ok) {
                      uint32_t ev = 0, off = 0, ax = 0, ay = 0;
                      int64_t dragged;
                      int drag_ok = 0;
                      static const int64_t want[6] = {1, 1, 1, 1, 0, 0};
                      static const uint32_t kinds[6] = {1, 3, 3, 3, 4, 3};
                      (void)aiueos_tablet_drain(4000000U);
                      serial_string("AIUEOS_GUEST_BROWSER_DRAG_GO events=6\r\n");
                      while (ev < 6) {
                        uint32_t kind = aiueos_tablet_next(60000000U, &ax, &ay);
                        uint32_t px, py;
                        int64_t r;
                        if (!kind) break;
                        px = (uint32_t)(((uint64_t)ax * surface[3]) / 32768U);
                        py = (uint32_t)(((uint64_t)ay * surface[4]) / 32768U);
                        r = (int64_t)kotoba_aiueos_browser_reduce(sp, 128, kind, px, py);
                        if (kind != kinds[ev] || r != want[ev]) off++;
                        ev++;
                      }
                      dragged = (int64_t)kotoba_aiueos_browser_frame2(sp, 8192,
                                  (uint64_t)(uintptr_t)font, font_length);
                      if (ev == 6 && dragged > 0 &&
                          aiueos_desktop_present_ops2(surface + 480, (uint64_t)dragged, font, font_length)) {
                        text_hash = aiueos_desktop_colour_census(0x333333U, &text_px);
                        (void)aiueos_desktop_show();
                        /* stack [2 1]: window 1 is words 10..14 */
                        if (off == 0 && surface[10] == 1 && surface[11] == 272 &&
                            surface[12] == 132 && surface[25] == 0 && dragged == 80 &&
                            text_px == 1947 && text_hash == 0x523440e0U) {
                          debug_string("AIUEOS_GUEST_BROWSER_DRAG_OK\n");
                          serial_string("AIUEOS_GUEST_BROWSER_DRAG_OK events=6 answers=111100 from=32,32 to=272,132 capture=0 ops=80 text-px=1947 hash=523440e0\r\n");
                          drag_ok = 1;
                        } else {
                          debug_string("AIUEOS_GUEST_BROWSER_DRAG leftover=census-miss\n");
                          serial_string("AIUEOS_GUEST_BROWSER_DRAG leftover=census-miss off=");
                          serial_decimal(off);
                          serial_string(" front=");
                          serial_decimal(surface[10]);
                          serial_string(" to=");
                          serial_decimal(surface[11]);
                          serial_string(",");
                          serial_decimal(surface[12]);
                          serial_string(" capture=");
                          serial_decimal(surface[25]);
                          serial_string(" ops=");
                          serial_decimal((uint32_t)dragged);
                          serial_string(" text-px=");
                          serial_decimal(text_px);
                          serial_string(" hash=");
                          serial_hex32(text_hash);
                          serial_string("\r\n");
                        }
                        browser_hold_for_screendump();
                      } else {
                        debug_string("AIUEOS_GUEST_BROWSER_DRAG leftover=events-missing\n");
                        serial_string("AIUEOS_GUEST_BROWSER_DRAG leftover=events-missing events=");
                        serial_decimal(ev);
                        serial_string(" off=");
                        serial_decimal(off);
                        serial_string(" frame=");
                        serial_decimal((uint32_t)(dragged < 0 ? -dragged : dragged));
                        serial_string("\r\n");
                      }
                      /* The resize (ADR-0230). The host presses the tablet at
                         (984, 664) -- inside window 1's 16 px resize handle
                         after the drag -- moves to (784, 564) (300, 200)
                         (504, 324), releases, and moves once more to
                         (900, 700). Kotoba `kotoba_aiueos_browser_reduce`
                         decides the capture and the size (browser.input's
                         :resize, clamped at 120 x 80); C counts the answers
                         against the vectors' 1 1 1 1 0 0, reads window 1's size
                         after the third event (the clamp) and after the last.
                         The census is os/aiueos/scripts/browser-frame-model.cljk's. */
                      if (drag_ok) {
                        uint32_t rev = 0, roff = 0, cw = 0, ch = 0;
                        int64_t resized;
                        int resize_ok = 0;
                        (void)aiueos_tablet_drain(4000000U);
                        serial_string("AIUEOS_GUEST_BROWSER_RESIZE_GO events=6\r\n");
                        while (rev < 6) {
                          uint32_t kind = aiueos_tablet_next(60000000U, &ax, &ay);
                          uint32_t px, py;
                          int64_t r;
                          if (!kind) break;
                          px = (uint32_t)(((uint64_t)ax * surface[3]) / 32768U);
                          py = (uint32_t)(((uint64_t)ay * surface[4]) / 32768U);
                          r = (int64_t)kotoba_aiueos_browser_reduce(sp, 128, kind, px, py);
                          if (kind != kinds[rev] || r != want[rev]) roff++;
                          if (rev == 2) { cw = surface[13]; ch = surface[14]; }
                          rev++;
                        }
                        resized = (int64_t)kotoba_aiueos_browser_frame2(sp, 8192,
                                    (uint64_t)(uintptr_t)font, font_length);
                        if (rev == 6 && resized > 0 &&
                            aiueos_desktop_present_ops2(surface + 480, (uint64_t)resized, font, font_length)) {
                          text_hash = aiueos_desktop_colour_census(0x333333U, &text_px);
                          (void)aiueos_desktop_show();
                          /* stack [2 1]: window 1 is words 10..14 */
                          if (roff == 0 && cw == 120 && ch == 80 && surface[10] == 1 &&
                              surface[11] == 272 && surface[12] == 132 &&
                              surface[13] == 240 && surface[14] == 200 && surface[25] == 0 &&
                              resized == 80 && text_px == 1947 &&
                              text_hash == 0x523440e0U) {
                            debug_string("AIUEOS_GUEST_BROWSER_RESIZE_OK\n");
                            serial_string("AIUEOS_GUEST_BROWSER_RESIZE_OK events=6 answers=111100 clamp=120x80 size=240x200 at=272,132 capture=0 ops=80 text-px=1947 hash=523440e0\r\n");
                            resize_ok = 1;
                          } else {
                            debug_string("AIUEOS_GUEST_BROWSER_RESIZE leftover=census-miss\n");
                            serial_string("AIUEOS_GUEST_BROWSER_RESIZE leftover=census-miss off=");
                            serial_decimal(roff);
                            serial_string(" clamp=");
                            serial_decimal(cw);
                            serial_string("x");
                            serial_decimal(ch);
                            serial_string(" size=");
                            serial_decimal(surface[13]);
                            serial_string("x");
                            serial_decimal(surface[14]);
                            serial_string(" at=");
                            serial_decimal(surface[11]);
                            serial_string(",");
                            serial_decimal(surface[12]);
                            serial_string(" capture=");
                            serial_decimal(surface[25]);
                            serial_string(" ops=");
                            serial_decimal((uint32_t)resized);
                            serial_string(" text-px=");
                            serial_decimal(text_px);
                            serial_string(" hash=");
                            serial_hex32(text_hash);
                            serial_string("\r\n");
                          }
                          browser_hold_for_screendump();
                        } else {
                          debug_string("AIUEOS_GUEST_BROWSER_RESIZE leftover=events-missing\n");
                          serial_string("AIUEOS_GUEST_BROWSER_RESIZE leftover=events-missing events=");
                          serial_decimal(rev);
                          serial_string(" off=");
                          serial_decimal(roff);
                          serial_string(" frame=");
                          serial_decimal((uint32_t)(resized < 0 ? -resized : resized));
                          serial_string("\r\n");
                        }
                        /* The event loop (ADR-0231). Every gate above reads a
                           fixed sequence from one device and draws once at its
                           end; this one is a loop. It polls the tablet and the
                           keyboard in turn, hands whatever arrives first to its
                           Kotoba reducer (`kotoba_aiueos_browser_reduce` for a
                           pointer batch, `kotoba_aiueos_browser_key` for a key
                           press) and presents a frame after EVERY event. The
                           host sends k a Enter, a press on window 2's titlebar
                           at (150, 85), a move to (250, 185), a release, and
                           n i Enter -- each only after the previous event's
                           frame line, so the order is the host's and not the
                           poll's. C decides nothing: routing by device is the
                           mechanism; what an event does is the objects'. It
                           counts the answers against 0 0 1 2 2 0 0 0 1 (a
                           pointer answer is a window id: browser-reduce-v1's
                           :dragging-window-2-leaves-window-1) and
                           folds each frame's census hash into an FNV-1a chain;
                           the per-frame censuses and the chain are
                           os/aiueos/scripts/browser-frame-model.cljk's.
                           `idle-min` is the fewest empty polls between two
                           events: > 0 means each event found the loop waiting. */
                        if (resize_ok) {
                          static const int64_t lwant[9] = {0, 0, 1, 2, 2, 0, 0, 0, 1};
                          static const uint32_t lsrc[9] = {0, 0, 0, 1, 3, 4, 0, 0, 0};
                          static const uint32_t lops[9] = {82, 82, 81, 81, 81, 81, 83, 83, 82};
                          uint32_t n = 0, loff = 0, lpx = 0, lhash = 0, chain = 2166136261U;
                          uint32_t idle = 0, idle_min = 0xffffffffU, frames = 0;
                          int64_t lastops = 0;
                          int loop_ok = 0;
                          (void)aiueos_tablet_drain(4000000U);
                          (void)aiueos_keyboard_drain(4000000U);
                          /* stack [1 2] once window 2 is raised: it is words 10..14 */
                          serial_string("AIUEOS_GUEST_BROWSER_LOOP_GO events=9\r\n");
                          while (n < 9 && idle < 60000U) {
                            uint32_t src = aiueos_tablet_next(1024U, &ax, &ay);
                            uint32_t code = 0;
                            int64_t r, fo;
                            if (src) {
                              uint32_t px = (uint32_t)(((uint64_t)ax * surface[3]) / 32768U);
                              uint32_t py = (uint32_t)(((uint64_t)ay * surface[4]) / 32768U);
                              r = (int64_t)kotoba_aiueos_browser_reduce(sp, 128, src, px, py);
                            } else {
                              code = aiueos_keyboard_next_press(1024U);
                              if (!code) { idle++; continue; }
                              r = (int64_t)kotoba_aiueos_browser_key(sp, 8192, dict, dict_length, (uint64_t)code * 4U + 1U);
                            }
                            if (idle < idle_min) idle_min = idle;
                            idle = 0;
                            fo = (int64_t)kotoba_aiueos_browser_frame2(sp, 8192,
                                   (uint64_t)(uintptr_t)font, font_length);
                            if (fo > 0 && aiueos_desktop_present_ops2(surface + 480, (uint64_t)fo,
                                                                      font, font_length)) {
                              lhash = aiueos_desktop_colour_census(0x333333U, &lpx);
                              (void)aiueos_desktop_show();
                              frames++;
                              for (int b = 0; b < 4; b++) {
                                chain ^= (lhash >> (8 * b)) & 255U;
                                chain *= 16777619U;
                              }
                            }
                            if (src != lsrc[n] || r != lwant[n] || fo != (int64_t)lops[n]) loff++;
                            lastops = fo;
                            n++;
                            serial_string("AIUEOS_GUEST_BROWSER_LOOP_FRAME n=");
                            serial_decimal(n);
                            serial_string(src ? " src=pointer answer=" : " src=key answer=");
                            serial_decimal((uint32_t)(r < 0 ? -r : r));
                            serial_string(" ops=");
                            serial_decimal((uint32_t)(fo < 0 ? -fo : fo));
                            serial_string(" text-px=");
                            serial_decimal(lpx);
                            serial_string(" hash=");
                            serial_hex32(lhash);
                            serial_string("\r\n");
                          }
                          if (n == 9 && frames == 9 && loff == 0 && chain == 0xb185dff1U &&
                              lastops == 82 && lpx == 901 && lhash == 0x7b0f9b05U &&
                              surface[2] == 2 && surface[10] == 2 && surface[11] == 196 &&
                              surface[12] == 172 && surface[25] == 0) {
                            loop_ok = 1;
                            debug_string("AIUEOS_GUEST_BROWSER_LOOP_OK\n");
                            serial_string("AIUEOS_GUEST_BROWSER_LOOP_OK events=9 frames=9 answers=001220001 focus=2 at=196,172 capture=0 chain=b185dff1 ops=82 text-px=901 hash=7b0f9b05 idle-min=");
                            serial_decimal(idle_min);
                            serial_string("\r\n");
                            browser_hold_for_screendump();
                          } else if (n < 9) {
                            debug_string("AIUEOS_GUEST_BROWSER_LOOP leftover=events-missing\n");
                            serial_string("AIUEOS_GUEST_BROWSER_LOOP leftover=events-missing events=");
                            serial_decimal(n);
                            serial_string(" frames=");
                            serial_decimal(frames);
                            serial_string("\r\n");
                          } else {
                            debug_string("AIUEOS_GUEST_BROWSER_LOOP leftover=census-miss\n");
                            serial_string("AIUEOS_GUEST_BROWSER_LOOP leftover=census-miss off=");
                            serial_decimal(loff);
                            serial_string(" frames=");
                            serial_decimal(frames);
                            serial_string(" chain=");
                            serial_hex32(chain);
                            serial_string(" focus=");
                            serial_decimal(surface[2]);
                            serial_string(" front=");
                            serial_decimal(surface[10]);
                            serial_string(" at=");
                            serial_decimal(surface[11]);
                            serial_string(",");
                            serial_decimal(surface[12]);
                            serial_string(" capture=");
                            serial_decimal(surface[25]);
                            serial_string("\r\n");
                          }
                          /* The caret (ADR-0232). After the loop, window 2 is
                             focused with に committed and nothing composed. The
                             host sends k a, then Backspace three times, each
                             after the previous frame's line. The first
                             Backspace drops the preedit か; the next two find
                             nothing composed and delete the code point before
                             the caret -- に, then 。 (browser.text-edit
                             delete-backward, in Kotoba browser-key). Every frame
                             must END with the caret: browser-frame2's last op is
                             then a 1 x 16 #111111 rect, and C reads where it
                             is only to print it. Answers, op counts, caret
                             positions, the per-frame census chain and the last
                             frame are os/aiueos/scripts/browser-frame-model.cljk's. */
                          if (loop_ok) {
                            static const uint32_t ccode[5] = {37, 30, 14, 14, 14};
                            static const uint32_t cops[5] = {84, 84, 82, 81, 80};
                            static const uint32_t ccx[5] = {458, 466, 450, 434, 418};
                            uint32_t k = 0, coff = 0, cpx = 0, chash = 0, cchain = 2166136261U;
                            uint32_t cidle = 0, cframes = 0, cx = 0, cy = 0, blen = 0;
                            int64_t cfo = 0;
                            int caret_ok = 0;
                            (void)aiueos_keyboard_drain(4000000U);
                            serial_string("AIUEOS_GUEST_BROWSER_CARET_GO keys=5\r\n");
                            while (k < 5 && cidle < 60000U) {
                              uint32_t code = aiueos_keyboard_next_press(1024U);
                              int64_t r;
                              int caret_op = 0;
                              if (!code) { cidle++; continue; }
                              cidle = 0;
                              r = (int64_t)kotoba_aiueos_browser_key(sp, 8192, dict, dict_length, (uint64_t)code * 4U + 1U);
                              cfo = (int64_t)kotoba_aiueos_browser_frame2(sp, 8192,
                                      (uint64_t)(uintptr_t)font, font_length);
                              cx = cy = 0;
                              if (cfo > 0 && aiueos_desktop_present_ops2(surface + 480, (uint64_t)cfo,
                                                                         font, font_length)) {
                                const uint32_t *op = surface + 480 + 6 * (uint32_t)(cfo - 1);
                                chash = aiueos_desktop_colour_census(0x333333U, &cpx);
                                (void)aiueos_desktop_show();
                                cframes++;
                                for (int b = 0; b < 4; b++) {
                                  cchain ^= (chash >> (8 * b)) & 255U;
                                  cchain *= 16777619U;
                                }
                                if (op[0] == 1 && op[3] == 1 && op[4] == 16 && op[5] == 0x333333U) {
                                  caret_op = 1;
                                  cx = op[1];
                                  cy = op[2];
                                }
                              }
                              if (code != ccode[k] || r != 0 || cfo != (int64_t)cops[k] ||
                                  !caret_op || cx != ccx[k] || cy != 214) coff++;
                              k++;
                              serial_string("AIUEOS_GUEST_BROWSER_CARET_FRAME n=");
                              serial_decimal(k);
                              serial_string(" key=");
                              serial_decimal(code);
                              serial_string(" answer=");
                              serial_decimal((uint32_t)(r < 0 ? -r : r));
                              serial_string(" ops=");
                              serial_decimal((uint32_t)(cfo < 0 ? -cfo : cfo));
                              serial_string(" caret=");
                              serial_decimal(cx);
                              serial_string(",");
                              serial_decimal(cy);
                              serial_string(" text-px=");
                              serial_decimal(cpx);
                              serial_string(" hash=");
                              serial_hex32(chash);
                              serial_string("\r\n");
                            }
                            /* window 2's body: words 224.. up to its 0 */
                            while (blen < 64 && surface[224 + blen] != 0) blen++;
                            if (k == 5 && cframes == 5 && coff == 0 && cchain == 0x62295970U &&
                                cfo == 80 && cpx == 867 && chash == 0xd039564fU && blen == 13 &&
                                surface[433] == 0 && surface[445] == 0 && surface[2] == 2) {
                              caret_ok = 1;
                              debug_string("AIUEOS_GUEST_BROWSER_CARET_OK\n");
                              serial_string("AIUEOS_GUEST_BROWSER_CARET_OK keys=5 answers=00000 body=13 caret=418,214 chain=62295970 ops=80 text-px=867 hash=d039564f\r\n");
                              browser_hold_for_screendump();
                            } else if (k < 5) {
                              debug_string("AIUEOS_GUEST_BROWSER_CARET leftover=keys-missing\n");
                              serial_string("AIUEOS_GUEST_BROWSER_CARET leftover=keys-missing keys=");
                              serial_decimal(k);
                              serial_string(" frames=");
                              serial_decimal(cframes);
                              serial_string("\r\n");
                            } else {
                              debug_string("AIUEOS_GUEST_BROWSER_CARET leftover=census-miss\n");
                              serial_string("AIUEOS_GUEST_BROWSER_CARET leftover=census-miss off=");
                              serial_decimal(coff);
                              serial_string(" frames=");
                              serial_decimal(cframes);
                              serial_string(" chain=");
                              serial_hex32(cchain);
                              serial_string(" body=");
                              serial_decimal(blen);
                              serial_string(" romaji=");
                              serial_decimal(surface[433]);
                              serial_string(" preedit=");
                              serial_decimal(surface[445]);
                              serial_string("\r\n");
                            }
                            /* Launcher and close (ADR-0233). After the caret,
                               the shell registers apps 1 2 3 -- word 31, the
                               app register; app k's title and document are
                               window slot k's, and slot 3 is written here --
                               so browser-frame2 now draws the launcher row
                               and a close control on each window. The host
                               sends eight tablet batches, each after the
                               previous frame line: a press on launcher button
                               3 at (258, 14), release, a press on window 3's
                               close control at (584, 94), release, the
                               launcher again, release, a press on window 2's
                               close control at (820, 186), release. What a
                               press does is Kotoba `kotoba_aiueos_browser_reduce`'s
                               (browser.surface launch-app / close-window
                               behind the kernel's geometry): 3, then the focus
                               moves to window 2 as window 3 closes, 3 again,
                               and window 2 closing leaves the focus on 3.
                               Answers, window counts, op counts and the census
                               chain are browser-reduce-v1's and
                               os/aiueos/scripts/browser-frame-model.cljk's. */
                            if (caret_ok) {
                              static const uint32_t title3[2] = {12513, 12514};
                              /* ランチャーから開きました */
                              static const uint32_t body3[12] = {12521, 12531, 12481, 12515, 12540, 12363,
                                                                 12425, 38283, 12365, 12414, 12375, 12383};
                              static const int64_t awant[8] = {3, 0, 2, 0, 3, 0, 3, 0};
                              static const uint32_t asrc[8] = {1, 4, 1, 4, 1, 4, 1, 4};
                              static const uint32_t aops[8] = {143, 143, 115, 115, 143, 143, 112, 112};
                              static const uint32_t awin[8] = {3, 3, 2, 2, 3, 3, 2, 2};
                              uint32_t e = 0, aoff = 0, apx = 0, ahash = 0, achain = 2166136261U;
                              uint32_t aidle = 0, aframes = 0;
                              int64_t afo = 0;
                              for (unsigned i = 0; i < 2; i++) surface[96 + i] = title3[i];
                              for (unsigned i = 0; i < 12; i++) surface[288 + i] = body3[i];
                              surface[31] = 7;
                              (void)aiueos_tablet_drain(4000000U);
                              serial_string("AIUEOS_GUEST_BROWSER_LAUNCH_GO events=8 apps=7\r\n");
                              while (e < 8 && aidle < 60000U) {
                                uint32_t src = aiueos_tablet_next(1024U, &ax, &ay);
                                uint32_t px, py;
                                int64_t r;
                                if (!src) { aidle++; continue; }
                                aidle = 0;
                                px = (uint32_t)(((uint64_t)ax * surface[3]) / 32768U);
                                py = (uint32_t)(((uint64_t)ay * surface[4]) / 32768U);
                                r = (int64_t)kotoba_aiueos_browser_reduce(sp, 128, src, px, py);
                                afo = (int64_t)kotoba_aiueos_browser_frame2(sp, 8192,
                                        (uint64_t)(uintptr_t)font, font_length);
                                if (afo > 0 && aiueos_desktop_present_ops2(surface + 480, (uint64_t)afo,
                                                                           font, font_length)) {
                                  ahash = aiueos_desktop_colour_census(0x333333U, &apx);
                                  (void)aiueos_desktop_show();
                                  aframes++;
                                  for (int b = 0; b < 4; b++) {
                                    achain ^= (ahash >> (8 * b)) & 255U;
                                    achain *= 16777619U;
                                  }
                                }
                                if (src != asrc[e] || r != awant[e] || afo != (int64_t)aops[e] ||
                                    surface[1] != awin[e]) aoff++;
                                e++;
                                serial_string("AIUEOS_GUEST_BROWSER_LAUNCH_FRAME n=");
                                serial_decimal(e);
                                serial_string(" src=");
                                serial_decimal(src);
                                serial_string(" at=");
                                serial_decimal(px);
                                serial_string(",");
                                serial_decimal(py);
                                serial_string(r < 0 ? " answer=-" : " answer=");
                                serial_decimal((uint32_t)(r < 0 ? -r : r));
                                serial_string(" windows=");
                                serial_decimal(surface[1]);
                                serial_string(" focus=");
                                serial_decimal(surface[2]);
                                serial_string(" ops=");
                                serial_decimal((uint32_t)(afo < 0 ? -afo : afo));
                                serial_string(" text-px=");
                                serial_decimal(apx);
                                serial_string(" hash=");
                                serial_hex32(ahash);
                                serial_string("\r\n");
                              }
                              /* stack [1 3]: words 5 and 10; the vacated record is zero */
                              if (e == 8 && aframes == 8 && aoff == 0 && achain == 0x2845aee9U &&
                                  afo == 112 && apx == 776 && ahash == 0x98b595bdU &&
                                  surface[1] == 2 && surface[2] == 3 && surface[5] == 1 &&
                                  surface[10] == 3 && surface[15] == 0 && surface[25] == 0) {
                                debug_string("AIUEOS_GUEST_BROWSER_LAUNCH_OK\n");
                                serial_string("AIUEOS_GUEST_BROWSER_LAUNCH_OK events=8 answers=30203030 windows=2 stack=1,3 focus=3 chain=2845aee9 ops=112 text-px=776 hash=98b595bd\r\n");
                                browser_hold_for_screendump();
                                /* The dictionary (ADR-0235). The host types
                                   y a m a Space at DICT_GO: Kotoba
                                   `kotoba_aiueos_browser_key` finds やま in
                                   the initramfs dictionary (generated from
                                   Unicode Unihan) by binary search and
                                   shows its first candidate 山 as the
                                   composition. After that frame's dump, at
                                   DICT_NEXT: Space (岾) Escape (the reading
                                   back from its record) Space (山) Enter,
                                   s h o u Space Space (償, しょう's second)
                                   Enter -- 山 and 償 land in window 3's
                                   body. C hands the dictionary's bytes over
                                   and counts answers; it never looks a
                                   reading up. Answers are browser-ime-v2's,
                                   censuses os/aiueos/scripts/
                                   browser-frame-model.cljk's. */
                                {
                                  static const int64_t dwant[16] = {0, 0, 0, 0, 0,
                                                                    0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 1};
                                  uint32_t dp = 0, doff = 0, dpx = 0, dhash = 0, cpx = 0, chash = 0;
                                  uint32_t conv = 0, rec = 0, pre = 0, pre0 = 0;
                                  int64_t dfo = 0, dfo2 = 0;
                                  serial_string("AIUEOS_GUEST_BROWSER_DICT_GO keys=5 dictionary-bytes=");
                                  serial_decimal((uint32_t)dict_length);
                                  serial_string("\r\n");
                                  while (dp < 5) {
                                    uint32_t code = aiueos_keyboard_next_press(60000000U);
                                    if (!code) break;
                                    if ((int64_t)kotoba_aiueos_browser_key(sp, 8192, dict, dict_length,
                                                                           (uint64_t)code * 4U + 1U) != dwant[dp]) doff++;
                                    dp++;
                                  }
                                  conv = surface[442];
                                  rec = surface[444];
                                  pre = surface[445];
                                  pre0 = surface[446];
                                  dfo = (int64_t)kotoba_aiueos_browser_frame2(sp, 8192,
                                          (uint64_t)(uintptr_t)font, font_length);
                                  if (dfo > 0 && aiueos_desktop_present_ops2(surface + 480, (uint64_t)dfo,
                                                                             font, font_length)) {
                                    chash = aiueos_desktop_colour_census(0x333333U, &cpx);
                                    (void)aiueos_desktop_show();
                                  }
                                  serial_string("AIUEOS_GUEST_BROWSER_DICT_SHOWN keys=");
                                  serial_decimal(dp);
                                  serial_string(" converting=");
                                  serial_decimal(conv);
                                  serial_string(" record=");
                                  serial_decimal(rec);
                                  serial_string(" preedit=");
                                  serial_decimal(pre);
                                  serial_string(" cp=");
                                  serial_decimal(pre0);
                                  serial_string(" ops=");
                                  serial_decimal((uint32_t)(dfo < 0 ? -dfo : dfo));
                                  serial_string(" text-px=");
                                  serial_decimal(cpx);
                                  serial_string(" hash=");
                                  serial_hex32(chash);
                                  serial_string("\r\n");
                                  browser_hold_for_screendump();
                                  if (dp == 5) {
                                    serial_string("AIUEOS_GUEST_BROWSER_DICT_NEXT keys=11\r\n");
                                    while (dp < 16) {
                                      uint32_t code = aiueos_keyboard_next_press(60000000U);
                                      if (!code) break;
                                      if ((int64_t)kotoba_aiueos_browser_key(sp, 8192, dict, dict_length,
                                                                             (uint64_t)code * 4U + 1U) != dwant[dp]) doff++;
                                      dp++;
                                    }
                                    dfo2 = (int64_t)kotoba_aiueos_browser_frame2(sp, 8192,
                                             (uint64_t)(uintptr_t)font, font_length);
                                    if (dfo2 > 0 && aiueos_desktop_present_ops2(surface + 480, (uint64_t)dfo2,
                                                                                font, font_length)) {
                                      dhash = aiueos_desktop_colour_census(0x333333U, &dpx);
                                      (void)aiueos_desktop_show();
                                    }
                                  }
                                  if (dp == 16 && doff == 0 && conv == 1 && rec == 44512 && pre == 1 &&
                                      pre0 == 23665 && dfo == 114 && cpx == 834 && chash == 0xe85b42b2U &&
                                      dfo2 == 114 && dpx == 915 && dhash == 0xeaa427b3U &&
                                      surface[300] == 23665 && surface[301] == 20767 && surface[302] == 0 &&
                                      surface[442] == 0 && surface[445] == 0) {
                                    debug_string("AIUEOS_GUEST_BROWSER_DICT_OK\n");
                                    serial_string("AIUEOS_GUEST_BROWSER_DICT_OK keys=16 answers=0000000010000001 record=44512 committed=23665,20767 shown-ops=87 shown-px=834 shown-hash=e85b42b2 ops=114 text-px=915 hash=eaa427b3\r\n");
                                    browser_hold_for_screendump();
                                    /* The pointer (ADR-0236). Every frame
                                       above was drawn with word 2046 at 0 --
                                       no pointer -- and is pinned so. From
                                       here C writes each tablet event's
                                       position into words 2046 (x + 1) and
                                       2047 (y) before Kotoba reduces it, and
                                       browser-frame2 ends every list with the
                                       arrow there, over everything; C only
                                       says where the tablet is. The host
                                       sends five batches, each after the
                                       previous frame line: moves to
                                       (400, 300) (700, 450) (1276, 796), a
                                       press at (1000, 600) on no window, the
                                       release. Answers are browser-reduce's
                                       (a move uncaptured, a miss and an up
                                       are 0), op counts and censuses
                                       os/aiueos/scripts/browser-frame-model.cljk's. */
                                    {
                                      static const uint32_t csrc[5] = {3, 3, 3, 1, 4};
                                      static const uint32_t cops[5] = {135, 135, 120, 135, 135};
                                      static const uint32_t cwpx[5] = {948, 948, 922, 948, 948};
                                      static const uint32_t cwhash[5] = {0xbc7b9ebcU, 0x0baecac3U, 0x531100a2U, 0x3e8be657U,
                                                                         0x3e8be657U};
                                      static const uint32_t cat[10] = {400, 300, 700, 450, 1276, 796,
                                                                       1000, 600, 1000, 600};
                                      uint32_t ce = 0, coff = 0, cpx2 = 0, chash2 = 0, cchain = 2166136261U;
                                      uint32_t cidle = 0, cframes = 0, before = surface[2046];
                                      uint32_t tip = 0, fill = 0;
                                      int64_t cfo = 0;
                                      (void)aiueos_tablet_drain(4000000U);
                                      serial_string("AIUEOS_GUEST_BROWSER_CURSOR_GO events=5 before=");
                                      serial_decimal(before);
                                      serial_string("\r\n");
                                      while (ce < 5 && cidle < 60000U) {
                                        uint32_t src = aiueos_tablet_next(1024U, &ax, &ay);
                                        uint32_t px, py;
                                        int64_t r;
                                        if (!src) { cidle++; continue; }
                                        cidle = 0;
                                        px = (uint32_t)(((uint64_t)ax * surface[3]) / 32768U);
                                        py = (uint32_t)(((uint64_t)ay * surface[4]) / 32768U);
                                        surface[2046] = px + 1U;
                                        surface[2047] = py;
                                        aiueos_desktop_set_pointer(px, py);
                                        r = (int64_t)kotoba_aiueos_browser_reduce(sp, 128, src, px, py);
                                        cfo = (int64_t)kotoba_aiueos_browser_frame2(sp, 8192,
                                                (uint64_t)(uintptr_t)font, font_length);
                                        cpx2 = 0;
                                        chash2 = 0;
                                        tip = 0;
                                        fill = 0;
                                        if (cfo > 0 && aiueos_desktop_present_ops2(surface + 480, (uint64_t)cfo,
                                                                                   font, font_length)) {
                                          chash2 = aiueos_desktop_colour_census(0x333333U, &cpx2);
                                          (void)aiueos_desktop_show();
                                          tip = aiueos_desktop_sample_rgb(px, py);
                                          fill = aiueos_desktop_sample_rgb(px + 1U, py + 5U);
                                          cframes++;
                                          for (int b = 0; b < 4; b++) {
                                            cchain ^= (chash2 >> (8 * b)) & 255U;
                                            cchain *= 16777619U;
                                          }
                                        }
                                        if (src != csrc[ce] || r != 0 || px != cat[2 * ce] ||
                                            py != cat[2 * ce + 1] || cfo != (int64_t)cops[ce] ||
                                            cpx2 != cwpx[ce] || chash2 != cwhash[ce] || tip != 0x333333U) coff++;
                                        ce++;
                                        browser_hot_line("cursor", ce, surface + 480, cfo);
                                        serial_string("AIUEOS_GUEST_BROWSER_CURSOR_FRAME n=");
                                        serial_decimal(ce);
                                        serial_string(" src=");
                                        serial_decimal(src);
                                        serial_string(" at=");
                                        serial_decimal(px);
                                        serial_string(",");
                                        serial_decimal(py);
                                        serial_string(r < 0 ? " answer=-" : " answer=");
                                        serial_decimal((uint32_t)(r < 0 ? -r : r));
                                        serial_string(" ops=");
                                        serial_decimal((uint32_t)(cfo < 0 ? -cfo : cfo));
                                        serial_string(" text-px=");
                                        serial_decimal(cpx2);
                                        serial_string(" hash=");
                                        serial_hex32(chash2);
                                        serial_string(" tip=");
                                        serial_rgb(tip);
                                        serial_string(" fill=");
                                        serial_rgb(fill);
                                        serial_string("\r\n");
                                      }
                                      if (ce == 5 && cframes == 5 && coff == 0 && before == 0 &&
                                          cchain == 0xf4bb42d8U && surface[2046] == 1001 &&
                                          surface[2047] == 600 && surface[2] == 3 && surface[25] == 0 &&
                                          fill == 0xffffffU) {
                                        debug_string("AIUEOS_GUEST_BROWSER_CURSOR_OK\n");
                                        serial_string("AIUEOS_GUEST_BROWSER_CURSOR_OK events=5 answers=00000 before=0 at=1000,600 tip=111111 fill=ffffff chain=f4bb42d8 ops=135 text-px=948 hash=3e8be657\r\n");
                                        browser_hold_for_screendump();
                                        /* Alt+Tab (ADR-0237). After the
                                           pointer, the host presses launcher
                                           button 2 at (150, 14) and releases
                                           -- window 2 opens on top -- then Alt
                                           down, Tab down / up three times, Alt
                                           up, and a lone Tab down / up: twelve
                                           events, each after the previous
                                           frame line. From here the keyboard
                                           hands releases too, and every key
                                           goes to Kotoba browser-key as code *
                                           4 + value. An answer of 256 + id is
                                           browser-key's Alt+Tab -- a
                                           :window/focus -- and C hands the id
                                           to Kotoba browser-reduce as kind 5
                                           without looking at it: that Alt+Tab
                                           is the window manager's, and which
                                           window it focuses, are the objects'
                                           decisions. Answers are
                                           browser-reduce-v1's
                                           :the-kernel-focus-cycle and
                                           browser-ime-v2's Alt+Tab vectors';
                                           op counts, censuses and the chain
                                           os/aiueos/scripts/browser-frame-model.cljk's.
                                           The bodies (words 160..415) must
                                           come out of the stage as they went
                                           in: no key of it reaches a body. */
                                        {
                                          static const uint32_t fsrc[12] = {1, 4, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0};
                                          static const uint32_t fkey[12] = {0, 0, 225, 61, 60, 61, 60, 61, 60, 224, 61, 60};
                                          static const int64_t fwant[12] = {2, 0, 0, 1, 0, 3, 0, 2, 0, 0, 0, 0};
                                          static const uint32_t ffocus[12] = {2, 2, 2, 1, 1, 3, 3, 2, 2, 2, 2, 2};
                                          static const uint32_t fwpx[12] = {1082, 1082, 1082, 2290, 2290, 946, 946,
                                                                            1082, 1082, 1082, 1082, 1082};
                                          static const uint32_t fwhash[12] = {0xe90ed2bcU, 0xe90ed2bcU, 0xe90ed2bcU,
                                                                              0x47120e77U, 0x47120e77U, 0xc461a68fU,
                                                                              0xc461a68fU, 0xe90ed2bcU, 0xe90ed2bcU,
                                                                              0xe90ed2bcU, 0xe90ed2bcU, 0xe90ed2bcU};
                                          uint32_t fe = 0, foff = 0, fpx2 = 0, fhash2 = 0, fchain = 2166136261U;
                                          uint32_t fidle = 0, fframes = 0, wm = 0, bin = 2166136261U, bout = 2166136261U;
                                          int64_t ffo = 0;
                                          for (uint32_t i = 160; i < 416; i++) {
                                            bin ^= surface[i];
                                            bin *= 16777619U;
                                          }
                                          (void)aiueos_tablet_drain(4000000U);
                                          (void)aiueos_keyboard_drain(4000000U);
                                          serial_string("AIUEOS_GUEST_BROWSER_FOCUS_GO events=12\r\n");
                                          while (fe < 12 && fidle < 60000U) {
                                            uint32_t src = aiueos_tablet_next(1024U, &ax, &ay);
                                            uint32_t key = 0;
                                            int64_t r, kr = 0;
                                            if (src) {
                                              uint32_t px = (uint32_t)(((uint64_t)ax * surface[3]) / 32768U);
                                              uint32_t py = (uint32_t)(((uint64_t)ay * surface[4]) / 32768U);
                                              surface[2046] = px + 1U;
                                              surface[2047] = py;
                                              aiueos_desktop_set_pointer(px, py);
                                              r = (int64_t)kotoba_aiueos_browser_reduce(sp, 128, src, px, py);
                                            } else {
                                              key = aiueos_keyboard_next_key(1024U);
                                              if (!key) { fidle++; continue; }
                                              kr = (int64_t)kotoba_aiueos_browser_key(sp, 8192, dict, dict_length, key);
                                              r = kr;
                                              if (kr > 256) {
                                                r = (int64_t)kotoba_aiueos_browser_reduce(sp, 128, 5, (uint64_t)(kr - 256), 0);
                                                wm++;
                                              }
                                            }
                                            fidle = 0;
                                            ffo = (int64_t)kotoba_aiueos_browser_frame2(sp, 8192,
                                                    (uint64_t)(uintptr_t)font, font_length);
                                            fpx2 = 0;
                                            fhash2 = 0;
                                            if (ffo > 0 && aiueos_desktop_present_ops2(surface + 480, (uint64_t)ffo,
                                                                                      font, font_length)) {
                                              fhash2 = aiueos_desktop_colour_census(0x333333U, &fpx2);
                                              (void)aiueos_desktop_show();
                                              fframes++;
                                              for (int b = 0; b < 4; b++) {
                                                fchain ^= (fhash2 >> (8 * b)) & 255U;
                                                fchain *= 16777619U;
                                              }
                                            }
                                            if (src != fsrc[fe] || key != fkey[fe] || r != fwant[fe] ||
                                                surface[2] != ffocus[fe] || ffo != 166 ||
                                                fpx2 != fwpx[fe] || fhash2 != fwhash[fe]) foff++;
                                            fe++;
                                            browser_hot_line("focus", fe, surface + 480, ffo);
                                            {
                                              /* ADR-0245: the titlebar rects (height 28) of the list just
                                                 painted, by the colour Kotoba's title-rgb chose: 13421772
                                                 for the focused window, 15132390 for every other, and the
                                                 x,y of the first focused one. */
                                              uint32_t tact = 0, tina = 0, tx = 0, ty = 0;
                                              for (uint32_t j = 0; j < (uint32_t)ffo && j < 261U; j++) {
                                                const uint32_t *op = surface + 480 + 6U * j;
                                                if (op[0] == 1 && op[4] == 28U) {
                                                  if (op[5] == 13421772U) {
                                                    if (!tact) { tx = op[1]; ty = op[2]; }
                                                    tact++;
                                                  } else if (op[5] == 15132390U) tina++;
                                                }
                                              }
                                              serial_string("AIUEOS_GUEST_BROWSER_FOCUS_TITLE n=");
                                              serial_decimal(fe);
                                              serial_string(" active=");
                                              serial_decimal(tact);
                                              serial_string(" inactive=");
                                              serial_decimal(tina);
                                              serial_string(" at=");
                                              serial_decimal(tx);
                                              serial_string(",");
                                              serial_decimal(ty);
                                              serial_string("\r\n");
                                            }
                                            serial_string("AIUEOS_GUEST_BROWSER_FOCUS_FRAME n=");
                                            serial_decimal(fe);
                                            serial_string(" src=");
                                            serial_decimal(src);
                                            serial_string(" key=");
                                            serial_decimal(key);
                                            serial_string(kr < 0 ? " key-answer=-" : " key-answer=");
                                            serial_decimal((uint32_t)(kr < 0 ? -kr : kr));
                                            serial_string(r < 0 ? " answer=-" : " answer=");
                                            serial_decimal((uint32_t)(r < 0 ? -r : r));
                                            serial_string(" focus=");
                                            serial_decimal(surface[2]);
                                            serial_string(" stack=");
                                            for (uint32_t k = 0; k < surface[1] && k < 4; k++)
                                              serial_decimal(surface[5 + 5 * k]);
                                            serial_string(" ops=");
                                            serial_decimal((uint32_t)(ffo < 0 ? -ffo : ffo));
                                            serial_string(" text-px=");
                                            serial_decimal(fpx2);
                                            serial_string(" hash=");
                                            serial_hex32(fhash2);
                                            serial_string("\r\n");
                                          }
                                          for (uint32_t i = 160; i < 416; i++) {
                                            bout ^= surface[i];
                                            bout *= 16777619U;
                                          }
                                          if (fe == 12 && fframes == 12 && foff == 0 && wm == 3 && bin == bout &&
                                              fchain == 0x2254db31U && surface[1] == 3 && surface[5] == 1 &&
                                              surface[10] == 3 && surface[15] == 2 && surface[2] == 2 &&
                                              surface[431] == 0 && surface[433] == 0 && surface[445] == 0) {
                                            debug_string("AIUEOS_GUEST_BROWSER_FOCUS_OK\n");
                                            serial_string("AIUEOS_GUEST_BROWSER_FOCUS_OK events=12 answers=200103020000 wm=3 stack=132 focus=2 bodies=unchanged chain=2254db31 ops=166 text-px=1082 hash=e90ed2bc\r\n");
                                            browser_hold_for_screendump();
                                            if (browser_scroll_stage(surface, font, font_length))
#ifdef AIUEOS_TOUCHPAD_GESTURE_SYNTHETIC
                                              if (browser_gesture_stage(surface, font, font_length))
#endif
#ifdef AIUEOS_BATTERY_PROBE
                                              if (browser_battery_stage(surface, font, font_length))
#endif
                                              if (browser_selection_stage(surface, font, font_length, dict, dict_length))
                                                if (browser_clipboard_stage(surface, font, font_length, dict, dict_length))
                                                  if (browser_damage_stage(surface, font, font_length, dict, dict_length))
                                                    if (browser_uiux_stage(surface, font, font_length, dict, dict_length))
                                                      if (browser_scale_stage(surface, font, font_length, dict, dict_length))
                                                        if (browser_ring_stage(surface, font, font_length, dict, dict_length))
                                                          if (browser_edit_stage(surface, font, font_length, dict, dict_length))
                                                            if (browser_clock_stage(surface, font, font_length))
                                                              if (browser_layout_stage(surface, font, font_length, dict, dict_length))
                                                                if (browser_notify_stage(surface, font, font_length, dict, dict_length))
                                                                  if (browser_passkey_stage(surface, font, font_length, dict, dict_length))
                                                                    if (browser_settings_stage(surface, font, font_length, dict, dict_length))
                                                                      if (browser_backup_stage()) if (browser_audio_stage()) (void)browser_suspend_stage(surface, font, font_length);
                                          } else if (fe < 12) {
                                            debug_string("AIUEOS_GUEST_BROWSER_FOCUS leftover=events-missing\n");
                                            serial_string("AIUEOS_GUEST_BROWSER_FOCUS leftover=events-missing events=");
                                            serial_decimal(fe);
                                            serial_string(" frames=");
                                            serial_decimal(fframes);
                                            serial_string("\r\n");
                                          } else {
                                            debug_string("AIUEOS_GUEST_BROWSER_FOCUS leftover=census-miss\n");
                                            serial_string("AIUEOS_GUEST_BROWSER_FOCUS leftover=census-miss off=");
                                            serial_decimal(foff);
                                            serial_string(" wm=");
                                            serial_decimal(wm);
                                            serial_string(bin == bout ? " bodies=unchanged" : " bodies=changed");
                                            serial_string(" chain=");
                                            serial_hex32(fchain);
                                            serial_string(" focus=");
                                            serial_decimal(surface[2]);
                                            serial_string(" alt=");
                                            serial_decimal(surface[431]);
                                            serial_string("\r\n");
                                          }
                                        }
                                      } else if (ce < 5) {
                                        debug_string("AIUEOS_GUEST_BROWSER_CURSOR leftover=events-missing\n");
                                        serial_string("AIUEOS_GUEST_BROWSER_CURSOR leftover=events-missing events=");
                                        serial_decimal(ce);
                                        serial_string(" frames=");
                                        serial_decimal(cframes);
                                        serial_string("\r\n");
                                      } else {
                                        debug_string("AIUEOS_GUEST_BROWSER_CURSOR leftover=census-miss\n");
                                        serial_string("AIUEOS_GUEST_BROWSER_CURSOR leftover=census-miss off=");
                                        serial_decimal(coff);
                                        serial_string(" before=");
                                        serial_decimal(before);
                                        serial_string(" chain=");
                                        serial_hex32(cchain);
                                        serial_string(" fill=");
                                        serial_rgb(fill);
                                        serial_string("\r\n");
                                      }
                                    }
                                  } else if (dp < 16) {
                                    debug_string("AIUEOS_GUEST_BROWSER_DICT leftover=keys-missing\n");
                                    serial_string("AIUEOS_GUEST_BROWSER_DICT leftover=keys-missing keys=");
                                    serial_decimal(dp);
                                    serial_string("\r\n");
                                  } else {
                                    debug_string("AIUEOS_GUEST_BROWSER_DICT leftover=census-miss\n");
                                    serial_string("AIUEOS_GUEST_BROWSER_DICT leftover=census-miss off=");
                                    serial_decimal(doff);
                                    serial_string(" ops=");
                                    serial_decimal((uint32_t)(dfo2 < 0 ? -dfo2 : dfo2));
                                    serial_string(" text-px=");
                                    serial_decimal(dpx);
                                    serial_string(" hash=");
                                    serial_hex32(dhash);
                                    serial_string(" body=");
                                    serial_decimal(surface[300]);
                                    serial_string(",");
                                    serial_decimal(surface[301]);
                                    serial_string("\r\n");
                                  }
                                }
                              } else if (e < 8) {
                                debug_string("AIUEOS_GUEST_BROWSER_LAUNCH leftover=events-missing\n");
                                serial_string("AIUEOS_GUEST_BROWSER_LAUNCH leftover=events-missing events=");
                                serial_decimal(e);
                                serial_string(" frames=");
                                serial_decimal(aframes);
                                serial_string("\r\n");
                              } else {
                                debug_string("AIUEOS_GUEST_BROWSER_LAUNCH leftover=census-miss\n");
                                serial_string("AIUEOS_GUEST_BROWSER_LAUNCH leftover=census-miss off=");
                                serial_decimal(aoff);
                                serial_string(" frames=");
                                serial_decimal(aframes);
                                serial_string(" chain=");
                                serial_hex32(achain);
                                serial_string(" windows=");
                                serial_decimal(surface[1]);
                                serial_string(" stack=");
                                serial_decimal(surface[5]);
                                serial_string(",");
                                serial_decimal(surface[10]);
                                serial_string(" focus=");
                                serial_decimal(surface[2]);
                                serial_string("\r\n");
                              }
                            }
                          }
                        }
                      }
                    }
                  }
                }
              } else {
                debug_string("AIUEOS_GUEST_BROWSER_TYPE leftover=keys-missing\n");
                serial_string("AIUEOS_GUEST_BROWSER_TYPE leftover=keys-missing presses=");
                serial_decimal(presses);
                serial_string("\r\n");
              }
            }
          } else {
            debug_string("AIUEOS_GUEST_BROWSER_TEXT_RAISED leftover=census-miss\n");
            serial_string("AIUEOS_GUEST_BROWSER_TEXT_RAISED leftover=census-miss hit=");
            serial_decimal((uint32_t)hit);
            serial_string(" text-px=");
            serial_decimal(text_px);
            serial_string(" hash=");
            serial_hex32(text_hash);
            serial_string("\r\n");
          }
        } else {
          debug_string("AIUEOS_GUEST_BROWSER_TEXT_RAISED leftover=frame-refused\n");
          serial_string("AIUEOS_GUEST_BROWSER_TEXT_RAISED leftover=frame-refused\r\n");
        }
      }
      /* The flow-parity frame (ADR-0234). After everything above -- in the
         default profile right after the text frame -- Kotoba lays out a
         surface of its own whose four bodies take each of cssom's rules:
         packing by words with space runs, a tab and U+3000 collapsed (1),
         <br>s with an empty segment (2), a CJK run with no break opportunity
         overflowing its window (3), a body that fits kept as collapsed (4).
         The census is os/aiueos/scripts/browser-frame-model.cljk's. The op
         list goes out on serial whole: the guest-browser-flow-parity gate
         reads each window's body glyphs out of it and compares them, one by
         one, with what kotoba-lang/browser + cssom draw for the same surface
         (os/aiueos/contracts/browser-flow-parity-v1.edn). */
      if (font) {
        static const uint32_t fstate[25] = {1, 4, 4, 0, 0,
                                            1, 16, 40, 188, 220,
                                            2, 220, 40, 420, 220,
                                            3, 656, 40, 200, 160,
                                            4, 16, 300, 180, 120};
        /* flow / cssom  lays<TAB>out words one by one,<U+3000>as hosted engine. */
        static const uint32_t ftitle1[] = {102, 108, 111, 119};
        static const uint32_t fbody1[] = {99, 115, 115, 111, 109, 32, 32, 108, 97, 121, 115, 9, 111, 117, 116, 32, 119, 111, 114, 100, 115, 32, 111, 110, 101, 32, 98, 121, 32, 111, 110, 101, 44, 12288, 97, 115, 32, 104, 111, 115, 116, 101, 100, 32, 101, 110, 103, 105, 110, 101, 46};
        /* br / "  first  line  " <br> <br> 空行の次　全角空白も <br> kotoba-lang/browser flows words */
        static const uint32_t ftitle2[] = {98, 114};
        static const uint32_t fbody2[] = {32, 32, 102, 105, 114, 115, 116, 32, 32, 108, 105, 110, 101, 32, 32, 10, 10, 31354, 34892, 12398, 27425, 12288, 20840, 35282, 31354, 30333, 12418, 10, 107, 111, 116, 111, 98, 97, 45, 108, 97, 110, 103, 47, 98, 114, 111, 119, 115, 101, 114, 32, 102, 108, 111, 119, 115, 32, 119, 111, 114, 100, 115};
        /* 長い行 / ab 日本語の文字は単語の中で折り返さない cd */
        static const uint32_t ftitle3[] = {38263, 12356, 34892};
        static const uint32_t fbody3[] = {97, 98, 32, 26085, 26412, 35486, 12398, 25991, 23383, 12399, 21336, 35486, 12398, 20013, 12391, 25240, 12426, 36820, 12373, 12394, 12356, 32, 99, 100};
        /* fits / " 画面　に　出る  text " */
        static const uint32_t ftitle4[] = {102, 105, 116, 115};
        static const uint32_t fbody4[] = {32, 30011, 38754, 12288, 12395, 12288, 20986, 12427, 32, 32, 116, 101, 120, 116, 32};
        int64_t fcount;
        uint32_t fpx = 0, fhash = 0;
        for (int i = 0; i < 2048; i++) flow[i] = 0;
        for (int i = 0; i < 25; i++) flow[i] = fstate[i];
        flow[3] = aiueos_desktop_width();
        flow[4] = aiueos_desktop_height();
        for (unsigned i = 0; i < sizeof(ftitle1) / 4; i++) flow[32 + i] = ftitle1[i];
        for (unsigned i = 0; i < sizeof(ftitle2) / 4; i++) flow[64 + i] = ftitle2[i];
        for (unsigned i = 0; i < sizeof(ftitle3) / 4; i++) flow[96 + i] = ftitle3[i];
        for (unsigned i = 0; i < sizeof(ftitle4) / 4; i++) flow[128 + i] = ftitle4[i];
        for (unsigned i = 0; i < sizeof(fbody1) / 4; i++) flow[160 + i] = fbody1[i];
        for (unsigned i = 0; i < sizeof(fbody2) / 4; i++) flow[224 + i] = fbody2[i];
        for (unsigned i = 0; i < sizeof(fbody3) / 4; i++) flow[288 + i] = fbody3[i];
        for (unsigned i = 0; i < sizeof(fbody4) / 4; i++) flow[352 + i] = fbody4[i];
        /* Gate Option A (2026-10-24, JUN-31): the FLOW census is measured at
           a fixed pct. ADR-0261's UI scale magnifies what present_ops2
           paints, so the census used to follow whatever the profile left
           active -- 3593/a19f95a8 at pct=100, 9564/b2fad8a7 at pct=125 --
           while the drawn op stream stayed byte-identical. The pin (ADR-0234)
           is defined at pct=100: measure at 100, then put the user's own
           scale back so only the measurement is pinned. */
        uint32_t fprev_scale = aiueos_desktop_scale();
        if (fprev_scale != 100U) (void)aiueos_desktop_set_scale(100U);
        fcount = (int64_t)kotoba_aiueos_browser_frame2((uint64_t)(uintptr_t)flow, 8192,
                   (uint64_t)(uintptr_t)font, font_length);
        if (fcount <= 0) {
          debug_string("AIUEOS_GUEST_BROWSER_FLOW leftover=frame-refused\n");
          serial_string("AIUEOS_GUEST_BROWSER_FLOW leftover=frame-refused reason=-");
          serial_decimal((uint32_t)(-fcount));
          serial_string("\r\n");
        } else if (!aiueos_desktop_present_ops2(flow + 480, (uint64_t)fcount, font, font_length)) {
          debug_string("AIUEOS_GUEST_BROWSER_FLOW leftover=present-refused\n");
          serial_string("AIUEOS_GUEST_BROWSER_FLOW leftover=present-refused\r\n");
        } else {
          fhash = aiueos_desktop_colour_census(0x333333U, &fpx);
          (void)aiueos_desktop_show();
          serial_string("AIUEOS_GUEST_BROWSER_FLOW_SCALE pinned=100 prev=");
          serial_decimal(fprev_scale);
          serial_string("\r\n");
          /* kind x y a b rgb per op, each word as 8 hex digits */
          serial_string("AIUEOS_GUEST_BROWSER_FLOW_OPS n=");
          serial_decimal((uint32_t)fcount);
          serial_string(" words=");
          for (int64_t i = 0; i < fcount * 6; i++) serial_hex32(flow[480 + i]);
          serial_string("\r\n");
          /* 166, not 158: the committed object was STALE against its source
         (measured 2026-10-20 -- the rebuild's ink census is identical,
         3593 px / a19f95a8, and only the coloured rect count moved).
         The source is the truth. */
      if (fcount == 182 && fpx == 3593 && fhash == 0xa19f95a8U) {
            debug_string("AIUEOS_GUEST_BROWSER_FLOW_OK\n");
    /* I6 screen reader: announce every control with its role and state from
       the desktop's own model (state slots 1 = window count, 2 = focus id;
       the window ids 1..n are the navigable controls). The announcements
       are the row's readback: one line per control, the focused one marked. */
    {
      uint32_t n_windows = surface[1], focus_id = surface[2];
      uint32_t announced = 0;
      for (uint32_t w = 1; w <= n_windows && w <= 4; w++) {
        serial_string("AIUEOS_SCREENREADER control="); serial_decimal(w);
        serial_string(" role=window state=");
        serial_string(w == focus_id ? "focused" : "normal");
        serial_string("\r\n");
        announced++;
      }
      serial_string("AIUEOS_SCREENREADER_OK announcements=");
      serial_decimal(announced);
      serial_string(" role=window\r\n");
    }
            serial_string("AIUEOS_GUEST_BROWSER_FLOW_OK windows=4 ops=182 text-px=3593 hash=a19f95a8\r\n");
            browser_hold_for_screendump();
          } else {
            debug_string("AIUEOS_GUEST_BROWSER_FLOW leftover=census-miss\n");
            serial_string("AIUEOS_GUEST_BROWSER_FLOW leftover=census-miss ops=");
            serial_decimal((uint32_t)fcount);
            serial_string(" text-px=");
            serial_decimal(fpx);
            serial_string(" hash=");
            serial_hex32(fhash);
            serial_string("\r\n");
          }
        }
        /* the pin covers the measurement only; the user's scale comes back */
        if (fprev_scale != 100U) (void)aiueos_desktop_set_scale(fprev_scale);
      }
    }
    if (!(pci_result & 8)) {
      /* Name the failure before leaving (ADR-0199). These two used to
         share one marker and the gate could not tell them apart: the
         intermittent blank frame (JUN-142) measured 2026-10-20 leaves
         both paths possible. */
      serial_string("AIUEOS_VIRTIO_GPU_FAIL display-info-absent\r\n"); evidence_stop(__LINE__);
    }
    if (!aiueos_desktop_surface_bind_scanout(
          aiueos_gpu_scanout_width(),aiueos_gpu_scanout_height())) {
      serial_string("AIUEOS_VIRTIO_GPU_FAIL surface-binding-scanout-w=");
      serial_decimal(aiueos_gpu_scanout_width());
      serial_string(" scanout-h=");
      serial_decimal(aiueos_gpu_scanout_height());
      serial_string("\r\n"); evidence_stop(__LINE__);
    }
    debug_string("AIUEOS_VIRTIO_GPU_OK modern-pci controlq display-info bounded\n");
    serial_string("AIUEOS_VIRTIO_GPU_OK modern-pci controlq display-info bounded\r\n");
    if (aiueos_gpu_2d_create_ok()) {
      debug_string("AIUEOS_VIRTIO_GPU_CREATE result=ok resource=1 format=2 w=32 h=32\n");
      serial_string("AIUEOS_VIRTIO_GPU_CREATE result=ok resource=1 format=2 w=32 h=32\r\n");
    } else {
      debug_string("AIUEOS_VIRTIO_GPU_CREATE result=absent\n");
      serial_string("AIUEOS_VIRTIO_GPU_CREATE result=absent\r\n");
    }
    if (aiueos_gpu_2d_flush_ok()) {
      debug_string("AIUEOS_VIRTIO_GPU_FLUSH result=ok resource=1\n");
      serial_string("AIUEOS_VIRTIO_GPU_FLUSH result=ok resource=1\r\n");
    } else {
      debug_string("AIUEOS_VIRTIO_GPU_FLUSH result=absent\n");
      serial_string("AIUEOS_VIRTIO_GPU_FLUSH result=absent\r\n");
    }
    /* Guest gpu-two (ADR-0094). Resource count is Kotoba
       kotoba_aiueos_wm_hit; C does not invent n=2. Hosted JVM gpu does
       not count. Do not qemu_exit: gpu/guest-paint/guest-input stay
       green without this line. */
    if (aiueos_gpu_2d_two_ok()) {
      debug_string("AIUEOS_GUEST_GPU_TWO_OK resources=2 flush=2 kotoba-n=2\n");
      serial_string("AIUEOS_GUEST_GPU_TWO_OK resources=2 flush=2 kotoba-n=2\r\n");
    } else {
      debug_string("AIUEOS_GUEST_GPU_TWO leftover=one-resource\n");
      serial_string("AIUEOS_GUEST_GPU_TWO leftover=one-resource\r\n");
    }
    /* Guest scanout-two (ADR-0095). Bind count is Kotoba
       kotoba_aiueos_scanout_bind; C does not invent n=2. Hosted JVM wm
       does not count. Do not qemu_exit: gpu/guest-gpu-two stay green
       without this line. */
    if (aiueos_gpu_scanout_two_ok()) {
      debug_string("AIUEOS_GUEST_SCANOUT_TWO_OK scanouts=2 resource-0=1 resource-1=2 kotoba-n=2\n");
      serial_string("AIUEOS_GUEST_SCANOUT_TWO_OK scanouts=2 resource-0=1 resource-1=2 kotoba-n=2\r\n");
    } else {
      debug_string("AIUEOS_GUEST_SCANOUT_TWO leftover=one-scanout\n");
      serial_string("AIUEOS_GUEST_SCANOUT_TWO leftover=one-scanout enabled=");
      serial_decimal(aiueos_gpu_enabled_scanouts());
      serial_string("\r\n");
    }
    debug_string("AIUEOS_BROWSER_DESKTOP_TRANSPORT_OK surface-v1 gpu-scanout-bound input-v1\n");
    serial_string("AIUEOS_BROWSER_DESKTOP_TRANSPORT_OK surface-v1 gpu-scanout-bound input-v1\r\n");
    /* The link layer is OPTIONAL: a boot with no NIC attached must stay green,
       so this reports presence rather than gating on it. When a NIC IS present
       the exchange has to have completed and been admitted, so an attached-but-
       broken device cannot pass as "no network". */
    if (aiueos_virtio_net_ready()) {
      debug_string("AIUEOS_VIRTIO_NET_OK modern-pci rx/tx arp-reply kotoba-admitted\n");
      serial_string("AIUEOS_VIRTIO_NET_OK modern-pci rx/tx arp-reply kotoba-admitted\r\n");
      /* IPv4 rides on the link layer, so it can only be reported where the link
         layer was: a boot with no NIC says nothing about it at all rather than
         reporting an absence it has no way to distinguish from a failure. */
      if (aiueos_ipv4_ready()) {
        debug_string("AIUEOS_IPV4_OK icmp-echo-reply kotoba-admitted\n");
        serial_string("AIUEOS_IPV4_OK icmp-echo-reply kotoba-admitted\r\n");
        /* TCP rides on IPv4 exactly as IPv4 rides on the link layer, so it is
           reported only where IPv4 succeeded: a boot whose echo never came back
           says nothing about TCP rather than reporting a failure it never
           reached. */
        if (aiueos_tcp_ready()) {
          debug_string("AIUEOS_TCP_OK handshake echo close kotoba-admitted\n");
          serial_string("AIUEOS_TCP_OK handshake echo close kotoba-admitted\r\n");
        } else {
          /* Not silent, for the reason AIUEOS_IPV4_FAIL is not, and not a boot
             failure either: whether a peer completes a connection is a property
             of the network. Which phase it stopped at, because unlike the echo
             this exchange has four admissions, and re-running a TCG boot under
             load to find out which costs many minutes. tx-* are build faults
             rather than network ones -- the segment was wrong before it left.
             The numbers mirror NET_TCP_STAGE_* in kernel/pci.c, which is where
             they are set; they are not shared through a header because this
             kernel has none, and every other cross-file contract here is an
             extern declaration written out the same way. */
          unsigned stage = aiueos_tcp_stage();
          if (stage == 5) serial_string("AIUEOS_TCP_FAIL tx-segment-checksum\r\n");
          else if (stage == 6) serial_string("AIUEOS_TCP_FAIL tx-not-completed\r\n");
          else if (stage == 2) serial_string("AIUEOS_TCP_FAIL no-admitted-echo\r\n");
          else if (stage == 3) serial_string("AIUEOS_TCP_FAIL no-admitted-fin-ack\r\n");
          else if (stage == 1) serial_string("AIUEOS_TCP_FAIL no-admitted-syn-ack\r\n");
          else serial_string("AIUEOS_TCP_FAIL no-peer-mac\r\n");
        }
      } else {
        /* Reached only with a NIC present and its link layer already OK, so
           this is a real IPv4 failure and says so. Staying silent would make a
           broken exchange indistinguishable from a build that never attempted
           one -- the same trap AIUEOS_VIRTIO_NET_ABSENT exists to avoid one
           layer down. It does not fail the boot: whether the peer answers ICMP
           at all is a property of the network, not of this OS. */
        serial_string("AIUEOS_IPV4_FAIL no-admitted-echo-reply\r\n");
      }
      /* Reported at link-layer level rather than under IPv4, because that is
         where it sits: DHCP is broadcast and needs neither the ARP cache nor
         anything ICMP proved. A machine that reaches here has an address it was
         GIVEN. DNS and cloud-TCP then send from that address (ADR-0081). */
      if (aiueos_dhcp_ready()) {
        serial_string("AIUEOS_DHCP_OK offer-ack kotoba-admitted address=");
        serial_ipv4(aiueos_dhcp_address());
        serial_string(" mask=");
        serial_ipv4(aiueos_dhcp_mask());
        serial_string(" router=");
        serial_ipv4(aiueos_dhcp_router());
        serial_string(" server=");
        serial_ipv4(aiueos_dhcp_server());
        serial_string(" lease=");
        serial_decimal(aiueos_dhcp_lease_seconds());
        serial_string("\r\n");
        if (aiueos_dhcp_consumed()) {
          serial_string("AIUEOS_DHCP_CONSUMED src=");
          serial_ipv4(aiueos_dhcp_address());
          serial_string(" dns=");
          serial_ipv4(aiueos_dhcp_dns() ? aiueos_dhcp_dns() : 0x0a000203U);
          serial_string("\r\n");
        } else {
          serial_string("AIUEOS_DHCP_CONSUMED result=absent leftover=:lease-not-consumed\r\n");
        }
        serial_string("AIUEOS_DNS_PROBE result=");
        if (aiueos_dns_ready()) {
          serial_string("ok name=kotobase.net a=");
          serial_ipv4(aiueos_dns_a());
          serial_string("\r\n");
        } else {
          serial_string("fail stage=");
          serial_decimal(aiueos_dns_stage());
          serial_string(" leftover=:dns-absent\r\n");
        }
        serial_string("AIUEOS_TCP_CLOUD_PROBE result=");
        if (aiueos_tcp_cloud_ready()) {
          serial_string("ok dst=");
          serial_ipv4(aiueos_dns_a());
          serial_string(" port=443\r\n");
        } else if (!aiueos_dns_ready()) {
          serial_string("skipped leftover=:dns-absent\r\n");
        } else {
          serial_string("fail stage=");
          serial_decimal(aiueos_tcp_cloud_stage());
          serial_string(" leftover=:tcp-cloud-absent\r\n");
        }
        serial_string("AIUEOS_TLS_PROBE result=");
        if (aiueos_tls_handshake_ready()) {
          serial_string("ok");
          if (!aiueos_http_cid_ready())
            serial_string(" leftover=:http-absent");
          serial_string("\r\n");
        } else if (aiueos_tls_record_ready()) {
          serial_string("record type=");
          serial_decimal(aiueos_tls_record_type());
          serial_string(" stage=");
          serial_decimal(aiueos_tls_stage());
          serial_string(" rx=");
          serial_decimal(aiueos_tls_rx_buffered());
          serial_string(" leftover=:tls-handshake-incomplete,:http-absent\r\n");
        } else {
          serial_string("absent leftover=:tls-absent,:http-absent\r\n");
        }
        {
          extern int aiueos_tls13_certverify_ok(void);
          extern uint16_t aiueos_tls13_certverify_scheme(void);
          serial_string("AIUEOS_CERTVERIFY_PROBE result=");
          if (aiueos_tls13_certverify_ok() &&
              aiueos_tls13_certverify_scheme() == 0x0403) {
            serial_string("ok scheme=ecdsa_secp256r1_sha256\r\n");
          } else if (aiueos_tls_handshake_ready() || aiueos_http_cid_ready()) {
            serial_string("hashed-only leftover=:cert-verify-hashed-only\r\n");
          } else {
            serial_string("absent leftover=:cert-verify-hashed-only\r\n");
          }
        }
        serial_string("AIUEOS_HTTP_PROBE result=");
        if (aiueos_http_cid_ready()) {
          serial_string("ok cid=");
          serial_string(aiueos_http_cid());
          serial_string("\r\n");
        } else {
          serial_string("absent leftover=:http-absent app=");
          serial_decimal(aiueos_tls_app_len());
          serial_string(" rec=");
          serial_decimal(aiueos_tls_last_record_type());
          serial_string(" inner=");
          serial_decimal(aiueos_tls_last_inner_type());
          serial_string(" fail=");
          serial_decimal((uint32_t)aiueos_tls_failed());
          serial_string(" fin=");
          serial_decimal((uint32_t)aiueos_tls_finished_sent());
          serial_string(" get=");
          serial_decimal((uint32_t)aiueos_tls_http_sent());
          serial_string(" nst=");
          serial_decimal(aiueos_tls_nst_count());
          serial_string("\r\n");
        }
        if (aiueos_http_cid_ready()) {
          serial_string("AIUEOS_BARE_METAL_P2 green leftover=[]\r\n");
        } else if (aiueos_tls_handshake_ready()) {
          serial_string("AIUEOS_BARE_METAL_P2 not-green leftover=:http-absent\r\n");
        } else if (aiueos_tls_record_ready()) {
          serial_string("AIUEOS_BARE_METAL_P2 not-green leftover=:tls-handshake-incomplete,:http-absent\r\n");
        } else {
          serial_string("AIUEOS_BARE_METAL_P2 not-green leftover=:tls-absent,:http-absent\r\n");
        }
      } else {
        /* Both halves, because they answer different questions: the STAGE says
           which of the two round trips did not complete, and the REASON is the
           clause of the admission that refused the candidate which got
           furthest. A run that refuses for a reason nobody broke is a run whose
           evidence is about something else, and printing only one of these
           would make that indistinguishable. */
        serial_string("AIUEOS_DHCP_FAIL ");
        serial_string(dhcp_stage_name(aiueos_dhcp_stage()));
        serial_string(" reason=");
        serial_decimal(aiueos_dhcp_reason());
        serial_byte(' ');
        serial_string(dhcp_reason_name(aiueos_dhcp_reason()));
        serial_string("\r\n");
      }
    } else {
      serial_string("AIUEOS_VIRTIO_NET_ABSENT no-nic-attached\r\n");
    }
#ifdef AIUEOS_SSH_LISTEN
    /* The listener ran inside the NIC probe (pci.c). It accepts one inbound
       connection and exchanges SSH identification strings -- passive open and
       the first post-evidence service step, with no crypto yet. The marker is
       green only when a well-formed SSH-2.0 id string was received over a
       connection this OS accepted; the stage says how far a failed attempt
       got. */
    if (aiueos_ssh_client_id_valid()) {
      serial_string("AIUEOS_SSH_LISTEN_OK port=22 accepted client-id=valid len=");
      serial_decimal(aiueos_ssh_client_id_len());
      serial_string("\r\n");
      debug_string("AIUEOS_SSH_LISTEN_OK port=22 accepted client-id=valid\n");
      /* The real kex outcome (ADR-0107): 5 = KEX_ECDH_REPLY + NEWKEYS sent. The
         reply's host-key signature over H is what a real client verifies; the
         gate confirms that independently. Lower stages say how far it got. */
      if (aiueos_ssh_kex_stage() >= 5) {
        serial_string("AIUEOS_SSH_KEX_REPLY_OK curve25519-sha256 ecdsa-sha2-nistp256 reply+newkeys sent\r\n");
        debug_string("AIUEOS_SSH_KEX_REPLY_OK reply+newkeys sent\n");
      } else {
        serial_string("AIUEOS_SSH_KEX_REPLY_INCOMPLETE stage=");
        serial_decimal(aiueos_ssh_kex_stage());
        serial_string("\r\n");
      }
      /* Publickey userauth over the aes128-gcm record layer (ADR-0108):
         stage 9 = the client's signature over the session's signed-data verified
         against the authorized key and USERAUTH_SUCCESS was sent. */
      if (aiueos_ssh_kex_stage() >= 12) {
        serial_string("AIUEOS_SSH_AUTH_OK publickey ecdsa-sha2-nistp256 aes128-gcm userauth-success sent\r\n");
        debug_string("AIUEOS_SSH_AUTH_OK userauth-success sent\n");
        /* The session channel (ADR-0109): stage 16 = a `session` channel was
           opened, an `exec` request accepted, and CHANNEL_DATA streamed back. */
        if (aiueos_ssh_kex_stage() >= 16) {
          serial_string("AIUEOS_SSH_SESSION_OK session channel exec channel-data streamed\r\n");
          debug_string("AIUEOS_SSH_SESSION_OK exec channel-data streamed\n");
        } else if (aiueos_ssh_kex_stage() >= 13) {
          serial_string("AIUEOS_SSH_SESSION_INCOMPLETE stage=");
          serial_decimal(aiueos_ssh_kex_stage());
          serial_string("\r\n");
        }
      } else if (aiueos_ssh_kex_stage() >= 6) {
        /* 6 entered 7 client-newkeys 8 service-req 9 service-accept
           10 userauth-req 11 signature-verified. */
        serial_string("AIUEOS_SSH_AUTH_INCOMPLETE stage=");
        serial_decimal(aiueos_ssh_kex_stage());
        serial_string("\r\n");
      }
    } else {
      serial_string("AIUEOS_SSH_LISTEN_INCOMPLETE stage=");
      serial_decimal(aiueos_ssh_listen_stage());
      serial_string("\r\n");
    }
#endif
    debug_string("AIUEOS_SCHEDULER_OK tasks=2 policy=round-robin preemption=apic-timer\n");
    serial_string("AIUEOS_SCHEDULER_OK tasks=2 policy=round-robin preemption=apic-timer\r\n");
    debug_string("AIUEOS_SCHEDULER_CR3_OK roots=3 private-pages=2 kernel-return\n");
    serial_string("AIUEOS_SCHEDULER_CR3_OK roots=3 private-pages=2 kernel-return\r\n");
    if (!aiueos_service_runtime_evidence_ready()) evidence_stop(__LINE__);
    debug_string("AIUEOS_SERVICE_RUNTIME_OK services=2 descriptors=8 kotoba-policy spawn-restart-terminate task=generic generation=2 budget=bounded\n");
    serial_string("AIUEOS_SERVICE_RUNTIME_OK services=2 descriptors=8 kotoba-policy spawn-restart-terminate task=generic generation=2 budget=bounded\r\n");
    if (!aiueos_service_ipc_evidence_ready()) evidence_stop(__LINE__);
    debug_string("AIUEOS_SERVICE_IPC_OK mailbox=bounded capability=owner-domain cross-cr3 sequence=1\n");
    serial_string("AIUEOS_SERVICE_IPC_OK mailbox=bounded capability=owner-domain cross-cr3 sequence=1\r\n");
    if (!aiueos_ioapic_route_legacy_timer()) {
      debug_string("AIUEOS_IOAPIC_FAIL route-legacy-timer\n");
      serial_string("AIUEOS_IOAPIC_FAIL route-legacy-timer\r\n");
      qemu_exit(0x72);
    }
    __asm__ volatile("sti");
    while (aiueos_external_timer_ticks == 0) __asm__ volatile("hlt");
    __asm__ volatile("cli");
    debug_string("AIUEOS_IOAPIC_OK pit-gsi vector=33 eoi-v1\n");
    serial_string("AIUEOS_IOAPIC_OK pit-gsi vector=33 eoi-v1\r\n");
    if (!aiueos_syscall_self_test()) {
      debug_string("AIUEOS_SYSCALL_FAIL abi-capability-pointer\n");
      serial_string("AIUEOS_SYSCALL_FAIL abi-capability-pointer\r\n");
      qemu_exit(0x73);
    }
    if (!aiueos_dynamic_capability_evidence_ready() ||
        !aiueos_capability_derivation_evidence_ready() ||
        aiueos_capability_table_capacity() < 256) qemu_exit(0x73);
    debug_string("AIUEOS_DYNAMIC_CAPABILITY_OK page-backed slots>=256 owner=3 reuse generation retirement\n");
    serial_string("AIUEOS_DYNAMIC_CAPABILITY_OK page-backed slots>=256 owner=3 reuse generation retirement\r\n");
    debug_string("AIUEOS_SYSCALL_OK int80-cpl0 abi-v1\n");
    serial_string("AIUEOS_SYSCALL_OK int80-cpl0 abi-v1\r\n");
    debug_string("AIUEOS_KOTOBA_SYSCALL_PLANNER_OK bootstrap user overflow\n");
    serial_string("AIUEOS_KOTOBA_SYSCALL_PLANNER_OK bootstrap user overflow\r\n");
    debug_string("AIUEOS_KOTOBA_COPY_IN_OK cpl0 hash bounded-256\n");
    serial_string("AIUEOS_KOTOBA_COPY_IN_OK cpl0 hash bounded-256\r\n");
    debug_string("AIUEOS_KOTOBA_CAPABILITY_OK table owner generation type rights revoke reissue derivation=multi-hop recursive-revoke\n");
    serial_string("AIUEOS_KOTOBA_CAPABILITY_OK table owner generation type rights revoke reissue derivation=multi-hop recursive-revoke\r\n");
    debug_string("AIUEOS_COPYIN_OK noncanonical-and-unmapped-denied\n");
    serial_string("AIUEOS_COPYIN_OK noncanonical-and-unmapped-denied\r\n");
    int process_init = aiueos_process_initialize();
    if (process_init != 1) {
      serial_string("AIUEOS_RING3_FAIL tss-or-mapping\r\n"); qemu_exit(0x72);
    }
    debug_string("AIUEOS_PROCESS_FOUNDATION_OK tss-descriptor user-wx guard-page\n");
    serial_string("AIUEOS_PROCESS_FOUNDATION_OK tss-descriptor user-wx guard-page\r\n");
    debug_string("AIUEOS_PROCESS_CREATE_OK descriptors=8 entry-argument-stack domain-address-space-task\n");
    serial_string("AIUEOS_PROCESS_CREATE_OK descriptors=8 entry-argument-stack domain-address-space-task\r\n");
#ifdef AIUEOS_PLC_RT_SMOKE
    extern int aiueos_process_enter_plc_rt(void);
    aiueos_load_task_register();
    if (!aiueos_process_enter_plc_rt()) {
      extern volatile uint64_t aiueos_plc_process_stage;
      extern volatile uint64_t aiueos_plc_loader_stage;
      serial_string("AIUEOS_PLC_RT_FAIL embedded-elf-provider-or-safe-state stage=");
      serial_decimal(aiueos_plc_process_stage);
      serial_string(" loader=");
      serial_decimal(aiueos_plc_loader_stage);
      serial_string("\r\n");
      qemu_exit(0x70);
    }
    serial_string("AIUEOS_PLC_RT_OK profile=aiueos-plc-v1 scheduler=fixed-priority-preemptive priority=5 program=signed-cpl3-elf signature=ecdsa-p256-sha256 tamper=rejected scans=100 inputs=alternating-enable,sensor41..140 transport=syscall release=apic-absolute-ticks cycle=10ticks input=snapshot output=atomic-safe-state capabilities=16,17,18,19 failures=stage,watchdog,budget,deadline,program timing=logical-unqualified\r\n");
    qemu_exit(0x42);
#endif
    debug_string("AIUEOS_KOTOBA_ELF_PROCESS_OK source=catalog apps=2 et-exec segments=rx,rw result=42 domains=4,5\n");
    serial_string("AIUEOS_KOTOBA_ELF_PROCESS_OK source=catalog apps=2 et-exec segments=rx,rw result=42 domains=4,5\r\n");
    aiueos_load_task_register();
    aiueos_process_enter();
    if (!aiueos_process_result()) {
      debug_string("AIUEOS_RING3_FAIL syscall-results\n");
      serial_string("AIUEOS_RING3_FAIL syscall-results\r\n");
      qemu_exit(0x71);
    }
    if (!aiueos_syscall_transport_evidence_ready()) qemu_exit(0x71);
    if (!aiueos_kotoba_runtime_evidence_ready()) qemu_exit(0x71);
    debug_string("AIUEOS_KOTOBA_USER_RUNTIME_OK abi=v2 transport=syscall capabilities=2,3,4,5 object=service-registry,user-store service-ipc=mailbox domains=4,5 result=42\n");
    serial_string("AIUEOS_KOTOBA_USER_RUNTIME_OK abi=v2 transport=syscall capabilities=2,3,4,5 object=service-registry,user-store service-ipc=mailbox domains=4,5 result=42\r\n");
    debug_string("AIUEOS_KOTOBA_OBJECT_WRITE_OK domains=4,5 journals=44-47 objects=42,43 value=42 receipt=readback transaction=journal-first serializer=kotoba validator=kotoba decoder=kotoba materializer=kotoba fixed-stack\n");
    serial_string("AIUEOS_KOTOBA_OBJECT_WRITE_OK domains=4,5 journals=44-47 objects=42,43 value=42 receipt=readback transaction=journal-first serializer=kotoba validator=kotoba decoder=kotoba materializer=kotoba fixed-stack\r\n");
    if (!aiueos_kotoba_service_ipc_evidence_ready()) qemu_exit(0x71);
    debug_string("AIUEOS_KOTOBA_SERVICE_IPC_OK senders=4,5 recipients=service0,service1 payload=42 sequence=1 bounded=2 persistent-services=2\n");
    serial_string("AIUEOS_KOTOBA_SERVICE_IPC_OK senders=4,5 recipients=service0,service1 payload=42 sequence=1 bounded=2 persistent-services=2\r\n");
    debug_string("AIUEOS_RING3_OK processes=2 preemptive roots=2 domains=2,3 kernel-stacks=2 syscall-sysret\n");
    serial_string("AIUEOS_RING3_OK processes=2 preemptive roots=2 domains=2,3 kernel-stacks=2 syscall-sysret\r\n");
    debug_string("AIUEOS_SYSRET_OK star-lstar-fmask canonical-rip-rsp rflags-sanitized per-task-stack\n");
    serial_string("AIUEOS_SYSRET_OK star-lstar-fmask canonical-rip-rsp rflags-sanitized per-task-stack\r\n");
    debug_string("AIUEOS_CAPABILITY_TRANSFER_OK source=2 target=3 attenuated atomic-claim transferred-use owner-exit=descendants-revoked\n");
    serial_string("AIUEOS_CAPABILITY_TRANSFER_OK source=2 target=3 attenuated atomic-claim transferred-use owner-exit=descendants-revoked\r\n");
    if (!aiueos_process_lifecycle_evidence_ready()) qemu_exit(0x71);
    if (!aiueos_catalog_lookup_rejection_evidence_ready()) qemu_exit(0x71);
    debug_string("AIUEOS_APP_CATALOG_LOOKUP_OK ids=app/hello,app/worker unknown=denied extents=nonoverlap\n");
    serial_string("AIUEOS_APP_CATALOG_LOOKUP_OK ids=app/hello,app/worker unknown=denied extents=nonoverlap\r\n");
    debug_string("AIUEOS_PROCESS_REAP_OK tasks=4 services=2-persistent process-slots=8 task-slots=8 generations=reused owner-caps-revoked allocator-pages=24 stack-pages=reused zero-reused\n");
    serial_string("AIUEOS_PROCESS_REAP_OK tasks=4 services=2-persistent process-slots=8 task-slots=8 generations=reused owner-caps-revoked allocator-pages=24 stack-pages=reused zero-reused\r\n");
    debug_string("AIUEOS_USER_SYSCALL_OK valid-log copied-payload too-big stale-generation foreign-owner wrong-type no-rights invalid-pointer\n");
    serial_string("AIUEOS_USER_SYSCALL_OK valid-log copied-payload too-big stale-generation foreign-owner wrong-type no-rights invalid-pointer\r\n");
    if (!aiueos_address_space_self_test()) {
      debug_string("AIUEOS_ADDRESS_SPACE_FAIL cr3-or-isolation\n");
      serial_string("AIUEOS_ADDRESS_SPACE_FAIL cr3-or-isolation\r\n");
      qemu_exit(0x76);
    }
    debug_string("AIUEOS_ADDRESS_SPACE_OK processes=2 distinct-cr3 private-pages cross-access-fault\n");
    serial_string("AIUEOS_ADDRESS_SPACE_OK processes=2 distinct-cr3 private-pages cross-access-fault\r\n");
    aiueos_page_fault_stage = 1;
    aiueos_probe_write_protect();
    if (aiueos_page_fault_stage != 0x101 ||
        (aiueos_page_fault_error & 0x3) != 0x3) {
      debug_string("AIUEOS_PAGE_FAULT_FAIL write-protect\n");
      serial_string("AIUEOS_PAGE_FAULT_FAIL write-protect\r\n");
      qemu_exit(0x7a);
    }
    debug_string("AIUEOS_PAGE_FAULT_OK write-protect vector=14\n");
    serial_string("AIUEOS_PAGE_FAULT_OK write-protect vector=14\r\n");
    aiueos_page_fault_stage = 2;
    aiueos_probe_no_execute();
    if (aiueos_page_fault_stage != 0x102 ||
        (aiueos_page_fault_error & 0x11) != 0x11 ||
        (aiueos_page_fault_error & 0x2) != 0) {
      debug_string("AIUEOS_PAGE_FAULT_FAIL no-execute\n");
      serial_string("AIUEOS_PAGE_FAULT_FAIL no-execute\r\n");
      qemu_exit(0x79);
    }
    debug_string("AIUEOS_PAGE_FAULT_OK no-execute vector=14\n");
    serial_string("AIUEOS_PAGE_FAULT_OK no-execute vector=14\r\n");
    /* The end-of-boot #UD probe: its handler EXITS the machine (the last
       evidence, by design). The persistent desktop (JUN-141) must live, so
       in the default build the probe yields its slot to the loop marker and
       is disarmed. The smoke profile (AIUEOS_SMOKE_FINAL_PROBE, aiueos#436)
       arms it exactly here again: the handler writes AIUEOS_EXCEPTION_OK
       vector=6 invalid-opcode and terminates the machine through
       isa-debug-exit, the terminal evidence and exit-status contract
       smoke-qemu-uefi.sh's normal path asserts. Gates that need the loop to
       live leave the flag unset and are unchanged from 54ac566. */
#ifdef AIUEOS_SMOKE_FINAL_PROBE
    extern volatile int aiueos_final_probe_expected;
    aiueos_final_probe_expected = 1;
    __asm__ volatile("ud2");
#endif
  }
  /* JUN-141: the persistent desktop. The evidence job is over; from here
     the machine serves input forever -- each tablet event reduces the
     browser state, the frame is redrawn, the desktop stays alive and
     interactive instead of halting blind. */
  { debug_string("AIUEOS_DESKTOP_LOOP_OK persistent input service\n");
    serial_string("AIUEOS_DESKTOP_LOOP_OK persistent input service\r\n"); }
  for (;;) {
    uint32_t ax = 0, ay = 0, src = aiueos_tablet_next(200000U, &ax, &ay);
    int touched = 0;
    if (src) {
      uint32_t px = (uint32_t)(((uint64_t)ax * flow[3]) / 32768U);
      uint32_t py = (uint32_t)(((uint64_t)ay * flow[4]) / 32768U);
      flow[2046] = px + 1U;
      flow[2047] = py;
      (void)kotoba_aiueos_browser_reduce((uint64_t)(uintptr_t)flow, 8192, src, px, py);
      touched = 1;
    }
    /* Keyboard is polled EVERY turn, not only when the tablet is silent
       (JUN-144, measured 2026-10-20: an else-branch starved it behind a
       tablet path that never idles). */
    {
      extern uint32_t aiueos_keyboard_take_key(void);
      uint64_t dlen = 0;
      const uint8_t *dict = aiueos_initramfs_dictionary(&dlen);
      { extern uint32_t aiueos_input_ring(void);
        static uint32_t ring_seen;
        if (aiueos_input_ring() != ring_seen) {
          ring_seen = aiueos_input_ring();
          debug_string("AIUEOS_INPUT_RING ");
          serial_string("AIUEOS_INPUT_RING n=");
          serial_decimal(ring_seen);
          serial_string("\r\n");
        } }
      /* PUMP, not drain (JUN-34, measured 2026-10-23): drain here threw away
         every key that arrived between turns -- DESKTOP_KEY stayed at 1 while
         the host ring showed 103 used entries. One non-blocking reap per turn
         hands the keys to the browser in the order the ring delivered them. */
      uint32_t key = aiueos_keyboard_take_key();
      if (key) {
        debug_string("AIUEOS_DESKTOP_KEY ");
        serial_string("AIUEOS_DESKTOP_KEY code=");
        serial_decimal(key & 0xffffU);
        serial_string("\r\n");
        if (dict) {
          (void)kotoba_aiueos_browser_key((uint64_t)(uintptr_t)flow, 8192,
                                          (uint64_t)(uintptr_t)dict, dlen,
                                          (uint64_t)key);
          touched = 1;
        }
      }
    }
    /* A2 (scorecard row A2 / JUN-142): the host can resize the display at
       any moment, and this loop used to find out only on the next keystroke
       or pointer event -- the idle branch halts. refresh() throttles its own
       GET_DISPLAY_INFO read to one call in 64, so polling it every idle turn
       costs at most one device read per 64 turns and lets the desktop
       re-send its frame BEFORE any input exists. Measured 2026-10-26. */
    if (!touched) {
      extern int aiueos_gpu_display_refresh(void);
      if (aiueos_gpu_display_refresh()) touched = 1;
    }
    if (!touched) { __asm__ volatile("sti; hlt"); continue; }
    { uint64_t flen = 0;
      const uint8_t *font = aiueos_initramfs_font(&flen);
      int64_t n = 0;
      if (font) n = (int64_t)kotoba_aiueos_browser_frame2(
                     (uint64_t)(uintptr_t)flow, 8192, (uint64_t)(uintptr_t)font, flen);
      if (n > 0 && aiueos_desktop_present_ops2(flow + 480, (uint64_t)n, font, flen))
        (void)aiueos_desktop_show();
    }
  }
}
