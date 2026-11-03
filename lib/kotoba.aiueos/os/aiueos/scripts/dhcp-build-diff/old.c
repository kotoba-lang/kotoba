/* The C net_build_dhcp was before JUN-552 moved it to kotoba/dhcp-build.o: verbatim from kernel/pci.c (main
   daa2b436), with the byte stores and net_udp_checksum it used -- itself a wrapper over kotoba/udp-checksum.o there --
   renamed old_build_dhcp. net_mac is set by old_set. kotoba_aiueos_ipv4_checksum is kotoba/ipv4-checksum.o. */
#include <stdint.h>
#define NET_DHCP_XID 0xa1e05dc0U
#define NET_DHCP_REQUEST 3
#define NET_DHCP_OPTIONS 64
#define NET_DHCP_BOOTP (236 + 4 + NET_DHCP_OPTIONS)
extern uint64_t kotoba_aiueos_ipv4_checksum(uint64_t buffer, uint64_t length);
static uint8_t net_mac[6];
void old_set(const uint8_t mac[6]) { for (int i = 0; i < 6; i++) net_mac[i] = mac[i]; }
static void net_store_be16(uint8_t *at, uint16_t value) {
  at[0] = (uint8_t)(value >> 8); at[1] = (uint8_t)value;
}
static void net_store_be32(uint8_t *at, uint32_t value) {
  at[0] = (uint8_t)(value >> 24); at[1] = (uint8_t)(value >> 16);
  at[2] = (uint8_t)(value >> 8); at[3] = (uint8_t)value;
}

extern int64_t kotoba_aiueos_udp_checksum_sum(uint64_t frame, uint64_t length, uint64_t udp_length);
static uint16_t net_udp_checksum(const uint8_t *frame, uint32_t udp_length) {
  uint16_t sum = (uint16_t)kotoba_aiueos_udp_checksum_sum((uint64_t)(uintptr_t)frame, 34 + (uint64_t)udp_length,
                                                          udp_length);
  /* RFC 768: a computed checksum of zero goes on the wire as all ones, because
     zero already means "not computed". The admission accepts both. */
  return sum ? sum : 0xffff;
}

uint32_t old_build_dhcp(uint8_t *frame, uint8_t message_type,
                               uint32_t requested, uint32_t server) {
  uint32_t udp_length = 8 + NET_DHCP_BOOTP;
  uint32_t total = 20 + udp_length;
  for (uint32_t i = 0; i < 14 + total; i++) frame[i] = 0;
  for (unsigned i = 0; i < 6; i++) frame[i] = 0xff;          /* broadcast */
  for (unsigned i = 0; i < 6; i++) frame[6 + i] = net_mac[i];
  net_store_be16(frame + 12, 0x0800);                        /* EtherType IPv4 */
  frame[14] = 0x45;                                          /* version 4, IHL 5 */
  net_store_be16(frame + 16, (uint16_t)total);
  net_store_be16(frame + 20, 0x4000);                        /* DF, id 0 (RFC 6864) */
  frame[22] = 64;                                            /* TTL */
  frame[23] = 17;                                            /* UDP */
  /* 0.0.0.0 to 255.255.255.255: this machine has no address to send from and
     does not know who to send to, which is the whole reason the exchange
     exists. */
  net_store_be32(frame + 26, 0);
  net_store_be32(frame + 30, 0xffffffffU);
  net_store_be16(frame + 24,
    (uint16_t)kotoba_aiueos_ipv4_checksum((uint64_t)(uintptr_t)(frame + 14), 20));
  net_store_be16(frame + 34, 68);                            /* client port */
  net_store_be16(frame + 36, 67);                            /* server port */
  net_store_be16(frame + 38, (uint16_t)udp_length);
  frame[42] = 1;                                             /* BOOTREQUEST */
  frame[43] = 1;                                             /* Ethernet */
  frame[44] = 6;                                             /* 6-byte address */
  net_store_be32(frame + 46, NET_DHCP_XID);
  /* The broadcast flag. A client with no address configured cannot receive a
     unicast datagram addressed to an address it does not yet hold, so RFC 2131
     has it ask for the reply to be broadcast. */
  net_store_be16(frame + 52, 0x8000);
  for (unsigned i = 0; i < 6; i++) frame[70 + i] = net_mac[i];
  net_store_be32(frame + 278, 0x63825363U);                  /* magic cookie */
  uint32_t at = 282;
  frame[at++] = 53; frame[at++] = 1; frame[at++] = message_type;
  if (message_type == NET_DHCP_REQUEST) {
    /* Both are required in a REQUEST that answers an OFFER: the address being
       accepted, and which server offered it, so that a second server's offer is
       declined by omission rather than by silence. */
    frame[at++] = 50; frame[at++] = 4; net_store_be32(frame + at, requested); at += 4;
    frame[at++] = 54; frame[at++] = 4; net_store_be32(frame + at, server); at += 4;
  }
  /* Parameter request list: subnet mask, router, DNS, lease time. Asking is not
     receiving -- the admission requires the mask, the server identifier and the
     lease regardless of what was asked for. */
  frame[at++] = 55; frame[at++] = 4;
  frame[at++] = 1; frame[at++] = 3; frame[at++] = 6; frame[at++] = 51;
  frame[at++] = 255;                                         /* END */
  net_store_be16(frame + 40, net_udp_checksum(frame, udp_length));
  return 14 + total;
}
