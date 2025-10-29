import argparse
import glob
import gzip
import os
import re
import shutil
import subprocess
import sys
import urllib.request

from html.parser import HTMLParser
from io import BytesIO
from zipfile import ZipFile


# Directories in which the Data, ScriptHookV, ScriptHookVDotNet, and Save Game files are saved
DIRECTORY_CONFIGS = os.path.join(os.getcwd(), 'Configs')
DIRECTORY_DATA = os.path.join(os.getcwd(), 'Data')
DIRECTORY_RENDERDOC = os.path.join(os.getcwd(), 'RenderDoc')
DIRECTORY_RENDERDOC_ON_C = os.path.join('C:', os.sep, 'Program Files', 'RenderDoc')
DIRECTORY_SCRIPTHOOKV = os.path.join(os.getcwd(), 'ScriptHookV')
DIRECTORY_SCRIPTHOOKVDOTNET = os.path.join(os.getcwd(), 'ScriptHookVDotNet')
DIRECTORY_SCRIPT = os.path.join(os.getcwd(), 'Script')
DIRECTORY_WBG = os.path.join(os.getcwd(), 'WBG')

# Files that need to be copied to the GTA V directory
FILES_PYTHON = ['python?.dll', '_ctypes.pyd']
FILES_SCRIPTHOOKV = ['ScriptHookV.dll', 'dinput8.dll', 'NativeTrainer.asi']
FILES_SCRIPTHOOKVDOTNET = ['ScriptHookVDotNet.asi', 'ScriptHookVDotNet.ini', 'ScriptHookVDotNet3.dll']
FILES_SAVEGAME = ['SGTA50015', 'SGTA50015.bak']
FILES_WBG = ['config.ini']

# Headers and URLs for retrieving the download links of the latest version of ScriptHookV and ScriptHookVDotNet
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:134.0) Gecko/20100101 Firefox/134.0',
           'Referer': 'http://www.dev-c.com/gtav/scripthookv/'}
WEBSITE_PYTHON = 'https://www.python.org/downloads/windows/'
DOWNLOAD_PYTHON_32 = 'https://www.python.org/ftp/python/?/python-?-embed-win32.zip'
DOWNLOAD_PYTHON_64 = 'https://www.python.org/ftp/python/?/python-?-embed-amd64.zip'
WEBSITE_RENDERDOC = 'https://github.com/baldurk/renderdoc'
DOWNLOAD_RENDERDOC = 'https://github.com/baldurk/renderdoc/archive/refs/tags/?.zip'
WEBSITE_SCRIPTHOOKV  = 'http://www.dev-c.com/gtav/scripthookv/'
DOWNLOAD_SCRIPTHOOKV = 'https://ntscorp.ru/dev-c/ScriptHookV_?.zip'
WEBSITE_SCRIPTHOOKVDOTNET  = 'https://github.com/scripthookvdotnet/scripthookvdotnet-nightly/releases/'
DOWNLOAD_SCRIPTHOOKVDOTNET = 'https://github.com/scripthookvdotnet/scripthookvdotnet-nightly/releases/download/?/ScriptHookVDotNet-?.zip'
WEBSITE_WBG  = 'https://westechsolutions.net/sites/WindowedBorderlessGaming/download'
DOWNLOAD_WBG = 'https://westechsolutions.net/sites/WindowedBorderlessGaming/downloading/?token='


