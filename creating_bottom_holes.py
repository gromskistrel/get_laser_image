from pathlib import Path
from time import perf_counter

import numpy as np
import pyvista as pv
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from shapely.geometry import Polygon, MultiPolygon, GeometryCollection
from shapely.ops import unary_union

EPS = 0.0001


def timed(label, fn, *args, **kwargs):
    start = perf_counter()
    result = fn(*args, **kwargs)
    print(f"{label}: {perf_counter() - start:.3f}s")
    return result


def normalize(c):
    """Fix coordinate order and preserve hole/shape metadata."""
    return {
        **c,
        "x1": min(c["x1"], c["x2"]),
        "x2": max(c["x1"], c["x2"]),
        "y1": min(c["y1"], c["y2"]),
        "y2": max(c["y1"], c["y2"]),
        "z1": min(c["z1"], c["z2"]),
        "z2": max(c["z1"], c["z2"]),
        "shape": c.get("shape", "rect"),
        "hole": int(c.get("hole", 0)),
    }


def volume(c):
    return max(0, c["x2"] - c["x1"]) * max(0, c["y2"] - c["y1"]) * max(0, c["z2"] - c["z1"])


def contains_box(c, x, y, z, eps=EPS):
    return (
        c["x1"] - eps <= x <= c["x2"] + eps
        and c["y1"] - eps <= y <= c["y2"] + eps
        and c["z1"] - eps <= z <= c["z2"] + eps
    )


def parse_bends(c):
    bend = c.get("bend")

    if not bend:
        return []

    if isinstance(bend, list) and bend and isinstance(bend[0], list):
        return bend

    if isinstance(bend, list) and len(bend) == 3:
        return [bend]

    return []


def get_bend_axis_side(bend):
    direction, z_direction, radius = bend

    if direction == "right":
        return "x", "max", z_direction, radius

    if direction == "left":
        return "x", "min", z_direction, radius

    if direction == "forward":
        return "y", "max", z_direction, radius

    if direction == "backward":
        return "y", "min", z_direction, radius

    return None, None, None, None


def bend_drop_for_point(c, bend, x, y):
    axis, side, z_direction, radius = get_bend_axis_side(bend)

    if axis is None:
        return z_direction, 0

    coord = x if axis == "x" else y
    low = c["x1"] if axis == "x" else c["y1"]
    high = c["x2"] if axis == "x" else c["y2"]

    if side == "max":
        bend_start = high - radius

        if coord <= bend_start:
            t = 0
        else:
            t = (coord - bend_start) / radius

    else:
        bend_end = low + radius

        if coord >= bend_end:
            t = 0
        else:
            t = (bend_end - coord) / radius

    t = min(max(t, 0), 1)
    drop = radius * (1 - np.cos(np.arcsin(t)))

    return z_direction, drop


def contains_bent_solid(c, x, y, z, eps=EPS):
    """
    Test whether a point lies inside a bent solid.

    Multiple bends are combined as signed offsets from the original z2:

        down -> negative top-height offset
        up   -> positive top-height offset

    This prevents an inactive "up" bend with drop=0 from undoing an active
    "down" bend.
    """
    bends = parse_bends(c)

    if not bends:
        return contains_box(c, x, y, z, eps)

    if not (
        c["x1"] - eps <= x <= c["x2"] + eps
        and c["y1"] - eps <= y <= c["y2"] + eps
    ):
        return False

    z1 = c["z1"]
    top_offset = 0.0

    for bend in bends:
        z_direction, drop = bend_drop_for_point(c, bend, x, y)

        if z_direction == "down":
            top_offset -= drop

        elif z_direction == "up":
            top_offset += drop

    z2 = c["z2"] + top_offset

    return z1 - eps <= z <= z2 + eps


def contains_solid(c, x, y, z):
    if parse_bends(c):
        return contains_bent_solid(c, x, y, z)

    return contains_box(c, x, y, z)


def get_wall_axis(c, wall_width, eps=EPS):
    widths = {
        "x": c["x2"] - c["x1"],
        "y": c["y2"] - c["y1"],
        "z": c["z2"] - c["z1"],
    }
    matches = [axis for axis, width in widths.items() if abs(width - wall_width) <= eps]
    if len(matches) != 1:
        raise ValueError(f"Expected one wall-width axis, got {matches}. Cuboid={c}, widths={widths}")
    return matches[0]


def contains_semi(h, x, y, z, wall_width, eps=EPS):
    """Point test for a semicircular hole through the wall thickness."""
    if not contains_box(h, x, y, z, eps):
        return False

    wall_axis = get_wall_axis(h, wall_width, eps)

    if wall_axis == "y":       # semicircle in XZ
        center = (h["x1"] + h["x2"]) / 2
        radius = (h["x2"] - h["x1"]) / 2
        return (x - center) ** 2 + (z - h["z2"]) ** 2 <= radius ** 2 + eps

    if wall_axis == "x":       # semicircle in YZ
        center = (h["y1"] + h["y2"]) / 2
        radius = (h["y2"] - h["y1"]) / 2
        return (y - center) ** 2 + (z - h["z2"]) ** 2 <= radius ** 2 + eps

    if wall_axis == "z":       # semicircle in XY
        center = (h["x1"] + h["x2"]) / 2
        radius = (h["x2"] - h["x1"]) / 2
        return (x - center) ** 2 + (y - h["y2"]) ** 2 <= radius ** 2 + eps

    return False


def contains_hole(h, x, y, z, wall_width):
    return contains_semi(h, x, y, z, wall_width) if h.get("shape") == "semi" else contains_box(h, x, y, z)

