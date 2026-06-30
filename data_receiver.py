import re
import math
import xml.etree.ElementTree as ET
from pathlib import Path

from shapely.geometry import Polygon, Point
from shapely import affinity
from svgpathtools import parse_path


INKSCAPE_NS = "{http://www.inkscape.org/namespaces/inkscape}"


def tag_name(elem):
    return elem.tag.split("}")[-1]


def is_layer(elem):
    return tag_name(elem) == "g" and elem.get(f"{INKSCAPE_NS}groupmode") == "layer"


def parse_numbers(text):
    return [float(n) for n in re.findall(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", text)]


# Shapely matrix order:
# [a, b, d, e, xoff, yoff]
#
# x' = a*x + b*y + xoff
# y' = d*x + e*y + yoff

def identity_matrix():
    return [1, 0, 0, 1, 0, 0]


def combine_matrices(first, second):
    """
    Return matrix for: first applied, then second.
    Both matrices are in Shapely order.
    """
    a1, b1, d1, e1, x1, y1 = first
    a2, b2, d2, e2, x2, y2 = second

    return [
        a2 * a1 + b2 * d1,
        a2 * b1 + b2 * e1,
        d2 * a1 + e2 * d1,
        d2 * b1 + e2 * e1,
        a2 * x1 + b2 * y1 + x2,
        d2 * x1 + e2 * y1 + y2,
    ]


def parse_single_transform(transform):
    nums = parse_numbers(transform)

    if transform.startswith("matrix"):
        a, b, c, d, e, f = nums
        return [a, c, b, d, e, f]

    if transform.startswith("translate"):
        tx = nums[0]
        ty = nums[1] if len(nums) > 1 else 0
        return [1, 0, 0, 1, tx, ty]

    if transform.startswith("scale"):
        sx = nums[0]
        sy = nums[1] if len(nums) > 1 else sx
        return [sx, 0, 0, sy, 0, 0]

    if transform.startswith("rotate"):
        angle = math.radians(nums[0])
        cos_a = math.cos(angle)
        sin_a = math.sin(angle)

        rotation = [cos_a, -sin_a, sin_a, cos_a, 0, 0]

        if len(nums) >= 3:
            cx, cy = nums[1], nums[2]

            return combine_matrices(
                combine_matrices(
                    [1, 0, 0, 1, -cx, -cy],
                    rotation,
                ),
                [1, 0, 0, 1, cx, cy],
            )

        return rotation

    if transform.startswith("skewX"):
        angle = math.radians(nums[0])
        return [1, math.tan(angle), 0, 1, 0, 0]

    if transform.startswith("skewY"):
        angle = math.radians(nums[0])
        return [1, 0, math.tan(angle), 1, 0, 0]

    return identity_matrix()


def parse_transform(transform):
    if not transform:
        return identity_matrix()

    chunks = re.findall(
        r"(?:matrix|translate|scale|rotate|skewX|skewY)\s*\([^)]*\)",
        transform,
    )

    total = identity_matrix()

    for chunk in chunks:
        total = combine_matrices(total, parse_single_transform(chunk))

    return total


def get_transform_chain(elem, parent_map):
    matrix = identity_matrix()
    chain = []
    current = elem

    while current is not None:
        chain.append(current)
        current = parent_map.get(current)

    for item in reversed(chain):
        matrix = combine_matrices(matrix, parse_transform(item.get("transform")))

    return matrix


def clean_float(value, ndigits=6):
    value = round(float(value), ndigits)
    return 0.0 if value == -0.0 else value


def clean_bounds(bounds, ndigits=6):
    return tuple(clean_float(v, ndigits) for v in bounds)


def get_style_value(elem, key):
    style = elem.get("style", "")

    for part in style.split(";"):
        if ":" in part:
            k, v = part.split(":", 1)
            if k.strip() == key:
                return v.strip()

    return None


def get_colors(elem):
    return {
        "fill": elem.get("fill") or get_style_value(elem, "fill"),
        "stroke": elem.get("stroke") or get_style_value(elem, "stroke"),
    }


def parse_svg_length(value, default=0.0):
    if value is None:
        return default

    value = value.strip()

    if value in {"", "none"}:
        return default

    match = re.match(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", value)

    if not match:
        return default

    return float(match.group(0))


def get_stroke_width(elem):
    return parse_svg_length(
        elem.get("stroke-width") or get_style_value(elem, "stroke-width"),
        default=0.0,
    )


def has_visible_stroke(elem):
    stroke = elem.get("stroke") or get_style_value(elem, "stroke")
    stroke_width = get_stroke_width(elem)

    if stroke is None:
        return False

    stroke = stroke.strip().lower()

    return stroke not in {"none", "transparent"} and stroke_width > 0


def matrix_scale_factor(matrix):
    """
    Approximate stroke scaling from the transform matrix.
    Works well for normal translate/rotate/uniform scale.

    For non-uniform scale, this uses the average scale.
    """
    a, b, d, e, xoff, yoff = matrix

    sx = math.sqrt(a * a + d * d)
    sy = math.sqrt(b * b + e * e)

    return (sx + sy) / 2


def apply_rect_stroke_to_polygon(poly, elem, transform_matrix):
    """
    Only applies stroke expansion for <rect> elements.
    Other elements are left unchanged.
    """
    if tag_name(elem) != "rect":
        return poly

    if not has_visible_stroke(elem):
        return poly

    stroke_width = get_stroke_width(elem)
    stroke_radius = stroke_width / 2

    stroke_radius *= matrix_scale_factor(transform_matrix)

    return poly.buffer(stroke_radius)


def rect_to_polygon(elem):
    x = float(elem.get("x", 0))
    y = float(elem.get("y", 0))
    w = float(elem.get("width", 0))
    h = float(elem.get("height", 0))

    return Polygon([
        (x, y),
        (x + w, y),
        (x + w, y + h),
        (x, y + h),
    ])


def circle_to_polygon(elem, resolution=64):
    cx = float(elem.get("cx", 0))
    cy = float(elem.get("cy", 0))
    r = float(elem.get("r", 0))

    return Point(cx, cy).buffer(r, resolution=resolution)


def path_to_polygon(elem, samples_per_segment=40):
    d = elem.get("d")
    if not d:
        return None

    path = parse_path(d)
    points = []

    for segment in path:
        for i in range(samples_per_segment + 1):
            p = segment.point(i / samples_per_segment)
            points.append((p.real, p.imag))

    if len(points) < 3:
        return None

    poly = Polygon(points)

    if not poly.is_valid:
        poly = poly.buffer(0)

    if poly.is_empty:
        return None

    return poly


def elem_to_polygon(elem):
    kind = tag_name(elem)

    if kind == "rect":
        return rect_to_polygon(elem)

    if kind == "circle":
        return circle_to_polygon(elem)

    if kind == "path":
        return path_to_polygon(elem)

    return None


def load_svg_layers(svg_file, round_digits=6):
    svg_file = Path(svg_file)

    tree = ET.parse(svg_file)
    root = tree.getroot()

    parent_map = {
        child: parent
        for parent in root.iter()
        for child in parent
    }

    layers = {}

    for layer in root.iter():
        if not is_layer(layer):
            continue

        layer_name = layer.get(f"{INKSCAPE_NS}label", layer.get("id", "unnamed"))
        layers[layer_name] = []

        for elem in layer.iter():
            if elem is layer:
                continue

            kind = tag_name(elem)

            if kind not in {"rect", "path", "circle"}:
                continue

            poly = elem_to_polygon(elem)

            if poly is None:
                continue

            transform_matrix = get_transform_chain(elem, parent_map)

            # Apply SVG/object transforms first
            poly = affinity.affine_transform(poly, transform_matrix)

            # Then include stroke only for rectangles
            poly = apply_rect_stroke_to_polygon(poly, elem, transform_matrix)

            colors = get_colors(elem)

            layers[layer_name].append({
                "id": elem.get("id", "no_id"),
                "type": kind,
                "polygon": poly,
                "area": clean_float(poly.area, round_digits),
                "bounds": clean_bounds(poly.bounds, round_digits),
                "transform": elem.get("transform"),
                "global_transform": tuple(
                    clean_float(v, round_digits) for v in transform_matrix
                ),
                "fill": colors["fill"],
                "stroke": colors["stroke"],
                "stroke_width": clean_float(get_stroke_width(elem), round_digits),
            })

    return layers