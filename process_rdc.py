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
import sys

from pathlib import Path

from utils import check_path_exists, load_config


# Load the config file
CONFIG = load_config(Path('config.toml'))

# Get the logger
LOGGER = logging.getLogger('process_rdc')

# Import RenderDoc
check_path_exists(Path(CONFIG['Paths']['RenderDoc']), 'Check the RenderDoc installation.')
sys.path.append(str(Path(CONFIG['Paths']['RenderDoc'])))
import renderdoc


def get_drawcalls(controller: renderdoc.ReplayController) -> None:
    """
    Identifies and returns the G-buffer drawcalls and the NVIDIA TXAA drawcall.

    Args:
        controller (renderdoc.ReplayController): The replay controller of the capture file.

    Returns:
        gbuffer_drawcalls (list[renderdoc.ActionDescription]): The G-buffer drawcalls.
        rgb_drawcall (renderdoc.ActionDescription): The NVIDIA TXAA drawcall.
    """

    # List of gbuffer drawcalls that match all conditions
    gbuffer_drawcalls = []
    rgb_drawcall = None

    # Iterate over all root actions
    for action in controller.GetRootActions():

        # Criteria for G-buffer drawcalls in GTA V:
        # - The action must be a drawcall.
        # - The action must have a depth output.
        # - The action must have exactly four color outputs.
        is_drawcall = 'Draw' in action.GetName(controller.GetStructuredFile())
        has_depth = action.depthOut != renderdoc.ResourceId.Null()
        has_four_outputs = len([resource for resource in action.outputs if resource != renderdoc.ResourceId.Null()]) == 4

        # If an action fulfils all the criteria for G-buffer drawcalls, add it to the list
        if (is_drawcall and has_depth and has_four_outputs):
            gbuffer_drawcalls.append(action)

        # If an action is the 'NV TXAA resolve' drawcall, save it as RGB drawcall
        if 'NV TXAA resolve' in action.GetName(controller.GetStructuredFile()):
            rgb_drawcall = action.children[-1]

    return gbuffer_drawcalls, rgb_drawcall


def save_rgb_as_image(controller: renderdoc.ReplayController, rgb_drawcall: renderdoc.ActionDescription, file_path: Path) -> None:
    """
    Saves the RGB image of the RGB drawcall as image file.

    Args:
        controller (renderdoc.ReplayController): The replay controller of the capture file.
        rgb_drawcall (renderdoc.ActionDescription): The NVIDIA TXAA drawcall.
        file_path (string): The file path to which the images should be saved.

    Returns:
        None
    """

    # Set the controller to the correct frame event
    controller.SetFrameEvent(rgb_drawcall.eventId, False)

    # Initialize the texture save
    save_data = renderdoc.TextureSave()

    # Save the RGB image
    save_data.resourceId = rgb_drawcall.outputs[0]
    save_data.destType = renderdoc.FileType.JPG
    save_data.channelExtract = -1
    save_data.alpha = renderdoc.AlphaMapping.Discard
    save_data.jpegQuality = 100
    controller.SaveTexture(save_data, str(file_path))


def save_depth_as_image(controller: renderdoc.ReplayController, last_gbuffer_drawcall: renderdoc.ActionDescription, file_path: Path) -> None:
    """
    Saves the depth buffer of the last G-Buffer drawcall as image file.

    Args:
        controller (renderdoc.ReplayController): The replay controller of the capture file.
        last_gbuffer_drawcall (renderdoc.ActionDescription): The last G-buffer drawcall.
        file_path (string): The file path to which the images should be saved.

    Returns:
        None
    """

    # Set the controller to the correct frame event
    controller.SetFrameEvent(last_gbuffer_drawcall.eventId, False)

    # Initialize the texture save
    save_data = renderdoc.TextureSave()

    # Save the depth buffer
    save_data.resourceId = last_gbuffer_drawcall.depthOut
    save_data.destType = renderdoc.FileType.EXR
    save_data.channelExtract = 0
    controller.SaveTexture(save_data, str(file_path))


def save_stencil_as_image(controller: renderdoc.ReplayController, last_gbuffer_drawcall: renderdoc.ActionDescription, file_path: Path) -> None:
    """
    Saves the stencil buffer of the last G-Buffer drawcall as image file.

    Args:
        controller (renderdoc.ReplayController): The replay controller of the capture file.
        last_gbuffer_drawcall (renderdoc.ActionDescription): The last G-buffer drawcall.
        file_path (string): The file path to which the images should be saved.

    Returns:
        None
    """

    # Set the controller to the correct frame event
    controller.SetFrameEvent(last_gbuffer_drawcall.eventId, False)

    # Initialize the texture save
    save_data = renderdoc.TextureSave()

    # Save the stencil buffer
    save_data.resourceId = last_gbuffer_drawcall.depthOut
    save_data.destType = renderdoc.FileType.PNG
    save_data.channelExtract = 1
    controller.SaveTexture(save_data, str(file_path))


def rdc_to_data(capture_file_path: Path, save_rgb: bool, save_depth: bool, save_stencil: bool) -> None:
    """
    Opens a RenderDoc Capture file, identifies the drawcalls, and saves the RGB image, depth buffer, and stencil buffer
    as image files.

    Args:
        capture_file_path (Path): The file path of the RDC file.
        save_rgb (bool): True if the RGB image should be extracted from the RDC file.
        save_depth (bool): True if the depth buffer should be extracted from the RDC file.
        save_stencil (bool): True if the stencil buffer should be extracted from the RDC file.

    Returns:
        None
    """

    # Open the capture file
    LOGGER.debug(f'Opening the RDC file {capture_file_path}.')
    capture_file = renderdoc.OpenCaptureFile()
    result = capture_file.OpenFile(capture_file_path, '', None)
    if not result.OK():
        try:
            capture_file.Shutdown()
        finally:
            LOGGER.error(f'The RDC file "{capture_file_path}" could not be opened.')
            raise RuntimeError(f'The RDC file "{capture_file_path}" could not be opened.')
    result, controller = capture_file.OpenCapture(renderdoc.ReplayOptions(), None)
    if not result.OK():
        try:
            controller.Shutdown()
            capture_file.Shutdown()
        finally:
            LOGGER.error(f'The RDC file "{capture_file_path}" could not be opened.')
            raise RuntimeError(f'The RDC file "{capture_file_path}" could not be opened.')

    # Get the file path and file name
    file_path = Path(capture_file_path).parent
    file_name = Path(capture_file_path).stem

    # Get the G-buffer drawcalls
    gbuffer_drawcalls, rgb_drawcall = get_drawcalls(controller)

    try:

        # Save the depth buffer, stencil buffer, and RGB image
        if save_rgb:
            LOGGER.debug('Extracting the RGB image from the RDC file.')
            save_rgb_as_image(controller, rgb_drawcall, file_path / f'{file_name}{CONFIG['Generation']['WaitForFileRGB']}')
        if save_depth:
            LOGGER.debug('Extracting the depth buffer from the RDC file.')
            save_depth_as_image(controller, gbuffer_drawcalls[-1], file_path / f'{file_name}{CONFIG['Generation']['WaitForFileDepth']}')
        if save_stencil:
            LOGGER.debug('Extracting the stencil buffer from the RDC file.')
            save_stencil_as_image(controller, gbuffer_drawcalls[-1], file_path / f'{file_name}{CONFIG['Generation']['WaitForFileStencil']}')

    finally:

        # Close the controller and capture file
        controller.Shutdown()
        capture_file.Shutdown()