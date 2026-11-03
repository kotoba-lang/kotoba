/* The C net_build_dns_query_named was before JUN-552 moved it to kotoba/dns-query.o: verbatim from kernel/pci.c
   (main 039cda76), with the byte helpers, net_dhcp_scratch and net_udp_checksum it used, renamed old_build_dns_query.
   Its MAC globals are set by old_set. kotoba_aiueos_ipv4_checksum is kotoba/ipv4-checksum.o, as in the kernel. */
#include <stdint.h>
#define NET_DNS_CLIENT_PORT 49154
#define NET_DNS_XID 0xa1e0
extern uint64_t kotoba_aiueos_ipv4_checksum(uint64_t buffer, uint64_t length);
static uint8_t net_mac[6], net_peer_mac[6];
static uint8_t net_dhcp_scratch[2048] __attribute__((aligned(16)));
void old_set(const uint8_t mac[6], const uint8_t peer[6]) {
  for (int i = 0; i < 6; i++) { net_mac[i] = mac[i]; net_peer_mac[i] = peer[i]; }
}
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

static uint16_t net_udp_checksum(const uint8_t *frame, uint32_t udp_length) {
  net_store_be32(net_dhcp_scratch, net_load_be32(frame + 26));
  net_store_be32(net_dhcp_scratch + 4, net_load_be32(frame + 30));
  net_dhcp_scratch[8] = 0;
  net_dhcp_scratch[9] = 17;                                  /* protocol UDP */
  net_store_be16(net_dhcp_scratch + 10, (uint16_t)udp_length);
  for (uint32_t i = 0; i < udp_length; i++) net_dhcp_scratch[12 + i] = frame[34 + i];
  uint16_t sum = (uint16_t)kotoba_aiueos_ipv4_checksum(
    (uint64_t)(uintptr_t)net_dhcp_scratch, 12 + udp_length);
  /* RFC 768: a computed checksum of zero goes on the wire as all ones, because
     zero already means "not computed". The admission accepts both. */
  return sum ? sum : 0xffff;
}

uint32_t old_build_dns_query(uint8_t *frame, uint32_t src,
                                          uint32_t dst, uint16_t server_port,
                                          const uint8_t *question,
                                          uint32_t question_length) {
  uint32_t udp_length = 8 + 12 + question_length;
  uint32_t total = 20 + udp_length;
  if (!frame || !question || question_length < 5 || question_length > 255)
    return 0;
  for (uint32_t i = 0; i < 14 + total; i++) frame[i] = 0;
  for (unsigned i = 0; i < 6; i++) frame[i] = net_peer_mac[i];
  for (unsigned i = 0; i < 6; i++) frame[6 + i] = net_mac[i];
  net_store_be16(frame + 12, 0x0800);
  frame[14] = 0x45;
  net_store_be16(frame + 16, (uint16_t)total);
  net_store_be16(frame + 20, 0x4000);
  frame[22] = 64;
  frame[23] = 17;
  net_store_be32(frame + 26, src);
  net_store_be32(frame + 30, dst);
  net_store_be16(frame + 24,
    (uint16_t)kotoba_aiueos_ipv4_checksum((uint64_t)(uintptr_t)(frame + 14), 20));
  net_store_be16(frame + 34, NET_DNS_CLIENT_PORT);
  net_store_be16(frame + 36, server_port);
  net_store_be16(frame + 38, (uint16_t)udp_length);
  net_store_be16(frame + 42, NET_DNS_XID);
  net_store_be16(frame + 44, 0x0100);                        /* RD */
  net_store_be16(frame + 46, 1);                             /* QDCOUNT */
  for (uint32_t i = 0; i < question_length; i++)
    frame[54 + i] = question[i];
  net_store_be16(frame + 40, net_udp_checksum(frame, udp_length));
  return 14 + total;
}
