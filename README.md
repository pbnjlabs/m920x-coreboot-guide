# coreboot on the Lenovo ThinkCentre M920x (Tiny)

This guide replaces the stock Lenovo UEFI on a ThinkCentre M920x with **upstream coreboot plus an edk2
(UEFI) payload**. It's written up from one real install on a machine that runs 24/7 as a home server.

The M920 Tiny board is supported upstream (`lenovo/m720q_m920q`). On this machine, though, the stock
port needed three fixes, and this guide covers all three:

| Problem | Symptom | Fix | Doc |
|---|---|---|---|
| NVMe link dies | The boot SSD shows up in edk2 but won't boot, and Linux can't see it | Build with PCIe ASPM / L1 sub-states off (Kconfig only) | [05](docs/05-nvme-aspm.md) |
| Fan ignores CPU temperature | Fan fixed at about 30% (~770 RPM), CPU at 83–89°C while nearly idle | Patch: fan curve driven by the PECI CPU temperature, plus a setup-menu fan profile | [06](docs/06-fan-control.md) |
| Power cut under all-core load | With a 65 W CPU, the machine switches off after about 30 s of full load | Patch: PL1/PL2 power limits of 35/45 W, adjustable in setup | [07](docs/07-power-limits.md) |

The patch also adds a coreboot **setup menu**, which upstream doesn't have for this board. It shows up
in the edk2 setup screen (press Esc at the logo) and has these options:
- **System:** Hyper-Threading.
- **Power:** restore AC power after loss, CPU PL1 and PL2, and CPU fan profile.

> [!WARNING]
> Flashing firmware can brick the machine. On the M920x the only way to recover a brick is an
> **external SPI programmer**, so you need one (a Raspberry Pi 4 and a SOIC-8 clip here) and a
> verified backup of **both** flash chips **before** you write anything. All of this was tested on a
> single unit. The patch isn't upstream and hasn't been reviewed by coreboot developers.

## Tested configuration

| | |
|---|---|
| Machine | ThinkCentre M920x Tiny (coreboot board "ThinkCentre M920 Tiny", `lenovo/m720q_m920q`) |
| CPU | Core i9-9900 (65 W, 8 cores / 16 threads) |
| Stock firmware | Lenovo BIOS M1UKT79A (latest at the time), CSME 12.0.6.1120 |
| Flash | BIOS1 W25Q128JV (16 MiB) + BIOS2 W25Q64JV (8 MiB) = 24 MiB image |
| Boot drive | WD_Black SN7100 4TB NVMe in slot SSD1 (plus a 2.5" SATA SSD) |
| coreboot | upstream `d20b38fb35` (26.09-226) + [the patch](patches/) |
| Payload | MrChromebox edk2 (`uefipayload_2608`, the coreboot default for `PAYLOAD_EDK2`) |
| Programmer | Raspberry Pi 4, flashrom `linux_spi`, SOIC-8 clip |
| OS | Ubuntu 26.04 with LUKS (passphrase unlock) |

**Checked working after the switch:**
- boots from NVMe through the shim fallback, with LUKS unlock;
- onboard Ethernet keeps its MAC address and its `eno1` name;
- VT-x (`kvm-ok`) and VT-d (`dmar0`, `dmar1`);
- NVMe link at 8 GT/s x4;
- the fan follows the CPU temperature, including under 16-thread load;
- no power cut under 16-thread load;
- the setup-menu options.

**Not tested:**
- the HAP bit (ME disable);
- suspend/resume;
- Wake-on-LAN;
- front audio (a known gap in the upstream board docs);
- the M720q, which shares the board directory the patch changes;
- 35 W "T" CPUs.

## Steps

1. [Before you start](docs/01-before-you-start.md): check for Boot Guard, update the BIOS, disable AMT,
   and prepare the OS (MAC address, interface name, LUKS, boot entries).
2. [Programmer and backup](docs/02-programmer-and-backup.md): Raspberry Pi 4 setup, clip wiring, and
   a verified backup of both chips.
3. [Build](docs/03-build.md): toolchain, patch, extracting your own IFD/ME/GbE regions, config, build,
   checks, and splitting the image into two chip halves.
4. [Flash and first boot](docs/04-flash-and-first-boot.md)
5. [Fix: NVMe link (ASPM / L1 sub-states)](docs/05-nvme-aspm.md)
6. [Fix: fan control](docs/06-fan-control.md)
7. [Fix: CPU power limits](docs/07-power-limits.md). This is power limiting, **not** undervolting.
   The doc explains the difference.
8. [Updating and recovery](docs/08-updating-and-recovery.md): internal reflashing, rollback, and the HAP bit.

The fixes in steps 5–7 are already built into the config and patch used in step 3. Those docs explain
what was wrong, how it was found, and how to check that each fix works.

## Repository layout

```
configs/defconfig.m920x   coreboot config (edit the three region paths)
patches/0001-*.patch       fan curve, power limits, setup menu (apply on coreboot d20b38fb35)
tools/ecdump.py           reads the Super I/O EC's fan/sensor registers and decodes them
tools/fantest.sh          ramps each PWM output to find the CPU fan (needs a third-party driver)
docs/                     the steps above
```

**Never commit firmware images or dumps to a public repo.** Your backups and your built
`coreboot.rom` contain your unit's serial number, your MAC address, and Lenovo/Intel proprietary
firmware. The `.gitignore` here blocks `*.bin`, `*.rom`, `*.tar` and `*.gpg` files.

## License

The patch in `patches/` modifies coreboot and is GPL-2.0-only, like coreboot.
