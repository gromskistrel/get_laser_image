from pathlib import Path

import matplotlib.pyplot as plt
from shapely.geometry import box
import math


FULL_HOLE_COLORS = {
    "#000000",
    "#000",
    "#1a1a1a",
    "black",
}

BROWN_COLORS = {
    "#552200",
    "#803300"
}



def safe_filename(name):
    return "".join(c if c.isalnum() or c in " _-" else "_" for c in name)


def bounds_dict_from_poly(poly):
    minx, miny, maxx, maxy = poly.bounds

    return {
        "x1": minx,
        "y1": miny,
        "x2": maxx,
        "y2": maxy,
        "length": maxx - minx,
        "width": maxy - miny,
    }


def bounds_poly_from_dict(bounds):
    return box(
        bounds["x1"],
        bounds["y1"],
        bounds["x2"],
        bounds["y2"],
    )


def normalize_color(color):
    if color is None:
        return None

    if isinstance(color, list):
        if not color:
            return None
        color = color[0].get("color")

    if isinstance(color, dict):
        color = color.get("color")

    if color is None:
        return None

    return str(color).strip().lower()


def clean_color(color, fallback="#cccccc"):
    if color is None:
        return fallback

    if isinstance(color, list):
        if not color:
            return fallback
        color = color[0].get("color")

    if isinstance(color, dict):
        color = color.get("color")

    if color is None:
        return fallback

    color = str(color).strip()

    if color.lower() in {"none", "transparent"}:
        return fallback

    return color


def fill_list_from_object(obj):
    fill = obj.get("fill")

    if isinstance(fill, list):
        return fill

    return [{
        "color": fill,
        "bounds": bounds_dict_from_poly(obj["polygon"]),
    }]


def get_fill_for_polygon(source_fill, target_polygon):
    result = []

    if isinstance(source_fill, str) or source_fill is None:
        return [{
            "color": source_fill,
            "bounds": bounds_dict_from_poly(target_polygon),
        }]

    for fill_part in source_fill:
        fill_poly = bounds_poly_from_dict(fill_part["bounds"])
        intersection = fill_poly.intersection(target_polygon)

        if not intersection.is_empty and intersection.area > 0:
            result.append({
                "color": fill_part.get("color"),
                "bounds": bounds_dict_from_poly(intersection),
            })

    return result


def is_full_hole_object(obj):
    fill = normalize_color(obj.get("fill"))
    return fill in FULL_HOLE_COLORS


def is_half_hole_object(obj):
    fill = normalize_color(obj.get("fill"))
    return fill in BROWN_COLORS


def make_wall(wall_id, parent_id, wall_type, polygon, source_id=None, fill=None):
    return {
        "id": wall_id,
        "parent_id": parent_id,
        "source_id": source_id,
        "type": wall_type,
        "polygon": polygon,
        "fill": get_fill_for_polygon(fill, polygon),
        "bounds": bounds_dict_from_poly(polygon),
        "angle": 1
    }


def find_touching_wall_types(polygon, walls, tolerance=0.01):
    touching = []

    test_polygon = polygon.buffer(tolerance)

    for wall in walls:
        if wall["type"] == "base":
            continue

        if test_polygon.intersects(wall["polygon"]):
            touching.append(wall["type"])

    return touching


def generate_outer_walls(group, wall_thickness=4):
    outer = group["outer"]

    if outer["type"] != "rect":
        return []

    parent_id = outer["id"]
    wall_fill = outer.get("fill")

    minx, miny, maxx, maxy = outer["polygon"].bounds
    t = wall_thickness

    return [
        make_wall(
            f"{parent_id}_base",
            parent_id,
            "base",
            outer["polygon"],
            parent_id,
            "#ffffff",
        ),
        make_wall(
            f"{parent_id}_outer_top",
            parent_id,
            "outer_top",
            box(minx, miny, maxx - t, miny + t),
            parent_id,
            wall_fill,
        ),
        make_wall(
            f"{parent_id}_outer_right",
            parent_id,
            "outer_right",
            box(maxx - t, miny, maxx, maxy - t),
            parent_id,
            wall_fill,
        ),
        make_wall(
            f"{parent_id}_outer_bottom",
            parent_id,
            "outer_bottom",
            box(minx + t, maxy - t, maxx, maxy),
            parent_id,
            wall_fill,
        ),
        make_wall(
            f"{parent_id}_outer_left",
            parent_id,
            "outer_left",
            box(minx, miny + t, minx + t, maxy),
            parent_id,
            wall_fill,
        ),
    ]