class HeaderTranslator():

    def strip_down_header(header_file):
        """
        Removes superfluous commands from the header file.

        Args:
            header_file (string): The header file including superfluous commands.

        Returns:
            header_file (string): The header file without superfluous commands.
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
        re_pattern  = re.compile(r'(\(.*?[,\|])(?:\n\s*)(.*?\)[;,])')
        header_file = re_pattern.sub(r'\1 \2', header_file)

        return header_file


    def translate_header(header_file):
        """
        Translates the header file from C to C#.

        Args:
            header_file (string): The header file in C.

        Returns:
            header_file (string): The header file in C#.
        """

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
        header_file = re.sub(r'const char \*\(', r'string(', header_file)
        header_file = re.sub(r'(const char|char) \*', r'[MarshalAs(UnmanagedType.LPStr)] string ', header_file)
        header_file = re.sub(r'RENDERDOC_DevicePointer', r'IntPtr', header_file)
        header_file = re.sub(r'RENDERDOC_WindowHandle', r'IntPtr', header_file)

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


    def c_to_cs(file_path_c, file_path_cs):
        """
        Translates the header file from C to C#.

        Args:
            file_path_c (string): The file path to the header file in C.
            file_path_cs (string): The file path to the header file in C#.

        Returns:
            None
        """

        # Open the header file in C and read the data
        with open(file_path_c, 'r', encoding='utf-8') as f:
            header_file = f.read()

        # Translate the header file to C#
        header_file = HeaderTranslator.strip_down_header(header_file)
        header_file = HeaderTranslator.translate_header(header_file)

        # Open the header file in C# and write the data
        with open(file_path_cs, 'w+', encoding='utf-8') as f:
            f.write(header_file)


class HTMLParserLinks(HTMLParser):

    def __init__(self, name):
        super().__init__()
        self.name = name
        self.link = ''
        self.latest_version = ''

    def handle_starttag(self, tag, attributes):
        """
        Sets the latest version and link to the software based on the name of the software and contents of the website.

        Args:
            tag (string): The start tag of the block.
            attributes (string): The attributes of the block.

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
                self.link = DOWNLOAD_PYTHON_32.replace('?', self.latest_version)
            if self.name == 'Python64':
                self.latest_version = sys.version.split(' ')[0]
                self.link = DOWNLOAD_PYTHON_64.replace('?', self.latest_version)

            # Get the download link for RenderDoc
            if self.name == 'RenderDoc' and '/baldurk/renderdoc/releases/tag/' in value:
                self.latest_version = value.split('/')[-1]
                self.link = DOWNLOAD_RENDERDOC.replace('?', self.latest_version)

            # Get the download link for ScriptHookV
            if self.name == 'ScriptHookV' and 'zip' in value and not 'SDK' in value:
                self.latest_version = '_'.join(value.split('_')[1:]).replace('.zip', '').replace('/', '_')
                self.link = DOWNLOAD_SCRIPTHOOKV.replace('?', self.latest_version)

            # Get the download link for ScriptHookVDotNet
            if self.name == 'ScriptHookVDotNet' and 'releases/tag/' in value:
                self.latest_version = value.split('/')[-1]
                self.link = DOWNLOAD_SCRIPTHOOKVDOTNET.replace('?', self.latest_version)

            # Get the download link for WBG
            if self.name == 'WBG' and 'downloading' in value:
                self.latest_version = value.split('=')[-1]
                self.link = DOWNLOAD_WBG + self.latest_version


def get_download_link(website, name):
    """
    Retrieves the download link and latest version given the name of the software and its website.

    Args:
        website (string): The website that contains the download link.
        name (string): The name of the software.

    Returns:
        link (string): The download link of the software.
        latest_version (string): The latest version of the software.
    """

    # Request the URL with a suitable request header
    request = urllib.request.Request(website, headers=HEADERS)
    response = urllib.request.urlopen(request)
    if not response.status == 200:
        print('[Mods]      ERROR: The website "{0}" could not be requested.'.format(website))
        raise RuntimeError

    # Decode the content of the website
    if response.getheader('Content-Encoding') == 'gzip':
        content = gzip.decompress(bytearray(response.read())).decode('utf-8')
    else:
        content = response.read().decode('utf-8')

    # Retrieve the download link for the latest version of Python, RenderDoc, ScriptHookV, ScriptHookVDotNet, or WBG
    parser = HTMLParserLinks(name)
    parser.feed(content)
    if not parser.link:
        print('[Mods]      ERROR: The website "{0}" does not contain any links.'.format(website))
        raise RuntimeError
    link = parser.link
    latest_version = parser.latest_version

    return link, latest_version


def download_and_extract_zip(name, website, directory):
    """
    Retrieves the download link and latest version of a software and downloads it.

    Args:
        website (string): The website that contains the download link.
        name (string): The name of the software.
        directory (string): The folder path to which the software should be downloaded and unpacked.

    Returns:
        None
    """

    # Get the download link
    download_link, latest_version = get_download_link(website, name)

    # Download the zip file
    request = urllib.request.Request(download_link, headers=HEADERS)
    response = urllib.request.urlopen(request)
    if not response.status == 200:
        print('[Mods]      ERROR: The file "{0}" could not be requested.'.format(download_link))
        raise RuntimeError

    # Unpack the files
    zipfile = ZipFile(BytesIO(response.read()))
    zipfile.extractall(path=directory)