def add_bend_grid_points(c, xs, ys, zs, bend_steps=16):
    for bend in parse_bends(c):
        axis, side, z_direction, radius = get_bend_axis_side(bend)

        if axis is None:
            continue

        if axis == "x":
            values = xs
            low = c["x1"]
            high = c["x2"]
        else:
            values = ys
            low = c["y1"]
            high = c["y2"]

        values.add(low)
        values.add(high)
        zs.add(c["z1"])
        zs.add(c["z2"])

        if side == "max":
            bend_start = high - radius
            values.add(bend_start)

            for t in np.linspace(0, 1, bend_steps):
                coord = bend_start + radius * t
                drop = radius * (1 - np.cos(np.arcsin(t)))

                values.add(coord)

                if z_direction == "down":
                    zs.add(c["z2"] - drop)
                elif z_direction == "up":
                    zs.add(c["z2"] + drop)

        else:
            bend_end = low + radius
            values.add(bend_end)

            for t in np.linspace(0, 1, bend_steps):
                coord = bend_end - radius * t
                drop = radius * (1 - np.cos(np.arcsin(t)))

                values.add(coord)

                if z_direction == "down":
                    zs.add(c["z2"] - drop)
                elif z_direction == "up":
                    zs.add(c["z2"] + drop)

def add_semi_grid_points(h, xs, ys, zs, wall_width, semi_steps):
    """Add points along semi-hole arcs so the voxel grid can approximate them."""
    wall_axis = get_wall_axis(h, wall_width)

    if wall_axis == "y":
        center = (h["x1"] + h["x2"]) / 2
        radius = (h["x2"] - h["x1"]) / 2
        for t in np.linspace(np.pi, 2 * np.pi, semi_steps):
            xs.add(center + radius * np.cos(t))
            zs.add(h["z2"] + radius * np.sin(t))

    elif wall_axis == "x":
        center = (h["y1"] + h["y2"]) / 2
        radius = (h["y2"] - h["y1"]) / 2
        for t in np.linspace(np.pi, 2 * np.pi, semi_steps):
            ys.add(center + radius * np.cos(t))
            zs.add(h["z2"] + radius * np.sin(t))

    elif wall_axis == "z":
        center = (h["x1"] + h["x2"]) / 2
        radius = (h["x2"] - h["x1"]) / 2
        for t in np.linspace(np.pi, 2 * np.pi, semi_steps):
            xs.add(center + radius * np.cos(t))
            ys.add(h["y2"] + radius * np.sin(t))


def order_cuboids_solids_first(cuboids):
    """Return normalized cuboids ordered so solids come before holes.

    hole == 0 -> solid / additive geometry
    hole == 1 -> subtractive geometry
    """
    return sorted(
        (normalize(c) for c in cuboids),
        key=lambda c: c.get("hole", 0),
    )


def split_solids_and_holes(cuboids):
    """First collect all solids, then all holes.

    This matches the intended workflow:
    1. build/merge all hole: 0 cuboids
    2. subtract all hole: 1 cuboids
    """
    ordered = order_cuboids_solids_first(cuboids)

    solids = []
    holes = []

    for c in ordered:
        if c["hole"] == 0:
            solids.append(c)
        else:
            holes.append(c)

    return solids, holes


def merge_cuboids_preserve_internal_holes(cuboids, semi_steps=64, wall_width=5):
    """Merge hole: 0 cuboids, then subtract hole: 1 cuboids.

    This function must be called per wall/group. Do not flatten all walls
    before calling it, otherwise holes from one wall can subtract another wall.
    """
    solids, holes = split_solids_and_holes(cuboids)
    all_cuboids = solids + holes

    if not all_cuboids:
        print("No cuboids supplied")
        return [], []

    xs = {v for c in all_cuboids for v in (c["x1"], c["x2"])}
    ys = {v for c in all_cuboids for v in (c["y1"], c["y2"])}
    zs = {v for c in all_cuboids for v in (c["z1"], c["z2"])}

    for h in holes:
        if h.get("shape") == "semi":
            add_semi_grid_points(h, xs, ys, zs, wall_width, semi_steps)
    for s in solids:
        if parse_bends(s):
            add_bend_grid_points(s, xs, ys, zs)

    xs, ys, zs = sorted(xs), sorted(ys), sorted(zs)

    print(f"Grid sizes: xs={len(xs)}, ys={len(ys)}, zs={len(zs)}")
    print(f"Max possible cells: {(len(xs) - 1) * (len(ys) - 1) * (len(zs) - 1)}")
    print(f"Solids={len(solids)}, holes={len(holes)}")

    result = []

    for xi in range(len(xs) - 1):
        for yi in range(len(ys) - 1):
            for zi in range(len(zs) - 1):
                cell = {
                    "x1": xs[xi],
                    "x2": xs[xi + 1],
                    "y1": ys[yi],
                    "y2": ys[yi + 1],
                    "z1": zs[zi],
                    "z2": zs[zi + 1],
                    "shape": "rect",
                    "hole": 0,
                }
                if volume(cell) <= EPS:
                    continue

                cx = (cell["x1"] + cell["x2"]) / 2
                cy = (cell["y1"] + cell["y2"]) / 2
                cz = (cell["z1"] + cell["z2"]) / 2

                solid_source = next(
                    (s for s in solids if contains_solid(s, cx, cy, cz)),
                    None,
                )

                in_hole = any(
                    contains_hole(h, cx, cy, cz, wall_width)
                    for h in holes
                )
                if solid_source is not None and not in_hole:
                    result.append(cell)

    print(f"Result cuboids: {len(result)}")
    return result, holes


