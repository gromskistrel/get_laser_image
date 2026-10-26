"""Pack polygon objects onto fixed-size rectangles and return an SVG.

The input format matches the uploaded sample: a list of objects containing
`polygons`, each polygon containing `points`, plus object `boundaries`.

Packing is based on each object's axis-aligned bounding box (not true polygon
nesting). Objects may be rotated 90 degrees when that improves the fit.
"""
from __future__ import annotations

from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Any, Iterable
import argparse
import ast
import json


@dataclass(frozen=True)
class FreeRect:
    x: float
    y: float
    w: float
    h: float


@dataclass(frozen=True)
class Placement:
    item_index: int
    bin_index: int
    x: float
    y: float
    w: float
    h: float
    rotated: bool


def _dims(obj: dict[str, Any]) -> tuple[float, float]:
    b = obj.get("boundaries", {})
    if "width" in b and "length" in b:
        return float(b["width"]), float(b["length"])
    xs, ys = [], []
    for poly in obj.get("polygons", []):
        for pt in poly.get("points", []):
            xs.append(float(pt["x"]))
            ys.append(float(pt["y"]))
    if not xs:
        raise ValueError(f"Object {obj.get('id', '<unknown>')} has no points")
    return max(xs) - min(xs), max(ys) - min(ys)


def _prune(rects: list[FreeRect], eps: float = 1e-9) -> list[FreeRect]:
    out: list[FreeRect] = []
    for i, a in enumerate(rects):
        if a.w <= eps or a.h <= eps:
            continue
        contained = False
        for j, b in enumerate(rects):
            if i == j:
                continue
            if (a.x >= b.x - eps and a.y >= b.y - eps and
                a.x + a.w <= b.x + b.w + eps and
                a.y + a.h <= b.y + b.h + eps):
                contained = True
                break
        if not contained:
            out.append(a)
    return out


def _split_free_rect(free: FreeRect, used: FreeRect) -> list[FreeRect]:
    # Guillotine split into right and bottom regions. This is stable, fast,
    # and avoids overlapping free rectangles.
    result: list[FreeRect] = []
    right_w = free.w - used.w
    bottom_h = free.h - used.h
    if right_w > 1e-9:
        result.append(FreeRect(free.x + used.w, free.y, right_w, used.h))
    if bottom_h > 1e-9:
        result.append(FreeRect(free.x, free.y + used.h, free.w, bottom_h))
    return result


def pack_objects(
    objects: list[dict[str, Any]],
    rectangle_width: float,
    rectangle_height: float,
    *,
    padding: float = 2.0,
    allow_rotate: bool = True,
) -> list[Placement]:
    """Pack all objects and return their placements.

    The number of rectangles is inferred as `1 + max(bin_index)`.
    Raises ValueError when an object cannot fit even on an empty rectangle.
    """
    if rectangle_width <= 0 or rectangle_height <= 0:
        raise ValueError("rectangle_width and rectangle_height must be positive")
    if padding < 0:
        raise ValueError("padding must be non-negative")

    items = []
    for i, obj in enumerate(objects):
        w, h = _dims(obj)
        items.append((i, w + 2 * padding, h + 2 * padding, w, h))

    # Large-first generally reduces the number of bins.
    items.sort(key=lambda t: (max(t[1], t[2]), t[1] * t[2]), reverse=True)
    bins: list[list[FreeRect]] = []
    placements: list[Placement] = []

    for item_index, padded_w, padded_h, raw_w, raw_h in items:
        candidates: list[tuple[float, float, int, int, bool, float, float]] = []
        for bin_index, free_rects in enumerate(bins):
            for free_index, fr in enumerate(free_rects):
                orientations = [(False, padded_w, padded_h)]
                if allow_rotate and abs(padded_w - padded_h) > 1e-9:
                    orientations.append((True, padded_h, padded_w))
                for rotated, w, h in orientations:
                    if w <= fr.w + 1e-9 and h <= fr.h + 1e-9:
                        short_side = min(fr.w - w, fr.h - h)
                        area_waste = fr.w * fr.h - w * h
                        candidates.append((short_side, area_waste, bin_index, free_index, rotated, w, h))

        if not candidates:
            orientations = [(False, padded_w, padded_h)]
            if allow_rotate and abs(padded_w - padded_h) > 1e-9:
                orientations.append((True, padded_h, padded_w))
            feasible = [(r, w, h) for r, w, h in orientations
                        if w <= rectangle_width + 1e-9 and h <= rectangle_height + 1e-9]
            if not feasible:
                obj_id = objects[item_index].get("id", str(item_index))
                raise ValueError(
                    f"Object {obj_id!r} ({raw_w:.3f} x {raw_h:.3f}) does not fit "
                    f"inside {rectangle_width} x {rectangle_height} with padding {padding}."
                )
            bins.append([FreeRect(0, 0, rectangle_width, rectangle_height)])
            bin_index = len(bins) - 1
            free_index = 0
            rotated, w, h = min(
                feasible,
                key=lambda x: (rectangle_width * rectangle_height - x[1] * x[2],
                               min(rectangle_width - x[1], rectangle_height - x[2]))
            )
        else:
            _, _, bin_index, free_index, rotated, w, h = min(candidates)

        fr = bins[bin_index].pop(free_index)
        used = FreeRect(fr.x, fr.y, w, h)
        bins[bin_index].extend(_split_free_rect(fr, used))
        bins[bin_index] = _prune(bins[bin_index])

        content_w, content_h = (raw_h, raw_w) if rotated else (raw_w, raw_h)
        placements.append(Placement(
            item_index=item_index,
            bin_index=bin_index,
            x=used.x + padding,
            y=used.y + padding,
            w=content_w,
            h=content_h,
            rotated=rotated,
        ))

    return sorted(placements, key=lambda p: p.item_index)


