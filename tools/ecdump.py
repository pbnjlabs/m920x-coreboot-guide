#!/usr/bin/python3 -I
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 pbnjlabs
# Dump the NCT6686D EC pages that hold the fan and temperature-sensor config,
# and decode the per-fan settings.
#
# Only reads EC registers. Like coreboot's nct6687d_ec_read_page() it selects
# each register through the EC's page/index ports, then reads the data port.
# Needs root (/dev/port). Unload any driver that is busy with the EC (nct6683,
# nct6687) if you want a dump that can't race with it.
#
#   sudo python3 -I ecdump.py [output-file]      (default: ./ecdump.txt)
import os
import sys

BASE = 0xa20  # EC I/O base: "device pnp 2e.b ... io 0x60 = 0xa20" in the devicetree
PAGES = [1, 6, 8, 9, 10, 11, 12]

fd = os.open("/dev/port", os.O_RDWR)


def outb(v, p):
    os.pwrite(fd, bytes([v]), p)


def inb(p):
    return os.pread(fd, 1, p)[0]


def rd(page, idx):
    outb(0xff, BASE)
    outb(page, BASE)
    outb(idx, BASE + 1)
    v = inb(BASE + 2)
    outb(0xff, BASE)
    return v


d = {p: [rd(p, i) for i in range(256)] for p in PAGES}
out = sys.argv[1] if len(sys.argv) > 1 else "ecdump.txt"
with open(out, "w") as f:
    for p in PAGES:
        for row in range(0, 256, 16):
            f.write(f"p{p:02d} {row:02x}: " + " ".join(f"{b:02x}" for b in d[p][row:row + 16]) + "\n")

print("customer id: %02x%02x" % (d[6][3], d[6][2]))
print("sensors (page1 a0..bf):", " ".join(f"{i}:{v:02x}" for i, v in enumerate(d[1][0xa0:0xc0]) if v))
print("manual_en=%02x channel_en=%02x default=%02x" % (d[10][0], d[12][0xfc], d[12][0xfd]))
for fan in range(1, 9):
    fi, fo = d[1][0xc0 + fan - 1], d[1][0xd0 + fan - 1]
    mode = d[9][0xd0 + fan - 1]
    src = [d[9][0x10 + x + 4 * (fan - 1)] for x in range(4)]
    base = 24 * (fan - 1)
    tl = d[11][base:base + 7]
    sl = [d[11][base + 8 + 2 * i] for i in range(7)]
    print(f"FAN{fan}: fanin={fi:02x}(pin {fi & 0x1f}, en {fi >> 7}) fanout={fo:02x}(pin {fo & 0x1f}, en {fo >> 7}) "
          f"mode={mode:02x} alg={d[9][fan - 1]:02x} func={d[10][8 + fan - 1]:02x} src={src} "
          f"temps={list(tl)} pwm={[round(x * 100 / 255) for x in sl]}")
print("full dump:", out)
