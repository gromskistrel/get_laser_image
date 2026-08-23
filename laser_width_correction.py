def simplify_space(space, white_spaces, original_wall_width, tolerance):
    parents = []
    children = []

    left, top, right, bottom = space["bounds"]

    for candidate in white_spaces:
        if candidate["id"] == space["id"]:
            continue

        c_left, c_top, c_right, c_bottom = candidate["bounds"]

        horizontal_overlap = (
            max(left, c_left)
            <= min(right, c_right) + tolerance
        )

        if not horizontal_overlap:
            continue

        # Candidate is below space
        if abs(c_top - (bottom + original_wall_width)) <= tolerance:
            children.append(candidate["id"])

        # Candidate is above space
        if abs(top - (c_bottom + original_wall_width)) <= tolerance:
            parents.append(candidate["id"])

    return {
        "id": space["id"],
        "polygon": space["polygon"],
        "bounds": space["bounds"],
        "parents": parents,
        "children": children,
    }


def is_white(space):
    return any(
        fill.get("color", "").lower() == "#ffffff"
        for fill in space.get("fill", [])
    )


def get_top_spaces(white_spaces, top_edge, original_wall_width, tolerance):
    return [
        space
        for space in white_spaces
        if abs(
            space["bounds"][1] - (top_edge + original_wall_width)
        ) <= tolerance
    ]


def get_next_spaces(current_step, white_spaces, original_wall_width, tolerance):
    next_step = []

    for current_space in current_step:
        current_left = current_space["bounds"][0]
        current_right = current_space["bounds"][2]
        current_bottom = current_space["bounds"][3]

        for candidate in white_spaces:
            if candidate in current_step:
                continue

            candidate_left = candidate["bounds"][0]
            candidate_top = candidate["bounds"][1]
            candidate_right = candidate["bounds"][2]

            correct_vertical_position = abs(
                candidate_top - (current_bottom + original_wall_width)
            ) <= tolerance

            if not correct_vertical_position:
                continue

            horizontal_overlap = (
                max(current_left, candidate_left)
                <= min(current_right, candidate_right) + tolerance
            )

            if not horizontal_overlap:
                continue

            if candidate not in next_step:
                next_step.append(candidate)

    return next_step


def build_levels(white_spaces, top_edge, original_wall_width, tolerance):
    levels = []

    current_step = get_top_spaces(
        white_spaces,
        top_edge,
        original_wall_width,
        tolerance
    )

    while current_step:
        levels.append([
            simplify_space(
                space,
                white_spaces,
                original_wall_width,
                tolerance
            )
            for space in current_step
        ])

        current_step = get_next_spaces(
            current_step,
            white_spaces,
            original_wall_width,
            tolerance
        )

    return levels


def laser_correction(grouped_layers, laser_width):
    original_wall_width = 4
    tolerance = 1e-3
    result = {}

    for layer_name, layer in grouped_layers.items():
        result[layer_name] = {}

        for rectangle in layer:
            outer = rectangle["outer"]

            if outer["type"] != "rect":
                continue

            white_spaces = [
                space
                for space in rectangle["inside"]
                if is_white(space)
            ]

            levels = build_levels(
                white_spaces,
                outer["bounds"][1],
                original_wall_width,
                tolerance
            )

            if levels:
                result[layer_name][outer["id"]] = levels

    return result