import gzip
import json
import logging
import re
import shutil
import subprocess
import sys
import urllib.request

from html.parser import HTMLParser
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

from compile_script import initialize_scripts
from utils import check_path_exists, configure_logging, find_vs_tool, load_config, replace_in_file


# Load the config file
CONFIG = load_config(Path('config.toml'))

# Get the logger
LOGGER = logging.getLogger('initialize_project')

# Headers for retrieving the download links of the latest version of ScriptHookV
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:134.0) Gecko/20100101 Firefox/134.0',
           'Referer': CONFIG['URLs']['WebsiteScriptHookV']}


class HeaderTranslator:

    def strip_down_header(header_file: str) -> str:
        """
        Removes superfluous commands from the header file.

        Args:
            header_file (str): The header file including superfluous commands.

        Returns:
            header_file (str): The header file without superfluous commands.
        """

        # Remove all comments and preprocessor statements
        re_pattern  = re.compile(r'\/\/.*?$|\/\*.*?\*\/|(#ifdef|#if).*?(#endif)|(#define|#pragma)(\s+\S+\s+\\.*?\{.*?\}|.*?$)', re.DOTALL | re.MULTILINE)
        header_file = re_pattern.sub('', header_file)

        # Remove the typedefs for older API versions
        re_pattern  = re.compile(r'typedef \w+[^\(] (?:\*|)\w+;', re.MULTILINE)
        header_file = re_pattern.sub('', header_file)

        # Remove all empty lines
        re_pattern  = re.compile(r'^\s*\n', re.MULTILINE)
        header_file = re_pattern.sub('', header_file)

        # Remove all additional line breaks
        re_pattern  = re.compile(r'typedef[^\n]*?\(RENDERDOC_CC\s*\*[^\n]*?\)\(.*?\);', re.DOTALL)
        header_file = re_pattern.sub(lambda match: re.sub(r'\s*\n\s*', ' ', match.group(0)), header_file)

        return header_file


    def translate_header(header_file: str) -> str:
        """
        Translates the header file from C to C#.

        Args:
            header_file (str): The header file in C.

        Returns:
            header_file (str): The header file in C#.
        """

        # Translate top-level unions into C# structs
        _translate_union = lambda m: '[StructLayout(LayoutKind.Explicit)]\npublic unsafe struct %s\n{\n%s\n}' % (
            m.group(1),
            '\n'.join(
                '  [FieldOffset(0)] public ' + re.sub(
                    r'^(\S+)\s+(\w+)(\[\d+\]);$', r'fixed \1 \2\3;',
                    re.sub(r'(?:const\s+char|char)\s*\*\s*(\w+)\s*;', r'IntPtr \1;', line.strip())
                )
                for line in m.group(2).strip('\n').split('\n') if line.strip()
            )
        )
        re_pattern  = re.compile(r'typedef union (\w+)\s*\{(.*?)\}\s*\1;', re.DOTALL)
        header_file = re_pattern.sub(_translate_union, header_file)

        # Translate the enum sections
        re_pattern  = re.compile(r'(?:typedef enum)(.*?^\})(?:.*?;$)', re.DOTALL | re.MULTILINE)
        header_file = re_pattern.sub(r'public enum\1', header_file)

        # Remove the unions from the structs
        re_pattern  = re.compile(r'(?:union\n\s*\{\n.*?;$\s*)(.*?;$)(?:\s*\};$)', re.MULTILINE)
        header_file = re_pattern.sub(r'\1', header_file)

        # Add public to each line of the struct
        re_pattern  = re.compile(r'(^\s+)(\S+\s+\S+;$)', re.MULTILINE)
        header_file = re_pattern.sub(r'\1public \2', header_file)

        # Translate the struct sections
        re_pattern  = re.compile(r'(?:typedef struct)(.*?)(?:\}.*?;$)', re.DOTALL | re.MULTILINE)
        header_file = re_pattern.sub(r'[StructLayout(LayoutKind.Sequential)]\npublic unsafe struct\1}', header_file)

        # Translate the data types
        header_file = re.sub(r'~0U', r'-1', header_file)
        header_file = re.sub(r'uint32_t', r'uint', header_file)
        header_file = re.sub(r'uint64_t', r'ulong', header_file)
        header_file = re.sub(r'int32_t', r'int', header_file)
        header_file = re.sub(r'int64_t', r'long', header_file)
        header_file = re.sub(r'const char \*\(', r'IntPtr(', header_file)
        header_file = re.sub(r'(const char|char) \*', r'[MarshalAs(UnmanagedType.LPStr)] string ', header_file)
        header_file = re.sub(r'RENDERDOC_DevicePointer', r'IntPtr', header_file)
        header_file = re.sub(r'RENDERDOC_WindowHandle', r'IntPtr', header_file)
        header_file = re.sub(r'\(void\)', r'()', header_file)

        # Remove all other const data types
        header_file = re.sub(r'\bconst\s+', '', header_file)

        # Translate object and string
        header_file = re.sub(r'\*object\b', r'*obj', header_file)
        header_file = re.sub(r'IntPtr string;', r'IntPtr str;', header_file)

        # Translate the delegate sections
        re_pattern  = re.compile(r'(?:typedef )(.+?)(?:\(RENDERDOC_CC \*)(\S+)(?:\)\()(.*?)(?:\);$)', re.MULTILINE)
        header_file = re_pattern.sub(r'public unsafe delegate \1 \2(\3);', header_file)

        # Add a tab to each line
        re_pattern  = re.compile(r'^(.*?)$', re.MULTILINE)
        header_file = re_pattern.sub(r'  \1', header_file)

        # Add the imports and namespace
        header_file = 'using System;\nusing System.Runtime.InteropServices;\nnamespace DataGeneration\n{\n' + header_file + '\n}'
        header_file = re.sub(r'  \n\}$', r'}', header_file)

        return header_file


    def c_to_cs(file_path_c: Path, file_path_cs: Path) -> None:
        """
        Translates the header file from C to C#.

        Args:
            file_path_c (Path): The file path to the header file in C.
            file_path_cs (Path): The file path to the header file in C#.

        Returns:
            None
        """

        # Read the data from the header file in C
        header_file = file_path_c.read_text(encoding='utf-8')

        # Translate the header file to C#
        header_file = HeaderTranslator.strip_down_header(header_file)
        header_file = HeaderTranslator.translate_header(header_file)

        # Write the data to the header file in C#
        file_path_cs.write_text(header_file, encoding='utf-8')


