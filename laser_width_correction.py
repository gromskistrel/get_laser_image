from shapely.affinity import translate
from shapely.geometry import Polygon, Point, LineString, box
from shapely.ops import unary_union


def get_laser_width_correction(wall_layers, laser_width, wall_width):
    index = 0
    tolerance = 1e-3
    for layer_name, walls in wall_layers.items():
        for key, polygons in walls.items():
            for i in range(len(polygons)):
                polygons[i]["index"] = index
                index += 1
                main_cuboids = []
                for j in range(len(polygons[i]["3D_cuboids"])):
                    x1, x2, y1, y2, z1, z2 = polygons[i]["3D_cuboids"][j]["x1"], polygons[i]["3D_cuboids"][j]["x2"], polygons[i]["3D_cuboids"][j]["y1"], polygons[i]["3D_cuboids"][j]["y2"], polygons[i]["3D_cuboids"][j]["z1"], polygons[i]["3D_cuboids"][j]["z2"]
                    if x1>x2:
                        polygons[i]["3D_cuboids"][j]["x1"] = x2
                        polygons[i]["3D_cuboids"][j]["x2"] = x1
                    if y1>y2:
                        polygons[i]["3D_cuboids"][j]["y1"] = y2
                        polygons[i]["3D_cuboids"][j]["y2"] = y1
                    if z1 > z2:
                        polygons[i]["3D_cuboids"][j]["z1"] = z2
                        polygons[i]["3D_cuboids"][j]["z2"] = z1
                initial = {"x1": polygons[i]['3D_cuboids'][0]["x1"], "x2": polygons[i]['3D_cuboids'][0]["x2"], "y1": polygons[i]['3D_cuboids'][0]["y1"], "y2": polygons[i]['3D_cuboids'][0]["y2"], "z1": polygons[i]['3D_cuboids'][0]["z1"], "z2": polygons[i]['3D_cuboids'][0]["z2"]}
                difference = {"x1": 0, "x2": 0, "y1": 0, "y2": 0, "z1": 0, "z2": 0}
                for cuboid in polygons[i]['3D_cuboids']:
                    for key in difference.keys():
                        difference[key] += cuboid[key]-initial[key]
                    if cuboid["main"] is True:
                        main_cuboids.append(cuboid)
                if difference["x1"] < tolerance and difference["x2"] < tolerance:
                    axis = ["y1", "y2", "z1", "z2"]
                elif difference["y1"] < tolerance and difference["y2"] < tolerance:
                    axis = ["x1", "x2", "z1", "z2"]
                else:
                    axis = ["x1", "x2", "y1", "y2"]
                left = main_cuboids[0][axis[0]]
                right = main_cuboids[0][axis[1]]
                bottom = main_cuboids[0][axis[2]]
                top = main_cuboids[0][axis[3]]
                if len(main_cuboids) > 1:
                    for k in range(len(main_cuboids)):
                        if main_cuboids[k][axis[2]] <= bottom:
                            bottom = main_cuboids[k][axis[2]]
                        if main_cuboids[k][axis[3]] >= top:
                            top = main_cuboids[k][axis[3]]
                        if main_cuboids[k][axis[0]] <= left:
                            left = main_cuboids[k][axis[0]]
                        if main_cuboids[k][axis[1]] >= right:
                            right = main_cuboids[k][axis[1]]
                for j in range(len(polygons[i]['3D_cuboids'])):
                    if polygons[i]["3D_cuboids"][j]["main"] is False:
                        polygons[i]["3D_cuboids"][j]["contained_within"] = -1
                        if len(main_cuboids) > 0:
                            for index, main_cuboid in enumerate(main_cuboids):
                                if (polygons[i]['3D_cuboids'][j][axis[0]] > main_cuboid[axis[0]]-tolerance
                                    and polygons[i]['3D_cuboids'][j][axis[1]] < main_cuboid[axis[1]]+tolerance
                                    and polygons[i]['3D_cuboids'][j][axis[2]] > main_cuboid[axis[2]]-tolerance
                                    and polygons[i]['3D_cuboids'][j][axis[3]] < main_cuboid[axis[3]]+tolerance):
                                        polygons[i]["3D_cuboids"][j]["contained_within"] = index

                for j in range(len(polygons[i]['3D_cuboids'])):
                    cuboid = polygons[i]["3D_cuboids"][j]
                    if cuboid["main"] is False:
                        if cuboid["hole"] == 1:
                            # left go left
                            if main_cuboids[cuboid["contained_within"]][axis[0]]-tolerance<cuboid[axis[0]]<main_cuboids[cuboid["contained_within"]][axis[0]]+tolerance:
                                if cuboid[axis[3]] - cuboid[axis[2]] != wall_width:
                                    polygons[i]["3D_cuboids"][j][axis[0]] -= laser_width/2
                                    polygons[i]["3D_cuboids"][j][axis[1]] -= laser_width/2
                            # right go right
                            elif main_cuboids[cuboid["contained_within"]][axis[1]]-tolerance<cuboid[axis[1]]<main_cuboids[cuboid["contained_within"]][axis[1]]+tolerance:
                                if cuboid[axis[3]] - cuboid[axis[2]] != wall_width:
                                    polygons[i]["3D_cuboids"][j][axis[0]] += laser_width/2
                                    polygons[i]["3D_cuboids"][j][axis[1]] += laser_width/2
                            # top go top
                            elif main_cuboids[cuboid["contained_within"]][axis[2]]-tolerance<cuboid[axis[2]]<main_cuboids[cuboid["contained_within"]][axis[2]]+tolerance:
                                if cuboid[axis[1]]-cuboid[axis[0]] != wall_width:
                                    polygons[i]["3D_cuboids"][j][axis[2]] -= laser_width/2
                                    polygons[i]["3D_cuboids"][j][axis[3]] -= laser_width/2
                            # bottom go bottom
                            elif main_cuboids[cuboid["contained_within"]][axis[3]]-tolerance<cuboid[axis[3]]<main_cuboids[cuboid["contained_within"]][axis[3]]+tolerance:
                                if cuboid[axis[1]] - cuboid[axis[0]] != wall_width:
                                    polygons[i]["3D_cuboids"][j][axis[2]] += laser_width/2
                                    polygons[i]["3D_cuboids"][j][axis[3]] += laser_width/2

                            if bottom - tolerance < cuboid[axis[2]] < bottom + tolerance:
                                polygons[i]["3D_cuboids"][j][axis[2]] -= laser_width / 2
                            if top - tolerance < cuboid[axis[3]] < top + tolerance:
                                polygons[i]["3D_cuboids"][j][axis[3]] += laser_width / 2
                            if left - tolerance < cuboid[axis[0]] < left + tolerance:
                                polygons[i]["3D_cuboids"][j][axis[0]] -= laser_width / 2
                            if right - tolerance < cuboid[axis[1]] < right + tolerance:
                                polygons[i]["3D_cuboids"][j][axis[1]] += laser_width / 2

                        else:
                            # left go left
                            if main_cuboids[cuboid["contained_within"]][axis[0]] - tolerance < cuboid[axis[1]] < main_cuboids[cuboid["contained_within"]][axis[0]] + tolerance:
                                polygons[i]["3D_cuboids"][j][axis[0]] -= laser_width / 2
                                polygons[i]["3D_cuboids"][j][axis[1]] -= laser_width / 2
                            # right go right
                            elif main_cuboids[cuboid["contained_within"]][axis[1]] - tolerance < cuboid[axis[0]] < main_cuboids[cuboid["contained_within"]][axis[1]] + tolerance:
                                polygons[i]["3D_cuboids"][j][axis[0]] += laser_width / 2
                                polygons[i]["3D_cuboids"][j][axis[1]] += laser_width / 2
                            # top go top
                            elif main_cuboids[cuboid["contained_within"]][axis[2]] - tolerance < cuboid[axis[3]] < main_cuboids[cuboid["contained_within"]][axis[2]] + tolerance:
                                polygons[i]["3D_cuboids"][j][axis[2]] -= laser_width / 2
                                polygons[i]["3D_cuboids"][j][axis[3]] -= laser_width / 2
                            # bottom go bottom
                            elif main_cuboids[cuboid["contained_within"]][axis[3]] - tolerance < cuboid[axis[2]] < main_cuboids[cuboid["contained_within"]][axis[3]] + tolerance:
                                polygons[i]["3D_cuboids"][j][axis[2]] += laser_width / 2
                                polygons[i]["3D_cuboids"][j][axis[3]] += laser_width / 2

                            if bottom - tolerance < cuboid[axis[2]] < bottom + tolerance:
                                polygons[i]["3D_cuboids"][j][axis[2]] -= laser_width / 2
                            if top - tolerance < cuboid[axis[3]] < top + tolerance:
                                polygons[i]["3D_cuboids"][j][axis[3]] += laser_width / 2
                            if left - tolerance < cuboid[axis[0]] < left + tolerance:
                                polygons[i]["3D_cuboids"][j][axis[0]] -= laser_width / 2
                            if right - tolerance < cuboid[axis[1]] < right + tolerance:
                                polygons[i]["3D_cuboids"][j][axis[1]] += laser_width / 2

                for j in range(len(polygons[i]['3D_cuboids'])):
                    cuboid = polygons[i]["3D_cuboids"][j]
                    if cuboid["main"] is True:
                        polygons[i]["3D_cuboids"][j][axis[0]] -= laser_width / 2
                        polygons[i]["3D_cuboids"][j][axis[1]] += laser_width / 2
                        polygons[i]["3D_cuboids"][j][axis[2]] -= laser_width / 2
                        polygons[i]["3D_cuboids"][j][axis[3]] += laser_width / 2

                # black holes are in the XY plane, so they need the main bounds after the growth above
                if "black_holes" in polygons[i] and main_cuboids:
                    main_bounds = (min(c["x1"] for c in main_cuboids), min(c["y1"] for c in main_cuboids),
                                   max(c["x2"] for c in main_cuboids), max(c["y2"] for c in main_cuboids))
                    for j, hole in enumerate(polygons[i]["black_holes"]):
                        polygons[i]["black_holes"][j] = [_correct_black_hole(hole[0], hole[1], main_bounds, laser_width), hole[1]]
    return wall_layers


