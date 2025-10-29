import cv2
import glob
import mmh3
import os
import OpenEXR
import shutil
import sys
import time

from ctypes import windll
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

sys.path.append('C:\\Program Files\\RenderDoc')
import renderdoc

# Use CuPy if CUDA is available, otherwise NumPy
try:
    import cupy as np
    from cupyx.scipy import ndimage
    GPU = True
except:
    import numpy as np
    from scipy import ndimage
    GPU = False


class Panorama:

    def get_orientations(number_of_cubemaps):
        """
        Defines the orientation vector for each orientation in the correct order.

        Args:
            number_of_cubemaps (int): The number of cubemaps (either 6 or 18).

        Returns:
            orientations ([[np.float64]]): The list of orientation vectors of shape [3].
        """

        # Check if the number of cubemaps is either 6 or 18
        assert number_of_cubemaps in [6, 18]

        # Create a list of orientations
        orientations = []

        # Add the six main orientations to the list
        orientations.append(np.array([ 0,  0, -1], dtype=np.float64)) # NORTH
        orientations.append(np.array([ 0,  0,  1], dtype=np.float64)) # SOUTH
        orientations.append(np.array([ 1,  0,  0], dtype=np.float64)) # EAST
        orientations.append(np.array([-1,  0,  0], dtype=np.float64)) # WEST
        orientations.append(np.array([ 0, -1,  0], dtype=np.float64)) # UP
        orientations.append(np.array([ 0,  1,  0], dtype=np.float64)) # DOWN

        # Return if the number of cubemaps is reached
        if number_of_cubemaps == len(orientations):
            return orientations

        # Add the remaining twelve orienations to the list
        orientations.append(np.array([ 1,  0, -1], dtype=np.float64)) # NORTHEAST
        orientations.append(np.array([-1,  0, -1], dtype=np.float64)) # NORTHWEST
        orientations.append(np.array([ 1,  0,  1], dtype=np.float64)) # SOUTHEAST
        orientations.append(np.array([-1,  0,  1], dtype=np.float64)) # SOUTHWEST
        orientations.append(np.array([ 0, -1, -1], dtype=np.float64)) # UPNORTH
        orientations.append(np.array([ 0, -1,  1], dtype=np.float64)) # UPSOUTH
        orientations.append(np.array([ 1, -1,  0], dtype=np.float64)) # UPEAST
        orientations.append(np.array([-1, -1,  0], dtype=np.float64)) # UPWEST
        orientations.append(np.array([ 0,  1, -1], dtype=np.float64)) # DOWNNORTH
        orientations.append(np.array([ 0,  1,  1], dtype=np.float64)) # DOWNSOUTH
        orientations.append(np.array([ 1,  1,  0], dtype=np.float64)) # DOWNEAST
        orientations.append(np.array([-1,  1,  0], dtype=np.float64)) # DOWNWEST

        return orientations


    def calculate_R(orientation, up=np.array([0, -1, 0])):
        """
        Calculates the rotation matrix for a given orientation.

        Args:
            orientation ([np.float64]): The orientation vector of shape 3.
            up ([np.float64]): The vector pointing in the up-direction of shape 3.

        Returns:
            R ([[np.float64]]): The rotation matrix of shape 3x3.
        """

        # Normalize the orientation
        orientation = orientation / np.linalg.norm(orientation)

        # If the orientation is close to the up or down vector
        # return a fixed value for the orientation due to numerical instabilities
        if np.allclose(orientation, up):
            return np.array([[1, 0, 0], [0, 0, 1], [0, -1, 0]], dtype=np.float64)
        if np.allclose(orientation, -up):
            return np.array([[1, 0, 0], [0, 0, -1], [0, 1, 0]], dtype=np.float64)

        # Calculate the other two rotation vectors
        x = np.cross(up, orientation)
        x = x / np.linalg.norm(x)
        y = np.cross(orientation, x)
        y = y / np.linalg.norm(y)

        # Construct the rotation matrix
        R = np.array([x, y, orientation])

        return R


    def rotate_xyz(R, x, y, z):
        """
        Applies the rotation matrix to all coordinates.

        Args:
            R ([[np.float64]]): The rotation matrix of shape 3x3.
            x ([[np.float64]]): The x-coordinates for each pixel of the panorama.
            y ([[np.float64]]): The y-coordinates for each pixel of the panorama.
            z ([[np.float64]]): The z-coordinates for each pixel of the panorama.

        Returns:
            x ([[np.float64]]): The rotated x-coordinates for each pixel of the panorama.
            y ([[np.float64]]): The rotated y-coordinates for each pixel of the panorama.
            z ([[np.float64]]): The rotated z-coordinates for each pixel of the panorama.
        """

        # Apply the rotation matrix to the coordinates 
        xyz = np.stack((x.ravel(), y.ravel(), z.ravel()))
        x, y, z = np.matmul(R, xyz).reshape(3, *x.shape)
        
        return x, y, z


    def uv_pano(orientations, cubemap_shape, pano_shape):
        """
        Calculates the pixel correspondences between the cubemaps and the panorama.

        Args:
            orientations ([[np.float64]]): The list of orientation vectors of shape [3].
            cubemap_shape ((int, int)): The shape of each cubemap in the format (cubemap_height, cubemap_width).
            panorama_shape ((int, int)): The shape of the panorama in the format (pano_height, pano_width).

        Returns:
            masks ([[[np.float64]]]): The mask of the area of the panorama to which each cubemap contributes
                                      in the shape of (#cubemaps, pano_height, pano_width).
            u_cubes ([[[np.float64]]]): The u-coordinates that map the cubemap coordinates to the panorama coordinates
                                        in the shape of (#cubemaps, pano_height, pano_width).
            v_cubes ([[[np.float64]]]): The v-coordinates that map the cubemap coordinates to the panorama coordinates
                                        in the shape of (#cubemaps, pano_height, pano_width).
        """

        # Initialize the u-coordinates and v-coordinates of the panorama
        u_pano, v_pano = np.meshgrid(np.arange(pano_shape[0]), np.arange(pano_shape[1]), indexing='ij')

        # Initialize the masks, u-coordinates, and v-coordinates for the cubemaps
        masks   = np.zeros((len(orientations), pano_shape[0], pano_shape[1]), dtype=np.float64)
        u_cubes = np.empty((len(orientations), pano_shape[0], pano_shape[1]), dtype=np.float64)
        v_cubes = np.empty((len(orientations), pano_shape[0], pano_shape[1]), dtype=np.float64)

        # Iterate over all orientations
        for i in range(len(orientations)):

            # Calculate the spherical coordinates for each pixel in the panorama
            phi = (u_pano / pano_shape[0] * 1 + 0.5) * np.pi
            theta = (v_pano / pano_shape[1] * 2 + 0.5) * np.pi

            # Convert the spherical coordinates to catesian coordinates
            x = np.cos(phi) * np.cos(theta)
            y = np.sin(phi)
            z = np.cos(phi) * np.sin(theta)
            del phi, theta

            # Calcuate the rotation matrix based on the orientation vector of the cubemap
            R = Panorama.calculate_R(orientations[i])
            x, y, z = Panorama.rotate_xyz(R, x, y, z)
            del R

            # Mask the regions of the panorama the cubemap contributes to
            condition = (abs(z) > abs(x)) & (abs(z) > abs(y)) & (z < 0)
            masks[i][condition] = 1.0
            a =  y
            b = -x
            max_abs_coord = abs(z)
            del x, y, z

            # Save the pixel correspondences between cubemap and the panorama
            u_cubes[i][condition] = ((a[condition] / max_abs_coord[condition]) + 1.0) * 0.5 * (cubemap_shape[0] - 1)
            v_cubes[i][condition] = ((b[condition] / max_abs_coord[condition]) + 1.0) * 0.5 * (cubemap_shape[1] - 1)
            del a, b

            # Round the values to get pixel values
            u_cubes = u_cubes.astype(int)
            v_cubes = v_cubes.astype(int)

            # Free the GPU memory if CuPy is used
            if GPU:
                np.get_default_memory_pool().free_all_blocks()

        return masks, u_cubes, v_cubes


    def transform(cubemaps, blending=False, exr=False):
        """
        Transforms all cubemaps to a single panorama and applies blending if necessary.

        Args:
            cubemaps ([[[np.float64]]]): The list of cubemaps of shape [(cubemap_height, cubemap_width)].
            blending (bool): True if blending should be applied.
            exr (bool): True if the the resulting panorama should be stored as EXR file and therefore needs no clipping.

        Returns:
            pano ([[[np.float64]]]): The stitched and blended RGB panorama of shape (pano_height, pano_width, 3).
        """
        
        # Get the cubemap and panorama shape and create a new panorama image (either BW or RGB)
        cubemap_shape = cubemaps[0].shape
        if len(cubemaps[0].shape) > 2:
            pano_shape = (int(cubemap_shape[0] * 2), int(cubemap_shape[1] * 4), cubemap_shape[2])
        else:
            pano_shape = (int(cubemap_shape[0] * 2), int(cubemap_shape[1] * 4))
        pano = np.zeros(pano_shape, dtype=np.float32)

        # Move the cubemaps to the GPU if CuPy is used
        if GPU:
            for i in range(len(cubemaps)):
                cubemaps[i] = np.asarray(cubemaps[i])

        # Get the orientation vector for each cubemap
        orientations = Panorama.get_orientations(len(cubemaps))

        # Get the pixel correspondences between the cubemaps an the panorama
        masks, u_cubes, v_cubes = Panorama.uv_pano(orientations, cubemap_shape, pano_shape)

        # Stitch and blend the panorama
        if blending:

            # For each cubemap, calculate the distance from the mask center to the mask border and use the distance as weight
            for i in range(len(cubemaps)):
                masks[i] = ndimage.distance_transform_edt(masks[i])
                if np.max(masks[i]) > 0:
                    masks[i] = masks[i] / np.max(masks[i])

            # For each cubemap, create a weight mask based on the calculated distances and stitch the cubemaps together
            for i in range(len(cubemaps)):
                weight = np.stack([masks[i][masks[i] > 0], masks[i][masks[i] > 0], masks[i][masks[i] > 0]], axis=1)
                pano[masks[i] > 0] += cubemaps[i][u_cubes[i][masks[i] > 0], v_cubes[i][masks[i] > 0]] * weight

            # Normalize the panorama
            weight_sum = np.stack([np.sum(masks, axis=0), np.sum(masks, axis=0), np.sum(masks, axis=0)], axis=2)
            weight_sum = np.where(weight_sum <= 0, 1, weight_sum)
            pano = pano / weight_sum

        # Stitch the panorama
        else:

            # Stitch the cubemaps together
            for i in range(len(cubemaps)):
                pano[masks[i] > 0] += cubemaps[i][u_cubes[i][masks[i] > 0], v_cubes[i][masks[i] > 0]]

        # Free the memory
        del masks, u_cubes, v_cubes            

        # Convert the panorama to uint8 if it is not saved as EXR file
        if not exr:
            pano = np.clip(pano, 0, 255).astype(np.uint8)

        # Move the panorama to the CPU and free the memory if CuPy is used
        if GPU:
            pano = np.asnumpy(pano)
            np.get_default_memory_pool().free_all_blocks()

        return pano


    def load_image(file_path):
        """
        Loads a cubemap from the given file path.

        Args:
            file_path (string): The file path at which the cubemap is located.

        Returns:
            image ([[[np.uint8/np.float64]]]): The loaded image of shape (cubemap_height, cubemap_width[, 3]).
        """

        # If the file is not an EXR file, load it using cv2
        if not file_path.lower().endswith('.exr'):
            image = cv2.imread(file_path, cv2.IMREAD_COLOR)

        # If the file is an EXR file, load it using OpenEXR
        else:
            image = OpenEXR.InputFile(file_path)
            dim_x = image.header()['dataWindow'].max.x + 1
            dim_y = image.header()['dataWindow'].max.y + 1
            image = np.frombuffer(image.channel('R'), dtype=np.float32).reshape(dim_y, dim_x)
            image = np.array(image)

        return image


    def save_pano(file_path, pano, exr=False):
        """
        Saves a panorama to the given file path.

        Args:
            file_path (string): The file path at which the cubemap is located.
            image ([[[np.uint8/np.float64]]]): The panorama of shape (pano_height, pano_width[, 3]).
            exr (bool): True if the the panorama should be stored as EXR file.

        Returns:
            None
        """

        # If the file is not an EXR file, save it using cv2
        if not exr:
            cv2.imwrite(file_path, pano)
        
        # If the file is an EXR file, save it using OpenEXR
        else:
            exr_file = OpenEXR.OutputFile(file_path, OpenEXR.Header(pano.shape[1], pano.shape[0]))
            exr_file.writePixels({'R': pano.tobytes(), 'G': pano.tobytes(), 'B': pano.tobytes()})
            exr_file.close()


    def stitch_panorama(file_paths_cubemaps, file_path_panorama):
        """
        Loads the cubemaps, stitches and blends the panorama, and saves the panorama as image file.

        Args:
            file_paths_cubemaps ([string]): The file paths at which the cubemaps are located.
            file_path_panorama (string): The file path to which the panorama should be saved.

        Returns:
            None
        """

        # Load the cubemaps
        cubemaps = []
        for file_path in file_paths_cubemaps:
            cubemaps.append(Panorama.load_image(file_path))

        # Stitch and blend the panorama
        if len(cubemaps) == 18:
            pano = Panorama.transform(cubemaps, blending=True, exr=False)
            Panorama.save_pano(file_path_panorama, pano, exr=False)
        elif len(cubemaps) == 6 and file_paths_cubemaps[-1].lower().endswith('.png'):
            pano = Panorama.transform(cubemaps, blending=False, exr=False)
            Panorama.save_pano(file_path_panorama, pano, exr=False)
        elif len(cubemaps) == 6 and file_paths_cubemaps[-1].lower().endswith('.exr'):
            pano = Panorama.transform(cubemaps, blending=False, exr=True)
            Panorama.save_pano(file_path_panorama, pano, exr=True)


