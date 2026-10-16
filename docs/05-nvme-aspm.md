# 5. Fix: NVMe link dies (ASPM / L1 sub-states)

**Short version:** build with PCIe ASPM and L1 sub-states turned off. The config in
[`configs/defconfig.m920x`](../configs/defconfig.m920x) already does this:

```
# CONFIG_PCIEXP_ASPM is not set
# CONFIG_PCIEXP_L1_SUB_STATE is not set
```

## Symptoms

The boot drive was a **WD_Black SN7100 4TB** (PCIe Gen4, no DRAM cache). On the first coreboot boot:

- edk2 listed `NVMe: WD_Black SN7100 4TB`, but booting it failed with **"Not Found"**, in both M.2
  slots.
- In the edk2 shell, the drive's EFI partition (`FS0:`) showed **0 files, 0 directories**, even though
  it had shim on it.
- A Ubuntu live USB booted, but **Linux didn't see the drive at all**.
- A **different NVMe drive in the same slot worked fine**, so the slot and coreboot in general were
  OK. The problem followed the SN7100.
- Nothing on the drive was lost. Only the firmware's link handling was involved.

## Diagnosis

The SN7100 went in slot SSD1. The spare drive went in SSD2 and booted a test Ubuntu install, which
allowed live debugging.

The M.2 slots map to these PCIe root ports:

| Slot | Root port | PCI address |
|---|---|---|
| SSD1 | 21 | `00:1b.4` |
| SSD2 | 17 | `00:1b.0` |

Linux's kernel log for SSD1:

```
pcieport 0000:00:1b.4: broken device, retraining non-functional downstream link at 2.5GT/s
pcieport 0000:00:1b.4: retraining failed
```

`lspci -vv` showed `EqualizationComplete-` on that port.

The coreboot log (`sudo cbmem -c`) showed the cause. coreboot found the SN7100, then turned on
**`ASPM: Enabled L1`** and **`L1 Sub-State Support = 0x7`** for it. The spare drive got
`ASPM: Enabled None`. So the link came up, edk2 read the drive's ID and partition table, and then the
link died when it entered a low-power state.

Fixing it at runtime didn't work: turning ASPM/L1SS off with `setpci`, a secondary bus reset, and a
link disable/retrain all failed. Only a power cycle brought the link back, so the fix has to be in the
firmware.

The likely root cause (not proven) is that the devicetree's CLKREQ# mapping for this slot doesn't
match what the SN7100 needs for L1.2. The upstream board port was tested on an M920q.

## Fix and result

After rebuilding with the two Kconfig options off:
- the SN7100 boots in SSD1;
- the link runs at **8 GT/s x4**, and `lspci` shows `LnkCtl: ASPM Disabled`.

This turns off ASPM for **every** PCIe device, not just the NVMe. The cost is somewhat higher idle
power from PCIe links that can no longer drop into low-power states. For a server that's a fair trade.

## Debugging a similar problem

- Check whether the problem follows the drive or the slot by trying another drive in the same slot.
- A second boot drive with any Linux install lets you debug the failing drive while the system runs.
- `sudo cbmem -c | grep -iE "aspm|l1 sub|00:1b"` shows what coreboot did on each port.
