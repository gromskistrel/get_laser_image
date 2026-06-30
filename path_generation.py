import copy

from shapely.geometry import box


def update_bounds_size(bounds):
    bounds["length"] = abs(bounds["x2"] - bounds["x1"])
    bounds["width"] = abs(bounds["y2"] - bounds["y1"])
    return bounds


def polygon_from_bounds(bounds):
    return box(
        bounds["x1"],
        bounds["y1"],
        bounds["x2"],
        bounds["y2"],
    )


def normalize_black_wall(black_wall):
    black_wall = copy.deepcopy(black_wall)

    if isinstance(black_wall["bounds"], tuple):
        x1, y1, x2, y2 = black_wall["bounds"]
        black_wall["bounds"] = {
            "x1": min(x1, x2),
            "y1": min(y1, y2),
            "x2": max(x1, x2),
            "y2": max(y1, y2),
        }

    update_bounds_size(black_wall["bounds"])

    if black_wall.get("fill"):
        black_wall["fill"][0]["bounds"] = copy.deepcopy(black_wall["bounds"])

    black_wall["polygon"] = polygon_from_bounds(black_wall["bounds"])

    return black_wall


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
    if cross < 0:
        return -1

    return 0


def turn_correct(line):
    b = line["bounds"]

    x1, x2 = b["x1"], b["x2"]
    y1, y2 = b["y1"], b["y2"]

    b["x1"] = min(x1, x2)
    b["x2"] = max(x1, x2)
    b["y1"] = min(y1, y2)
    b["y2"] = max(y1, y2)

    update_bounds_size(b)

    return line


def wall_to_polygon(wall):
    return polygon_from_bounds(wall["bounds"])


def sync_fill_bounds_to_line(fill_part, line):
    fill_part = copy.deepcopy(fill_part)

    b = fill_part["bounds"]
    lb = line["bounds"]

    is_horizontal = lb["length"] > lb["width"]

    if is_horizontal:
        b["x1"] = max(b["x1"], lb["x1"])
        b["x2"] = min(b["x2"], lb["x2"])
        b["y1"] = lb["y1"]
        b["y2"] = lb["y2"]
    else:
        b["y1"] = max(b["y1"], lb["y1"])
        b["y2"] = min(b["y2"], lb["y2"])
        b["x1"] = lb["x1"]
        b["x2"] = lb["x2"]

    update_bounds_size(b)

    return fill_part


def insert_black_wall_into_line_fill(line, black_wall):
    if not line.get("fill"):
        return line

    line = copy.deepcopy(line)
    black_wall = normalize_black_wall(black_wall)

    is_horizontal = line["bounds"]["length"] > line["bounds"]["width"]

    if is_horizontal:
        start_key = "x1"
        end_key = "x2"

        black_wall["bounds"]["y1"] = line["bounds"]["y1"]
        black_wall["bounds"]["y2"] = line["bounds"]["y2"]
    else:
        start_key = "y1"
        end_key = "y2"

        black_wall["bounds"]["x1"] = line["bounds"]["x1"]
        black_wall["bounds"]["x2"] = line["bounds"]["x2"]

    update_bounds_size(black_wall["bounds"])

    black_start = black_wall["bounds"][start_key]
    black_end = black_wall["bounds"][end_key]

    line["fill"] = [
        sync_fill_bounds_to_line(fill_part, line)
        for fill_part in line["fill"]
    ]

    line["fill"] = sorted(
        line["fill"],
        key=lambda fill_part: fill_part["bounds"][start_key],
    )

    new_fill = []

    for fill_part in line["fill"]:
        part_start = fill_part["bounds"][start_key]
        part_end = fill_part["bounds"][end_key]

        if black_end <= part_start or black_start >= part_end:
            new_fill.append(sync_fill_bounds_to_line(fill_part, line))
            continue

        if part_start < black_start:
            before = copy.deepcopy(fill_part)
            before["bounds"][end_key] = black_start
            update_bounds_size(before["bounds"])
            new_fill.append(sync_fill_bounds_to_line(before, line))

        inserted_fill = {
            "bounds": copy.deepcopy(black_wall["bounds"]),
            "color": "#000000",
        }

        inserted_fill["bounds"][start_key] = max(part_start, black_start)
        inserted_fill["bounds"][end_key] = min(part_end, black_end)
        update_bounds_size(inserted_fill["bounds"])

        new_fill.append(sync_fill_bounds_to_line(inserted_fill, line))

        if black_end < part_end:
            after = copy.deepcopy(fill_part)
            after["bounds"][start_key] = black_end
            update_bounds_size(after["bounds"])
            new_fill.append(sync_fill_bounds_to_line(after, line))

    line["fill"] = [
        fill_part
        for fill_part in new_fill
        if fill_part["bounds"]["length"] > 0
        and fill_part["bounds"]["width"] > 0
    ]

    return line


