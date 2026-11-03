/* The C net_build_tcp was before JUN-552 moved it to kotoba/tcp-build.o: verbatim from kernel/pci.c (main 3569d11c),
   with the byte helpers, net_tcp_scratch and net_tcp_checksum it used, renamed old_build_tcp. Its globals are set by
   old_set. kotoba_aiueos_ipv4_checksum is kotoba/ipv4-checksum.o, as in the kernel. */
#include <stdint.h>
extern uint64_t kotoba_aiueos_ipv4_checksum(uint64_t buffer, uint64_t length);
static uint8_t net_mac[6], net_peer_mac[6];
static uint16_t net_tx_window, net_ip_id;
void old_set(const uint8_t mac[6], const uint8_t peer[6], uint16_t window, uint16_t id) {
  for (int i = 0; i < 6; i++) { net_mac[i] = mac[i]; net_peer_mac[i] = peer[i]; }
  net_tx_window = window; net_ip_id = id;
}
uint16_t old_ip_id(void) { return net_ip_id; }
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

static uint8_t net_tcp_scratch[4096] __attribute__((aligned(4096)));

static uint16_t net_tcp_checksum(const uint8_t *frame, uint32_t tcp_length,
                                 uint32_t src, uint32_t dst) {
  net_store_be32(net_tcp_scratch, src);
  net_store_be32(net_tcp_scratch + 4, dst);
  net_tcp_scratch[8] = 0;
  net_tcp_scratch[9] = 6;                                    /* protocol TCP */
  net_store_be16(net_tcp_scratch + 10, (uint16_t)tcp_length);
  for (uint32_t i = 0; i < tcp_length; i++) net_tcp_scratch[12 + i] = frame[34 + i];
  return (uint16_t)kotoba_aiueos_ipv4_checksum(
    (uint64_t)(uintptr_t)net_tcp_scratch, 12 + tcp_length);
}

uint32_t old_build_tcp(uint8_t *frame, uint32_t src, uint32_t dst,
                              uint16_t sport, uint16_t dport,
                              uint32_t sequence, uint32_t acknowledgement,
                              uint8_t flags, const uint8_t *payload,
                              uint32_t payload_length) {
  uint32_t total = 40 + payload_length;                      /* 20 IPv4 + 20 TCP */
  for (unsigned i = 0; i < 6; i++) frame[i] = net_peer_mac[i];
  for (unsigned i = 0; i < 6; i++) frame[6 + i] = net_mac[i];
  net_store_be16(frame + 12, 0x0800);                        /* EtherType IPv4 */
  frame[14] = 0x45;                                          /* version 4, IHL 5 */
  frame[15] = 0;
  net_store_be16(frame + 16, (uint16_t)total);
  /* Identification 0 with DF set, as for the echo: RFC 6864 permits it because
     a datagram that may not be fragmented can never need reassembly. Distinct
     IDs still help SLIRP tell later TCP segments apart from the ClientHello. */
  net_store_be16(frame + 18, net_ip_id);
  net_ip_id++;
  net_store_be16(frame + 20, 0x4000);
  frame[22] = 64;                                            /* TTL */
  frame[23] = 6;                                             /* TCP */
  net_store_be16(frame + 24, 0);                             /* checksum covers itself as 0 */
  net_store_be32(frame + 26, src);
  net_store_be32(frame + 30, dst);
  net_store_be16(frame + 24,
    (uint16_t)kotoba_aiueos_ipv4_checksum((uint64_t)(uintptr_t)(frame + 14), 20));
  net_store_be16(frame + 34, sport);
  net_store_be16(frame + 36, dport);
  net_store_be32(frame + 38, sequence);
  net_store_be32(frame + 42, acknowledgement);
  frame[46] = 0x50;                                          /* data offset 5, no options */
  frame[47] = flags;
  net_store_be16(frame + 48, net_tx_window);
  net_store_be16(frame + 50, 0);                             /* checksum covers itself as 0 */
  net_store_be16(frame + 52, 0);                             /* no urgent data */
  for (uint32_t i = 0; i < payload_length; i++) frame[54 + i] = payload[i];
  net_store_be16(frame + 50, net_tcp_checksum(frame, 20 + payload_length, src, dst));
  /* 54 bytes without a payload, 62 with the echo, 196 with a ClientHello. The
     first is under Ethernet's 60-byte minimum and is emitted unpadded, which
     the ARP request at 42 bytes already showed this device and SLIRP both
     accept -- so nothing here depends on padding that has never been
     exercised. A real NIC on a real wire pads it itself, and the receiver
     ignores the difference because the IPv4 total length, not the frame
     length, says where the datagram ends. */
  return 14 + total;
}

