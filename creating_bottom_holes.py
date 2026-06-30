from pathlib import Path
from time import perf_counter

import numpy as np
import pyvista as pv

EPS = 0.0001


def timed(label, fn, *args, **kwargs):
    start = perf_counter()
    result = fn(*args, **kwargs)
    elapsed = perf_counter() - start
    print(f"{label}: {elapsed:.3f}s")
    return result


def normalize(c):
    return {
        "x1": min(c["x1"], c["x2"]),
        "x2": max(c["x1"], c["x2"]),
        "y1": min(c["y1"], c["y2"]),
        "y2": max(c["y1"], c["y2"]),
        "z1": min(c["z1"], c["z2"]),
        "z2": max(c["z1"], c["z2"]),
        "shape": c.get("shape", "rect"),
    }


def volume(c):
    return (
        max(0, c["x2"] - c["x1"])
        * max(0, c["y2"] - c["y1"])
        * max(0, c["z2"] - c["z1"])
    )


def contains_point(c, x, y, z, eps=EPS):
    return (
        c["x1"] - eps <= x <= c["x2"] + eps
        and c["y1"] - eps <= y <= c["y2"] + eps
        and c["z1"] - eps <= z <= c["z2"] + eps
    )


def get_wall_axis(c, wall_width, eps=EPS):
    c = normalize(c)

    widths = {
        "x": c["x2"] - c["x1"],
        "y": c["y2"] - c["y1"],
        "z": c["z2"] - c["z1"],
    }

    matching = [
        axis for axis, width in widths.items()
        if abs(width - wall_width) <= eps
    ]

    if len(matching) != 1:
        raise ValueError(
            f"Expected exactly one wall-width axis for {c}, "
            f"but found {matching}. Widths={widths}, wall_width={wall_width}"
        )

    return matching[0]


def contains_semi_point(h, x, y, z, wall_width, eps=EPS):
    h = normalize(h)
    wall_axis = get_wall_axis(h, wall_width, eps)

    if wall_axis == "y":
        cx = (h["x1"] + h["x2"]) / 2
        r = (h["x2"] - h["x1"]) / 2

        if not contains_point(h, x, y, z, eps):
            return False

        return (x - cx) ** 2 + (z - h["z2"]) ** 2 <= r ** 2 + eps

    if wall_axis == "x":
        cy = (h["y1"] + h["y2"]) / 2
        r = (h["y2"] - h["y1"]) / 2

        if not contains_point(h, x, y, z, eps):
            return False

        return (y - cy) ** 2 + (z - h["z2"]) ** 2 <= r ** 2 + eps

    if wall_axis == "z":
        cx = (h["x1"] + h["x2"]) / 2
        r = (h["x2"] - h["x1"]) / 2

        if not contains_point(h, x, y, z, eps):
            return False

        return (x - cx) ** 2 + (y - h["y2"]) ** 2 <= r ** 2 + eps

    return False


def contains_hole_point(h, x, y, z, wall_width):
    if h.get("shape") == "semi":
        return contains_semi_point(h, x, y, z, wall_width)

    return contains_point(h, x, y, z)


def is_inside_another(c, others, eps=EPS):
    for other in others:
        if other is c:
            continue

        if (
            c["x1"] >= other["x1"] - eps
            and c["x2"] <= other["x2"] + eps
            and c["y1"] >= other["y1"] - eps
            and c["y2"] <= other["y2"] + eps
            and c["z1"] >= other["z1"] - eps
            and c["z2"] <= other["z2"] + eps
        ):
            return True

    return False


def cuboid_to_pv(c):
    c = normalize(c)

    return pv.Box(
        bounds=(
            c["x1"],
            c["x2"],
            c["y1"],
            c["y2"],
            c["z1"],
            c["z2"],
        )
    )


