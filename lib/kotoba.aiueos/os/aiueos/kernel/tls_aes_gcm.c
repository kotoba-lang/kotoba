#include "tls_aes_gcm.h"

/* The kernel build puts movable scratch in the `.high_bss` 4..6 MiB window
   (linker.ld); the host-side known-answer build is a userland binary with no
   such section, so it keeps a plain static. */
#ifdef AIUEOS_TLS_AES_GCM_HOST_TEST
#define AIUEOS_GCM_HIGH_BSS
#else
#define AIUEOS_GCM_HIGH_BSS __attribute__((section(".high_bss")))
#endif

/* AES-128-GCM is `os/aiueos/kotoba/aes128-gcm.kotoba`, compiled to
   `kotoba_aiueos_aes128_gcm` (ADR-0132), and its boot known-answer test is
   `kotoba/aes128-gcm-selftest.kotoba` (ADR-0220). What is left in this file
   is the marshalling between the two shapes and nothing else: the S-box, the
   key schedule, the cipher, GHASH, CTR and the tag comparison -- 185 lines
   that held the whole confidentiality and integrity decision of every TLS
   1.3 record and every SSH packet this kernel sends -- are gone, and so are
   the 120 lines of vectors and comparisons the self-test was.

   TWO SHAPES, AND THE DIFFERENCE IS NOT COSMETIC.

   * The object returns a REASON CODE and ZERO IS SUCCESS.  This file's two
     entry points keep returning 1 for success because `kernel/tls13.c` and
     `kernel/pci.c` have twenty call sites between them that read
     `if (!aes(...)) return 0;`, and a silent convention flip is the one thing
     worse than a loud one.  The inversion happens HERE, once, on the two
     `return` lines below, and it is the only place in the kernel that knows
     the two conventions differ.
   * The object works IN PLACE on one region; these entry points take separate
     input and output pointers.  So the input is copied to the output first and
     the object is asked to transform the output.  That is exact -- CTR is an
     XOR -- and it needs no bounce buffer: every caller here already owns an
     output region of the right size.
   * The object AUTHENTICATES BEFORE IT DECRYPTS.  The C this replaces
     decrypted first and compared the tag afterwards, so a forged record left
     attacker-chosen plaintext in the caller's buffer for as long as the caller
     took to look at the return value.  A refused record now leaves the
     CIPHERTEXT there instead. */

extern uint64_t kotoba_aiueos_aes128_gcm(uint8_t *, uint64_t, uint8_t *,
                                         uint64_t, uint64_t);

/* The object's one caller-owned region: key, nonce, AAD, tag and every scratch
   buffer it uses.  1280 bytes, laid out by aes128-gcm.kotoba's header.  It is
   `.bss` rather than a stack frame because the kernel's stacks are 4 KiB and
   this is a third of one. */
static uint8_t gcm_ctx[1280];

static void gcm_copy(uint8_t *d, const uint8_t *s, uint32_t n) {
  uint32_t i;
  if (d == s) return;
  for (i = 0; i < n; i++) d[i] = s[i];
}

static uint64_t gcm_call(const uint8_t key[16], const uint8_t nonce[12],
                         const uint8_t *aad, uint32_t aad_len,
                         uint8_t *data, uint32_t data_len, int seal) {
  uint32_t i;
  for (i = 0; i < sizeof(gcm_ctx); i++) gcm_ctx[i] = 0;
  gcm_copy(gcm_ctx, key, 16);
  gcm_copy(gcm_ctx + 16, nonce, 12);
  gcm_ctx[28] = (uint8_t)aad_len;
  gcm_copy(gcm_ctx + 64, aad, aad_len);
  return kotoba_aiueos_aes128_gcm(gcm_ctx, sizeof(gcm_ctx), data,
                                  (uint64_t)data_len, seal ? 1u : 0u);
}

int aiueos_aes128_gcm_encrypt(const uint8_t key[16], const uint8_t nonce[12],
                              const uint8_t *aad, uint32_t aad_len,
                              const uint8_t *pt, uint32_t pt_len,
                              uint8_t *ct, uint8_t tag[16]) {
  uint32_t i;
  if (aad_len > 64) return 0;
  gcm_copy(ct, pt, pt_len);
  if (gcm_call(key, nonce, aad, aad_len, ct, pt_len, 1) != 0) return 0;
  for (i = 0; i < 16; i++) tag[i] = gcm_ctx[32 + i];
  return 1;
}

int aiueos_aes128_gcm_decrypt(const uint8_t key[16], const uint8_t nonce[12],
                              const uint8_t *aad, uint32_t aad_len,
                              const uint8_t *ct, uint32_t ct_len,
                              const uint8_t tag[16], uint8_t *pt) {
  uint32_t i;
  if (aad_len > 64) return 0;
  gcm_copy(pt, ct, ct_len);
  for (i = 0; i < sizeof(gcm_ctx); i++) gcm_ctx[i] = 0;
  gcm_copy(gcm_ctx, key, 16);
  gcm_copy(gcm_ctx + 16, nonce, 12);
  gcm_ctx[28] = (uint8_t)aad_len;
  gcm_copy(gcm_ctx + 64, aad, aad_len);
  gcm_copy(gcm_ctx + 32, tag, 16);
  return kotoba_aiueos_aes128_gcm(gcm_ctx, sizeof(gcm_ctx), pt,
                                  (uint64_t)ct_len, 0) == 0;
}

extern int64_t kotoba_aiueos_aes128_gcm_selftest(uint8_t *scratch,
                                                 int64_t length);

int aiueos_aes128_gcm_selftest(void) {
  /* The known-answer test is `os/aiueos/kotoba/aes128-gcm-selftest.kotoba`
     (ADR-0220): SP 800-38D's empty-message tag, the 64-byte message's
     ciphertext and tag, the round trip, a flipped tag bit refused with the
     ciphertext left in place, and the 20-byte-AAD tag -- run at boot over
     the SAME core module the linked cipher object is built from. Zero is
     every step agreeing; a non-zero answer is the number of the step that
     did not. gcm_ctx stays .bss; the scratch moved to `.high_bss` on
     2026-10-26 because the merged tree was one page over the low-region
     budget, and this buffer zeroes itself before every use. */
  static uint8_t scratch[1536] AIUEOS_GCM_HIGH_BSS;
  uint32_t i;
  for (i = 0; i < sizeof(scratch); i++) scratch[i] = 0;
  return kotoba_aiueos_aes128_gcm_selftest(scratch, (int64_t)sizeof(scratch)) == 0;
}

#ifdef AIUEOS_TLS_AES_GCM_HOST_TEST
#include <stdio.h>
int main(void) {
  if (!aiueos_aes128_gcm_selftest()) {
    puts("AES-GCM selftest FAIL");
    return 1;
  }
  puts("AES-GCM selftest OK");
  return 0;
}
#endif
