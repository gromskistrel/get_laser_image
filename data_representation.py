from pathlib import Path
import matplotlib.pyplot as plt


def safe_filename(name):
    return "".join(c if c.isalnum() or c in " _-" else "_" for c in name)


def clean_color(color, fallback="none"):
    if color is None:
        return fallback

    color = color.strip()

    if color.lower() in {"none", "transparent"}:
        return fallback

    return color


def plot_polygon(poly, fill_color=None, edge_color=None, linewidth=1):
    fill_color = clean_color(fill_color, fallback="none")
    edge_color = clean_color(edge_color, fallback="black")

    if poly.geom_type == "Polygon":
        x, y = poly.exterior.xy
        plt.fill(
            x,
            y,
            facecolor=fill_color,
            edgecolor=edge_color,
            linewidth=linewidth,
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
            )


def render_grouped_layers(grouped_layers, out_dir):
    out_dir = Path(out_dir)
    out_dir.mkdir(exist_ok=True)

    for layer_name, groups in grouped_layers.items():
        layer_out_dir = out_dir / safe_filename(layer_name)
        layer_out_dir.mkdir(exist_ok=True)

        for i, group in enumerate(groups):
            outer = group["outer"]
            inside = group["inside"]

            plt.figure(figsize=(8, 8))

            plot_polygon(
                outer["polygon"],
                fill_color=outer["fill"],
                edge_color=outer["stroke"],
                linewidth=2,
            )

            for obj in inside:
                plot_polygon(
                    obj["polygon"],
                    fill_color=obj["fill"],
                    edge_color=obj["stroke"],
                    linewidth=1,
                )

                cx = obj["polygon"].centroid.x
                cy = obj["polygon"].centroid.y
                plt.text(cx, cy, obj["id"], fontsize=6, ha="center", va="center")

            plt.title(
                f"Layer: {layer_name}\n"
                f"{outer['id']} contains {len(inside)} same-layer objects"
            )

            plt.axis("equal")
            plt.gca().invert_yaxis()

            out_png = layer_out_dir / f"{i:03d}_{safe_filename(outer['id'])}.png"
            plt.savefig(out_png, dpi=150, bbox_inches="tight")
            plt.close()

            print("Saved:", out_png)


def find_wall_for_outer(walls, outer_id):
    matches = []

    for wall in walls:
        parent_id = wall.get("parent_id", "")

        if parent_id == outer_id:
            matches.append(wall)

        elif parent_id.startswith(f"{outer_id}_piece_"):
            matches.append(wall)

    return matches


def render_groups_with_walls(grouped_layers, wall_layers, out_dir):
    """
    Debug renderer.

    Shows:
    - original outer object
    - original inner objects
    - generated wall material on top

    This lets you check if wall generation is real or nonsense.
    """

    out_dir = Path(out_dir)
    out_dir.mkdir(exist_ok=True)

    for layer_name, groups in grouped_layers.items():

        layer_out_dir = out_dir / safe_filename(layer_name)
        layer_out_dir.mkdir(exist_ok=True)

        walls = wall_layers.get(layer_name, [])

        for i, group in enumerate(groups):
            outer = group["outer"]
            inside = group["inside"]

            matching_walls = find_wall_for_outer(walls, outer["id"])

            plt.figure(figsize=(8, 8))

            # 1. draw original outer lightly
            plot_polygon(
                outer["polygon"],
                fill_color="#eeeeee",
                edge_color="black",
                linewidth=2,
            )

            # 2. draw original inner objects
            for obj in inside:
                plot_polygon(
                    obj["polygon"],
                    fill_color=obj["fill"],
                    edge_color=obj["stroke"],
                    linewidth=1,
                )

                cx = obj["polygon"].centroid.x
                cy = obj["polygon"].centroid.y
                plt.text(cx, cy, obj["id"], fontsize=6, ha="center", va="center")

            # 3. draw generated wall material on top
            for wall in matching_walls:
                plot_polygon(
                    wall["polygon"],
                    fill_color=wall.get("fill", "#ff9900"),
                    edge_color="black",
                    linewidth=2,
                )

            plt.title(
                f"Layer: {layer_name}\n"
                f"{outer['id']} | inside={len(inside)} | walls={len(matching_walls)}"
            )

            plt.axis("equal")
            plt.gca().invert_yaxis()

            out_png = layer_out_dir / f"{i:03d}_{safe_filename(outer['id'])}_with_walls.png"

            plt.savefig(out_png, dpi=150, bbox_inches="tight")
            plt.close()

            print("    Saved:", out_png)