def _correct_black_hole(hole, sides, main_bounds, laser_width):
    """Move a black hole inward by laser_width and stretch its open sides past the main edge.

    sides is e.g. "right" or "right, bottom"; top is the min-y edge, bottom the max-y edge.
    Without the stretch a thin strip of material is left between the hole and the grown main edge.
    """
    sides = str(sides)
    main_x1, main_y1, main_x2, main_y2 = main_bounds
    is_right, is_left = "right" in sides, "left" in sides
    is_top, is_bottom = "top" in sides or "up" in sides, "bottom" in sides or "down" in sides
    xoff = (laser_width if is_left else 0.0) - (laser_width if is_right else 0.0)
    yoff = (laser_width if is_top else 0.0) - (laser_width if is_bottom else 0.0)
    hole = translate(hole, xoff=xoff, yoff=yoff)

    # beyond the main edge on each open side; a corner hole's boxes run to the corner so they meet
    out_x1, out_y1 = main_x1 - laser_width, main_y1 - laser_width
    out_x2, out_y2 = main_x2 + laser_width, main_y2 + laser_width

    eps = 1e-4
    hx1, hy1, hx2, hy2 = hole.bounds
    extensions = []
    if is_right or is_left:
        edge_x = hx2 - eps if is_right else hx1 + eps
        y1, y2 = _extent_along_line(hole, ((edge_x, hy1 - 1), (edge_x, hy2 + 1)), 1)
        y1 = out_y1 if is_top else y1
        y2 = out_y2 if is_bottom else y2
        extensions.append(box(edge_x, y1, out_x2, y2) if is_right else box(out_x1, y1, edge_x, y2))
    if is_top or is_bottom:
        edge_y = hy1 + eps if is_top else hy2 - eps
        x1, x2 = _extent_along_line(hole, ((hx1 - 1, edge_y), (hx2 + 1, edge_y)), 0)
        x1 = out_x1 if is_left else x1
        x2 = out_x2 if is_right else x2
        extensions.append(box(x1, out_y1, x2, edge_y) if is_top else box(x1, edge_y, x2, out_y2))
    if extensions:
        hole = unary_union([hole] + extensions)
    return hole


