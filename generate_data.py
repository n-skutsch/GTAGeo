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
import panorama_projection_toolkit as ppt
import subprocess
import sys
import time
import wmi

from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileCreatedEvent, FileMovedEvent, FileSystemEventHandler

from process_rdc import rdc_to_data
from utils import check_path_exists, configure_logging, load_config, shorten_path, sort_metadata


# Load the config file
CONFIG = load_config(Path('config.toml'))

# Get the logger
LOGGER = logging.getLogger('generate_data')

# Import RenderDoc
check_path_exists(Path(CONFIG['Paths']['RenderDoc']), 'Check the RenderDoc installation.')
sys.path.append(str(Path(CONFIG['Paths']['RenderDoc'])))
import renderdoc


def process_cubemaps(file_path: Path, number_of_cubemaps: int) -> Path | None:
    """
    Checks if all cubemaps have been extracted from the RDC file and stitches the panorama if the set of cubemaps is
    complete.

    Args:
        file_path (Path): The file path of the last created file.
        number_of_cubemaps (int): The number of cubemaps that should be processed; either 6 or 18.

    Returns:
        pano_file_path (Path | None): The file path of the stitched panorama, or None if the panorama was not stitched.
    """

    # Check the number of cubemaps
    if not number_of_cubemaps in [6, 18]:
        LOGGER.warning('The number of cubemaps needs to be either 6 or 18.')
        return None

    # Depending on whether blending should be applied, select the corresponding list of orientations
    orientations = CONFIG['Panorama']['PanoramaHeadings'][:number_of_cubemaps]

    # Check if the last created file completes the set of cubemaps
    if not orientations[-1] in file_path:
        return None

    # Check if all other cubemaps have been created successfully and save the file paths
    cubemap_file_paths = []
    for orientation in orientations:
        cubemap_file_path = Path(str(file_path).replace(orientations[-1], orientation))
        if cubemap_file_path.exists():
            cubemap_file_paths.append(cubemap_file_path)
        else:
            LOGGER.warning(f'The cubemap file "{cubemap_file_path}" is missing. Panorama can not be created.')
            return None

    # Load all cubemaps
    cubemaps = []
    for cubemap_file_path in cubemap_file_paths:
        cubemaps.append(ppt.load_image(str(cubemap_file_path)))

    # Stitch the panorama and save it
    pano_size = (2 * cubemaps[0].shape[0], 4 * cubemaps[0].shape[1])
    pano_file_path = Path(str(cubemap_file_paths[-1]).replace(orientations[-1], ''))
    LOGGER.info(f'Stitching the panorama file "{pano_file_path}".')
    pano = ppt.cubemaps_to_pano(cubemaps, pano_size)
    ppt.save_image(str(pano_file_path), pano)

    return pano_file_path


