// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 Nicolai Skutsch
//
// This program is free software: you can redistribute it and/or modify
// it under the terms of the GNU General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.
//
// This program is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU General Public License for more details.
//
// You should have received a copy of the GNU General Public License
// along with this program.  If not, see <https://www.gnu.org/licenses/>.
//
// Additional permission under GNU GPL version 3 section 7
//
// If you modify this Program, or any covered work, by linking or combining
// it with ScriptHookV or Grand Theft Auto V (or a modified version of
// those), containing parts covered by the terms of their respective
// proprietary licenses, the licensors of this Program grant you additional
// permission to convey the resulting work.

using System;
using System.IO;
using System.Runtime.InteropServices;

namespace DataGeneration
{
    internal static class Libdl
    {
        public const int RTLD_NOW = 0x002;

        [DllImport("libdl")]
        public static extern IntPtr DLopen(string filename, int flags);

        [DllImport("libdl")]
        public static extern IntPtr DLsym(IntPtr module, string procname);

        [DllImport("libdl")]
        public static extern void DLclose(IntPtr module);
    }

    internal static class Kernel32
    {
        [DllImport("kernel32")]
        public static extern IntPtr LoadLibrary(string filename);

        [DllImport("kernel32")]
        public static extern IntPtr GetProcAddress(IntPtr module, string procname);

        [DllImport("kernel32")]
        public static extern int FreeLibrary(IntPtr module);
    }

    public abstract class Library
    {
        private readonly IntPtr library_pointer;

        public Library(string library_path)
        {
            this.library_pointer = LoadLibrary(library_path);
            if (this.library_pointer == IntPtr.Zero)
            {
                throw new Exception("The following library could not be loaded: " + library_path);
            }
        }

        public static Library LoadOSLibrary(string library_path)
        {
            if (RuntimeInformation.IsOSPlatform(OSPlatform.Windows))
            {
                return new LibraryWindows(library_path);
            }
            else if (RuntimeInformation.IsOSPlatform(OSPlatform.Linux) || RuntimeInformation.IsOSPlatform(OSPlatform.OSX))
            {
                return new LibraryUnix(library_path);
            }
            else
            {
                throw new Exception("The library could be loaded on this OS.");
            }
        }

        public void FreeOSLibrary()
        {
            FreeLibrary(this.library_pointer);
        }

        public unsafe void LoadOSFunction<T>(string function_name, out T field)
        {
            IntPtr function_pointer = LoadFunction(function_name);
            if (function_pointer != IntPtr.Zero)
            {
                field = Marshal.GetDelegateForFunctionPointer<T>(function_pointer);
            }
            else
            {
                throw new Exception("The following function could be loaded: " + function_name);
            }
        }

        protected abstract IntPtr LoadLibrary(string library_path);
        protected abstract void FreeLibrary(IntPtr library_pointer);
        protected abstract IntPtr LoadFunction(string function_name);

        private class LibraryWindows : Library
        {
            public LibraryWindows(string library_path) : base(library_path) { }
            protected override IntPtr LoadLibrary(string library_path)
            {
                return Kernel32.LoadLibrary(library_path);
            }
            protected override void FreeLibrary(IntPtr library_pointer)
            {
                Kernel32.FreeLibrary(library_pointer);
            }
            protected override IntPtr LoadFunction(string function_name)
            {
                return Kernel32.GetProcAddress(this.library_pointer, function_name);
            }
        }

        private class LibraryUnix : Library
        {
            public LibraryUnix(string library_path) : base(library_path) { }
            protected override IntPtr LoadLibrary(string library_path)
            {
                return Libdl.DLopen(library_path, Libdl.RTLD_NOW);
            }
            protected override void FreeLibrary(IntPtr library_pointer)
            {
                Libdl.DLclose(library_pointer);
            }
            protected override IntPtr LoadFunction(string function_name)
            {
                return Libdl.DLsym(this.library_pointer, function_name);
            }
        }
    }

    public unsafe class RenderDoc
    {
        private readonly string RENDERDOC_PATH = "renderdoc.dll";
        public readonly RENDERDOC_API_1_7_0 API;

        public unsafe RenderDoc(string file_path)
        {
            Library renderdoc_library = Library.LoadOSLibrary(RENDERDOC_PATH);
            renderdoc_library.LoadOSFunction("RENDERDOC_GetAPI", out pRENDERDOC_GetAPI GetAPI);
            void* api_pointer;
            if (GetAPI(RENDERDOC_Version.eRENDERDOC_API_Version_1_7_0, &api_pointer) != 1)
            {
                throw new Exception("The RenderDoc API could not be loaded from the following path: " + RENDERDOC_PATH);
            }
            this.API = Marshal.PtrToStructure<RENDERDOC_API_1_7_0>((IntPtr)api_pointer);
            this.SetFilePath(file_path);
        }

        public unsafe void SetFilePath(string file_path)
        {
            if (!file_path.EndsWith("\\\\"))
            {
                file_path = file_path + "\\\\";
            }
            this.API.SetCaptureFilePathTemplate(Path.Combine(file_path, "capture"));
        }
    }
}
