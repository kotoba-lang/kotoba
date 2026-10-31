/* A valid IPv4 TCP segment in frame (frames.h): total length TOTAL (>= 40), from SRC, the acknowledgement ACK and the
   flags byte FLAGS, both checksums right. JUN-552. */
static void tcp_segment(uint32_t total, uint32_t src, uint32_t ack, uint8_t flags) {
  ipv4(total, 6, src, (uint32_t)rnd());
  be32(42, ack); frame[46] = 0x50; frame[47] = flags;
  l4_checksum(50, 6, total - 20);
}
