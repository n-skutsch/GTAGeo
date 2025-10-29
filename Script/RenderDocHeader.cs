using System;
using System.Runtime.InteropServices;
namespace DataGeneration
{
  public enum RENDERDOC_CaptureOption
  {
    eRENDERDOC_Option_AllowVSync = 0,
    eRENDERDOC_Option_AllowFullscreen = 1,
    eRENDERDOC_Option_APIValidation = 2,
    eRENDERDOC_Option_DebugDeviceMode = 2,    
    eRENDERDOC_Option_CaptureCallstacks = 3,
    eRENDERDOC_Option_CaptureCallstacksOnlyDraws = 4,
    eRENDERDOC_Option_CaptureCallstacksOnlyActions = 4,
    eRENDERDOC_Option_DelayForDebugger = 5,
    eRENDERDOC_Option_VerifyBufferAccess = 6,
    eRENDERDOC_Option_VerifyMapWrites = eRENDERDOC_Option_VerifyBufferAccess,
    eRENDERDOC_Option_HookIntoChildren = 7,
    eRENDERDOC_Option_RefAllResources = 8,
    eRENDERDOC_Option_SaveAllInitials = 9,
    eRENDERDOC_Option_CaptureAllCmdLists = 10,
    eRENDERDOC_Option_DebugOutputMute = 11,
    eRENDERDOC_Option_AllowUnsupportedVendorExtensions = 12,
    eRENDERDOC_Option_SoftMemoryLimit = 13,
  }
  public unsafe delegate int pRENDERDOC_SetCaptureOptionU32(RENDERDOC_CaptureOption opt, uint val);
  public unsafe delegate int pRENDERDOC_SetCaptureOptionF32(RENDERDOC_CaptureOption opt, float val);
  public unsafe delegate uint pRENDERDOC_GetCaptureOptionU32(RENDERDOC_CaptureOption opt);
  public unsafe delegate float pRENDERDOC_GetCaptureOptionF32(RENDERDOC_CaptureOption opt);
  public enum RENDERDOC_InputButton
  {
    eRENDERDOC_Key_0 = 0x30,
    eRENDERDOC_Key_1 = 0x31,
    eRENDERDOC_Key_2 = 0x32,
    eRENDERDOC_Key_3 = 0x33,
    eRENDERDOC_Key_4 = 0x34,
    eRENDERDOC_Key_5 = 0x35,
    eRENDERDOC_Key_6 = 0x36,
    eRENDERDOC_Key_7 = 0x37,
    eRENDERDOC_Key_8 = 0x38,
    eRENDERDOC_Key_9 = 0x39,
    eRENDERDOC_Key_A = 0x41,
    eRENDERDOC_Key_B = 0x42,
    eRENDERDOC_Key_C = 0x43,
    eRENDERDOC_Key_D = 0x44,
    eRENDERDOC_Key_E = 0x45,
    eRENDERDOC_Key_F = 0x46,
    eRENDERDOC_Key_G = 0x47,
    eRENDERDOC_Key_H = 0x48,
    eRENDERDOC_Key_I = 0x49,
    eRENDERDOC_Key_J = 0x4A,
    eRENDERDOC_Key_K = 0x4B,
    eRENDERDOC_Key_L = 0x4C,
    eRENDERDOC_Key_M = 0x4D,
    eRENDERDOC_Key_N = 0x4E,
    eRENDERDOC_Key_O = 0x4F,
    eRENDERDOC_Key_P = 0x50,
    eRENDERDOC_Key_Q = 0x51,
    eRENDERDOC_Key_R = 0x52,
    eRENDERDOC_Key_S = 0x53,
    eRENDERDOC_Key_T = 0x54,
    eRENDERDOC_Key_U = 0x55,
    eRENDERDOC_Key_V = 0x56,
    eRENDERDOC_Key_W = 0x57,
    eRENDERDOC_Key_X = 0x58,
    eRENDERDOC_Key_Y = 0x59,
    eRENDERDOC_Key_Z = 0x5A,
    eRENDERDOC_Key_NonPrintable = 0x100,
    eRENDERDOC_Key_Divide,
    eRENDERDOC_Key_Multiply,
    eRENDERDOC_Key_Subtract,
    eRENDERDOC_Key_Plus,
    eRENDERDOC_Key_F1,
    eRENDERDOC_Key_F2,
    eRENDERDOC_Key_F3,
    eRENDERDOC_Key_F4,
    eRENDERDOC_Key_F5,
    eRENDERDOC_Key_F6,
    eRENDERDOC_Key_F7,
    eRENDERDOC_Key_F8,
    eRENDERDOC_Key_F9,
    eRENDERDOC_Key_F10,
    eRENDERDOC_Key_F11,
    eRENDERDOC_Key_F12,
    eRENDERDOC_Key_Home,
    eRENDERDOC_Key_End,
    eRENDERDOC_Key_Insert,
    eRENDERDOC_Key_Delete,
    eRENDERDOC_Key_PageUp,
    eRENDERDOC_Key_PageDn,
    eRENDERDOC_Key_Backspace,
    eRENDERDOC_Key_Tab,
    eRENDERDOC_Key_PrtScrn,
    eRENDERDOC_Key_Pause,
    eRENDERDOC_Key_Max,
  }
  public unsafe delegate void pRENDERDOC_SetFocusToggleKeys(RENDERDOC_InputButton *keys, int num);
  public unsafe delegate void pRENDERDOC_SetCaptureKeys(RENDERDOC_InputButton *keys, int num);
  public enum RENDERDOC_OverlayBits
  {
    eRENDERDOC_Overlay_Enabled = 0x1,
    eRENDERDOC_Overlay_FrameRate = 0x2,
    eRENDERDOC_Overlay_FrameNumber = 0x4,
    eRENDERDOC_Overlay_CaptureList = 0x8,
    eRENDERDOC_Overlay_Default = (eRENDERDOC_Overlay_Enabled | eRENDERDOC_Overlay_FrameRate | eRENDERDOC_Overlay_FrameNumber | eRENDERDOC_Overlay_CaptureList),
    eRENDERDOC_Overlay_All = 0x7ffffff,
    eRENDERDOC_Overlay_None = 0,
  }
  public unsafe delegate uint pRENDERDOC_GetOverlayBits();
  public unsafe delegate void pRENDERDOC_MaskOverlayBits(uint And, uint Or);
  public unsafe delegate void pRENDERDOC_RemoveHooks();
  public unsafe delegate void pRENDERDOC_UnloadCrashHandler();
  public unsafe delegate void pRENDERDOC_SetCaptureFilePathTemplate([MarshalAs(UnmanagedType.LPStr)] string pathtemplate);
  public unsafe delegate string pRENDERDOC_GetCaptureFilePathTemplate();
  public unsafe delegate uint pRENDERDOC_GetNumCaptures();
  public unsafe delegate uint pRENDERDOC_GetCapture(uint idx, [MarshalAs(UnmanagedType.LPStr)] string filename, uint *pathlength, ulong *timestamp);
  public unsafe delegate void pRENDERDOC_SetCaptureFileComments([MarshalAs(UnmanagedType.LPStr)] string filePath, [MarshalAs(UnmanagedType.LPStr)] string comments);
  public unsafe delegate uint pRENDERDOC_IsTargetControlConnected();
  public unsafe delegate uint pRENDERDOC_LaunchReplayUI(uint connectTargetControl, [MarshalAs(UnmanagedType.LPStr)] string cmdline);
  public unsafe delegate void pRENDERDOC_GetAPIVersion(int *major, int *minor, int *patch);
  public unsafe delegate uint pRENDERDOC_ShowReplayUI();
  public unsafe delegate void pRENDERDOC_SetActiveWindow(IntPtr device, IntPtr wndHandle);
  public unsafe delegate void pRENDERDOC_TriggerCapture();
  public unsafe delegate void pRENDERDOC_TriggerMultiFrameCapture(uint numFrames);
  public unsafe delegate void pRENDERDOC_StartFrameCapture(IntPtr device, IntPtr wndHandle);
  public unsafe delegate uint pRENDERDOC_IsFrameCapturing();
  public unsafe delegate uint pRENDERDOC_EndFrameCapture(IntPtr device, IntPtr wndHandle);
  public unsafe delegate uint pRENDERDOC_DiscardFrameCapture(IntPtr device, IntPtr wndHandle);
  public unsafe delegate void pRENDERDOC_SetCaptureTitle([MarshalAs(UnmanagedType.LPStr)] string title);
  public enum RENDERDOC_Version
  {
    eRENDERDOC_API_Version_1_0_0 = 10000,    
    eRENDERDOC_API_Version_1_0_1 = 10001,    
    eRENDERDOC_API_Version_1_0_2 = 10002,    
    eRENDERDOC_API_Version_1_1_0 = 10100,    
    eRENDERDOC_API_Version_1_1_1 = 10101,    
    eRENDERDOC_API_Version_1_1_2 = 10102,    
    eRENDERDOC_API_Version_1_2_0 = 10200,    
    eRENDERDOC_API_Version_1_3_0 = 10300,    
    eRENDERDOC_API_Version_1_4_0 = 10400,    
    eRENDERDOC_API_Version_1_4_1 = 10401,    
    eRENDERDOC_API_Version_1_4_2 = 10402,    
    eRENDERDOC_API_Version_1_5_0 = 10500,    
    eRENDERDOC_API_Version_1_6_0 = 10600,    
  }
  [StructLayout(LayoutKind.Sequential)]
  public unsafe struct RENDERDOC_API_1_6_0
  {
    public pRENDERDOC_GetAPIVersion GetAPIVersion;
    public pRENDERDOC_SetCaptureOptionU32 SetCaptureOptionU32;
    public pRENDERDOC_SetCaptureOptionF32 SetCaptureOptionF32;
    public pRENDERDOC_GetCaptureOptionU32 GetCaptureOptionU32;
    public pRENDERDOC_GetCaptureOptionF32 GetCaptureOptionF32;
    public pRENDERDOC_SetFocusToggleKeys SetFocusToggleKeys;
    public pRENDERDOC_SetCaptureKeys SetCaptureKeys;
    public pRENDERDOC_GetOverlayBits GetOverlayBits;
    public pRENDERDOC_MaskOverlayBits MaskOverlayBits;
    public pRENDERDOC_RemoveHooks RemoveHooks;
    public pRENDERDOC_UnloadCrashHandler UnloadCrashHandler;
    public pRENDERDOC_SetCaptureFilePathTemplate SetCaptureFilePathTemplate;
    public pRENDERDOC_GetCaptureFilePathTemplate GetCaptureFilePathTemplate;
    public pRENDERDOC_GetNumCaptures GetNumCaptures;
    public pRENDERDOC_GetCapture GetCapture;
    public pRENDERDOC_TriggerCapture TriggerCapture;
    public pRENDERDOC_IsTargetControlConnected IsTargetControlConnected;
    public pRENDERDOC_LaunchReplayUI LaunchReplayUI;
    public pRENDERDOC_SetActiveWindow SetActiveWindow;
    public pRENDERDOC_StartFrameCapture StartFrameCapture;
    public pRENDERDOC_IsFrameCapturing IsFrameCapturing;
    public pRENDERDOC_EndFrameCapture EndFrameCapture;
    public pRENDERDOC_TriggerMultiFrameCapture TriggerMultiFrameCapture;
    public pRENDERDOC_SetCaptureFileComments SetCaptureFileComments;
    public pRENDERDOC_DiscardFrameCapture DiscardFrameCapture;
    public pRENDERDOC_ShowReplayUI ShowReplayUI;
    public pRENDERDOC_SetCaptureTitle SetCaptureTitle;
  }
  public unsafe delegate int pRENDERDOC_GetAPI(RENDERDOC_Version version, void **outAPIPointers);
}