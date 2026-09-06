# Datasheet-backed component selection

**Status:** selected for the first schematic pass in issue #3

**Evidence date:** 2026-09-06 UTC

**Machine-readable record:** [`component-selection.csv`](component-selection.csv)

This document freezes the critical component choices needed to start schematic capture. Manufacturer documentation is the electrical source of truth. Distributor quantities are only a dated availability snapshot; they are not reservations, price guarantees, or lifecycle guarantees.

No KiCad schematic exists at this milestone. Therefore these values are staged in `component-selection.csv`; issue #3 must copy them into every placed symbol using the property conventions below. The final BOM source of truth remains the KiCad schematic, not this document or `bom/preliminary-bom.csv`.

## 1. Selected topology

```text
USB-C VBUS
  -> 0.50 A hold PPTC
  -> 5 V VBUS TVS clamp
  -> 5 V input rail
  -> TPS62162 fixed 3.3 V / 1 A buck
  -> ESP32-C3-MINI-1-H4X + ADS1115 + SHT40 + VEML7700 + probes

USB-C D+/D-
  -> USBLC6-2SC6
  -> ESP32-C3 GPIO19/GPIO18 native USB

Four SEN0193 probes
  -> four keyed PH2.0 connectors
  -> TPD4E05U06 quad low-leakage ESD array
  -> per-channel RC footprints
  -> ADS1115 AIN0..AIN3

ESP32-C3 I2C
  -> ADS1115 at 0x48 (ADDR = GND)
  -> SHT40 at 0x44
  -> VEML7700 at 0x10
```

This preserves four electrically distinct moisture channels and avoids consuming the ESP32-C3 ADC channels for long external analog leads. The selected I2C addresses do not conflict.

## 2. Selection summary

| Class | Selected manufacturer / MPN | Critical validated facts | Why selected |
|---|---|---|---|
| MCU module | Espressif `ESP32-C3-MINI-1-H4X` | Recommended 4 MB module variant; 3.0–3.6 V; −40 to +105 °C; external supply capability at least 0.5 A; 13.2 × 16.6 × 2.4 mm; GPIO18=`USB_D-`, GPIO19=`USB_D+`; GPIO20/21 expose UART0 | Meets the architecture’s ESP32-C3, Wi-Fi, native-USB recovery, and temperature needs while avoiding the NRND N4 revision |
| ADC | Texas Instruments `ADS1115IDGSR` | 2.0–5.5 V; four single-ended inputs; 16 bit; 8–860 SPS; −40 to +125 °C; VSSOP-10; ADDR=GND gives 7-bit address `0x48`; analog pins limited to GND−0.3 V through VDD+0.3 V | One part provides all four independent channels with deterministic I2C ownership and ample rate for 30 s minimum sample intervals |
| Regulator | Texas Instruments `TPS62162DSGR` | 3–17 V input; fixed 3.3 V; up to 1 A; 17 µA typical quiescent current; −40 to +125 °C junction; WSON-8 2 × 2 mm with exposed pad; 2.2 µH-class typical application | Provides margin above the module’s 0.5 A supply recommendation without the worst-case heat of a 5 V-to-3.3 V SOT-23 LDO |
| Ambient sensor | Sensirion `SHT40-AD1B-R2` | 1.08–3.6 V; 0–100 %RH and −40 to +125 °C operating ranges; I2C address `0x44`; DFN-4; manufacturer lists the exact orderable MPN | Fits the 3.3 V rail and does not collide with the ADC or light sensor |
| Light sensor | Vishay `VEML7700-TR` | 2.5–3.6 V; 0–140 klx; 16-bit result; −25 to +85 °C; fixed I2C address `0x10`; 6.8 × 2.35 × 3.0 mm | Covers indoor low light through bright-window conditions and uses the shared 3.3 V bus |
| Moisture probe | DFRobot `SEN0193` (quantity 4) | 3.3–5.5 V input; analog output documented up to 3.0 V; 5 mA; PH2.0-3P cable; 98 × 23 mm | Traceable capacitive probe with manufacturer documentation; compatible with a 3.3 V ADC when powered at 3.3 V |
| USB connector | GCT `USB4105-GF-A` | USB Type-C USB 2.0 receptacle; collective VBUS rating 5 A; 48 VDC connector rating; −40 to +85 °C | Exposes power, CC, and USB 2.0 data in a mechanically anchored receptacle |
| Probe connector | JST `S3B-PH-K-S(LF)(SN)` (quantity 4) | Right-angle 3-position PH, 2.0 mm pitch; 2 A; 100 V; −40 to +105 °C | Matches the SEN0193 cable family and supports keyed, user-serviceable probes |
| USB ESD | STMicroelectronics `USBLC6-2SC6` | Two-line, low-capacitance USB 2.0 ESD protection in SOT-23-6 | Purpose-designed protection for the native USB data pair |
| VBUS TVS | onsemi `ESD5Z5.0T1G` | 5 V reverse standoff; 6.2 V minimum breakdown; 174 W peak pulse; SOD-523 | Adds a dedicated clamp for USB VBUS transients instead of misusing the data-line array |
| Probe ESD | Texas Instruments `TPD4E05U06DQAR` | Four channels; 0–5.5 V signal range; 0.5 pF; 10 nA maximum leakage; −40 to +125 °C; active production | Protects all four analog lines with leakage low enough not to dominate sensor measurements |
| Input fuse | Bourns `MF-MSMF050-2` | 15 V maximum; 0.50 A hold and 1.00 A trip at 23 °C; −40 to +85 °C; 1812 | Adds resettable USB input overcurrent protection while preserving the module’s required 0.5 A supply capability |

