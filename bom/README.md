# Pot Pulse bill of materials

The editable KiCad schematic is the source of truth for every board-mounted purchased part. `bom/bom.csv` is a deterministic export; do not hand-edit it. Procurement items that do not have schematic symbols are tracked separately in `bom/non-schematic-items.csv`.

## Files

- `bom/bom.csv` — grouped board BOM generated from KiCad properties.
- `bom/non-schematic-items.csv` — probes, cable, enclosure, fasteners, and conditional debug tooling.
- `scripts/export_bom.py` — deterministic schematic-to-CSV export.
- `scripts/validate_bom.py` — property, export, schema, quantity, and procurement-list checks.
- `bom/preliminary-bom.csv` — historical planning input only; it is not authoritative.

## KiCad property contract

Every purchased symbol (`in_bom=yes`, excluding power symbols) must carry:

- `Manufacturer` and exact `MPN`
- assigned `Footprint`
- `Supplier` (`Unassigned` is explicit when no source is selected)
- `Supplier PN` when a supplier is assigned
- `Source URL`
- `Estimated Unit Cost USD` (numeric dated estimate or explicit `TBD - live quote required`)
- `Price Snapshot Date`
- `Datasheet`
- `BOM Comments`

`Value` remains the electrical/display value and never replaces the MPN. The generator in `hardware/kicad/generate_schematic.py` owns these properties so regenerating the schematic does not erase BOM data.

## Update workflow

1. Verify the exact manufacturer MPN and package against the manufacturer datasheet.
2. Query the intended supplier by exact MPN. Confirm manufacturer identity, package, and supplier PN; same-MPN clone records are not accepted as substitutions.
3. Update the component call and, when applicable, `SOURCING` in `hardware/kicad/generate_schematic.py` with the source URL, unit-price snapshot, and snapshot date. Never copy current stock or price into the BOM without recording the date.
4. Regenerate the editable schematic:

   ```sh
   KICAD_SYMBOL_DIR=/usr/share/kicad/symbols \
     /tmp/pot-pulse-kicad-venv/bin/python hardware/kicad/generate_schematic.py
   ```

5. Export and validate:

   ```sh
   /tmp/pot-pulse-kicad-venv/bin/python scripts/export_bom.py
   /tmp/pot-pulse-kicad-venv/bin/python scripts/validate_bom.py
   ```

6. Review the diff in both `pot-pulse.kicad_sch` and `bom/bom.csv`. Re-run native ERC because regeneration touches the electrical source.
7. Re-query all prices, stock, lifecycle state, MOQ, and order multiples immediately before purchasing. A dated estimate is not availability or a reservation.

## Current sourcing boundary

The 2026-09-08 LCSC/JLCSearch query found exact MPN records for 18 of 21 unique schematic MPNs (21 of 24 grouped BOM lines). Three MPNs (`GRM188R71C105KA12D`, `GRM31CR61C226ME15L`, and `VLS252012T-2R2M1R3`) remain explicitly unassigned and require live quotes. The ST `USBLC6-2SC6` and TI `TPD4E05U06DQAR` retain the manufacturer-validated LCSC records from the 2026-09-05 selection snapshot; ambiguous newer same-MPN search hits were not substituted.

The numeric extended total in `bom/bom.csv` is therefore a **partial board-component estimate**, excluding the three unquoted schematic lines, all non-schematic items, PCB fabrication, assembly, shipping, tax, setup fees, and spare quantities.

## Evidence boundary

This pipeline proves static property completeness and deterministic export only. Supplier records and costs are dated catalog evidence. It does not prove present stock, successful ordering, assembly yield, electrical behavior, bench performance, or field performance.
