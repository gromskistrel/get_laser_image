def increase_size_by_laser_width(wall_layers):
    for layer in wall_layers.values():
        for key, item in layer.items():
            if 'rect' in key:
                print("rect")
            elif "path" in key:
                print(item)