def merge_adjacent_cuboids(cuboids, eps=EPS, precision=8):
    """Collapse adjacent voxel cells without changing the represented solid.

    Two cuboids are merged when they touch along one axis and have identical
    ranges on the other two axes. Multiple axis passes are repeated until no
    further reduction is possible.
    """
    cuboids = [normalize(c) for c in cuboids if volume(normalize(c)) > eps]

    def rounded(value):
        return round(float(value), precision)

    def merge_along_axis(items, axis):
        other_axes = [candidate for candidate in ("x", "y", "z") if candidate != axis]
        groups = {}

        for cuboid in items:
            key = (
                rounded(cuboid[f"{other_axes[0]}1"]),
                rounded(cuboid[f"{other_axes[0]}2"]),
                rounded(cuboid[f"{other_axes[1]}1"]),
                rounded(cuboid[f"{other_axes[1]}2"]),
                cuboid.get("shape", "rect"),
                int(cuboid.get("hole", 0)),
            )
            groups.setdefault(key, []).append(cuboid)

        merged = []
        low_key = f"{axis}1"
        high_key = f"{axis}2"

        for group in groups.values():
            group.sort(key=lambda cuboid: (cuboid[low_key], cuboid[high_key]))
            current = dict(group[0])

            for next_cuboid in group[1:]:
                if abs(current[high_key] - next_cuboid[low_key]) <= eps:
                    current[high_key] = max(current[high_key], next_cuboid[high_key])
                else:
                    merged.append(current)
                    current = dict(next_cuboid)

            merged.append(current)

        return merged

    while True:
        before = len(cuboids)
        for axis in ("x", "y", "z"):
            cuboids = merge_along_axis(cuboids, axis)
        if len(cuboids) == before:
            break

    return cuboids


def cuboid_to_pv(c):
    c = normalize(c)
    return pv.Box(
        bounds=(
            c["x1"], c["x2"],
            c["y1"], c["y2"],
            c["z1"], c["z2"],
        )
    )


def cuboids_to_outer_surface_and_edges(cuboids, feature_angle=30):
    """
    Build one visual surface from many cuboids and extract meaningful object edges.

    boundary_edges=False is important. The cuboid grid contains many separate
    surface patches, and treating their borders as boundary edges creates the
    unwanted internal/grid lines.
    """
    boxes = [
        cuboid_to_pv(c)
        for c in cuboids
        if volume(normalize(c)) > EPS
    ]

    if not boxes:
        return None, None

    merged = pv.MultiBlock(boxes).combine(merge_points=True)

    surface = (
        merged
        .extract_surface()
        .clean(tolerance=EPS)
    )

    edges = surface.extract_feature_edges(
        feature_angle=feature_angle,

        # Do not draw borders between separate voxel surface patches.
        boundary_edges=False,

        # Keep actual corners and changes in face direction.
        feature_edges=True,

        # Do not draw every shared polygon edge.
        manifold_edges=False,

        # Usually indicates problematic/internal mesh structure.
        non_manifold_edges=False,
    )

    return surface, edges



def _clip_cuboid_to_axis_range(cuboid, axis, lower, upper, eps=EPS):
    """Return the portion of a cuboid inside one interval on the given axis."""
    c = normalize(cuboid)
    low_key = f"{axis}1"
    high_key = f"{axis}2"

    clipped_low = max(float(c[low_key]), float(lower))
    clipped_high = min(float(c[high_key]), float(upper))

    if clipped_high - clipped_low <= eps:
        return None

    clipped = dict(c)
    clipped[low_key] = clipped_low
    clipped[high_key] = clipped_high
    return clipped


def split_wall_cuboids_into_three_layers(cuboids, thickness_axis):
    """
    Split one wall through its thickness into three equal layers.

    Returned order:
        outer edge  -> light
        middle      -> dark
        inner edge  -> light
    """
    cuboids = [normalize(c) for c in cuboids if volume(normalize(c)) > EPS]
    if not cuboids:
        return {"edge_1": [], "middle": [], "edge_2": []}

    low_key = f"{thickness_axis}1"
    high_key = f"{thickness_axis}2"
    wall_min = min(c[low_key] for c in cuboids)
    wall_max = max(c[high_key] for c in cuboids)
    thickness = wall_max - wall_min

    if thickness <= EPS:
        return {"edge_1": cuboids, "middle": [], "edge_2": []}

    one_third = thickness / 3.0
    cuts = (
        wall_min,
        wall_min + one_third,
        wall_min + 2.0 * one_third,
        wall_max,
    )

    layers = {"edge_1": [], "middle": [], "edge_2": []}
    intervals = (
        ("edge_1", cuts[0], cuts[1]),
        ("middle", cuts[1], cuts[2]),
        ("edge_2", cuts[2], cuts[3]),
    )

    for cuboid in cuboids:
        for layer_name, lower, upper in intervals:
            clipped = _clip_cuboid_to_axis_range(
                cuboid,
                thickness_axis,
                lower,
                upper,
            )
            if clipped is not None:
                layers[layer_name].append(clipped)

    return layers


