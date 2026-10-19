
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
                print("yay")
    return wall_layers








