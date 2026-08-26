import logging
import re
import shutil
import subprocess

from pathlib import Path

from utils import check_path_exists, configure_logging, find_vs_tool, load_config, replace_in_file


# Load the config file
CONFIG = load_config(Path('config.toml'))

# Get the logger
LOGGER = logging.getLogger('compile_script')


def initialize_scripts() -> None:
    """
    Replaces the versions and paths in the scripts with the correct ones, compiles the script, and copies the compiled
    script, its dependencies, and the config file to the GTA V directory.

    Args:
        None

    Returns:
        None
    """

    # Get the new API version from the RenderDoc header file
    LOGGER.info('Reading the new API version from the RenderDoc header file.')
    file = (Path(CONFIG['Paths']['Scripts']) / 'RenderDocHeader.cs').read_text(encoding='utf-8')
    re_pattern = r'RENDERDOC_API_(\d+_\d+_\d+)'
    match = re.search(re_pattern, file)
    if not match:
        LOGGER.info('The new API version could not be found in the RenderDoc header file.')
        raise RuntimeError('The new API version could not be found in the RenderDoc header file.')
    new_api_version = match.group(1)

    # Replace the API version in the scripts
    LOGGER.info(f'Replacing the API version with v{new_api_version} in the script.')
    replace_in_file(Path(CONFIG['Paths']['Scripts']) / 'RenderDoc.cs', r'RENDERDOC_API_\d+_\d+_\d+', f'RENDERDOC_API_{new_api_version}')
    replace_in_file(Path(CONFIG['Paths']['Scripts']) / 'RenderDoc.cs', r'eRENDERDOC_API_Version_\d+_\d+_\d+', f'eRENDERDOC_API_Version_{new_api_version}')

    # Compile the script
    LOGGER.info('Compiling the script.')
    script_sln_path = Path(CONFIG['Paths']['Scripts']) / 'DataGeneration.sln'
    result = subprocess.run([find_vs_tool(Path(CONFIG['Paths']['VS']), 'Current/bin/MSBuild.exe'),
                             script_sln_path,
                             '-p:Configuration=Release',
                             '-p:Platform=x64',
                             '-p:AllowUnsafeBlocks=true'],
                            capture_output=True, text=True)
    if result.returncode != 0:
        LOGGER.error(f'An error occurred during the compilation of the script. Error: {result.stdout}')
        raise RuntimeError(f'An error occurred during the compilation of the script. Error: {result.stdout}')

    # Create the directory for the scripts if it doesn't exist yet
    (Path(CONFIG['Paths']['GTAV']) / 'scripts').mkdir(parents=True, exist_ok=True)

    # Copy the compiled DataGeneration.dll and its NuGet dependencies to the GTA directory
    LOGGER.info('Copying the compiled script and its dependencies to the GTA V directory.')
    dll_files = [
        'DataGeneration.dll',
        'Microsoft.Bcl.AsyncInterfaces.dll',
        'System.Buffers.dll',
        'System.Collections.Immutable.dll',
        'System.IO.Pipelines.dll',
        'System.Memory.dll',
        'System.Numerics.Vectors.dll',
        'System.Runtime.CompilerServices.Unsafe.dll',
        'System.Text.Encodings.Web.dll',
        'System.Text.Json.dll',
        'System.Threading.Tasks.Extensions.dll',
        'Tomlyn.dll'
    ]
    for dll_file in dll_files:
        shutil.copy(Path(CONFIG['Paths']['Scripts']) / 'bin' / 'x64' / 'Release' / dll_file, Path(CONFIG['Paths']['GTAV']) / 'scripts')

    # Copy the config file to the GTA directory
    shutil.copy(Path('config.toml'), Path(CONFIG['Paths']['GTAV']))


def main():

    # Configure the logging
    configure_logging(Path(CONFIG['Paths']['Logs']), CONFIG['Logging']['Level'])

    # Check if all directories exist and if the directories contain the right files
    check_path_exists(Path(CONFIG['Paths']['GTAV']), 'Check the GTA V directories or the config file.')
    check_path_exists(Path(CONFIG['Paths']['GTAV']) / Path('GTA5.exe'), 'Check the GTA V directories or the config file.')

    # Initialize the scripts
    initialize_scripts()


if __name__ == '__main__':
    main()