class EventHandler(FileSystemEventHandler):

    def __init__(self, save_rgb, save_depth, save_stencil):
        super().__init__()
        self.save_rgb = save_rgb
        self.save_depth = save_depth
        self.save_stencil = save_stencil


    def on_moved(self, event: FileMovedEvent) -> None:
        """
        This event is triggered when a file has been moved. This happens any time the data generation script has
        finished saving a RenderDoc Capture file and renamed the TMP file.

        Args:
            event (FileMovedEvent): The file moved event.

        Returns:
            None
        """

        LOGGER.debug('Event (file moved): "{0}" -> "{1}"'.format(shorten_path(event.src_path), shorten_path(event.dest_path)))

        # Ignore all files that are not RDC files
        if not event.dest_path.lower().endswith(('.rdc')):
            return

        # The 12 extended panorama orientations (beyond N, S, E, W, U, D) only carry a RGB image, so depth and
        # stencil are not extracted for them
        extended_headings = tuple(CONFIG['Panorama']['PanoramaHeadings'][6:])
        is_extended_orientation = Path(event.dest_path).stem.endswith(extended_headings)
        save_depth = self.save_depth and not is_extended_orientation
        save_stencil = self.save_stencil and not is_extended_orientation

        # Determine the data that is extracted from the capture file
        extracted_data = ', '.join(label for label, extract in (
            ('RGB image', self.save_rgb),
            ('depth map', save_depth),
            ('stencil map', save_stencil)
        ) if extract)

        LOGGER.info(f'Extracting the following data from the capture file "{shorten_path(event.dest_path)}": {extracted_data}')

        # Extract the RGB image, depth map, and stencil map from the RDC file
        rdc_to_data(
            event.dest_path,
            save_rgb=self.save_rgb,
            save_depth=save_depth,
            save_stencil=save_stencil
        )

        # Delete the RDC file now that the required data has been extracted
        LOGGER.debug(f'Deleting the capture file "{shorten_path(event.dest_path)}".')
        Path(event.dest_path).unlink()


    def on_created(self, event: FileCreatedEvent) -> None:
        """
        This event is triggered when a file has been created. This happens any time the postprocessing script has
        finished generating the RGB image, depth map, or stencil map.

        Args:
            event (FileCreatedEvent): The file created event.

        Returns:
            None
        """

        LOGGER.debug('Event (file created): {0}'.format(shorten_path(event.src_path)))

        # Ignore all files that are not a RGB image, depth map, or stencil map file
        if not event.src_path.lower().endswith(('_rgb.jpg', '_stencil.png', '_depth.exr')):
            return

        # Set the number of cubemaps: the RGB panorama is stitched from all 18 views, the depth and stencil
        # panoramas are stitched from the first 6 views only (N, S, E, W, U, D)
        number_of_cubemaps = 0
        if event.src_path.lower().endswith(('_rgb.jpg')):
            number_of_cubemaps = 18
        if event.src_path.lower().endswith(('_stencil.png', '_depth.exr')):
            number_of_cubemaps = 6

        # If all cubemaps have been extracted from the RDC files, stitch the panorama
        pano_file_path = process_cubemaps(event.src_path, number_of_cubemaps)


def initialize_renderdoc() -> None:
    """
    Initializes RenderDoc by activating the global hook.

    Args:
        None

    Returns:
        None
    """

    # Check if the global hook feature is available
    if not renderdoc.CanGlobalHook():
        LOGGER.error('The RenderDoc global hook can not be activated.')
        raise RuntimeError('The RenderDoc global hook can not be activated.')

    # Get the default capture options
    capture_options = renderdoc.GetDefaultCaptureOptions()

    # Activate the global hook
    gta_exe_path = Path(CONFIG['Paths']['GTAV']) / 'GTA5.exe'
    global_hook = renderdoc.StartGlobalHook(str(gta_exe_path), str(Path(CONFIG['Paths']['Data'])), capture_options)
    if not global_hook.OK():
        LOGGER.error(f'The RenderDoc global hook can not be activated. Error Message: {global_hook.Message()}')
        raise RuntimeError(f'The RenderDoc global hook can not be activated. Error Message: {global_hook.Message()}')

    # Check if the global hook is active
    if not renderdoc.IsGlobalHookActive():
        LOGGER.error('The RenderDoc global hook could not be activated.')
        raise RuntimeError('The RenderDoc global hook can not be activated.')


def get_gta_pid(timeout_s: int = 120) -> int:
    """
    Determines the PID of the GTA V process.

    Args:
        timeout_s (int): The timeout of the function in seconds.

    Returns:
        gta_pid (int): The PID of the GTA V process.
    """

    start = time.time()

    # Start searching for the GTA V process
    gta_pid = -1
    while gta_pid == -1:

        # Check for timeout
        if time.time() - start > timeout_s:
            LOGGER.error('The PID of the GTA V process could not be found.')
            raise TimeoutError('The PID of the GTA V process could not be found.')

        # Get a list of all processes
        processes = wmi.WMI()

        # Check if GTA V is running
        for process in processes.Win32_Process():

            # Get the PID of GTA V
            if 'GTA5.exe' in process.Name:
                gta_pid = process.ProcessId

        time.sleep(1)

    return gta_pid
    

