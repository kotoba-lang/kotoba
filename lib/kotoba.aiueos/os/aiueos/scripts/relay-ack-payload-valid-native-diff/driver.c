/* relay-ack-payload-valid built on amu's native object route (JUN-708) against the committed kotoba-compiler/1 object.
   The 55-byte ACK "AIUEOS_NODE_ACK_V1 boot=<16 hex> state=accepted" for random nonces (and nonce halves at 0, 2^31 and
   2^32 - 1), then one byte mutated in turn (each position, to a random byte, an upper-case hex digit or a neighbour),
   the expected nonce halves off by one, negative or past 2^32 - 1, lengths other than 55, and a null payload; answers
   and traps compared. */
#include "diff.h"
extern int64_t kotoba_aiueos_relay_ack_payload_valid(int64_t, int64_t, int64_t, int64_t);
extern int64_t kotoba_aiueos_relay_ack_payload_valid_native(int64_t, int64_t, int64_t, int64_t);
static uint8_t p[128] __attribute__((aligned(16)));
void test_main(void) {
  guard_init(); puts_("BUFDIFF\n");
  static const char A[] = "AIUEOS_NODE_ACK_V1 boot=", B[] = " state=accepted";
  void *o = (void *)kotoba_aiueos_relay_ack_payload_valid, *n = (void *)kotoba_aiueos_relay_ack_payload_valid_native;
  for (unsigned k = 0; k < 40000; k++) {
    for (int i = 0; i < 128; i++) p[i] = (uint8_t)rnd();
    static const uint32_t E[] = {0, 1, 0x7fffffffu, 0x80000000u, 0xffffffffu};
    uint32_t hi = rnd() % 4 ? (uint32_t)rnd() : E[rnd() % 5], lo = rnd() % 4 ? (uint32_t)rnd() : E[rnd() % 5];
    for (int i = 0; i < 24; i++) p[i] = (uint8_t)A[i];
    for (int i = 0; i < 8; i++) { unsigned d = (hi >> (28 - 4 * i)) & 15; p[24 + i] = (uint8_t)(d < 10 ? 48 + d : 87 + d); }
    for (int i = 0; i < 8; i++) { unsigned d = (lo >> (28 - 4 * i)) & 15; p[32 + i] = (uint8_t)(d < 10 ? 48 + d : 87 + d); }
    for (int i = 0; i < 15; i++) p[40 + i] = (uint8_t)B[i];
    int64_t len = 55, ehi = hi, elo = lo;
    unsigned m = (unsigned)(rnd() % 8);
    if (m == 1) p[k % 55] = (uint8_t)rnd();
    if (m == 2) { int i = 24 + (int)(rnd() % 16); if (p[i] >= 'a') p[i] = (uint8_t)(p[i] - 32); else p[i] = (uint8_t)(p[i] + 1); }
    if (m == 3) p[rnd() % 55] ^= 1;
    if (m == 4) { if (rnd() % 2) ehi += (int64_t)(rnd() % 3) - 1; else elo += (int64_t)(rnd() % 3) - 1; }
    if (m == 5) { int64_t v = rnd() % 2 ? -1 - (int64_t)(rnd() % 3) : 0x100000000ll + (int64_t)(rnd() % 3); if (rnd() % 2) ehi = v; else elo = v; }
    if (m == 6) len = rnd() % 2 ? 54 + (int64_t)(rnd() % 3) : (int64_t)(rnd() % 600);
    same(o, n, k % 199 == 0 ? 0 : (int64_t)(uintptr_t)p, len, ehi, elo, 0);
  }
  report();
}
