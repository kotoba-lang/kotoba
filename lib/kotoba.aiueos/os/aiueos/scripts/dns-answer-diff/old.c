/* The C net_dns_answer_ok_named was before JUN-552 moved it to kotoba/dns-answer.o: verbatim from kernel/pci.c
   (main c3817f8f), with the byte helpers, net_dhcp_scratch and net_udp_rx_checksum_ok it used, renamed
   old_dns_answer_ok_named. kotoba_aiueos_ipv4_checksum is kotoba/ipv4-checksum.o, as in the kernel. */
#include <stdint.h>
#define NET_DNS_CLIENT_PORT 49154
#define NET_DNS_XID 0xa1e0
extern uint64_t kotoba_aiueos_ipv4_checksum(uint64_t buffer, uint64_t length);
static uint8_t net_dhcp_scratch[2048] __attribute__((aligned(16)));
static void net_store_be16(uint8_t *at, uint16_t value) {
  at[0] = (uint8_t)(value >> 8); at[1] = (uint8_t)value;
}
static void net_store_be32(uint8_t *at, uint32_t value) {
  at[0] = (uint8_t)(value >> 24); at[1] = (uint8_t)(value >> 16);
  at[2] = (uint8_t)(value >> 8); at[3] = (uint8_t)value;
}
/* The inverse pair, needed only once TCP has to carry a number the PEER chose --
   every field this driver sent before was one it had picked itself. Reading a
   field is not admitting it: these are used only on frames a Kotoba object has
   already accepted, the same rule under which the peer's MAC is lifted out of an
   admitted ARP reply (ADR-0021). */
static uint16_t net_load_be16(const uint8_t *at) {
  return (uint16_t)(((uint32_t)at[0] << 8) | at[1]);
}
static uint32_t net_load_be32(const uint8_t *at) {
  return ((uint32_t)at[0] << 24) | ((uint32_t)at[1] << 16) |
         ((uint32_t)at[2] << 8) | at[3];
}

static int net_udp_rx_checksum_ok(const uint8_t *frame, uint32_t udp_length) {
  net_store_be32(net_dhcp_scratch, net_load_be32(frame + 26));
  net_store_be32(net_dhcp_scratch + 4, net_load_be32(frame + 30));
  net_dhcp_scratch[8] = 0;
  net_dhcp_scratch[9] = 17;
  net_store_be16(net_dhcp_scratch + 10, (uint16_t)udp_length);
  for (uint32_t i = 0; i < udp_length; i++) net_dhcp_scratch[12 + i] = frame[34 + i];
  return (uint16_t)kotoba_aiueos_ipv4_checksum(
    (uint64_t)(uintptr_t)net_dhcp_scratch, 12 + udp_length) == 0;
}

int old_dns_answer_ok_named(const uint8_t *frame, uint32_t length,
                                   uint32_t src, uint32_t dst,
                                   uint16_t server_port,
                                   const uint8_t *question,
                                   uint32_t question_length,
                                   uint32_t *out_a) {
  uint32_t total, udp_length, answer;
  unsigned i;
  if (!frame || !question || !out_a || question_length < 5 ||
      question_length > 255 || length < 70 + question_length) return 0;
  if (net_load_be16(frame + 12) != 0x0800) return 0;
  if (frame[14] != 0x45 || frame[23] != 17) return 0;
  total = net_load_be16(frame + 16);
  if (total < 58 || 14 + total > length) return 0;
  if (kotoba_aiueos_ipv4_checksum((uint64_t)(uintptr_t)(frame + 14), 20) != 0)
    return 0;
  if (net_load_be32(frame + 26) != src) return 0;
  if (net_load_be32(frame + 30) != dst) return 0;
  if (net_load_be16(frame + 34) != server_port) return 0;
  if (net_load_be16(frame + 36) != NET_DNS_CLIENT_PORT) return 0;
  udp_length = net_load_be16(frame + 38);
  if (udp_length < 20 + question_length || 20 + udp_length != total) return 0;
  if (net_load_be16(frame + 40) != 0 && !net_udp_rx_checksum_ok(frame, udp_length))
    return 0;
  if (net_load_be16(frame + 42) != NET_DNS_XID) return 0;
  if ((net_load_be16(frame + 44) & 0x8000) == 0) return 0;   /* QR */
  if ((net_load_be16(frame + 44) & 0x000f) != 0) return 0;   /* RCODE */
  if (net_load_be16(frame + 46) != 1) return 0;              /* QDCOUNT */
  if (net_load_be16(frame + 48) == 0) return 0;              /* ANCOUNT */
  for (i = 0; i < question_length; i++) {
    if (frame[54 + i] != question[i]) return 0;
  }
  answer = 54 + question_length;
  if (frame[answer] == 0xc0 && frame[answer + 1] == 0x0c) {
    if (length < answer + 16) return 0;
    if (net_load_be16(frame + answer + 2) != 1) return 0;
    if (net_load_be16(frame + answer + 4) != 1) return 0;
    if (net_load_be16(frame + answer + 10) != 4) return 0;
    *out_a = net_load_be32(frame + answer + 12);
    return *out_a != 0;
  }
  if (length < answer + question_length + 10) return 0;
  for (i = 0; i < question_length; i++) {
    if (frame[answer + i] != question[i]) return 0;
  }
  if (net_load_be16(frame + answer + question_length + 4) != 4) return 0;
  *out_a = net_load_be32(frame + answer + question_length + 6);
  return *out_a != 0;
}

