/* Frame builders for the native-route network differentials (JUN-552): big-endian stores, the internet checksum, and
   valid Ethernet II frames -- an ARP reply, an IPv4 ICMP echo reply, an IPv4 TCP segment and a DHCP reply -- that a
   driver then mutates one field at a time. Every builder leaves the rest of the 2048-byte frame random. */
#include <stdint.h>
#pragma GCC diagnostic ignored "-Wunused-function"
#define FRAME 2048
static uint8_t frame[FRAME + 64] __attribute__((aligned(16)));
static void be16(int o, uint32_t v) { frame[o] = (uint8_t)(v >> 8); frame[o + 1] = (uint8_t)v; }
static void be32(int o, uint32_t v) { be16(o, v >> 16); be16(o + 2, v & 0xffff); }
static uint32_t get16(int o) { return (uint32_t)frame[o] << 8 | frame[o + 1]; }
static uint32_t sum16(const uint8_t *p, int n, uint32_t s) {
  for (int i = 0; i + 1 < n; i += 2) s += (uint32_t)p[i] << 8 | p[i + 1];
  if (n & 1) s += (uint32_t)p[n - 1] << 8;
  return s;
}
static uint16_t fold(uint32_t s) { while (s >> 16) s = (s & 0xffff) + (s >> 16); return (uint16_t)~s; }
static void fill_random(void) { for (int i = 0; i < FRAME + 64; i++) frame[i] = (uint8_t)rnd(); }
/* IPv4 header at 14 with protocol PROTO and total length TOTAL, from SRC; the header checksum made right */
static void ipv4(uint32_t total, uint8_t proto, uint32_t src, uint32_t dst) {
  be16(12, 0x0800); frame[14] = 0x45; be16(16, total); frame[23] = proto; be32(26, src); be32(30, dst);
  be16(24, 0); be16(24, fold(sum16(frame + 14, 20, 0)));
}
static void ip_checksum(void) { be16(24, 0); be16(24, fold(sum16(frame + 14, 20, 0))); }
static uint32_t pseudo(uint8_t proto, uint32_t len) {
  return get16(26) + get16(28) + get16(30) + get16(32) + proto + len;
}
/* checksum field at FIELD over [34, 34 + LEN) with the pseudo header for PROTO */
static void l4_checksum(int field, uint8_t proto, uint32_t len) {
  be16(field, 0); be16(field, fold(sum16(frame + 34, (int)len, pseudo(proto, len))));
}
static void icmp_checksum(uint32_t len) { be16(36, 0); be16(36, fold(sum16(frame + 34, (int)len, 0))); }
