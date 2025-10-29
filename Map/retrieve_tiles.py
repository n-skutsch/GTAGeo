import argparse
import os
import requests


# Parameters of the URL
MAIN_URL = 'https://s.rsg.sc/sc/images/games/GTAV/map/'
TILE_TYPES = ['game', 'print', 'render']
MAX_ZOOM_LEVEL = 7
MAX_DIMENSIONS = [[0, 0], [0, 1], [1, 2], [3, 5],
                  [7, 11], [15, 23], [31, 47], [63, 95]]


def download_and_save_tiles(tile_directory):
    """
    Downloads all tiles and saves them in a suitable folder structure.

    Args:
        tile_directory (string): The folder path to which the tiles are saved.

    Returns:
        None
    """

    # Create the directory if it doesn't exist yet
    if not os.path.exists(tile_directory):
        os.mkdir(tile_directory)

    # For each tile type
    for tile_type in TILE_TYPES:

        # Add the tile type to the URL and directory
        type_directory = os.path.join(tile_directory, tile_type)
        type_url = MAIN_URL + tile_type + '/'

        # Create the directory if it doesn't exist yet
        if not os.path.exists(type_directory):
            os.mkdir(type_directory)

        # For each zoom level
        for zoom_level in range(MAX_ZOOM_LEVEL + 1):

            # Add the zoom level to the URL and directory
            zoom_directory = os.path.join(type_directory, str(zoom_level))
            zoom_url = tile_url + str(zoom_level) + '/'

            # Create the directory if it doesn't exist yet
            if not os.path.exists(zoom_directory):
                os.mkdir(zoom_directory)

            # For each dimension
            for x in range(MAX_DIMENSIONS[zoom_level][0] + 1):
                for y in range(MAX_DIMENSIONS[zoom_level][1] + 1):

                    # Add the dimensions to the URL
                    url = zoom_url + '{0}/{1}.jpg'.format(x, y)
                    
                    # Set the dimensions as file name
                    file_name = '{0}_{1}.jpg'.format(x, y)
                    file_path = os.path.join(zoom_directory, file_name)

                    # Download and save the tile
                    with open(file_path, 'wb') as f:
                        response = requests.get(url)
                        if not response.ok:
                            print(response)
                            continue
                        f.write(response.content)


def main():

    # Parse the input arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', '-o', help='Output directory for the tile files', type=str, metavar='PATH',
                        default=os.path.join(os.getcwd(), 'tiles'))
    args = parser.parse_args()

    # Download and save all tiles
    download_and_save_tiles(args.output)


if __name__ == '__main__':
    main()