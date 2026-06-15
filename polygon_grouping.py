from shapely.ops import unary_union


SPECIAL_INNER_COLORS = {"#ffffff", "#000000", "#552200"}

BROWN = "#552200"


def object_color(obj):
    fill = obj.get("fill")

    if isinstance(fill, list):
        if not fill:
            return None
        return fill[0].get("color")

    return fill


def add_fill_part(obj, color, polygon):
    obj = normalize_fill(obj)

    obj["fill"].append({
        "color": color,
        "bounds": bounds_dict_from_poly(polygon),
    })

    return obj


def apply_brown_overlays(outer, inside):
    brown_objects = [
        obj for obj in inside
        if object_color(obj) == BROWN
    ]

    non_brown_inside = [
        obj for obj in inside
        if object_color(obj) != BROWN
    ]

    for brown in brown_objects:
        brown_poly = brown["polygon"]

        best_target_index = None
        best_area = 0

        for idx, candidate in enumerate(non_brown_inside):
            inter = brown_poly.intersection(candidate["polygon"])

            if not inter.is_empty and inter.area > best_area:
                best_area = inter.area
                best_target_index = idx

        if best_target_index is not None:
            target = non_brown_inside[best_target_index]
            inter = brown_poly.intersection(target["polygon"])

            non_brown_inside[best_target_index] = add_fill_part(
                target,
                BROWN,
                inter,
            )
        else:
            inter = brown_poly.intersection(outer["polygon"])

            if not inter.is_empty:
                outer = add_fill_part(
                    outer,
                    BROWN,
                    inter,
                )

    return outer, non_brown_inside


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


def normalize_fill(obj, container_fill=None):
    obj = dict(obj)

    fill = obj.get("fill")

    if fill is None and container_fill is not None:
        fill = container_fill

    if isinstance(fill, list):
        obj["fill"] = fill
    else:
        obj["fill"] = [{
            "color": fill,
            "bounds": bounds_dict_from_poly(obj["polygon"]),
        }]

    return obj


def fill_list_from_object(obj):
    obj = normalize_fill(obj)
    return obj["fill"]


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
    all_inner = []

    for outer in outers:
        fills.extend(fill_list_from_object(outer))
        all_inner.extend(outer.get("inner", []))

    seen_inner_ids = set()
    deduped_inner = []

    for inner in all_inner:
        if inner["id"] not in seen_inner_ids:
            seen_inner_ids.add(inner["id"])
            deduped_inner.append(inner)

    merged_outer["fill"] = fills
    merged_outer["inner"] = deduped_inner
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
        true_overlap_ids = set()

        for inner in objects_sorted:
            overlaps = []

            if inner.get("fill") not in SPECIAL_INNER_COLORS:
                continue

            for outer in objects_sorted:
                if inner is outer:
                    continue

                inner_coords = bounds_dict_from_poly(inner["polygon"])
                outer_coords = bounds_dict_from_poly(outer["polygon"])
                if inner["id"] == "rect7" and outer["id"] == "rect11":
                    print("yay")
                if (inner_coords["x1"]>outer_coords["x1"] and inner_coords["x2"]<outer_coords["x2"]) or (inner_coords["y1"]>outer_coords["y1"] and inner_coords["y2"]<outer_coords["y2"]):

                    outer_poly = outer["polygon"]
                    inner_poly = inner["polygon"]

                    if inner_poly.area <= 0 or outer_poly.area <= 0:
                        continue

                    percentage_of_coverage = (
                        inner_poly.intersection(outer_poly).area / inner_poly.area
                    )

                    distance = 100
                    if outer.get("fill") not in SPECIAL_INNER_COLORS and inner.get("fill") == '#ffffff':
                        distance = inner_poly.boundary.distance(outer_poly.boundary)

                    if percentage_of_coverage > 0.1 or distance < 0.2:
                        if "inner" not in outer:
                            outer["inner"] = []

                        outer["inner"].append(inner)
                        overlaps.append(outer)

                if len(overlaps) > 1:
                    true_overlap.append(overlaps)

                    for outer in overlaps:
                        true_overlap_ids.add(outer["id"])

        deduped_true_overlaps = []

        for overlap_group in true_overlap:
            overlap_ids = tuple(sorted(obj["id"] for obj in overlap_group))

            already_exists = False

            for existing_group in deduped_true_overlaps:
                existing_ids = tuple(sorted(obj["id"] for obj in existing_group))

                if overlap_ids == existing_ids:
                    already_exists = True
                    break

            if not already_exists:
                deduped_true_overlaps.append(overlap_group)

        merge = True

        while merge:
            merge = False

            for i in range(len(deduped_true_overlaps)):
                ids_i = {obj["id"] for obj in deduped_true_overlaps[i]}

                for j in range(i + 1, len(deduped_true_overlaps)):
                    ids_j = {obj["id"] for obj in deduped_true_overlaps[j]}

                    if ids_i & ids_j:
                        merged_group = (
                            deduped_true_overlaps[i]
                            + deduped_true_overlaps[j]
                        )

                        seen_ids = set()
                        deduped_merged_group = []

                        for obj in merged_group:
                            if obj["id"] not in seen_ids:
                                seen_ids.add(obj["id"])
                                deduped_merged_group.append(obj)

                        new_array = []

                        for k in range(len(deduped_true_overlaps)):
                            if k != i and k != j:
                                new_array.append(deduped_true_overlaps[k])

                        new_array.append(deduped_merged_group)

                        deduped_true_overlaps = new_array
                        merge = True
                        break

                if merge:
                    break

        for overlap_group in deduped_true_overlaps:
            groups.append(merge_outer_objects(overlap_group))

        for obj in objects_sorted:
            if (
                obj["id"] not in true_overlap_ids
                and obj.get("fill") not in SPECIAL_INNER_COLORS
            ):
                groups.append(normalize_fill(obj))

        for i in range(len(groups)):
            outer = dict(groups[i])
            inside = outer.pop("inner", [])

            outer = normalize_fill(outer)

            normalized_inside = []

            for inner in inside:
                inner = normalize_fill(inner)

                if inner["fill"][0]["color"] == "#ffffff":
                    inner["container_fill"] = outer["fill"]

                normalized_inside.append(inner)

            groups[i] = {
                "outer": outer,
                "inside": normalized_inside,
            }

        grouped_layers[layer_name] = groups

    return grouped_layers


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