def initialize_scripthookv(directory_gta):
    """
    Initializes ScriptHookV by downloading the latest version and moving it to the GTA V directory.

    Args:
        directory_gta (string): The main installation directory of GTA V.

    Returns:
        None
    """

    # Create the directory if it doesn't exist yet
    if not os.path.exists(DIRECTORY_SCRIPTHOOKV):
        os.mkdir(DIRECTORY_SCRIPTHOOKV)

    # Download the latest version of the mod
    print('[SHV]       Downloading and unpacking the latest version of ScriptHookV...')
    download_and_extract_zip('ScriptHookV', WEBSITE_SCRIPTHOOKV, DIRECTORY_SCRIPTHOOKV)
    print('            Done.')

    # Copy the files to the GTA directory
    print('            Copying all files to the GTA directory...')
    for file in FILES_SCRIPTHOOKV:
        file_path = os.path.join(DIRECTORY_SCRIPTHOOKV, 'bin', file)
        shutil.copy(file_path, directory_gta)
    print('            Done.')

    # Delete the downloaded files
    print('            Deleting downloaded files...')
    shutil.rmtree(DIRECTORY_SCRIPTHOOKV)
    print('            Done.')


def initialize_scripthookvdotnet(directory_gta):
    """
    Initializes ScriptHookVDotNet by downloading the latest version and moving it to the GTA V directory.

    Args:
        directory_gta (string): The main installation directory of GTA V.

    Returns:
        None
    """

    # Create the directory if it doesn't exist yet
    if not os.path.exists(DIRECTORY_SCRIPTHOOKVDOTNET):
        os.mkdir(DIRECTORY_SCRIPTHOOKVDOTNET)

    # Download the latest version of the mod
    print('[SHVDN]     Downloading and unpacking the latest version of ScriptHookVDotNet...')
    download_and_extract_zip('ScriptHookVDotNet', WEBSITE_SCRIPTHOOKVDOTNET, DIRECTORY_SCRIPTHOOKVDOTNET)
    print('            Done.')

    # Open the file and read the data
    with open(os.path.join(DIRECTORY_SCRIPTHOOKVDOTNET, 'ScriptHookVDotNet.ini'), 'r') as f:
        ini_file = f.read()

    # Change the keybindings
    ini_file = ini_file.replace('ConsoleKeyBinding=F4', 'ConsoleKeyBinding=F5')

    # Open the file and write the data
    with open(os.path.join(DIRECTORY_SCRIPTHOOKVDOTNET, 'ScriptHookVDotNet.ini'), 'w') as f:
        f.write(ini_file)

    # Copy the files to the GTA directory
    print('            Copying all files to the GTA directory...')
    for file in FILES_SCRIPTHOOKVDOTNET:
        file_path = os.path.join(DIRECTORY_SCRIPTHOOKVDOTNET, file)
        shutil.copy(file_path, directory_gta)
    print('            Done.')

    # Delete the downloaded files
    print('            Deleting downloaded files...')
    shutil.rmtree(DIRECTORY_SCRIPTHOOKVDOTNET)
    print('            Done.')


def initialize_wbg():
    """
    Initializes Windowed Borderless Gaming by downloading the latest version and replacing the config file.

    Args:
        None

    Returns:
        None
    """

    # Create the directory if it doesn't exist yet
    if not os.path.exists(DIRECTORY_WBG):
        os.mkdir(DIRECTORY_WBG)

    # Download the latest version of WBG
    print('[WBG]       Downloading and unpacking the latest version of WBG...')
    download_and_extract_zip('WBG', WEBSITE_WBG, DIRECTORY_WBG)
    print('            Done.')

    # Copy the config file to the directory
    print('            Copying the config file to the directory...')
    for file in FILES_WBG:
        file_path = os.path.join(DIRECTORY_CONFIGS, file)
        shutil.copy(file_path, DIRECTORY_WBG)
    print('            Done.')


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


