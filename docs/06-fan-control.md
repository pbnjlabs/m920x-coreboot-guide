# 6. Fix: fan control

**Short version:** on upstream coreboot, the M920's CPU fan **ignores CPU temperature** and runs at a
fixed ~30%. The [patch](../patches/) gives the fan a temperature curve based on the CPU temperature
(read over PECI), adds a fan-profile setting to the setup menu, and clears fan-controller defaults that
otherwise fight the curve.

## Symptoms

- With the CPU nearly idle, it sat at **83–89°C** while the fan stayed at **~770 RPM** whatever the
  temperature.
- `sensors` (driver `nct6683 force=1`) showed `fan2` at about 770 RPM and `pwm2` at about 35%.

## Hardware

- **Super I/O:** Nuvoton **NCT6686D**. coreboot's driver for it is `superio/nuvoton/nct6687d`. Linux
  reports it as `nct6686`.
- **EC firmware:** version 1.0, built 2018-08-16, Lenovo customer ID `0x0102`. The EC's I/O base is
  `0xa20`.
- **The CPU fan is EC channel FAN2:** tach input on **pin 10** and PWM output on **pin 9**. At 100% it
  spins at about 6,150 RPM. This was found with [`tools/fantest.sh`](../tools/fantest.sh), which drives
  each PWM output to 100% in turn and watches the RPM. Only `pwm2` moved the fan. FAN3 has pins
  configured, but its tach reads 0 RPM.

## Root cause: the temperature sources get wiped

The board's devicetree turns on the Super I/O EC device but gives it **no sensor or fan settings**.
coreboot's `nct6687d` driver runs its hardware-monitor setup (`nct6687d_hwm_init()`) for that device
anyway, using the empty settings. That writes **"disabled" into all 32 temperature-source slots and
locks them**.

FAN2 keeps its EC firmware default: follow temperature slot 0. Slot 0 is now disabled, so the fan falls
back to the EC's default duty, `0x4c` (≈30%). [`tools/ecdump.py`](../tools/ecdump.py) showed this on
the unpatched build:

```
sensors (page1 a0..bf):                                  <- every slot empty
manual_en=05 channel_en=06 default=4c
FAN2: fanin=aa(pin 10, en 1) fanout=a9(pin 9, en 1) mode=04 func=c8 src=[0, 0, 0, 1] ...
```

This probably affects **every M720q/M920q on upstream coreboot**.

## Second problem: Lenovo's leftover fan features

Once slot 0 had a valid temperature again, the fan **surged**. It jumped to full speed (~6,200 RPM) at
only ~67–71°C, then dropped back to ~1,500 RPM while still under load.

The cause was other fan features that Lenovo's EC firmware leaves switched on for FAN2:
- Intel DTS fan control and the DTS upper bound;
- smart tracking;
- an "ambient floor" whose leftover settings can push the fan's minimum as high as 2,800 RPM.

coreboot only programs the curve and leaves these running, so they fight it. The patch clears them in
`set_fan_pins_and_mode()`. Any of them that the devicetree does request are switched back on later in
`misc_fan_config()`.

> **Keep `FAN_ALG_FUNCTRL_ALG_EN` set.** One test build also cleared that bit, and the fan then stayed
> at a fixed 38% while the CPU reached 89°C. The algorithm engine has to stay enabled for any fan mode
> to follow temperature.

## What the patch configures

In `devicetree.cb`:

```
register "sensors[0]" = "PECI_AGENT0_DOMAIN0"   # CPU temperature over PECI
register "peci_speed" = "PECI_1200KHZ"
register "FAN2.mode" = "FAN_SMART_FAN_IV"       # 7-point temperature -> PWM curve
register "FAN2.fanin_sel" = "TACH_PWM10"
register "FAN2.fanout_sel" = "TACH_PWM9"
register "FAN2.crit_temp" = "95"                # full speed at 95 C
register "FAN2.temp_err_duty" = "0xff"          # full speed if the sensor fails
register "FAN2.smart_fan.temp_src" = "{ 1, 0, 0, 0 }"   # follow sensor slot 0
```

The curve layout follows the MSI MS-7D25, the only other coreboot board that sets up this chip's fan
curves.

The **CPU fan profile** setting (*Power* menu) chooses the curve. `fan.c` copies the chosen curve into
the Super I/O settings early in boot, before the driver programs the EC. The curve points are:

| Profile | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|
| **Balanced** (default) | 45°C → 25% | 55 → 30 | 65 → 40 | 75 → 55 | 82 → 75 | 88 → 90 | 93 → 100 |
| Quiet | 50°C → 20% | 60 → 25 | 70 → 35 | 80 → 50 | 85 → 70 | 90 → 90 | 93 → 100 |
| Performance | 40°C → 35% | 50 → 45 | 60 → 55 | 70 → 70 | 78 → 85 | 85 → 100 | 90 → 100 |
| Full speed | 100% always | | | | | | |

## Checking it

**coreboot log** (`sudo cbmem -c`):

```
CPU fan profile: Balanced
NCT6687D programming sensors
Initializing Smart FAN IV for FAN2
Enabling critical temperature for FAN2
    Configuration invalid                        : no
    Configuration locked                         : yes
```

**EC registers** (`sudo python3 -I tools/ecdump.py`):

```
sensors (page1 a0..bf): 0:20                             <- slot 0 = PECI
FAN2: ... mode=03 alg=e0 func=00 src=[0, 0, 0, 1] temps=[45, 55, 65, 75, 82, 88, 93] pwm=[25, 30, 40, 55, 75, 90, 100]
```

The values mean:
- `mode=03`: Smart Fan IV.
- `alg=e0`: algorithm engine, critical temperature and sensor-error handling on.
- `func=00`: none of the leftover features.

## Results (i9-9900, Balanced, 35/45 W power limits)

| Test | Fan | Peak CPU temp |
|---|---|---|
| Idle | ~850 RPM | ~50°C |
| 4 threads × 30 s | rose smoothly to ~3,550 RPM and held there | 77°C, steady |
| 16 threads × 60 s | rose smoothly to ~2,800 RPM, then eased off as the power limit dropped from PL2 to PL1 | 74°C |
| After the load stopped | back to idle within ~10 s | |

For comparison, **before the patch**: 83–89°C nearly idle, and the fan stuck at ~770 RPM.

## Linux sensors

Linux's built-in `nct6683` driver reads this chip but needs `force=1`. Load it automatically at boot:

```sh
echo nct6683 | sudo tee /etc/modules-load.d/nct6683.conf
echo "options nct6683 force=1" | sudo tee /etc/modprobe.d/nct6683.conf
sudo modprobe nct6683 force=1
sensors nct6686-isa-0a20      # fan2 RPM, PECI 0.0 = CPU temperature, pwm2
```

**Go by the RPM, not `pwm2`.** The driver's percentage is on a different scale: it showed "128%" at
full speed.

You don't need the out-of-tree `nct6687` driver for any of this. It was used once, only to find which
output drives the fan.

## Notes

- The patch changes `lenovo/m720q_m920q`, which the **M720q shares**. The fan pins (tach 10 / PWM 9)
  were confirmed only on this M920x.
- The change in `nct6687d_hwm.c` also affects the MSI MS-7D25, the other board that uses this driver.
  That would need review before going upstream.
