import pandas as pd

def get_color_scheme(filename, game_name):
    df = pd.read_csv(filename, header=None)

    for i, cell in enumerate(df[0]):
        if pd.isna(cell):
            continue

        # Does this section start with the requested game name?
        if str(cell).split()[0] == game_name:
            colors = {}
            j = i + 1  # Start after the game name

            while j < len(df):
                # Stop at empty row
                if pd.isna(df.iloc[j, 0]) or str(df.iloc[j, 0]).strip() == "":
                    break

                hex_color = str(df.iloc[j, 0]).strip().lower()
                value = int(df.iloc[j, 1])

                colors[hex_color] = value
                j += 1

            return colors

    return None