def initialize_renderdoc(directory_gta, directory_vs):
    """
    Initializes RenderDoc by downloading the latest version of RenderDoc and Python, modifying the files according to the versions,
    compiling RenderDoc, and moving it to the GTA V directory and its own directory.

    Args:
        directory_gta (string): The main installation directory of GTA V.
        directory_vs (string): The main installation directory of Visual Studio.

    Returns:
        None
    """

    # Create the directories if they don't exist yet
    if not os.path.exists(DIRECTORY_RENDERDOC):
        os.mkdir(DIRECTORY_RENDERDOC)
    if not os.path.exists(os.path.join(DIRECTORY_RENDERDOC, 'Python32')):
        os.mkdir(os.path.join(DIRECTORY_RENDERDOC, 'Python32'))
    if not os.path.exists(os.path.join(DIRECTORY_RENDERDOC, 'Python64')):
        os.mkdir(os.path.join(DIRECTORY_RENDERDOC, 'Python64'))
    if not os.path.exists(os.path.join(DIRECTORY_RENDERDOC, 'RenderDoc')):
        os.mkdir(os.path.join(DIRECTORY_RENDERDOC, 'RenderDoc'))

    # Current Python version and directories
    python_version = sys.version.split(' ')[0]
    python_version_short = ''.join(python_version.split('.')[:2])
    python_header_directory = os.path.join(os.path.dirname(sys.executable), 'include')

    # Download the Python and RenderDoc files
    print('[RenderDoc] Downloading and unpacking the Python embeddable packages for v{0}...'.format(python_version))
    download_and_extract_zip('Python32', WEBSITE_PYTHON, os.path.join(DIRECTORY_RENDERDOC, 'Python32'))
    download_and_extract_zip('Python64', WEBSITE_PYTHON, os.path.join(DIRECTORY_RENDERDOC, 'Python64'))
    print('            Done.')
    print('            Downloading and unpacking the latest version of RenderDoc source code...')
    download_and_extract_zip('RenderDoc', WEBSITE_RENDERDOC, os.path.join(DIRECTORY_RENDERDOC, 'RenderDoc'))
    print('            Done.')

    # RenderDoc directories
    renderdoc_main_directory = os.path.join(DIRECTORY_RENDERDOC, 'RenderDoc', os.listdir(os.path.join(DIRECTORY_RENDERDOC, 'RenderDoc'))[0])
    renderdoc_sln_path = os.path.join(renderdoc_main_directory, 'renderdoc.sln')
    renderdoc_qrenderdoc_directory = os.path.join(renderdoc_main_directory, 'qrenderdoc')
    renderdoc_natvis_path = glob.glob(os.path.join(renderdoc_qrenderdoc_directory, '*.natvis'))[0]
    renderdoc_vcxproj_path = os.path.join(renderdoc_qrenderdoc_directory, 'qrenderdoc_local.vcxproj')
    renderdoc_python_props_path = os.path.join(renderdoc_qrenderdoc_directory, 'Code', 'pyrenderdoc', 'python.props')
    renderdoc_qrenderdoc_pro_path = os.path.join(renderdoc_qrenderdoc_directory, 'qrenderdoc.pro')
    renderdoc_python_directory = os.path.join(renderdoc_qrenderdoc_directory, '3rdparty', 'python')
    renderdoc_python_header_directory = os.path.join(renderdoc_qrenderdoc_directory, '3rdparty', 'python', 'include')
    renderdoc_compiled_x86_directory = os.path.join(renderdoc_main_directory, 'Win32', 'Release')
    renderdoc_compiled_x64_directory = os.path.join(renderdoc_main_directory, 'x64', 'Release')
    renderdoc_compiled_renderdoc_dll_path = os.path.join(renderdoc_compiled_x64_directory, 'renderdoc.dll')
    renderdoc_compiled_renderdoc_header_path = os.path.join(renderdoc_compiled_x64_directory, 'renderdoc_app.h')
    renderdoc_compiled_renderdoc_pyd_path = os.path.join(renderdoc_compiled_x64_directory, 'pymodules', 'renderdoc.pyd')
    renderdoc_compiled_qrenderdoc_pyd_path = os.path.join(renderdoc_compiled_x64_directory, 'pymodules', 'qrenderdoc.pyd')

    # Old Python version
    python_version_old = os.path.basename(glob.glob(os.path.join(renderdoc_qrenderdoc_directory, '*.natvis'))[0]).replace('python', '').replace('.natvis', '')
    
    # Replace the Python version in the RenderDoc files
    print('            Replacing the Python version v{0} with v{1} in the RenderDoc files...'.format(python_version_old, python_version_short))
    replace_in_file(renderdoc_natvis_path, r'python\d+', 'python' + python_version_short)
    replace_in_file(renderdoc_vcxproj_path, r'python\d+\.natvis', 'python' + python_version_short + '.natvis')
    replace_in_file(renderdoc_python_props_path, r'<PythonMajorMinor>\d+</PythonMajorMinor>', '<PythonMajorMinor>' + python_version_short + '</PythonMajorMinor>')
    replace_in_file(renderdoc_python_props_path, r'python\d+', 'python' + python_version_short)
    replace_in_file(renderdoc_qrenderdoc_pro_path, r'python\d+\.lib', 'python' + python_version_short + '.lib')
    os.rename(renderdoc_natvis_path, renderdoc_natvis_path.replace('python' + python_version_old, 'python' + python_version_short))
    print('            Done.')

    # Copy the Python header files to the RenderDoc directory
    print('            Copying the header files from "{0}" to the RenderDoc directory...'.format(python_header_directory))
    shutil.rmtree(renderdoc_python_header_directory)
    shutil.copytree(python_header_directory, renderdoc_python_header_directory)
    print('            Done.')

    # Setting up the Python files for each platform
    for platform in ['32', '64']:

        # Directories depending on the platform
        directory_platform = 'Win32' if platform == '32' else 'x64'
        renderdoc_python_x86_x64_directory = os.path.join(renderdoc_qrenderdoc_directory, '3rdparty', 'python', directory_platform)
        renderdoc_python_dll_path = os.path.join(renderdoc_python_x86_x64_directory, 'python?.dll'.replace('?', python_version_short))
        print('            Python ({0}):'.format(directory_platform))

        # Copy the Python embeddable package to the RenderDoc directory
        print('                Copying the Python embeddable package to the RenderDoc directory...')
        file_path = os.path.join(DIRECTORY_RENDERDOC, 'Python' + platform, 'python?.zip'.replace('?', python_version_short))
        shutil.copy(file_path, renderdoc_python_directory)
        for file in glob.glob(os.path.join(renderdoc_python_directory, '*{0}*'.format(python_version_old))):
            os.remove(file)
        file_path = os.path.join(DIRECTORY_RENDERDOC, 'Python' + platform, 'python?.dll'.replace('?', python_version_short))
        shutil.copy(file_path, renderdoc_python_x86_x64_directory)
        file_path = os.path.join(DIRECTORY_RENDERDOC, 'Python' + platform, '_ctypes.pyd')
        shutil.copy(file_path, renderdoc_python_x86_x64_directory)
        for file in glob.glob(os.path.join(renderdoc_python_x86_x64_directory, '*{0}*'.format(python_version_old))):
            os.remove(file)
        print('                Done.')

        # Create the pythonXX.def from the pythonXX.dll
        print('                Generating the python{0}.def from the python{0}.dll...'.format(python_version_short))
        result = subprocess.run(['dumpbin',
                                 '/exports',
                                 renderdoc_python_dll_path],
                                capture_output=True, text=True)
        if result.returncode != 0:
            print('[RenderDoc] ERROR: {0}'.format(result.stdout))
            raise RuntimeError
        print('                Done.')

        # Create the pythonXX.lib from the pythonXX.def
        print('                Generating the python{0}.lib from the python{0}.def...'.format(python_version_short))
        def_file = result.stdout
        re_pattern = re.compile(r'^(\s+\d+\s+[\dA-F]+\s[\dA-F]+\s)(\w+)(\n)', re.MULTILINE)
        functions = re_pattern.findall(def_file)
        def_file = 'EXPORTS\n' + '\n'.join([function[1] for function in functions])
        with open(renderdoc_python_dll_path.replace('dll', 'def'), 'w+', encoding='utf-8') as f:
            f.write(def_file)
        result = subprocess.run(['lib',
                                 '/def:{0}'.format(renderdoc_python_dll_path.replace('dll', 'def')),
                                 '/machine:{0}'.format('x86' if platform == '32' else 'x64'),
                                 '/out:{0}'.format(renderdoc_python_dll_path.replace('dll', 'lib'))],
                                stdout=subprocess.DEVNULL)
        if result.returncode != 0:
            print('[RenderDoc] ERROR: {0}'.format(result.stdout))
            raise RuntimeError
        print('                Done.')

    # Update the Platform Toolset version for each vcxproj file and surpress a deprecation warning
    toolset_version = glob.glob(os.path.join(directory_vs, 'VC', 'Auxiliary', 'Build', 'Microsoft.VCToolsVersion.v*.default.txt'))[0]
    toolset_version = toolset_version.split('.')[2]
    print('            Updating the toolset version in all vcxproj files to {0}...'.format(toolset_version))
    for file in glob.glob(os.path.join(os.getcwd(), '**', '*.vcxproj'), recursive=True):
        replace_in_file(file, r'(<PlatformTool[sS]et>)v\d+(<\/PlatformTool[sS]et>)', r'\1' + toolset_version + r'\2')
        replace_in_file(file, '<PreprocessorDefinitions>', '<PreprocessorDefinitions>_SILENCE_STDEXT_ARR_ITERS_DEPRECATION_WARNING;')
    print('            Done.')

    # Compile RenderDoc for each platform
    for platform in ['x86', 'x64']:

        print('            Compiling RenderDoc for platform {0} (this may take a while)...'.format(platform))
        result = subprocess.run(['MSBuild',
                                 renderdoc_sln_path,
                                 '-p:Configuration=Release',
                                 '-p:Platform={0}'.format(platform)],
                                capture_output=True, text=True)
        if result.returncode != 0:
            print('[RenderDoc] ERROR: {0}'.format(result.stdout))
            raise RuntimeError
        print('            Done.')

    # Create the directory for compiled x86 files
    if not os.path.exists(os.path.join(renderdoc_compiled_x64_directory, 'x86')):
        os.mkdir(os.path.join(renderdoc_compiled_x64_directory, 'x86'))

    # Copy the compiled files to the directories
    print('            Copying the compiled files to the directories...')
    shutil.copy(renderdoc_compiled_renderdoc_dll_path, DIRECTORY_SCRIPT)
    shutil.copy(renderdoc_compiled_renderdoc_pyd_path, renderdoc_compiled_x64_directory)
    shutil.copy(renderdoc_compiled_qrenderdoc_pyd_path, renderdoc_compiled_x64_directory)
    compiled_files_x86 = [glob.glob(os.path.join(renderdoc_compiled_x86_directory, extension)) for extension in ['*.dll', '*.json', '*.exe', '*.yes']]
    os.mkdir
    for files in compiled_files_x86:
        for file in files:
            shutil.copy(file, os.path.join(renderdoc_compiled_x64_directory, 'x86'))
    print('            Done.')

    # Translate the Renderdoc header file to C# and copy it to the DataGeneration directory
    print('            Translating the RenderDoc header file to C# and copying it to the script directory...')
    file_path_header_c = renderdoc_compiled_renderdoc_header_path
    file_path_header_cs = os.path.join(DIRECTORY_SCRIPT, 'RenderDocHeader.cs')
    HeaderTranslator.c_to_cs(file_path_header_c, file_path_header_cs)
    print('            Done.')

    # Copy the RenderDoc file to C:
    print('            Copying the RenderDoc files to "{0}"...'.format(DIRECTORY_RENDERDOC_ON_C))
    if os.path.exists(DIRECTORY_RENDERDOC_ON_C) and os.path.isdir(DIRECTORY_RENDERDOC_ON_C):
        shutil.rmtree(DIRECTORY_RENDERDOC_ON_C)
    shutil.rmtree(os.path.join(renderdoc_compiled_x64_directory, 'obj'))
    for file in glob.glob(os.path.join(renderdoc_compiled_x64_directory, '*.exp')):
        os.remove(file)
    for file in glob.glob(os.path.join(renderdoc_compiled_x64_directory, '*.lib')):
        os.remove(file)
    for file in glob.glob(os.path.join(renderdoc_compiled_x64_directory, '*.pdb')):
        os.remove(file)
    shutil.move(renderdoc_compiled_x64_directory, DIRECTORY_RENDERDOC_ON_C)
    print('            Done.')

    # Delete the downloaded files
    print('            Deleting downloaded files...')
    shutil.rmtree(DIRECTORY_RENDERDOC)
    print('            Done.')


