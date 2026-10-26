/* aiueos.hvt V1 virtqueue-transmit test guest (aarch64, freestanding).
 *
 * Completes the virtio-mmio transport handshake against the tender's emulated
 * console device, then sets up a split virtqueue (queue 1, transmitq) in guest
 * RAM, puts a single descriptor pointing at a "HI\n" buffer on the available
 * ring, and notifies the queue. The tender reads the avail ring + descriptor
 * chain out of guest RAM, pulls the bytes (into the run receipt's :console),
 * writes the used ring, and bumps its idx. The guest polls the used ring and,
 * on completion, also writes "HI\n" to the plain serial port as its own
 * confirmation, then halts. So :console == "HI\n" proves the data traversed the
 * virtqueue, and :serial == "HI\n" proves the guest observed the completion.
 *
 * Freestanding: no libc, entry is _start, all state is on the stack (the tender
 * sets SP to the top of guest RAM). Built with the V1 ELF loader's linker
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
    if (v[0x000 / 4] != 0x74726976u) goto done;       /* MagicValue */
    if (v[0x004 / 4] != 2u) goto done;                /* Version */
    if (v[0x008 / 4] != 3u) goto done;                /* DeviceID == console */
    v[0x070 / 4] = 0;                                 /* Status reset */
    v[0x070 / 4] = 1;                                 /* ACKNOWLEDGE */
    v[0x070 / 4] = 3;                                 /* ACKNOWLEDGE | DRIVER */
    v[0x014 / 4] = 0; u32 fl = v[0x010 / 4];          /* device features low */
    v[0x024 / 4] = 0; v[0x020 / 4] = fl;              /* accept low */
    v[0x014 / 4] = 1; u32 fh = v[0x010 / 4];          /* device features high */
    v[0x024 / 4] = 1; v[0x020 / 4] = fh;              /* accept high */
    v[0x070 / 4] = 0xb;                               /* FEATURES_OK */
    if (!(v[0x070 / 4] & 0x8)) goto done;             /* verify it stuck */
    v[0x070 / 4] = 0xf;                               /* DRIVER_OK */

    /* --- split virtqueue in guest RAM (above the loaded image) --- */
    volatile u64 *desc  = (volatile u64 *)0x40010000UL;
    volatile u16 *avail = (volatile u16 *)0x40020000UL;
    volatile u16 *used  = (volatile u16 *)0x40030000UL;
    volatile u8  *buf   = (volatile u8  *)0x40040000UL;
    buf[0] = 'H'; buf[1] = 'I'; buf[2] = '\n';
    desc[0] = 0x40040000UL;                           /* descriptor 0 addr */
    ((volatile u32 *)desc)[2] = 3;                    /* len (@ +8) */
    ((volatile u16 *)desc)[6] = 0;                    /* flags (@ +12) */
    ((volatile u16 *)desc)[7] = 0;                    /* next (@ +14) */
    avail[0] = 0;                                     /* avail.flags */
    avail[2] = 0;                                     /* avail.ring[0] = desc 0 */
    avail[1] = 1;                                     /* avail.idx = 1 */
    used[0] = 0; used[1] = 0;                          /* used.flags, used.idx */

    v[0x030 / 4] = 1;                                 /* QueueSel = 1 */
    v[0x038 / 4] = 8;                                 /* QueueNum = 8 */
    v[0x080 / 4] = 0x40010000u; v[0x084 / 4] = 0;     /* QueueDesc */
    v[0x090 / 4] = 0x40020000u; v[0x094 / 4] = 0;     /* QueueDriver (avail) */
    v[0x0a0 / 4] = 0x40030000u; v[0x0a4 / 4] = 0;     /* QueueDevice (used) */
    v[0x044 / 4] = 1;                                 /* QueueReady */
    v[0x050 / 4] = 1;                                 /* QueueNotify = 1 */

    /* --- await completion, then confirm on the plain serial port --- */
    /* NB: write each byte to the SAME serial-register address. Writing s[0],
     * s[1], s[2] (distinct addresses) makes the compiler emit a post-index
     * `strb w,[x],#1`, whose MMIO access has no decodable syndrome on aarch64
     * KVM (KVM_RUN then fails ENOSYS). A serial data port is one register. */
    volatile u8 *s = (volatile u8 *)0x09000000UL;
    for (int i = 0; i < 1000000; i++) {
        if (used[1] >= 1) {
            *s = 'H'; *s = 'I'; *s = '\n';
            break;
        }
    }
done:
    *(volatile u8 *)0x09000008UL = 1;                 /* poweroff -> VMM halts */
    for (;;) { }
}
