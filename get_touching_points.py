from pathlib import Path

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
from shapely.geometry import box, Polygon
from shapely.ops import unary_union
import copy
import numpy as np


from matplotlib.patches import Rectangle

def plot_bounds_rect(bounds, fill_color, edge_color="black", linewidth=1, alpha=0.5):
    x = bounds["x1"]
    y = bounds["y1"]
    length = bounds["x2"] - bounds["x1"]
    width = bounds["y2"] - bounds["y1"]

    rect = Rectangle(
        (x, y),
        length,
        width,
        facecolor=fill_color,
        edgecolor=edge_color,
        linewidth=linewidth,
        alpha=alpha,
    )

    plt.gca().add_patch(rect)

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
        "length": maxx - minx,
        "width": maxy - miny,
    }

def polygon_from_bounds(bounds):
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
        fill_poly = polygon_from_bounds(fill_part["bounds"])
        intersection = fill_poly.intersection(target_polygon)

        if not intersection.is_empty and intersection.area > 0:
            result.append({
                "color": fill_part.get("color"),
                "bounds": bounds_dict_from_poly(intersection),
            })

    return result

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

HOLE_COLORS = {"#552200", "#000000", "#803300"}

def order_walls_fills_by_color(wall, color):
    if len(wall["fill"]) != 1:
        skey = wall["edge_indices"]["wall_start_index"]
        ekey = wall["edge_indices"]["wall_end_index"]

        to_remove = set()
        to_add = []

        for i, hole_fill in enumerate(wall["fill"]):
            if hole_fill["color"] != color:
                continue

            hole_start = hole_fill["bounds"][skey]
            hole_end = hole_fill["bounds"][ekey]

            for j, fill in enumerate(wall["fill"]):
                if i == j:
                    continue

                fill_start = fill["bounds"][skey]
                fill_end = fill["bounds"][ekey]

                if fill_start < hole_start and fill_end > hole_end:
                    right_fill = copy.deepcopy(wall["fill"][j])

                    wall["fill"][j]["bounds"][ekey] = hole_start
                    right_fill["bounds"][skey] = hole_end

                    to_add.append(right_fill)

                elif fill_start < hole_start < fill_end:
                    fill["bounds"][ekey] = hole_start

                elif fill_start > hole_start and fill_end < hole_end:
                    to_remove.add(j)

                elif fill_start < hole_end < fill_end:
                    fill["bounds"][skey] = hole_end

                if abs(fill["bounds"][ekey]-fill["bounds"][skey]) < 0.001:
                    to_remove.add(j)

        wall["fill"] = [
            fill
            for i, fill in enumerate(wall["fill"])
            if i not in to_remove
        ]

        wall["fill"].extend(to_add)
        for fill in wall["fill"]:
            fill["bounds"]["length"] = fill["bounds"]["x2"]-fill["bounds"]["x1"]
            fill["bounds"]["width"] = fill["bounds"]["y2"]-fill["bounds"]["y1"]
        wall["fill"] = sorted(wall["fill"], key=lambda x: x["bounds"][skey])
    return wall

def add_holes_to_color(walls):
    for wall in walls:
        if wall["bounds"]["length"] > wall["bounds"]["width"]:
            wall_edge_index = {"wall_start_index": "x1", "wall_end_index": "x2"}
        else:
            wall_edge_index = {"wall_start_index": "y1", "wall_end_index": "y2"}

        if len(wall["fill"]) > 0:
            wall["fill"] = sorted(
                wall["fill"],
                key=lambda x: x["bounds"][wall_edge_index["wall_start_index"]]
            )
            wall["edge_indices"] = wall_edge_index

    for hole_wall in walls:
        if not any(fill["color"] in HOLE_COLORS for fill in hole_wall["fill"]):
            continue

        for i in range(len(walls)):
            if walls[i]["id"] == hole_wall["id"]:
                continue

            if walls[i]["fill"][0]["color"] != "#ffffff":
                percentage_of_coverage = (
                    hole_wall["polygon"].intersection(walls[i]["polygon"]).area
                    / hole_wall["polygon"].area
                )

                if percentage_of_coverage > 0.8:
                    walls[i]["fill"].append(hole_wall["fill"][0])

    for wall in walls:
        wall["fill"] = sorted(
            wall["fill"],
            key=lambda x: x["bounds"][wall["edge_indices"]["wall_start_index"]]
        )

        for color in ["#000000", "#552200", "#803300"]:
            previous_fill = None

            while previous_fill != wall["fill"]:
                previous_fill = copy.deepcopy(wall["fill"])
                wall = order_walls_fills_by_color(wall, color)

    new_walls = []
    for wall in walls:
        if not (
            len(wall["fill"]) == 1
            and wall["fill"][0]["color"] in HOLE_COLORS
        ):
            new_walls.append(wall)

    return new_walls

