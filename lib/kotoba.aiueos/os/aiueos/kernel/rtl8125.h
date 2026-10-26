/* SPDX-License-Identifier: Apache-2.0 */
#ifndef AIUEOS_RTL8125_H
#define AIUEOS_RTL8125_H

#include <stdint.h>

/* A deliberately small RTL8125 handoff surface.  AIUEOS reaches this driver
   through UEFI PXE, so firmware has already powered the PHY and negotiated the
   link.  The first physical slice takes over one TX and one RX descriptor; it
   does not upload vendor firmware or rewrite PHY calibration. */

#define AIUEOS_RTL8125_FRAME_CAPACITY 2048U

enum aiueos_rtl8125_result {
  AIUEOS_RTL8125_OK = 0,
  AIUEOS_RTL8125_INVALID = 1,
  AIUEOS_RTL8125_UNSUPPORTED_REVISION = 2,
  AIUEOS_RTL8125_INVALID_MAC = 3,
  AIUEOS_RTL8125_FIFO_TIMEOUT = 4,
  AIUEOS_RTL8125_TX_BUSY = 5,
  AIUEOS_RTL8125_RX_INVALID = 6
};

enum aiueos_rtl8125_revision {
  AIUEOS_RTL8125_REV_NONE = 0,
  AIUEOS_RTL8125_REV_8125 = 1,
  AIUEOS_RTL8125_REV_8125B = 2,
  AIUEOS_RTL8125_REV_8125D_1 = 3,
  AIUEOS_RTL8125_REV_8125D_2 = 4
};

struct aiueos_rtl8125_tx_desc {
  volatile uint32_t command;
  volatile uint32_t extension;
  volatile uint64_t address;
  uint32_t reserved[4];
} __attribute__((packed, aligned(16)));

struct aiueos_rtl8125_rx_desc {
  uint64_t low0;
  uint64_t low1;
  volatile uint64_t address;
  volatile uint32_t extension;
  volatile uint32_t command;
} __attribute__((packed, aligned(16)));

struct aiueos_rtl8125_io {
  void *context;
  uint8_t (*read8)(void *, uint32_t);
  uint16_t (*read16)(void *, uint32_t);
  uint32_t (*read32)(void *, uint32_t);
  void (*write8)(void *, uint32_t, uint8_t);
  void (*write16)(void *, uint32_t, uint16_t);
  void (*write32)(void *, uint32_t, uint32_t);
};

struct aiueos_rtl8125 {
  struct aiueos_rtl8125_io io;
  struct aiueos_rtl8125_tx_desc *tx;
  struct aiueos_rtl8125_rx_desc *rx;
  uint8_t *tx_frame;
  uint8_t *rx_frame;
  uint64_t tx_desc_physical;
  uint64_t rx_desc_physical;
  uint64_t tx_frame_physical;
  uint64_t rx_frame_physical;
  uint8_t mac[6];
  uint8_t ready;
  enum aiueos_rtl8125_revision revision;
};

enum aiueos_rtl8125_result aiueos_rtl8125_takeover(
    struct aiueos_rtl8125 *device,
    const struct aiueos_rtl8125_io *io,
    struct aiueos_rtl8125_tx_desc *tx, uint64_t tx_desc_physical,
    struct aiueos_rtl8125_rx_desc *rx, uint64_t rx_desc_physical,
    uint8_t *tx_frame, uint64_t tx_frame_physical,
    uint8_t *rx_frame, uint64_t rx_frame_physical);

/* Stop, drain, and reinstall the already-owned one-descriptor rings without
   rereading the hardware revision or disturbing firmware PHY calibration. */
enum aiueos_rtl8125_result aiueos_rtl8125_restart(
    struct aiueos_rtl8125 *device);

int aiueos_rtl8125_link_up(const struct aiueos_rtl8125 *device);
enum aiueos_rtl8125_result aiueos_rtl8125_tx_submit(
    struct aiueos_rtl8125 *device, uint32_t frame_length);
int aiueos_rtl8125_tx_complete(const struct aiueos_rtl8125 *device);
enum aiueos_rtl8125_result aiueos_rtl8125_rx_poll(
    struct aiueos_rtl8125 *device, uint32_t *frame_length);
void aiueos_rtl8125_rx_rearm(struct aiueos_rtl8125 *device);

/* Pure, peer-bound ARP helpers used by the persistent direct-link worker.
   IPv4 arguments use the same big-endian numeric form as an Ethernet frame,
   for example 10.77.0.10 is 0x0a4d000a. */
int aiueos_rtl8125_direct_arp_request(
    const uint8_t *frame, uint32_t frame_length,
    const uint8_t local_mac[6], const uint8_t peer_mac[6],
    uint32_t local_ip, uint32_t peer_ip);
uint32_t aiueos_rtl8125_direct_arp_reply(
    uint8_t *frame, uint32_t capacity,
    const uint8_t local_mac[6], const uint8_t peer_mac[6],
    uint32_t local_ip, uint32_t peer_ip);

#endif