## 3. Electrical compatibility and schematic constraints

### Power

- The TPS62162’s 1 A rating exceeds the ESP32-C3 module’s requirement for an external supply capable of at least 0.5 A and leaves headroom for four 5 mA probes plus the digital sensors. This is a **static capacity comparison**, not a measured current budget.
- Do not replace the buck with an AP2112K-class SOT-23 LDO without a thermal review. At the architecture’s 250 mA average-current ceiling, `(5.0 V - 3.3 V) × 0.25 A = 0.425 W` before tolerances; radio bursts increase instantaneous dissipation.
- Implement the TPS62162 manufacturer application/layout guidance, including the exposed-pad ground, local input/output ceramics, short switch-node loop, and an inductor selected from the allowed inductance/current region. Issue #3 must record exact passive MPNs.
- Place the MF-MSMF050-2 immediately after VBUS. Its 0.50 A hold value is not proof that radio bursts will be trouble-free; bench verification in issue #8 must check startup, peak current, rail droop, and nuisance trips.

### Moisture acquisition

- Power all SEN0193 probes from 3.3 V so their outputs remain in the ADS1115 supply domain.
- Route one probe signal to each of AIN0–AIN3. Keep ADDR at GND (`0x48`).
- The ADS1115 programmable full-scale setting does **not** relax the absolute input pin limit. Protect and filter each input so it remains within GND−0.3 V to VDD+0.3 V.
- Place the TPD4E05U06 at the connector boundary, followed by footprints for a series resistor and shunt capacitor per channel. Exact RC values require cable/noise characterization; issue #3 should provide conservative defaults and issue #8 should measure settling, cross-channel coupling, open-probe behavior, and dry/wet repeatability.
- `SEN0193` selection does not establish soil-water-content accuracy. Firmware must retain raw readings and require per-zone dry/wet calibration as defined by the architecture.

### I2C

| Device | 7-bit address | Address behavior |
|---|---:|---|
| VEML7700 | `0x10` | Fixed |
| SHT40-AD1B-R2 | `0x44` | Fixed for the selected orderable variant |
| ADS1115 | `0x48` | ADDR tied to GND; other strap options are `0x49`–`0x4B` |

Use one set of calculated 3.3 V pull-ups for the assembled bus. Do not populate independent breakout-board pull-ups. Confirm total bus capacitance after layout and use firmware timeouts/bus recovery as required by risk R-04.

### USB and debug

- Connect GPIO18 to USB D− and GPIO19 to USB D+ through the USBLC6-2SC6 protected path. Keep the ESD device adjacent to the receptacle with a short ground return.
- Add independent 5.1 kΩ Rd resistors from CC1 and CC2 to ground for a USB-C sink; the connector rating does not replace Type-C configuration resistors or input current limiting.
- Expose GPIO20/U0RXD, GPIO21/U0TXD, EN, boot strapping access, 3.3 V, and GND as documented test/programming points. Native USB is the normal recovery path; UART pads remain the fallback.
- Respect Espressif’s antenna keepout. No copper, components, enclosure metal, or cable bundle should obstruct the module antenna region.