def generate_inner_walls(group, wall_thickness=4, existing_walls=None):
    parent_id = group["outer"]["id"]
    walls = []

    if existing_walls is None:
        existing_walls = []

    for obj in group["inside"]:
        if obj["type"] != "rect":
            continue

        obj_id = obj["id"]
        minx, miny, maxx, maxy = obj["polygon"].bounds

        if is_full_hole_object(obj):
            touching_wall_types = find_touching_wall_types(
                obj["polygon"],
                existing_walls,
                tolerance=0.01,
            )

            if touching_wall_types:
                touching_name = "_".join(touching_wall_types)
                hole_id = f"{parent_id}_{obj_id}_full_hole_on_{touching_name}"
            else:
                hole_id = f"{parent_id}_{obj_id}_full_hole"

            walls.append(
                make_wall(
                    hole_id,
                    parent_id,
                    "full_hole",
                    obj["polygon"],
                    obj_id,
                    obj.get("fill"),
                )
            )
            continue

        if is_half_hole_object(obj):
            touching_wall_types = find_touching_wall_types(
                obj["polygon"],
                existing_walls,
                tolerance=0.01,
            )

            if touching_wall_types:
                touching_name = "_".join(touching_wall_types)
                hole_id = f"{parent_id}_{obj_id}_half_hole_on_{touching_name}"
            else:
                hole_id = f"{parent_id}_{obj_id}_half_hole"

            walls.append(
                make_wall(
                    hole_id,
                    parent_id,
                    "half_hole",
                    obj["polygon"],
                    obj_id,
                    obj.get("fill"),
                )
            )
            continue

        wall_fill = obj.get("fill")

        if normalize_color(wall_fill) == "#ffffff" and "container_fill" in obj:
            wall_fill = obj["container_fill"]

        walls.extend([
            make_wall(
                f"{parent_id}_{obj_id}_inner_top",
                parent_id,
                "inner_top",
                box(minx, miny - wall_thickness, maxx, miny),
                obj_id,
                wall_fill,
            ),
            make_wall(
                f"{parent_id}_{obj_id}_inner_bottom",
                parent_id,
                "inner_bottom",
                box(minx, maxy, maxx, maxy + wall_thickness),
                obj_id,
                wall_fill,
            ),
            make_wall(
                f"{parent_id}_{obj_id}_inner_left",
                parent_id,
                "inner_left",
                box(minx - wall_thickness, miny, minx, maxy),
                obj_id,
                wall_fill,
            ),
            make_wall(
                f"{parent_id}_{obj_id}_inner_right",
                parent_id,
                "inner_right",
                box(maxx, miny, maxx + wall_thickness, maxy),
                obj_id,
                wall_fill,
            ),
        ])

    return walls


def generate_walls_for_group(group, wall_thickness=4):
    outer_walls = generate_outer_walls(group, wall_thickness)

    inner_walls = generate_inner_walls(
        group,
        wall_thickness=wall_thickness,
        existing_walls=outer_walls,
    )

    walls = outer_walls + inner_walls

    return cleanup_walls(
        walls,
        tolerance=0.25,
    )


def generate_walls_for_layers(grouped_layers, wall_thickness=4):
    wall_layers = {}

    for layer_name, groups in grouped_layers.items():
        wall_layers[layer_name] = []

        for group in groups:
            if "path" not in group["outer"]["id"]:
                wall_layers[layer_name].extend(
                    generate_walls_for_group(group, wall_thickness)
                )

    return wall_layers


def plot_polygon(
    poly,
    fill_color="none",
    edge_color="black",
    linewidth=1,
    alpha=0.4,
):
    fill_color = clean_color(fill_color)

    if poly.geom_type == "Polygon":
        x, y = poly.exterior.xy

        plt.fill(
            x,
            y,
            facecolor=fill_color,
            edgecolor=edge_color,
            linewidth=linewidth,
            alpha=alpha,
        )

    elif poly.geom_type == "MultiPolygon":
        for part in poly.geoms:
            x, y = part.exterior.xy

            plt.fill(
                x,
                y,
                facecolor=fill_color,
                edgecolor=edge_color,
                linewidth=linewidth,
                alpha=alpha,
            )


