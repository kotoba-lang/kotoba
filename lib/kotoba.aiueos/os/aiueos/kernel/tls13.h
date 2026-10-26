#ifndef AIUEOS_TLS13_H
#define AIUEOS_TLS13_H

#include <stdint.h>

/* TLS 1.3 record layer + key schedule for one ClientHello → Finished →
   HTTP GET. Mechanism: AES-GCM, HKDF, X25519 (Kotoba), SHA-256 (Kotoba).
   CID admission is not here. */
int aiueos_tls13_configure(const char *host,
                           const uint8_t *request, uint32_t request_len,
                           const uint8_t client_random[32],
                           const uint8_t ephemeral_scalar[32]);
void aiueos_tls13_reset(void);
int aiueos_tls13_clienthello(uint8_t *out, uint32_t *len);
int aiueos_tls13_feed(const uint8_t *data, uint32_t len);
int aiueos_tls13_saw_record(void);
uint8_t aiueos_tls13_first_record_type(void);
int aiueos_tls13_handshake_ready(void);
int aiueos_tls13_take_finished(uint8_t *out, uint32_t *len);
int aiueos_tls13_take_http(uint8_t *out, uint32_t *len);
uint32_t aiueos_tls13_app_len(void);
const uint8_t *aiueos_tls13_app(void);
int aiueos_tls13_aes_selftest(void);
int aiueos_tls13_hmac_selftest(void);
int aiueos_tls13_ecdsa_selftest(void);
int aiueos_tls13_record_selftest(void);
int aiueos_tls13_run_certverify(void);
int aiueos_tls13_certverify_ok(void);
uint16_t aiueos_tls13_certverify_scheme(void);
uint32_t aiueos_tls13_stage(void);
uint32_t aiueos_tls13_rx_buffered(void);
uint8_t aiueos_tls13_last_record_type(void);
uint8_t aiueos_tls13_last_inner_type(void);
int aiueos_tls13_failed(void);
uint32_t aiueos_tls13_nst_count(void);
uint8_t aiueos_tls13_alert_level(void);
uint8_t aiueos_tls13_alert_desc(void);

#endif
