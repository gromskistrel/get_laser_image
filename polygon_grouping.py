from shapely.ops import unary_union


def bounds_dict_from_poly(poly):
    minx, miny, maxx, maxy = poly.bounds

    return {
        "x1": minx,
        "y1": miny,
        "x2": maxx,
        "y2": maxy,
        "width": maxx - minx,
        "height": maxy - miny,
    }

def group_objects_inside_layers(layers, tolerance=0.5):
    grouped_layers = {}

    for layer_name, objects in layers.items():
        objects_sorted = sorted(objects, key=lambda o: o["area"], reverse=True)
        groups = []

        for outer in objects_sorted:
            inside = []

            for inner in objects_sorted:
                if inner is outer:
                    continue

                if inner["area"] >= outer["area"]:
                    continue

                outer_poly = outer["polygon"].buffer(tolerance)
                inner_point = inner["polygon"].representative_point()

                if outer_poly.covers(inner_point):
                    inside.append(inner)

            if inside:
                groups.append({
                    "outer": outer,
                    "inside": inside,
                })

        grouped_layers[layer_name] = groups

    return grouped_layers

def fill_list_from_object(obj):
    fill = obj.get("fill")

    if isinstance(fill, list):
        return fill

    return [{
        "color": fill,
        "bounds": bounds_dict_from_poly(obj["polygon"]),
    }]

def merge_outer_objects(outers):
    merged_poly = unary_union([
        outer["polygon"]
        for outer in outers
    ]).envelope

    merged_outer = dict(outers[0])

    merged_outer["polygon"] = merged_poly
    merged_outer["bounds"] = merged_poly.bounds
    merged_outer["area"] = merged_poly.area

    fills = []

    for outer in outers:
        fills.extend(fill_list_from_object(outer))

    merged_outer["fill"] = fills
    merged_outer["id"] = (
        f"{'_'.join(outer['id'] for outer in outers)}_merged_base"
    )

    return merged_outer


def group_objects_inside_layers_v4(layers, tolerance=0.5):
    grouped_layers = {}

    for layer_name, objects in layers.items():
        objects_sorted = sorted(objects, key=lambda o: o["area"], reverse=True)
        groups = []
        true_overlap = []
        # Original grouping logic
        true_overlap_ids = []
        for inner_index, inner in enumerate(objects_sorted):
            overlaps = []
            for outer_index, outer in enumerate(objects_sorted):
                if inner is outer:
                    continue

                if inner["fill"] == '#ffffff' or inner["fill"] == '#000000' or inner["fill"] == '#552200':
                    outer_poly = outer["polygon"]
                    inner_poly = inner["polygon"]

                    if inner_poly.area > 0 and outer_poly.area > 0:
                        percentage_of_coverage = (inner_poly.intersection(outer_poly).area)/inner_poly.area
                        if percentage_of_coverage > 0.1:
                            if "inner" in outer:
                                outer["inner"].append(inner)
                            else:
                                outer["inner"] = [inner]
                            overlaps.append(outer)
            if len(overlaps) > 1:
                true_overlap.append(overlaps)
                for i in range(len(overlaps)):
                    true_overlap_ids.append(overlaps[i]["id"])
        merged = []
        for i in range(len(true_overlap)):
            merged.append(merge_outer_objects(true_overlap[i]))

        for i in range(len(objects_sorted)):
            if objects_sorted[i]["id"] not in true_overlap_ids and objects_sorted[i]["fill"] != '#ffffff' and objects_sorted[i]["fill"] != '#000000' and objects_sorted[i]["fill"] != '#552200':
                new_group_entry = objects_sorted[i]
                new_group_entry["fill"] = fill_list_from_object(new_group_entry)
                groups.append(new_group_entry)


        for i in range(len(groups)):
            outer = dict(groups[i])
            outer.pop("inner", None)

            groups[i] = {
                "outer": outer,
                "inside": groups[i]["inner"],
            }

        grouped_layers[layer_name] = groups

    return grouped_layers


