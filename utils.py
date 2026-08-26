import csv
import logging
import os
import re
import tomli

from datetime import datetime
from pathlib import Path


# Get the logger
LOGGER = logging.getLogger('utils')


# ----------------------------------------------------------
# Configuration
# ----------------------------------------------------------

def normalize_paths(config: dict) -> dict:
    """
    Resolves environment variables and normalizes paths by replacing all separators with OS-specific ones. It
    recursively normalizes dictionaries and lists. Strings that contain '/' or '\\' are assumed to be paths.

    Args:
        config (dict): The config file.

    Returns:
        config (dict): The config file with normalized paths.
    """

    # Iterate over all paths
    for section in ('Paths', 'TmpPaths'):

        # Check if the section exists
        if not section in config:
            LOGGER.error(f'The section "{section}" is not included in the config file.')
            raise KeyError(f'The section "{section}" is not included in the config file.')

        # Expand the environment variables
        for key in config[section]:
            config[section][key] = str(Path(os.path.expandvars(config[section][key])).expanduser())
            if re.search(r'~|%[^%]+%', config[section][key]):
                LOGGER.error(f'The environment variables in path "{config[section][key]}" could not be expanded.')
                raise ValueError(f'The environment variables in path "{config[section][key]}" could not be expanded.')

    return config


def load_config(file_path: Path) -> dict:
    """
    Loads the config file and normalizes the paths. 

    Args:
        file_path (Path): The file path at which the config file is located.

    Returns:
        config (dict): The loaded configuration.
    """

    # Check if the file exists
    if not file_path.exists():
        LOGGER.error(f'The config file "{file_path}" could not be found.')
        raise FileNotFoundError(f'The config file "{file_path}" could not be found.')

    # Check if the file extension corresponds to TOML
    if not file_path.suffix.lower() == '.toml':
        LOGGER.error(f'The config file "{file_path}" is not a TOML file.')
        raise RuntimeError(f'The config file "{file_path}" is not a TOML file.')

    # Read the file
    with file_path.open('rb') as f:
        config = tomli.load(f)

    # Normalize the paths
    config = normalize_paths(config)

    return config


# ----------------------------------------------------------
# Paths
# ----------------------------------------------------------

def check_path_exists(path: Path, hint: str = '') -> None:
    """
    Checks if a path exists and raises a RuntimeError if not.

    Args:
        path (str): The path to be checked.
        hint (str): The hint that is shown in addition to the error message.

    Returns:
        None
    """

    if not path.exists():
        LOGGER.error(f'The path "{path}" does not exist. {hint}')
        raise RuntimeError(f'The path "{path}" does not exist. {hint}')


def shorten_path(path: str) -> str:
    """
    Shortens a path to only include the parent directory and the file name.

    Args:
        path (str): The full path.

    Returns:
        path (str): The shortened path.
    """

    path = Path(path)

    return str(Path(path.parent.name) / path.name)


# ----------------------------------------------------------
# Metadata
# ----------------------------------------------------------

def sort_metadata(file_path: Path, key_field: str = 'file') -> None:
    """
    Deduplicates and sorts a metadata CSV file in place, keeping only the latest entry for each key.

    Args:
        file_path (Path): The file path to the metadata file.
        key_field (str): The column used as the deduplication and sorting key.

    Returns:
        None
    """

    # Check if the file exists
    check_path_exists(file_path, 'Check the data generation results.')

    # Read the metadata from the file, keeping only the latest entry for each key
    with file_path.open('r', newline='') as f:
        csv_reader = csv.DictReader(f, delimiter=';')
        fieldnames = csv_reader.fieldnames
        metadata = {line[key_field]: line for line in csv_reader}

    # Sort the metadata by the key field and write it back to the file
    with file_path.open('w', newline='') as f:
        csv_writer = csv.DictWriter(f, delimiter=';', fieldnames=fieldnames)
        csv_writer.writeheader()
        for key in sorted(metadata):
            csv_writer.writerow(metadata[key])


# ----------------------------------------------------------
# Logging
# ----------------------------------------------------------

def configure_logging(log_directory: Path, log_level: str = 'INFO') -> None:
    """
    Configures the logging to write to both a log file and the console.

    Args:
        log_directory (Path): The directory in which the log file is created.
        log_level (str): The logging level.

    Returns:
        None
    """

    # Check the logging level
    level = logging.getLevelNamesMapping().get(log_level.upper())
    if level is None:
        raise ValueError(f'The logging level "{log_level}" is invalid.')

    # Create a directory for the logs if it doesn't exist yet
    log_directory.mkdir(parents=True, exist_ok=True)

    # Create a log file
    logfile = log_directory / f'{datetime.now():%Y%m%d-%H%M%S}.log'

    # Configure the logging
    logging.basicConfig(
        level=level,
        format='%(asctime)s %(levelname)s %(name)s: %(message)s',
        handlers=[
            logging.FileHandler(logfile, encoding='utf-8', delay=True),
            logging.StreamHandler(),
        ],
        force=True,
    )


# ----------------------------------------------------------
# Script Editing and Compilation
# ----------------------------------------------------------

def find_vs_tool(vs_path: Path, tool: str) -> Path:
    """
    Searches for the path of a Visual Studio tool. Throws a Runtime exception if the tool could not be found.

    Args:
        vs_path (Path): The path to Visual Studio.
        tool (str): The name of the tool.

    Returns:
        tool_path (Path): The path to the tool.
    """

    # Search for the tool path
    tool_path = next(vs_path.rglob(tool), None)
    if tool_path is None:
        raise RuntimeError(f'The Visual Studio tool "{tool}" could not be found.')

    return tool_path


def replace_in_file(file_path: Path, old_pattern: str, new_pattern: str) -> None:
    """
    Replaces a REGEX pattern inside a file with a new pattern or string.

    Args:
        file_path (Path): The file path.
        old_pattern (str): The pattern that should be replaced.
        new_pattern (str): The pattern that the old pattern should be replaced with.

    Returns:
        None
    """
    
    # Read the data from the file
    file = file_path.read_text(encoding='utf-8')

    # Compile the pattern that should be replaced
    re_pattern = re.compile(old_pattern)

    # Replace the pattern in the file
    file = re_pattern.sub(new_pattern, file)

    # Write the data to the file
    file_path.write_text(file, encoding='utf-8')