# 8. Updating and recovery

## Updating from the running system (no clip)

After the first external flash, updates can be written **internally**, from Linux on the machine
itself. Lenovo's flash descriptor lets the OS write the BIOS region, and the build keeps that
descriptor as it is (`DO_NOT_TOUCH_DESCRIPTOR_REGION`).

```sh
sudo apt install flashrom
sha256sum coreboot.rom                                   # check it's the image you built
sudo flashrom -p internal --ifd -i bios -N -w coreboot.rom
```

- `--ifd -i bios` writes **only the BIOS region**. The descriptor, ME and GbE regions on the chips
  stay as they are. `-N` makes flashrom verify only the region it wrote.
- Wait for `VERIFIED`, then reboot. If it doesn't say `VERIFIED`, **don't reboot**. Write the image
  again, or write the previous image.
- Every fix in this guide after the first flash was installed this way.

**Every internal flash resets UEFI settings.** The image includes an empty variable store (SMMSTORE),
so the boot order and your setup-menu choices (fan profile, PL1/PL2 and so on) go back to their
defaults. The shim fallback brings back the Ubuntu boot entry by itself.

Keep the last image that worked on the machine (for example `~/coreboot-good.rom`). If a new build
boots, but something's wrong, flash the old one back the same way.

## If it won't boot: external recovery

Use the clip and the Pi, as in [doc 04](04-flash-and-first-boot.md):

- **Back to a coreboot build that worked:** split that image into its two halves and write both chips.
- **Back to stock Lenovo firmware:** write the backups, `bios1.bin` to BIOS1 and `bios2.bin` to BIOS2
  (use `-c "W25Q64JV-.Q"` for BIOS2).

Run a separate `-v` verify on each chip before you power on.

## Optional: the HAP bit (not done yet)

The HAP bit tells the ME to stop after it has brought up the platform, which also gets rid of AMT. Set
it in the descriptor with `ifdtool -p cnl -M 1`.

- Lenovo's descriptor doesn't let the OS write the descriptor region, so this needs an **external**
  flash.
- After setting it, `intelmetool` should report the ME as disabled, and `/dev/mei0` may disappear.
- It hasn't been tested on this unit yet. Run coreboot on its own until you trust it, then change the
  ME as a separate step.

## Maintenance

- **There are no ready-made releases for this board.** coreboot, edk2 and FSP updates mean rebuilding
  and flashing yourself. After the first time, you can flash internally.
- **CPU microcode** also gets updated at boot by the OS (Ubuntu's `intel-microcode` package), whatever
  version is in the firmware.
- **No picture?** The optional COM1 serial header (on a small add-on board) carries coreboot's
  console. After a successful boot, `sudo cbmem -c` shows the same log.
- Don't use MrChromebox's `firmware-util.sh`. It's for Chromebooks only.