def wall_insert(wall, hole_wall):
    start = -1
    end = -1
    different_widths = len(wall["fill"])
    if len(wall["fill"]) > 0:
        wall["fill"] = sorted(wall["fill"], key=lambda x: x["bounds"][wall["edge_indices"]["wall_start_index"]])
    for j in range(different_widths):
        if j != different_widths:
            if wall["fill"][j]["bounds"][wall["edge_indices"]["wall_start_index"]] < hole_wall["fill"][0]["bounds"][wall["edge_indices"]["wall_start_index"]] < \
                    wall["fill"][j]["bounds"][wall["edge_indices"]["wall_end_index"]]:
                start = j
            if wall["fill"][j]["bounds"][wall["edge_indices"]["wall_start_index"]] < hole_wall["fill"][0]["bounds"][wall["edge_indices"]["wall_end_index"]] < \
                    wall["fill"][j]["bounds"][wall["edge_indices"]["wall_end_index"]]:
                end = j
        else:
            if start == -1:
                start = j
            if end == -1:
                end = j
    left_wall = copy.deepcopy(wall["fill"][start])
    right_wall = copy.deepcopy(wall["fill"][end])
    left_wall["bounds"][wall["edge_indices"]["wall_end_index"]] = hole_wall["fill"][0]["bounds"][wall["edge_indices"]["wall_start_index"]]
    right_wall["bounds"][wall["edge_indices"]["wall_start_index"]] = hole_wall["fill"][0]["bounds"][wall["edge_indices"]["wall_end_index"]]
    if start != end:
        wall["fill"][start] = left_wall
        wall["fill"][end] = right_wall
        wall["fill"] = wall["fill"][:(start - 1)] + hole_wall["fill"] + wall["fill"][end:]
    else:
        wall["fill"] = wall["fill"][:(start)] + [left_wall] + hole_wall["fill"] + [right_wall] + wall[
            "fill"][end + 1:]
    return wall

def split_wall_around_black_fills(wall, base_wall):
    if wall["type"] == "base":
        return [wall], base_wall

    fill = wall.get("fill", [])
    black_fills = [f for f in fill if f.get("color") == "#000000"]

    if not black_fills:
        return [wall], base_wall

    if "outer" in wall["id"] and "top" in wall["id"]:
        direction = "down"
        orientation = "horizontal"
    elif "outer" in wall["id"] and "bottom" in wall["id"]:
        direction = "up"
        orientation = "horizontal"
    elif "outer" in wall["id"] and "left" in wall["id"]:
        direction = "right"
        orientation = "vertical"
    else:
        direction = "left"
        orientation = "vertical"

    append_black_fill = []
    for bfill in black_fills:
        append_black_fill.append({"bounds": bfill["bounds"], "direction": direction, "orientation": orientation})

    if "black_holes" not in base_wall:
        base_wall["black_holes"] = append_black_fill
    else:
        base_wall["black_holes"] += append_black_fill

    b = wall["bounds"]

    if b["width"] > b["length"]:
        start_key = "y1"
        end_key = "y2"
    else:
        start_key = "x1"
        end_key = "x2"

    black_fills = sorted(
        black_fills,
        key=lambda f: f["bounds"][start_key],
    )

    pieces = []
    current_start = b[start_key]

    for index, black_fill in enumerate(black_fills, start=1):
        black_start = black_fill["bounds"][start_key]
        black_end = black_fill["bounds"][end_key]

        if black_start > current_start:
            new_wall = copy.deepcopy(wall)
            new_wall["id"] = f"{wall['id']}_split_{len(pieces) + 1}"

            new_wall["bounds"][start_key] = current_start
            new_wall["bounds"][end_key] = black_start
            new_wall["bounds"]["length"] = new_wall["bounds"]["x2"] - new_wall["bounds"]["x1"]
            new_wall["bounds"]["width"] = new_wall["bounds"]["y2"] - new_wall["bounds"]["y1"]
            new_wall["polygon"] = polygon_from_bounds(new_wall["bounds"])

            new_wall["fill"] = [
                f for f in fill
                if f.get("color") != "#000000"
                and f["bounds"][start_key] >= current_start
                and f["bounds"][end_key] <= black_start
            ]

            pieces.append(new_wall)

        current_start = black_end

    if current_start < b[end_key]:
        new_wall = copy.deepcopy(wall)
        new_wall["id"] = f"{wall['id']}_split_{len(pieces) + 1}"

        new_wall["bounds"][start_key] = current_start
        new_wall["bounds"][end_key] = b[end_key]
        new_wall["bounds"]["length"] = new_wall["bounds"]["x2"] - new_wall["bounds"]["x1"]
        new_wall["bounds"]["width"] = new_wall["bounds"]["y2"] - new_wall["bounds"]["y1"]
        new_wall["polygon"] = polygon_from_bounds(new_wall["bounds"])

        new_wall["fill"] = [
            f for f in fill
            if f.get("color") != "#000000"
            and f["bounds"][start_key] >= current_start
            and f["bounds"][end_key] <= b[end_key]
        ]

        pieces.append(new_wall)

    return pieces, base_wall