def _extent_along_line(hole, line, coordinate):
    """Return (min, max) of the hole's cross-section along a line; coordinate 0 = x, 1 = y."""
    bounds = hole.intersection(LineString(line)).bounds
    return bounds[coordinate], bounds[coordinate + 2]


def get_wall_numbering(wall_layers, wall_width):
    tolerance = 1e-3
    number = 1
    size = 3
    for layer_name, walls in wall_layers.items():
        for key, polygons in walls.items():
            for i, polygon in enumerate(polygons):
                left_bottom_point = (0, 0)
                writing_direction = "horizontal"
                if polygon["type"] == "base":
                    # case 1: between two cuboids in a horizontal row
                    found = False
                    for j in range(len(polygon['3D_cuboids'])-1):
                        cuboid = polygon["3D_cuboids"][j]
                        next_cuboid = polygon["3D_cuboids"][j+1]
                        if abs(cuboid["y1"]-next_cuboid["y1"]) < tolerance and abs(cuboid["y2"]-next_cuboid["y2"]) < tolerance:
                            point = ((cuboid["x2"]+next_cuboid["x1"])/2-size/2, (cuboid["y1"]+cuboid["y2"])/2-size/2)
                            points = [Point(point[0], point[1]), Point(point[0], point[1]+size), Point(point[0]+size, point[1]), Point(point[0]+size, point[1]+size)]
                            contains = False
                            for black_hole in polygon.get("black_holes", []):
                                for p in points:
                                    if black_hole[0].contains(p):
                                        contains = True
                                        break
                                if contains == True:
                                    break
                            if contains == False:
                                left_bottom_point = point
                                writing_direction = "horizontal"
                                found = True
                                break

                    # case 2: nothing found, so between two cuboids in a vertical column
                    if found == False:
                        for j in range(len(polygon['3D_cuboids'])-1):
                            cuboid = polygon["3D_cuboids"][j]
                            next_cuboid = polygon["3D_cuboids"][j+1]
                            if abs(cuboid["x1"]-next_cuboid["x1"]) < tolerance and abs(cuboid["x2"]-next_cuboid["x2"]) < tolerance:
                                point = ((cuboid["x1"]+cuboid["x2"])/2-size/2, (cuboid["y2"]+next_cuboid["y1"])/2-size/2)
                                points = [Point(point[0], point[1]), Point(point[0], point[1]+size), Point(point[0]+size, point[1]), Point(point[0]+size, point[1]+size)]
                                contains = False
                                for black_hole in polygon.get("black_holes", []):
                                    for p in points:
                                        if black_hole[0].contains(p):
                                            contains = True
                                            break
                                    if contains == True:
                                        break
                                if contains == False:
                                    left_bottom_point = point
                                    writing_direction = "vertical"
                                    found = True
                                    break

                    # case 3: still nothing found, so put it in the center at the bottom of the main cuboid
                    # (bottom = max y, as in the SVG), past the wall_width deep bottom notches plus a gap of size
                    if found == False:
                        for cuboid in polygon["3D_cuboids"]:
                            if cuboid["main"] is True:
                                left_bottom_point = ((cuboid["x1"]+cuboid["x2"])/2-size/2, cuboid["y2"]-wall_width-2*size)
                                writing_direction = "horizontal"
                                found = True
                                break

                else:
                    # same 2D plane as get_2d_projection: vertical -> YZ, horizontal -> XZ
                    h1, h2 = ("y1", "y2") if polygon.get("direction") == "vertical" else ("x1", "x2")
                    for j in range(len(polygon['3D_cuboids'])):
                        cuboid = polygon["3D_cuboids"][j]
                        if cuboid["hole"] == 0 and cuboid["main"] is False:
                            left_bottom_point = ((cuboid[h2]+cuboid[h1])/2-size/2, (cuboid["z2"]+cuboid["z1"])/2-size/2)
                            if wall_width-tolerance<cuboid["y2"]-cuboid["y1"]<wall_width+tolerance:
                                writing_direction = "horizontal"
                            else:
                                writing_direction = "vertical"
                polygons[i]["written_number"] = {"point": left_bottom_point, "number": number, "size": size, "direction": writing_direction}
            number += 1

    return wall_layers