def _object_min_xy(obj: dict[str, Any]) -> tuple[float, float]:
    xs, ys = [], []
    for poly in obj.get("polygons", []):
        for pt in poly.get("points", []):
            xs.append(float(pt["x"]))
            ys.append(float(pt["y"]))
    return (min(xs), min(ys)) if xs else (0.0, 0.0)


def objects_to_svg(
    objects: list[dict[str, Any]],
    rectangle_width: float,
    rectangle_height: float,
    *,
    padding: float = 2.0,
    allow_rotate: bool = True,
    rectangle_gap: float = 15.0,
    stroke_width: float = 0.5,
    filled: bool = False,
    show_labels: bool = True,
) -> tuple[str, list[Placement]]:
    """Return `(svg_text, placements)` for the packed objects."""
    placements = pack_objects(
        objects, rectangle_width, rectangle_height,
        padding=padding, allow_rotate=allow_rotate,
    )
    rectangle_count = 0 if not placements else max(p.bin_index for p in placements) + 1
    canvas_w = rectangle_width
    canvas_h = rectangle_count * rectangle_height + max(0, rectangle_count - 1) * rectangle_gap

    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        (f'<svg xmlns="http://www.w3.org/2000/svg" width="{canvas_w}mm" '
         f'height="{canvas_h}mm" viewBox="0 0 {canvas_w} {canvas_h}">'),
        '<rect width="100%" height="100%" fill="white"/>',
    ]

    for b in range(rectangle_count):
        oy = b * (rectangle_height + rectangle_gap)
        parts.append(
            f'<rect x="0" y="{oy}" width="{rectangle_width}" height="{rectangle_height}" '
            f'fill="none" stroke="black" stroke-width="{stroke_width}"/>'
        )
        if show_labels:
            parts.append(
                f'<text x="2" y="{oy + 5}" font-family="sans-serif" font-size="3.5" fill="black">'
                f'Rectangle {b + 1}</text>'
            )

    by_index = {p.item_index: p for p in placements}
    for i, obj in enumerate(objects):
        p = by_index[i]
        bin_y = p.bin_index * (rectangle_height + rectangle_gap)
        min_x, min_y = _object_min_xy(obj)
        transform = f'translate({p.x},{bin_y + p.y}) '
        if p.rotated:
            # Rotate clockwise, then shift so the rotated bounding box starts at (0,0).
            raw_w, raw_h = _dims(obj)
            transform += f'translate({raw_h},0) rotate(90) '
        transform += f'translate({-min_x},{-min_y})'

        d_parts = []
        for poly in obj.get("polygons", []):
            pts = poly.get("points", [])
            if not pts:
                continue
            d_parts.append(f'M {pts[0]["x"]} {pts[0]["y"]}')
            for pt in pts[1:]:
                d_parts.append(f'L {pt["x"]} {pt["y"]}')
            d_parts.append('Z')
        fill = "black" if filled else "none"
        parts.append(
            f'<path d="{" ".join(d_parts)}" transform="{transform}" '
            f'fill="{fill}" fill-rule="evenodd" stroke="black" stroke-width="{stroke_width}" '
            f'vector-effect="non-scaling-stroke"/>'
        )
        written = obj.get("written_number")
        if written:
            # Drawn in the object's local frame, so it moves/rotates with the object.
            # The text fills the box (x, y)..(x + size, y + size); its baseline is
            # on the y + size edge, which is the bottom edge in the SVG view.
            size = float(written.get("size", 3))
            wx, wy = float(written["point"]["x"]), float(written["point"]["y"])
            parts.append(
                f'<text x="{wx}" y="{wy + size}" transform="{transform}" '
                f'font-family="sans-serif" font-size="{size}" fill="black">'
                f'{escape(str(written["number"]))}</text>'
            )
        if show_labels:
            label = escape(str(obj.get("id", i)))
            parts.append(
                f'<text x="{p.x}" y="{bin_y + p.y - 0.8}" font-family="sans-serif" '
                f'font-size="2.5" fill="black">{label}</text>'
            )

    parts.append('</svg>')
    return "\n".join(parts), placements


def load_objects(path: str | Path) -> list[dict[str, Any]]:
    text = Path(path).read_text(encoding="utf-8")
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        data = ast.literal_eval(text)
    if not isinstance(data, list):
        raise ValueError("Input must be a list of objects")
    return data


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input")
    parser.add_argument("output")
    parser.add_argument("--width", type=float, required=True)
    parser.add_argument("--height", type=float, required=True)
    parser.add_argument("--padding", type=float, default=2.0)
    parser.add_argument("--no-rotate", action="store_true")
    parser.add_argument("--filled", action="store_true")
    parser.add_argument("--no-labels", action="store_true")
    args = parser.parse_args()

    objects = load_objects(args.input)
    svg, placements = objects_to_svg(
        objects, args.width, args.height,
        padding=args.padding,
        allow_rotate=not args.no_rotate,
        filled=args.filled,
        show_labels=not args.no_labels,
    )
    Path(args.output).write_text(svg, encoding="utf-8")
    count = 0 if not placements else max(p.bin_index for p in placements) + 1
    print(f"Packed {len(objects)} objects onto {count} rectangles -> {args.output}")


if __name__ == "__main__":
    main()
