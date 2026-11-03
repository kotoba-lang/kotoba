/* The C HTTP response heads were before JUN-552 moved them to kotoba/http-head.o, verbatim from kernel/pci.c (main
   47d7a83b): net_http_cid_admit's lines up to its body offset (its signature, the digest buffer and everything after
   the offset -- the SHA-256 and the digest comparison, unchanged -- left out), as old_cid_body answering that offset,
   and rtl8125_http_success, renamed old_http_success. */
#include <stdint.h>
uint32_t old_cid_body(const uint8_t *app, uint32_t n) {
  uint32_t i, body = 0;
  /* Mechanism: find the compiled status line and header terminator. */
  if (n < 12) return 0;
  if (app[0] != 'H' || app[1] != 'T' || app[2] != 'T' || app[3] != 'P') return 0;
  if (app[5] != '1' || app[9] != '2' || app[10] != '0' || app[11] != '0') return 0;
  for (i = 0; i + 3 < n; i++) {
    if (app[i] == '\r' && app[i + 1] == '\n' &&
        app[i + 2] == '\r' && app[i + 3] == '\n') {
      body = i + 4;
      break;
    }
  }
  return body;
}
int old_http_success(const uint8_t *bytes, uint32_t length) {
  return bytes && length >= 12 &&
    bytes[0] == 'H' && bytes[1] == 'T' && bytes[2] == 'T' && bytes[3] == 'P' &&
    bytes[4] == '/' && bytes[5] == '1' && bytes[6] == '.' && bytes[7] == '1' &&
    bytes[8] == ' ' && bytes[9] == '2' &&
    bytes[10] >= '0' && bytes[10] <= '9' &&
    bytes[11] >= '0' && bytes[11] <= '9';
}