def sector(center, rx, ry, start_deg, end_deg, n=64):
    """Elliptical pie slice from start_deg to end_deg (CCW from +x, true angles)."""
    cx, cy = center
    if end_deg < start_deg:
        end_deg += 360
    phi = np.radians(np.linspace(start_deg, end_deg, n))
    # distance from center to the ellipse edge at angle phi
    r = rx * ry / np.sqrt((ry * np.cos(phi))**2 + (rx * np.sin(phi))**2)
    x = cx + r * np.cos(phi)
    y = cy + r * np.sin(phi)
    return Polygon([(cx, cy)] + list(zip(x, y)))

def split_walls_around_black_fills(walls, wall_width):

    tolerance = 1e-3
    split_walls = []
    base_index = 0
    for i, wall in enumerate(walls):
        if wall["type"] == "base":
            base_index = i

    for wall in walls:
        wall_result, walls[base_index] = split_wall_around_black_fills(wall, walls[base_index])
        split_walls.extend(wall_result)
    # adding quarter circular holes into base if holes are next to each other in the corners
    holes = []
    if "black_holes" in split_walls[base_index]:
        for i in range(len(split_walls[base_index]["black_holes"])):
            for j in range(len(split_walls[base_index]["black_holes"])):
                first_orientation = split_walls[base_index]["black_holes"][i]["orientation"]
                second_orientation = split_walls[base_index]["black_holes"][j]["orientation"]
                first_direction = split_walls[base_index]["black_holes"][i]["direction"]
                second_direction = split_walls[base_index]["black_holes"][j]["direction"]

                first_split = split_walls[base_index]["black_holes"][i]["bounds"]
                second_split = split_walls[base_index]["black_holes"][j]["bounds"]
                # useless if, but more descriptive
                if first_orientation == 'vertical' and second_orientation == 'horizontal':
                    radius = min(first_split["y2"]-first_split["y1"], second_split["x2"]-second_split["x1"])
                    if first_direction == "right" and second_direction == "down":
                        # left long, top short 1
                        if first_split["y1"]-tolerance < second_split["y1"]<first_split["y1"] + tolerance and first_split["x2"]-tolerance < second_split["x1"]<first_split["x2"]+tolerance:
                            hole1 = sector((second_split["x1"], second_split["y2"]), second_split["length"], first_split["width"]-wall_width, 0, 90)
                            hole2 = polygon_from_bounds(first_split)
                            hole3 = polygon_from_bounds(second_split)
                            hole = [unary_union([g.buffer(tolerance) for g in (hole1, hole2, hole3)]).buffer(-tolerance), "left, top"]
                            if hole[0].geom_type != "Polygon":
                                print("not_correct 1")
                            holes.append(hole)
                            split_walls[base_index]["black_holes"][i]["done"] = True
                            split_walls[base_index]["black_holes"][j]["done"] = True
                        # left short, top long 2
                        elif first_split["y1"]-tolerance < second_split["y2"]<first_split["y1"] + tolerance and first_split["x1"]-tolerance < second_split["x1"]<first_split["x1"]+tolerance:
                            hole1 = sector((first_split["x2"], first_split["y1"]), second_split["length"]-wall_width, first_split["width"], 0, 90)
                            hole2 = polygon_from_bounds(first_split)
                            hole3 = polygon_from_bounds(second_split)
                            hole = [unary_union([g.buffer(tolerance) for g in (hole1, hole2, hole3)]).buffer(-tolerance), "left, top"]
                            if hole[0].geom_type != "Polygon":
                                print("not_correct 2")
                            holes.append(hole)
                            split_walls[base_index]["black_holes"][i]["done"] = True
                            split_walls[base_index]["black_holes"][j]["done"] = True

                    if first_direction == "right" and second_direction == "up":
                        # left short, bottom long 3
                        if first_split["y2"] - tolerance < second_split["y1"] < first_split["y2"] + tolerance and first_split["x1"] - tolerance < second_split["x1"] < first_split["x1"] + tolerance:
                            hole1 = sector((first_split["x2"], first_split["y2"]), second_split["length"]-wall_width, first_split["width"], 270, 360)
                            hole2 = polygon_from_bounds(first_split)
                            hole3 = polygon_from_bounds(second_split)
                            hole = [unary_union([g.buffer(tolerance) for g in (hole1, hole2, hole3)]).buffer(-tolerance), "left, bottom"]
                            if hole[0].geom_type != "Polygon":
                                print("not_correct 3")
                            holes.append(hole)
                            split_walls[base_index]["black_holes"][i]["done"] = True
                            split_walls[base_index]["black_holes"][j]["done"] = True
                        # left long, bottom short 4
                        elif first_split["y2"] - tolerance < second_split["y2"] < first_split["y2"] + tolerance and first_split["x2"] - tolerance < second_split["x1"] < first_split["x2"] + tolerance:
                            hole1 = sector((second_split["x1"], second_split["y1"]), second_split["length"], first_split["width"]-wall_width, 270, 360)
                            hole2 = polygon_from_bounds(first_split)
                            hole3 = polygon_from_bounds(second_split)
                            hole = [unary_union([g.buffer(tolerance) for g in (hole1, hole2, hole3)]).buffer(-tolerance), "left, bottom"]
                            if hole[0].geom_type != "Polygon":
                                print("not_correct 4")
                            holes.append(hole)
                            split_walls[base_index]["black_holes"][i]["done"] = True
                            split_walls[base_index]["black_holes"][j]["done"] = True

                    if first_direction == "left" and second_direction == "down":
                        # right long, top short 5
                        if first_split["y1"] - tolerance < second_split["y1"] < first_split["y1"] + tolerance and first_split["x1"] - tolerance < second_split["x2"] < first_split["x1"] + tolerance:
                            hole1 = sector((second_split["x2"], second_split["y2"]), second_split["length"], first_split["width"]-wall_width, 90, 180)
                            hole2 = polygon_from_bounds(first_split)
                            hole3 = polygon_from_bounds(second_split)
                            hole = [unary_union([g.buffer(tolerance) for g in (hole1, hole2, hole3)]).buffer(-tolerance), "right, top"]
                            if hole[0].geom_type != "Polygon":
                                print("not_correct 5")
                            holes.append(hole)
                            split_walls[base_index]["black_holes"][i]["done"] = True
                            split_walls[base_index]["black_holes"][j]["done"] = True

                        # right short, top long 6
                        elif first_split["y1"] - tolerance < second_split["y2"] < first_split["y1"] + tolerance and first_split["x2"] - tolerance < second_split["x2"] < first_split["x2"] + tolerance:
                            hole1 =sector((first_split["x1"], first_split["y1"]), second_split["length"]-wall_width, first_split["width"], 90, 180)
                            hole2 = polygon_from_bounds(first_split)
                            hole3 = polygon_from_bounds(second_split)
                            hole = [unary_union([g.buffer(tolerance) for g in (hole1, hole2, hole3)]).buffer(-tolerance), "right, top"]
                            if hole[0].geom_type != "Polygon":
                                print("not_correct 6")
                            holes.append(hole)
                            split_walls[base_index]["black_holes"][i]["done"] = True
                            split_walls[base_index]["black_holes"][j]["done"] = True

                    if first_direction == "left" and second_direction == "up":
                        # right_short, bottom long 7
                        if first_split["y2"] - tolerance < second_split["y1"] < first_split["y2"] + tolerance and first_split["x2"] - tolerance < second_split["x2"] < first_split["x2"] + tolerance:
                            hole1 = sector((first_split["x1"], first_split["y2"]), second_split["length"]-wall_width, first_split["width"], 180, 270)
                            hole2 = polygon_from_bounds(first_split)
                            hole3 = polygon_from_bounds(second_split)
                            hole = [unary_union([g.buffer(tolerance) for g in (hole1, hole2, hole3)]).buffer(-tolerance), "right, bottom"]
                            if hole[0].geom_type != "Polygon":
                                print("not_correct 7")
                            holes.append(hole)
                            split_walls[base_index]["black_holes"][i]["done"] = True
                            split_walls[base_index]["black_holes"][j]["done"] = True
                        # right long, bottom short 8
                        elif first_split["y2"] - tolerance < second_split["y2"] < first_split["y2"] + tolerance and first_split["x1"] - tolerance < second_split["x2"] < first_split["x1"] + tolerance:
                            first_split = {"x1": first_split["x1"],"x2": first_split["x2"],"y1": first_split["y1"],"y2": first_split["y2"]}
                            second_split = {"x1": second_split["x1"],"x2": second_split["x2"],"y1": second_split["y1"],"y2": second_split["y2"]}
                            hole1 = sector((second_split["x2"], second_split["y1"]), second_split["length"], first_split["width"]-wall_width, 180,270)
                            hole2 = polygon_from_bounds(first_split)
                            hole3 = polygon_from_bounds(second_split)
                            hole = [unary_union([g.buffer(tolerance) for g in (hole1, hole2, hole3)]).buffer(-tolerance), "right, bottom"]
                            if hole[0].geom_type != "Polygon":
                                print("not_correct 8")
                            holes.append(hole)
                            split_walls[base_index]["black_holes"][i]["done"] = True
                            split_walls[base_index]["black_holes"][j]["done"] = True

        for i in range(len(split_walls[base_index]["black_holes"])):
            split_direction = split_walls[base_index]["black_holes"][i]["direction"]
            split = split_walls[base_index]["black_holes"][i]["bounds"]
            split["x1"] -= tolerance
            split["x2"] += tolerance
            split["y1"] -= tolerance
            split["y2"] += tolerance
            if "done" not in split_walls[base_index]["black_holes"][i]:
                if split_direction == "down" or split_direction == "up":
                    max_width = (walls[base_index]["bounds"]["y2"]- walls[base_index]["bounds"]["y1"]-wall_width)/4
                    if split_direction == "down":
                        split_extended_bounds = {"x1": split["x1"],"x2": split["x2"],"y1": split["y1"],"y2": split["y2"]}
                        hole1 = sector(((split_extended_bounds["x1"] + split_extended_bounds["x2"])/2, split_extended_bounds["y2"]), (split_extended_bounds["x2"] - split_extended_bounds["x1"])/2, min(max_width, 8), 0,180)
                        hole2 = polygon_from_bounds(split_extended_bounds)
                        hole = [unary_union([g.buffer(tolerance) for g in (hole1, hole2)]).buffer(-tolerance), "top"]
                        if hole[0].geom_type != "Polygon":
                            print("not_correct down")
                        holes.append(hole)
                    elif split_direction == "up":
                        split_extended_bounds = {"x1": split["x1"],"x2": split["x2"],"y1": split["y1"],"y2": split["y2"]}
                        hole1 = sector(((split_extended_bounds["x1"] + split_extended_bounds["x2"])/2, split_extended_bounds["y1"]), (split_extended_bounds["x2"] - split_extended_bounds["x1"])/2, min(max_width, 8), 180,360)
                        hole2 = polygon_from_bounds(split_extended_bounds)
                        hole = [unary_union([g.buffer(tolerance) for g in (hole1, hole2)]).buffer(-tolerance), "bottom"]
                        if hole[0].geom_type != "Polygon":
                            print("not_correct up")
                        holes.append(hole)
                if split_direction == "right" or split_direction == "left":
                    max_width = (walls[base_index]["bounds"]["y2"] - walls[base_index]["bounds"]["y1"] - wall_width) / 4
                    if split_direction == "right":
                        split_extended_bounds = {"x1": split["x1"], "x2": split["x2"],"y1": split["y1"],"y2": split["y2"]}
                        hole1 = sector((split_extended_bounds["x2"] ,(split_extended_bounds["y1"] + split_extended_bounds["y2"]) / 2), min(max_width, 8), (split_extended_bounds["y2"] - split_extended_bounds["y1"])/2, -90, 90)
                        hole2 = polygon_from_bounds(split_extended_bounds)
                        hole = [unary_union([g.buffer(tolerance) for g in (hole1, hole2)]).buffer(-tolerance), "left"]
                        if hole[0].geom_type != "Polygon":
                            print("not_correct right")
                        holes.append(hole)
                    elif split_direction == "left":
                        split_extended_bounds = {"x1": split["x1"], "x2": split["x2"],"y1": split["y1"],"y2": split["y2"]}
                        hole1 = sector((split_extended_bounds["x1"] ,(split_extended_bounds["y1"] + split_extended_bounds["y2"]) / 2), min(max_width, 8), (split_extended_bounds["y2"] - split_extended_bounds["y1"])/2, 90, 270)
                        hole2 = polygon_from_bounds(split_extended_bounds)
                        hole = [unary_union([g.buffer(tolerance) for g in (hole1, hole2)]).buffer(-tolerance), "right"]
                        if hole[0].geom_type != "Polygon":
                            print("not_correct left")
                        holes.append(hole)

        walls[base_index]["black_holes"] = holes

    return split_walls

