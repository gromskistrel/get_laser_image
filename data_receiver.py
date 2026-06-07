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


def identity_matrix():
    return [1, 0, 0, 1, 0, 0]


def combine_matrices(first, second):
    a1, b1, c1, d1, e1, f1 = first
    a2, b2, c2, d2, e2, f2 = second

    return [
        a2 * a1 + c2 * b1,
        b2 * a1 + d2 * b1,
        a2 * c1 + c2 * d1,
        b2 * c1 + d2 * d1,
        a2 * e1 + c2 * f1 + e2,
        b2 * e1 + d2 * f1 + f2,
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
        return [math.cos(angle), -math.sin(angle), math.sin(angle), math.cos(angle), 0, 0]

    return identity_matrix()


def parse_transform(transform):
    if not transform:
        return identity_matrix()

    chunks = re.findall(r"(?:matrix|translate|scale|rotate)\s*\([^)]*\)", transform)
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


def rect_to_polygon(elem):
    x = float(elem.get("x", 0))
    y = float(elem.get("y", 0))
    w = float(elem.get("width", 0))
    h = float(elem.get("height", 0))

    return Polygon([(x, y), (x + w, y), (x + w, y + h), (x, y + h)])


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


def load_svg_layers(svg_file):
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
            poly = affinity.affine_transform(poly, transform_matrix)

            colors = get_colors(elem)

            layers[layer_name].append({
                "id": elem.get("id", "no_id"),
                "type": kind,
                "polygon": poly,
                "area": poly.area,
                "bounds": poly.bounds,
                "transform": elem.get("transform"),
                "fill": colors["fill"],
                "stroke": colors["stroke"],
            })

    return layers