class HTMLParserLinks(HTMLParser):

    def __init__(self, name):
        super().__init__()
        self.name = name
        self.link = ''
        self.latest_version = ''

    def handle_starttag(self, tag: str, attributes: str) -> None:
        """
        Sets the latest version and link to the software based on the name of the software and contents of the website.

        Args:
            tag (str): The start tag of the block.
            attributes (str): The attributes of the block.

        Returns:
            None
        """

        # Only handle 'a' tags 
        if tag != 'a':
            return

        # Iterate over all possible links
        for attribute, value in attributes:

            # End the search if the link has been found
            if self.link:
                return

            # Skip the attributes that are no link
            if attribute != 'href':
                continue

            # Get the download link for Python
            if self.name == 'Python32':
                self.latest_version = sys.version.split(' ')[0]
                self.link = CONFIG['URLs']['DownloadPython32'].replace('?', self.latest_version)
            if self.name == 'Python64':
                self.latest_version = sys.version.split(' ')[0]
                self.link = CONFIG['URLs']['DownloadPython64'].replace('?', self.latest_version)

            # Get the download link for RenderDoc
            if self.name == 'RenderDoc' and '/baldurk/renderdoc/releases/tag/' in value:
                self.latest_version = value.split('/')[-1]
                self.link = CONFIG['URLs']['DownloadRenderDoc'].replace('?', self.latest_version)

            # Get the download link for ScriptHookV
            if self.name == 'ScriptHookV' and 'zip' in value and not 'SDK' in value:
                self.latest_version = '_'.join(value.split('_')[1:]).replace('.zip', '').replace('/', '_')
                self.link = CONFIG['URLs']['DownloadScriptHookV'].replace('?', self.latest_version)

            # Get the download link for ScriptHookVDotNet
            if self.name == 'ScriptHookVDotNet' and 'releases/tag/' in value:
                self.latest_version = value.split('/')[-1]
                self.link = CONFIG['URLs']['DownloadScriptHookVDotNet'].replace('?', self.latest_version)

            # Get the download link for WBG
            if self.name == 'WBG' and 'downloading' in value:
                self.latest_version = value.split('=')[-1]
                self.link = CONFIG['URLs']['DownloadWBG'] + self.latest_version


