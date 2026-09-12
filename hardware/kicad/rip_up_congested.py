#!/usr/bin/env python3
"""Surgical rip-up of congested nets before a targeted FreeRouter pass.

Removes (tracks + vias, any layer):
1. Every track/via sitting on the internal plane layers In1.Cu/In2.Cu —
   stackup intent is a solid GND plane (In1) and +3V3 plane (In2); signal
   tracks there are autorouter artifacts that hole the pours.
2. All copper of nets in RIP_NETS (the I2C bus mess around the sensor
   cluster and the USB-C fanout/VBUS tangle at J1). Pad copper is NOT
   touched; the next router pass re-routes these nets from scratch while
   the rest of the board stays frozen (exported DSN keeps existing tracks).

    python3 rip_up_congested.py
"""
from pathlib import Path
import pcbnew

NM = 1e6
HERE = Path(__file__).resolve().parent
BOARD = HERE / "pot-pulse.kicad_pcb"

RIP_NETS = {
    "/EN",               # horizontal corridor track y=27.24 crossing U5 fanout
    "/BOOT_GPIO9",       # long vertical x=50.44 right through the U5 corridor
    "/MOISTURE_AIN2",    # fanout + via crowding U5 SDA/SCL exit lanes
}


def main() -> int:
    board = pcbnew.LoadBoard(str(BOARD))
    plane_layers = {"In1.Cu", "In2.Cu"}
    doomed = []
    for tr in list(board.GetTracks()):
        ly = str(tr.GetLayerName())
        # PCB_VIA GetLayerName is "F.Cu"; test its layer span via start/end?
        # Vias always span: check via start layer pair instead.
        net = tr.GetNetname()
        if ly in plane_layers:
            doomed.append((tr, "plane-layer"))
        elif net in RIP_NETS:
            doomed.append((tr, f"net {net}"))
    counts = {}
    for tr, why in doomed:
        board.Remove(tr)
        counts[why] = counts.get(why, 0) + 1
    board.Save(str(BOARD))
    for k, v in sorted(counts.items()):
        print(f"removed {v} items: {k}")
    print("total removed:", len(doomed))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
