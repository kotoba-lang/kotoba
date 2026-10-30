/* kernel/tls13.c before JUN-553 moved its decisions to kotoba/tls13-hs.o: consume_hs_messages, process_record and
   aiueos_tls13_feed, verbatim, over prelude.h's state and stubs. */
#define PFX(x) old_##x
#include "prelude.h"
static int consume_hs_messages(const uint8_t *p, uint32_t n) {
  if (hs_partial_len + n > TLS_HS_MAX) return 0;
  copy_bytes(hs_partial + hs_partial_len, p, n);
  hs_partial_len += n;
  while (hs_partial_len >= 4) {
    uint32_t mlen = be24(hs_partial + 1);
    uint32_t total = 4 + mlen;
    uint8_t typ = hs_partial[0];
    if (total > TLS_HS_MAX) return 0;
    if (hs_partial_len < total) return 1;
    if (typ == 0x14) {
      if (!certverify_parsed) return 0;
      if (!finish_check(hs_partial + 4, mlen)) return 0;
      if (!transcript_add(hs_partial, total)) return 0;
      if (!derive_ap_keys()) return 0;
      handshake_ready = 1;
    } else if (typ == 0x0b) {
      if (!parse_certificate(hs_partial, total)) return 0;
      if (!transcript_add(hs_partial, total)) return 0;
    } else if (typ == 0x0f) {
      /* Hash transcript BEFORE adding CertificateVerify (RFC 8446 4.4.3). */
      if (!verify_certificate_verify(hs_partial, total)) return 0;
      if (!transcript_add(hs_partial, total)) return 0;
    } else if (!have_server_finished) {
      /* EE / others before Finished. Do not hash NST after Finished. */
      if (!transcript_add(hs_partial, total)) return 0;
    }
    if (hs_partial_len > total)
      copy_bytes(hs_partial, hs_partial + total, hs_partial_len - total);
    hs_partial_len -= total;
  }
  return 1;
}

static uint32_t nst_count;

static uint8_t last_alert_level;
static uint8_t last_alert_desc;

static int process_record(uint8_t *rec, uint32_t rec_len) {
  uint8_t typ = rec[0];
  last_record_type = typ;
  if (!saw_record) {
    saw_record = 1;
    first_record_type = typ;
  }
  if (typ == 0x14) return 1; /* CCS */
  if (typ == 0x15) {
    if (rec_len >= 7) {
      last_alert_level = rec[5];
      last_alert_desc = rec[6];
    }
    failed = 1;
    return 0;
  }
  if (typ == 0x16) {
    uint32_t hlen = (uint32_t)be16(rec + 3);
    if (handshake_ready) return 1;
    if (!have_sh) return parse_serverhello(rec + 5, hlen);
    return consume_hs_messages(rec + 5, hlen);
  }
  if (typ == 0x17) {
    uint8_t inner;
    uint32_t plen = 0;
    static uint8_t TLS_SCRATCH plain[TLS_HS_MAX];
    if (!have_hs_keys) return 0;
    if (!handshake_ready) {
      if (!unprotect(s_hs_key, s_hs_iv, s_hs_seq, rec, rec_len, plain, &plen, &inner))
        return 0;
      s_hs_seq++;
      last_inner_type = inner;
      if (inner == 0x15) {
        if (plen >= 2) {
          last_alert_level = plain[0];
          last_alert_desc = plain[1];
        }
        failed = 1;
        return 0;
      }
      if (inner != 0x16) return 0;
      return consume_hs_messages(plain, plen);
    }
    if (!unprotect(s_ap_key, s_ap_iv, s_ap_seq, rec, rec_len, plain, &plen, &inner))
      return 0;
    s_ap_seq++;
    last_inner_type = inner;
    if (inner == 0x15) {
      if (plen >= 2) {
        last_alert_level = plain[0];
        last_alert_desc = plain[1];
      }
      /* close_notify (warning/0): prior application data stays valid. */
      if (plen >= 2 && plain[0] == 1 && plain[1] == 0) return 1;
      failed = 1;
      return 0;
    }
    if (inner != 0x17) {
      nst_count++;
      return 1; /* NST and other post-handshake */
    }
    if (app_len + plen > TLS_APP_MAX) return 0;
    copy_bytes(app_buf + app_len, plain, plen);
    app_len += plen;
    return 1;
  }
  return 1;
}

int aiueos_tls13_feed(const uint8_t *data, uint32_t len) {
  if (failed) return 0;
  if (rx_len + len > TLS_RX_MAX) return 0;
  copy_bytes(rx + rx_len, data, len);
  rx_len += len;
  while (rx_len >= 5) {
    uint32_t rec_len = 5u + (uint32_t)be16(rx + 3);
    if (rec_len < 5 || rec_len > TLS_RX_MAX) {
      failed = 1;
      return 0;
    }
    if (rx_len < rec_len) return 1;
    if (!process_record(rx, rec_len)) {
      failed = 1;
      return 0;
    }
    if (rx_len > rec_len) copy_bytes(rx, rx + rec_len, rx_len - rec_len);
    rx_len -= rec_len;
  }
  return 1;
}

#include "epilogue.h"
