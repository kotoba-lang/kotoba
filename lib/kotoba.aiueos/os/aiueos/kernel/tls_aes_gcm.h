#ifndef AIUEOS_TLS_AES_GCM_H
#define AIUEOS_TLS_AES_GCM_H

#include <stdint.h>

/* Decision-free AES-128-GCM (FIPS 197 + SP 800-38D). Mechanism only:
   encrypt, decrypt, compare a tag. Admission of a CID stays in Kotoba. */
int aiueos_aes128_gcm_encrypt(const uint8_t key[16], const uint8_t nonce[12],
                              const uint8_t *aad, uint32_t aad_len,
                              const uint8_t *pt, uint32_t pt_len,
                              uint8_t *ct, uint8_t tag[16]);
int aiueos_aes128_gcm_decrypt(const uint8_t key[16], const uint8_t nonce[12],
                              const uint8_t *aad, uint32_t aad_len,
                              const uint8_t *ct, uint32_t ct_len,
                              const uint8_t tag[16], uint8_t *pt);
int aiueos_aes128_gcm_selftest(void);

#endif