def add_semi_grid_points(c, xs, ys, zs, wall_width, semi_steps):
    c = normalize(c)
    wall_axis = get_wall_axis(c, wall_width)

    if wall_axis == "y":
        cx = (c["x1"] + c["x2"]) / 2
        r = (c["x2"] - c["x1"]) / 2

        for t in np.linspace(np.pi, 2 * np.pi, semi_steps):
            xs.add(cx + r * np.cos(t))
            zs.add(c["z2"] + r * np.sin(t))

    elif wall_axis == "x":
        cy = (c["y1"] + c["y2"]) / 2
        r = (c["y2"] - c["y1"]) / 2

        for t in np.linspace(np.pi, 2 * np.pi, semi_steps):
            ys.add(cy + r * np.cos(t))
            zs.add(c["z2"] + r * np.sin(t))

    elif wall_axis == "z":
        cx = (c["x1"] + c["x2"]) / 2
        r = (c["x2"] - c["x1"]) / 2

        for t in np.linspace(np.pi, 2 * np.pi, semi_steps):
            xs.add(cx + r * np.cos(t))
            ys.add(c["y2"] + r * np.sin(t))


def merge_cuboids_preserve_internal_holes(cuboids, semi_steps=64, wall_width=4):
    cuboids = [normalize(c) for c in cuboids]

    solids = []
    holes = []

    for c in cuboids:
        if c.get("shape") == "semi":
            solid_part = dict(c)
            solid_part["shape"] = "rect"
            solids.append(solid_part)

            holes.append(semi_to_hole(c, wall_width))

        elif is_inside_another(c, cuboids):
            holes.append(c)

        else:
            solids.append(c)

    all_for_grid = solids + holes

    xs = {v for c in all_for_grid for v in (c["x1"], c["x2"])}
    ys = {v for c in all_for_grid for v in (c["y1"], c["y2"])}
    zs = {v for c in all_for_grid for v in (c["z1"], c["z2"])}

    for h in holes:
        if h.get("shape") == "semi":
            add_semi_grid_points(h, xs, ys, zs, wall_width, semi_steps)

    xs = sorted(xs)
    ys = sorted(ys)
    zs = sorted(zs)

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
                }

                if volume(cell) <= EPS:
                    continue

                cx = (cell["x1"] + cell["x2"]) / 2
                cy = (cell["y1"] + cell["y2"]) / 2
                cz = (cell["z1"] + cell["z2"]) / 2

                in_solid = any(contains_point(s, cx, cy, cz) for s in solids)
                in_hole = any(
                    contains_hole_point(h, cx, cy, cz, wall_width)
                    for h in holes
                )

                if in_solid and not in_hole:
                    result.append(cell)

    print(f"Result cuboids: {len(result)}")

    return result, holes


def plot_cuboids_pyvista(cuboids, title="Cuboids", save_path=None):
    cuboids = [normalize(c) for c in cuboids]

    if save_path:
        save_path = Path(save_path)
        save_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"3D cuboids to draw: {len(cuboids)}")

    plotter = pv.Plotter(off_screen=save_path is not None)
    plotter.set_background("white")

    for c in cuboids:
        plotter.add_mesh(
            cuboid_to_pv(c),
            color="steelblue",
            show_edges=False,
        )

    plotter.add_title(title, font_size=12)

    plotter.camera_position = [
        (200, -200, 150),
        (75, 2, 15),
        (0, 0, 1),
    ]

    if save_path:
        plotter.render()
        plotter.screenshot(str(save_path))
        plotter.close()
        print(f"Saved to {save_path}")
    else:
        plotter.show()


def get_2d_projection(solids, holes=None, eps=EPS):
    holes = holes or []
    all_cuboids = solids + holes

    def is_uniform_axis(a1, a2):
        widths = [(c[a2] - c[a1]) for c in all_cuboids]
        return max(widths) - min(widths) < eps

    for axis, (a1, a2), (b1, b2), (c1, c2) in [
        ("x", ("x1", "x2"), ("y1", "y2"), ("z1", "z2")),
        ("y", ("y1", "y2"), ("x1", "x2"), ("z1", "z2")),
        ("z", ("z1", "z2"), ("x1", "x2"), ("y1", "y2")),
    ]:
        if is_uniform_axis(a1, a2):
            print(
                f"2D projection: thin axis {axis}, "
                f"plane {b1[0].upper()}{c1[0].upper()}"
            )
            return axis, (b1, b2, c1, c2)

    raise ValueError("No uniform thin axis found")


