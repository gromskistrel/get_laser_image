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


def add_connection_info_to_walls(wall_layers, out_dir=None, render=False):
    tolerance = 1
    returned = {}

    for layer_name, walls in wall_layers.items():
        print(layer_name)

        returned[layer_name] = {}

        layer_out_dir = None
        if render and out_dir is not None:
            layer_out_dir = Path(out_dir) / layer_name

        for key, polygon in walls.items():
            print(key)

            for rectangle in polygon:
                if rectangle["bounds"]["height"] > rectangle["bounds"]["width"]:
                    rectangle["direction"] = "vertical"
                else:
                    rectangle["direction"] = "horizontal"

                rectangle["ridges"] = []

            for rectangle in polygon:
                for other_rectangle in polygon:
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
                                rectangle["ridges"].append({
                                    "direction": "head_top",
                                    "location": {
                                        "start": [b["x1"], b["y1"]],
                                        "end": [b["x2"], b["y1"]],
                                    },
                                })

                                other_rectangle["ridges"].append({
                                    "direction": "side_bottom",
                                    "location": {
                                        "start": [b["x1"], ob["y2"]],
                                        "end": [b["x2"], ob["y2"]],
                                    },
                                })

                            if (
                                b["y2"] > ob["y1"] - tolerance
                                and b["y2"] < ob["y2"] + tolerance
                            ):
                                rectangle["ridges"].append({
                                    "direction": "head_bottom",
                                    "location": {
                                        "start": [b["x1"], b["y2"]],
                                        "end": [b["x2"], b["y2"]],
                                    },
                                })

                                other_rectangle["ridges"].append({
                                    "direction": "side_top",
                                    "location": {
                                        "start": [b["x1"], ob["y1"]],
                                        "end": [b["x2"], ob["y1"]],
                                    },
                                })

                    else:
                        if (
                            b["y1"] > ob["y1"] - tolerance
                            and b["y2"] < ob["y2"] + tolerance
                        ):
                            if (
                                b["x1"] > ob["x1"] - tolerance
                                and b["x1"] < ob["x2"] + tolerance
                            ):
                                rectangle["ridges"].append({
                                    "direction": "head_left",
                                    "location": {
                                        "start": [b["x1"], b["y1"]],
                                        "end": [b["x1"], b["y2"]],
                                    },
                                })

                                other_rectangle["ridges"].append({
                                    "direction": "side_right",
                                    "location": {
                                        "start": [ob["x2"], b["y1"]],
                                        "end": [ob["x2"], b["y2"]],
                                    },
                                })

                            if (
                                b["x2"] > ob["x1"] - tolerance
                                and b["x2"] < ob["x2"] + tolerance
                            ):
                                rectangle["ridges"].append({
                                    "direction": "head_right",
                                    "location": {
                                        "start": [b["x2"], b["y1"]],
                                        "end": [b["x2"], b["y2"]],
                                    },
                                })

                                other_rectangle["ridges"].append({
                                    "direction": "side_left",
                                    "location": {
                                        "start": [ob["x1"], b["y1"]],
                                        "end": [ob["x1"], b["y2"]],
                                    },
                                })

            if render and layer_out_dir is not None:
                plot_single_polygon_debug(
                    f"{layer_name}_{key}",
                    polygon,
                    layer_out_dir,
                )

            returned[layer_name][key] = polygon

    return returned