def plot_three_layer_wall_groups_pyvista(
    wall_groups,
    title="Cuboids",
    save_path=None,
    light_brown="#C8A27A",
    dark_brown="#6B3E26",
    show_outer_edges=True,
    edge_color="black",
    feature_angle=30,
):
    """
    Plot all walls with three equal layers through each wall's thickness.

    Each wall group must contain:
        cuboids
        thickness_axis: "x", "y", or "z"

    The two outside thirds are light brown and the middle third is dark brown.
    """
    if save_path:
        save_path = Path(save_path)
        save_path.parent.mkdir(parents=True, exist_ok=True)

    plotter = pv.Plotter(off_screen=save_path is not None)
    plotter.set_background("white")

    meshes_by_layer = {
        "edge_1": [],
        "middle": [],
        "edge_2": [],
    }
    all_original_cuboids = []

    for group in wall_groups:
        cuboids = group.get("cuboids", [])
        thickness_axis = group["thickness_axis"]
        all_original_cuboids.extend(cuboids)

        split_layers = split_wall_cuboids_into_three_layers(
            cuboids,
            thickness_axis,
        )
        for layer_name, layer_cuboids in split_layers.items():
            meshes_by_layer[layer_name].extend(layer_cuboids)

    layer_colors = {
        "edge_1": light_brown,
        "middle": dark_brown,
        "edge_2": light_brown,
    }

    for layer_name in ("edge_1", "middle", "edge_2"):
        layer_cuboids = meshes_by_layer[layer_name]
        surface, _ = cuboids_to_outer_surface_and_edges(
            layer_cuboids,
            feature_angle=feature_angle,
        )
        if surface is not None:
            plotter.add_mesh(
                surface,
                color=layer_colors[layer_name],
                show_edges=False,
                smooth_shading=False,
            )

    if show_outer_edges:
        _, edges = cuboids_to_outer_surface_and_edges(
            all_original_cuboids,
            feature_angle=feature_angle,
        )
        if edges is not None and edges.n_cells > 0:
            plotter.add_mesh(
                edges,
                color=edge_color,
                line_width=2,
            )

    plotter.add_title(title, font_size=12)
    plotter.view_isometric()
    plotter.reset_camera()
    plotter.camera_position = [
        (200, -100, 150),
        (75, 75, 15),
        (0, 0, 1),
    ]
    plotter.reset_camera()
    plotter.camera.zoom(0.85)

    if save_path:
        plotter.render()
        plotter.screenshot(str(save_path))
        plotter.close()
        print(f"Saved to {save_path}")
    else:
        plotter.show()

def plot_cuboids_pyvista(
    cuboids,
    title="Cuboids",
    save_path=None,
    show_outer_edges=True,
    edge_color="black",
    feature_angle=30,
):
    """Plot cuboids as one clean object.

    Important:
    This does NOT use show_edges=True on every voxel cuboid, because that creates
    the unwanted grid. Instead it extracts the visible outside surface and draws
    only the outer/feature edges.
    """
    cuboids = [normalize(c) for c in cuboids if volume(normalize(c)) > EPS]
    print(f"3D cuboids to draw: {len(cuboids)}")

    if save_path:
        save_path = Path(save_path)
        save_path.parent.mkdir(parents=True, exist_ok=True)

    plotter = pv.Plotter(off_screen=save_path is not None)
    plotter.set_background("white")

    surface, edges = cuboids_to_outer_surface_and_edges(
        cuboids,
        feature_angle=feature_angle,
    )

    if surface is not None:
        plotter.add_mesh(
            surface,
            color="steelblue",
            show_edges=False,
            smooth_shading=False,
        )

    if show_outer_edges and edges is not None and edges.n_cells > 0:
        plotter.add_mesh(
            edges,
            color=edge_color,
            line_width=2,
        )

    plotter.add_title(title, font_size=12)

    # Fit the whole object automatically instead of using a fixed camera that can crop it.
    plotter.view_isometric()
    plotter.reset_camera()
    plotter.camera_position = [
        (200, -100, 150),
        (75, 75, 15),
        (0, 0, 1),
    ]
    plotter.reset_camera()
    plotter.camera.zoom(0.85)

    if save_path:
        plotter.render()
        plotter.screenshot(str(save_path))
        plotter.close()
        print(f"Saved to {save_path}")
    else:
        plotter.show()


def get_2d_projection(wall_name, orientation=None):
    """
    Choose a deterministic 2D projection.

    Rules:
        name ending in "_base" or exactly "base" -> XY, looking along Z
        orientation == "vertical"               -> YZ, looking along X
        orientation == "horizontal"             -> XZ, looking along Y
    """
    normalized_name = str(wall_name or "").strip().lower().rstrip("_")
    normalized_orientation = str(orientation or "").strip().lower()
    last_part = normalized_name.split("_")[-1] if normalized_name else ""

    if last_part == "base":
        axis = "z"
        plane = ("x1", "x2", "y1", "y2")
        plane_name = "XY"
    elif normalized_orientation == "vertical":
        axis = "x"
        plane = ("y1", "y2", "z1", "z2")
        plane_name = "YZ"
    elif normalized_orientation == "horizontal":
        axis = "y"
        plane = ("x1", "x2", "z1", "z2")
        plane_name = "XZ"
    else:
        raise ValueError(
            f"Cannot determine projection for wall={wall_name!r}, "
            f"orientation={orientation!r}. Expected a name ending in "
            f"'_base', orientation='vertical', or orientation='horizontal'."
        )

    print(
        f"2D projection for {wall_name}: orientation={orientation}, "
        f"plane={plane_name}, viewing along {axis.upper()}"
    )
    return axis, plane


def _point(horizontal, vertical):
    """Return one JSON-safe 2D point."""
    return {
        "horizontal": float(horizontal),
        "vertical": float(vertical),
    }


