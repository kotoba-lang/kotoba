/* The C net_build_arp_request and net_build_icmp_echo were before JUN-552 moved them to kotoba/arp-icmp-build.o:
   verbatim from kernel/pci.c (main 2f8209e0), with the byte stores they used, renamed old_*. Their MAC globals are
   set by old_set. kotoba_aiueos_ipv4_checksum is kotoba/ipv4-checksum.o, as in the kernel. */
#include <stdint.h>
#define NET_GUEST_IP 0x0a00020fU
#define NET_PEER_IP 0x0a000202U
#define NET_ICMP_IDENT 0xa1e0
#define NET_ICMP_SEQUENCE 1
extern uint64_t kotoba_aiueos_ipv4_checksum(uint64_t buffer, uint64_t length);
static uint8_t net_mac[6], net_peer_mac[6];
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

uint32_t old_build_arp_request(uint8_t *frame) {
  for (unsigned i = 0; i < 6; i++) frame[i] = 0xff;          /* broadcast */
  for (unsigned i = 0; i < 6; i++) frame[6 + i] = net_mac[i];
  net_store_be16(frame + 12, 0x0806);                        /* EtherType ARP */
  net_store_be16(frame + 14, 1);                             /* Ethernet */
  net_store_be16(frame + 16, 0x0800);                        /* IPv4 */
  frame[18] = 6; frame[19] = 4;
  net_store_be16(frame + 20, 1);                             /* request */
  for (unsigned i = 0; i < 6; i++) frame[22 + i] = net_mac[i];
  net_store_be32(frame + 28, NET_GUEST_IP);
  for (unsigned i = 0; i < 6; i++) frame[32 + i] = 0;        /* unknown target */
  net_store_be32(frame + 38, NET_PEER_IP);
  return 42;
}

uint32_t old_build_icmp_echo(uint8_t *frame) {
  for (unsigned i = 0; i < 6; i++) frame[i] = net_peer_mac[i];
  for (unsigned i = 0; i < 6; i++) frame[6 + i] = net_mac[i];
  net_store_be16(frame + 12, 0x0800);                        /* EtherType IPv4 */
  frame[14] = 0x45;                                          /* version 4, IHL 5 */
  frame[15] = 0;                                             /* no DSCP, no ECN */
  net_store_be16(frame + 16, 28);                            /* 20 IPv4 + 8 ICMP */
  /* Identification 0 with DF set: RFC 6864 permits it precisely because a
     datagram that may not be fragmented can never need to be reassembled. */
  net_store_be16(frame + 18, 0);
  net_store_be16(frame + 20, 0x4000);
  frame[22] = 64;                                            /* TTL */
  frame[23] = 1;                                             /* ICMP */
  net_store_be16(frame + 24, 0);                             /* checksum covers itself as 0 */
  net_store_be32(frame + 26, NET_GUEST_IP);
  net_store_be32(frame + 30, NET_PEER_IP);
  net_store_be16(frame + 24,
    (uint16_t)kotoba_aiueos_ipv4_checksum((uint64_t)(uintptr_t)(frame + 14), 20));
  frame[34] = 8;                                             /* echo request */
  frame[35] = 0;
  net_store_be16(frame + 36, 0);
  net_store_be16(frame + 38, NET_ICMP_IDENT);
  net_store_be16(frame + 40, NET_ICMP_SEQUENCE);
  net_store_be16(frame + 36,
    (uint16_t)kotoba_aiueos_ipv4_checksum((uint64_t)(uintptr_t)(frame + 34), 8));
  /* 42 bytes, the same length as the ARP request the device already accepted,
     so nothing here depends on a minimum-frame rule that has not been tested. */
  return 42;
}
