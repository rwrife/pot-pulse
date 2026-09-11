import pcbnew
b = pcbnew.LoadBoard("pot-pulse.kicad_pcb")
print("GetNetCount:", b.GetNetCount())
checks = {"U2": {"3": "/+3V3", "1": "/GND", "26": "/USB_DM", "27": "/USB_DP"},
          "U1": {"2": "/+5V_PROTECTED", "7": "/SW_NODE"},
          "U4": {"4": "/MOISTURE_AIN0"},
          "J1": {"A4": "/VBUS", "B9": "/VBUS"},
          "U6": {"1": "/I2C_SCL", "4": "/I2C_SDA"},
          "U3": {"1": "/PROBE1_RAW", "5": "/PROBE4_RAW"}}
ok = True
seen = set()
for fp in b.GetFootprints():
    r = fp.GetReference()
    if r in checks:
        seen.add(r)
        for pad in fp.Pads():
            want = checks[r].get(pad.GetPadName())
            got = pad.GetNetname()
            if want and got != want:
                ok = False
                print(f"MISMATCH {r}.{pad.GetPadName()}: want {want} got {got!r}")
print("footprints:", len(b.GetFootprints()), "zones:", len(b.Zones()))
import re as _re
print("net count:", b.GetNetCount() - 1)
print("reload probe:", "OK" if (ok and seen == set(checks)) else "FAILED")
