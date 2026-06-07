import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from shapely.geometry import box
from shapely.ops import unary_union

def turn_between(edge1, edge2):
    x1 = edge1["bounds"]["x1"]
    y1 = edge1["bounds"]["y1"]
    x2 = edge1["bounds"]["x2"]
    y2 = edge1["bounds"]["y2"]
    x3 = edge2["bounds"]["x1"]
    y3 = edge2["bounds"]["y1"]
    x4 = edge2["bounds"]["x2"]
    y4 = edge2["bounds"]["y2"]

    v1 = (x2 - x1, y2 - y1)
    v2 = (x4 - x3, y4 - y3)

    cross = v1[0] * v2[1] - v1[1] * v2[0]

    if cross > 0:
        return 1
    elif cross < 0:
        return -1
    else:
        return 0

def turn_correct(line):
    x1 = line["bounds"]["x1"]
    y1 = line["bounds"]["y1"]
    x2 = line["bounds"]["x2"]
    y2 = line["bounds"]["y2"]
    if x1>x2:
        line["bounds"]["x1"] = x2
        line["bounds"]["x2"] = x1
    elif y1>y2:
        line["bounds"]["y1"] = y2
        line["bounds"]["y2"] = y1
    return line

def wall_to_polygon(wall):
    rectangles = []


    x_min = min(wall["bounds"]["x1"], wall["bounds"]["x2"])
    x_max = max(wall["bounds"]["x1"], wall["bounds"]["x2"])
    y_min = min(wall["bounds"]["y1"], wall["bounds"]["y2"])
    y_max = max(wall["bounds"]["y1"], wall["bounds"]["y2"])

    rectangles.append(box(x_min, y_min, x_max, y_max))

    polygon = unary_union(rectangles)

    return polygon

def get_path_base(layers, wall_thickness):
    returned = {}
    for layer in layers.items():
        layer_items = {}
        for item in layer[1]:
            if "path" in item["outer"]["id"]:
                coords = list(item["outer"]["polygon"].exterior.coords)

                for i in range(len(coords)-1):
                    if coords[i] == (item["outer"]["bounds"][0], item["outer"]["bounds"][1]):
                        if coords[i+1][0]>coords[i][0]:
                            coords = coords[i::]+coords[:i:]
                        else:
                            coords = coords[i::-1]+coords[:i:-1]



                start = coords[0]
                lines = []
                position = "horizontal" if start[1] == coords[1][1] else "vertical"
                for i in range(len(coords)+1):
                    current_i = i%len(coords)
                    next_i = (i+1)%len(coords)
                    if position == "horizontal":
                        if coords[current_i][1] == coords[next_i][1]:
                            continue
                        else:
                            position = "vertical"
                            lines.append({"id": f"{item["outer"]["id"]}_outer_wall_{i}", "parent_id": item["outer"]["id"], "source_id": item["outer"]["id"],"position": position, "bounds":{"x1":start[0], "y1":start[1], "x2":coords[current_i][0], "y2":coords[current_i][1]}})
                            start = coords[current_i]
                    else:
                        if coords[current_i][0] == coords[next_i][0]:
                            continue
                        else:
                            position = "horizontal"
                            lines.append({"id": f"{item["outer"]["id"]}_outer_wall_{i}", "parent_id": item["outer"]["id"], "source_id": item["outer"]["id"],"position": position, "bounds":{"x1":start[0], "y1":start[1], "x2":coords[current_i][0], "y2":coords[current_i][1]}})
                            start = coords[current_i]


                for i in range(len(lines)):
                    next_i = (i + 1) % len(lines)

                    lines[i]["angle"]= turn_between(lines[i], lines[next_i])


                """directions = ["right", "down", "left", "up"]"""

                for i in range(len(lines)):
                    if i == 0:
                        lines[i]["direction"] = 1
                    else:
                        lines[i]["direction"] = lines[i-1]["direction"]+lines[i-1]["angle"]
                    if lines[i]["direction"]%4 == 1:
                        lines[i]["bounds"]["y2"] = lines[i]["bounds"]["y2"] + wall_thickness
                        if lines[i]["angle"] == 1:
                            lines[i]["bounds"]["x2"] = lines[i]["bounds"]["x2"] - wall_thickness
                        else:
                            lines[i]["bounds"]["x2"] = lines[i]["bounds"]["x2"] + wall_thickness
                    elif lines[i]["direction"]%4 == 2:
                        lines[i]["bounds"]["x1"] = lines[i]["bounds"]["x1"] - wall_thickness
                        if lines[i]["angle"] == 1:
                            lines[i]["bounds"]["y2"] = lines[i]["bounds"]["y2"] - wall_thickness
                        else:
                            lines[i]["bounds"]["y2"] = lines[i]["bounds"]["y2"] + wall_thickness
                    elif lines[i]["direction"]%4 == 3:
                        lines[i]["bounds"]["y1"] = lines[i]["bounds"]["y1"] - wall_thickness
                        if lines[i]["angle"] == 1:
                            lines[i]["bounds"]["x2"] = lines[i]["bounds"]["x2"] + wall_thickness
                        else:
                            lines[i]["bounds"]["x2"] = lines[i]["bounds"]["x2"] - wall_thickness
                    else:
                        lines[i]["bounds"]["x2"] = lines[i]["bounds"]["x2"] + wall_thickness
                        if lines[i]["angle"] == 1:
                            lines[i]["bounds"]["y2"] = lines[i]["bounds"]["y2"] + wall_thickness
                        else:
                            lines[i]["bounds"]["y2"] = lines[i]["bounds"]["y2"] - wall_thickness

                    lines[i] = turn_correct(lines[i])
                    lines[i]["polygon"] = wall_to_polygon(lines[i])
                    lines[i]["type"] = "outer_wall"
                    lines[i]["fill"] = item["outer"]["fill"]
                    lines[i]["bounds"]["height"] = abs(lines[i]["bounds"]["y2"] - lines[i]["bounds"]["y1"])
                    lines[i]["bounds"]["width"] = abs(lines[i]["bounds"]["x2"] - lines[i]["bounds"]["x1"])
                base_line = item["outer"].copy()
                original_id = base_line["id"]
                base_line["id"] = f"{original_id}_base"
                base_line["type"] = "base"
                base_line["source_id"] = original_id
                base_line["parent_id"] = original_id
                base_line["bounds"] = {"x1": min(base_line["bounds"][0], base_line["bounds"][2]), "x2": max(base_line["bounds"][0], base_line["bounds"][2]), "y1": min(base_line["bounds"][1], base_line["bounds"][3]), "y2": max(base_line["bounds"][1], base_line["bounds"][3]),
                                                                                                        "width":abs(base_line["bounds"][0]- base_line["bounds"][2]), "height": abs(base_line["bounds"][1] - base_line["bounds"][3])}
                lines.append(base_line)
                layer_items[original_id] = lines
        returned[layer[0]] = layer_items
    return returned


