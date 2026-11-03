/* A valid DHCP reply in frame (frames.h), JUN-552: IPv4/UDP 67 -> 68 with both checksums right (or a zero UDP checksum),
   BOOTREPLY, Ethernet, hlen 6, XID, CHADDR = MAC, YIADDR, the magic cookie, and options from 282: pad bytes, then message
   type TYPE, server id, subnet mask MASK, lease LEASE, an unknown option, and END. Answers the frame length. */
static int dhcp_opt(int at, uint8_t code, uint8_t len, uint32_t value) {
  frame[at] = code; frame[at + 1] = len;
  for (int i = 0; i < len; i++) frame[at + 2 + i] = (uint8_t)(len == 4 ? value >> (24 - 8 * i) : value >> (8 * i));
  return at + 2 + len;
}
static uint32_t dhcp_frame(uint32_t xid, uint64_t mac, uint8_t type, uint32_t yiaddr, uint32_t mask, uint32_t lease, int zero_udp) {
  int at = 282;
  for (unsigned i = (unsigned)(rnd() % 4); i; i--) frame[at++] = 0;
  at = dhcp_opt(at, 53, 1, type);
  at = dhcp_opt(at, 54, 4, (uint32_t)rnd());
  if (rnd() % 2) at = dhcp_opt(at, 200, (uint8_t)(rnd() % 6), (uint32_t)rnd());
  at = dhcp_opt(at, 1, 4, mask);
  at = dhcp_opt(at, 51, 4, lease);
  at = dhcp_opt(at, 6, 4, (uint32_t)rnd());
  at = dhcp_opt(at, 3, 4, (uint32_t)rnd());
  frame[at++] = 255;
  uint32_t udp = (uint32_t)(at - 34) + (uint32_t)(rnd() % 3 ? 0 : rnd() % 40);
  if (udp < 248) udp = 248;
  uint32_t total = udp + 20;
  ipv4(total, 17, (uint32_t)rnd(), (uint32_t)rnd());
  be16(34, 67); be16(36, 68); be16(38, udp);
  frame[42] = 2; frame[43] = 1; frame[44] = 6; be32(46, xid); be32(58, yiaddr);
  be16(70, (uint32_t)(mac >> 32)); be32(72, (uint32_t)mac);
  be32(278, 0x63825363u);
  if (zero_udp) be16(40, 0); else l4_checksum(40, 17, udp);
  return 14 + total;
}