def get_base_texts(wall_layers, svg_texts):
    """Put every svg text into the base whose main cuboid covers the text's first line.

    Bases of the same layer are checked first, then bases of all other layers.
    The texts are stored in base["texts"]; texts that are not on any base are printed.
    """
    for layer_name, texts in svg_texts.items():
        for text in texts:
            x, y = text["lines"][0]["x"], text["lines"][0]["y"]
            layer_order = [layer_name] + [name for name in wall_layers.keys() if name != layer_name]
            found = False
            for wall_layer_name in layer_order:
                if wall_layer_name not in wall_layers:
                    continue
                for key, polygons in wall_layers[wall_layer_name].items():
                    for i, polygon in enumerate(polygons):
                        if polygon["type"] != "base":
                            continue
                        for cuboid in polygon["3D_cuboids"]:
                            if cuboid["main"] is True and cuboid["x1"] <= x <= cuboid["x2"] and cuboid["y1"] <= y <= cuboid["y2"]:
                                if "texts" not in polygons[i]:
                                    polygons[i]["texts"] = []
                                polygons[i]["texts"].append(text)
                                found = True
                                break
                        if found == True:
                            break
                    if found == True:
                        break
                if found == True:
                    break
            if found == False:
                print(f"Text {text['id']} ({text['lines'][0]['text']!r}) in {layer_name} is not on any base")

    return wall_layers







