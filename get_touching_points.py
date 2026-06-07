from pathlib import Path

import matplotlib.pyplot as plt
from shapely.geometry import box


def split_walls_by_parent_id(walls):
    walls_by_parent = {}

    for wall in walls:
        parent_id = wall["parent_id"]

        if parent_id not in walls_by_parent:
            walls_by_parent[parent_id] = []

        walls_by_parent[parent_id].append(wall)

    return walls_by_parent


def bounds_dict_from_poly(poly):
    minx, miny, maxx, maxy = poly.bounds

    return {
        "x1": minx,
        "y1": miny,
        "x2": maxx,
        "y2": maxy,
        "width": maxx - minx,
        "height": maxy - miny,
    }


def bounds_poly_from_dict(bounds):
    return box(
        bounds["x1"],
        bounds["y1"],
        bounds["x2"],
        bounds["y2"],
    )


def clean_color(color, fallback="#cccccc"):
    if color is None:
        return fallback

    if isinstance(color, dict):
        color = color.get("color")

    if isinstance(color, list):
        if not color:
            return fallback
        color = color[0].get("color")

    if color is None:
        return fallback

    color = str(color).strip()

    if color.lower() in {"none", "transparent"}:
        return fallback

    return color


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


def update_wall_from_bounds(wall):
    b = wall["bounds"]

    wall["polygon"] = box(
        b["x1"],
        b["y1"],
        b["x2"],
        b["y2"],
    )

    b["width"] = b["x2"] - b["x1"]
    b["height"] = b["y2"] - b["y1"]

    wall["fill"] = get_fill_for_polygon(
        wall.get("fill"),
        wall["polygon"],
    )


def update_bounds_from_polygon(wall):
    wall["bounds"] = bounds_dict_from_poly(wall["polygon"])

    wall["fill"] = get_fill_for_polygon(
        wall.get("fill"),
        wall["polygon"],
    )


def clone_wall_with_polygon(wall, polygon, index):
    new_wall = {
        **wall,
        "id": f"{wall['id']}_part_{index}",
        "polygon": polygon,
    }

    update_bounds_from_polygon(new_wall)

    return new_wall


def split_geometry_into_polygons(geometry):
    if geometry.is_empty:
        return []

    if geometry.geom_type == "Polygon":
        return [geometry]

    if geometry.geom_type == "MultiPolygon":
        return list(geometry.geoms)

    if geometry.geom_type == "GeometryCollection":
        return [
            part
            for part in geometry.geoms
            if part.geom_type == "Polygon" and not part.is_empty
        ]

    return []


def split_walls_around_full_holes(parent_walls, tolerance=0.01):
    full_holes = [
        wall
        for wall in parent_walls
        if wall["type"] == "full_hole"
    ]

    if not full_holes:
        return [
            wall for wall in parent_walls
            if wall["type"] != "full_hole"
        ]

    result = []

    for wall in parent_walls:
        if wall["type"] == "full_hole":
            continue

        if wall["type"] == "base":
            result.append(wall)
            continue

        polygon = wall["polygon"]

        touching_holes = [
            hole
            for hole in full_holes
            if polygon.buffer(tolerance).intersects(hole["polygon"])
        ]

        if not touching_holes:
            result.append(wall)
            continue

        for hole in touching_holes:
            polygon = polygon.difference(
                hole["polygon"].buffer(tolerance)
            )

        pieces = split_geometry_into_polygons(polygon)

        for index, piece in enumerate(pieces, start=1):
            if piece.area <= 0:
                continue

            result.append(
                clone_wall_with_polygon(
                    wall,
                    piece,
                    index,
                )
            )

    return result