def split_wall_around_black_fills(wall):
    if wall.get("type") == "base":
        return [wall]

    fill = wall.get("fill", [])
    black_fills = [f for f in fill if f.get("color") == "#000000"]

    if not black_fills:
        return [wall]

    wall = copy.deepcopy(wall)
    b = wall["bounds"]

    is_horizontal = b["length"] > b["width"]

    if is_horizontal:
        start_key = "x1"
        end_key = "x2"
    else:
        start_key = "y1"
        end_key = "y2"

    black_fills = sorted(
        black_fills,
        key=lambda f: f["bounds"][start_key],
    )

    pieces = []
    current_start = b[start_key]

    for black_fill in black_fills:
        black_start = black_fill["bounds"][start_key]
        black_end = black_fill["bounds"][end_key]

        black_start = max(black_start, b[start_key])
        black_end = min(black_end, b[end_key])

        if black_start > current_start:
            new_wall = copy.deepcopy(wall)
            new_wall["id"] = f"{wall['id']}_split_{len(pieces) + 1}"

            new_wall["bounds"][start_key] = current_start
            new_wall["bounds"][end_key] = black_start
            update_bounds_size(new_wall["bounds"])

            new_wall["polygon"] = polygon_from_bounds(new_wall["bounds"])

            new_wall["fill"] = [
                sync_fill_bounds_to_line(f, new_wall)
                for f in fill
                if f.get("color") != "#000000"
                and f["bounds"][start_key] < black_start
                and f["bounds"][end_key] > current_start
            ]

            pieces.append(new_wall)

        current_start = max(current_start, black_end)

    if current_start < b[end_key]:
        new_wall = copy.deepcopy(wall)
        new_wall["id"] = f"{wall['id']}_split_{len(pieces) + 1}"

        new_wall["bounds"][start_key] = current_start
        new_wall["bounds"][end_key] = b[end_key]
        update_bounds_size(new_wall["bounds"])

        new_wall["polygon"] = polygon_from_bounds(new_wall["bounds"])

        new_wall["fill"] = [
            sync_fill_bounds_to_line(f, new_wall)
            for f in fill
            if f.get("color") != "#000000"
            and f["bounds"][start_key] < b[end_key]
            and f["bounds"][end_key] > current_start
        ]

        pieces.append(new_wall)

    return pieces


def split_walls_around_black_fills(walls):
    split_walls = []

    for wall in walls:
        split_walls.extend(split_wall_around_black_fills(wall))

    return split_walls


def dedupe_by_id(items):
    return list({
        item["id"]: item
        for item in items
    }.values())