def get_download_link_github(github_api_url: str, name: str):
    """
    Retrieves the download link and latest version given the GitHub API URL.

    Args:
        github_api_url (str): The GitHub API URL.
        name (str): The name of the software.

    Returns:
        link (str): The download link of the software.
        latest_version (str): The latest version of the software.
    """

    # Request the URL with a suitable request header
    request = urllib.request.Request(github_api_url, headers=HEADERS)
    response = urllib.request.urlopen(request)
    if not response.status == 200:
        LOGGER.error(f'The website "{github_api_url}" could not be requested.')
        raise RuntimeError(f'The website "{github_api_url}" could not be requested.')

    # Decode the content of the website
    data = json.loads(response.read().decode('utf-8'))

    # Retrieve the download link for the latest version of RenderDoc
    latest_version = data['tag_name']
    if name == 'RenderDoc':
        link = CONFIG['URLs']['DownloadRenderDoc'].replace('?', latest_version)

    return link, latest_version


def get_download_link(website: str, name: str) -> tuple[str, str]:
    """
    Retrieves the download link and latest version given the name of the software and its website.

    Args:
        website (str): The website that contains the download link.
        name (str): The name of the software.

    Returns:
        link (str): The download link of the software.
        latest_version (str): The latest version of the software.
    """

    # Request the URL with a suitable request header
    request = urllib.request.Request(website, headers=HEADERS)
    response = urllib.request.urlopen(request)
    if not response.status == 200:
        LOGGER.error(f'The website "{website}" could not be requested.')
        raise RuntimeError(f'The website "{website}" could not be requested.')

    # Decode the content of the website
    if response.getheader('Content-Encoding') == 'gzip':
        content = gzip.decompress(bytearray(response.read())).decode('utf-8')
    else:
        content = response.read().decode('utf-8')

    # Retrieve the download link for the latest version of Python, ScriptHookV, ScriptHookVDotNet, or WBG
    parser = HTMLParserLinks(name)
    parser.feed(content)
    if not parser.link:
        LOGGER.error(f'The website "{website}" does not contain any links.')
        raise RuntimeError(f'The website "{website}" does not contain any links.')
    link = parser.link
    latest_version = parser.latest_version

    return link, latest_version


def download_and_extract_zip(name: str, website: str, directory: Path) -> None:
    """
    Retrieves the download link and latest version of a software and downloads it.

    Args:
        name (str): The name of the software.
        website (str): The website that contains the download link.
        directory (Path): The folder path to which the software should be downloaded and unpacked.

    Returns:
        None
    """

    # Get the download link
    if name == 'RenderDoc':
        download_link, latest_version = get_download_link_github(website, name)
    else:
        download_link, latest_version = get_download_link(website, name)

    # Download the zip file
    request = urllib.request.Request(download_link, headers=HEADERS)
    response = urllib.request.urlopen(request)
    if not response.status == 200:
        LOGGER.error(f'The file "{download_link}" could not be requested.')
        raise RuntimeError(f'The file "{download_link}" could not be requested.')

    # Unpack the files
    zipfile = ZipFile(BytesIO(response.read()))
    zipfile.extractall(path=directory)


