#!/usr/bin/env python3
"""Strip inner copper layers from a KiCad Specctra DSN for a 2-layer route.

Pot Pulse's stackup reserves In1.Cu for the GND plane and In2.Cu for the
+3V3 plane; letting the autorouter drop signal tracks on those layers makes
its last-hop vias collide with plane copper (and starves zone spokes on the
GND plane). This transformer rewrites the DSN so FreeRouter sees only
F.Cu/B.Cu:

- removes the `(layer InN.Cu ...)` structure blocks (balanced parens)
- removes `(plane ... (polygon InN.Cu ...))` and keepout rows for those layers

All SMD pads live on F.Cu and all through pads span F<->B, so no other DSN
element references an inner layer.

    python3 dsn_strip_inner_layers.py in.dsn out.dsn
"""
import sys
from pathlib import Path

INNER = ("In1.Cu", "In2.Cu", "In3.Cu", "In4.Cu", "In5.Cu")


def strip_block(text: str, start_marker: str) -> tuple[str, int]:
    """Remove every balanced block beginning at `start_marker`."""
    count = 0
    while True:
        i = text.find(start_marker)
        if i < 0:
            return text, count
        depth = 0
        j = i
        while j < len(text):
            if text[j] == "(":
                depth += 1
            elif text[j] == ")":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        text = text[:i] + text[j + 1:]
        count += 1


def strip_shapes_on(text: str, layers: tuple[str, ...]) -> tuple[str, int]:
    """Remove every balanced `(shape (<kind> <inner-layer> ...))` block."""
    count = 0
    idx = 0
    while True:
        i = text.find("(shape (", idx)
        if i < 0:
            return text, count
        rest = text[i + len("(shape ("):]
        tokens = rest.replace("(", " ").replace(")", " ").split(None, 2)
        layer = tokens[1] if len(tokens) > 1 else ""
        if layer not in layers:
            idx = i + 8
            continue
        depth = 0
        j = i
        while j < len(text):
            if text[j] == "(":
                depth += 1
            elif text[j] == ")":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        text = text[:i] + text[j + 1:]
        count += 1


def main() -> int:
    src, dst = Path(sys.argv[1]), Path(sys.argv[2])
    text = src.read_text()
    total = 0
    for n in INNER:
        text, c = strip_block(text, f"(layer {n}")
        total += c
    text, shapes = strip_shapes_on(text, INNER)
    out_lines = []
    dropped_rows = 0
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("(plane") or s.startswith("(keepout"):
            if any(f" {n} " in s + " " for n in INNER):
                dropped_rows += 1
                continue
        out_lines.append(line)
    dst.write_text("\n".join(out_lines) + "\n")
    print(f"stripped {total} inner layer blocks + {shapes} padstack shapes + {dropped_rows} plane/keepout rows -> {dst}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
