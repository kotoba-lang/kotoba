/* The C net_udp_checksum and net_udp_rx_checksum_ok were before JUN-552 moved their sum to kotoba/udp-checksum.o:
   verbatim from kernel/pci.c (main 039cda76), with the byte helpers and net_dhcp_scratch they used, renamed old_*.
   kotoba_aiueos_ipv4_checksum is kotoba/ipv4-checksum.o, as in the kernel. */
#include <stdint.h>
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

uint16_t old_udp_checksum(const uint8_t *frame, uint32_t udp_length) {
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

int old_udp_rx_checksum_ok(const uint8_t *frame, uint32_t udp_length) {
  net_store_be32(net_dhcp_scratch, net_load_be32(frame + 26));
  net_store_be32(net_dhcp_scratch + 4, net_load_be32(frame + 30));
  net_dhcp_scratch[8] = 0;
  net_dhcp_scratch[9] = 17;
  net_store_be16(net_dhcp_scratch + 10, (uint16_t)udp_length);
  for (uint32_t i = 0; i < udp_length; i++) net_dhcp_scratch[12 + i] = frame[34 + i];
  return (uint16_t)kotoba_aiueos_ipv4_checksum(
    (uint64_t)(uintptr_t)net_dhcp_scratch, 12 + udp_length) == 0;
}
