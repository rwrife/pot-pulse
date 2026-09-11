#!/usr/bin/env python3
"""Route pot-pulse.kicad_pcb via Specctra DSN -> FreeRouter -> SES import.

Run this script's two phases separately (the FreeRouter JVM runs on the host):

  phase 1 (in pcbnew container):  python3 route_driver.py export  reports/routing/passN.dsn
  phase 2 (host, JDK25 jar):      java -Djava.awt.headless=true -jar freerouting-2.4.1.jar \
                                    -de passN.dsn -do passN.ses -mp 12 -gui.enabled=false
  phase 3 (in pcbnew container):  python3 route_driver.py import reports/routing/passN.ses

Each import saves the board IMMEDIATELY (skill pitfall 17) before any probe.
Every pass must be exported from the CURRENT board state (skill pitfall 18).
Truth is adjudicated by `kicad-cli pcb drc --format json`, never this log.
"""
import sys
from pathlib import Path

import pcbnew

HERE = Path(__file__).resolve().parent
BOARD = HERE / "pot-pulse.kicad_pcb"


def main() -> int:
    mode, path = sys.argv[1], Path(sys.argv[2])
    board = pcbnew.LoadBoard(str(BOARD))
    if mode == "export":
        ok = pcbnew.ExportSpecctraDSN(board, str(path))
        print(f"export dsn -> {path}: {ok}")
        return 0 if ok else 1
    if mode == "import":
        ok = pcbnew.ImportSpecctraSES(board, str(path))
        board.Save(str(BOARD))  # save first, probe after (never lose the route)
        b = pcbnew.LoadBoard(str(BOARD))
        tracks = len(b.GetTracks())
        print(f"import ses <- {path}: {ok}; tracks/vias after reload: {tracks}")
        return 0 if ok else 1
    print("usage: route_driver.py export|import <file>", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
