# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Nicolai Skutsch
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import logging
import requests
import sys

from pathlib import Path
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from tqdm import tqdm

# Add the project root directory to the path to allow importing utils
sys.path.append(str(Path(__file__).resolve().parent.parent))
from utils import configure_logging, load_config


MAIN_URL = 'https://s.rsg.sc/sc/images/games/GTAV/map/'
TILE_TYPES = ['game', 'print', 'render']
MAX_ZOOM_LEVEL = 7
TILE_LIMITS = [(0, 0), (0, 1), (1, 2), (3, 5), (7, 11), (15, 23), (31, 47), (63, 95)]


# Load the config file
CONFIG = load_config(Path('config.toml'))

# Get the logger
LOGGER = logging.getLogger('retrieve_tiles')


def create_session() -> requests.Session:
    """
    Creates a requests session with retry policy.

    Args:
        None

    Returns:
        session (requests.Session): The created request session.
    """

    session = requests.Session()
    retries = Retry(total=5, backoff_factor=0.5, status_forcelist=[500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retries)
    session.mount('https://', adapter)

    return session


def download_and_save_tiles(tile_directory: Path) -> None:
    """
    Downloads all GTA V map tiles and stores them in a folder structure.

    Args:
        tile_directory (Path): Root output directory.

    Returns:
        None
    """

    session = create_session()
    tile_directory.mkdir(parents=True, exist_ok=True)

    for tile_type in TILE_TYPES:
        for zoom_level in range(MAX_ZOOM_LEVEL + 1):

            zoom_dir = tile_directory / tile_type / str(zoom_level)
            zoom_dir.mkdir(parents=True, exist_ok=True)

            max_x, max_y = TILE_LIMITS[zoom_level]
            base_url = f'{MAIN_URL}{tile_type}/{zoom_level}'

            for x in tqdm(range(max_x + 1), desc=f'{tile_type} z{zoom_level}'):
                for y in range(max_y + 1):

                    file_path = zoom_dir / f"{x}_{y}.jpg"
                    if file_path.exists():
                        continue

                    url = f'{base_url}/{x}/{y}.jpg'

                    try:
                        response = session.get(url, timeout=10)
                        response.raise_for_status()
                        file_path.write_bytes(response.content)
                    except requests.RequestException as e:
                        LOGGER.warning(f'Failed: {url} ({e})')


def main():

    # Configure the logging
    configure_logging(Path(CONFIG['Paths']['Logs']), CONFIG['Logging']['Level'])

    # Download and save the map tiles to the directory
    download_and_save_tiles(CONFIG['Paths']['MapTiles'])


if __name__ == '__main__':
    main()
