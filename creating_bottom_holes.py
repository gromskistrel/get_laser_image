from pathlib import Path

import matplotlib.pyplot as plt
from shapely.geometry import box


def make_rect_hole(wall, position, hole_width=10.0, hole_height=3.0):
    polygon = wall["polygon"]
    minx, miny, maxx, maxy = polygon.bounds

    hole_x1 = (minx + maxx - hole_width) / 2
    hole_x2 = hole_x1 + hole_width

    if position == "middle":
        cy = (miny + maxy) / 2
        hole_y1 = cy - hole_height / 2
        hole_y2 = cy + hole_height / 2

    elif position == "bottom":
        # SVG/image coords: bottom edge is maxy
        hole_y1 = maxy - hole_height
        hole_y2 = maxy

    else:
        raise ValueError("position must be 'middle' or 'bottom'")

    return box(hole_x1, hole_y1, hole_x2, hole_y2)


def plot_wall(wall, out_path=None):
    fig, ax = plt.subplots(figsize=(7, 4))

    geom = wall["polygon"]

    def draw_geom(g):
        if g.geom_type == "Polygon":
            x, y = g.exterior.xy
            ax.fill(
                x,
                y,
                facecolor="black",
                edgecolor="black",
                linewidth=1,
            )

            # interior holes (middle holes only) stay white
            for interior in g.interiors:
                ix, iy = interior.xy
                ax.fill(
                    ix,
                    iy,
                    facecolor="white",
                    edgecolor="white",
                )

        elif g.geom_type == "MultiPolygon":
            for part in g.geoms:
                draw_geom(part)

    draw_geom(geom)

    ax.set_aspect("equal")
    ax.invert_yaxis()
    ax.axis("off")

    if out_path is not None:
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(
            out_path,
            dpi=200,
            bbox_inches="tight",
            pad_inches=0,
            facecolor="white",
        )
        plt.close(fig)
    else:
        plt.show()


def get_bottom_with_holes(
    wall_layers,
    out_dir=None,
    render=True,
    hole_width=10.0,
    hole_height=3.0,
):
    if out_dir is not None:
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

    for layer_name, layer in wall_layers.items():
        for key, walls in layer.items():
            for wall in walls:
                if not wall["id"].endswith("_base"):
                    continue

                original_polygon = wall["polygon"]

                middle_hole = make_rect_hole(
                    wall,
                    position="middle",
                    hole_width=hole_width,
                    hole_height=hole_height,
                )

                bottom_hole = make_rect_hole(
                    wall,
                    position="bottom",
                    hole_width=hole_width,
                    hole_height=hole_height,
                )

                # Important:
                # - middle_hole becomes a true interior hole
                # - bottom_hole cuts through the boundary, so it becomes an open notch
                new_polygon = original_polygon.difference(middle_hole).difference(bottom_hole)

                wall["original_polygon"] = original_polygon
                wall["middle_hole"] = middle_hole
                wall["bottom_hole"] = bottom_hole
                wall["holes"] = [middle_hole, bottom_hole]
                wall["polygon"] = new_polygon

                if "bounds" in wall:
                    minx, miny, maxx, maxy = new_polygon.bounds
                    wall["bounds"].update({
                        "polygon": new_polygon,
                        "x1": minx,
                        "y1": miny,
                        "x2": maxx,
                        "y2": maxy,
                        "width": maxx - minx,
                        "height": maxy - miny,
                    })

                print(f"cut middle + bottom holes in {wall['id']}")

                if render:
                    plot_path = None
                    if out_dir is not None:
                        plot_path = out_dir / layer_name / f"{wall['id']}_holes.png"

                    plot_wall(wall, out_path=plot_path)

    return wall_layers

