from pathlib import Path

from data_receiver import load_svg_layers
from polygon_grouping import group_objects_inside_layers, group_objects_inside_layers_v4
from data_representation import render_grouped_layers
from wall_generation import generate_and_render_walls
from path_generation import get_path_base
from get_touching_points import modify_and_plot_wall_layers
from create_ridges import add_connection_info_to_walls
from merging_path_and_rect import merge_wall_layers
from creating_bottom_holes import generate_wall_graphs_timed
from get_dict_from_csv import get_color_scheme

board_game_name = "Arnak"

SVG_FILE = Path(fr"D:\board_game_insert_code\{board_game_name}.svg")

OUT_DIR = SVG_FILE.parent / f"{board_game_name}_subitems"
WALL_DIR = SVG_FILE.parent / f"{board_game_name}_walls"
PATH_DIR = SVG_FILE.parent / f"{board_game_name}_path_lines"
CSV_FILE = Path(r"D:\board_game_insert_code\Color_scheme.csv")
def main():
    wall_thickness = 5
    laser_width = 0.075
    layers = load_svg_layers(SVG_FILE)

    color_height_dict = get_color_scheme(CSV_FILE, board_game_name)
    grouped_layers = group_objects_inside_layers_v4(layers)
    path_walls = get_path_base(grouped_layers, wall_thickness=wall_thickness)

    rect_walls = generate_and_render_walls(
        grouped_layers,
        WALL_DIR,
        print_coordinates=True,
        render=True,
    )


    rect_walls = modify_and_plot_wall_layers(
        rect_walls,
        wall_width=wall_thickness,
        out_dir=WALL_DIR / "debug_resized_by_parent",
    )

    wall_layers = merge_wall_layers(
        rect_walls,
        path_walls,
    )

    walls_with_ridges = add_connection_info_to_walls(
        wall_layers,
        color_height_dict,
        out_dir=WALL_DIR / "debug_ridges_by_parent",
        render=True,
        wall_width=wall_thickness,
        laser_width=laser_width
    )

    walls = []
    for wall in walls_with_ridges["Layer 1"]["rect51"]:
        walls.append(wall)

    outputs = generate_wall_graphs_timed(
        walls=walls,
        out_dir=WALL_DIR / "holes",
        wall_width=wall_thickness,
        semi_steps_3d=10,
        semi_steps_2d=64,
    )

    print(outputs)
    print("\nDone.")


if __name__ == "__main__":
    main()