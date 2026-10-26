/* aiueos.hvt V1 virtqueue-RECEIVE test guest (aarch64, freestanding).
 *
 * The mirror of the transmit guest: completes the virtio-mmio transport
 * handshake, then sets up the receiveq (queue 0) in guest RAM with a single
 * device-WRITABLE buffer, and notifies it. The tender fills the buffer with a
 * fixed "console input" ("HI\n") and completes the descriptor on the used ring.
 * The guest polls the used ring, reads the delivered length, and echoes the
 * received bytes to the plain serial port. So a receipt serial of "HI\n" proves
 * the device -> guest (receiveq) path: device-writable descriptors, the tender
 * writing into guest RAM, and the used-ring completion.
 *
 * Freestanding; SP is set by the tender. Built with the V1 ELF loader's linker
 * script; see scripts/build-hvt-guest.cljk.
 */
typedef unsigned int   u32;
typedef unsigned short u16;
typedef unsigned long  u64;
typedef unsigned char  u8;

void _start(void)
{
    volatile u32 *v = (volatile u32 *)0x0a000000UL;   /* virtio-mmio window */

    /* --- transport handshake --- */
    if (v[0x000 / 4] != 0x74726976u) goto done;
    if (v[0x004 / 4] != 2u) goto done;
    if (v[0x008 / 4] != 3u) goto done;
    v[0x070 / 4] = 0;
    v[0x070 / 4] = 1;
    v[0x070 / 4] = 3;
    v[0x014 / 4] = 0; u32 fl = v[0x010 / 4];
    v[0x024 / 4] = 0; v[0x020 / 4] = fl;
    v[0x014 / 4] = 1; u32 fh = v[0x010 / 4];
    v[0x024 / 4] = 1; v[0x020 / 4] = fh;
    v[0x070 / 4] = 0xb;
    if (!(v[0x070 / 4] & 0x8)) goto done;
    v[0x070 / 4] = 0xf;

    /* --- receiveq (queue 0): one device-WRITABLE buffer --- */
    volatile u64 *desc  = (volatile u64 *)0x40010000UL;
    volatile u16 *avail = (volatile u16 *)0x40020000UL;
    volatile u16 *used  = (volatile u16 *)0x40030000UL;
    volatile u8  *buf   = (volatile u8  *)0x40040000UL;
    desc[0] = 0x40040000UL;                           /* descriptor 0 addr */
    ((volatile u32 *)desc)[2] = 16;                   /* len 16 (@ +8) */
    ((volatile u16 *)desc)[6] = 2;                    /* flags = VIRTQ_DESC_F_WRITE (@ +12) */
    ((volatile u16 *)desc)[7] = 0;                    /* next */
    avail[0] = 0;                                     /* avail.flags */
    avail[2] = 0;                                     /* avail.ring[0] = desc 0 */
    avail[1] = 1;                                     /* avail.idx = 1 */
    used[0] = 0; used[1] = 0;                          /* used.flags, used.idx */

    v[0x030 / 4] = 0;                                 /* QueueSel = 0 (receiveq) */
    v[0x038 / 4] = 8;                                 /* QueueNum = 8 */
    v[0x080 / 4] = 0x40010000u; v[0x084 / 4] = 0;     /* QueueDesc */
    v[0x090 / 4] = 0x40020000u; v[0x094 / 4] = 0;     /* QueueDriver (avail) */
    v[0x0a0 / 4] = 0x40030000u; v[0x0a4 / 4] = 0;     /* QueueDevice (used) */
    v[0x044 / 4] = 1;                                 /* QueueReady */
    v[0x050 / 4] = 0;                                 /* QueueNotify = 0 (receiveq) */

    /* --- await delivery, then echo the received bytes to the serial port --- */
    volatile u8 *s = (volatile u8 *)0x09000000UL;
    for (int i = 0; i < 1000000; i++) {
        if (used[1] >= 1) {
            u32 len = ((volatile u32 *)used)[2];      /* used.ring[0].len (@ +8) */
            for (u32 j = 0; j < len; j++)
                *s = buf[j];                          /* echo each received byte */
            break;
        }
    }
done:
    *(volatile u8 *)0x09000008UL = 1;                 /* poweroff -> VMM halts */
    for (;;) { }
}
