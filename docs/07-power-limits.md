# 7. Fix: CPU power limits

**Short version:** with a **65 W desktop CPU** (here an i9-9900), upstream coreboot lets the CPU draw
65 W on all cores, and the M920x **switches itself off** about 30 seconds into a full load. The
[patch](../patches/) sets PL1 = 35 W and PL2 = 45 W by default, and adds both limits to the setup menu.

## Power limiting is not undervolting

The two are often confused.

| | **Power limiting** (what this guide does) | **Undervolting** (not done here) |
|---|---|---|
| What changes | Caps the CPU package's power draw (Intel RAPL: PL1 sustained, PL2 short boost) | Lowers the CPU voltage at a given frequency (a negative offset through the OC mailbox) |
| Effect | Under heavy sustained load the CPU runs at lower clocks. Short bursts still boost. | The same clocks at lower power and heat, **if** the chip stays stable at the lower voltage |
| Risk | None to stability; it only costs sustained performance | Crashes or silent errors if the offset is too large; every chip is different |

On this machine the problem is **how much current the board can supply**, and capping power fixes that
directly.

## Symptom

- With all 16 threads loaded, the machine **lost power within about 30 seconds**. Every light went
  off.
- The system log simply stops. There's no kernel panic, no thermal warning, and no machine-check
  record on the next boot.

That pattern points to a hardware protection cutting power, not an OS crash.

## Cause (likely, not proven)

- The M920x Tiny was designed for **35 W "T"** CPUs (for example the i9-9900T).
- Upstream coreboot sets **PL1 to the CPU's rated TDP** (65 W for an i9-9900), and the board's
  devicetree sets **PL2 to 65 W**.
- Running 8 cores at full turbo for that long is most likely more current than the board's CPU voltage
  regulator was designed for, so its over-current protection cuts power.
- The **135 W power adapter wasn't the limit**, so a larger adapter wouldn't help.

## Quick test without reflashing

coreboot doesn't lock the power-limit register, so you can lower the limits from Linux until the next
reboot:

```sh
echo 35000000 | sudo tee /sys/class/powercap/intel-rapl:0/constraint_0_power_limit_uw   # PL1 35 W
echo 45000000 | sudo tee /sys/class/powercap/intel-rapl:0/constraint_1_power_limit_uw   # PL2 45 W
```

## What the patch sets

In `devicetree.cb`:

```
register "power_limits_config" = "{
	.tdp_pl1_override = 35,
	.tdp_pl2_override = 45,
}"
```

In the setup menu (*Power*):
- **CPU PL1 power limit (W)** and **CPU PL2 power limit (W)**, each 15–65 W.
- They use the `tdp_pl1_override` / `tdp_pl2_override` options that coreboot's power-limit code
  already reads.
- If PL2 is set lower than PL1, coreboot raises it to match PL1.

Check the result after booting:

```sh
cat /sys/class/powercap/intel-rapl:0/constraint_{0,1}_power_limit_uw   # 35000000 / 45000000
sudo cbmem -c | grep -E "CPU PL[12]"
```

## Results (i9-9900)

| Limits | 16 threads × 60 s |
|---|---|
| 65 / 65 W (upstream) | **lost power after about 30 s** |
| 35 / 45 W (patch) | **no power loss**, peak 74°C, fan below 2,800 RPM |

Short bursts, like starting a container or loading a page, still reach full turbo. Only long all-core
work slows down, to roughly where an i9-9900T would run.

If you raise the limits in setup, go up in small steps and run a load test while watching the
machine. On this unit, 65/65 W is known to fail and 35/45 W is known to work. Values in between
haven't been tested.

## Optional: undervolting (not tested here)

coreboot can undervolt this CPU family through the OC mailbox. The Kconfig option is
`INTEL_OC_MAILBOX_ENABLE_UNDERVOLTING`, and the setup-menu entries are in
`src/drivers/intel/oc_mailbox/cfr.h` (the `cpu_voltage` form). To use it on this board, you would add
that form to the board's `cfr.c`.

It **hasn't been tried on the M920x**. If you try it:
- start with small offsets;
- test stability under load;
- keep a way to recover, because an offset that's too large can stop the machine booting.