def initialize_scripthookv() -> None:
    """
    Initializes ScriptHookV by downloading the latest version and moving it to the GTA V directory.

    Args:
        None

    Returns:
        None
    """
    
    # Create the directory if it doesn't exist yet
    Path(CONFIG['TmpPaths']['ScriptHookV']).mkdir(parents=True, exist_ok=True)

    # Download the latest version of the mod
    LOGGER.info('Downloading and unpacking the latest version of ScriptHookV.')
    download_and_extract_zip('ScriptHookV', CONFIG['URLs']['WebsiteScriptHookV'], Path(CONFIG['TmpPaths']['ScriptHookV']))

    # Copy the files to the GTA V directory
    LOGGER.info('Copying the ScriptHookV files to the GTA V directory.')
    for file in CONFIG['Files']['ScriptHookV']:
        file_path = Path(CONFIG['TmpPaths']['ScriptHookV']) / Path('bin') / Path(file)
        shutil.copy(file_path, Path(CONFIG['Paths']['GTAV']))

    # Delete the downloaded files
    LOGGER.info('Deleting the downloaded ScriptHookV files and TMP directory.')
    shutil.rmtree(CONFIG['TmpPaths']['ScriptHookV'])


def initialize_scripthookvdotnet() -> None:
    """
    Initializes ScriptHookVDotNet by downloading the latest version and moving it to the GTA V directory.

    Args:
        None

    Returns:
        None
    """

    # Create the directory if it doesn't exist yet
    Path(CONFIG['TmpPaths']['ScriptHookVDotNet']).mkdir(parents=True, exist_ok=True)

    # Download the latest version of the mod
    LOGGER.info('Downloading and unpacking the latest version of ScriptHookVDotNet.')
    download_and_extract_zip('ScriptHookVDotNet', CONFIG['URLs']['WebsiteScriptHookVDotNet'], Path(CONFIG['TmpPaths']['ScriptHookVDotNet']))

    # Change the keybindings in the ini file
    ini_file_path = Path(CONFIG['TmpPaths']['ScriptHookVDotNet']) / 'ScriptHookVDotNet.ini'
    ini_file = ini_file_path.read_text(encoding='utf-8')
    ini_file = ini_file.replace('ConsoleKeyBinding=F4', 'ConsoleKeyBinding=F5')
    ini_file_path.write_text(ini_file, encoding='utf-8')

    # Copy the files to the GTA V directory
    LOGGER.info('Copying the ScriptHookVDotNet files to the GTA V directory.')
    for file in CONFIG['Files']['ScriptHookVDotNet']:
        file_path = Path(CONFIG['TmpPaths']['ScriptHookVDotNet']) / Path(file)
        shutil.copy(file_path, Path(CONFIG['Paths']['GTAV']))

    # Delete the downloaded files
    LOGGER.info('Deleting the downloaded ScriptHookV files and TMP directory.')
    shutil.rmtree(CONFIG['TmpPaths']['ScriptHookVDotNet'])


def initialize_wbg() -> None:
    """
    Initializes Windowed Borderless Gaming by downloading the latest version, replacing the config file, and setting
    the resolution in the config file.

    Args:
        None

    Returns:
        None
    """

    # Create the directory if it doesn't exist yet
    Path(CONFIG['Paths']['WBG']).mkdir(parents=True, exist_ok=True)

    # Download the latest version of WBG
    LOGGER.info('Downloading and unpacking the latest version of WBG.')
    download_and_extract_zip('WBG', CONFIG['URLs']['WebsiteWBG'], Path(CONFIG['Paths']['WBG']))

    # Override the config files in the WBG directory
    LOGGER.info('Overriding the WBG files in the WBG directory.')
    for file in CONFIG['Files']['WBG']:
        file_path = Path(CONFIG['Paths']['Configs']) / Path(file)
        shutil.copy(file_path, Path(CONFIG['Paths']['WBG']))

    # Set the resolution in the WBG config file
    LOGGER.info('Setting the resolution in the WBG config file.')
    resolution = CONFIG['Generation']['Resolution']
    wbg_config_path = Path(CONFIG['Paths']['WBG']) / 'config.ini'
    replace_in_file(wbg_config_path, r'(?m)^DefaultDeskTopWidth=\d+$', f'DefaultDeskTopWidth={resolution}')
    replace_in_file(wbg_config_path, r'(?m)^DefaultDeskTopHeight=\d+$', f'DefaultDeskTopHeight={resolution}')
    replace_in_file(wbg_config_path, r'(?m)^Width=\d+$', f'Width={resolution}')
    replace_in_file(wbg_config_path, r'(?m)^Height=\d+$', f'Height={resolution}')