def modify_and_plot_walls_by_parent_id(
    walls,
    wall_width,
    out_dir,
):
    new_walls = add_holes_to_color(walls)

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    walls_by_parent = split_walls_by_parent_id(new_walls)
    final_walls_by_parent = {}

    for parent_id, parent_walls in walls_by_parent.items():
        top_wall = -1000
        bottom_wall = 1000
        left_wall = -1000
        right_wall = 1000

        for wall in parent_walls:
            if wall["bounds"]["width"] > 5 and wall["bounds"]["length"] > 5:
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

            elif "inner" in wall["id"]:

                if b["width"] > b["length"]:
                    if b["y1"] < top_wall + 5:
                        b["y1"] = b["y1"] -4+wall_width
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

            b["length"] = b["x2"] - b["x1"]
            b["width"] = b["y2"] - b["y1"]
            wall["polygon"] = polygon_from_bounds(wall["bounds"])

            if wall["fill"]:
                old_minx = min(fill["bounds"]["x1"] for fill in wall["fill"])
                old_miny = min(fill["bounds"]["y1"] for fill in wall["fill"])
                old_maxx = max(fill["bounds"]["x2"] for fill in wall["fill"])
                old_maxy = max(fill["bounds"]["y2"] for fill in wall["fill"])

                old_w = old_maxx - old_minx
                old_h = old_maxy - old_miny

                for fill in wall["fill"]:
                    fb = fill["bounds"]

                    # avoid divide-by-zero on very thin/degenerate fills
                    if old_w:
                        new_x1 = b["x1"] + (fb["x1"] - old_minx) / old_w * b["length"]
                        new_x2 = b["x1"] + (fb["x2"] - old_minx) / old_w * b["length"]
                    else:
                        new_x1 = b["x1"]
                        new_x2 = b["x2"]

                    if old_h:
                        new_y1 = b["y1"] + (fb["y1"] - old_miny) / old_h * b["width"]
                        new_y2 = b["y1"] + (fb["y2"] - old_miny) / old_h * b["width"]
                    else:
                        new_y1 = b["y1"]
                        new_y2 = b["y2"]

                    fb["x1"] = new_x1
                    fb["x2"] = new_x2
                    fb["y1"] = new_y1
                    fb["y2"] = new_y2
                    fb["length"] = fb["x2"] - fb["x1"]
                    fb["width"] = fb["y2"] - fb["y1"]
                    fb["polygon"] = polygon_from_bounds(fb)

        final_parent_walls = split_walls_around_black_fills(
            parent_walls,
            wall_width
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
                plot_polygon(
                    wall["polygon"],
                    fill_color=wall["fill"][0].get("color", "#00ff00") if wall.get("fill") else "#00ff00",
                    edge_color="black",
                    linewidth=2,
                    alpha=0.5,
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