# Pot Pulse first-pass PCB design notes

Editable source: [`kicad/pot-pulse.kicad_pcb`](kicad/pot-pulse.kicad_pcb)
(project [`kicad/pot-pulse.kicad_pro`](kicad/pot-pulse.kicad_pro), KiCad 9).
The board is generated reproducibly through the `pcbnew` Python API —
see `kicad/build_pcb.py` for the placement table and `kicad/README.md` for
the reproduce commands. This document records the layout intent and the
evidence boundaries for issue #5.

## Board outline and mounting strategy

- **Outline:** 70 × 50 mm rectangle on `Edge.Cuts`, 0.05 mm line width.
- **Mounting:** three M3 clearance holes (3.2 mm drill, `MountingHole_3.2mm_M3`
  footprints MK1/MK2/MK3) at (3.6, 3.6), (3.6, 46.4), (63.5, 3.6). The
  top-right corner is intentionally empty: the JST zone-connector bank
  (J2–J5) owns that edge, and `hardware/requirements.md` requires "at least
  two mounting holes." Three holes at non-collinear corners keep the board
  flat in a standoffs enclosure. Hole-to-courtyard clearance is enforced by
  `build_pcb.py check_placement()` and re-checked by native DRC.
- **Layers:** 4-layer intent — F.Cu signal / In1.Cu solid GND plane /
  In2.Cu +3V3 plane / B.Cu signal, 1.6 mm FR-4. If the fab quote pushes
  toward 2 layers, signal routing is already complete on F.Cu/B.Cu only
  (the autorouter was constrained to those layers) and the inner planes
  can be dropped by removing the pour zones; signal integrity then relies
  on the bottom-side return path.

## Connector placement

- **J1 USB-C (power + provisioning):** left edge, mouth centered at
  y = 25 mm, mating face flush with the edge — the cable exits left and
  never crosses the sensor-cable bundle.
- **J2–J5 JST-PH zone connectors:** right edge at x = 66.9 mm, 9.2 mm
  pitch, cables exit rightward away from the antenna band.
- **J6 6-pin debug/programming header:** top edge (55, 47.5), rotated 180°
  so the keyed notch faces outward; sits next to the MCU for short UART/BOOT
  fanout.
- **Sensor/RF separation:** USB entry + input protection + buck sit on the
  top band between J1 and the MCU; the ADS1115 + probe conditioning + zone
  bank live on the right; the ESP32-C3-MINI-1 is rotated 180° so its PCB
  antenna points at the bottom edge.

## Keepout strategy

- **RF keepout (hard rule area, all copper/via/track forbidden):** rectangle
  x 24–46 mm, y < 17.4 mm in front of the U2 antenna end (bottom edge). It
  stops 0.075 mm clear of U2's courtyard so the rule area does not graze the
  module (a grazing rule area flags the footprint as an `items_not_allowed`
  DRC error). This matches the ESP32-C3-MINI-1 datasheet keepout figure;
  actual RF performance still requires bench verification.
- **Edge strategy:** copper edge clearance 0.5 mm design rule; test points
  and mounting holes are placed so no silk or copper violates it.
- The keepouts are committed in the board file as rule-area zones (KiCad
  "rule areas"), so they are DRC-enforced, not just documentation.

## Grounding approach

- **Solid GND plane:** In1.Cu is a single uninterrupted +GND pour with no
  splits; F.Cu carries a second GND pour stitched to the plane through via
  fences along the main signal corridors and under every IC ground pad.
  This is the "explicit grounding approach" for the critical nets: USB
  shield/return, buck input/output loops, and ADC analog returns all have a
  plane directly beneath their signal layer.
- **+3V3:** In2.Cu plane plus an F.Cu pour around the sensor/ADC cluster;
  the Power net class (0.5 mm / 0.7–0.35 vias) carries VBUS → protection →
  buck → +3V3 bulk path.
- **Analog class:** MOISTURE_AIN* / PROBE*_RAW run 0.20 mm / 0.25 mm
  clearance away from the buck switch node and the antenna band; returns
  reference the solid GND plane.

## Critical-net routing record (first pass)

| Net group | Class | Notes |
|---|---|---|
| VBUS, +5V_PROTECTED, SW_NODE, +3V3, GND | Power 0.5 mm | Short buck loop J1→F1/D1→U1→L1→C3/C4; bulk caps adjacent to the IC. |
| USB_DP/DM, USB_CONN_DP/DM | USB 0.15 mm | USB-C staggered 0.5 mm-pitch pads (0.3×1.15 mm) physically cannot pass a 0.2 mm corridor; 0.15 mm is the documented fanout compromise. **Not impedance-controlled on this pass** — see gaps below. |
| I2C (SCL/SDA) | Default 0.2 mm | Shared bus U2→R4/R5 pull-ups→U5/U6→TP5/TP6, single trunk, no stubs >10 mm. |
| MOISTURE_AIN* / PROBE*_RAW | Analog | Filtered (R/C grid) per probe channel to U3 (ESD) and U4 (ADS1115). |
| EN, BOOT, U0RXD/TXD, REG_PG, ADC_ALERT_N | Default | Debug/diagnostic nets to J6 and test points. |

## DRC evidence and remaining known gaps

Native reports (regenerate with the commands in `kicad/README.md` §PCB):

- `kicad/reports/drc-placement.json` — placement-only stage (before routing).
- `kicad/reports/routing/passN-drc.json` — per-router-pass adjudication.
- `kicad/reports/drc-final.json` — final committed state.

Adjudication is always `kicad-cli pcb drc --format json` on the reloaded
board, never the router's own log (the two metrics count different things).

