import argparse
import os
import subprocess
import sys
import time
import wmi

from ctypes import windll
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

sys.path.append('C:\\Program Files\\RenderDoc')
import renderdoc
import rdc_to_data


def panorama_stitching(file_path):
    """
    Check if the file completes a set of cubemaps such that a new panorama can be stitched.

    Args:
        file_path (string): The file path of the created file.

        Returns:
            None
    """

    # If the file is a RGB image, 18 orientation are required
    if file_path.lower().endswith('_rgb.jpg'):
        orientations = ['_N' , '_S' , '_E' , '_W' , '_U' , '_D' ,
                        '_NE', '_NW', '_SE', '_SW',
                        '_UN', '_US', '_UE', '_UW',
                        '_DN', '_DS', '_DE', '_DW']

    # If the file is a stencil or depth image, 6 orientations are required
    elif file_path.lower().endswith(('_stencil.png', '_depth.exr')):
        orientations = ['_N', '_S', '_E', '_W', '_U', '_D']

    # It the file is neither a RGB image nor a stencil or depth image, something went wrong
    else:
        return

    # Check if it's the last of the cubemaps
    if not orientations[-1] in file_path:
        return

    # Check if all other cubemaps have been created successfully and save the file paths
    cubemap_file_paths = []
    for orientation in orientations:
        cubemap_file_path = file_path.replace(orientations[-1], orientation)
        if os.path.exists(cubemap_file_path):
            cubemap_file_paths.append(cubemap_file_path)
        else:
            return

    # Stitch and blend the panorama
    pano_file_path = cubemap_file_paths[-1].replace(orientations[-1], '')
    rdc_to_data.Panorama.stitch_panorama(cubemap_file_paths, pano_file_path)


class Logger():

    def __init__(self, file_path):
        self.file_path = file_path

    def log(self, line):
        """
        Adds a line to the log file.

        Args:
            line (string): The line that should be added to the log file.

        Returns:
            None
        """

        # Open the file, get the current timestamp, and write the timestamp and line to the log file
        with open(self.file_path, 'a') as f:
            time_stamp = time.strftime('%Y%m%d-%H%M%S', time.localtime())
            f.write(time_stamp + '\t' + line + '\n')


class EventHandler(FileSystemEventHandler):

    def __init__(self, logger, data_dir):
        super().__init__()
        self.logger = logger
        self.data_dir = data_dir

    def on_modified(self, event):
        return

    def on_deleted(self, event):
        return
        
    def on_created(self, event):
        """
        Extracts the render, depth, and stencil frame if a RDC file has been created.

        Args:
            event (FileCreatedEvent): The file path of the render frame.

        Returns:
            None
        """

        # Check if a RGB, depth, or stencil image or a RDC capture file has been created
        if event.src_path.lower().endswith(('_rgb.jpg', '_stencil.png', '_depth.exr')):
            panorama_stitching(event.src_path)
            return
        elif not event.src_path.lower().endswith('.rdc'):
            return

        # Extract the file name of the created file from the path
        file_name = os.path.basename(event.src_path).split('.')[0]
        self.logger.log('[WatchDog]  The file "{0}" has been created.'.format(file_name))

        # Remove the frame number from the file name
        file_name = file_name.split('_')
        file_name = '_'.join(file_name[:-1])

        # Extract the data from the capture file
        rdc_to_data.convert_rdc(event.src_path, file_name)
        self.logger.log('[RenderDoc] Succesfully extracted all data from the capture.')

        # Delete the capture file
        os.remove(event.src_path)
        self.logger.log('[WatchDog]  The file "{0}" has been deleted.'.format(os.path.basename(event.src_path)))


class Initializer():

    def __init__(self, logger):
        self.logger = logger

    def initialize_renderdoc(self, gta_ins_dir, data_dir):
        """
        Initializes RenderDoc by activating the global hook.

        Args:
            gta_ins_dir (string): The main installation directory of GTA V.
            data_dir (string): The log directory.

        Returns:
            None
        """

        self.logger.log('[RenderDoc] Activating the global hook...')

        # Check if the global hook feature is available
        if not renderdoc.CanGlobalHook():
            self.logger.log('[RenderDoc] ERROR: The global hook can not be activated.')
            raise RuntimeError

        # Get the default capture options
        capture_options = renderdoc.GetDefaultCaptureOptions()

        # Activate the global hook
        gta_exe_path = os.path.join(gta_ins_dir, 'GTA5.exe')
        global_hook = renderdoc.StartGlobalHook(gta_exe_path, data_dir, capture_options)
        if not global_hook.OK():
            raise RuntimeError(global_hook.Message())

        # Check if the global hook is active
        if not renderdoc.IsGlobalHookActive():
            self.logger.log('[RenderDoc] ERROR: The global hook could not be activated.')
            raise RuntimeError

        self.logger.log('            Done.')


    def start_process(self, file_path, name):
        """
        Starts a process.

        Args:
            file_path (string): The file path of the executable application.
            name (string): The name of the application.

        Returns:
            process (subprocess.Popen): The started process.
        """

        self.logger.log('[System]    Starting {0}...'.format(name))

        process = subprocess.Popen([file_path])

        self.logger.log('            Done.')

        return process


    def terminate_process(self, process, name):
        """
        Terminates a process.

        Args:
            process (subprocess.Popen): The subprocess that should be terminated.
            name (string): The name of the application.

        Returns:
            None
        """

        self.logger.log('[System]    Closing {0}...'.format(name))

        process.terminate()

        self.logger.log('            Done.')


    def get_gta_pid(self):
        """
        Determines the PID of the GTA V process.

        Args:
            None

        Returns:
            None
        """

        self.logger.log('[System]    Searching for the PID of GTA...')

        # Start searching for the GTA V process
        gta_pid = -1
        while gta_pid == -1:

            # Get a list of all processes
            processes = wmi.WMI()

            # Check if GTA V is running
            for process in processes.Win32_Process():

                # Get the PID of GTA V
                if 'GTA5.exe' in process.Name:
                    gta_pid = process.ProcessId

            time.sleep(1)

        self.logger.log('            Done.')

        return gta_pid
        

    def inject_into_process(self, pid, data_dir):
        """
        Injects RenderDoc into the GTA V process.

        Args:
            pid (int): The PID of the GTA V process.
            data_dir (string): The log directory.

        Returns:
            None
        """

        self.logger.log('[RenderDoc] Injecting into the process of GTA...')

        # Get the default capture options
        capture_options = renderdoc.GetDefaultCaptureOptions()
        
        # Inject RenderDoc into the process
        injection = renderdoc.InjectIntoProcess(pid, [], data_dir, capture_options, False)
        if not injection.result.OK():
            raise RuntimeError(injection.result.Message())

        self.logger.log('            Done.')