def inject_into_process(pid: int) -> None:
    """
    Injects RenderDoc into the GTA V process.

    Args:
        pid (int): The PID of the GTA V process.

    Returns:
        None
    """

    # Get the default capture options
    capture_options = renderdoc.GetDefaultCaptureOptions()
    
    # Inject RenderDoc into the process
    injection = renderdoc.InjectIntoProcess(pid, [], str(Path(CONFIG['Paths']['Data'])), capture_options, False)
    if not injection.result.OK():
        LOGGER.error(f'The injection into the GTA V process was not successful. Error Message: {injection.result.Message()}')
        raise RuntimeError(f'The injection into the GTA V process was not successful. Error Message: {injection.result.Message()}')


def main():

    # Configure the logging
    configure_logging(Path(CONFIG['Paths']['Logs']), CONFIG['Logging']['Level'])

    # Check if all directories exist and if the directories contain the right files
    check_path_exists(Path(CONFIG['Paths']['GTAV']), 'Check the GTA V directories or the config file.')
    check_path_exists(Path(CONFIG['Paths']['GTAV']) / Path('GTA5.exe'), 'Check the GTA V directories or the config file.')
    check_path_exists(Path(CONFIG['Paths']['GTAV']) / Path('GTAVLauncher.exe'), 'Check the GTA V directories or the config file.')
    check_path_exists(Path(CONFIG['Paths']['Data']), 'Check the config file.')
    check_path_exists(Path(CONFIG['Paths']['WBG']), 'Check the initialization or the config file.')

    # Create the directory if it doesn't exist yet
    Path(CONFIG['Paths']['Data']).mkdir(parents=True, exist_ok=True)

    process_wbg = None
    process_gta = None
    file_observer = None

    try:

        # Initialize RenderDoc
        LOGGER.info('Initializing RenderDoc and starting the global hook.')
        initialize_renderdoc()

        # Start Windowed Borderless Gaming
        wbg_path = Path(CONFIG['Paths']['WBG']) / 'WindowedBorderlessGaming.exe'
        LOGGER.info(f'Starting the WBG process "{wbg_path}".')
        process_wbg = subprocess.Popen([wbg_path])

        # Start GTA V
        gta_path = Path(CONFIG['Paths']['GTAV']) / 'GTAVLauncher.exe'
        LOGGER.info(f'Starting the GTA V process "{gta_path}".')
        process_gta = subprocess.Popen([gta_path])
        
        # Inject RenderDoc into the GTA V process
        LOGGER.info('Injecting into the process of GTA V.')
        inject_into_process(get_gta_pid())

        # Start the WatchDog
        LOGGER.info('Starting the watchdog for Renderdoc capture files.')
        file_observer = Observer()
        file_observer.schedule(
            EventHandler(
                CONFIG['Generation']['GenerateRGB'],
                CONFIG['Generation']['GenerateDepth'],
                CONFIG['Generation']['GenerateStencil']
            ),
            path=Path(CONFIG['Paths']['Data']),
            recursive=True
        )
        file_observer.start()

        LOGGER.info('RenderDoc is initialized and WatchDog is active. You may now start the data generation process.')

        while True:
            time.sleep(0.1)    

    # Terminate all processes if the script is terminated
    except KeyboardInterrupt:
        LOGGER.debug('KeyboardInterrupt received. Terminating the data generation.')

    finally:

        # Sort and deduplicate the metadata file
        metadata_file = Path(CONFIG['Paths']['Data']) / 'metadata.csv'
        if metadata_file.exists():
            LOGGER.info(f'Sorting the metadata file "{metadata_file}".')
            sort_metadata(metadata_file)

        if file_observer is not None:
            LOGGER.info('Terminating the watchdog for Renderdoc capture files.')
            file_observer.stop()
            file_observer.join()

        if process_gta is not None:
            LOGGER.info('Terminating the GTA V process.')
            process_gta.terminate()

        if process_wbg is not None:
            LOGGER.info('Terminating the WBG process.')
            process_wbg.terminate()

        LOGGER.info('Terminating the global hook.')
        renderdoc.StopGlobalHook()
        

if __name__ == '__main__':
    main()