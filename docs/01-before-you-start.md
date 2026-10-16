# 1. Before you start

Do everything on this page **on the stock Lenovo firmware**, before you take the backup.

## Can this unit run coreboot? (Boot Guard)

If Intel Boot Guard verified boot is fused on, the CPU refuses to run firmware that Lenovo didn't
sign. Check it from Linux:

```sh
sudo apt install coreboot-utils        # provides intelmetool
sudo intelmetool -b
```

On the tested unit:

```
Boot Guard MSR Output : 0x100000000
Measured boot        : OFF
Verified boot        : OFF
FACB in FPFs         : OFF
Your system is Boot Guard ready but verified boot is disabled.
You can flash other firmware!
```

`Verified boot : OFF` means coreboot can run. **If it says ON, stop here.** If `GET FWCAPS message
failed` shows up, ignore it; it doesn't affect the Boot Guard result.

## Update the Lenovo firmware first

The coreboot image reuses **your own** descriptor, ME and GbE regions, extracted from the backup. They
stay on the board for as long as you run coreboot, so update first.

- **BIOS:** flash the latest Lenovo BIOS. The tested unit was already on M1UKT79A.
- **ME version:** `cat /sys/class/mei/mei0/fw_ver`. (`intelmetool` prints the fields in a scrambled
  order.) Even on the latest BIOS, the tested unit had launch-era CSME **12.0.6.1120**. Lenovo's
  separate "Corporate Intel ME FW Update Tool for CFL" runs on Windows only, so the ME wasn't updated
  here. Setting the HAP bit later ([doc 08](08-updating-and-recovery.md)) is the alternative.

## Disable AMT

The M920x has full vPro/AMT, and it keeps running under coreboot as long as the stock ME does. If you
don't use it, turn it off in Lenovo setup (F1 at boot): **Advanced → Intel Manageability Control →
Disabled**. Then check from another machine that the AMT ports are closed:

```sh
nc -zv -w2 <server-ip> 16992 16993 623 664
```

While you're in setup, write down anything you want to recreate later, such as After Power Loss.

## Prepare the OS

Coreboot only rewrites the two flash chips; it doesn't touch the disks. What can break is boot and
network identity.

### MAC address

The onboard NIC's MAC lives in the flash's **GbE region**. Because you build with your own GbE region
from the backup, the MAC stays the same, and so does any DHCP reservation. Write it down now so you can
check it later:

```sh
ip link show eno1          # link/ether xx:xx:xx:xx:xx:xx
```

### Interface name

The `eno1` name comes from onboard-device information the firmware provides. It could change under
coreboot (the fallback name is `enp0s31f6`), which would break any network config tied to `eno1`. Pin
the name to the MAC in netplan. Ubuntu's installer usually does this already
(`/etc/netplan/00-installer-config.yaml`):

```yaml
network:
  ethernets:
    eno1:
      match:
        macaddress: "xx:xx:xx:xx:xx:xx"
      set-name: eno1
```

### LUKS

- **Passphrase unlock:** not affected. You type the same passphrase as before.
- **TPM-bound unlock** (clevis or `systemd-cryptenroll --tpm2-device`): **will fail**, because the
  firmware measurements change. Make sure a passphrase keyslot exists before you flash:
  `sudo cryptsetup luksDump /dev/<dev>`.

You'll need a monitor and keyboard for the first boot.

### Boot entries

UEFI boot entries are stored in the flash, so flashing wipes them. Ubuntu's shim fallback recreates
its entry automatically. Check it's there:

```sh
ls /boot/efi/EFI/BOOT/      # expect BOOTX64.EFI (shim) and fbx64.efi
```

### Virtualization baseline

Record these now so you can compare after the switch:

```sh
sudo apt install cpu-checker && kvm-ok     # "KVM acceleration can be used"
ls /sys/class/iommu/                       # dmar0 dmar1 = VT-d on
```

## Physical access

The chips sit on the **top (CPU) side** of the board, along the top edge by the M.2 and PCIe slots,
and are silkscreened **BIOS1** and **BIOS2**. A **2.5" SATA SSD in the riser area covers them and has
to come out**. That means:

- If the SATA SSD is in `/etc/fstab` or `/etc/crypttab`, mark it `nofail`. Otherwise a boot test
  without it waits about 90 s and then drops to emergency mode, which looks like a coreboot problem
  but isn't.
- If Ubuntu is on the NVMe drive, you can do a full boot test with the SATA SSD out.

## Plan the downtime

If the server provides DNS (for example Pi-hole), point your other devices at a fallback DNS first.

**Tailscale gotcha:** if the server is a Tailscale **subnet router** for your LAN, then once it's
down, a laptop with `accept-routes` on (or with an exit node active) **can't reach anything on the
LAN, including the Pi you're flashing with**. Before you start, on the laptop:

```sh
tailscale set --accept-routes=false --exit-node=     # or: tailscale down
```

Undo this afterwards.

## Optional: practice the build in QEMU

coreboot's tutorial (an emulated i440fx board with the coreinfo payload) builds and boots in QEMU with
no risk to anything. It's a good way to test the toolchain before the real build.