def initialize_scripts(directory_script):
    """
    Replaces the versions and paths in the scripts with the correct ones, compiles the script, and copies it to the GTA V directory.

    Args:
        directory_script (string): The folder path of the GTA V scripts directory.

    Returns:
        None
    """

    # Create the directory if it doesn't exist yet
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
    replace_in_file(os.path.join(DIRECTORY_SCRIPT, 'DataGenerator.cs'), r'log_path = ".+";', 'log_path = "{0}";'.format(DIRECTORY_DATA.replace('\\', '\\\\\\\\') + '\\\\\\\\'))
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


def copy_savegame(directory_gta_user):
    """
    Copies the save game to the GTA V user directory.

    Args:
        directory_gta_user (string): The folder path of the GTA V user directory.

    Returns:
        None
    """

    # Get the profile directory inside the GTA user directory
    profile_directory = os.path.join(directory_gta_user, 'Profiles')
    profiles = [path for path in os.listdir(profile_directory) if os.path.isdir(os.path.join(profile_directory, path))]
    profile_directory = os.path.join(profile_directory, profiles[0])

    # Copy the save game files to the profile directory
    print('[SaveGame]  Copying the save game files to the GTA user directory...')
    for file in FILES_SAVEGAME:
        file_path = os.path.join(DIRECTORY_CONFIGS, file)
        shutil.copy(file_path, profile_directory)
    print('            Done.')


