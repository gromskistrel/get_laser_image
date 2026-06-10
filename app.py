from pathlib import Path

from data_receiver import load_svg_layers
from polygon_grouping import group_objects_inside_layers, group_objects_inside_layers_v4
from data_representation import render_grouped_layers
from wall_generation import generate_and_render_walls
from path_generation import get_path_base
from get_touching_points import modify_and_plot_wall_layers
from create_ridges import add_connection_info_to_walls
from merging_path_and_rect import merge_wall_layers


board_game_name = "Arnak"

SVG_FILE = Path(fr"D:\board_game_insert_code\{board_game_name}.svg")

OUT_DIR = SVG_FILE.parent / f"{board_game_name}_subitems"
WALL_DIR = SVG_FILE.parent / f"{board_game_name}_walls"
PATH_DIR = SVG_FILE.parent / f"{board_game_name}_path_lines"


def main():
    layers = load_svg_layers(SVG_FILE)

    """render_grouped_layers(
        grouped_layers,
        OUT_DIR,
    )"""
    #grouped = group_objects_inside_layers_v3(layers, tolerance=0.5)
    grouped_layers = group_objects_inside_layers_v4(layers)
    path_walls = get_path_base(grouped_layers, wall_thickness = 4)

    rect_walls = generate_and_render_walls(
        grouped_layers,
        WALL_DIR,
        print_coordinates=True,
        render=True,
    )


    rect_walls = modify_and_plot_wall_layers(
        rect_walls,
        wall_width=3,
        out_dir=WALL_DIR / "debug_resized_by_parent",
    )

    wall_layers = merge_wall_layers(
        rect_walls,
        path_walls,
    )

    walls_with_ridges = add_connection_info_to_walls(
        wall_layers["Layer 1"],
        out_dir=WALL_DIR / "debug_ridges_by_parent",
    )

    print("\nDone.")


if __name__ == "__main__":
    main()