def _line(start_horizontal, start_vertical, end_horizontal, end_vertical,
          source, part_index, edge_name, parent_width_2d, parent_height_2d):
    """Return one JSON-safe 2D line primitive."""
    dx = float(end_horizontal - start_horizontal)
    dy = float(end_vertical - start_vertical)
    return {
        "type": "line",
        "source": source,
        "part_index": int(part_index),
        "edge": edge_name,
        "start": _point(start_horizontal, start_vertical),
        "end": _point(end_horizontal, end_vertical),
        "width_2d": abs(dx),
        "height_2d": abs(dy),
        "length_2d": float(np.hypot(dx, dy)),
        "parent_width_2d": float(parent_width_2d),
        "parent_height_2d": float(parent_height_2d),
    }



def _rectangle_part(c, b1, b2, c1, c2, source, part_index):
    """
    Convert a projected cuboid into one closed 2D polygon.

    width_2d is the horizontal span.
    length_2d is the vertical span (also exposed as height_2d).
    """
    left = float(c[b1])
    right = float(c[b2])
    bottom = float(c[c1])
    top = float(c[c2])

    width_2d = right - left
    length_2d = top - bottom

    polygon_points = [
        _point(left, bottom),
        _point(right, bottom),
        _point(right, top),
        _point(left, top),
        _point(left, bottom),  # close the polygon
    ]

    lines = [
        _line(left, bottom, right, bottom, source, part_index, "bottom", width_2d, length_2d),
        _line(right, bottom, right, top, source, part_index, "right", width_2d, length_2d),
        _line(right, top, left, top, source, part_index, "top", width_2d, length_2d),
        _line(left, top, left, bottom, source, part_index, "left", width_2d, length_2d),
    ]

    return {
        "type": "polygon",
        "shape": "rectangle",
        "source": source,
        "part_index": int(part_index),
        "width_2d": float(width_2d),
        "length_2d": float(length_2d),
        "height_2d": float(length_2d),
        "area_2d": float(width_2d * length_2d),
        "polygon_points": polygon_points,
        "bounds_2d": {
            "horizontal_min": left,
            "horizontal_max": right,
            "vertical_min": bottom,
            "vertical_max": top,
        },
        "corners": {
            "bottom_left": _point(left, bottom),
            "bottom_right": _point(right, bottom),
            "top_right": _point(right, top),
            "top_left": _point(left, top),
        },
        "lines": lines,
        "source_3d": {
            "x1": float(c["x1"]),
            "x2": float(c["x2"]),
            "y1": float(c["y1"]),
            "y2": float(c["y2"]),
            "z1": float(c["z1"]),
            "z2": float(c["z2"]),
        },
    }


def _arc_points(center_horizontal, center_vertical, radius,
                start_angle, end_angle, steps=33):
    """Sample an arc into points, including both endpoints."""
    angles = np.linspace(
        np.deg2rad(start_angle),
        np.deg2rad(end_angle),
        max(2, int(steps)),
    )
    return [
        _point(
            center_horizontal + radius * np.cos(angle),
            center_vertical + radius * np.sin(angle),
        )
        for angle in angles
    ]



def _arc_part(h, b1, b2, c1, c2, source, part_index, arc_steps=33):
    """
    Return a semicircle or quarter-circle as a closed polygon.

    The curved edge is sampled into points. The returned polygon represents the
    filled wedge that is drawn by Matplotlib.

    Supported shape values:
        semi, semicircle
        quarter, quarter_circle

    Optional arc metadata:
        start_angle
        end_angle
        center_horizontal
        center_vertical
        radius
    """
    shape = str(h.get("shape", "semi")).strip().lower()

    if shape in {"semi", "semicircle"}:
        start_angle = float(h.get("start_angle", 180.0))
        end_angle = float(h.get("end_angle", 360.0))
        default_center_horizontal = (h[b1] + h[b2]) / 2
        default_center_vertical = h[c2]
        default_radius = (h[b2] - h[b1]) / 2
        canonical_shape = "semicircle"
    elif shape in {"quarter", "quarter_circle"}:
        start_angle = float(h.get("start_angle", 270.0))
        end_angle = float(h.get("end_angle", 360.0))
        default_center_horizontal = h[b1]
        default_center_vertical = h[c2]
        default_radius = min(h[b2] - h[b1], h[c2] - h[c1])
        canonical_shape = "quarter_circle"
    else:
        raise ValueError(f"Unsupported arc shape: {shape!r}")

    center_horizontal = float(
        h.get("center_horizontal", default_center_horizontal)
    )
    center_vertical = float(
        h.get("center_vertical", default_center_vertical)
    )
    radius = float(h.get("radius", default_radius))

    arc_points = _arc_points(
        center_horizontal,
        center_vertical,
        radius,
        start_angle,
        end_angle,
        steps=arc_steps,
    )

    # Wedge polygon: center -> arc -> center.
    polygon_points = [
        _point(center_horizontal, center_vertical),
        *arc_points,
        _point(center_horizontal, center_vertical),
    ]

    horizontal_values = [point["horizontal"] for point in polygon_points]
    vertical_values = [point["vertical"] for point in polygon_points]
    horizontal_min = min(horizontal_values)
    horizontal_max = max(horizontal_values)
    vertical_min = min(vertical_values)
    vertical_max = max(vertical_values)
    width_2d = horizontal_max - horizontal_min
    length_2d = vertical_max - vertical_min

    sweep_radians = abs(np.deg2rad(end_angle - start_angle))
    sector_area = 0.5 * radius * radius * sweep_radians

    return {
        "type": "polygon",
        "shape": canonical_shape,
        "source": source,
        "part_index": int(part_index),
        "center": _point(center_horizontal, center_vertical),
        "radius": radius,
        "start_angle_degrees": start_angle,
        "end_angle_degrees": end_angle,
        "sweep_angle_degrees": float(end_angle - start_angle),
        "clockwise": False,
        "start_point": arc_points[0],
        "end_point": arc_points[-1],
        "arc_points": arc_points,
        "polygon_points": polygon_points,
        "width_2d": float(width_2d),
        "length_2d": float(length_2d),
        "height_2d": float(length_2d),
        "area_2d": float(sector_area),
        "bounds_2d": {
            "horizontal_min": float(horizontal_min),
            "horizontal_max": float(horizontal_max),
            "vertical_min": float(vertical_min),
            "vertical_max": float(vertical_max),
        },
        "source_3d": {
            "x1": float(h["x1"]),
            "x2": float(h["x2"]),
            "y1": float(h["y1"]),
            "y2": float(h["y2"]),
            "z1": float(h["z1"]),
            "z2": float(h["z2"]),
        },
    }



