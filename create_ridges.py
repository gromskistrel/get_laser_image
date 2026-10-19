import matplotlib.pyplot as plt
from pathlib import Path
from matplotlib.patches import Rectangle
from shapely.geometry import box
from itertools import combinations

from shapely.geometry import Polygon

def remove_collinear_points(poly, tolerance=1e-9):
    coords = list(poly.exterior.coords)

    # remove duplicate closing point
    if coords[0] == coords[-1]:
        coords = coords[:-1]

    # remove consecutive duplicate points
    deduped = []
    for pt in coords:
        if not deduped or pt != deduped[-1]:
            deduped.append(pt)

    coords = deduped

    if len(coords) < 3:
        return poly

    cleaned = []

    for i in range(len(coords)):
        prev_pt = coords[i - 1]
        curr_pt = coords[i]
        next_pt = coords[(i + 1) % len(coords)]

        v1 = (curr_pt[0] - prev_pt[0], curr_pt[1] - prev_pt[1])
        v2 = (next_pt[0] - curr_pt[0], next_pt[1] - curr_pt[1])

        cross = v1[0] * v2[1] - v1[1] * v2[0]

        if abs(cross) > tolerance:
            cleaned.append(curr_pt)

    # fallback: don't destroy the polygon
    if len(cleaned) < 3:
        return poly

    cleaned.append(cleaned[0])

    return Polygon(cleaned)

from shapely.geometry import box

def polygon_to_rectangles(poly, min_area=1e-9):
    xs = sorted(set(x for x, y in poly.exterior.coords))
    ys = sorted(set(y for x, y in poly.exterior.coords))

    rects = []

    # step 1: grid cells (same as before)
    for x1, x2 in zip(xs, xs[1:]):
        for y1, y2 in zip(ys, ys[1:]):
            cell = box(x1, y1, x2, y2)

            if poly.contains(cell.centroid):
                inter = poly.intersection(cell)

                if not inter.is_empty and inter.area > min_area:
                    rects.append({
                        "shape": "rect",
                        "x1": x1,
                        "x2": x2,
                        "y1": y1,
                        "y2": y2,
                    })

    # step 2: merge pairs that form a bigger rectangle
    area = lambda r: (r["x2"] - r["x1"]) * (r["y2"] - r["y1"])

    merged = True
    while merged:
        merged = False
        for a, b in combinations(rects, 2):
            big = {
                "shape": "rect",
                "x1": min(a["x1"], b["x1"]),
                "x2": max(a["x2"], b["x2"]),
                "y1": min(a["y1"], b["y1"]),
                "y2": max(a["y2"], b["y2"]),
            }
            if abs(area(big) - area(a) - area(b)) < 1e-9:
                rects.remove(a)
                rects.remove(b)
                rects.append(big)
                merged = True
                break

    return rects


