# Schematic notes and interface contract

**Revision:** A0 first-pass schematic, 2026-09-07
**Editable source:** [`kicad/pot-pulse.kicad_sch`](kicad/pot-pulse.kicad_sch)

The schematic implements the issue #1 architecture and issue #2 datasheet-backed selections. Manufacturer documents listed in [`component-selection.md`](component-selection.md) are the electrical ground truth. KiCad connectivity and ERC are static evidence, not physical validation.

## Power tree

```text
USB-C J1 VBUS
  -> F1 MF-MSMF050-2 (0.50 A hold / 1.00 A trip)
  -> +5V_PROTECTED
     -> D1 ESD5Z5.0T1G to GND
     -> U1 TPS62162DSGR fixed 3.3 V buck
        -> L1 2.2 uH
        -> +3V3
```

`+3V3` powers the ESP32-C3 module, ADS1115, SHT40, VEML7700, probe connectors, and I2C pull-ups. `VBUS`, `+5V_PROTECTED`, `+3V3`, and `GND` have ERC source declarations and labeled test pads. The 0.50 A PPTC rating and regulator capacity are static ratings only; startup, radio burst droop, ripple, and nuisance-trip behavior remain bench work for issue #8.

TPS62162 connections follow TI's fixed-output guidance: FB and the exposed pad go to GND, VOS senses `+3V3`, SW feeds the selected 2.2 uH inductor, and PG has a 100 kOhm pull-up. The input/output network is 10 uF plus 100 nF at the input and 22 uF at the output.

## Named interfaces

| Interface | Nets | Ownership / use |
|---|---|---|
| USB Type-C sink | `VBUS`, `CC1`, `CC2`, `USB_CONN_DP`, `USB_CONN_DM` | J1 entry; CC1/CC2 each have independent 5.1 kOhm Rd |
| Protected native USB | `USB_DP`, `USB_DM` | U7 USBLC6-2SC6 to ESP32-C3 GPIO19/GPIO18 |
| Regulator status | `REG_PG`, `SW_NODE` | `REG_PG` is testable; `SW_NODE` is local to the buck/inductor loop |
| Shared I2C | `I2C_SDA`, `I2C_SCL` | ESP32 GPIO4/GPIO5; ADS1115 0x48, SHT40 0x44, VEML7700 0x10 |
| ADC ready | `ADC_ALERT_N` | ADS1115 open-drain ALERT/RDY to ESP32 GPIO6 with 10 kOhm pull-up |
| Probe entry | `PROBE1_RAW` ... `PROBE4_RAW` | JST PH pin 3 through TPD4E05U06 boundary protection |
| Filtered moisture | `MOISTURE_AIN0` ... `MOISTURE_AIN3` | 1 kOhm / 100 nF RC outputs to ADS1115 AIN0..AIN3 |
| Reset / boot | `EN`, `BOOT_GPIO9` | EN pull-up/1 uF reset delay; GPIO9 boot strap pull-up and debug access |
| UART fallback | `U0RXD`, `U0TXD` | ESP32-C3 GPIO20/GPIO21 at J6 |

## Connector pinout

### J2–J5 moisture probes

All four connectors use the same orientation:

1. `+3V3`
2. `GND`
3. `PROBEn_RAW`

They target JST `S3B-PH-K-S(LF)(SN)` and the SEN0193 PH2.0-3P cable family. The board silkscreen and assembly guide must repeat this mapping, and issue #5/#8 must check the received cable orientation before power is applied.

### J6 unpopulated debug/program pads

1. `+3V3`
2. `GND`
3. `EN`
4. `BOOT_GPIO9`
5. `U0RXD`
6. `U0TXD`

Native USB is the normal provisioning/recovery path. J6 is a fallback for UART flashing and controlled reset/boot entry.

## Test access

The schematic provides 16 unpopulated test pads:

- rails: `VBUS`, `+5V_PROTECTED`, `+3V3`, `GND`;
- representative bus: `I2C_SDA`, `I2C_SCL`;
- USB: `USB_DP`, `USB_DM`;
- control/status: `REG_PG`, `EN`, `BOOT_GPIO9`, `ADC_ALERT_N`;
- analog: `MOISTURE_AIN0` through `MOISTURE_AIN3`.

Issue #5 owns final probe-pad placement, keepouts, silkscreen labels, and physical accessibility.

## Net naming conventions

- `+<voltage>` denotes a regulated or protected power rail, for example `+3V3` and `+5V_PROTECTED`.
- `VBUS` is the raw USB connector rail before F1.
- `_N` suffix means active-low or open-drain asserted-low behavior.
- `USB_CONN_*` names the connector side of U7; `USB_*` names the protected MCU side.
- `PROBEn_RAW` names an external connector node before the RC filter.
- `MOISTURE_AINn` names a filtered ADS1115 single-ended channel.
- `I2C_*` is the single shared assembled bus; only R4/R5 provide board pull-ups.
- `SW_NODE` is a high-dV/dt local switching node and must not be used elsewhere.
- GPIO function is included where it is an interface contract (`BOOT_GPIO9`, `U0RXD`, `U0TXD`); spare GPIO nets are explicitly named and testable in the source but are not external interfaces.

## Datasheet pin-map checks

The project symbol library records these reviewed mappings:

- ESP32-C3-MINI-1 v2.2 Table 3-1: pad 3=3V3, 8=EN, 18=GPIO4, 19=GPIO5, 20=GPIO6, 23=GPIO9, 26=USB_D-, 27=USB_D+, 30=GPIO20/U0RXD, 31=GPIO21/U0TXD, and all documented GND/NC pads.
- ADS1115 Rev. E Table 4-1: 1=ADDR, 2=ALERT/RDY, 3=GND, 4..7=AIN0..AIN3, 8=VDD, 9=SDA, 10=SCL.
- TPS6216x Rev. E pin functions: 1=PGND, 2=VIN, 3=EN, 4=AGND, 5=FB, 6=VOS, 7=SW, 8=PG, exposed pad=AGND.
- SHT4x v7.3 Figure 18: 1=SDA, 2=SCL, 3=VDD, 4=VSS.
- VEML7700 Rev. 1.8: 1=SCL, 2=VDD, 3=GND, 4=SDA.
- TPD4E05U06 Rev. O Table 4-2: protected channels on 1, 2, 4, 5; GND on 3 and 8; remaining pads NC.

## ERC configuration and intentional limits

The committed native KiCad report must contain zero electrical errors and zero warnings. No electrical violation is waived. Two footprint identifiers (`pot-pulse:ESP32-C3-MINI-1` and `pot-pulse:VEML7700`) intentionally name project land patterns that issue #5 must implement and validate against the manufacturer drawings before PCB placement. That is a PCB/library handoff, not electrical ERC evidence.

## Evidence not yet available

- No PCB layout or DRC evidence exists (issue #5).
- No SPICE simulation was run; this milestone does not claim ripple, transient, filter-settling, or signal-integrity simulation.
- No assembled hardware, voltage/current measurement, USB enumeration, sensor readout, ESD, thermal, environmental, or field test was performed.
- Probe calibration accuracy and dry/wet repeatability remain firmware/bench tasks.
