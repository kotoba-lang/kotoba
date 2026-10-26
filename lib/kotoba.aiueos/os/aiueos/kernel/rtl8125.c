/* SPDX-License-Identifier: Apache-2.0 */
#include "rtl8125.h"

/* Register facts and descriptor layouts are cross-checked against the
   ISC-licensed OpenBSD rge(4) interface (if_rgereg.h).  This implementation is
   an AIUEOS-specific, bounded PXE-handoff driver: it keeps the firmware's PHY
   and MCU setup and replaces only the DMA rings after ExitBootServices. */

/* The register offsets, the command bits and the receive-configuration words
   are NOT here any more.  They live in the Kotoba objects that write them --
   `rtl8125-program.kotoba` names each offset at its use site with the
   hexadecimal in a comment, and `aiueos/lib/rtl8125_regs.kotoba` holds the
   revision table and the receive filter (ADR-0140).  Twenty-five `#define`s
   went with them.  The two below survive because C still reads the OWN bit in
   `tx_complete` and the parity self-test still names both in its pinned
   descriptor expectations. */

#define RGE_DESC_OWN 0x80000000U
#define RGE_DESC_EOR 0x40000000U

_Static_assert(sizeof(struct aiueos_rtl8125_tx_desc)==32,"RTL8125 TX descriptor");
_Static_assert(sizeof(struct aiueos_rtl8125_rx_desc)==32,"RTL8125 RX descriptor");

static void bytes_zero(void *value, uint32_t bytes) {
  uint8_t *p = value;
  while (bytes--) *p++ = 0;
}

static uint16_t load_be16(const uint8_t *at) {
  return (uint16_t)(((uint16_t)at[0] << 8) | at[1]);
}

static uint32_t load_be32(const uint8_t *at) {
  return ((uint32_t)at[0] << 24) | ((uint32_t)at[1] << 16) |
         ((uint32_t)at[2] << 8) | at[3];
}

static void store_be16(uint8_t *at, uint16_t value) {
  at[0] = (uint8_t)(value >> 8); at[1] = (uint8_t)value;
}

static void store_be32(uint8_t *at, uint32_t value) {
  at[0] = (uint8_t)(value >> 24); at[1] = (uint8_t)(value >> 16);
  at[2] = (uint8_t)(value >> 8); at[3] = (uint8_t)value;
}

static int mac_equal(const uint8_t *left, const uint8_t *right) {
  uint8_t difference = 0;
  for (unsigned i = 0; i < 6; i++) difference |= left[i] ^ right[i];
  return difference == 0;
}

static int mac_broadcast(const uint8_t *mac) {
  uint8_t all = 0xff;
  for (unsigned i = 0; i < 6; i++) all &= mac[i];
  return all == 0xff;
}

int aiueos_rtl8125_direct_arp_request(
    const uint8_t *frame, uint32_t frame_length,
    const uint8_t local_mac[6], const uint8_t peer_mac[6],
    uint32_t local_ip, uint32_t peer_ip) {
  if (!frame || !local_mac || !peer_mac || frame_length < 42U ||
      !local_ip || !peer_ip) return 0;
  if ((!mac_broadcast(frame) && !mac_equal(frame, local_mac)) ||
      !mac_equal(frame + 6, peer_mac) ||
      load_be16(frame + 12) != 0x0806U ||
      load_be16(frame + 14) != 1U ||
      load_be16(frame + 16) != 0x0800U ||
      frame[18] != 6U || frame[19] != 4U ||
      load_be16(frame + 20) != 1U ||
      !mac_equal(frame + 22, peer_mac) ||
      load_be32(frame + 28) != peer_ip ||
      load_be32(frame + 38) != local_ip) return 0;
  return 1;
}

uint32_t aiueos_rtl8125_direct_arp_reply(
    uint8_t *frame, uint32_t capacity,
    const uint8_t local_mac[6], const uint8_t peer_mac[6],
    uint32_t local_ip, uint32_t peer_ip) {
  if (!frame || capacity < 42U || !local_mac || !peer_mac ||
      !local_ip || !peer_ip) return 0;
  bytes_zero(frame, 42U);
  for (unsigned i = 0; i < 6; i++) {
    frame[i] = peer_mac[i]; frame[6 + i] = local_mac[i];
    frame[22 + i] = local_mac[i]; frame[32 + i] = peer_mac[i];
  }
  store_be16(frame + 12, 0x0806U);
  store_be16(frame + 14, 1U);
  store_be16(frame + 16, 0x0800U);
  frame[18] = 6U; frame[19] = 4U;
  store_be16(frame + 20, 2U);
  store_be32(frame + 28, local_ip);
  store_be32(frame + 38, peer_ip);
  return 42U;
}