### Sensor placement

- The SHT40 is open-cavity. Follow Sensirion’s land pattern: do not place copper under the body other than pin pads, and keep it away from the regulator, module, indicator LEDs, and enclosure heat traps.
- The VEML7700 optical aperture must face a defined enclosure opening and be shielded from status-LED spill. Its −25 °C lower operating limit still exceeds the MVP’s 10 °C minimum.

## 4. Sourceability snapshot

The exact quantities are captured in `component-selection.csv`. On 2026-09-06 UTC, the public LCSC/JLC catalog reported positive stock for every selected board-mounted critical part:

- `ESP32-C3-MINI-1-H4X` / C41349510: 911
- `ADS1115IDGSR` / C37593: 14,470
- `TPS62162DSGR` / C40256: 439
- `SHT40-AD1B-R2` / C2909890: 20,692
- `VEML7700-TR` / C504893: 4,861
- `USB4105-GF-A` / C3020560: 11,505
- `S3B-PH-K-S(LF)(SN)` / C157929: 227,315
- `USBLC6-2SC6` (ST) / C7519: 36,380
- `ESD5Z5.0T1G` (onsemi) / C82044: 315,966
- `TPD4E05U06DQAR` (TI) / C138714: 94,387
- `MF-MSMF050-2` / C17313: 19,184

DFRobot’s manufacturer store listed `SEN0193` as a current purchasable product at the snapshot date but did not expose a quantity. DigiKey also listed the exact MPN as active and “buy now, ships today.” Recheck quantities, authorized-source status, lead time, and prices immediately before purchasing; these values are evidence of sourceability on the stated date only.

## 5. Lifecycle assessment

- **Recommended:** Espressif lists `ESP32-C3-MINI-1-H4X` as a recommended module variant in datasheet v2.2.
- **Active / Production:** TI’s current datasheet orderable addenda mark `ADS1115IDGSR`, `TPS62162DSGR`, and `TPD4E05U06DQAR` active and in production.
- **Current orderable/catalog parts:** the current Sensirion datasheet lists `SHT40-AD1B-R2`; Vishay, GCT, ST, onsemi, Bourns, JST, and DFRobot maintain current product/catalog documentation for the selected parts.
- These checks are a point-in-time lifecycle screen, not a product-longevity guarantee. Issue #4 must repeat lifecycle and stock checks before an order is generated.

## 6. Rejected alternatives

| Alternative | Decision | Reason |
|---|---|---|
| `ESP32-C3-MINI-1-N4` | Reject | Espressif datasheet v2.2 explicitly marks this older chip-revision module NRND. Use the recommended H4X variant. |
| ESP32-C3 development board mounted on the carrier | Reject for production schematic | Duplicates USB/power circuitry, complicates mechanical integration, and weakens the KiCad/BOM source-of-truth. A dev kit remains useful only as firmware test equipment. |
| ESP32-C3 internal ADC for all probes | Reject | Four long external analog channels benefit from one dedicated ADC, explicit protection/filtering, deterministic channel mapping, and freedom from MCU ADC resource constraints. |
| ADS1015 | Reject | Pin-compatible and faster, but its 12-bit resolution offers no benefit at the slow sampling interval; ADS1115’s 16-bit output gives more calibration headroom. |
| AP2112K-3.3 or similar SOT-23 LDO | Reject | The 1.7 V drop produces 0.425 W at the 250 mA average-current ceiling and has poor burst/thermal margin compared with the selected buck. |
| SHT31-class sensor | Reject | Valid but larger/older for this design; SHT40 is current, low power, supports 3.3 V directly, and has a non-conflicting address. |
| BH1750 breakout/module | Reject | Breakouts create duplicate regulators/pull-ups and a weak BOM boundary. The VEML7700 IC is a direct 3.3 V, current manufacturer-supported option with a defined optical package. |
| Anonymous “capacitive v1.2” probes | Reject | Seller-dependent construction and missing traceable MPN/datasheet undermine calibration, lifecycle, and repeatability evidence. |
| JST-XH probe connector | Reject | The selected SEN0193 cable uses PH2.0-3P; XH’s 2.5 mm family would require a different harness and invite assembly mistakes. |
| Same-MPN USBLC6/TPD4 clones | Reject | Select the named ST and TI manufacturer records; identical marketing part strings from unrelated manufacturers are not assumed electrically equivalent. |

