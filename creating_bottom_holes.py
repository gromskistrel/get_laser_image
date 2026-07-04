from pathlib import Path
from time import perf_counter

import numpy as np
import pyvista as pv
import matplotlib.pyplot as plt
import matplotlib.patches as patches

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

                if any(contains_box(s, cx, cy, cz) for s in solids) and not any(
                    contains_hole(h, cx, cy, cz, wall_width) for h in holes
                ):
                    result.append(cell)

    print(f"Result cuboids: {len(result)}")
    return result, holes


def cuboid_to_pv(c):
    c = normalize(c)
    return pv.Box(bounds=(c["x1"], c["x2"], c["y1"], c["y2"], c["z1"], c["z2"]))


def cuboids_to_outer_surface_and_edges(cuboids, feature_angle=30):
    """Build one visual surface from many voxel cuboids and extract only real outer edges.

    The merge algorithm returns many small cuboids. If PyVista draws edges on each
    cuboid directly, you see the voxel/grid lines. This function combines the
    cuboids, extracts the outside surface, and then extracts only feature edges
    from that surface.
    """
    boxes = [cuboid_to_pv(c) for c in cuboids if volume(normalize(c)) > EPS]

    if not boxes:
        return None, None

    merged = pv.MultiBlock(boxes).combine(merge_points=True)
    surface = merged.extract_surface().clean()

    edges = surface.extract_feature_edges(
        feature_angle=feature_angle,
        boundary_edges=True,
        feature_edges=True,
        manifold_edges=False,
        non_manifold_edges=False,
    )

    return surface, edges


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
    plotter.camera.zoom(0.85)

    if save_path:
        plotter.render()
        plotter.screenshot(str(save_path))
        plotter.close()
        print(f"Saved to {save_path}")
    else:
        plotter.show()

def get_2d_projection(solids, holes=None, eps=EPS):
    all_cuboids = [normalize(c) for c in solids + (holes or [])]

    for axis, thin, plane in [
        ("x", ("x1", "x2"), ("y1", "y2", "z1", "z2")),
        ("y", ("y1", "y2"), ("x1", "x2", "z1", "z2")),
        ("z", ("z1", "z2"), ("x1", "x2", "y1", "y2")),
    ]:
        widths = [c[thin[1]] - c[thin[0]] for c in all_cuboids]
        if max(widths) - min(widths) < eps:
            print(f"2D projection: thin axis {axis}, plane {plane[0][0].upper()}{plane[2][0].upper()}")
            return axis, plane

    raise ValueError("No uniform thin axis found")


def plot_2d_projection(solids, holes=None, title="2D Projection", save_path=None):

    solids = [normalize(c) for c in solids]
    holes = [normalize(h) for h in (holes or [])]
    print(f"2D solid rectangles to draw: {len(solids)}")
    print(f"2D holes to draw: {len(holes)}")

    _, (b1, b2, c1, c2) = get_2d_projection(solids, holes)

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.set_facecolor("white")
    ax.set_aspect("equal")

    for c in solids:
        ax.add_patch(patches.Rectangle((c[b1], c[c1]), c[b2] - c[b1], c[c2] - c[c1], linewidth=0, facecolor="steelblue"))

    for h in holes:
        if h.get("shape") == "semi":
            center = (h[b1] + h[b2]) / 2
            radius = (h[b2] - h[b1]) / 2
            ax.add_patch(patches.Wedge((center, h[c2]), radius, 180, 360, linewidth=0, facecolor="white"))
        else:
            ax.add_patch(patches.Rectangle((h[b1], h[c1]), h[b2] - h[b1], h[c2] - h[c1], linewidth=0, facecolor="white"))

    all_cuboids = solids + holes
    ax.set_xlim(min(c[b1] for c in all_cuboids), max(c[b2] for c in all_cuboids))
    ax.set_ylim(min(c[c1] for c in all_cuboids), max(c[c2] for c in all_cuboids))
    ax.set_xlabel(b1[0].upper())
    ax.set_ylabel(c1[0].upper())
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



def safe_filename(name):
    """Make a string safe to use as a file name."""
    allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
    cleaned = "".join(ch if ch in allowed else "_" for ch in str(name))
    cleaned = cleaned.strip("_")
    return cleaned or "wall"


def get_wall_name_and_cuboids(wall, index):
    """Accept either a wall dict or a raw cuboid list.

    Preferred input shape:
        {"id": "path2_outer_wall_41_split_1", "3D_cuboids": [...]}

    Backward-compatible input shape:
        [{...cuboid...}, {...cuboid...}]
    """
    if isinstance(wall, dict):
        name = wall.get("id") or wall.get("source_id") or wall.get("parent_id") or f"wall_{index}"
        cuboids = wall.get("3D_cuboids", [])
        return str(name), cuboids

    return f"wall_{index}", wall


def generate_wall_graphs_timed(walls, out_dir, wall_width=5, semi_steps_3d=10, semi_steps_2d=64):
    """
    Create one combined 3D image and one 2D image per wall group.

    The 3D image draws only the outer/feature edges, not the internal voxel grid.
    The 2D image filename and title use the wall id when the input wall is a dict.

    Important:
    Holes are subtracted PER WALL, not globally.
    If we flatten all walls first, a hole belonging to one wall can subtract
    material from a neighbouring wall at a corner/joint. That is what made
    parts of the bottom wall disappear.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    total_start = perf_counter()

    print("\n--- Merging individual walls ---")
    merged_groups = []
    combined_result = []

    for i, wall in enumerate(walls, start=1):
        wall_name, wall_cuboids = get_wall_name_and_cuboids(wall, i)
        print(f"\n{wall_name}")

        result, holes = timed(
            f"merge {wall_name}",
            merge_cuboids_preserve_internal_holes,
            wall_cuboids,
            semi_steps=semi_steps_2d,
            wall_width=wall_width,
        )

        print(f"{wall_name}: result cuboids={len(result)}, holes={len(holes)}")
        merged_groups.append((wall_name, result, holes))

        # Add already-subtracted wall geometry to the combined 3D model.
        # Do NOT run one global hole subtraction over all walls.
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
    )

    print("\n--- Plotting separate 2D images ---")
    walls_2d = {}

    for wall_name, result, holes in merged_groups:
        file_stem = safe_filename(wall_name)
        save_path = out_dir / f"{file_stem}.png"

        timed(
            f"plot {wall_name} 2D",
            plot_2d_projection,
            result,
            holes=holes,
            title=wall_name,
            save_path=save_path,
        )

        walls_2d[wall_name] = save_path

    print(f"\nTOTAL: {perf_counter() - total_start:.3f}s")

    return {
        "combined_3d": combined_3d_path,
        "walls_2d": walls_2d,
    }