#ifndef AIUEOS_RTL8125_ARP_ONLY
/* Everything below this line calls a Kotoba object, and a Kotoba kernel object
   is an `x86_64-aiueos-kernel-v1` ELF.  `scripts/smoke-rtl8125-handoff.sh`
   builds this file with a HOST compiler to exercise the two ARP helpers above,
   and on an arm64 host those objects cannot be linked at all -- so it defines
   AIUEOS_RTL8125_ARP_ONLY and gets the pure-C half.  Nothing in the kernel
   build defines it; the driver and its self-test are always present there. */

/* ==========================================================================
   THE DRIVER, WHICH IS NOW SEQUENCING (ADR-0140)
   ==========================================================================
   Every function below used to write registers and descriptor fields itself.
   They call Kotoba objects now, and what remains in C is the two things an
   object cannot do:

     * hold the struct -- which pointers and physical addresses this device is
       using, its MAC, its revision, whether it has been taken over.  A kernel
       object's loads and stores must be based on a literal, `kernel-boot-info`
       or an ARGUMENT, so a device handle it could read a BAR address back out
       of is not expressible; the handle stays here and its fields arrive as
       arguments.
     * sequence one object after another.  `rings_restart` is stop -> drain ->
       build both descriptors -> program -> enable, and a kernel object cannot
       call another kernel object, so the interleaving is here.

   `struct aiueos_rtl8125_io`'s six function pointers are NO LONGER CALLED by
   this driver.  The objects reach the device through `io.context`, which on
   this path is the BAR's physical address itself (kernel/pci.c:4068 builds it
   as `(void *)(uintptr_t)bar`).  The pointers are still required to be present
   because the header declares them and a caller that left them null has
   misunderstood the handoff, and because the parity self-test below still uses
   an io vtable of its own.

   WHAT WENT AWAY: `revision_from_txcfg`, `receive_config`, `mac_valid`, the
   sixteen register offsets, the eight command/status bit masks, the MAC
   assembly, the FIFO drain loop, the descriptor stores, the release and
   acquire fences.  `RGE_DESC_OWN` and `RGE_DESC_EOR` survive because
   `tx_complete` and the self-test's pinned table still name them.  */

/* `aiueos_map_pci_mmio(bar, 4096)` (kernel/pci.c:4056) maps exactly one page
   per BAR, and the objects refuse any other length -- so this is not a bound
   they check against, it is the length the mapping actually has. */
#define RTL_MMIO_WINDOW 4096U
#define RTL_DESC_BYTES 32U

extern uint64_t kotoba_aiueos_rtl8125_identify(uint64_t, uint64_t, uint64_t,
                                               uint64_t);
extern uint64_t kotoba_aiueos_rtl8125_link_up(uint64_t, uint64_t);
extern uint64_t kotoba_aiueos_rtl8125_ring_build(uint64_t, uint64_t, uint64_t,
                                                 uint64_t, uint64_t);
extern uint64_t kotoba_aiueos_rtl8125_program(uint64_t, uint64_t, uint64_t,
                                              uint64_t, uint64_t);
extern uint64_t kotoba_aiueos_rtl8125_tx_submit(uint64_t, uint64_t, uint64_t,
                                                uint64_t, uint64_t);
extern int64_t kotoba_aiueos_rtl8125_rx_poll(uint64_t, uint64_t);

static int io_valid(const struct aiueos_rtl8125_io *io) {
  return io && io->context && io->read8 && io->read16 && io->read32 &&
         io->write8 && io->write16 && io->write32;
}

static void dma_acquire(void) {
  __atomic_thread_fence(__ATOMIC_ACQUIRE);
}

/* rtl8125.c's old `rings_restart`, as four object calls.  The order is the
   whole function: the engine is stopped and its transmit FIFO drained BEFORE
   the descriptors are rewritten, because on a restart the ring registers still
   point at these very descriptors and rewriting an address the hardware owns
   is how a frame lands in a buffer the kernel has handed on.
   `aiueos-rtl8125-program` takes 0 for the stop phase and the revision for the
   program phase; that is why it is one symbol and not two. */
static enum aiueos_rtl8125_result rings_restart(
    struct aiueos_rtl8125 *device) {
  const uint64_t mmio = (uint64_t)(uintptr_t)device->io.context;
  uint64_t reason = kotoba_aiueos_rtl8125_program(mmio, RTL_MMIO_WINDOW, 0, 0, 0);
  if (reason) {
    /* The C set this on the FIFO-timeout path and callers depend on it: a
       device that would not drain is not one this kernel keeps using. */
    device->ready = 0;
    return (enum aiueos_rtl8125_result)reason;
  }
  reason = kotoba_aiueos_rtl8125_ring_build(
    (uint64_t)(uintptr_t)device->tx, RTL_DESC_BYTES,
    device->tx_frame_physical, 0, AIUEOS_RTL8125_FRAME_CAPACITY);
  if (reason) return (enum aiueos_rtl8125_result)reason;
  reason = kotoba_aiueos_rtl8125_ring_build(
    (uint64_t)(uintptr_t)device->rx, RTL_DESC_BYTES,
    device->rx_frame_physical, 1, AIUEOS_RTL8125_FRAME_CAPACITY);
  if (reason) return (enum aiueos_rtl8125_result)reason;
  return (enum aiueos_rtl8125_result)kotoba_aiueos_rtl8125_program(
    mmio, RTL_MMIO_WINDOW, device->tx_desc_physical, device->rx_desc_physical,
    (uint64_t)device->revision);
}