def main():

    # Parse the input arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('--gta_ins_dir', '-g', help='Installation directory of GTA V', type=str, metavar='PATH',
                        default='C:\\Program Files\\Rockstar Games\\Grand Theft Auto V Legacy')
    parser.add_argument('--data_dir', '-d', help='Directory in which the data and logs are saved', type=str, metavar='PATH',
                        default='Data')
    parser.add_argument('--wbg_dir', '-w', help='Installation directory of WindowedBorderlessGaming', type=str, metavar='PATH',
                        default='WBG')
    args = parser.parse_args()

    # Check if all directories exist and if the directories contain the right files
    print('[OS]        Checking all directories given as input...')
    if not os.path.exists(args.gta_ins_dir):
        print('[OS]        ERROR: The path "{0}" does not exist. Please check your GTA installation.'.format(args.gta_ins_dir))
        print('[OS]        Usage: python generate_data.py -g GTA_INS_DIR -d DATA_DIR -w WBG_DIR')
        raise RuntimeError
    if not os.path.exists(os.path.join(args.gta_ins_dir, 'GTA5.exe')):
        print('[OS]        ERROR: The GTA installation path "{0}" does not contain "GTA5.exe". Please check your GTA installation.'.format(args.gta_ins_dir))
        print('[OS]        Usage: python generate_data.py -g GTA_INS_DIR -d DATA_DIR -w WBG_DIR')
        raise RuntimeError
    if not os.path.exists(args.data_dir):
        print('[OS]        ERROR: The path "{0}" does not exist. Please check your folder structure.'.format(args.data_dir))
        print('[OS]        Usage: python generate_data.py -g GTA_INS_DIR -d DATA_DIR -w WBG_DIR')
        raise RuntimeError
    if not os.path.exists(args.wbg_dir):
        print('[OS]        ERROR: The path "{0}" does not exist. Please check your initialization.'.format(args.wbg_dir))
        print('[OS]        Usage: python generate_data.py -g GTA_INS_DIR -d DATA_DIR -w WBG_DIR')
        raise RuntimeError
    print('            Done.')

    print('[WatchDog]  Starting and initializing GTA V, WBG, RenderDoc, and WatchDog...')

    # Create the directories if they don't exist yet
    if not os.path.exists(args.data_dir):
        os.mkdir(args.data_dir)
    if not os.path.exists(os.path.join(args.data_dir, 'ground-view')):
        os.mkdir(os.path.join(args.data_dir, 'ground-view'))
    if not os.path.exists(os.path.join(args.data_dir, 'drone-view')):
        os.mkdir(os.path.join(args.data_dir, 'drone-view'))
    if not os.path.exists(os.path.join(args.data_dir, 'satellite-view')):
        os.mkdir(os.path.join(args.data_dir, 'satellite-view'))

    # Create a new logger and initializer
    logger = Logger(os.path.join(args.data_dir, 'log.txt'))
    initializer = Initializer(logger)

    # Initialize RenderDoc
    initializer.initialize_renderdoc(args.gta_ins_dir, args.data_dir)

    # Start Windowed Borderless Gaming and GTA V
    process_wbg = initializer.start_process(os.path.join(args.wbg_dir, 'WindowedBorderlessGaming.exe'), 'WindowedBorderlessGaming')
    process_gta = initializer.start_process(os.path.join(args.gta_ins_dir, 'GTAVLauncher.exe'), 'Grand Theft Auto V')
    
    # Inject RenderDoc into the GTA V process
    pid = initializer.get_gta_pid()
    initializer.inject_into_process(pid, args.data_dir)

    # Start the WatchDog
    logger.log('[WatchDog]  Starting the watchdog for Renderdoc capture files.')
    file_observer = Observer()
    file_observer.schedule(EventHandler(logger, args.data_dir), path=args.data_dir, recursive=True)
    file_observer.start()
    logger.log('            Done.')

    print('            Done.')
    print('[WatchDog]  WatchDog is active. You may now start the data generation process.')

    # Terminate all processes if the script is terminated
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        file_observer.stop()
    file_observer.join()
    initializer.terminate_process(process_wbg, 'WindowedBorderlessGaming')
    renderdoc.StopGlobalHook()


if __name__ == '__main__':
    main()