def get_projected_2d_geometry(
    solids,
    holes=None,
    wall_name=None,
    orientation=None,
    arc_steps=33,
):
    """
    Return every projected 2D polygon for one wall.

    The "polygons" list contains both solid and hole polygons. Every polygon has:
        width_2d
        length_2d
        height_2d
        polygon_points
        source ("solid" or "hole")

    Rectangles have four corners plus a repeated closing point.
    Semicircles and quarter-circles are returned as sampled wedge polygons.
    """
    solids = [normalize(c) for c in solids]
    holes = [normalize(h) for h in (holes or [])]

    projection_axis, (b1, b2, c1, c2) = get_2d_projection(
        wall_name=wall_name,
        orientation=orientation,
    )

    horizontal_axis = b1[0].upper()
    vertical_axis = c1[0].upper()
    projection_plane = f"{horizontal_axis}{vertical_axis}"

    all_cuboids = solids + holes
    if all_cuboids:
        horizontal_min = float(min(c[b1] for c in all_cuboids))
        horizontal_max = float(max(c[b2] for c in all_cuboids))
        vertical_min = float(min(c[c1] for c in all_cuboids))
        vertical_max = float(max(c[c2] for c in all_cuboids))
    else:
        horizontal_min = horizontal_max = 0.0
        vertical_min = vertical_max = 0.0

    full_2d_width = horizontal_max - horizontal_min
    full_2d_length = vertical_max - vertical_min

    solid_polygons = []
    hole_polygons = []
    polygons = []
    lines = []

    for index, solid in enumerate(solids):
        polygon = _rectangle_part(
            solid, b1, b2, c1, c2, "solid", index
        )
        solid_polygons.append(polygon)
        polygons.append(polygon)
        lines.extend(polygon["lines"])

    for index, hole in enumerate(holes):
        shape = str(hole.get("shape", "rect")).strip().lower()

        if shape in {"semi", "semicircle", "quarter", "quarter_circle"}:
            polygon = _arc_part(
                hole,
                b1,
                b2,
                c1,
                c2,
                "hole",
                index,
                arc_steps=arc_steps,
            )
        else:
            polygon = _rectangle_part(
                hole, b1, b2, c1, c2, "hole", index
            )
            lines.extend(polygon["lines"])

        hole_polygons.append(polygon)
        polygons.append(polygon)

    return {
        "wall_name": str(wall_name),
        "orientation": orientation,
        "projection_axis": projection_axis.upper(),
        "projection_plane": projection_plane,
        "horizontal_axis": horizontal_axis,
        "vertical_axis": vertical_axis,
        "full_2d_width": float(full_2d_width),
        "full_2d_length": float(full_2d_length),
        "full_2d_height": float(full_2d_length),
        "full_2d_area": float(full_2d_width * full_2d_length),
        "bounds_2d": {
            "horizontal_min": horizontal_min,
            "horizontal_max": horizontal_max,
            "vertical_min": vertical_min,
            "vertical_max": vertical_max,
        },
        "solid_polygons": solid_polygons,
        "hole_polygons": hole_polygons,
        "polygons": polygons,
        "lines": lines,
    }


