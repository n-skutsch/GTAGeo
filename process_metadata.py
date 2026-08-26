import csv
import logging

from pathlib import Path

from utils import check_path_exists, configure_logging, load_config


# Load the config file
CONFIG = load_config(Path('config.toml'))

# Get the logger
LOGGER = logging.getLogger('process_metadata')


def create_trajectory_from_metadata(file_path_metadata: Path, file_path_trajectory: Path) -> None:
    """
    Creates a Reality Scan trajectory file for all overlapping aerial-view images from the metadata file.

    Args:
        file_path_metadata (Path): The file path to the metadata file.
        file_path_trajectory (Path): The file path to the trajectory file.

    Returns:
        None
    """

    # Name of the folder that contains the overlapping aerial-view images
    aerial_view_area_folder = Path(CONFIG['Paths']['DataAerialViewArea']).name

    # Read the metadata from the metadata file, keeping only the latest entry for each file
    LOGGER.info(f'Reading the metadata from "{file_path_metadata}".')
    metadata = {}
    with file_path_metadata.open('r', newline='') as f:
        csv_reader = csv.DictReader(f, delimiter=';')
        for line in csv_reader:
            metadata[line['file']] = line

    # Filter out the metadata that belongs to the overlapping aerial-view images
    LOGGER.info('Filtering the metadata for the overlapping aerial-view images.')
    trajectory = []
    for file, line in metadata.items():
        folder, file_name = file.replace('\\', '/').split('/', 1)
        if folder != aerial_view_area_folder:
            continue

        position = [float(value) for value in line['position'].strip('[]').split(',')]
        rotation = [float(value) for value in line['rotation'].strip('[]').split(',')]

        trajectory.append({'file_name': f'{file_name}_rgb.jpg',
                            'x': position[0],
                            'y': position[1],
                            'z': position[2],
                            'yaw': rotation[2],
                            'pitch': rotation[0],
                            'roll': rotation[1]})

    # Sort the trajectory by file name for a deterministic output
    trajectory.sort(key=lambda row: row['file_name'])

    # Write the trajectory file
    LOGGER.info(f'Writing {len(trajectory)} images to the trajectory file "{file_path_trajectory}".')
    with file_path_trajectory.open('w', newline='') as f:
        csv_writer = csv.DictWriter(f, delimiter=';', fieldnames=['file_name', 'x', 'y', 'z', 'yaw', 'pitch', 'roll'])
        csv_writer.writeheader()
        for row in trajectory:
            csv_writer.writerow(row)


def main():

    # Configure the logging
    configure_logging(Path(CONFIG['Paths']['Logs']), CONFIG['Logging']['Level'])

    # Check if the metadata file exists
    check_path_exists(Path(CONFIG['Paths']['Data']) / 'metadata.csv', 'Check the data generation results.')

    # Create the trajectory file
    create_trajectory_from_metadata(Path(CONFIG['Paths']['Data']) / 'metadata.csv', Path(CONFIG['Paths']['Data']) / 'trajectory.csv')


if __name__ == '__main__':
    main()