enum aiueos_rtl8125_result aiueos_rtl8125_takeover(
    struct aiueos_rtl8125 *device,
    const struct aiueos_rtl8125_io *io,
    struct aiueos_rtl8125_tx_desc *tx, uint64_t tx_desc_physical,
    struct aiueos_rtl8125_rx_desc *rx, uint64_t rx_desc_physical,
    uint8_t *tx_frame, uint64_t tx_frame_physical,
    uint8_t *rx_frame, uint64_t rx_frame_physical) {
  /* The descriptor alignment and non-zero checks the C made here are made by
     the objects instead, and with the same answer: `desc-ok` refuses a null or
     un-256-aligned base and both `ring-build` and `program` return 1, which IS
     AIUEOS_RTL8125_INVALID.  What is left here is the pointers, which no
     object sees. */
  if (!device || !io_valid(io) || !tx || !rx || !tx_frame || !rx_frame ||
      !tx_frame_physical || !rx_frame_physical)
    return AIUEOS_RTL8125_INVALID;

  /* `identify` writes a 16-byte record: the revision code at 0 and the six MAC
     bytes at 8, in wire order.  It reads TXCFG before anything writes it,
     which is the only moment the revision bits are readable at all. */
  _Alignas(16) uint8_t identity[16] = {0};
  uint64_t reason = kotoba_aiueos_rtl8125_identify(
    (uint64_t)(uintptr_t)io->context, RTL_MMIO_WINDOW,
    (uint64_t)(uintptr_t)identity, sizeof(identity));
  if (reason) return (enum aiueos_rtl8125_result)reason;

  *device = (struct aiueos_rtl8125){0};
  device->io = *io; device->tx = tx; device->rx = rx;
  device->tx_frame = tx_frame; device->rx_frame = rx_frame;
  device->tx_desc_physical = tx_desc_physical;
  device->rx_desc_physical = rx_desc_physical;
  device->tx_frame_physical = tx_frame_physical;
  device->rx_frame_physical = rx_frame_physical;
  for (unsigned i = 0; i < 6; i++) device->mac[i] = identity[8 + i];
  device->revision = (enum aiueos_rtl8125_revision)identity[0];
  device->ready = 1;
  return rings_restart(device);
}

enum aiueos_rtl8125_result aiueos_rtl8125_restart(
    struct aiueos_rtl8125 *device) {
  if (!device || !device->ready || !io_valid(&device->io) ||
      !device->tx || !device->rx || !device->tx_frame || !device->rx_frame ||
      !device->tx_desc_physical || !device->rx_desc_physical ||
      !device->tx_frame_physical || !device->rx_frame_physical ||
      device->revision < AIUEOS_RTL8125_REV_8125 ||
      device->revision > AIUEOS_RTL8125_REV_8125D_2)
    return AIUEOS_RTL8125_INVALID;
  return rings_restart(device);
}

int aiueos_rtl8125_link_up(const struct aiueos_rtl8125 *device) {
  return device && device->ready &&
    (int)kotoba_aiueos_rtl8125_link_up(
      (uint64_t)(uintptr_t)device->io.context, RTL_MMIO_WINDOW);
}

enum aiueos_rtl8125_result aiueos_rtl8125_tx_submit(
    struct aiueos_rtl8125 *device, uint32_t frame_length) {
  if (!device || !device->ready) return AIUEOS_RTL8125_INVALID;
  /* The 14..2048 bound, the OWN test, the acquire fence, the two release
     fences and the doorbell are all inside the object.  So is TX_BUSY. */
  return (enum aiueos_rtl8125_result)kotoba_aiueos_rtl8125_tx_submit(
    (uint64_t)(uintptr_t)device->io.context, RTL_MMIO_WINDOW,
    (uint64_t)(uintptr_t)device->tx, device->tx_frame_physical, frame_length);
}

/* The one status read left in C.  It is one bit of one word and it has no
   decision in it -- the caller's question is "may I submit again", and the
   answer is the OWN bit -- so it did not earn a seventh export name. */
int aiueos_rtl8125_tx_complete(const struct aiueos_rtl8125 *device) {
  if (!device || !device->ready) return 0;
  dma_acquire();
  return !(device->tx->command & RGE_DESC_OWN);
}

/* NOT ZERO-IS-SUCCESS ON THE OBJECT SIDE.  `aiueos-rtl8125-rx-poll` answers
   with a non-negative LENGTH (zero = the descriptor is still device-owned,
   which is the C's `*frame_length = 0` with OK) or a negative reason code,
   because a length and a reason cannot share a non-negative value space and an
   object has one i64 to answer with.  This restores the C's shape. */