def plot_2d_projection(
    solids,
    holes=None,
    title="2D Projection",
    save_path=None,
    wall_name=None,
    orientation=None,
    arc_steps=33,
):
    """
    Draw one 2D wall projection and return the complete projected geometry.
    """
    solids = [normalize(c) for c in solids]
    holes = [normalize(h) for h in (holes or [])]
    resolved_wall_name = wall_name or title

    geometry = get_projected_2d_geometry(
        solids,
        holes=holes,
        wall_name=resolved_wall_name,
        orientation=orientation,
        arc_steps=arc_steps,
    )

    projection_axis = geometry["projection_axis"].lower()
    planes = {
        "x": ("y1", "y2", "z1", "z2"),
        "y": ("x1", "x2", "z1", "z2"),
        "z": ("x1", "x2", "y1", "y2"),
    }
    b1, b2, c1, c2 = planes[projection_axis]

    print(f"2D solid rectangles to draw: {len(solids)}")
    print(f"2D holes to draw: {len(holes)}")
    print(
        f"Full 2D size: {geometry['full_2d_width']} x "
        f"{geometry['full_2d_height']} "
        f"({geometry['horizontal_axis']} x {geometry['vertical_axis']})"
    )

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.set_facecolor("white")
    ax.set_aspect("equal")

    for c in solids:
        ax.add_patch(
            patches.Rectangle(
                (c[b1], c[c1]),
                c[b2] - c[b1],
                c[c2] - c[c1],
                linewidth=0,
                facecolor="steelblue",
            )
        )

    for h in holes:
        shape = str(h.get("shape", "rect")).strip().lower()

        if shape in {"semi", "semicircle", "quarter", "quarter_circle"}:
            part = _arc_part(
                h,
                b1,
                b2,
                c1,
                c2,
                "hole",
                0,
                arc_steps=arc_steps,
            )
            ax.add_patch(
                patches.Wedge(
                    (
                        part["center"]["horizontal"],
                        part["center"]["vertical"],
                    ),
                    part["radius"],
                    part["start_angle_degrees"],
                    part["end_angle_degrees"],
                    linewidth=0,
                    facecolor="white",
                )
            )
        else:
            ax.add_patch(
                patches.Rectangle(
                    (h[b1], h[c1]),
                    h[b2] - h[b1],
                    h[c2] - h[c1],
                    linewidth=0,
                    facecolor="white",
                )
            )

    bounds = geometry["bounds_2d"]
    if solids or holes:
        ax.set_xlim(
            bounds["horizontal_min"],
            bounds["horizontal_max"],
        )
        ax.set_ylim(
            bounds["vertical_min"],
            bounds["vertical_max"],
        )

    ax.set_xlabel(geometry["horizontal_axis"])
    ax.set_ylabel(geometry["vertical_axis"])
    ax.set_title(title)
    plt.tight_layout()

    if save_path:
        save_path = Path(save_path)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(str(save_path), dpi=200)
        plt.close(fig)
        print(f"Saved to {save_path}")
    else:
        plt.show()

    return geometry


def safe_filename(name):
    """Make a string safe to use as a file name."""
    allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
    cleaned = "".join(ch if ch in allowed else "_" for ch in str(name))
    cleaned = cleaned.strip("_")
    return cleaned or "wall"


def get_wall_name_and_cuboids(wall, index):
    """
    Return:
        wall name
        cuboids
        orientation
    """
    if isinstance(wall, dict):
        name = (
            wall.get("id")
            or wall.get("source_id")
            or wall.get("parent_id")
            or f"wall_{index}"
        )
        cuboids = wall.get("3D_cuboids", [])
        orientation = wall.get("orientation")
        return str(name), cuboids, orientation

    return f"wall_{index}", wall, None



def flatten_wall_input(walls):
    """
    Accept either a list of wall dictionaries or a dictionary of wall groups.

    Examples:
        [wall, wall, ...]
        {"rect33_base": [wall, ...], "outer_left": [wall, ...]}
    """
    if isinstance(walls, dict):
        flattened = []
        for group in walls.values():
            if isinstance(group, (list, tuple)):
                flattened.extend(group)
            else:
                flattened.append(group)
        return flattened

    return list(walls)



def _json_default(value):
    """Convert common non-JSON values used by this module."""
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, np.generic):
        return value.item()
    raise TypeError(
        f"Object of type {type(value).__name__} is not JSON serializable"
    )



def _ring_points_local(ring, offset_x, offset_y):
    """Convert a Shapely ring to closed local x/y point dictionaries."""
    return [
        {
            "x": float(x - offset_x),
            "y": float(y - offset_y),
        }
        for x, y in ring.coords
    ]


def _ring_return_record(
    ring,
    *,
    offset_x,
    offset_y,
    is_hole,
    component_index,
    hole_index=None,
):
    """Return one exterior or enclosed interior ring."""
    points = _ring_points_local(ring, offset_x, offset_y)
    xs = [point["x"] for point in points]
    ys = [point["y"] for point in points]

    x1 = min(xs)
    x2 = max(xs)
    y1 = min(ys)
    y2 = max(ys)

    record = {
        "shape": "inside_hole" if is_hole else "exterior",
        "is_hole": bool(is_hole),
        "component_index": int(component_index),
        "width": float(x2 - x1),
        "length": float(y2 - y1),
        "points": points,
        "boundaries": {
            "x1": float(x1),
            "x2": float(x2),
            "y1": float(y1),
            "y2": float(y2),
        },
    }

    if hole_index is not None:
        record["hole_index"] = int(hole_index)

    return record


def _iter_union_polygons(geometry):
    """Yield Polygon objects from Polygon, MultiPolygon or collections."""
    if geometry.is_empty:
        return

    if isinstance(geometry, Polygon):
        yield geometry
        return

    if isinstance(geometry, MultiPolygon):
        yield from geometry.geoms
        return

    if isinstance(geometry, GeometryCollection):
        for part in geometry.geoms:
            yield from _iter_union_polygons(part)