def plot_wall_with_fill_parts(
    wall,
    edge_color="black",
    linewidth=1,
    alpha=0.4,
):
    fill = wall.get("fill")

    if isinstance(fill, list):
        if not fill:
            plot_polygon(
                wall["polygon"],
                fill_color="#cccccc",
                edge_color=edge_color,
                linewidth=linewidth,
                alpha=alpha,
            )
            return

        for fill_part in fill:
            fill_poly = bounds_poly_from_dict(fill_part["bounds"])
            clipped = fill_poly.intersection(wall["polygon"])

            if clipped.is_empty:
                continue

            plot_polygon(
                clipped,
                fill_color=fill_part.get("color"),
                edge_color=edge_color,
                linewidth=linewidth,
                alpha=alpha,
            )

        return

    plot_polygon(
        wall["polygon"],
        fill_color=fill,
        edge_color=edge_color,
        linewidth=linewidth,
        alpha=alpha,
    )


def render_walls_2d(wall_layers, out_dir):
    out_dir = Path(out_dir)
    out_dir.mkdir(exist_ok=True)

    for layer_name, walls in wall_layers.items():
        layer_out_dir = out_dir / safe_filename(layer_name)
        layer_out_dir.mkdir(exist_ok=True)

        walls_by_parent = {}

        for wall in walls:
            walls_by_parent.setdefault(wall["parent_id"], []).append(wall)

        for parent_id, parent_walls in walls_by_parent.items():
            plt.figure(figsize=(10, 8))

            for wall in parent_walls:
                if wall["type"] == "base":
                    plot_wall_with_fill_parts(
                        wall,
                        edge_color="black",
                        linewidth=1,
                    )

                if wall["type"].startswith("inner_"):
                    plot_wall_with_fill_parts(
                        wall,
                        edge_color="black",
                        linewidth=1,
                    )

            for wall in parent_walls:
                if wall["type"].startswith("outer_"):
                    plot_wall_with_fill_parts(
                        wall,
                        edge_color="black",
                        linewidth=2,
                    )

                if wall["type"] == "full_hole":
                    plot_polygon(
                        wall["polygon"],
                        fill_color=clean_color(wall.get("fill"), "#000000"),
                        edge_color="red",
                        linewidth=2,
                        alpha=0.4,
                    )

                if wall["type"] == "half_hole":
                    plot_wall_with_fill_parts(
                        wall,
                        edge_color="orange",
                        linewidth=2,
                        alpha=0.4,
                    )

            for wall in parent_walls:
                cx = wall["polygon"].centroid.x
                cy = wall["polygon"].centroid.y

                plt.text(
                    cx,
                    cy,
                    f"{wall['id']}\n({cx:.1f}, {cy:.1f})",
                    fontsize=5,
                    ha="center",
                    va="center",
                )

            plt.title(f"{layer_name} / {parent_id}\nall generated wall objects")
            plt.axis("equal")
            plt.gca().invert_yaxis()

            out_png = layer_out_dir / f"{safe_filename(parent_id)}_all_generated_walls.png"

            plt.savefig(out_png, dpi=200, bbox_inches="tight")
            plt.close()

            print("Saved:", out_png)


def print_wall_coordinates(wall_layers):
    for layer_name, walls in wall_layers.items():
        for wall in walls:
            b = wall["bounds"]
            print(
                f"{wall['id']} | type={wall['type']} | "
                f"parent={wall['parent_id']} | source={wall['source_id']} | "
                f"fill={wall.get('fill')} | "
                f"x1={b['x1']:.3f}, y1={b['y1']:.3f}, "
                f"x2={b['x2']:.3f}, y2={b['y2']:.3f}, "
                f"length={b['length']:.3f}, width={b['width']:.3f}"
            )

def bounds_close(b1, b2, tol=0.1):
    return (
        math.isclose(b1["x1"], b2["x1"], abs_tol=tol) and
        math.isclose(b1["x2"], b2["x2"], abs_tol=tol) and
        math.isclose(b1["y1"], b2["y1"], abs_tol=tol) and
        math.isclose(b1["y2"], b2["y2"], abs_tol=tol)
    )