def plot_2d_projection(solids, holes=None, title="2D Projection", save_path=None):
    import matplotlib.pyplot as plt
    import matplotlib.patches as patches

    solids = [normalize(c) for c in solids]
    holes = [normalize(h) for h in (holes or [])]

    print(f"2D solid rectangles to draw: {len(solids)}")
    print(f"2D holes to draw: {len(holes)}")

    axis, (b1, b2, c1, c2) = get_2d_projection(solids, holes)

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
        if h.get("shape") == "semi":
            cx = (h[b1] + h[b2]) / 2
            r = (h[b2] - h[b1]) / 2

            ax.add_patch(
                patches.Wedge(
                    (cx, h[c2]),
                    r,
                    180,
                    360,
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

    all_cuboids = solids + holes

    ax.set_xlim(
        min(c[b1] for c in all_cuboids),
        max(c[b2] for c in all_cuboids),
    )
    ax.set_ylim(
        min(c[c1] for c in all_cuboids),
        max(c[c2] for c in all_cuboids),
    )

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

def semi_to_hole(c, wall_width, eps=EPS):
    """
    shape='semi' is treated as a solid wall section,
    and this function creates the semicircular hole inside it.
    """
    c = normalize(c)
    wall_axis = get_wall_axis(c, wall_width, eps)

    hole = dict(c)
    hole["shape"] = "semi"

    if wall_axis == "y":
        # Wall thickness through Y, semicircle in XZ
        r = (c["x2"] - c["x1"]) / 2
        hole["z1"] = c["z2"] - r

    elif wall_axis == "x":
        # Wall thickness through X, semicircle in YZ
        r = (c["y2"] - c["y1"]) / 2
        hole["z1"] = c["z2"] - r

    elif wall_axis == "z":
        # Wall thickness through Z, semicircle in XY
        r = (c["x2"] - c["x1"]) / 2
        hole["y1"] = c["y2"] - r

    return hole


def generate_wall_graphs_timed(
    walls,
    out_dir,
    wall_width=5,
    semi_steps_3d=10,
    semi_steps_2d=64,
):
    """
    walls must be a list of wall groups:

    walls = [
        [cuboid, cuboid, cuboid],
        [cuboid, cuboid, cuboid],
        ...
    ]
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    total_start = perf_counter()

    merged_groups = []

    print("\n--- Merging individual walls for 2D ---")

    for i, wall in enumerate(walls, start=1):
        print(f"\nWall {i}")

        result, holes = timed(
            f"merge wall {i} (2D)",
            merge_cuboids_preserve_internal_holes,
            wall,
            semi_steps=semi_steps_2d,
            wall_width=wall_width,
        )

        print(f"wall {i}: result cuboids={len(result)}, holes={len(holes)}")
        merged_groups.append((result, holes))

    print("\n--- Building combined 3D data ---")

    combined_input = []

    for wall in walls:
        combined_input.extend(wall)

    combined_result, _ = timed(
        "merge combined 3D",
        merge_cuboids_preserve_internal_holes,
        combined_input,
        semi_steps=semi_steps_3d,
        wall_width=wall_width,
    )

    print(f"combined 3D cuboids={len(combined_result)}")

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

    for i, (result, holes) in enumerate(merged_groups, start=1):
        save_path = out_dir / f"wall_{i}_2d.png"

        timed(
            f"plot wall {i} 2D",
            plot_2d_projection,
            result,
            holes=holes,
            title=f"Wall {i} - 2D",
            save_path=save_path,
        )

        walls_2d[f"wall_{i}"] = save_path

    print(f"\nTOTAL: {perf_counter() - total_start:.3f}s")

    return {
        "combined_3d": combined_3d_path,
        "walls_2d": walls_2d,
    }