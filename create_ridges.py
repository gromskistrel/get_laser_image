import matplotlib.pyplot as plt
from pathlib import Path
from shapely.geometry import box
from matplotlib.patches import Rectangle


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
            plot_bounds_rect(
                wall["bounds"],
                fill_color="#cccccc",
                edge_color=edge_color,
                linewidth=linewidth,
                alpha=alpha,
            )
            return

        for fill_part in fill:
            plot_bounds_rect(
                fill_part["bounds"],
                fill_color=fill_part.get("color"),
                edge_color=edge_color,
                linewidth=linewidth,
                alpha=alpha,
            )

        return

    plot_bounds_rect(
        wall["bounds"],
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


def plot_single_polygon_debug(key, polygon, out_dir):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    plt.figure(figsize=(10, 8))

    for rectangle in polygon:
        if rectangle["id"].endswith("_base"):
            continue

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

def ridge_places(start, end, laser_width):
    perfect = 7.5
    interval_number = 1
    prev = 1000
    while True:
        interval_length = (end-start)/interval_number
        if abs(perfect-interval_length) > abs(perfect-prev):
            interval_length = prev
            break
        else:
            interval_number = interval_number+2
            prev = interval_length
    ridge_places = [laser_width+start]
    for i in range(interval_number-2):
        if i%2 == 0:
            ridge_places.append((i+1)*interval_length + start - laser_width)
        else:
            ridge_places.append((i+1)*interval_length + start + laser_width)

    print(f"ridge_start_difference = {ridge_places[0]-start}")
    print(f"ridge_end_difference = {end-ridge_places[-1]}")
    ridge_places = [
        ridge_places[i:i + 2]
        for i in range(0, len(ridge_places), 2)
    ]
    return ridge_places

def add_connection_info_to_walls(wall_layers, color_height_dict, out_dir=None, render=False, wall_width=3, laser_width = 0.075):
    tolerance = 1
    returned = {}

    for layer_name, walls in wall_layers.items():
        print(layer_name)

        returned[layer_name] = {}

        layer_out_dir = None
        if render and out_dir is not None:
            layer_out_dir = Path(out_dir) / layer_name

        # Used for getting middle walls (when walls are from each side)
        for key, polygons in walls.items():
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
                                    polygons[j]["bounds"]["y1"] + 0.1 > polygons[i]["bounds"]["y1"] >
                                    polygons[j]["bounds"]["y1"] - 0.1
                                    and polygons[j]["bounds"]["y2"] + 0.1 > polygons[i]["bounds"]["y2"] >
                                    polygons[j]["bounds"]["y2"] - 0.1
                            ):
                                ordered = [polygons[i], polygons[j]] if polygons[i]["bounds"]["x1"] < \
                                                                        polygons[j]["bounds"]["x1"] else [polygons[j],
                                                                                                          polygons[i]]
                                if ordered[1]["bounds"]["x1"]-ordered[0]["bounds"]["x2"] < wall_width+0.1:

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
                                    new_polygon["bounds"]["lengthh"] = new_polygon["bounds"]["x2"] - new_polygon["bounds"][
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
                        if (
                            b["x1"] > ob["x1"] - tolerance
                            and b["x2"] < ob["x2"] + tolerance
                        ):
                            if (
                                b["y1"] > ob["y1"] - tolerance
                                and b["y1"] < ob["y2"] + tolerance
                            ):
                                if "outer" in other_rectangle["id"] and len(other_rectangle["fill"]) > 1:
                                    split_fills_at(other_rectangle, b["x1"], b["x2"], "x")
                                height = min(color_height_dict[get_wall_color_at_point(rectangle, b["y1"], "y")], color_height_dict[get_wall_color_at_point(other_rectangle, (b["x1"]+b["x2"])/2, "x")])

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
                                if "outer" in rectangle["id"] and "outer" in other_rectangle["id"]:
                                    if rectangle["bounds"]["width"] < 4 and other_rectangle["bounds"]["length"] < (wall_width+4):
                                        rectangle["no_ridge_places"].append({"x1": b["x1"], "x2": b["x2"], "y1": b["y1"], "y2": b["y2"]})
                                        other_rectangle["no_ridge_places"].append({"x1": ob["x1"], "x2": ob["x2"], "y1": ob["y1"], "y2": ob["y2"]})
                                    elif rectangle["bounds"]["width"] < 4:
                                        other_rectangle[]
                                        rectangle["no_ridge_places"].append({"x1": b["x1"], "x2": b["x2"], "y1": b["y1"], "y2": b["y2"]})
                                    elif other_rectangle["bounds"]["length"] < (wall_width+4):
                                        other_rectangle["no_ridge_places"].append({"x1": ob["x1"], "x2": ob["x2"], "y1": ob["y1"], "y2": ob["y2"]})
                                    else:
                                        rectangle["no_ridge_places"].append({"x1": b["x1"], "x2": b["x2"], "y1": b["y1"], "y2": b["y2"]+4})
                                        other_rectangle["no_ridge_places"].append({"x1": b["x1"], "x2": b["x2"]+4, "y1": ob["y1"], "y2": ob["y2"]})


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
                                if "outer" in rectangle["id"] and "outer" in other_rectangle["id"]:
                                    other_rectangle["no_ridge_places"].append({"x1": b["x1"], "x2": b["x2"], "y1": ob["y1"], "y2": ob["y2"]})

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
                                if "outer" in rectangle["id"] and "outer" in other_rectangle["id"]:
                                    other_rectangle["no_ridge_places"].append({"x1": ob["x1"], "x2": ob["x2"], "y1": b["y1"], "y2": b["y2"]})


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
                                    if "outer" in rectangle["id"] and "outer" in other_rectangle["id"]:
                                        other_rectangle["no_ridge_places"].append({"x1": ob["x1"], "x2": ob["x2"], "y1": b["y1"], "y2": b["y2"]})

        for key, polygons in walls.items():
            for rectangle in polygons:
                b = rectangle["bounds"]
                if "outer" in rectangle["id"]:
                    if rectangle["no_ridge_places"] != []:
                        rectangle.setdefault("ridge_places", []).append(b)
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
                        rectangle.setdefault("ridge_places", []).append(b)



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
                if rectangle["id"] == 'rect17_outer_top' or rectangle["id"] == 'rect37_outer_top' :
                    print("yay")
                if "outer" in rectangle["id"]:
                    if rectangle["direction"] == "horizontal":
                        rectangle["bottom_ridge_places"] = ridge_places(rectangle["ridge_places"][0]["x1"], rectangle["ridge_places"][0]["x2"], laser_width)
                    else:
                        rectangle["bottom_ridge_places"] = ridge_places(rectangle["ridge_places"][0]["y1"], rectangle["ridge_places"][0]["y2"], laser_width)
                for ridge in rectangle["ridges"]:
                    ridge["ridge_places"] = ridge_places(4, ridge["height"], laser_width)
                for fill in rectangle["fill"]:

                    color_height_dict["#552200"] = 0
                    color_height_dict["#803300"] = 20
                    if "base" not in rectangle["id"]:
                        print(color_height_dict[fill["color"]])
                        fill["bounds"]["height"] = color_height_dict[fill["color"]]
                if "base" in rectangle["id"]:
                    rectangle["3D_cuboids"].append({"x1": rectangle["bounds"]["x1"], "x2": rectangle["bounds"]["x2"], "y1": rectangle["bounds"]["y1"], "y2": rectangle["bounds"]["y2"], "z1": 0, "z2": wall_width, "shape": "rect"})
                if "base" not in rectangle["id"]:
                    if rectangle["bounds"]["width"] == wall_width:
                        for fill in rectangle["fill"]:
                            rectangle["3D_cuboids"].append({"x1":fill["bounds"]["x1"], "x2": fill["bounds"]["x2"], "y1": fill["bounds"]["y1"], "y2": fill["bounds"]["y2"], "z1": wall_width, "z2": fill["bounds"]["height"], "shape": "rect"})
                        for bottom_ridge in rectangle.get("bottom_ridge_places", []):
                            rectangle["3D_cuboids"].append({"x1": bottom_ridge[0], "x2": bottom_ridge[1], "y1":rectangle["bounds"]["y1"], "y2":rectangle["bounds"]["y2"], "z1": 0, "z2": wall_width, "shape": "rect"})
                            for rect2 in rectangles:
                                if "base" in rect2["id"]:
                                    rect2["3D_cuboids"].append({"x1": bottom_ridge[0], "x2": bottom_ridge[1], "y1":rectangle["bounds"]["y1"], "y2":rectangle["bounds"]["y2"], "z1": wall_width, "z2": 0, "shape": "rect"})
                        for ridge in rectangle["ridges"]:
                            for ridge_place in ridge["ridge_places"]:
                                if ridge["direction"] == 'head_right':
                                    rectangle["3D_cuboids"].append({"x1": rectangle["bounds"]["x2"], "x2": rectangle["bounds"]["x2"] + wall_width, "y1": rectangle["bounds"]["y1"], "y2": rectangle["bounds"]["y2"], "z1": ridge_place[0], "z2": ridge_place[1], "shape": "rect"})
                                if ridge["direction"] == 'head_left':
                                    rectangle["3D_cuboids"].append({"x1": rectangle["bounds"]["x1"]-wall_width, "x2": rectangle["bounds"]["x1"], "y1":rectangle["bounds"]["y1"], "y2":rectangle["bounds"]["y2"], "z1": ridge_place[0], "z2": ridge_place[1], "shape": "rect"})
                                if ridge["direction"] == 'side_top' or ridge["direction"] == 'side_bottom':
                                    rectangle["3D_cuboids"].append({"x1": ridge["location"]["start"][0], "x2": ridge["location"]["end"][0], "y1":rectangle["bounds"]["y1"], "y2":rectangle["bounds"]["y2"], "z1": ridge_place[0], "z2": ridge_place[1], "shape": "rect"})
                    else:
                        for fill in rectangle["fill"]:
                            rectangle["3D_cuboids"].append({"x1":fill["bounds"]["x1"], "x2": fill["bounds"]["x2"], "y1": fill["bounds"]["y1"], "y2": fill["bounds"]["y2"], "z1": wall_width, "z2": fill["bounds"]["height"], "shape": "rect"})
                        for bottom_ridge in rectangle.get("bottom_ridge_places", []):
                            rectangle["3D_cuboids"].append({"x1": rectangle["bounds"]["x1"], "x2": rectangle["bounds"]["x2"], "y1": bottom_ridge[0], "y2": bottom_ridge[1], "z1": 0, "z2": wall_width, "shape": "rect"})
                            for rect2 in rectangles:
                                if "base" in rect2["id"]:
                                    rect2["3D_cuboids"].append({"x1": rectangle["bounds"]["x1"], "x2": rectangle["bounds"]["x2"], "y1": bottom_ridge[0], "y2": bottom_ridge[1], "z1": wall_width, "z2": 0, "shape": "rect"})
                        for ridge in rectangle["ridges"]:
                            for ridge_place in ridge["ridge_places"]:
                                if ridge["direction"] == 'head_top':
                                    rectangle["3D_cuboids"].append({"x1": rectangle["bounds"]["x1"], "x2": rectangle["bounds"]["x2"], "y1": rectangle["bounds"]["y1"]+wall_width, "y2": rectangle["bounds"]["y1"], "z1": ridge_place[0], "z2": ridge_place[1], "shape": "rect"})
                                if ridge["direction"] == 'head_bottom':
                                    rectangle["3D_cuboids"].append({"x1": rectangle["bounds"]["x1"], "x2": rectangle["bounds"]["x2"], "y1":rectangle["bounds"]["y2"], "y2":rectangle["bounds"]["y2"]+wall_width, "z1": ridge_place[0], "z2": ridge_place[1], "shape": "rect"})
                                if ridge["direction"] == 'side_right' or ridge["direction"] == 'side_left':
                                    rectangle["3D_cuboids"].append({"x1": rectangle["bounds"]["x1"], "x2": rectangle["bounds"]["x2"], "y1":ridge["location"]["start"][1], "y2":ridge["location"]["end"][1], "z1": ridge_place[0], "z2": ridge_place[1], "shape": "rect"})

    return returned