def cleanup_walls(walls, tolerance=0.25):
    for wall in walls:
        if wall["bounds"]["length"] > wall["bounds"]["width"]:
            wall["orientation"] = "horizontal"
        else:
            wall["orientation"] = "vertical"

    base_walls = [
        wall for wall in walls
        if wall["type"] == "base"
    ]

    outer_walls = [
        wall for wall in walls
        if wall["type"].startswith("outer_")
    ]

    inner_walls = [
        wall for wall in walls
        if wall["type"].startswith("inner_")
    ]

    full_holes = [
        wall for wall in walls
        if wall["type"] == "full_hole"
    ]

    half_holes = [
        wall for wall in walls
        if wall["type"] == "half_hole"
    ]

    kept_inner_walls = []

    walls_for_removal_test = inner_walls + outer_walls
    for inner in inner_walls:
        inner_poly = inner["polygon"]
        remove_inner = False

        for removal_wall in walls_for_removal_test:
            if inner != removal_wall and not bounds_close(inner["bounds"], removal_wall["bounds"]):
                outer_poly = removal_wall["polygon"].buffer(tolerance)

                if outer_poly.contains(inner_poly) or outer_poly.covers(inner_poly):
                    remove_inner = True
                    break

        if remove_inner:
            continue

        for kept in kept_inner_walls:
            kept_poly = kept["polygon"].buffer(tolerance)

            if kept_poly.contains(inner_poly) or kept_poly.covers(inner_poly):
                remove_inner = True
                break

        if not remove_inner:
            kept_inner_walls.append(inner)

    removed_walls = []
    merged_walls = []
    for wall1 in kept_inner_walls:
        for wall2 in kept_inner_walls:
            if wall1 != wall2:
                if wall1["orientation"] == wall2["orientation"]:
                    if (wall1["orientation"] == "horizontal" and wall2["bounds"]["y1"] + 0.1 > wall1["bounds"][
                        "y1"] > wall2["bounds"]["y1"] - 0.1
                            and wall2["bounds"]["y2"] + 0.1 > wall1["bounds"]["y2"] > wall2["bounds"][
                                "y2"] - 0.1):
                        intersection_area = wall1["polygon"].intersection(wall2["polygon"]).area
                        coverage_ratio = intersection_area / wall1["polygon"].area
                        if coverage_ratio > 0.1:
                            if wall1["bounds"]["x1"] < wall2["bounds"]["x1"]:
                                ordered = [wall1, wall2]
                            else:
                                ordered = [wall2, wall1]
                            removed_walls.extend(ordered)
                            new_wall = ordered[0]
                            new_wall["bounds"]["x2"] = ordered[1]["bounds"]["x2"]
                            new_wall["fill"][0]["bounds"]["x2"] = ordered[1]["bounds"]["x2"]
                            new_wall["bounds"]["length"] = new_wall["bounds"]["x2"]-new_wall["bounds"]["x1"]
                            new_wall["fill"][0]["bounds"]["length"] = new_wall["bounds"]["x2"] - new_wall["bounds"]["x1"]
                            new_wall["polygon"] = bounds_poly_from_dict(new_wall["bounds"])
                            if new_wall not in merged_walls:
                                merged_walls.append(new_wall)
                    elif (wall1["orientation"] == "vertical" and wall2["bounds"]["x1"] + 0.1 > wall1["bounds"][
                        "x1"] > wall2["bounds"]["x1"] - 0.1
                          and wall2["bounds"]["x2"] + 0.1 > wall1["bounds"]["x2"] > wall2["bounds"][
                              "x2"] - 0.1):
                        intersection_area = wall1["polygon"].intersection(wall2["polygon"]).area
                        coverage_ratio = intersection_area / wall1["polygon"].area
                        if coverage_ratio > 0.1:
                            removed_walls.extend((wall1, wall2))
                            if wall1["bounds"]["y1"] < wall2["bounds"]["y1"]:
                                ordered = [wall1, wall2]
                            else:
                                ordered = [wall2, wall1]
                            removed_walls.extend(ordered)
                            new_wall = ordered[0]
                            new_wall["bounds"]["y2"] = ordered[1]["bounds"]["y2"]
                            new_wall["fill"][0]["bounds"]["y2"] = ordered[1]["bounds"]["y2"]
                            new_wall["bounds"]["width"] = new_wall["bounds"]["y2"] - new_wall["bounds"]["y1"]
                            new_wall["fill"][0]["bounds"]["width"] = new_wall["bounds"]["y2"] - new_wall["bounds"]["y1"]
                            new_wall["polygon"] = bounds_poly_from_dict(new_wall["bounds"])
                            if new_wall not in merged_walls:
                                merged_walls.append(new_wall)

    new_kept_inner_walls = []
    for kept_inner_wall in kept_inner_walls:
        if kept_inner_wall not in removed_walls:
            new_kept_inner_walls.append(kept_inner_wall)


    kept_inner_walls = new_kept_inner_walls + merged_walls

    return base_walls + outer_walls + kept_inner_walls + full_holes + half_holes


def generate_and_render_walls(
    grouped_layers,
    out_dir,
    print_coordinates=True,
    render=True,
    wall_thickness=4,
):
    wall_layers = generate_walls_for_layers(
        grouped_layers,
        wall_thickness=wall_thickness,
    )

    if print_coordinates:
        print_wall_coordinates(wall_layers)

    if render:
        render_walls_2d(
            wall_layers,
            out_dir,
        )

    return wall_layers