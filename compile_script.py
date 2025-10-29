import argparse
import os
import re
import shutil
import subprocess


# Directories in which the Data and Script files are saved
DIRECTORY_DATA = os.path.join(os.getcwd(), 'Data')
DIRECTORY_SCRIPT = os.path.join(os.getcwd(), 'Script')


def replace_in_file(file_path, old_pattern, new_pattern):
    """
    Replaces a REGEX pattern inside a file with a new pattern or string.

    Args:
        file_path (string): The file path.
        old_pattern (string): The pattern that should be replaced.
        new_pattern (string): The pattern that the old pattern should be replaced with.

    Returns:
        None
    """
    
    # Open the file and read the data
    with open(file_path, 'r', encoding='utf-8') as f:
        file = f.read()

    # Generate the pattern that should be replaced
    re_pattern = re.compile(old_pattern)

    # Replace the pattern in the file
    file = re_pattern.sub(new_pattern, file)

    # Open the file and write the data
    with open(file_path, 'w+', encoding='utf-8') as f:
        f.write(file)


def initialize_scripts(directory_script):
    """
    Replaces the versions and paths in the scripts with the correct ones, compiles the script, and copies it to the GTA V directory.

    Args:
        directory_script (string): The folder path of the GTA V scripts directory.

    Returns:
        None
    """

    # Create the directory
    if not os.path.exists(directory_script):
        os.mkdir(directory_script)

    # Get the new API version from the compiled header file
    with open(os.path.join(DIRECTORY_SCRIPT, 'RenderDocHeader.cs'), 'r', encoding='utf-8') as f:
        file = f.read()
    re_pattern = r'RENDERDOC_API_(\d+_\d+_\d+)'
    match = re.search(re_pattern, file)
    if not match:
        print('[Scripts]   ERROR: The new API version could not be found.')
        raise RuntimeError
    new_api_version = match.groups()[0]

    # Replace the API version in the scripts
    print('[Scripts]   Replacing the API version with v{0} in the scripts...'.format(new_api_version))
    replace_in_file(os.path.join(DIRECTORY_SCRIPT, 'RenderDoc.cs'), r'RENDERDOC_API_\d+_\d+_\d+', 'RENDERDOC_API_' + new_api_version)
    print('            Done.')

    # Replace the log directory in the scripts
    print('[Scripts]   Replacing the log directroy with {0} in the scripts...'.format(os.getcwd()))
    replace_in_file(os.path.join(DIRECTORY_SCRIPT, 'DataGenerator.cs'), r'data_path_orig = ".+";', 'data_path_orig = "{0}";'.format(DIRECTORY_DATA.replace('\\', '\\\\\\\\') + '\\\\\\\\'))
    print('            Done.')

    # Compile the script
    print('            Compiling the script...')
    script_sln_path = os.path.join(DIRECTORY_SCRIPT, 'DataGeneration.sln')
    result = subprocess.run(['MSBuild',
                             script_sln_path,
                             '-p:Configuration=Release',
                             '-p:Platform=x64',
                             '-p:AllowUnsafeBlocks=true'],
                            capture_output=True, text=True)
    if result.returncode != 0:
        print('[RenderDoc] ERROR: {0}'.format(result.stdout))
        raise RuntimeError
    print('            Done.')

    # Copy the compiled DataGeneration.dll to the GTA directory
    print('            Copying the compiled DataGeneration.dll to the GTA directory...')
    shutil.copy(os.path.join(DIRECTORY_SCRIPT, 'bin', 'x64', 'Release', 'DataGeneration.dll'), directory_script)
    print('            Done.')


def main():

    # Parse the input arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('--gta_ins_dir', '-g', help='Installation directory of GTA V', type=str, metavar='PATH',
                        default='C:\\Program Files\\Rockstar Games\\Grand Theft Auto V Legacy')
    args = parser.parse_args()

    # Check if all directories exist and if the directories contain the right files
    print('[OS]        Checking all directories given as input...')
    if not os.path.exists(args.gta_ins_dir):
        print('[OS]        ERROR: The path "{0}" does not exist. Please check your GTA installation.'.format(args.gta_ins_dir))
        print('[OS]        Usage: python compile_script.py -g GTA_INS_DIR')
        raise RuntimeError
    if not os.path.exists(os.path.join(args.gta_ins_dir, 'GTA5.exe')):
        print('[OS]        ERROR: The GTA installation path "{0}" does not contain "GTA5.exe". Please check your GTA installation.'.format(args.gta_ins_dir))
        print('[OS]        Usage: python compile_script.py -g GTA_INS_DIR')
        raise RuntimeError
    print('            Done.')

    # Initialize the scripts
    initialize_scripts(os.path.join(args.gta_ins_dir, 'scripts'))


if __name__ == '__main__':
    main()