def initialize_renderdoc() -> None:
    """
    Initializes RenderDoc by downloading the latest version of RenderDoc and Python, modifying the files according to the versions,
    compiling RenderDoc, and moving it to the GTA V directory and its own directory.

    Args:
        None

    Returns:
        None
    """

    # Create the directories if they don't exist yet
    (Path(CONFIG['TmpPaths']['RenderDoc']) / Path('Python32')).mkdir(parents=True, exist_ok=True)
    (Path(CONFIG['TmpPaths']['RenderDoc']) / Path('Python64')).mkdir(parents=True, exist_ok=True)
    (Path(CONFIG['TmpPaths']['RenderDoc']) / Path('RenderDoc')).mkdir(parents=True, exist_ok=True)

    # Get the current Python version and directories
    python_version = sys.version.split(' ')[0]
    python_version_short = ''.join(python_version.split('.')[:2])
    python_header_directory = Path(sys.executable).parent / 'include'

    # Download the Python and RenderDoc files
    LOGGER.info(f'Downloading and unpacking the Python embeddable packages for v{python_version}.')
    download_and_extract_zip('Python32', CONFIG['URLs']['WebsitePython'], Path(CONFIG['TmpPaths']['RenderDoc']) / Path('Python32'))
    download_and_extract_zip('Python64', CONFIG['URLs']['WebsitePython'], Path(CONFIG['TmpPaths']['RenderDoc']) / Path('Python64'))
    LOGGER.info('Downloading and unpacking the latest version of RenderDoc source code.')
    download_and_extract_zip('RenderDoc', CONFIG['URLs']['WebsiteRenderDoc'], Path(CONFIG['TmpPaths']['RenderDoc']) / Path('RenderDoc'))

    # Get the RenderDoc directories
    renderdoc_main_directory = next((Path(CONFIG['TmpPaths']['RenderDoc']) / Path('RenderDoc')).iterdir())
    renderdoc_sln_path = renderdoc_main_directory / 'renderdoc.sln'
    renderdoc_qrenderdoc_directory = renderdoc_main_directory / 'qrenderdoc'
    renderdoc_natvis_path = next(renderdoc_qrenderdoc_directory.glob('*.natvis'))
    renderdoc_vcxproj_path = renderdoc_qrenderdoc_directory / 'qrenderdoc_local.vcxproj'
    renderdoc_python_props_path = renderdoc_qrenderdoc_directory / 'Code' / 'pyrenderdoc' / 'python.props'
    renderdoc_qrenderdoc_pro_path = renderdoc_qrenderdoc_directory / 'qrenderdoc.pro'
    renderdoc_python_directory = renderdoc_qrenderdoc_directory / '3rdparty' / 'python'
    renderdoc_python_header_directory = renderdoc_qrenderdoc_directory / '3rdparty' / 'python' / 'include'
    renderdoc_compiled_x86_directory = renderdoc_main_directory / 'Win32' / 'Release'
    renderdoc_compiled_x64_directory = renderdoc_main_directory / 'x64' / 'Release'
    renderdoc_compiled_renderdoc_dll_path = renderdoc_compiled_x64_directory / 'renderdoc.dll'
    renderdoc_compiled_renderdoc_header_path = renderdoc_compiled_x64_directory / 'renderdoc_app.h'
    renderdoc_compiled_renderdoc_pyd_path = renderdoc_compiled_x64_directory / 'pymodules' / 'renderdoc.pyd'
    renderdoc_compiled_qrenderdoc_pyd_path = renderdoc_compiled_x64_directory / 'pymodules' / 'qrenderdoc.pyd'

    # Get the old Python version
    python_version_old = next(renderdoc_qrenderdoc_directory.glob('*.natvis')).stem.removeprefix('python')
    
    # Replace the Python version in the RenderDoc files
    LOGGER.info(f'Replacing the Python version v{python_version_old} with v{python_version_short} in the RenderDoc source files.')
    replace_in_file(renderdoc_natvis_path, r'python\d+', f'python{python_version_short}')
    replace_in_file(renderdoc_vcxproj_path, r'python\d+\.natvis', f'python{python_version_short}.natvis')
    replace_in_file(renderdoc_python_props_path, r'<PythonMajorMinor>\d+</PythonMajorMinor>', f'<PythonMajorMinor>{python_version_short}</PythonMajorMinor>')
    replace_in_file(renderdoc_python_props_path, r'python\d+', f'python{python_version_short}')
    replace_in_file(renderdoc_qrenderdoc_pro_path, r'python\d+\.lib', f'python{python_version_short}.lib')
    renderdoc_natvis_path.rename(
        renderdoc_natvis_path.with_stem(
            renderdoc_natvis_path.stem.replace(
                f'python{python_version_old}',
                f'python{python_version_short}'
            )
        )
    )

    # Copy the Python header files to the RenderDoc directory
    LOGGER.info('Copying the Python header files to the RenderDoc directory.')
    shutil.rmtree(renderdoc_python_header_directory)
    shutil.copytree(python_header_directory, renderdoc_python_header_directory)

    # Set up the Python files for each platform
    for platform in ['32', '64']:

        # Directories depending on the platform
        directory_platform = 'Win32' if platform == '32' else 'x64'
        renderdoc_python_x86_x64_directory = renderdoc_qrenderdoc_directory / '3rdparty' / 'python' / directory_platform
        renderdoc_python_dll_path = renderdoc_python_x86_x64_directory / f'python{python_version_short}.dll'

        # Copy the Python embeddable package to the RenderDoc directory
        LOGGER.info('Copying the Python embeddable package to the RenderDoc directory.')
        shutil.copy(Path(CONFIG['TmpPaths']['RenderDoc']) / f'Python{platform}' / f'python{python_version_short}.zip', renderdoc_python_directory)
        for file in renderdoc_python_directory.glob(f'*{python_version_old}*'):
            file.unlink()
        file_path = Path(CONFIG['TmpPaths']['RenderDoc']) / f'Python{platform}' / f'python{python_version_short}.dll'
        shutil.copy(file_path, renderdoc_python_x86_x64_directory)
        file_path = Path(CONFIG['TmpPaths']['RenderDoc']) / f'Python{platform}' / '_ctypes.pyd'
        shutil.copy(file_path, renderdoc_python_x86_x64_directory)
        for file in renderdoc_python_x86_x64_directory.glob(f'*{python_version_old}*'):
            file.unlink()

        # Create the pythonXX.def from the pythonXX.dll
        LOGGER.info(f'Generating the python{python_version_short}.def file from the python{python_version_short}.dll file.')
        result = subprocess.run([find_vs_tool(Path(CONFIG['Paths']['VS']), 'Hostx64/x64/dumpbin.exe'),
                                 '/exports',
                                 renderdoc_python_dll_path],
                                 capture_output=True,
                                 text=True)
        if result.returncode != 0:
            LOGGER.error(f'An error occurred during the generation of the python{python_version_short}.def file. Error: {result.stdout}')
            raise RuntimeError(result.stdout)

        # Create the pythonXX.lib from the pythonXX.def
        LOGGER.info(f'Generating the python{python_version_short}.lib file from the python{python_version_short}.def file.')
        def_file = result.stdout
        re_pattern = re.compile(r'^(\s+\d+\s+[\dA-F]+\s[\dA-F]+\s)(\w+)(\n)', re.MULTILINE)
        functions = re_pattern.findall(def_file)
        def_file = 'EXPORTS\n' + '\n'.join([function[1] for function in functions])
        renderdoc_python_dll_path.with_suffix('.def').write_text(def_file, encoding='utf-8')
        result = subprocess.run([find_vs_tool(Path(CONFIG['Paths']['VS']), 'Hostx64/x64/lib.exe'),
                                 f'/def:{renderdoc_python_dll_path.with_suffix('.def')}',
                                 f'/machine:{'x86' if platform == '32' else 'x64'}',
                                 f'/out:{renderdoc_python_dll_path.with_suffix('.lib')}'],
                                 stdout=subprocess.DEVNULL)
        if result.returncode != 0:
            LOGGER.error(f'An error occurred during the generation of the python{python_version_short}.lib file. Error: {result.stdout}')
            raise RuntimeError(result.stdout)

    # Update the Platform Toolset version for each vcxproj file and surpress all deprecation warnings
    toolset_version = next((Path(CONFIG['Paths']['VS']) / 'VC' / 'Auxiliary' / 'Build').glob('Microsoft.VCToolsVersion.v*.default.txt')).stem.split('.')[2]
    LOGGER.info(f'Updating the toolset version in all .vcxproj files to {toolset_version}.')
    for file in Path.cwd().rglob('*.vcxproj'):
        replace_in_file(file, r'(<PlatformTool[sS]et>)v\d+(<\/PlatformTool[sS]et>)', r'\1' + toolset_version + r'\2')
        replace_in_file(file, '<PreprocessorDefinitions>', '<PreprocessorDefinitions>_SILENCE_STDEXT_ARR_ITERS_DEPRECATION_WARNING;')

    # Compile RenderDoc for each platform
    for platform in ['x86', 'x64']:
        LOGGER.info(f'Compiling the RenderDoc source code for platform {platform}. This may take a while.')
        result = subprocess.run([find_vs_tool(Path(CONFIG['Paths']['VS']), 'Current/bin/MSBuild.exe'),
                                 renderdoc_sln_path,
                                 '-p:Configuration=Release',
                                 f'-p:Platform={platform}'],
                                 capture_output=True, text=True)
        if result.returncode != 0:
            LOGGER.error(f'An error occurred during the compilation of the RenderDoc source code for platform {platform}. Error: {result.stdout}')
            raise RuntimeError(f'An error occurred during the compilation of the RenderDoc source code for platform {platform}. Error: {result.stdout}')

    # Create the directory for compiled x86 files
    (renderdoc_compiled_x64_directory / 'x86').mkdir(parents=True, exist_ok=True)

    # Copy the compiled files to the directories
    LOGGER.info('Copying the compiled RenderDoc files to the directories.')
    shutil.copy(renderdoc_compiled_renderdoc_dll_path, CONFIG['Paths']['Scripts'])
    shutil.copy(renderdoc_compiled_renderdoc_pyd_path, renderdoc_compiled_x64_directory)
    shutil.copy(renderdoc_compiled_qrenderdoc_pyd_path, renderdoc_compiled_x64_directory)
    for extension in ['*.dll', '*.json', '*.exe', '*.yes']:
        for file in renderdoc_compiled_x86_directory.glob(extension):
            shutil.copy(file, renderdoc_compiled_x64_directory / 'x86')

    # Translate the Renderdoc header file to C# and copy it to the DataGeneration directory
    LOGGER.info('Translating the RenderDoc header file to C# and copying it to the script directory.')
    file_path_header_c  = renderdoc_compiled_renderdoc_header_path
    file_path_header_cs = Path(CONFIG['Paths']['Scripts']) / 'RenderDocHeader.cs'
    HeaderTranslator.c_to_cs(file_path_header_c, file_path_header_cs)

    # Remove the existing RenderDoc directory in %PROGRAMFILES%
    LOGGER.info('Copying the compiled RenderDoc files to its %PROGRAMFILES% directory.')
    if Path(CONFIG['Paths']['RenderDoc']).is_dir():
        try:
            shutil.rmtree(Path(CONFIG['Paths']['RenderDoc']))
        except (PermissionError, OSError):
            LOGGER.warning(f'Failed to remove the existing RenderDoc directory "{Path(CONFIG['Paths']['RenderDoc'])}".')

    # Remove the compiled RenderDoc files that are not required
    if (renderdoc_compiled_x64_directory / 'obj').is_dir():
        shutil.rmtree(renderdoc_compiled_x64_directory / 'obj')
    for pattern in ['*.exp', '*.lib', '*.pdb']:
        for file in renderdoc_compiled_x64_directory.glob(pattern):
            file.unlink()

    # Move the RenderDoc files to the RenderDoc directory in %PROGRAMFILES%
    Path(CONFIG['Paths']['RenderDoc']).mkdir(parents=True, exist_ok=True)
    for source in renderdoc_compiled_x64_directory.rglob('*'):
        destination = Path(CONFIG['Paths']['RenderDoc']) / source.relative_to(renderdoc_compiled_x64_directory)
        try:
            if source.is_dir():
                destination.mkdir(parents=True, exist_ok=True)
            else:
                destination.parent.mkdir(parents=True, exist_ok=True)
                if destination.exists():
                    if destination.is_dir():
                        shutil.rmtree(destination)
                    else:
                        destination.unlink()
                shutil.move(source, destination)
        except Exception:
            LOGGER.warning(f'Failed to move the file "{source}" to the RenderDoc directory "{Path(CONFIG['Paths']['RenderDoc'])}".')

    # Delete the downloaded files
    LOGGER.info('Deleting the downloaded RenderDoc files, Python files, and TMP directory.')
    shutil.rmtree(Path(CONFIG['TmpPaths']['RenderDoc']))