def _element_return_data(geometry_2d):
    """
    Merge all projected solid cells into their true 2D wall shape.

    The result contains one exterior polygon per connected component. Only
    fully enclosed empty areas are returned as separate inside-hole polygons.
    Openings/notches that touch the outside boundary become part of the exterior
    polygon and are not returned as holes.

    All returned coordinates are translated so the complete element begins at
    (0, 0).
    """
    solid_shapes = []

    for solid in geometry_2d["solid_polygons"]:
        coordinates = [
            (point["horizontal"], point["vertical"])
            for point in solid["polygon_points"]
        ]
        polygon = Polygon(coordinates)
        if not polygon.is_empty and polygon.area > EPS:
            solid_shapes.append(polygon)

    if not solid_shapes:
        return {
            "id": geometry_2d["wall_name"],
            "orientation": geometry_2d["orientation"],
            "projection_plane": geometry_2d["projection_plane"],
            "polygons": [],
            "boundaries": {
                "x1": 0.0,
                "x2": 0.0,
                "y1": 0.0,
                "y2": 0.0,
                "width": 0.0,
                "length": 0.0,
            },
            "original_origin": {"x": 0.0, "y": 0.0},
        }

    merged = unary_union(solid_shapes)

    # Repair occasional tiny numerical invalidities without changing the
    # visible graph-generation path.
    if not merged.is_valid:
        merged = merged.buffer(0)

    min_x, min_y, max_x, max_y = merged.bounds
    width = float(max_x - min_x)
    length = float(max_y - min_y)

    polygons = []
    components = sorted(
        _iter_union_polygons(merged),
        key=lambda polygon: polygon.area,
        reverse=True,
    )

    for component_index, polygon in enumerate(components):
        exterior = _ring_return_record(
            polygon.exterior,
            offset_x=min_x,
            offset_y=min_y,
            is_hole=False,
            component_index=component_index,
        )
        exterior["area"] = float(polygon.area)
        exterior["inside_hole_count"] = len(polygon.interiors)
        polygons.append(exterior)

        for hole_index, interior in enumerate(polygon.interiors):
            hole_record = _ring_return_record(
                interior,
                offset_x=min_x,
                offset_y=min_y,
                is_hole=True,
                component_index=component_index,
                hole_index=hole_index,
            )
            polygons.append(hole_record)

    return {
        "id": geometry_2d["wall_name"],
        "orientation": geometry_2d["orientation"],
        "projection_plane": geometry_2d["projection_plane"],
        "polygons": polygons,
        "boundaries": {
            "x1": 0.0,
            "x2": width,
            "y1": 0.0,
            "y2": length,
            "width": width,
            "length": length,
        },
        "original_origin": {
            "x": float(min_x),
            "y": float(min_y),
        },
    }

def generate_wall_graphs_timed(
    walls,
    out_dir,
    wall_width=5,
    semi_steps_3d=10,
    semi_steps_2d=64,
    polygon_arc_steps=33,
):
    """
    Draw the same combined 3D graph and separate 2D wall graphs as before.

    Return only a list of wall elements. All projected solid cells are unioned
    into one exterior polygon per connected component. Only fully enclosed
    empty regions are returned as separate inside-hole polygons. Open cutouts
    touching the exterior remain part of the exterior contour.

    Every returned element is translated into local 2D coordinates so its
    lower-left boundary is (0, 0).

    Return example:
        [
            {
                "id": "wall_name",
                "polygons": [
                    {
                        "shape": "rectangle",
                        "source": "solid",
                        "is_hole": False,
                        "width": 20.0,
                        "length": 50.0,
                        "points": [{"x": 0.0, "y": 0.0}, ...],
                        "boundaries": {
                            "x1": 0.0,
                            "x2": 20.0,
                            "y1": 0.0,
                            "y2": 50.0,
                        },
                    },
                    ...
                ],
                "boundaries": {
                    "x1": 0.0,
                    "x2": 20.0,
                    "y1": 0.0,
                    "y2": 50.0,
                    "width": 20.0,
                    "length": 50.0,
                },
            }
        ]

    `walls` may be either a flat list of wall dictionaries or a dictionary
    containing wall-group lists, such as walls_with_ridges["Layer 1"].
    """
    walls = flatten_wall_input(walls)

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    total_start = perf_counter()

    print("\n--- Merging individual walls ---")
    merged_groups = []
    combined_result = []

    for i, wall in enumerate(walls, start=1):
        wall_name, wall_cuboids, orientation = get_wall_name_and_cuboids(
            wall,
            i,
        )

        print(f"\n{wall_name}")

        result, holes = timed(
            f"merge {wall_name}",
            merge_cuboids_preserve_internal_holes,
            wall_cuboids,
            semi_steps=semi_steps_3d,
            wall_width=wall_width,
        )

        voxel_count = len(result)
        result = timed(
            f"collapse adjacent cells {wall_name}",
            merge_adjacent_cuboids,
            result,
        )

        print(
            f"{wall_name}: cuboids {voxel_count} -> {len(result)}, "
            f"holes={len(holes)}, orientation={orientation}"
        )

        thickness_axis, _ = get_2d_projection(
            wall_name=wall_name,
            orientation=orientation,
        )

        merged_groups.append(
            (wall_name, orientation, thickness_axis, result, holes)
        )
        combined_result.extend(result)

    print(f"\ncombined 3D cuboids={len(combined_result)}")

    print("\n--- Plotting combined 3D ---")
    combined_3d_path = out_dir / "combined_walls_3d.png"
    timed(
        "plot combined 3D",
        plot_cuboids_pyvista,
        combined_result,
        title="Combined walls - 3D",
        save_path=combined_3d_path,
        show_outer_edges=False,
    )

    print("\n--- Plotting separate 2D images ---")
    returned_elements = []

    for wall_name, orientation, thickness_axis, result, holes in merged_groups:
        file_stem = safe_filename(wall_name)
        save_path = out_dir / f"{file_stem}.png"

        geometry_2d = timed(
            f"plot {wall_name} 2D",
            plot_2d_projection,
            result,
            holes=holes,
            title=wall_name,
            save_path=save_path,
            wall_name=wall_name,
            orientation=orientation,
            arc_steps=polygon_arc_steps,
        )

        returned_elements.append(
            _element_return_data(geometry_2d)
        )

    print(f"\nTOTAL: {perf_counter() - total_start:.3f}s")
    return returned_elements
