def merge_wall_layers(rect_walls, path_walls):
    merged = {}

    all_layers = set(rect_walls.keys()) | set(path_walls.keys())

    for layer_name in all_layers:
        merged[layer_name] = {}

        merged[layer_name].update(
            rect_walls.get(layer_name, {})
        )

        merged[layer_name].update(
            path_walls.get(layer_name, {})
        )

    return merged