def plot_polygon(
    poly,
    fill_color="#cccccc",
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


def modify_and_plot_walls_by_parent_id(
    walls,
    wall_width,
    out_dir,
):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    walls_by_parent = split_walls_by_parent_id(walls)
    final_walls_by_parent = {}

    for parent_id, parent_walls in walls_by_parent.items():
        top_wall = -1000
        bottom_wall = 1000
        left_wall = -1000
        right_wall = 1000

        for wall in parent_walls:
            if "base" in wall["id"]:
                left_wall = wall["bounds"]["x1"]
                right_wall = wall["bounds"]["x2"]
                top_wall = wall["bounds"]["y1"]
                bottom_wall = wall["bounds"]["y2"]

        for wall in parent_walls:
            if wall["type"] == "full_hole":
                continue

            b = wall["bounds"]

            if "outer" in wall["id"]:

                if "top" in wall["id"]:
                    b["x2"] = b["x2"] + 4 - wall_width
                    b["y2"] = b["y1"] + wall_width

                elif "right" in wall["id"]:
                    b["x1"] = b["x2"] - wall_width
                    b["y2"] = b["y2"] + 4 - wall_width

                elif "bottom" in wall["id"]:
                    b["y1"] = b["y2"] - wall_width
                    b["x1"] = b["x1"] - 4 + wall_width

                elif "left" in wall["id"]:
                    b["y1"] = b["y1"] - 4 + wall_width
                    b["x2"] = b["x1"] + wall_width

                update_wall_from_bounds(wall)

            elif "inner" in wall["id"]:

                if b["height"] > b["width"]:
                    if b["y1"] < top_wall + 5:
                        b["y1"] = b["y1"] + (-4 + wall_width)
                    else:
                        b["y1"] = b["y1"] + (-4 + wall_width) / 2

                    if b["y2"] > bottom_wall - 5:
                        b["y2"] = b["y2"] + (4 - wall_width)
                    else:
                        b["y2"] = b["y2"] + (4 - wall_width) / 2

                    b["x1"] = b["x1"] + 2 - wall_width / 2
                    b["x2"] = b["x2"] - 2 + wall_width / 2

                else:
                    if b["x1"] < left_wall + 5:
                        b["x1"] = b["x1"] + (-4 + wall_width)
                    else:
                        b["x1"] = b["x1"] + (-4 + wall_width) / 2

                    if b["x2"] > right_wall - 5:
                        b["x2"] = b["x2"] + (4 - wall_width)
                    else:
                        b["x2"] = b["x2"] + (4 - wall_width) / 2

                    b["y1"] = b["y1"] + 2 - wall_width / 2
                    b["y2"] = b["y2"] - 2 + wall_width / 2

                update_wall_from_bounds(wall)

        final_parent_walls = split_walls_around_full_holes(
            parent_walls,
            tolerance=0.01,
        )

        final_walls_by_parent[parent_id] = final_parent_walls

        plt.figure(figsize=(10, 8))

        for wall in final_parent_walls:
            if wall["type"] == "base":
                plot_polygon(
                    wall["polygon"],
                    fill_color="#dddddd",
                    edge_color="black",
                    linewidth=1,
                    alpha=0.25,
                )

        for wall in final_parent_walls:
            if wall["type"] != "base":
                plot_wall_with_fill_parts(
                    wall,
                    edge_color="black",
                    linewidth=2,
                    alpha=0.5,
                )

        for wall in final_parent_walls:
            centroid = wall["polygon"].centroid

            plt.text(
                centroid.x,
                centroid.y,
                wall["id"],
                fontsize=6,
                ha="center",
                va="center",
            )

        plt.title(f"{parent_id}\nwall_width={wall_width}")
        plt.axis("equal")
        plt.gca().invert_yaxis()

        out_file = out_dir / f"{parent_id}_wall_width_{wall_width}.png"

        plt.savefig(
            out_file,
            dpi=300,
            bbox_inches="tight",
        )

        plt.close()

    return final_walls_by_parent


def modify_and_plot_wall_layers(
    wall_layers,
    wall_width,
    out_dir,
):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    returned_by_layer = {}

    for layer_name, layer_walls in wall_layers.items():
        safe_layer_name = layer_name.replace(" ", "_")

        print(f"Processing layer: {layer_name}")

        returned_by_layer[layer_name] = modify_and_plot_walls_by_parent_id(
            layer_walls,
            wall_width=wall_width,
            out_dir=out_dir / safe_layer_name,
        )

    return returned_by_layer