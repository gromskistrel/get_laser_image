from shapely.affinity import translate
from shapely.geometry import Polygon, Point


def get_laser_width_correction(wall_layers, laser_width, wall_width):
    index = 0
    tolerance = 1e-3
    for layer_name, walls in wall_layers.items():
        for key, polygons in walls.items():
            for i in range(len(polygons)):
                if "black_holes" in polygons[i]:
                    for j, hole in enumerate(polygons[i]["black_holes"]):
                        if hole[1] == "right":
                            polygons[i]["black_holes"][j] = [translate(hole[0], xoff=-laser_width/2), hole[1]]
                        if hole[1] == "left":
                            polygons[i]["black_holes"][j] = [translate(hole[0], xoff=laser_width / 2), hole[1]]
                        if hole[1] == "up":
                            polygons[i]["black_holes"][j] = [translate(hole[0], yoff=-laser_width / 2), hole[1]]
                        if hole[1] == "down":
                            polygons[i]["black_holes"][j] = [translate(hole[0], xoff=laser_width / 2), hole[1]]

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
    return wall_layers


def get_wall_numbering(wall_layers):
    number = 1
    size = 3
    for layer_name, walls in wall_layers.items():
        for key, polygons in walls.items():
            for i, polygon in enumerate(polygons):
                left_bottom_point = (0, 0)
                if polygon["type"] == "base":
                    for j in range(len(polygon['3D_cuboids'])-1):
                        if polygon["3D_cuboids"][j]["y1"] == polygon["3D_cuboids"][j+1]["y1"] and polygon["3D_cuboids"][j]["y2"] == polygon["3D_cuboids"][j+1]["y2"]:
                            left_bottom_point = ((polygon["3D_cuboids"][j]["x2"]+polygon["3D_cuboids"][j+1]["x1"])/2-size/2, (polygon["3D_cuboids"][j]["y1"]+polygon["3D_cuboids"][j]["y2"])/2-size/2)
                            points = [Point(left_bottom_point[0], left_bottom_point[1]), Point(left_bottom_point[0], left_bottom_point[1]+size), Point(left_bottom_point[0]+size, left_bottom_point[1]), Point(left_bottom_point[0]+size, left_bottom_point[1]+size)]
                            if "black_holes" not in polygons[i]:
                                break
                            else:
                                contains = False
                                for black_hole in polygons[i]["black_holes"]:
                                    for point in points:
                                        if black_hole[0].contains(point):
                                            contains  = True
                                            break
                                    if contains == True:
                                        break
                            if contains == False:
                                break
                else:
                    # same 2D plane as get_2d_projection: vertical -> YZ, horizontal -> XZ
                    h1, h2 = ("y1", "y2") if polygon.get("direction") == "vertical" else ("x1", "x2")
                    for j in range(len(polygon['3D_cuboids'])):
                        cuboid = polygon["3D_cuboids"][j]
                        if cuboid["hole"] == 0 and cuboid["main"] is True:
                            left_bottom_point = ((cuboid[h2]+cuboid[h1])/2-size/2, (cuboid["z2"]+cuboid["z1"])/2-size/2)
                polygons[i]["written_number"] = {"point": left_bottom_point, "number": number, "size": size}
                number += 1

    return wall_layers