enum aiueos_rtl8125_result aiueos_rtl8125_rx_poll(
    struct aiueos_rtl8125 *device, uint32_t *frame_length) {
  if (!device || !device->ready || !frame_length)
    return AIUEOS_RTL8125_INVALID;
  int64_t answer = kotoba_aiueos_rtl8125_rx_poll(
    (uint64_t)(uintptr_t)device->rx, AIUEOS_RTL8125_FRAME_CAPACITY);
  if (answer < 0) return (enum aiueos_rtl8125_result)(-answer);
  *frame_length = (uint32_t)answer;
  return AIUEOS_RTL8125_OK;
}

/* Rearming a receive descriptor is building one: the same address store, the
   same release fence, the same OWN|EOR|capacity command.  The C spelled them
   as two functions only because one of them also cleared the status words the
   hardware wrote, and clearing those is safe on both paths -- the device
   overwrites them the moment OWN is set. */
void aiueos_rtl8125_rx_rearm(struct aiueos_rtl8125 *device) {
  if (!device || !device->ready) return;
  (void)kotoba_aiueos_rtl8125_ring_build(
    (uint64_t)(uintptr_t)device->rx, RTL_DESC_BYTES,
    device->rx_frame_physical, 1, AIUEOS_RTL8125_FRAME_CAPACITY);
}

/* ==========================================================================
   THE KOTOBA PARITY SELF-TEST (ADR-0140)
   ==========================================================================
   Six Kotoba objects now express this driver's register sequence, its
   descriptor layouts and its status decisions.  QEMU has no RTL8125 model, so
   the evidence that they say what the C above says is this: run BOTH against a
   SOFTWARE MODEL of the BAR -- 4,096 bytes of ordinary memory seeded so that
   each register read returns what a real RTL8125B returns at that point -- and
   compare the bytes each leaves behind.

   That catches width and offset errors, which is most of what a driver gets
   wrong: a `write16` where the hardware wants a `write32` leaves two neighbours
   different, and an offset off by four writes into a register nobody meant.

   WHAT IT DOES NOT CATCH, said plainly rather than left to be discovered.  A
   memory model has no time in it, so the ORDER two writes happen in is
   invisible whenever both survive to the end.  Three things recover part of
   that and none of them recovers all of it:

     * The FIFO-drain stage seeds MCUCMD so the engine never reports empty.
       Both implementations must then return FIFO_TIMEOUT and must leave
       RGE_CMD at 0x8c -- the STOP bit set and the register NOT cleared.  That
       is an ordering assertion: the drain gate happens after the stop and
       before everything downstream of it.
     * The TX_BUSY stage submits twice.  The second must refuse, which is only
       true if the first actually set the OWN bit before the doorbell.
     * The store fences themselves are checked as EMITTED BYTES, not here:
       `verify-kotoba-kernel-object.py` sees the objects, and
       `rtl8125-ring-build.o` / `-tx-submit.o` contain `sfence` (0f ae f8).
       A fence writes no memory, so no memory comparison can ever see one.

   The seed values are not invented here.  `tests/rtl8125_handoff_model.c`:23-25
   already seeds MAC0 = 0x0bfc7070, MAC4 = 0x32b6, TXCFG = 0x64100000 and
   PHYSTAT = 0x0013, and asserts the resulting register file at :63-68.  So the
   fixture is the repository's own and a disagreement is a disagreement with a
   test that predates these objects.
   ========================================================================== */


#define RTL_PARITY_BAR_BYTES 4096U
#define RTL_PARITY_DESC_BYTES 32U
/* The frames are never read or written by anything -- no DMA engine exists in
   this model -- so only their ADDRESSES matter, and 64 bytes is enough to have
   one.  Sized down from AIUEOS_RTL8125_FRAME_CAPACITY deliberately: 4 KiB of
   .bss for a buffer nothing touches is 4 KiB the kernel does not have. */
#define RTL_PARITY_FRAME_BYTES 64U

/* In .high_bss, not .bss: the production node image's low region was at
   exactly `aiueos_low_end == 0x1f4000` when linear_attention's output norm
   moved into the norm object (aiueos ADR-0222), and those 792 bytes crossed a
   page.  This buffer is zeroed by `rtl_parity_seed` before every use and is
   only ever read through its address, so where it lives is not observable. */
static uint8_t rtl_parity_bar[RTL_PARITY_BAR_BYTES]
    __attribute__((section(".high_bss"), aligned(4096)));
static struct aiueos_rtl8125_tx_desc rtl_parity_tx __attribute__((aligned(256)));
static struct aiueos_rtl8125_rx_desc rtl_parity_rx __attribute__((aligned(256)));
static uint8_t rtl_parity_txframe[RTL_PARITY_FRAME_BYTES] __attribute__((aligned(64)));
static uint8_t rtl_parity_rxframe[RTL_PARITY_FRAME_BYTES] __attribute__((aligned(64)));
static struct aiueos_rtl8125 rtl_parity_device;

