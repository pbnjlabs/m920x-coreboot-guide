# 2. Programmer and backup

This step makes a **verified backup of both flash chips**. That backup is your only way back to the
stock firmware, so don't move on to building until you have it.

## Hardware

- **Raspberry Pi 4.** Its GPIO runs at 3.3 V, which matches these chips, so it needs no voltage
  modification. A CH341A works too, but the common black board puts 5 V on the data lines unless it's
  been modified. Don't use one of those unmodified.
- **SOIC-8 test clip.** The one used here came with a CH341A kit and has an adapter board, so it
  connects to the Pi's header with female-to-female jumpers.
- Both chips are 3.3 V parts: **BIOS1 = Winbond W25Q128JV** (16 MiB) and **BIOS2 = Winbond W25Q64JV**
  (8 MiB).

## Pi software

The Pi here ran Ubuntu 26.04. The steps are the same on Raspberry Pi OS.

1. **Turn on SPI:** add `dtparam=spi=on` to `/boot/firmware/config.txt`, then reboot. Check that
   `/dev/spidev0.0` exists.
2. **Build a recent flashrom.** Older packaged versions don't have `--read-repeated` (Ubuntu's 1.6.0
   didn't). Build from source with only the Pi programmer enabled:
   ```sh
   sudo apt install git build-essential meson ninja-build pkg-config
   git clone https://review.coreboot.org/flashrom.git && cd flashrom
   meson setup build -Dprogrammer=linux_spi -Dtests=disabled -Ddocumentation=disabled -Dman-pages=disabled
   ninja -C build
   ```
   If `meson setup` reports a missing dependency, install it and run it again. Run the result as
   `sudo ~/flashrom/build/flashrom …`, because `/dev/spidev0.0` is owned by root.

Every command below uses this programmer string:

```
-p linux_spi:dev=/dev/spidev0.0,spispeed=1000
```

Always give `spispeed` (in kHz). 1 MHz was reliable for every read and write here.

## Wiring

Pin numbers in the right-hand column are the Pi 4's **physical** header pins:

| Chip pin | Signal | Pi 4 pin |
|---|---|---|
| 1 | CS# | 24 (CE0 / GPIO8) |
| 2 | DO (MISO) | 21 (GPIO9) |
| 3 | WP# | 3.3 V, must not float |
| 4 | GND | 25 |
| 5 | DI (MOSI) | 19 (GPIO10) |
| 6 | CLK | 23 (GPIO11) |
| 7 | HOLD# | 3.3 V, must not float |
| 8 | VCC | 17 (3.3 V) |

Three chip pins need 3.3 V, but the Pi has only two 3.3 V pins (1 and 17, which are the same rail).
Here, **WP# went to pin 1, and HOLD# and VCC were joined at the clip and run to pin 17.** Bridging
chip pins 3, 7 and 8 together to pin 17 also works.
- Don't leave WP# or HOLD# unconnected.
- Don't use a GPIO pin as a 3.3 V supply.
- **Never use pins 2 or 4, which carry 5 V.**

Find pin 1 on the chip from the package marking (a dimple or bevel), not from a paint dot.

## Open the machine

1. Shut down and **unplug the power adapter.** It's a desktop with no battery, and the coin cell can
   stay in.
2. Remove the cover, then the 2.5" SATA SSD and its bracket. The chips are underneath, on the top
   side of the board along the edge by the M.2 and PCIe slots, marked **BIOS1** and **BIOS2**.

## Probe

Clip onto **BIOS1**. Then probe repeatedly; every run should find the chip:

```sh
for i in $(seq 10); do
  sudo ~/flashrom/build/flashrom -p linux_spi:dev=/dev/spidev0.0,spispeed=1000 2>&1 | grep -E "Found|No EEPROM"
done
```

You want `Found Winbond flash chip "W25Q128.V"` all 10 times. Here, the first attempts read as all
`0x00` (MISO held low) or found the chip only some of the time, and **reseating the clip fixed it**.
If it's still unreliable after that:
1. check that WP# and HOLD# really are at 3.3 V;
2. lower `spispeed`;
3. shorten the wires;
4. add 100 nF + 4.7 µF capacitors at the chip's VCC pin.

For **BIOS2**, add `-c "W25Q64JV-.Q"` to every command. Without it, flashrom finds more than one
matching chip definition and won't pick one.

## Read and verify

`--read-repeated` reads the chip several times (3 by default) and only saves the dump if every read
matches:

```sh
# BIOS1
sudo ~/flashrom/build/flashrom -p linux_spi:dev=/dev/spidev0.0,spispeed=1000 \
  --read-repeated bios1.bin -o bios1-read.log
# BIOS2 (move the clip first)
sudo ~/flashrom/build/flashrom -p linux_spi:dev=/dev/spidev0.0,spispeed=1000 -c "W25Q64JV-.Q" \
  --read-repeated bios2.bin -o bios2-read.log
```

> **flashrom quirk:** `--read-repeated=3 bios1.bin` fails with "Extra parameter found". The `3` is
> taken as the file name, so pass the file name directly as shown.

The file sizes should be exactly 16,777,216 bytes (`bios1.bin`) and 8,388,608 bytes (`bios2.bin`).

If the Pi resets while you move the clip (it happened once here), it's a short supply dip. Nothing is
harmed as long as no write was running. Power-cycle the Pi and carry on.

## Check the backup

Join the two dumps into the full 24 MiB image and check its layout with `ifdtool` from the coreboot
tree. [Doc 03](03-build.md) shows how to build it.

```sh
cat bios1.bin bios2.bin > stock.rom                 # 25,165,824 bytes
ifdtool -p cnl -d stock.rom | grep -E "Flash Region [0-3] "
```

Expected regions:

| Region | Range |
|---|---|
| Descriptor | `0x000000–0x000fff` |
| GbE | `0x001000–0x002fff` |
| ME | `0x003000–0xbfffff` |
| BIOS | `0xc00000–0x17fffff`, which runs on into BIOS2 |

Check that the GbE region begins with your MAC address:

```sh
od -An -tx1 -j $((0x1000)) -N 6 stock.rom     # should match the MAC you recorded
```

Make sure `bios2.bin` isn't just a copy of BIOS1: `strings bios2.bin | grep -i lenovo` should show
Lenovo BIOS strings.

## Store the backup

Keep `bios1.bin` and `bios2.bin` on at least two machines **and off-site**. They're your only way back
to stock.

The dumps contain your **serial number**, your **MAC address**, and proprietary firmware. Encrypt
anything you put in the cloud, for example:

```sh
tar -cf m920x-backup.tar bios1.bin bios2.bin stock.rom *.log
gpg -c --cipher-algo AES256 --no-symkey-cache m920x-backup.tar
```

Then test that it decrypts with the saved passphrase, and that the checksums match, before you
delete the `.tar`.