def main():

    # Parse the input arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('--gta_ins_dir', '-g', help='Installation directory of GTA V', type=str, metavar='PATH',
                        default='C:\\Program Files\\Rockstar Games\\Grand Theft Auto V Legacy')
    parser.add_argument('--gta_usr_dir', '-u', help='User directory of GTA V', type=str, metavar='PATH',
                        default=os.path.expanduser('~\\Documents\\Rockstar Games\\GTA V'))
    parser.add_argument('--vs_dir', '-v', help='Installation directory of Visual Studio', type=str, metavar='PATH',
                        default='C:\\Program Files\\Microsoft Visual Studio\\2022\\Community')
    args = parser.parse_args()

    # Check if all directories exist and if the directories contain the right files
    print('[OS]        Checking all directories given as input...')
    if not os.path.exists(args.gta_ins_dir):
        print('[OS]        ERROR: The path "{0}" does not exist. Please check your GTA installation.'.format(args.gta_ins_dir))
        print('[OS]        Usage: python initialize_project.py -g GTA_INS_DIR -u GTA_USR_DIR -v VS_DIR')
        raise RuntimeError
    if not os.path.exists(os.path.join(args.gta_ins_dir, 'GTA5.exe')):
        print('[OS]        ERROR: The GTA installation path "{0}" does not contain "GTA5.exe". Please check your GTA installation.'.format(args.gta_ins_dir))
        print('[OS]        Usage: python initialize_project.py -g GTA_INS_DIR -u GTA_USR_DIR -v VS_DIR')
        raise RuntimeError
    if not os.path.exists(args.gta_usr_dir):
        print('[OS]        ERROR: The path "{0}" does not exist. Please check your GTA installation.'.format(args.gta_usr_dir))
        print('[OS]        Usage: python initialize_project.py -g GTA_INS_DIR -u GTA_USR_DIR -v VS_DIR')
        raise RuntimeError
    if not os.path.exists(os.path.join(args.gta_usr_dir, 'Profiles')):
        print('[OS]        ERROR: The GTA installation path "{0}" does not contain "Profiles". Please check your GTA installation.'.format(args.gta_usr_dir))
        print('[OS]        Usage: python initialize_project.py -g GTA_INS_DIR -u GTA_USR_DIR -v VS_DIR')
        raise RuntimeError
    if not os.path.exists(args.vs_dir):
        print('[OS]        ERROR: The path "{0}" does not exist. Please check your Visual Studio installation.'.format(args.vs_dir))
        print('[OS]        Usage: python initialize_project.py -g GTA_INS_DIR -u GTA_USR_DIR -v VS_DIR')
        raise RuntimeError
    if not os.path.exists(os.path.join(args.vs_dir, 'MSBuild')):
        print('[OS]        ERROR: The GTA installation path "{0}" does not contain "MSBuild". Please check your Visual Studio installation.'.format(args.vs_dir))
        print('[OS]        Usage: python initialize_project.py -g GTA_INS_DIR -u GTA_USR_DIR -v VS_DIR')
        raise RuntimeError
    print('            Done.')

    # Initialize ScriptHookV, ScriptHookVDotNet, WBG, and Renderdoc
    initialize_scripthookv(args.gta_ins_dir)
    initialize_scripthookvdotnet(args.gta_ins_dir)
    initialize_wbg()
    initialize_renderdoc(args.gta_ins_dir, args.vs_dir)

    # Initialize the scripts
    initialize_scripts(os.path.join(args.gta_ins_dir, 'scripts'))

    # Copy the save games to the GTA user directory
    copy_savegame(args.gta_usr_dir)


if __name__ == '__main__':
    main()