def get_drawcalls(controller):
    """
    Identifies and returns the G-buffer drawcalls and the NVIDIA TXAA drawcall.

    Args:
        controller (renderdoc.ReplayController): The replay controller of the capture file.

    Returns:
        gbuffer_drawcalls ([renderdoc.ActionDescription]): The G-buffer drawcalls.
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

        # If an action fullfils all the criteria for G-buffer drawcalls, add it to the list
        if (is_drawcall and has_depth and has_four_outputs):
            gbuffer_drawcalls.append(action)

        # If an action is the 'NV TXAA resolve' drawcall, save it as RGB drawcall
        if 'NV TXAA resolve' in action.GetName(controller.GetStructuredFile()):
            rgb_drawcall = action.children[-1]

    return gbuffer_drawcalls, rgb_drawcall


def render_buffers(controller, gbuffer_drawcall, rgb_drawcall, file_path):
    """
    Saves the results of the drawcalls, namely the depth, stencil, and RGB image, as images files.

    Args:
        controller (renderdoc.ReplayController): The replay controller of the capture file.
        gbuffer_drawcalls (renderdoc.ActionDescription): The final G-buffer drawcall.
        rgb_drawcall (renderdoc.ActionDescription): The NVIDIA TXAA drawcall.
        file_path (string): The file path to which the images should be saved.

    Returns:
        None
    """

    # Set the controller to the correct frame event
    controller.SetFrameEvent(gbuffer_drawcall.eventId, False)

    # Initialize the texture save
    save_data = renderdoc.TextureSave()

    # Save the depth buffer
    save_data.resourceId = gbuffer_drawcall.depthOut
    save_data.destType = renderdoc.FileType.EXR
    save_data.channelExtract = 0
    controller.SaveTexture(save_data, '{0}_depth.exr'.format(file_path))

    # Save the stencil buffer
    save_data.resourceId = gbuffer_drawcall.depthOut
    save_data.destType = renderdoc.FileType.PNG
    save_data.channelExtract = 1
    controller.SaveTexture(save_data, '{0}_stencil.png'.format(file_path))

    # Set the controller to the correct frame event
    controller.SetFrameEvent(rgb_drawcall.eventId, False)
    save_data = renderdoc.TextureSave()

    # Save the RGB image
    save_data.resourceId = rgb_drawcall.outputs[0]
    save_data.destType = renderdoc.FileType.JPG
    save_data.channelExtract = -1
    save_data.alpha = renderdoc.AlphaMapping.Discard
    save_data.jpegQuality = 100
    controller.SaveTexture(save_data, '{0}_rgb.jpg'.format(file_path))


def wait_for_file_saving(file_path):
    """
    Waits for a file to be saved successfully.

    Args:
        file_path (string): The file path of the capture file.

    Returns:
        True (bool): If the file was saved successfully.
    """

    # Repeat until the file was saved successfully
    previous_size = -1
    while True:

        # Get the current file size
        current_size = os.path.getsize(file_path)
        time.sleep(1)

        # Check if the file size has changed
        if current_size == previous_size:
            return True
        else:
            previous_size = current_size


def convert_rdc(capture_file_path, file_name):
    """
    Opens a RDC capture file, identifies the drawcalls, and saves the depth, stencil, and RGB image as image files.

    Args:
        capture_file_path (string): The file path of the capture file.
        capture_file_path (string): The file name of the image files.

    Returns:
        None
    """

    # Wait until the capture file was saved successfully
    wait_for_file_saving(capture_file_path)

    # Open the capture file
    capture_file = renderdoc.OpenCaptureFile()
    result = capture_file.OpenFile(capture_file_path, '', None)
    if not result.OK():
        try:
            capture_file.Shutdown()
        finally:
            print('[RenderDoc] ERROR: The capture file could not be opened.')
            return
    result, controller = capture_file.OpenCapture(renderdoc.ReplayOptions(), None)
    if not result.OK():
        try:
            controller.Shutdown()
            capture_file.Shutdown()
        finally:
            print('[RenderDoc] ERROR: The capture file could not be opened.')
            return

    # Get the file path
    file_path = os.path.dirname(capture_file_path)

    # Get the G-buffer drawcalls
    gbuffer_drawcalls, rgb_drawcall = get_drawcalls(controller)

    # Render all outputs of the last G-buffer drawcall
    render_buffers(controller, gbuffer_drawcalls[-1], rgb_drawcall, os.path.join(file_path, file_name))

    # Close the controller and capture file
    controller.Shutdown()
    capture_file.Shutdown()