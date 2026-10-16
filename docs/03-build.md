# 3. Build

The build ran on an Arch-based laptop (Omarchy). Package names for Debian/Ubuntu are in brackets.

## Toolchain

```sh
sudo pacman -S base-devel git curl gcc-ada ncurses zlib nasm imagemagick util-linux-libs python
#  [Debian/Ubuntu: build-essential git curl gnat libncurses-dev zlib1g-dev nasm imagemagick uuid-dev python3]

git clone https://review.coreboot.org/coreboot.git && cd coreboot
git checkout d20b38fb35          # the tested base (26.09-226)
git submodule update --init --checkout

make crossgcc-i386 CPUS=$(nproc)
```

What the edk2 payload needs from that list:
- `nasm`;
- `imagemagick`, to convert the boot logo;
- `libuuid` (`util-linux-libs` / `uuid-dev`);
- `python3`.

The cross toolchain also builds its own ACPI compiler, `iasl`.

If `make crossgcc-i386` stalls downloading from `ftpmirror.gnu.org`, use coreboot's own mirror instead
(the downloads are still checked against their hashes):

```sh
make crossgcc-i386 CPUS=$(nproc) BUILDGCC_OPTIONS=-m
```

Build the flash-layout tool too, since you'll use it below:

```sh
make -C util/ifdtool
```

`make distclean` deletes it, so rebuild it after any `distclean`.

## Apply the patch

```sh
git switch -c m920x
git am /path/to/m920x-coreboot-guide/patches/0001-*.patch
```

The patch:
- adds the fan curve and the PL1/PL2 defaults to the board's devicetree;
- adds a setup menu (`cfr.c`) and the fan-profile code (`fan.c`);
- changes the shared `nct6687d` Super I/O driver.

Docs [06](06-fan-control.md) and [07](07-power-limits.md) cover what it does and why. It applies
cleanly on `d20b38fb35`. On newer coreboot you may need to resolve conflicts.

## Extract your own flash regions

The image needs **your** flash descriptor, ME firmware and GbE region (the GbE region holds your MAC
address), taken from the stock backup:

```sh
mkdir -p ~/m920x-build/regions && cd ~/m920x-build/regions
cp /path/to/stock.rom .
/path/to/coreboot/util/ifdtool/ifdtool -p cnl -x stock.rom
ls     # flashregion_0_flashdescriptor.bin  flashregion_1_bios.bin
       # flashregion_2_intel_me.bin  flashregion_3_gbe.bin
```

These files are as private as the backup itself.

## Configure

Copy [`configs/defconfig.m920x`](../configs/defconfig.m920x) and change the three `/path/to/regions/`
paths to match your setup. Here's what each setting does:

| Setting | Why |
|---|---|
| `BOARD_LENOVO_M920Q` | The M920 Tiny board, which includes the M920x. It sets up the 24 MiB / two-chip layout. |
| `USE_BLOBS` | Takes Intel FSP and CPU microcode from coreboot's `3rdparty` submodules. The board ships its own video BIOS table (VBT), so you don't need to extract one. |
| `IFD_BIN_PATH` / `ME_BIN_PATH` / `GBE_BIN_PATH` | Your own descriptor, ME and GbE regions from the backup. Using your GbE region keeps the MAC address. |
| `PAYLOAD_EDK2` | The UEFI payload. The default source is MrChromebox's edk2 fork. |
| `POWER_STATE_OFF_AFTER_FAILURE` | Stay off after a power cut. **This SoC's default is ON.** With the patch, this becomes the default for a setup-menu option. |
| `DO_NOT_TOUCH_DESCRIPTOR_REGION` | Keeps Lenovo's flash region permissions. The default, `UNLOCK_FLASH_REGIONS`, rewrites the descriptor to make every region writable. Lenovo's descriptor already lets the OS write the BIOS and GbE regions, so internal updates work either way. |
| `PCIEXP_ASPM` / `PCIEXP_L1_SUB_STATE` off | The NVMe fix ([doc 05](05-nvme-aspm.md)). |

Once the patch is applied, you don't need any extra settings for the setup menu. The board selects
`DRIVERS_OPTION_CFR_ENABLED` whenever edk2 and SMMSTORE are on (SMMSTORE is on by default with edk2),
and setup values are stored as UEFI variables.

```sh
cd /path/to/coreboot
make defconfig KBUILD_DEFCONFIG=/path/to/defconfig.m920x
make -j$(nproc)
```

The result is `build/coreboot.rom`.

## Check the image before flashing

```sh
ls -l build/coreboot.rom                         # exactly 25,165,824 bytes
build/cbfstool build/coreboot.rom print          # microcode, intel_fit, fspm.bin, fsps.bin, vbt.bin, fallback/payload

# Descriptor, ME and GbE must be byte-identical to stock:
mkdir -p /tmp/new && cd /tmp/new && /path/to/coreboot/util/ifdtool/ifdtool -p cnl -x /path/to/coreboot/build/coreboot.rom
for r in 0_flashdescriptor 2_intel_me 3_gbe; do
  cmp flashregion_$r.bin ~/m920x-build/regions/flashregion_$r.bin && echo "$r identical"
done
```

Also run `ifdtool -p cnl -d` on both images and compare the `FLMSTR1` section. Stock reads
`0x00a00f00`: the OS can write the BIOS and GbE regions, but not the ME or descriptor. This build
should be the same.

## Split into the two chip halves

BIOS1 holds the first 16 MiB of the image and BIOS2 the last 8 MiB:

```sh
dd if=build/coreboot.rom of=coreboot_flash_1.rom bs=1M count=16
dd if=build/coreboot.rom of=coreboot_flash_2.rom bs=1M skip=16 count=8
cat coreboot_flash_1.rom coreboot_flash_2.rom | cmp - build/coreboot.rom && echo "halves OK"
sha256sum coreboot_flash_1.rom coreboot_flash_2.rom > SHA256SUMS
```

Copy the halves and `SHA256SUMS` to the Pi, and run `sha256sum -c` there before flashing.

**Don't share `coreboot.rom` or its halves.** Like the backup, they contain your ME firmware and your
MAC address.
