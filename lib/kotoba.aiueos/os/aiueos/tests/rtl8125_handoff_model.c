/* SPDX-License-Identifier: Apache-2.0 */
/* What is left of this test, and why.
 *
 * It used to drive the whole RTL8125 handoff against a fake BAR: takeover,
 * revision, MAC, ring installation, transmit submission, receive completion,
 * rearm and a bounded FIFO flush.  Those bodies are Kotoba objects now
 * (ADR-0140), and a Kotoba kernel object is an `x86_64-aiueos-kernel-v1` ELF
 * that a host compiler on an arm64 machine cannot link -- so the half of this
 * file that called them cannot be built here at all.
 *
 * The coverage did not go away, it moved and got stronger:
 * `aiueos_rtl8125_kotoba_selftest` in `kernel/rtl8125.c` runs the EMITTED
 * MACHINE CODE against a software model of the BAR on every UEFI boot and
 * prints `NIC-PARITY` on the serial console, which is a claim about the
 * artifact rather than about a host recompilation of the source.
 *
 * What remains here is the part that is still ordinary C and still testable
 * without a device: the two peer-bound ARP helpers.  They are pure functions
 * over a frame buffer, they are called on the direct-link path in
 * `kernel/pci.c`, and a host run of them is worth having because it is the
 * cheapest place to catch an offset error in a 42-byte frame. */
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "rtl8125.h"

static void be16(uint8_t*p,uint16_t v){p[0]=(uint8_t)(v>>8);p[1]=(uint8_t)v;}
static void be32(uint8_t*p,uint32_t v){p[0]=(uint8_t)(v>>24);p[1]=(uint8_t)(v>>16);p[2]=(uint8_t)(v>>8);p[3]=(uint8_t)v;}

#define CHECK(x) do { if (!(x)) { fprintf(stderr,"FAIL line=%d expr=%s\n",__LINE__,#x); return 1; } } while(0)

int main(void) {
  const uint8_t local_mac[6]={0x70,0x70,0xfc,0x0b,0xb6,0x32};
  const uint8_t peer_mac[6]={0x80,0x69,0x1a,0x17,0x4f,0x15};
  uint8_t arp[64]={0};
  memset(arp,0xff,6);memcpy(arp+6,peer_mac,6);
  be16(arp+12,0x0806);be16(arp+14,1);be16(arp+16,0x0800);
  arp[18]=6;arp[19]=4;be16(arp+20,1);memcpy(arp+22,peer_mac,6);
  be32(arp+28,0x0a4d0001U);be32(arp+38,0x0a4d000aU);
  CHECK(aiueos_rtl8125_direct_arp_request(
        arp,42,local_mac,peer_mac,0x0a4d000aU,0x0a4d0001U));
  CHECK(!aiueos_rtl8125_direct_arp_request(
        arp,41,local_mac,peer_mac,0x0a4d000aU,0x0a4d0001U));
  arp[21]=2;
  CHECK(!aiueos_rtl8125_direct_arp_request(
        arp,42,local_mac,peer_mac,0x0a4d000aU,0x0a4d0001U));
  arp[21]=1;arp[41]=2;
  CHECK(!aiueos_rtl8125_direct_arp_request(
        arp,42,local_mac,peer_mac,0x0a4d000aU,0x0a4d0001U));
  arp[41]=10;
  CHECK(aiueos_rtl8125_direct_arp_reply(
        arp,sizeof(arp),local_mac,peer_mac,0x0a4d000aU,0x0a4d0001U)==42);
  CHECK(!memcmp(arp,peer_mac,6)&&!memcmp(arp+6,local_mac,6));
  CHECK(arp[20]==0&&arp[21]==2&&!memcmp(arp+22,local_mac,6));
  CHECK(arp[28]==10&&arp[29]==77&&arp[30]==0&&arp[31]==10);
  CHECK(!memcmp(arp+32,peer_mac,6));
  CHECK(arp[38]==10&&arp[39]==77&&arp[40]==0&&arp[41]==1);
  CHECK(aiueos_rtl8125_direct_arp_reply(
        arp,41,local_mac,peer_mac,0x0a4d000aU,0x0a4d0001U)==0);
  puts("AIUEOS_RTL8125_MODEL_OK arp=peer-bound-reply "
       "driver=kotoba-objects-see-NIC-PARITY-under-qemu");
  return 0;
}
