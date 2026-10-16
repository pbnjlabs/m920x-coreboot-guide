# 4. Flash and first boot

## Write both chips

The machine is still unplugged, the SATA SSD is still out, and you have a verified backup. **Flash
both chips before you power the board on.** The BIOS region runs across both chips, so if only one is
written, the board has half an image.

For each chip:
1. Probe 10 times, as in [doc 02](02-programmer-and-backup.md).
2. Write. flashrom checks its own write and prints `VERIFIED`.
3. Run a separate verify pass before you unclip.

```sh
FR="sudo $HOME/flashrom/build/flashrom -p linux_spi:dev=/dev/spidev0.0,spispeed=1000"

# BIOS1
$FR -w coreboot_flash_1.rom -o bios1-write.log      # ... VERIFIED.
$FR -v coreboot_flash_1.rom                         # ... VERIFIED.

# move the clip to BIOS2
$FR -c "W25Q64JV-.Q" -w coreboot_flash_2.rom -o bios2-write.log
$FR -c "W25Q64JV-.Q" -v coreboot_flash_2.rom
```

**Never move the clip while a read or write is running.** If a write fails partway, **don't power on
the board**. Fix the connection and write that chip again. If the board then fails to boot, write
`bios1.bin` and `bios2.bin` back.

## First boot

Leave the clip and Pi within reach until the machine has booted at least once.

What to expect:
- **The coreboot logo, then edk2.** The first boot can be slower than usual while memory training
  runs. Don't interrupt it.
- **Esc** opens edk2 setup. With the patch, the coreboot options are in setup under **System** and
  **Power**.
- **The boot entries are gone.** edk2 boots the drive's fallback loader (`EFI/BOOT/BOOTX64.EFI`), and
  shim recreates the Ubuntu entry. If you get a `Shell>` prompt, type `exit` and pick the drive in
  Boot Manager.
- **The LUKS passphrase prompt** appears as usual.

**If edk2 lists your NVMe drive but booting it fails with "Not Found",** and `FS0:` in the edk2 shell
shows 0 files, that's the ASPM problem in [doc 05](05-nvme-aspm.md). The config in this repo already
includes the fix.

## Checks after boot

```sh
cat /sys/class/dmi/id/bios_vendor /sys/class/dmi/id/bios_version   # coreboot, version string
ip link show eno1                    # same name, same MAC as before
kvm-ok                               # "KVM acceleration can be used"
ls /sys/class/iommu/                 # dmar0 dmar1
findmnt /boot/efi; lsblk             # the expected drive is mounted
sudo lspci -vv -s 1b.4 | grep -E "LnkSta:|LnkCtl:"   # SSD1 slot: 8GT/s x4, ASPM Disabled
```

The coreboot boot log shows what the firmware did. That includes ASPM, the fan setup, and the power
limits.

```sh
sudo apt install coreboot-utils     # provides cbmem
sudo cbmem -c | less
```

Then set up the fan sensors and check the temperatures ([doc 06](06-fan-control.md)).

When everything checks out, power off, unplug, put the SATA SSD back, and boot normally.