def get_path_base(layers, wall_thickness):
    returned = {}

    for layer_id, layer_items_raw in layers.items():
        layer_items = {}
        black_walls = []

        for item in layer_items_raw:
            for inner_item in item.get("inside", []):
                fill = inner_item.get("fill", [])

                if fill and fill[0].get("color") in ["#000000", "#552200"]:
                    black_walls.append(normalize_black_wall(inner_item))

        black_walls = dedupe_by_id(black_walls)

        for item in layer_items_raw:
            outer = item["outer"]

            if "path" not in outer["id"]:
                continue

            coords = list(outer["polygon"].exterior.coords)

            for i in range(len(coords) - 1):
                if coords[i] == (outer["bounds"][0], outer["bounds"][1]):
                    if coords[i + 1][0] > coords[i][0]:
                        coords = coords[i:] + coords[:i]
                    else:
                        coords = coords[i::-1] + coords[:i:-1]
                    break

            start = coords[0]
            lines = []

            position = "horizontal" if start[1] == coords[1][1] else "vertical"

            for i in range(len(coords) + 1):
                current_i = i % len(coords)
                next_i = (i + 1) % len(coords)

                if position == "horizontal":
                    if coords[current_i][1] == coords[next_i][1]:
                        continue

                    position = "vertical"

                    lines.append({
                        "id": f"{outer['id']}_outer_wall_{i}",
                        "parent_id": outer["id"],
                        "source_id": outer["id"],
                        "position": position,
                        "bounds": {
                            "x1": start[0],
                            "y1": start[1],
                            "x2": coords[current_i][0],
                            "y2": coords[current_i][1],
                        },
                    })

                    start = coords[current_i]

                else:
                    if coords[current_i][0] == coords[next_i][0]:
                        continue

                    position = "horizontal"

                    lines.append({
                        "id": f"{outer['id']}_outer_wall_{i}",
                        "parent_id": outer["id"],
                        "source_id": outer["id"],
                        "position": position,
                        "bounds": {
                            "x1": start[0],
                            "y1": start[1],
                            "x2": coords[current_i][0],
                            "y2": coords[current_i][1],
                        },
                    })

                    start = coords[current_i]

            for i in range(len(lines)):
                next_i = (i + 1) % len(lines)
                lines[i]["angle"] = turn_between(lines[i], lines[next_i])

            for i in range(len(lines)):
                if i == 0:
                    lines[i]["direction"] = 1
                else:
                    lines[i]["direction"] = (
                        lines[i - 1]["direction"] + lines[i - 1]["angle"]
                    )

                b = lines[i]["bounds"]
                angle = lines[i]["angle"]
                direction = lines[i]["direction"] % 4

                if direction == 1:
                    b["y2"] += wall_thickness
                    b["x2"] += -wall_thickness if angle == 1 else wall_thickness

                elif direction == 2:
                    b["x1"] -= wall_thickness
                    b["y2"] += -wall_thickness if angle == 1 else wall_thickness

                elif direction == 3:
                    b["y1"] -= wall_thickness
                    b["x2"] += wall_thickness if angle == 1 else -wall_thickness

                else:
                    b["x2"] += wall_thickness
                    b["y2"] += wall_thickness if angle == 1 else -wall_thickness

                lines[i] = turn_correct(lines[i])
                lines[i]["polygon"] = wall_to_polygon(lines[i])
                lines[i]["type"] = "outer_wall"
                lines[i]["fill"] = copy.deepcopy(outer["fill"])

                lines[i]["fill"] = [
                    sync_fill_bounds_to_line(fill_part, lines[i])
                    for fill_part in lines[i]["fill"]
                ]

            base_line = copy.deepcopy(outer)
            original_id = base_line["id"]

            base_line["id"] = f"{original_id}_base"
            base_line["type"] = "base"
            base_line["source_id"] = original_id
            base_line["parent_id"] = original_id

            base_line["bounds"] = {
                "x1": min(base_line["bounds"][0], base_line["bounds"][2]),
                "x2": max(base_line["bounds"][0], base_line["bounds"][2]),
                "y1": min(base_line["bounds"][1], base_line["bounds"][3]),
                "y2": max(base_line["bounds"][1], base_line["bounds"][3]),
                "length": abs(base_line["bounds"][0] - base_line["bounds"][2]),
                "width": abs(base_line["bounds"][1] - base_line["bounds"][3]),
            }

            lines.append(base_line)

            for black_wall in black_walls:
                percent_coverage = 0
                biggest_coverage_index = None

                for i in range(len(lines)):
                    if "base" in lines[i]["id"]:
                        continue

                    if black_wall["polygon"].area == 0:
                        continue

                    coverage = (
                        black_wall["polygon"].intersection(lines[i]["polygon"]).area
                        / black_wall["polygon"].area
                    )

                    if coverage > percent_coverage:
                        percent_coverage = coverage
                        biggest_coverage_index = i

                if biggest_coverage_index is not None and percent_coverage > 0.5:
                    lines[biggest_coverage_index] = insert_black_wall_into_line_fill(
                        lines[biggest_coverage_index],
                        black_wall,
                    )

            lines = split_walls_around_black_fills(lines)

            layer_items[original_id] = lines

        returned[layer_id] = layer_items

    return returned