def plot_bounds_rect(bounds, fill_color, edge_color="black", linewidth=1, alpha=0.4):
    fill_color = clean_color(fill_color)

    rect = Rectangle(
        (bounds["x1"], bounds["y1"]),
        bounds["x2"] - bounds["x1"],
        bounds["y2"] - bounds["y1"],
        facecolor=fill_color,
        edgecolor=edge_color,
        linewidth=linewidth,
        alpha=alpha,
    )

    plt.gca().add_patch(rect)


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
            fill_poly = polygon_from_any_bounds(fill_part["bounds"])

            plot_polygon(
                fill_poly,
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


def plot_ridges(walls):
    for wall in walls:
        for ridge in wall.get("ridges", []):
            start = ridge["location"]["start"]
            end = ridge["location"]["end"]

            plt.plot(
                [start[0], end[0]],
                [start[1], end[1]],
                color="red",
                linewidth=3,
                solid_capstyle="round",
            )

def polygon_from_any_bounds(bounds):
    if "polygon" in bounds:
        return bounds["polygon"]

    return bounds_poly_from_dict(bounds)

def plot_single_polygon_debug(key, polygon, out_dir):
    for poly in polygon:
        if "rect22" in poly["id"]:
            print("yay")
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    plt.figure(figsize=(10, 8))

    for rectangle in polygon:
        if rectangle["id"].endswith("_base"):
            plot_polygon(
                rectangle["polygon"],
                fill_color=rectangle["fill"][0].get("color") if rectangle.get("fill") else "#cccccc",
                edge_color="black",
                linewidth=1,
                alpha=0.4,
            )
        else:
            plot_wall_with_fill_parts(
                rectangle,
                edge_color="black",
                linewidth=1,
                alpha=0.4,
            )

        for ridge in rectangle.get("ridge_places", []):
            plot_bounds_rect(
                ridge,
                fill_color="#808080",
                edge_color="black",
                linewidth=1,
                alpha=0.6,
            )

        for ridge in rectangle.get("ridges", []):
            start = ridge["location"]["start"]
            end = ridge["location"]["end"]

            plt.plot(
                [start[0], end[0]],
                [start[1], end[1]],
                color="red",
                linewidth=3,
            )

        b = rectangle["bounds"]
        centroid_x = (b["x1"] + b["x2"]) / 2
        centroid_y = (b["y1"] + b["y2"]) / 2

        plt.text(
            centroid_x,
            centroid_y,
            rectangle["id"],
            fontsize=5,
            ha="center",
            va="center",
        )

    plt.title(key)
    plt.axis("equal")
    plt.gca().invert_yaxis()

    out_file = out_dir / f"{key}_ridges.png"

    plt.savefig(
        out_file,
        dpi=300,
        bbox_inches="tight",
    )

    plt.close()

def get_wall_color_at_point(wall, value, axis):
    tolerance = 1e-3
    color = None
    for fill in wall["fill"]:
        if axis == "x":
            if fill["bounds"]["x1"]-tolerance<value<fill["bounds"]["x2"]+tolerance:
                color = fill["color"]
        elif axis == "y":
            if fill["bounds"]["y1"]-tolerance<value<fill["bounds"]["y2"]+tolerance:
                color = fill["color"]
        else:
            raise ValueError("axis must be 'x' or 'y'")
    if color == None:
        print(wall["id"])
    return color

def split_fills_at(wall, value1, value2, axis, tolerance=1e-3):
    idx1 = None
    idx2 = None

    # gets in which fill part value1 and value2 are
    for i, fill in enumerate(wall["fill"]):
        bounds = fill["bounds"]

        if axis == "x":
            start = bounds["x1"]
            end = bounds["x2"]
        elif axis == "y":
            start = bounds["y1"]
            end = bounds["y2"]
        else:
            raise ValueError("axis must be 'x' or 'y'")

        if start - tolerance <= value1 <= end + tolerance:
            idx1 = i

        if start - tolerance <= value2 <= end + tolerance:
            idx2 = i
    # makes the part of the wall where ridges will be, have the same fill (so not split)
    if idx1 != idx2:
        if axis == "x":
            if wall["bounds"]["x1"] - tolerance < value1 < wall["bounds"]["x1"] + tolerance:
                wall["fill"][idx1]["bounds"]["x2"] = value2
                wall["fill"][idx1]["bounds"]["length"] = wall["fill"][idx1]["bounds"]["x2"]-wall["fill"][idx1]["bounds"]["x1"]
                wall["fill"][idx2]["bounds"]["x1"] = value2
                wall["fill"][idx2]["bounds"]["length"] = wall["fill"][idx2]["bounds"]["x2"] - wall["fill"][idx2]["bounds"]["x1"]
            else:
                wall["fill"][idx1]["bounds"]["x2"] = value1
                wall["fill"][idx1]["bounds"]["length"] = wall["fill"][idx1]["bounds"]["x2"] - wall["fill"][idx1]["bounds"]["x1"]
                wall["fill"][idx2]["bounds"]["x1"] = value1
                wall["fill"][idx2]["bounds"]["length"] = wall["fill"][idx2]["bounds"]["x2"] - wall["fill"][idx2]["bounds"]["x1"]
        elif axis == "y":
            if wall["bounds"]["y1"] - tolerance < value1 < wall["bounds"]["y1"] + tolerance:
                wall["fill"][idx1]["bounds"]["y1"] = value2
                wall["fill"][idx1]["bounds"]["width"] = wall["fill"][idx1]["bounds"]["y2"]-wall["fill"][idx1]["bounds"]["y1"]
                wall["fill"][idx2]["bounds"]["y1"] = value2
                wall["fill"][idx2]["bounds"]["width"] = wall["fill"][idx2]["bounds"]["y2"] - wall["fill"][idx2]["bounds"]["y1"]
            else:
                wall["fill"][idx1]["bounds"]["y2"] = value1
                wall["fill"][idx1]["bounds"]["width"] = wall["fill"][idx1]["bounds"]["y2"] - wall["fill"][idx1]["bounds"]["y1"]
                wall["fill"][idx2]["bounds"]["y1"] = value1
                wall["fill"][idx2]["bounds"]["width"] = wall["fill"][idx2]["bounds"]["y2"] - wall["fill"][idx2]["bounds"]["y1"]


    return True

def ridge_places(start, end):
    perfect = 7.5
    interval_number = 2
    prev = 1000
    # gets the best number of ridges based on their length
    while True:
        interval_length = (end-start)/interval_number
        if abs(perfect-interval_length) > abs(perfect-prev):
            interval_length = prev
            break
        else:
            if interval_number %2 == 0:
                interval_number = interval_number+1
            else:
                interval_number = interval_number+2
            prev = interval_length
    ridge_places = [start]
    # gets all ridge places
    for i in range(interval_number-2):
            ridge_places.append((i+1)*interval_length + start)

    print(f"ridge_start_difference = {ridge_places[0]-start}")
    print(f"ridge_end_difference = {end-ridge_places[-1]}")
    # splits ridge places into pairs of 2's
    ridge_places = [
        ridge_places[i:i + 2]
        for i in range(0, len(ridge_places), 2)
    ]
    return ridge_places

def bend_append(bend, direction, vertical_direction, bend_length):
    if bend_length > 0:
        bend.append([direction, vertical_direction, bend_length])
    return bend

def polygon_from_bounds(bounds):
    """Create a rectangular Shapely polygon from numeric bounds."""
    return Polygon([
        (bounds["x1"], bounds["y1"]),
        (bounds["x2"], bounds["y1"]),
        (bounds["x2"], bounds["y2"]),
        (bounds["x1"], bounds["y2"]),
    ])


def get_bounds_from_fill(fills):
    """Calculate the combined rectangular bounds of all fills."""
    if not fills:
        raise ValueError("Cannot calculate bounds from an empty fill list.")

    x1 = min(fill["bounds"]["x1"] for fill in fills)
    y1 = min(fill["bounds"]["y1"] for fill in fills)
    x2 = max(fill["bounds"]["x2"] for fill in fills)
    y2 = max(fill["bounds"]["y2"] for fill in fills)

    bounds = {
        "x1": x1,
        "x2": x2,
        "y1": y1,
        "y2": y2,
        "length": x2 - x1,
        "width": y2 - y1,
    }

    return bounds, polygon_from_bounds(bounds)


def rebuild_from_fills(item):
    """Rebuild every fill polygon and then rebuild the parent polygon."""
    fills = item.get("fill", [])

    if not fills:
        raise ValueError(
            f'Cannot rebuild {item.get("id", "unknown item")}: no fills remain.'
        )

    for fill in fills:
        bounds = fill["bounds"]

        bounds["length"] = bounds["x2"] - bounds["x1"]
        bounds["width"] = bounds["y2"] - bounds["y1"]
        bounds["polygon"] = polygon_from_bounds(bounds)

    item["bounds"], item["polygon"] = get_bounds_from_fill(fills)

def add_connection_info_to_walls(wall_layers, color_height_dict, out_dir=None, render=False, wall_width=3):
    tolerance = 1e-3
    returned = {}

    for layer_name, walls in wall_layers.items():

        returned[layer_name] = {}

        #file name for out
        layer_out_dir = None
        if render and out_dir is not None:
            layer_out_dir = Path(out_dir) / layer_name

        # Used for getting middle walls (when walls are from each side) so overlapping vertical and horizontal walls in the middle
        for key, polygons in walls.items():
            # gets direction of wall
            for rectangle in polygons:
                if rectangle["bounds"]["length"] == wall_width:
                    rectangle["direction"] = "vertical"
                else:
                    rectangle["direction"] = "horizontal"

                rectangle["ridges"] = []
                rectangle["ridge_places"] = []
                rectangle["no_ridge_places"] = []

            to_remove = set()
            to_add = []

            for i in range(len(polygons)):
                for j in range(i + 1, len(polygons)):

                    if i in to_remove or j in to_remove:
                        continue

                    if (
                            "inner" in polygons[i]["id"]
                            and "inner" in polygons[j]["id"]
                            and polygons[i]["direction"] == polygons[j]["direction"]
                    ):

                        if polygons[i]["direction"] == "horizontal":
                            if (
                                    polygons[j]["bounds"]["y1"] + tolerance > polygons[i]["bounds"]["y1"] >
                                    polygons[j]["bounds"]["y1"] - tolerance
                                    and polygons[j]["bounds"]["y2"] + tolerance > polygons[i]["bounds"]["y2"] >
                                    polygons[j]["bounds"]["y2"] - tolerance
                            ):
                                ordered = [polygons[i], polygons[j]] if polygons[i]["bounds"]["x1"] < \
                                                                        polygons[j]["bounds"]["x1"] else [polygons[j],
                                                                                                          polygons[i]]
                                if ordered[1]["bounds"]["x1"]-ordered[0]["bounds"]["x2"] < wall_width+tolerance:

                                    new_polygon = ordered[0].copy()
                                    new_polygon["bounds"] = ordered[0]["bounds"].copy()

                                    fill_middle = {
                                        "color": "#000001",
                                        "bounds": {
                                            "width": ordered[0]["bounds"]["y2"] - ordered[0]["bounds"]["y1"],
                                            "length": ordered[1]["bounds"]["x1"] - ordered[0]["bounds"]["x2"],
                                            "x1": ordered[0]["bounds"]["x2"],
                                            "x2": ordered[1]["bounds"]["x1"],
                                            "y1": ordered[0]["bounds"]["y1"],
                                            "y2": ordered[0]["bounds"]["y2"],
                                        },
                                    }

                                    fill_middle["bounds"]["polygon"] = bounds_poly_from_dict(fill_middle["bounds"])

                                    new_polygon["fill"] = ordered[0]["fill"] + [fill_middle] + ordered[1]["fill"]
                                    new_polygon["bounds"]["x2"] = ordered[1]["bounds"]["x2"]
                                    new_polygon["bounds"]["length"] = new_polygon["bounds"]["x2"] - new_polygon["bounds"][
                                        "x1"]
                                    new_polygon["bounds"]["polygon"] = bounds_poly_from_dict(new_polygon["bounds"])

                                    new_polygon["ridges"].append({
                                        "direction": "middle_high",
                                        "location": {
                                            "start": [fill_middle["bounds"]["x1"], fill_middle["bounds"]["y1"]],
                                            "end": [fill_middle["bounds"]["x2"], fill_middle["bounds"]["y2"]],
                                        },
                                    })

                                    to_remove.add(i)
                                    to_remove.add(j)
                                    to_add.append(new_polygon)

                        if polygons[i]["direction"] == "vertical":
                            if (
                                    polygons[j]["bounds"]["x1"] + 0.1 > polygons[i]["bounds"]["x1"] >
                                    polygons[j]["bounds"]["x1"] - 0.1
                                    and polygons[j]["bounds"]["x2"] + 0.1 > polygons[i]["bounds"]["x2"] >
                                    polygons[j]["bounds"]["x2"] - 0.1
                            ):


                                ordered = [polygons[i], polygons[j]] if polygons[i]["bounds"]["y1"] < \
                                                                        polygons[j]["bounds"]["y1"] else [polygons[j],
                                                                                                          polygons[i]]
                                if ordered[1]["bounds"]["y1"]-ordered[0]["bounds"]["y2"] < wall_width+0.1:

                                    new_polygon = ordered[0].copy()
                                    new_polygon["bounds"] = ordered[0]["bounds"].copy()

                                    fill_middle = {
                                        "color": "#000002",
                                        "bounds": {
                                            "width": ordered[1]["bounds"]["y1"] - ordered[0]["bounds"]["y2"],
                                            "length": ordered[0]["bounds"]["x2"] - ordered[0]["bounds"]["x1"],
                                            "y1": ordered[0]["bounds"]["y2"],
                                            "y2": ordered[1]["bounds"]["y1"],
                                            "x1": ordered[0]["bounds"]["x1"],
                                            "x2": ordered[0]["bounds"]["x2"],
                                        },
                                    }

                                    fill_middle["bounds"]["polygon"] = bounds_poly_from_dict(fill_middle["bounds"])

                                    new_polygon["fill"] = ordered[0]["fill"] + [fill_middle] + ordered[1]["fill"]
                                    new_polygon["bounds"]["y2"] = ordered[1]["bounds"]["y2"]
                                    new_polygon["bounds"]["width"] = new_polygon["bounds"]["y2"] - new_polygon["bounds"][
                                        "y1"]
                                    new_polygon["bounds"]["polygon"] = bounds_poly_from_dict(new_polygon["bounds"])

                                    new_polygon["ridges"].append({
                                        "direction": "middle_low",
                                        "location": {
                                            "start": [fill_middle["bounds"]["x1"], fill_middle["bounds"]["y1"]],
                                            "end": [fill_middle["bounds"]["x2"], fill_middle["bounds"]["y2"]],
                                        },
                                    })

                                    to_remove.add(i)
                                    to_remove.add(j)
                                    to_add.append(new_polygon)

            walls[key] = [
                             polygon
                             for index, polygon in enumerate(polygons)
                             if index not in to_remove
                         ] + to_add

        for key, polygons in walls.items():
            for rectangle in polygons:
                for other_rectangle in polygons:
                    if (
                        rectangle == other_rectangle
                        or rectangle["direction"] == other_rectangle["direction"]
                        or rectangle["id"].endswith("_base")
                        or other_rectangle["id"].endswith("_base")
                    ):
                        continue
                    b = rectangle["bounds"]
                    ob = other_rectangle["bounds"]

                    if rectangle["direction"] == "vertical":
                        # horizontal alignment
                        if (
                            b["x1"] > ob["x1"] - tolerance
                            and b["x2"] < ob["x2"] + tolerance
                        ):
                            # vertically on top
                            if (
                                b["y1"] > ob["y1"] - tolerance
                                and b["y1"] < ob["y2"] + tolerance
                            ):
                                # Synchronises the fill of the parts of the rectangles where ridges will be (so the edge is not split into 3mm of 1 height and 1mm of another height, so ridges go smoothly)
                                if "outer" in other_rectangle["id"] and len(other_rectangle["fill"]) > 1:
                                    split_fills_at(other_rectangle, b["x1"], b["x2"], "x")
                                # At the part of the ridge gets the minimum height.
                                height = min(color_height_dict[get_wall_color_at_point(rectangle, b["y1"], "y")], color_height_dict[get_wall_color_at_point(other_rectangle, (b["x1"]+b["x2"])/2, "x")])

                                # creates a dict for where and what type of ridges there should be
                                rectangle["ridges"].append({
                                    "direction": "head_top",
                                    "location": {
                                        "start": [b["x1"], b["y1"]],
                                        "end": [b["x2"], b["y1"]],
                                    },
                                    "height": height,
                                })

                                other_rectangle["ridges"].append({
                                    "direction": "side_bottom",
                                    "location": {
                                        "start": [b["x1"], ob["y2"]],
                                        "end": [b["x2"], ob["y2"]],
                                    },
                                    "height": height,
                                })

                                # gets what the left space of no_ridges is left
                                rect_width = rectangle["bounds"]["width"]
                                for no_ridge_place in rectangle["no_ridge_places"]:
                                    rect_width -= no_ridge_place["y2"] - no_ridge_place["y1"]

                                other_rect_length = other_rectangle["bounds"]["length"]
                                for no_ridge_place in other_rectangle["no_ridge_places"]:
                                    other_rect_length -= no_ridge_place["x2"] - no_ridge_place["x1"]

                                # calculates where there will be no ridges depending on how much space is left for ridges on which part
                                #TODO should there be rect_width and other_rect_length instead of bounds?
                                if "outer" in rectangle["id"] and "outer" in other_rectangle["id"]:
                                    if rect_width > 40 and other_rect_length > 40:
                                        rectangle["no_ridge_places"].append({"x1": b["x1"], "x2": b["x2"], "y1": b["y1"], "y2": b["y1"] + wall_width})
                                        other_rectangle["no_ridge_places"].append({"x1": b["x1"], "x2": b["x1"] + wall_width + 4, "y1": ob["y1"], "y2": ob["y2"]})
                                    elif rectangle["bounds"]["width"] < 4 and other_rectangle["bounds"]["length"] < (wall_width+4):
                                        other_rectangle["no_ridge_places"].append({"x1": ob["x1"], "x2": ob["x2"], "y1": ob["y1"], "y2": ob["y2"]})
                                    elif rectangle["bounds"]["width"] < 4 or rect_width < other_rect_length:
                                        other_rectangle["no_ridge_places"].append({"x1": ob["x1"], "x2": ob["x1"]+wall_width+4, "y1": ob["y1"], "y2": ob["y2"]})
                                    else:
                                        other_rectangle["no_ridge_places"].append({"x1": ob["x1"], "x2": ob["x1"]+wall_width, "y1": ob["y1"], "y2": ob["y2"]})
                                        rectangle["no_ridge_places"].append({"x1": b["x1"], "x2": b["x2"], "y1": b["y1"], "y2": b["y1"]+4})


                            if (
                                b["y2"] > ob["y1"] - tolerance
                                and b["y2"] < ob["y2"] + tolerance
                            ):
                                if "outer" in other_rectangle["id"] and len(other_rectangle["fill"]) > 1:
                                    split_fills_at(other_rectangle, b["x1"], b["x2"], "x")

                                height = min(color_height_dict[get_wall_color_at_point(rectangle, b["y2"], "y")], color_height_dict[get_wall_color_at_point(rectangle, (b["x1"]+b["x2"])/2, "x")])

                                rectangle["ridges"].append({
                                    "direction": "head_bottom",
                                    "location": {
                                        "start": [b["x1"], b["y2"]],
                                        "end": [b["x2"], b["y2"]],
                                    },
                                    "height": height,
                                })

                                other_rectangle["ridges"].append({
                                    "direction": "side_top",
                                    "location": {
                                        "start": [b["x1"], ob["y1"]],
                                        "end": [b["x2"], ob["y1"]],
                                    },
                                    "height": height,
                                })
                                rect_width = rectangle["bounds"]["width"]
                                for no_ridge_place in rectangle["no_ridge_places"]:
                                    rect_width -= no_ridge_place["y2"] - no_ridge_place["y1"]

                                other_rect_length = other_rectangle["bounds"]["length"]
                                for no_ridge_place in other_rectangle["no_ridge_places"]:
                                    other_rect_length -= no_ridge_place["x2"] - no_ridge_place["x1"]

                                if "outer" in rectangle["id"] and "outer" in other_rectangle["id"]:
                                    if rect_width > 40 and other_rect_length > 40:
                                        rectangle["no_ridge_places"].append({"x1": b["x1"], "x2": b["x2"], "y1": b["y2"] - 4, "y2": b["y2"]})
                                        other_rectangle["no_ridge_places"].append({"x1": b["x2"] - wall_width - 4, "x2": b["x2"], "y1": ob["y1"], "y2": ob["y2"]})
                                    elif rectangle["bounds"]["width"] < 4 and other_rectangle["bounds"]["length"] < (wall_width + 4):
                                        other_rectangle["no_ridge_places"].append({"x1": ob["x1"], "x2": ob["x2"], "y1": ob["y1"], "y2": ob["y2"]})
                                    elif rectangle["bounds"]["width"] < 4 or rect_width < other_rect_length:
                                        other_rectangle["no_ridge_places"].append({"x1": ob["x2"]-wall_width-4, "x2": ob["x2"], "y1": ob["y1"],"y2": ob["y2"]})
                                    else:
                                        other_rectangle["no_ridge_places"].append({"x1": ob["x2"]-wall_width, "x2": ob["x2"], "y1": ob["y1"],"y2": ob["y2"]})
                                        rectangle["no_ridge_places"].append({"x1": b["x1"], "x2": b["x2"], "y1": b["y2"]-4, "y2": b["y2"]})

                    else:
                        if (
                            b["y1"] > ob["y1"] - tolerance
                            and b["y2"] < ob["y2"] + tolerance
                        ):
                            if (
                                b["x1"] > ob["x1"] - tolerance
                                and b["x1"] < ob["x2"] + tolerance
                            ):
                                if "outer" in other_rectangle["id"] and len(other_rectangle["fill"]) > 1:
                                    split_fills_at(other_rectangle, b["y1"], b["y2"], "y")

                                height = min(color_height_dict[get_wall_color_at_point(rectangle, b["x1"], "x")], color_height_dict[get_wall_color_at_point(rectangle, (b["y1"]+b["y2"])/2, "y")])

                                rectangle["ridges"].append({
                                    "direction": "head_left",
                                    "location": {
                                        "start": [b["x1"], b["y1"]],
                                        "end": [b["x1"], b["y2"]],
                                    },
                                    "height": height,
                                })

                                other_rectangle["ridges"].append({
                                    "direction": "side_right",
                                    "location": {
                                        "start": [ob["x2"], b["y1"]],
                                        "end": [ob["x2"], b["y2"]],
                                    },
                                    "height": height,
                                })

                                rect_length = rectangle["bounds"]["length"]
                                for no_ridge_place in rectangle["no_ridge_places"]:
                                    rect_length -= no_ridge_place["x2"] - no_ridge_place["x1"]

                                other_rect_width = other_rectangle["bounds"]["width"]
                                for no_ridge_place in other_rectangle["no_ridge_places"]:
                                    other_rect_width -= no_ridge_place["y2"] - no_ridge_place["y1"]

                                if "outer" in rectangle["id"] and "outer" in other_rectangle["id"]:
                                    if rect_length > 40 and other_rect_width > 40:
                                        rectangle["no_ridge_places"].append({"x1": b["x1"], "x2": b["x1"] + wall_width, "y1": b["y1"], "y2": b["y2"]})
                                        other_rectangle["no_ridge_places"].append({"x1": ob["x1"], "x2": ob["x2"], "y1": ob["y2"] - wall_width - 4, "y2": ob["y2"]})
                                    elif rectangle["bounds"]["length"] < 4 and other_rectangle["bounds"]["width"] < (wall_width+4):
                                        other_rectangle["no_ridge_places"].append({"x1": ob["x1"], "x2": ob["x2"], "y1": ob["y1"], "y2": ob["y2"]})
                                    elif rectangle["bounds"]["length"] < 4 or rect_length < other_rect_width:
                                        other_rectangle["no_ridge_places"].append({"x1": ob["x1"], "x2": ob["x2"], "y1": ob["y2"]-wall_width-4, "y2": ob["y2"]})
                                    else:
                                        rectangle["no_ridge_places"].append({"x1": b["x1"], "x2": b["x1"]+4, "y1": b["y1"], "y2": b["y2"]})
                                        other_rectangle["no_ridge_places"].append({"x1": ob["x1"], "x2": ob["x2"], "y1": ob["y2"]-wall_width, "y2": ob["y2"]})

                            if (
                                b["x2"] > ob["x1"] - tolerance
                                and b["x2"] < ob["x2"] + tolerance
                            ):
                                if "outer" in other_rectangle["id"] and len(other_rectangle["fill"]) > 1:
                                    split_fills_at(other_rectangle, b["y1"], b["y2"], "y")

                                height = min(color_height_dict[get_wall_color_at_point(rectangle, b["x2"], "x")], color_height_dict[get_wall_color_at_point(rectangle, (b["y1"]+b["y2"])/2, "y")])

                                rectangle["ridges"].append({
                                    "direction": "head_right",
                                    "location": {
                                        "start": [b["x2"], b["y1"]],
                                        "end": [b["x2"], b["y2"]],
                                    },
                                    "height": height,
                                })

                                other_rectangle["ridges"].append({
                                    "direction": "side_left",
                                    "location": {
                                        "start": [ob["x1"], b["y1"]],
                                        "end": [ob["x1"], b["y2"]],
                                    },
                                    "height": height,
                                })
                                rect_length = rectangle["bounds"]["length"]
                                for no_ridge_place in rectangle["no_ridge_places"]:
                                    rect_length -= no_ridge_place["x2"] - no_ridge_place["x1"]

                                other_rect_width = other_rectangle["bounds"]["width"]
                                for no_ridge_place in other_rectangle["no_ridge_places"]:
                                    other_rect_width -= no_ridge_place["y2"] - no_ridge_place["y1"]

                                if "outer" in rectangle["id"] and "outer" in other_rectangle["id"]:
                                    if rect_length > 40 and other_rect_width > 40:
                                        rectangle["no_ridge_places"].append({"x1": b["x2"] - 4, "x2": b["x2"], "y1": b["y1"], "y2": b["y2"]})
                                        other_rectangle["no_ridge_places"].append({"x1": ob["x1"], "x2": ob["x2"], "y1": ob["y1"], "y2": ob["y1"] + wall_width + 4})
                                    elif rectangle["bounds"]["length"] < 4 and other_rectangle["bounds"]["width"] < (wall_width + 4):
                                        other_rectangle["no_ridge_places"].append({"x1": ob["x1"], "x2": ob["x2"], "y1": ob["y1"], "y2": ob["y2"]})
                                    elif rectangle["bounds"]["length"] < 4 or rect_length < other_rect_width:
                                        other_rectangle["no_ridge_places"].append({"x1": ob["x1"], "x2": ob["x2"], "y1": ob["y1"], "y2": ob["y1"]+wall_width+4})
                                    else:
                                        rectangle["no_ridge_places"].append({"x1": b["x2"]-4, "x2": b["x2"], "y1": b["y1"], "y2": b["y2"]})
                                        other_rectangle["no_ridge_places"].append( {"x1": ob["x1"], "x2": ob["x2"], "y1": ob["y1"], "y2": ob["y1"]+ wall_width})

        # makes ridge places not be in the corners ever
        for key, polygons in walls.items():
            for rectangle in polygons:
                b = rectangle["bounds"]
                if "outer" in rectangle["id"]:
                    if rectangle["no_ridge_places"] != []:
                        rectangle.setdefault("ridge_places", []).append(b.copy())
                        for ridge in rectangle["no_ridge_places"]:
                            if rectangle["direction"] == "horizontal":
                                if b["x1"]-tolerance <= ridge["x1"] <= b["x1"] + tolerance:
                                    rectangle["ridge_places"][0]["x1"] = ridge["x2"]
                                elif b["x2"]-tolerance <= ridge["x2"] <= b["x2"]+tolerance:
                                    rectangle["ridge_places"][0]["x2"] = ridge["x1"]
                            else:
                                if b["y1"] - tolerance <= ridge["y1"] <= b["y1"] + tolerance:
                                    rectangle["ridge_places"][0]["y1"] = ridge["y2"]
                                elif b["y2"] - tolerance <= ridge["y2"] <= b["y2"] + tolerance:
                                    rectangle["ridge_places"][0]["y2"] = ridge["y1"]
                    else:
                        rectangle.setdefault("ridge_places", []).append(b.copy())


            for polygon in polygons:
                if polygon["direction"] == "vertical":
                    match_handled = False
                    for fill_index, fill in enumerate(polygon["fill"]):
                        # runs only if fill is the length of wall_width (4cm originally) (maybe so it removes base or bottom ridges?)
                        if fill["bounds"]["width"] != wall_width:
                            continue
                        for ridge in polygon["ridges"]:
                            # ridge is not the whole fill bounds
                            same_vertical_span = (ridge["location"]["start"][1] == fill["bounds"]["y1"] and ridge["location"]["end"][1] == fill["bounds"]["y2"])
                            if not same_vertical_span:
                                continue
                            for other_polygon in polygons:
                                if other_polygon is polygon:
                                    continue
                                for other_ridge in other_polygon["ridges"]:
                                    if other_ridge["location"] != ridge["location"]:
                                        continue
                                    new_ridge_location = {"start": [polygon["bounds"]["x1"], ridge["location"]["start"][1]], "end": [polygon["bounds"]["x2"], ridge["location"]["start"][1]]}
                                    if (other_ridge["direction"] == "head_left" and ridge["direction"] == "side_right"):
                                        if fill_index == len(polygon["fill"]) - 1:
                                            next_fill = fill_index - 1
                                        else:
                                            next_fill = fill_index + 1
                                        height = min(color_height_dict[polygon["fill"][fill_index]["color"]], color_height_dict[polygon["fill"][next_fill]["color"]])
                                        other_polygon["fill"][0]["bounds"]["x1"] -= wall_width
                                        rebuild_from_fills(other_polygon)
                                        polygon["fill"].pop(fill_index)
                                        if polygon["fill"]:
                                            rebuild_from_fills(polygon)
                                        else:
                                            polygons.remove(polygon)
                                        ridge.update({"direction": "head_bottom", "height": height, "location": new_ridge_location})
                                        other_ridge.update({"direction": "side_top", "height": height, "location": new_ridge_location})
                                        match_handled = True
                                        break

                                    elif (other_ridge["direction"] == "head_right" and ridge[
                                        "direction"] == "side_left"):
                                        if fill_index == 0:
                                            next_fill = fill_index + 1
                                        else:
                                            next_fill = fill_index - 1
                                        height = min(color_height_dict[polygon["fill"][fill_index]["color"]], color_height_dict[polygon["fill"][next_fill]["color"]])
                                        other_polygon["fill"][0]["bounds"]["y2"] += wall_width
                                        rebuild_from_fills(other_polygon)
                                        polygon["fill"].pop(fill_index)
                                        if polygon["fill"]:
                                            rebuild_from_fills(polygon)
                                        else:
                                            polygons.remove(polygon)
                                        ridge.update({"direction": "head_right", "height": height, "location": new_ridge_location})
                                        other_ridge.update({"direction": "side_left", "height": height, "location": new_ridge_location})
                                        match_handled = True
                                        break
                                if match_handled:
                                    break
                            if match_handled:
                                break
                        if match_handled:
                            break

                # If the one of the walls (at the edge), has a certain height only for wall width and then it lowers/highers, changes the orientation of the ridges,
                # So the ridges can attach. Otherwise in the short part of the wall you would get floating pieces.
                if polygon["direction"] == "horizontal":
                    match_handled = False
                    for fill_index, fill in enumerate(polygon["fill"][:]):
                        if fill["bounds"]["length"] != wall_width:
                            continue
                        for ridge in polygon["ridges"]:
                            same_vertical_span = (ridge["location"]["start"][0] == fill["bounds"]["x1"] and ridge["location"]["end"][0] == fill["bounds"]["x2"])
                            if not same_vertical_span:
                                continue
                            for other_polygon in polygons:
                                if other_polygon is polygon:
                                    continue
                                for other_ridge in other_polygon["ridges"]:
                                    if other_ridge["location"] != ridge["location"]:
                                        continue
                                    new_ridge_location = {"start": [ridge["location"]["end"][0], polygon["bounds"]["y1"]], "end": [ridge["location"]["end"][0], polygon["bounds"]["y2"]]}
                                    if (other_ridge["direction"] == "head_top" and ridge["direction"] == "side_bottom"):
                                        if fill_index == len(polygon["fill"]) - 1:
                                            next_fill = fill_index - 1
                                        else:
                                            next_fill = fill_index + 1
                                        height = min(color_height_dict[polygon["fill"][fill_index]["color"]], color_height_dict[polygon["fill"][next_fill]["color"]])
                                        other_polygon["fill"][0]["bounds"]["y1"] -= wall_width
                                        rebuild_from_fills(other_polygon)
                                        polygon["fill"].pop(fill_index)
                                        if polygon["fill"]:
                                            rebuild_from_fills(polygon)
                                        else:
                                            polygons.remove(polygon)
                                        ridge.update({"direction": "head_left", "height": height, "location": new_ridge_location})
                                        other_ridge.update({"direction": "side_right", "height": height, "location": new_ridge_location})
                                        match_handled = True
                                        break

                                    elif (other_ridge["direction"] == "head_bottom" and ridge["direction"] == "side_top"):
                                        if fill_index == 0:
                                            next_fill = fill_index + 1
                                        else:
                                            next_fill = fill_index - 1
                                        height = min(color_height_dict[polygon["fill"][fill_index]["color"]], color_height_dict[polygon["fill"][next_fill]["color"]])
                                        other_polygon["fill"][0]["bounds"]["y2"] += wall_width
                                        rebuild_from_fills(other_polygon)
                                        polygon["fill"].pop(fill_index)
                                        if polygon["fill"]:
                                            rebuild_from_fills(polygon)
                                        else:
                                            polygons.remove(polygon)
                                        ridge.update({"direction": "head_right", "height": height, "location": new_ridge_location})
                                        other_ridge.update({"direction": "side_left", "height": height, "location": new_ridge_location})
                                        match_handled = True
                                        break
                                if match_handled:
                                    break
                            if match_handled:
                                break
                        if match_handled:
                            break

            for polygon in polygons:
                for fill in polygon["fill"]:
                    fill["bounds"]["polygon"] = polygon_from_any_bounds(fill["bounds"])

            if render and layer_out_dir is not None:
                plot_single_polygon_debug(
                    f"{layer_name}_{key}",
                    polygons,
                    layer_out_dir,
                )

            returned[layer_name][key] = polygons

    for key, polygons in returned.items():
        for key2, rectangles in polygons.items():
            for rectangle in rectangles:
                rectangle["3D_cuboids"] = []
            for rectangle in rectangles:
                if "outer" in rectangle["id"]:
                    # gets bottom ridges
                    if rectangle["direction"] == "horizontal":
                        rectangle["bottom_ridge_places"] = ridge_places(rectangle["ridge_places"][0]["x1"], rectangle["ridge_places"][0]["x2"])
                    else:
                        rectangle["bottom_ridge_places"] = ridge_places(rectangle["ridge_places"][0]["y1"], rectangle["ridge_places"][0]["y2"])
                # gets vertical ridge places
                for ridge in rectangle["ridges"]:
                    ridge["ridge_places"] = ridge_places(wall_width, ridge["height"])
                for fill in rectangle["fill"]:
                    color_height_dict["#552200"] = 15
                    if rectangle["type"] != "base":
                        fill["bounds"]["height"] = color_height_dict[fill["color"]]
                # gets the 3D cuboid for simple rectangle basis, or split a complex shape into simple rectangles
                if rectangle["type"] == "base":
                    if "path" not in rectangle["id"]:
                        rectangle["3D_cuboids"].append({"x1": rectangle["bounds"]["x1"], "x2": rectangle["bounds"]["x2"], "y1": rectangle["bounds"]["y1"], "y2": rectangle["bounds"]["y2"], "z1": 0, "z2": wall_width, "shape": "rect", "hole": 0, "bend": None, "main": True})
                    else:
                        simple_poly = remove_collinear_points(rectangle["polygon"])
                        subrects = polygon_to_rectangles(simple_poly)
                        for subrect in subrects:
                            rectangle["3D_cuboids"].append({"x1": subrect["x1"], "x2": subrect["x2"], "y1": subrect["y1"], "y2": subrect["y2"], "z1": 0, "z2": wall_width, "shape": "rect", "hole": 0, "bend": None, "main": True})
                if rectangle["type"] != "base":
                    if rectangle["direction"] == "horizontal":
                        for i in range(len(rectangle["fill"])):
                            bend = []
                            ridge_edges = {"x1":-1000000, "x2":1000000, "y1": -1000000, "y2": 1000000}
                            # if brown, gets the highest wall of the neighbours
                            if rectangle["fill"][i]["color"] == "#552200":
                                height = 0
                                if rectangle["fill"][i - 1]["color"] != "#552200" and rectangle["fill"][i+1]["color"] != "#552200":
                                    if i+1 < len(rectangle["fill"]) and i-1 > 0:
                                        height = max(color_height_dict[rectangle["fill"][i-1]["color"]], color_height_dict[rectangle["fill"][i + 1]["color"]], height)
                                    elif i+1 < len(rectangle["fill"]):
                                        height = max(color_height_dict[rectangle["fill"][i + 1]["color"]], height)
                                    else:
                                        height = max(color_height_dict[rectangle["fill"][i - 1]["color"]], height)
                                """
                                for j in range(1, i-1):
                                    if rectangle["fill"][i-j]["color"] != "#552200":
                                        height = max(color_height_dict[rectangle["fill"][i-j]["color"]], height)
                                        break
                                for j in range(i+1, len(rectangle["fill"])):
                                    if rectangle["fill"][j]["color"] != "#552200":
                                        height = max(color_height_dict[rectangle["fill"][i - j]["color"]], height)
                                        break"""
                                # applies a bend to it
                                bend = bend_append(bend, "left", "up", max((rectangle["fill"][i]["bounds"]["x2"]-rectangle["fill"][i]["bounds"]["x1"])/2, 20))
                                bend = bend_append(bend, "right", "up", max((rectangle["fill"][i]["bounds"]["x2"] -rectangle["fill"][i]["bounds"]["x1"]) / 2,20))
                                if height > 20:
                                    color_height_dict["#552200"] = height-20
                                else:
                                    color_height_dict["#552200"] = height

                            # changes ridge_edges locations at most from start to end
                            for ridge in rectangle["ridges"]:
                                if "side" in ridge["direction"]:
                                    if ridge["location"]["end"][0]<=rectangle["fill"][i]["bounds"]["x2"] and ridge["location"]["start"][0]>=rectangle["fill"][i]["bounds"]["x1"]:
                                        if ridge["location"]["start"][0] > ridge_edges["x1"]:
                                            ridge_edges["x1"] = ridge["location"]["start"][0]
                                        if ridge["location"]["end"][0] < ridge_edges["x2"]:
                                            ridge_edges["x2"] = ridge["location"]["end"][0]

                            right_bend_length = 5
                            left_bend_length = 5
                            #I think this should be bend length not ridge length
                            # In general shortens bend if it's next to a wall
                            for ridge in rectangle["ridges"]:
                                if i == len(rectangle["fill"]) - 1:
                                    if "head_right" in ridge["direction"]:
                                        right_bend_length = 0
                                    elif rectangle["bounds"]["x2"] - wall_width - tolerance < ridge["location"]["end"][0]:
                                        right_bend_length = rectangle["bounds"]["x2"] - ridge["location"]["end"][0] - tolerance
                                    elif ridge["location"]["start"][0] - tolerance < rectangle["bounds"]["x2"] < ridge["location"]["end"][0]:
                                        right_bend_length = 0
                                if i == 0:
                                    if "head_left" in ridge["direction"]:
                                        left_bend_length = 0
                                    elif rectangle["bounds"]["x1"] + wall_width + tolerance > ridge["location"]["start"][0]:
                                        left_bend_length = ridge["location"]["start"][0] - rectangle["bounds"]["x1"] - tolerance
                                    elif ridge["location"]["start"][0] - tolerance < rectangle["bounds"]["x2"] < ridge["location"]["end"][0]:
                                        left_bend_length = 0
                                if len(rectangle["fill"]) != 1:
                                    if i == 0:
                                        right_bend_length = 0
                                    if i == len(rectangle["fill"]) - 1:
                                        left_bend_length = 0

                            bend = bend_append(bend, "right", "down", min(right_bend_length, 5))
                            bend = bend_append(bend, "left", "down",  min(left_bend_length, 5))

                            # gets how long the bend should be between 2 heights (taking account of ridges from inner walls)
                            if i < len(rectangle["fill"])-1:
                                bend_length = 5
                                for ridge in rectangle["ridges"]:
                                    if rectangle["fill"][i]["bounds"]["x1"] - tolerance < ridge["location"]["start"][0] < rectangle["fill"][i]["bounds"]["x1"] + wall_width + tolerance:
                                        bend_length = min(ridge["location"]["start"][0] - rectangle["fill"][i]["bounds"]["x1"],bend_length)
                                    elif rectangle["fill"][i]["bounds"]["x1"] - wall_width - tolerance < ridge["location"]["start"][0] < rectangle["fill"][i]["bounds"]["x1"] + tolerance:
                                        bend_length = 0
                                if color_height_dict[rectangle["fill"][i+1]["color"]]<color_height_dict[rectangle["fill"][i]["color"]] and rectangle["fill"][i]["color"] != "#552200":
                                    bend = bend_append(bend, "left", "down", min(rectangle["fill"][i]["bounds"]["length"]/2, abs(ridge_edges["x2"]-rectangle["fill"][i]["bounds"]["x2"]), bend_length))


                            if i>0:
                                bend_length = 5
                                for ridge in rectangle["ridges"]:
                                   if rectangle["fill"][i]["bounds"]["x2"]-wall_width-tolerance < ridge["location"]["end"][0] < rectangle["fill"][i]["bounds"]["x2"]-tolerance:
                                       bend_length = min(rectangle["fill"][i]["bounds"]["x2"] - ridge["location"]["end"][0], bend_length)
                                   if rectangle["fill"][i]["bounds"]["x2"] - tolerance < ridge["location"]["end"][0] < rectangle["fill"][i]["bounds"]["x2"] + wall_width - tolerance:
                                        bend_length = 0
                                if color_height_dict[rectangle["fill"][i-1]["color"]]<color_height_dict[rectangle["fill"][i]["color"]] and rectangle["fill"][i]["color"] != "#552200":
                                    bend_append(bend, "right", "down", min(rectangle["fill"][i]["bounds"]["length"]/2, abs(ridge_edges["x1"]-rectangle["fill"][i]["bounds"]["x1"]), bend_length))

                        # fill 3D cuboids for each fill part
                            rectangle["3D_cuboids"].append({"x1": rectangle["fill"][i]["bounds"]["x1"], "x2": rectangle["fill"][i]["bounds"]["x2"], "y1": rectangle["fill"][i]["bounds"]["y1"], "y2": rectangle["fill"][i]["bounds"]["y2"], "z1": wall_width, "z2": rectangle["fill"][i]["bounds"]["height"], "shape": "rect", "hole": 0, "bend": bend, "main": True})
                        # get all the 3D cuboids for ridges
                        for bottom_ridge in rectangle.get("bottom_ridge_places", []):
                            rectangle["3D_cuboids"].append({"x1": bottom_ridge[0], "x2": bottom_ridge[1], "y1":rectangle["bounds"]["y1"], "y2": rectangle["bounds"]["y2"], "z1": 0, "z2": wall_width, "shape": "rect", "hole": 0, "bend": None, "main": False})
                            for rect2 in rectangles:
                                if rect2["type"] == "base":
                                    rect2["3D_cuboids"].append({"x1": bottom_ridge[0], "x2": bottom_ridge[1], "y1": rectangle["bounds"]["y1"], "y2":rectangle["bounds"]["y2"], "z1": wall_width, "z2": 0, "shape": "rect", "hole": 1, "bend": None, "main": False})
                        for ridge in rectangle["ridges"]:
                            for ridge_place in ridge["ridge_places"]:
                                if ridge["direction"] == 'head_right':
                                    rectangle["3D_cuboids"].append({"x1": rectangle["bounds"]["x2"], "x2": rectangle["bounds"]["x2"] + wall_width, "y1": rectangle["bounds"]["y1"], "y2": rectangle["bounds"]["y2"], "z1": ridge_place[0], "z2": ridge_place[1], "shape": "rect", "hole": 0, "bend": None, "main": False})
                                if ridge["direction"] == 'head_left':
                                    rectangle["3D_cuboids"].append({"x1": rectangle["bounds"]["x1"]-wall_width, "x2": rectangle["bounds"]["x1"], "y1":rectangle["bounds"]["y1"], "y2":rectangle["bounds"]["y2"], "z1": ridge_place[0], "z2": ridge_place[1], "shape": "rect", "hole": 0, "bend": None, "main": False})
                                if ridge["direction"] == 'side_top' or ridge["direction"] == 'side_bottom':
                                    rectangle["3D_cuboids"].append({"x1": ridge["location"]["start"][0], "x2": ridge["location"]["end"][0], "y1":rectangle["bounds"]["y1"], "y2":rectangle["bounds"]["y2"], "z1": ridge_place[0], "z2": ridge_place[1], "shape": "rect", "hole": 1, "bend": None, "main": False})
                    else:
                        for i in range(len(rectangle["fill"])):
                            ridge_edges = {"x1": -1000000, "x2": 1000000, "y1": -1000000, "y2": 1000000}
                            bend = []
                            if rectangle["fill"][i]["color"] == "#552200":
                                height = 0
                                for j in range(1, i-1):
                                    if rectangle["fill"][i-j]["color"] != "#552200":
                                        height = max(color_height_dict[rectangle["fill"][i-j]["color"]], height)
                                        break
                                for j in range(i+1, len(rectangle["fill"])):
                                    if rectangle["fill"][j]["color"] != "#552200":
                                        height = max(color_height_dict[rectangle["fill"][i - j]["color"]], height)
                                        break
                                bend_append(bend, "backward", "up", max((rectangle["fill"][i]["bounds"]["x2"]-rectangle["fill"][i]["bounds"]["x1"])/2, 20))
                                bend_append(bend, "forward", "up", max((rectangle["fill"][i]["bounds"]["x2"] - rectangle["fill"][i]["bounds"]["x1"]) / 2, 20))
                                if height > 20:
                                    color_height_dict["#552200"] = height-20
                                else:
                                    color_height_dict["#552200"] = height

                            for ridge in rectangle["ridges"]:
                                if "side" in ridge["direction"]:
                                    if (ridge["location"]["end"][1] <= rectangle["fill"][i]["bounds"]["y2"]
                                            and ridge["location"]["start"][1] >= rectangle["fill"][i]["bounds"]["y1"]):
                                        if ridge["location"]["start"][1] > ridge_edges["y1"]:
                                            ridge_edges["y1"] = ridge["location"]["start"][1]
                                        if ridge["location"]["end"][1] < ridge_edges["y2"]:
                                            ridge_edges["y2"] = ridge["location"]["end"][1]

                            top_bend_length = 5
                            bottom_bend_length = 5
                            for ridge in rectangle["ridges"]:
                                if i == len(rectangle["fill"])-1:
                                    if "head_bottom" in ridge["direction"]:
                                        top_bend_length = 0
                                    elif rectangle["bounds"]["y2"] - wall_width - tolerance < ridge["location"]["end"][1]:
                                        top_bend_length = rectangle["bounds"]["y2"]-ridge["location"]["end"][1]-tolerance
                                    elif ridge["location"]["start"][1]-tolerance<rectangle["bounds"]["y2"]<ridge["location"]["end"][1]:
                                        top_bend_length = 0
                                if i == 0:
                                    if "head_top" in ridge["direction"]:
                                        bottom_bend_length = 0
                                    elif rectangle["bounds"]["y1"] + wall_width + tolerance > ridge["location"]["start"][1]:
                                        bottom_bend_length = ridge["location"]["start"][1]-rectangle["bounds"]["y1"]-tolerance
                                    elif ridge["location"]["start"][1]-tolerance<rectangle["bounds"]["y2"]<ridge["location"]["end"][1]:
                                        bottom_bend_length = 0
                                if len(rectangle["fill"]) != 1:
                                    if i == 0:
                                        top_bend_length = 0
                                    if i == len(rectangle["fill"])-1:
                                        bottom_bend_length = 0

                            bend_append(bend, "forward", "down", min(top_bend_length, 5))
                            bend_append(bend, "backward", "down", min(bottom_bend_length, 5))

                            if i < len(rectangle["fill"]) - 1:
                                bend_length = 5
                                for ridge in rectangle["ridges"]:
                                    if rectangle["fill"][i]["bounds"]["y1"]+tolerance < ridge["location"]["start"][1] < rectangle["fill"][i]["bounds"]["y1"]+wall_width+tolerance:
                                        bend_length = min(ridge["location"]["start"][1]-rectangle["fill"][i]["bounds"]["y1"], bend_length)
                                    elif rectangle["fill"][i]["bounds"]["y1"]-wall_width+tolerance < ridge["location"]["start"][1] < rectangle["fill"][i]["bounds"]["y1"]+tolerance:
                                        bend_length = 0
                                if bend_length > 0:
                                    if (color_height_dict[rectangle["fill"][i + 1]["color"]] < color_height_dict[rectangle["fill"][i]["color"]] and rectangle["fill"][i]["color"] != "#552200"):
                                        bend_append(bend, "backward","down",min(rectangle["fill"][i]["bounds"]["width"] / 2, abs(ridge_edges["y2"] - rectangle["fill"][i]["bounds"]["y2"]),bend_length))

                            if i > 0:
                                bend_length = 5
                                for ridge in rectangle["ridges"]:
                                   if rectangle["fill"][i]["bounds"]["y2"]-wall_width-tolerance < ridge["location"]["end"][1] < rectangle["fill"][i]["bounds"]["y2"]-tolerance:
                                       bend_length = min(rectangle["fill"][i]["bounds"]["y2"] - ridge["location"]["end"][1], bend_length)
                                   if rectangle["fill"][i]["bounds"]["y2"] - tolerance < ridge["location"]["end"][1] < rectangle["fill"][i]["bounds"]["y2"] + wall_width - tolerance:
                                        bend_length = 0
                                if bend_length > 0:
                                    if (color_height_dict[rectangle["fill"][i - 1]["color"]] < color_height_dict[rectangle["fill"][i]["color"]] and rectangle["fill"][i]["color"] != "#552200"):
                                        bend_append(bend, "forward", "down", min(rectangle["fill"][i]["bounds"]["width"] / 2, abs(ridge_edges["y1"] - rectangle["fill"][i]["bounds"]["y1"]),bend_length))

                            rectangle["3D_cuboids"].append({
                                "x1": rectangle["fill"][i]["bounds"]["x1"],
                                "x2": rectangle["fill"][i]["bounds"]["x2"],
                                "y1": rectangle["fill"][i]["bounds"]["y1"],
                                "y2": rectangle["fill"][i]["bounds"]["y2"],
                                "z1": wall_width,
                                "z2": rectangle["fill"][i]["bounds"]["height"],
                                "shape": "rect",
                                "hole": 0,
                                "bend": bend,
                                "main": True
                            })

                        for bottom_ridge in rectangle.get("bottom_ridge_places", []):
                            rectangle["3D_cuboids"].append({
                                "x1": rectangle["bounds"]["x1"],
                                "x2": rectangle["bounds"]["x2"],
                                "y1": bottom_ridge[0],
                                "y2": bottom_ridge[1],
                                "z1": 0,
                                "z2": wall_width,
                                "shape": "rect",
                                "hole": 0,
                                "bend": None,
                                "main": False
                            })

                            for rect2 in rectangles:
                                if rect2["type"] == "base":
                                    rect2["3D_cuboids"].append({
                                        "x1": rectangle["bounds"]["x1"],
                                        "x2": rectangle["bounds"]["x2"],
                                        "y1": bottom_ridge[0],
                                        "y2": bottom_ridge[1],
                                        "z1": wall_width,
                                        "z2": 0,
                                        "shape": "rect",
                                        "hole": 1,
                                        "bend": None,
                                        "main": False
                                    })

                        for ridge in rectangle["ridges"]:
                            for ridge_place in ridge["ridge_places"]:
                                if ridge["direction"] == "head_top":
                                    rectangle["3D_cuboids"].append({
                                        "x1": rectangle["bounds"]["x1"],
                                        "x2": rectangle["bounds"]["x2"],
                                        "y1": rectangle["bounds"]["y1"] - wall_width,
                                        "y2": rectangle["bounds"]["y1"],
                                        "z1": ridge_place[0],
                                        "z2": ridge_place[1],
                                        "shape": "rect",
                                        "hole": 0,
                                        "bend": None,
                                        "main": False
                                    })

                                if ridge["direction"] == "head_bottom":
                                    rectangle["3D_cuboids"].append({
                                        "x1": rectangle["bounds"]["x1"],
                                        "x2": rectangle["bounds"]["x2"],
                                        "y1": rectangle["bounds"]["y2"],
                                        "y2": rectangle["bounds"]["y2"] + wall_width,
                                        "z1": ridge_place[0],
                                        "z2": ridge_place[1],
                                        "shape": "rect",
                                        "hole": 0,
                                        "bend": None,
                                        "main": False
                                    })

                                if ridge["direction"] == "side_right" or ridge["direction"] == "side_left":
                                    rectangle["3D_cuboids"].append({
                                        "x1": rectangle["bounds"]["x1"],
                                        "x2": rectangle["bounds"]["x2"],
                                        "y1": ridge["location"]["start"][1],
                                        "y2": ridge["location"]["end"][1],
                                        "z1": ridge_place[0],
                                        "z2": ridge_place[1],
                                        "shape": "rect",
                                        "hole": 1,
                                        "bend": None,
                                        "main": False
                                    })
    return returned