## 7. KiCad symbol-property conventions

Issue #3 must populate these properties on every real schematic symbol. Do not encode multiple physical parts in one comma-separated MPN; use separate symbols or explicit non-schematic procurement rows.

| Property | Required | Format and ownership |
|---|---|---|
| `Manufacturer` | Yes for every purchased part | Manufacturer’s canonical name, for example `Texas Instruments` |
| `MPN` | Yes for every purchased part | One exact orderable manufacturer part number; no generic family names |
| `Datasheet` | Yes for critical ICs/modules/connectors/protection | Direct manufacturer datasheet or manufacturer product-document URL |
| `LCSC` | When an exact LCSC match is selected | Exact `C` number, for example `C40256`; never a search URL |
| `DigiKey` | When a DigiKey SKU is selected | Exact orderable DigiKey part number, not the manufacturer MPN |
| `Mouser` | When a Mouser SKU is selected | Exact orderable Mouser part number |
| `BOM Comments` | As needed | Assembly, substitution, variant, orientation, or procurement caveats |
| KiCad `DNP` flag | As needed | Population state; explain conditional use in `BOM Comments` |

Rules:

1. `Manufacturer` + `MPN` are the universal identity and must be written together.
2. `Value` remains the electrical/display value; it must not substitute for `MPN`.
3. `Footprint` must match the selected package and datasheet land pattern before issue #3 closes.
4. Supplier fields are optional cross-references and must be revalidated before ordering.
5. The schematic is authoritative once it exists. `bom/bom.csv` is generated from it in issue #4; `component-selection.csv` is only the issue #3 import checklist.
6. Generic passives introduced during schematic capture need exact MPNs too before issue #4 claims BOM completeness.

## 8. Evidence and remaining validation

### Completed here (static evidence)

- Manufacturer datasheet review for electrical limits, package, pin/interface behavior, and current orderable status.
- I2C address compatibility check.
- Static power-path capacity comparison.
- Dated sourceability lookup from public distributor/manufacturer listings.

### Not completed here

- No KiCad schematic exists, so symbol-to-pin, symbol-to-footprint, ERC, and property-completeness checks are deferred to issue #3.
- No SPICE simulation was applicable because no schematic/subcircuit netlist exists.
- No bench evidence exists for current draw, regulator ripple, USB recovery, probe range/noise, calibration repeatability, or ESD behavior.
- No field evidence exists; the selected probes do not establish agronomic accuracy.
- Mouser API inventory could not be queried because the cron environment did not expose `MOUSER_SEARCH_API_KEY`; no Mouser quantity is claimed.

## 9. Manufacturer sources

- Espressif, *ESP32-C3-MINI-1 & MINI-1U Datasheet v2.2*, Tables 1-1, 3-1, and 6-2.
- Texas Instruments, *ADS111x Datasheet Rev. E*, features, Sections 6.1 and 7.5.1.1, and orderable addendum.
- Texas Instruments, *TPS6216x Datasheet Rev. E*, Sections 5, 7.3, 9.2, and orderable addendum.
- Sensirion, *SHT4x Datasheet v7.3*, highlights, quick-start/I2C sections, Section 5, and orderable table.
- Vishay, *VEML7700 Datasheet Rev. 1.8*, features, ratings, and device-address section.
- DFRobot, *SEN0193 manufacturer wiki/product documentation*.
- GCT, *USB4105 Product Specification Rev. A3*, Section 4 ratings.
- JST, *PH Connector catalog*, specifications and 3-circuit header table.
- STMicroelectronics, *USBLC6-2 datasheet/product page*.
- onsemi, *ESD5Z Series ESD Protection Diodes datasheet/product page*.
- Texas Instruments, *TPDxE05U06 Datasheet Rev. O*, features, Section 6.3, and orderable addendum.
- Bourns, *MF-MSMF Series PTC Resettable Fuses*, ratings table and environmental characteristics.
