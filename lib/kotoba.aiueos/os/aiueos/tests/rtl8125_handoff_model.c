/* SPDX-License-Identifier: Apache-2.0 */
/* What is left of this test, and why.
 *
 * It used to drive the whole RTL8125 handoff against a fake BAR: takeover,
 * revision, MAC, ring installation, transmit submission, receive completion,
 * rearm and a bounded FIFO flush.  Those bodies are Kotoba objects now
 * (ADR-0140), and `aiueos_rtl8125_kotoba_selftest` in `kernel/rtl8125.c` runs
 * the EMITTED MACHINE CODE against a software model of the BAR on every UEFI
 * boot and prints `NIC-PARITY` on the serial console.
 *
 * What remains here is the two peer-bound ARP helpers.  They are called on the
 * direct-link path in `kernel/pci.c` and are now kotoba/rtl8125-arp.o behind
 * C wrappers (JUN-553), an x86_64-aiueos-kernel-v1 object a host compiler on an
 * arm64 machine cannot link -- so this file is freestanding and runs inside the
 * QEMU image of `scripts/rtl8125-arp-diff`, against the wrappers in
 * kernel/rtl8125.c built with AIUEOS_RTL8125_ARP_ONLY.  It returns 0, or the
 * line of the first check that failed. */
#include <stdint.h>
#include "rtl8125.h"

static void be16(uint8_t*p,uint16_t v){p[0]=(uint8_t)(v>>8);p[1]=(uint8_t)v;}
static void be32(uint8_t*p,uint32_t v){p[0]=(uint8_t)(v>>24);p[1]=(uint8_t)(v>>16);p[2]=(uint8_t)(v>>8);p[3]=(uint8_t)v;}
static int same(const uint8_t*a,const uint8_t*b,unsigned n){uint8_t d=0;for(unsigned i=0;i<n;i++)d|=a[i]^b[i];return d==0;}

#define CHECK(x) do { if (!(x)) return __LINE__; } while(0)

int rtl8125_handoff_model(void) {
  const uint8_t local_mac[6]={0x70,0x70,0xfc,0x0b,0xb6,0x32};
  const uint8_t peer_mac[6]={0x80,0x69,0x1a,0x17,0x4f,0x15};
  uint8_t arp[64]={0};
  for(unsigned i=0;i<6;i++){arp[i]=0xff;arp[6+i]=peer_mac[i];}
  be16(arp+12,0x0806);be16(arp+14,1);be16(arp+16,0x0800);
  arp[18]=6;arp[19]=4;be16(arp+20,1);for(unsigned i=0;i<6;i++)arp[22+i]=peer_mac[i];
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
  CHECK(same(arp,peer_mac,6)&&same(arp+6,local_mac,6));
  CHECK(arp[20]==0&&arp[21]==2&&same(arp+22,local_mac,6));
  CHECK(arp[28]==10&&arp[29]==77&&arp[30]==0&&arp[31]==10);
  CHECK(same(arp+32,peer_mac,6));
  CHECK(arp[38]==10&&arp[39]==77&&arp[40]==0&&arp[41]==1);
  CHECK(aiueos_rtl8125_direct_arp_reply(
        arp,41,local_mac,peer_mac,0x0a4d000aU,0x0a4d0001U)==0);
  return 0;
}