Committed final state (`reports/drc-final.json`): **0 error-class violations
(clearance/shorts/courtyards/keepouts/copper-edge all clean) and 0 warning-
class violations except one dangling via; 5 ratsnest pairs remain unrouted**:

| # | Net | Gap (verbatim DRC pair) |
|---|-----|--------------------------|
| 1 | +3V3 | `Pad 3 [/+3V3] of U5` ↔ 1.77 mm F.Cu stub |
| 2 | I2C_SCL | `Pad 2 [/I2C_SCL] of U5` ↔ 3.21 mm F.Cu stub |
| 3 | I2C_SDA | dangling B.Cu via at (52.97, 24.94) ↔ `Pad 1 [/I2C_SDA] of U5` |
| 4 | USB_CONN_DM | `Pad A7 [/USB_CONN_DM] of J1` ↔ 0.88 mm F.Cu stub |
| 5 | VBUS | `Track [/VBUS] on B.Cu` (4.80 mm) ↔ `Track [/VBUS] on B.Cu` |

Root causes are congestion, not missing routes:

- **U5 (SHT4x DFN-4, 0.8 mm pitch, 0.5×0.3 mm pads):** at the 0.2 mm
  design clearance a track physically cannot pass between adjacent pads
  (pad gap 0.5 mm < track+2×clearance = 0.6 mm). The three U5 fanout stubs
  need either a local clearance relaxation (like the USB class) or a small
  pad sweep before the next router pass. Documented as a known limitation
  for pass 2, not hidden.
- **USB-C staggered fanout (USB_CONN_DM A7):** the 0.5 mm staggered row is
  already routed at the 0.15 mm USB-class compromise; the last A7 hop
  collides with the DP stub. Needs a fan-out re-order (B-row first) next pass.
- **VBUS B.Cu gap:** the A9↔A4 bridge is closed (deterministic stub-closer);
  the remaining 4.8 mm gap is between two B.Cu trunks across the USB corner,
  blocked by J1 pads/shield. A Z-detour at 0.2 mm clearance fails the
  capsule collision test (dumped verbatim by `lane_blockers.py`).

`close_stubs.py --dry` against the final DRC reports these pairs verbatim
(`LEFT` lines); `final_pipeline.py` reproduces the exact committed board from
`build_pcb.py` + `reports/routing/t1.ses`.

Documented first-pass gaps (intentional, each with a rationale):

1. **USB full-speed impedance is not controlled** on the 4-layer stackup
   guess (no fab stackup confirmed yet). Acceptable for full-speed USB
   provisioning per the architecture doc; revisit when a fab stackup is
   quoted.
2. **No solder-mask/paste design review against a specific fab** — design
   rules are set to JLCPCB-2-layer-capable minimums (0.2 mm clearance,
   0.2 mm track, 0.3/0.6 vias); fab-specific CAM review is a fabrication
   milestone, not this issue.
3. RF keepout geometry is datasheet-derived; measured antenna performance
   is bench evidence we do not yet claim.

## Assembly and testability notes

- **Probe access:** sixteen 1.5 mm test points (TP1–TP16) in two blocks
  (bottom-left rail/debug cluster: VBUS, +5V_PROTECTED, +3V3, GND, I2C,
  USB_DP/DM, AIN2/AIN3; bottom-right analog/diagnostic row: REG_PG, EN,
  BOOT, ADC_ALERT_N, AIN0/AIN1). All are outside the RF keepout and clear of
  connector mating envelopes. TP references stay visible on silk (identity
  is part of testability); dense passives use F.Fab-only references.
- **Connector orientation checks (assembly-time):** J1 mouth must be flush
  with the left Edge.Cuts line (0.2 mm inset); J2–J5 locking-latch side
  faces the board edge so cables pull outward; J6 notch faces outward for
  ribbon-key alignment. Silkscreen pin-1 marks are present on J2–J6; J1 is
  mechanically keyed.
- **Polarity/orientation-sensitive parts:** D1 (SOD-523) band toward the
  buck input; U7 USBLC6 pin-1 dot toward J1; U1 buck EP with thermal via
  cluster (do not hand-solder without hot-air); F1 fuse 1812; C1/C3/C4
  1206 bulk — all have silk pin-1/orientation marks from footprint graphics.
- **Mounting:** M3 standoffs at MK1–MK3; no components within the 6 mm
  courtyard of any hole.
- **Test sequence hook:** TP1/TP2/TP3/TP4 are 5V/3V3/GND rails — first
  bring-up step is a rail check at these four pads before plugging in the
  zone cables.

## Reproducing the routing evidence

```sh
# from hardware/kicad/ (pcbnew container per kicad/README.md)
python3 netlist_to_json.py            # refresh reports/pcb-input/*.json
python3 build_pcb.py                  # rebuild board from placement table
python3 route_driver.py export reports/routing/passN.dsn
# host: FreeRouter headless (JDK25 + freerouting-2.4.1.jar)
#   java -Djava.awt.headless=true -jar freerouting-2.4.1.jar \
#     -de passN.dsn -do passN.ses -mp 12 -gui.enabled=false
python3 route_driver.py import reports/routing/passN.ses
python3 rip_up_dangling.py            # drop stranded fragments
python3 fill_zones.py                 # refill pours after import
python3 close_stubs.py --drc reports/routing/passN-drc.json   # deterministic final stubs
kicad-cli pcb drc --severity-error --severity-warning --format json \
  --output reports/drc-final.json pot-pulse.kicad_pcb
```

`dsn_strip_inner_layers.py` keeps the router on F.Cu/B.Cu so the inner
planes stay solid; `rip_up_congested.py` is the surgical rip-up used to
clear autorouter dead-ends before a targeted pass.