def copy_savegame() -> None:
    """
    Copies the save game to the GTA V user directory.

    Args:
        None

    Returns:
        None
    """

    # Get the profile directory inside the GTA user directory
    profile_directory = next(path for path in (Path(CONFIG['Paths']['GTAVUsr']) / 'Profiles').iterdir() if path.is_dir())

    # Copy the save game files to the profile directory
    LOGGER.info('Copying the save game files to the GTA user directory.')
    for file in CONFIG['Files']['Savegame']:
        shutil.copy(Path(CONFIG['Paths']['Configs']) / file, profile_directory)


def main():

    # Configure the logging
    configure_logging(Path(CONFIG['Paths']['Logs']), CONFIG['Logging']['Level'])

    # Clean-up old installations
    tmp_directory = Path(CONFIG['TmpPaths']['RenderDoc']).parent
    if tmp_directory.exists():
        shutil.rmtree(tmp_directory)

    # Check if all directories exist and if the directories contain the right files
    check_path_exists(Path(CONFIG['Paths']['GTAV']), 'Check the GTA V directories or the config file.')
    check_path_exists(Path(CONFIG['Paths']['GTAV']) / Path('GTA5.exe'), 'Check the GTA V directories or the config file.')
    check_path_exists(Path(CONFIG['Paths']['GTAV']) / Path('GTAVLauncher.exe'), 'Check the GTA V directories or the config file.')
    check_path_exists(Path(CONFIG['Paths']['GTAVUsr']), 'Check the GTA V directories or the config file.')
    check_path_exists(Path(CONFIG['Paths']['GTAVUsr']) / Path('Profiles'), 'Check the GTA V directories or the config file.')
    check_path_exists(Path(CONFIG['Paths']['VS']), 'Check the Visual Studio directory or the config file.')
    check_path_exists(Path(CONFIG['Paths']['VS']) / Path('MSBuild'), 'Check the Visual Studio directory or the config file.')

    # Initialize ScriptHookV, ScriptHookVDotNet, WBG, and Renderdoc
    initialize_scripthookv()
    initialize_scripthookvdotnet()
    initialize_wbg()
    initialize_renderdoc()

    # Initialize the scripts
    initialize_scripts()

    # Copy the save games to the GTA user directory
    copy_savegame()


if __name__ == '__main__':
    main()