/* The stage that failed, 0 when every stage passed, and a byte offset when the
   failure was a byte comparison.  Globals rather than out-parameters so main.c
   can print them without this file owning a printer. */
unsigned aiueos_rtl8125_parity_stage;
unsigned aiueos_rtl8125_parity_detail;

static uint8_t rtl_parity_r8(void *c, uint32_t o) {
  return ((const volatile uint8_t *)c)[o];
}
static uint16_t rtl_parity_r16(void *c, uint32_t o) {
  const volatile uint8_t *p = (const volatile uint8_t *)c + o;
  return (uint16_t)((uint16_t)p[0] | ((uint16_t)p[1] << 8));
}
static uint32_t rtl_parity_r32(void *c, uint32_t o) {
  const volatile uint8_t *p = (const volatile uint8_t *)c + o;
  return (uint32_t)p[0] | ((uint32_t)p[1] << 8) | ((uint32_t)p[2] << 16) |
         ((uint32_t)p[3] << 24);
}
static void rtl_parity_w8(void *c, uint32_t o, uint8_t v) {
  ((volatile uint8_t *)c)[o] = v;
}
static void rtl_parity_w16(void *c, uint32_t o, uint16_t v) {
  volatile uint8_t *p = (volatile uint8_t *)c + o;
  p[0] = (uint8_t)v; p[1] = (uint8_t)(v >> 8);
}
static void rtl_parity_w32(void *c, uint32_t o, uint32_t v) {
  volatile uint8_t *p = (volatile uint8_t *)c + o;
  p[0] = (uint8_t)v; p[1] = (uint8_t)(v >> 8);
  p[2] = (uint8_t)(v >> 16); p[3] = (uint8_t)(v >> 24);
}

static void rtl_parity_seed(void) {
  bytes_zero(rtl_parity_bar, RTL_PARITY_BAR_BYTES);
  rtl_parity_bar[0x00] = 0x70; rtl_parity_bar[0x01] = 0x70;
  rtl_parity_bar[0x02] = 0xfc; rtl_parity_bar[0x03] = 0x0b; /* MAC0 */
  rtl_parity_bar[0x04] = 0xb6; rtl_parity_bar[0x05] = 0x32; /* MAC4 */
  rtl_parity_bar[0x42] = 0x10; rtl_parity_bar[0x43] = 0x64; /* TXCFG 8125B */
  rtl_parity_bar[0x6c] = 0x13;                              /* PHYSTAT: link */
  rtl_parity_bar[0x37] = 0x0c;                              /* CMD: TX|RX */
  rtl_parity_bar[0xd3] = 0x30;                              /* MCUCMD: FIFO empty */
}

static void rtl_parity_fill(uint8_t *at, unsigned bytes, uint8_t value) {
  for (unsigned i = 0; i < bytes; i++) at[i] = value;
}

static int rtl_parity_agree(const uint8_t *a, const uint8_t *b, unsigned bytes,
                            unsigned stage) {
  for (unsigned i = 0; i < bytes; i++)
    if (a[i] != b[i]) {
      aiueos_rtl8125_parity_stage = stage;
      aiueos_rtl8125_parity_detail = i;
      return 0;
    }
  return 1;
}

/* The register file this driver leaves behind, written out.
 *
 * It exists so the parity above is not the ONLY evidence.  A comparison
 * between two implementations says they agree; it does not say they are right,
 * and once the C bodies delegate to these objects the comparison would be
 * between an implementation and itself.  This table is checked against BOTH
 * while both still exist, so the day the C goes away it is a claim that was
 * measured against the C rather than transcribed from the Kotoba.
 *
 * Only the fixed bytes are here.  The four ring-address registers hold
 * addresses this kernel chooses at link time and are checked separately, and
 * every byte not named here or in that range must be zero -- which is the half
 * that catches a stray write into a register nobody meant to touch.
 */
struct rtl_parity_pin { uint16_t offset; uint8_t value; };
static const struct rtl_parity_pin rtl_parity_pins[] = {
  {0x00, 0x70}, {0x01, 0x70}, {0x02, 0xfc},     /* MAC0, seeded, never written */
  {0x03, 0x0b}, {0x04, 0xb6}, {0x05, 0x32},     /* MAC4 */
  {0x37, 0x0c},                                 /* RGE_CMD = TX|RX, written last */
  {0x3c, 0xff}, {0x3d, 0xff},                   /* RGE_ISR = 0xffffffff */
  {0x3e, 0xff}, {0x3f, 0xff},
  {0x41, 0x07}, {0x43, 0x03},                   /* RGE_TXCFG = 0x03000700 */
  {0x44, 0x0a}, {0x45, 0x0c}, {0x47, 0x41},     /* RGE_RXCFG = 0x41000c0a */
  {0x6c, 0x13},                                 /* RGE_PHYSTAT, seeded */
  {0xd3, 0x30},                                 /* RGE_MCUCMD, seeded */
  {0xdb, 0x08}                                  /* RGE_RXMAXSIZE = 0x0800 */
};
/* RGE_IMR (0x38) is deliberately absent: it is written, and written to ZERO,
   so the "everything else is zero" sweep is what asserts it. */
#define RTL_PARITY_ADDRESS_REGISTER(offset) \
  (((offset) >= 0x20 && (offset) < 0x28) || ((offset) >= 0xe4 && (offset) < 0xec))

static int rtl_parity_pinned(uint64_t txd, uint64_t rxd, unsigned stage) {
  for (unsigned i = 0; i < sizeof(rtl_parity_pins)/sizeof(rtl_parity_pins[0]); i++)
    if (rtl_parity_bar[rtl_parity_pins[i].offset] != rtl_parity_pins[i].value) {
      aiueos_rtl8125_parity_stage = stage;
      aiueos_rtl8125_parity_detail = rtl_parity_pins[i].offset;
      return 0;
    }
  for (unsigned offset = 0; offset < RTL_PARITY_BAR_BYTES; offset++) {
    unsigned named = 0;
    if (RTL_PARITY_ADDRESS_REGISTER(offset)) continue;
    for (unsigned i = 0; i < sizeof(rtl_parity_pins)/sizeof(rtl_parity_pins[0]); i++)
      if (rtl_parity_pins[i].offset == offset) { named = 1; break; }
    if (!named && rtl_parity_bar[offset]) {
      aiueos_rtl8125_parity_stage = stage + 1;
      aiueos_rtl8125_parity_detail = offset;
      return 0;
    }
  }
  if (rtl_parity_r32(rtl_parity_bar, 0x20) != (uint32_t)txd ||
      rtl_parity_r32(rtl_parity_bar, 0x24) != (uint32_t)(txd >> 32) ||
      rtl_parity_r32(rtl_parity_bar, 0xe4) != (uint32_t)rxd ||
      rtl_parity_r32(rtl_parity_bar, 0xe8) != (uint32_t)(rxd >> 32)) {
    aiueos_rtl8125_parity_stage = stage + 2;
    return 0;
  }
  /* The descriptors, in full.  A transmit descriptor is RGE_DESC_EOR and the
     frame address; a receive descriptor is OWN|EOR|capacity and its own. */
  if (rtl_parity_tx.command != RGE_DESC_EOR ||
      rtl_parity_tx.extension != 0 ||
      rtl_parity_tx.address != (uint64_t)(uintptr_t)rtl_parity_txframe) {
    aiueos_rtl8125_parity_stage = stage + 3;
    return 0;
  }
  if (rtl_parity_rx.command !=
        (RGE_DESC_OWN | RGE_DESC_EOR | AIUEOS_RTL8125_FRAME_CAPACITY) ||
      rtl_parity_rx.extension != 0 ||
      rtl_parity_rx.address != (uint64_t)(uintptr_t)rtl_parity_rxframe ||
      rtl_parity_rx.low0 != 0 || rtl_parity_rx.low1 != 0) {
    aiueos_rtl8125_parity_stage = stage + 4;
    return 0;
  }
  return 1;
}

#define RTL_PARITY_REQUIRE(condition, stage_number)      \
  do {                                                   \
    if (!(condition)) {                                  \
      aiueos_rtl8125_parity_stage = (stage_number);      \
      return 0;                                          \
    }                                                    \
  } while (0)

/* WHAT CHANGED WHEN THE C WAS FLIPPED.
 *
 * Until the commit that made the bodies above delegate, this ran the C driver
 * and the objects against two copies of the same seeded model and compared
 * every byte.  That comparison is gone, and not because it stopped passing --
 * it stopped MEANING anything.  `aiueos_rtl8125_takeover` now calls the same
 * objects, so comparing them would be comparing one implementation with
 * itself, which is the shape a test takes when it can no longer fail.
 *
 * What replaces it is the table `rtl_parity_pinned` checks, and the table is
 * not a transcription of what these objects do: it was written before the
 * flip, checked against the REAL C driver in the same boot, and the QEMU run
 * that reported `NIC-PARITY ok` at that commit is what measured it.  It is
 * kept here so that the register file this driver leaves behind is asserted
 * value by value rather than asserted to equal itself.
 *
 * Everything else in this function survives unchanged in kind, because none of
 * it was ever a C-versus-Kotoba comparison: a submission that must set OWN
 * before the doorbell, a second submission that must therefore refuse, three
 * receive-completion verdicts, a rearm, a FIFO that never drains, and two
 * argument refusals.  Those assert the driver's behaviour, and they fail when
 * it is wrong regardless of which language expresses it.
 */
int aiueos_rtl8125_kotoba_selftest(void) {
  const uint64_t txd = (uint64_t)(uintptr_t)&rtl_parity_tx;
  const uint64_t rxd = (uint64_t)(uintptr_t)&rtl_parity_rx;
  const uint64_t txf = (uint64_t)(uintptr_t)rtl_parity_txframe;
  const uint64_t rxf = (uint64_t)(uintptr_t)rtl_parity_rxframe;
  const uint64_t bar = (uint64_t)(uintptr_t)rtl_parity_bar;
  _Alignas(16) uint8_t identity[16];
  struct aiueos_rtl8125_io io = {
    rtl_parity_bar, rtl_parity_r8, rtl_parity_r16, rtl_parity_r32,
    rtl_parity_w8, rtl_parity_w16, rtl_parity_w32
  };
  uint32_t received;

  aiueos_rtl8125_parity_stage = 0;
  aiueos_rtl8125_parity_detail = 0;

  /* ---- 1. takeover, which is now four object calls and a struct ---------- */
  /* The descriptors start filled with 0xff rather than zeroed, so a path that
     failed to write a field leaves 0xff where the table expects 0.  A zeroed
     start would let an unwritten field agree by accident. */
  rtl_parity_seed();
  rtl_parity_fill((uint8_t *)&rtl_parity_tx, RTL_PARITY_DESC_BYTES, 0xff);
  rtl_parity_fill((uint8_t *)&rtl_parity_rx, RTL_PARITY_DESC_BYTES, 0xff);
  RTL_PARITY_REQUIRE(
    aiueos_rtl8125_takeover(&rtl_parity_device, &io, &rtl_parity_tx, txd,
                            &rtl_parity_rx, rxd, rtl_parity_txframe, txf,
                            rtl_parity_rxframe, rxf) == AIUEOS_RTL8125_OK, 1);
  RTL_PARITY_REQUIRE(rtl_parity_device.revision == AIUEOS_RTL8125_REV_8125B, 2);
  {
    static const uint8_t expected_mac[6] = {0x70, 0x70, 0xfc, 0x0b, 0xb6, 0x32};
    if (!rtl_parity_agree(rtl_parity_device.mac, expected_mac, 6, 3)) return 0;
  }
  RTL_PARITY_REQUIRE(aiueos_rtl8125_link_up(&rtl_parity_device) != 0, 4);

  /* ---- 2. every register and both descriptors, value by value ----------- */
  if (!rtl_parity_pinned(txd, rxd, 36)) return 0;

  /* ---- 3. transmit submission ------------------------------------------- */
  RTL_PARITY_REQUIRE(aiueos_rtl8125_tx_submit(&rtl_parity_device, 60) ==
                     AIUEOS_RTL8125_OK, 13);
  /* OWN|EOR|SOF|EOF|length.  The length is in the command word, not a separate
     field, which is why a submission with the wrong width would still set the
     flags and still transmit -- the wrong number of bytes. */
  RTL_PARITY_REQUIRE(rtl_parity_tx.command == (0xf0000000U | 60U), 14);
  RTL_PARITY_REQUIRE(rtl_parity_tx.extension == 0, 15);
  RTL_PARITY_REQUIRE(rtl_parity_tx.address == txf, 16);
  RTL_PARITY_REQUIRE(rtl_parity_r16(rtl_parity_bar, 0x90) == 1, 17);
  RTL_PARITY_REQUIRE(aiueos_rtl8125_tx_complete(&rtl_parity_device) == 0, 18);

  /* The descriptor is now owned by the device, so a second submission must
     refuse -- which is only true if the first one really set the OWN bit
     before ringing the doorbell.  This is the ordering assertion a memory
     model can make. */
  RTL_PARITY_REQUIRE(aiueos_rtl8125_tx_submit(&rtl_parity_device, 60) ==
                     AIUEOS_RTL8125_TX_BUSY, 19);
  /* And the bounds, which are the object's and no longer this file's. */
  rtl_parity_tx.command &= ~RGE_DESC_OWN;
  RTL_PARITY_REQUIRE(aiueos_rtl8125_tx_complete(&rtl_parity_device) == 1, 20);
  RTL_PARITY_REQUIRE(aiueos_rtl8125_tx_submit(&rtl_parity_device, 13) ==
                     AIUEOS_RTL8125_INVALID, 21);
  RTL_PARITY_REQUIRE(aiueos_rtl8125_tx_submit(&rtl_parity_device, 2049) ==
                     AIUEOS_RTL8125_INVALID, 22);

  /* ---- 4. receive completion -------------------------------------------- */
  received = 0xffffffffU;
  RTL_PARITY_REQUIRE(aiueos_rtl8125_rx_poll(&rtl_parity_device, &received) ==
                       AIUEOS_RTL8125_OK && received == 0, 23);

  /* A 68-byte completion: 64 bytes of frame plus the four FCS bytes the
     hardware leaves in the buffer.  tests/rtl8125_handoff_model.c:45 uses this
     exact command word and :48 asserts 64. */
  rtl_parity_rx.command = 0x43000000U | 68U;
  received = 0;
  RTL_PARITY_REQUIRE(aiueos_rtl8125_rx_poll(&rtl_parity_device, &received) ==
                       AIUEOS_RTL8125_OK && received == 64, 24);

  /* The four refusals a completed descriptor can earn: the error flag, a
     missing start-of-frame, a missing end-of-frame, and a length below an
     Ethernet header plus its FCS.  All four are the object's decision. */
  rtl_parity_rx.command = 0x43100044U;
  RTL_PARITY_REQUIRE(aiueos_rtl8125_rx_poll(&rtl_parity_device, &received) ==
                     AIUEOS_RTL8125_RX_INVALID, 25);
  rtl_parity_rx.command = 0x41000044U;
  RTL_PARITY_REQUIRE(aiueos_rtl8125_rx_poll(&rtl_parity_device, &received) ==
                     AIUEOS_RTL8125_RX_INVALID, 26);
  rtl_parity_rx.command = 0x42000044U;
  RTL_PARITY_REQUIRE(aiueos_rtl8125_rx_poll(&rtl_parity_device, &received) ==
                     AIUEOS_RTL8125_RX_INVALID, 27);
  rtl_parity_rx.command = 0x43000011U;
  RTL_PARITY_REQUIRE(aiueos_rtl8125_rx_poll(&rtl_parity_device, &received) ==
                     AIUEOS_RTL8125_RX_INVALID, 28);

  aiueos_rtl8125_rx_rearm(&rtl_parity_device);
  RTL_PARITY_REQUIRE(rtl_parity_rx.command ==
                     (RGE_DESC_OWN | RGE_DESC_EOR | AIUEOS_RTL8125_FRAME_CAPACITY), 29);
  RTL_PARITY_REQUIRE(rtl_parity_rx.extension == 0, 30);
  RTL_PARITY_REQUIRE(rtl_parity_rx.address == rxf, 31);

  /* ---- 5. the drain gate, which is the other ordering assertion ---------- */
  /* Seeded so the transmit FIFO never reports empty.  The driver must spend
     its budget and refuse, must leave RGE_CMD at 0x8c -- the STOP bit set by
     the first write and NOT cleared by the write that follows a successful
     drain -- and must clear `ready`.  A port that cleared RGE_CMD before
     waiting, or waited before stopping, leaves 0x00 or 0x0c here. */
  /* restart=bounded-fifo-flush -- the assertion the host model test used to
     make under that name, now made against the emitted objects. */
  rtl_parity_seed();
  rtl_parity_bar[0xd3] = 0x00;
  RTL_PARITY_REQUIRE(aiueos_rtl8125_restart(&rtl_parity_device) ==
                     AIUEOS_RTL8125_FIFO_TIMEOUT, 32);
  RTL_PARITY_REQUIRE(rtl_parity_bar[0x37] == 0x8c, 33);
  RTL_PARITY_REQUIRE(rtl_parity_device.ready == 0, 34);
  RTL_PARITY_REQUIRE(aiueos_rtl8125_link_up(&rtl_parity_device) == 0, 35);

  /* ---- 6. argument refusals the public API cannot reach ------------------ */
  /* A half-page window and a misaligned descriptor.  Neither is expressible
     through `takeover`, because the driver supplies both -- so they are
     checked against the objects directly, which is also the only place in this
     file that still names one. */
  rtl_parity_fill((uint8_t *)&rtl_parity_tx, RTL_PARITY_DESC_BYTES, 0xff);
  rtl_parity_fill(identity, sizeof(identity), 0);
  RTL_PARITY_REQUIRE(kotoba_aiueos_rtl8125_identify(
                       bar, 2048, (uint64_t)(uintptr_t)identity,
                       sizeof(identity)) == AIUEOS_RTL8125_INVALID, 41);
  RTL_PARITY_REQUIRE(identity[0] == 0 && identity[8] == 0, 42);
  RTL_PARITY_REQUIRE(kotoba_aiueos_rtl8125_ring_build(
                       txd + 16, RTL_PARITY_DESC_BYTES, txf, 0,
                       AIUEOS_RTL8125_FRAME_CAPACITY) ==
                     AIUEOS_RTL8125_INVALID, 43);
  RTL_PARITY_REQUIRE(kotoba_aiueos_rtl8125_ring_build(
                       txd, RTL_PARITY_DESC_BYTES, txf, 2,
                       AIUEOS_RTL8125_FRAME_CAPACITY) ==
                     AIUEOS_RTL8125_INVALID, 44);
  for (unsigned i = 0; i < RTL_PARITY_DESC_BYTES; i++)
    RTL_PARITY_REQUIRE(((const uint8_t *)&rtl_parity_tx)[i] == 0xff, 45);

  return 1;
}
#endif /* AIUEOS_RTL8125_ARP_ONLY */
