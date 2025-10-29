using GTA;
using GTA.Chrono;
using GTA.Math;
using GTA.Native;
using GTA.UI;
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text;
using System.Text.RegularExpressions;
using System.Windows.Forms;

namespace DataGeneration
{
    public class MetadataLogger
    {
        private readonly string file_path;
        private readonly string header = "frame;time;weather;position;orientation;K;Rt";

        public MetadataLogger(string file_path)
        {
            if (!file_path.EndsWith("\\\\"))  file_path = file_path + "\\\\";
            this.file_path = Path.Combine(file_path, "metadata" + ".csv");
            this.WriteHeader();
        }

        public void WriteHeader()
        {
            if (File.Exists(this.file_path)) return;

            using (StreamWriter writer = new StreamWriter(file_path, false, new UTF8Encoding(false)))
            {
                writer.WriteLine(header);
            }
        }

        public void LogData(string file_name, Camera camera)
        {
            // Create a string for the data
            string data = file_name + ";";

            // Log all the game data
            data += GameData.GetTimeString() + ";" +
                    GameData.GetWeather() + ";" +
                    GameData.GetCameraPositionString(camera) + ";" +
                    GameData.GetCameraOrientationString(camera) + ";" +
                    GameData.GetIntrinsicMatrixString(camera) + ";" +
                    GameData.GetExtrinsicMatrixString(camera);

            // Read all existing lines into a list
            List<string> lines = new List<string>();
            if (File.Exists(file_path)) lines = File.ReadAllLines(this.file_path).ToList();

            // Search for the file name in the existing metadata and replace it if possible
            bool metadata_exists = false;
            for (int i = 1; i < lines.Count; i++)
            {
                if (lines[i].StartsWith(file_name + ";"))
                {
                    lines[i] = data;
                    metadata_exists = true;
                    break;
                }
            }

            // If the file_name was not found in the existing metadata, append as new line
            if (!metadata_exists) lines.Add(data);

            // Separate the header and the data for sorting
            string header_line = lines[0];
            List<string> data_lines = lines.Skip(1).ToList();

            // Sort the data lines alphabetically by the file_name
            data_lines.Sort((a, b) => string.Compare(a.Split(';')[0], b.Split(';')[0], StringComparison.Ordinal));

            // Write the header followed by the sorted data lines back to the file
            using (StreamWriter writer = new StreamWriter(file_path, false, new UTF8Encoding(false)))
            {
                writer.WriteLine(header_line);
                foreach (string data_line in data_lines) writer.WriteLine(data_line);
            }
        }
    }

    public class Location
    {
        public Vector3 position;
        public string setting;
        public bool rendered;

        public Location(string setting, float x, float y)
        {
            this.setting = setting;
            this.rendered = false;
            this.position = new Vector3(x, y, 0.0f);
        }

        public Location(string setting, float x, float y, float z, bool rendered)
        {
            this.setting = setting;
            this.rendered = rendered;
            this.position = new Vector3(x, y, z);
        }
    }

    public class RenderTargets
    {
        private readonly string file_path_csv;
        public List<Location> locations;

        public RenderTargets(string file_path_csv, bool new_file)
        {

            this.file_path_csv = file_path_csv;
            this.locations = new List<Location>();

            if (!new_file)
            {
                if (File.Exists(file_path_csv)) this.ReadCSV();
                else throw new Exception("An error occured while loading the locations.");
            }
            else
            {
                if (!File.Exists(this.file_path_csv)) File.Create(this.file_path_csv).Dispose();
            }
        }

        public void ReadCSV()
        {
            // Create a CSV-Reader
            using (StreamReader reader = new StreamReader(this.file_path_csv, new UTF8Encoding(false)))
            {
                // Read the data from the file and split it into lines
                string data = reader.ReadToEnd();
                data = Regex.Replace(data, @"\n+$", string.Empty);
                string[] lines = data.Split('\n');

                // For each line of the file
                for (int i = 0; i < lines.Length - 1; i++)
                {
                    // Split the line into values and add it to the list of locations
                    string[] values = lines[i + 1].Split(';');
                    this.locations.Add(new Location(values[0], float.Parse(values[1], CultureInfo.InvariantCulture), float.Parse(values[2], CultureInfo.InvariantCulture),
                                                    float.Parse(values[3], CultureInfo.InvariantCulture), bool.Parse(values[4])));
                }
            }
        }

        public void WriteCSV()
        {
            // Create a CSV-Writer
            using (StreamWriter writer = new StreamWriter(this.file_path_csv, false, new UTF8Encoding(false)))
            {
                // Write the header
                writer.WriteLine("setting;x;y;z;rendered");

                // For each location in the list of locations
                foreach (Location location in this.locations)
                {
                    // Write the location to the next line in the file
                    writer.WriteLine(string.Format(CultureInfo.InvariantCulture,
                                                   "{0};{1:G};{2:G};{3:G};{4}",
                                                   location.setting, location.position.X, location.position.Y,
                                                   location.position.Z, location.rendered));
                }
            }
        }

        public int GetNextLocation()
        {
            // Default value if all locations have been rendered
            int next_location = -1;

            // For each location in the list of locations
            for (int i = 0; i < this.locations.Count; i++)
            {
                // If the location hasn't been rendered yet, return its index in the list of locations
                if (!this.locations[i].rendered)
                {
                    next_location = i;
                    break;
                }
            }

            return next_location;
        }
    }

    public static class GameData
    {
        private static string Vector3ToString(Vector3 v) => string.Format(CultureInfo.InvariantCulture,
            "[{0:G},{1:G},{2:G}]",
            v.X, v.Y, v.Z);
        private static string Matrix3ToString(Matrix m) => string.Format(CultureInfo.InvariantCulture,
            "[{0:G},{1:G},{2:G},{3:G},{4:G},{5:G},{6:G},{7:G},{8:G}]",
            m[0], m[4], m[8], m[1], m[5], m[9], m[2], m[6], m[10]);
        private static string Matrix4ToString(Matrix m) => string.Format(CultureInfo.InvariantCulture,
            "[{0:G},{1:G},{2:G},{3:G},{4:G},{5:G},{6:G},{7:G},{8:G},{9:G},{10:G},{11:G},{12:G},{13:G},{14:G},{15:G}]",
            m[0], m[4], m[8], m[12], m[1], m[5], m[9], m[13], m[2], m[6], m[10], m[14], m[3], m[7], m[11], m[15]);

        public static Ped GetPlayer() => Game.Player.Character ?? throw new Exception("An error occured while retrieving the player.");

        public static Vehicle GetVehicle() => GetPlayer().CurrentVehicle ?? throw new Exception("An error occured while retrieving the vehicle of the player.");

        public static Vector3 GetCameraPosition(Camera camera)
        {
            if (camera != null) return camera.Position;
            else return GameplayCamera.Position;
        }

        public static string GetCameraPositionString(Camera camera) => Vector3ToString(GetCameraPosition(camera));

        public static Vector3 GetCameraOrientation(Camera camera)
        {
            if (camera != null) return camera.Rotation;
            else return GameplayCamera.Rotation;
        }

        public static string GetCameraOrientationString(Camera camera) => Vector3ToString(GetCameraOrientation(camera));

        public static float GetCameraFOV(Camera camera)
        {
            if (camera != null) return camera.FieldOfView;
            else return GameplayCamera.FieldOfView;
        }

        public static string GetCameraFOVString(Camera camera) => GetCameraFOV(camera).ToString();

        private static Matrix GetIntrinsicMatrix(Camera camera)
        {
            float fov;
            if (camera != null) fov = camera.FieldOfView;
            else fov = GameplayCamera.FieldOfView;

            float focal_length = (float) ((1024.0 / 2.0) / Math.Tan(fov * Math.PI / 360.0));

            float[] intrinsic_values = {focal_length, 0, 512, 0, 0, focal_length, 512, 0, 0, 0, 1, 0, 0, 0, 0, 0};
            Matrix K = new Matrix(intrinsic_values);

            return K;
        }

        public static string GetIntrinsicMatrixString(Camera camera) => Matrix3ToString(GetIntrinsicMatrix(camera));

        private static Matrix GetExtrinsicMatrix(Camera camera)
        {
            Vector3 position = GetCameraPosition(camera);
            Vector3 orienation = GetCameraOrientation(camera);

            Matrix R = Matrix.RotationQuaternion(Quaternion.Euler(orienation));

            float[] extrinsic_values = { R[0],  R[1],  R[2],  0,
                                         R[4],  R[5],  R[6],  0,
                                         R[8],  R[9],  R[10], 0,
                                         position[0], position[1], position[2], 1 };
            Matrix Rt = new Matrix(extrinsic_values);

            return Rt;
        }

        public static string GetExtrinsicMatrixString(Camera camera) => Matrix4ToString(GetExtrinsicMatrix(camera));

        public static Camera CreateCamera(Vector3 position, Vector3 orientation, float fov)
        {
            Camera camera = Camera.Create(ScriptedCameraNameHash.DefaultScriptedCamera, position, orientation, fov, true);
            Function.Call(Hash.RENDER_SCRIPT_CAMS, true, false, 0, true, false);

            return camera;
        }

        public static Camera DeleteCamera(Camera camera)
        {
            if (camera == null) return null;

            camera.Delete();
            Function.Call(Hash.RENDER_SCRIPT_CAMS, false, false, 0, true, false);

            return null;
        }

        public static string GetWeather() => World.Weather.ToString();

        public static string GetTimeString()
        {
            GameClockTime time = GameClock.Now.Time;
            string hour = time.Hour.ToString("00");
            string minute = time.Minute.ToString("00");
            string second = time.Second.ToString("00");
            string time_string = hour + ":" + minute + ":" + second;
            return time_string;
        }

        public static int[] GetTime()
        {
            GameClockTime time = GameClock.Now.Time;
            int[] time_array = new int[3];
            time_array[0] = time.Hour;
            time_array[1] = time.Minute;
            time_array[2] = time.Second;
            return time_array;
        }
    }

    public class DataGenerator : Script
    {
        private MetadataLogger metadata_logger = null;
        private MetadataLogger metadata_logger_satellite = null;
        private RenderDoc renderdoc = null;
        private RenderTargets render_targets = null;
        private Camera camera = null;

        private bool fpv = false;
        private bool freeze = false;

        // IMPORTANT:
        // This data path needs to be set to the correct absolute path before compiling the script.
        // This is either done automatically by the initialization script, by the compilation script, or it needs to be done manually.
        private readonly string data_path_orig = "C:\\Users\\USER\\Documents\\GTAGeo\\Data\\";
        private string data_path = null;
        private string data_path_satellite = null;

        public DataGenerator()
        {
            Tick += OnTick;
            KeyDown += OnKeyDown;
        }

        private void ToggleView()
        {
            // Toggle the attribute
            this.fpv = !this.fpv;
            
            // Set the camera view to either FPV or TPV
            if (this.fpv) Function.Call(Hash.SET_FOLLOW_PED_CAM_VIEW_MODE, 4);
            else Function.Call(Hash.SET_FOLLOW_PED_CAM_VIEW_MODE, 2);

            // Make the player and its vehicle visible/invisible
            Game.Player.Character.IsVisible = !this.fpv;
            if (GameData.GetPlayer().IsInVehicle()) GameData.GetVehicle().IsVisible = !this.fpv;
            if (this.fpv) Function.Call(Hash.SET_ENTITY_ALPHA, Game.Player.Character, 0);
            else Function.Call(Hash.SET_ENTITY_ALPHA, Game.Player.Character, 255);

            // Make the HUD visible/invisible
            Function.Call(Hash.DISPLAY_HUD, !this.fpv);
            Function.Call(Hash.DISPLAY_RADAR, !this.fpv);
            Function.Call(Hash.DISPLAY_AREA_NAME, !this.fpv);
            Function.Call(Hash.SET_POLICE_RADAR_BLIPS, !this.fpv);
        }

        private void ToggleFreeze()
        {
            // Toggle the attribute
            this.freeze = !this.freeze;

            // Either freeze or unfreeze each vehicle and character
            foreach (Vehicle vehicle in World.GetAllVehicles()) Function.Call(Hash.FREEZE_ENTITY_POSITION, vehicle, this.freeze);
            foreach (Ped ped in World.GetAllPeds()) Function.Call(Hash.FREEZE_ENTITY_POSITION, ped, this.freeze);

            // Either freeze or unfreeze the time
            if (this.freeze) Game.TimeScale = 0f;
            else Game.TimeScale = 1f;
        }

        public Vector3 CalculateZAndTeleport(Vector3 position, bool recalculate_z, float offset_z)
        {
            // Only re-calculate the z-coordinate if it's 0.0 or recalculate_z is set to true
            if (position.Z == 0.0f || recalculate_z)
            {
                // Start at a height of 1000.0 to search for ground
                for (float z = 1000.0f; z >= 0f; z -= 100f)
                {
                    // Teleport the player to the position with the current height
                    Function.Call(Hash.START_PLAYER_TELEPORT, Game.Player, position.X, position.Y, z, false, false, true);
                    while (Function.Call<bool>(Hash.IS_PLAYER_TELEPORT_ACTIVE)) Script.Wait(1000);

                    // Cast a ray towards the ground
                    Vector3 source = new Vector3(position.X, position.Y, z);
                    Vector3 target = new Vector3(position.X, position.Y, 0f);
                    RaycastResult ray = World.Raycast(source, target, IntersectFlags.Everything, Game.Player.Character);

                    // Save the raycast result as point if the ray hit an object
                    if (ray.DidHit)
                    {
                        position.Z = ray.HitPosition.Z;
                        break;
                    }
                }
            }

            // Teleport the character either to the location on the ground or to the height above the ground given by the offset
            if (position.Z < 0.0f) position.Z = 0.0f;
            if (offset_z > 0.0f)
            {
                position.Z += offset_z;
                Function.Call(Hash.START_PLAYER_TELEPORT, Game.Player, position.X, position.Y, position.Z, false, false, true);
                while (Function.Call<bool>(Hash.IS_PLAYER_TELEPORT_ACTIVE)) Script.Wait(1000);
            }
            else
            {
                Function.Call(Hash.START_PLAYER_TELEPORT, Game.Player, position.X, position.Y, position.Z + 25.0f, false, true, true);
                while (Function.Call<bool>(Hash.IS_PLAYER_TELEPORT_ACTIVE)) Script.Wait(1000);
            }

            return position;
        }

        private void RenderSingleView(string file_name, string data_path, MetadataLogger logger, Vector3? camera_position, Vector3? camera_orientation, float fov)
        {
            // Save the current camera position and orientation
            if (camera_position == null) camera_position = GameData.GetCameraPosition(null);
            if (camera_orientation == null) camera_orientation = GameData.GetCameraOrientation(null);
            if (fov == 0) fov = GameData.GetCameraFOV(null);

            // Create a new camera with the position and orientation of the game camera and set the FOV
            this.camera = GameData.CreateCamera(camera_position.Value, camera_orientation.Value, fov);

            // Trigger the frame capture using RenderDoc
            string path = data_path + file_name;
            renderdoc.API.SetCaptureFilePathTemplate(path);
            renderdoc.API.TriggerCapture();

            // Wait for the creation of the RGB file
            string file_pattern = string.Format("{0}_rgb.jpg", file_name);
            bool file_created = false;
            while (!file_created)
            {
                string[] files = Directory.GetFiles(data_path, file_pattern);
                if (files.Length > 0)
                {
                    break;
                }
                Script.Wait(1000);
            }

            // Log the metadata
            logger.LogData(file_name, camera);

            // Delete the camera
            this.camera = GameData.DeleteCamera(this.camera);
        }

        private void PreDataGeneration()
        {
            // Initialize RenderDoc if not already initialized
            if (this.renderdoc == null) this.renderdoc = new RenderDoc(this.data_path);

            // Initialize the metadata loggers if not already initialized
            if (this.metadata_logger == null) this.metadata_logger = new MetadataLogger(this.data_path);
            if (this.metadata_logger_satellite == null) this.metadata_logger_satellite = new MetadataLogger(this.data_path_satellite);

            // Initialize the render targets if not already initialized
            if (this.render_targets == null) this.render_targets = new RenderTargets(this.data_path + "render_targets.csv", false);

            // Switch to FPV and hide all HUD elements
            if (!this.fpv) this.ToggleView();

            // Activate no clip mode
            NoClip.Instance?.ToggleNoClip();
        }

        private void PostDataGeneration()
        {
            // Switch to TPV and show all HUD elements
            if (this.fpv) this.ToggleView();

            // De-activate no clip mode
            NoClip.Instance?.ToggleNoClip();
        }

        private void SetWeatherTime(string weather, int h, int m, int s)
        {
            // Set the weather
            Function.Call(Hash.SET_WEATHER_TYPE_NOW_PERSIST, weather);

            // Set the time
            Function.Call(Hash.SET_CLOCK_TIME, h, m, s);

            // Wait for the changes
            Script.Wait(2000);
        }

        private void OnTick(object sender, EventArgs e)
        {
            // Disable all phone interactions
            Function.Call(Hash.TERMINATE_ALL_SCRIPTS_WITH_THIS_NAME, "cellphone_controller");

            // Disable looking backwards, attack moves, the weapon wheel, and character changes
            Function.Call(Hash.DISABLE_CONTROL_ACTION, 2, 12, true);
            Function.Call(Hash.DISABLE_CONTROL_ACTION, 2, 13, true);
            Function.Call(Hash.DISABLE_CONTROL_ACTION, 2, 14, true);
            Function.Call(Hash.DISABLE_CONTROL_ACTION, 2, 15, true);
            Function.Call(Hash.DISABLE_CONTROL_ACTION, 2, 16, true);
            Function.Call(Hash.DISABLE_CONTROL_ACTION, 2, 17, true);
            Function.Call(Hash.DISABLE_CONTROL_ACTION, 2, 19, true);
            Function.Call(Hash.DISABLE_CONTROL_ACTION, 2, 24, true);
            Function.Call(Hash.DISABLE_CONTROL_ACTION, 2, 25, true);
            Function.Call(Hash.DISABLE_CONTROL_ACTION, 2, 26, true);
            Function.Call(Hash.DISABLE_CONTROL_ACTION, 2, 37, true);
            Function.Call(Hash.DISABLE_CONTROL_ACTION, 2, 79, true);

            // Set the player invincible and disable police
            Function.Call(Hash.SET_PLAYER_INVINCIBLE, Game.Player, true);
            Function.Call(Hash.SET_POLICE_IGNORE_PLAYER, Game.Player, true);
            Function.Call(Hash.SET_EVERYONE_IGNORE_PLAYER, Game.Player, true);
            Function.Call(Hash.SET_MAX_WANTED_LEVEL, 0);
            Function.Call(Hash.CLEAR_PLAYER_WANTED_LEVEL, Game.Player);
        }

        private void OnKeyDown(object sender, KeyEventArgs e)
        {

            // F6: Toggle the view
            if (e.KeyCode == Keys.F6)
            {
                this.ToggleView();
                if (this.fpv) Notification.PostTicker("FPV ~b~enabled~w~.", false);
                else Notification.PostTicker("FPV ~r~disabled~w~.", false);
            }

            // F7: Toggle the freezing of the scene
            if (e.KeyCode == Keys.F7)
            {
                this.ToggleFreeze();
                if (this.freeze) Notification.PostTicker("Scene freeze ~b~enabled~w~.", false);
                else Notification.PostTicker("Scene freeze ~r~disabled~w~.", false);
            }

            // F8: Toggle the No-Clip mode
            if (e.KeyCode == Keys.F8)
            {
                // Reserved for NoClip
            }

            // F9: GROUND-VIEW DATA GENERATION
            // - Position: random
            // - Orientation: random
            // - Panorama: no
            // - Iterations: 100
            if (e.KeyCode == Keys.F9)
            {
                // Set the data paths to 'ground-view' and 'satellite-view'
                this.data_path = this.data_path_orig + "ground-view\\";
                this.data_path_satellite = this.data_path_orig + "satellite-view\\";

                // Initialize RenderDoc, the metadata logger, and the render targets if not already initialized,
                // switch to FPV, hide all HUD elements, activate no clip mode and disable the visibility of the player model
                this.PreDataGeneration();

                // For each location that has not been completed yet
                for (int i = 0; i < 100; i++)
                {
                    // Declare the random number generator
                    Random random;

                    // Generate random locations until one is on land
                    Vector3 position = new Vector3(0f, 0f, 0f);
                    while (position.Z <= 0f)
                    {
                        // Get a random location
                        random = new Random();
                        float pos_x = (float)(10 * random.NextDouble());
                        float pos_y = (float)(10 * random.NextDouble());
                        float pos_z = 0f;
                        position = new Vector3(pos_x, pos_y, pos_z);

                        // Teleport the player to that location
                        position = this.CalculateZAndTeleport(position, true, 0f);
                    }

                    // Generate a random orientation
                    random = new Random();
                    float rot_x = (float)(10 * random.NextDouble());
                    float rot_y = 0f;
                    float rot_z = (float)(360 * random.NextDouble());
                    Vector3 orientation = new Vector3(rot_x, rot_y, rot_z);

                    // Set the weather to extra sunny and the time to a random value between 6 AM and 7 PM
                    random = new Random();
                    int h = random.Next(6, 19);
                    int m = random.Next(0, 60);
                    int s = random.Next(0, 60);
                    this.SetWeatherTime("EXTRASUNNY", h, m, s);

                    // Set the file name
                    string setting = "random";
                    string file_name = string.Format("{0}_{1:D7}", setting, i);

                    // Freeze the scene
                    this.ToggleFreeze();

                    // Render the scene
                    this.RenderSingleView(file_name, this.data_path, this.metadata_logger, null, orientation, 90f);

                    // Un-freeze the scene
                    this.ToggleFreeze();

                    // Teleport the player to an altitude of 100m
                    this.CalculateZAndTeleport(position, false, 100f);

                    // Set the weather to extra sunny and the time to 12 PM
                    this.SetWeatherTime("EXTRASUNNY", 12, 0, 0);

                    // Freeze the scene
                    this.ToggleFreeze();

                    // Render the scene
                    this.RenderSingleView(file_name, this.data_path_satellite, this.metadata_logger_satellite, null, new Vector3(-90f, 0f, 0f), 50f);

                    // Un-freeze the scene
                    this.ToggleFreeze();
                }

                // Switch to TPV, show all HUD elements, de-activate no clip mode and enable the visibility of the player model
                this.PostDataGeneration();
            }

            // F10: GROUND-VIEW DATA GENERATION
            // - Position: pre-defined
            // - Orientation: full 360°
            // - Panorama: yes
            // - Iterations: pre-defined
            if (e.KeyCode == Keys.F10)
            {
                // Set the data paths to 'ground-view' and 'satellite-view'
                this.data_path = this.data_path_orig + "ground-view\\";
                this.data_path_satellite = this.data_path_orig + "satellite-view\\";

                // Initialize RenderDoc, the metadata logger, and the render targets if not already initialized,
                // switch to FPV, hide all HUD elements, activate no clip mode and disable the visibility of the player model
                this.PreDataGeneration();

                // For each location that has not been completed yet
                int i = this.render_targets.GetNextLocation();
                while (i >= 0 && i < this.render_targets.locations.Count)
                {
                    // Declare the random number generator
                    Random random;

                    // Teleport player to the next position and don't re-calculate the z-value
                    this.render_targets.locations[i].position = this.CalculateZAndTeleport(this.render_targets.locations[i].position, false, 0f);
                    this.render_targets.WriteCSV();

                    // Set the weather to extra sunny and the time to a random value between 6 AM and 7 PM
                    random = new Random();
                    int h = random.Next(6, 19);
                    int m = random.Next(0, 60);
                    int s = random.Next(0, 60);
                    this.SetWeatherTime("EXTRASUNNY", h, m, s);

                    // Freeze the scene
                    this.ToggleFreeze();

                    // Save the camera position
                    Vector3 position = GameData.GetCameraPosition(null);

                    // For each of the 18 different viewing angles
                    for (int j = 0; j < 18; j++)
                    {
                        Vector3 orientation;
                        string heading;

                        // Set the camera orientation and heading tag accordingly
                        switch (j)
                        {
                            case 0:
                                heading = "N";
                                orientation = new Vector3(0f, 0f, 0f);
                                break;
                            case 1:
                                heading = "S";
                                orientation = new Vector3(0f, 0f, 180f);
                                break;
                            case 2:
                                heading = "E";
                                orientation = new Vector3(0f, 0f, 270f);
                                break;
                            case 3:
                                heading = "W";
                                orientation = new Vector3(0f, 0f, 90f);
                                break;
                            case 4:
                                heading = "U";
                                orientation = new Vector3(90f, 0f, 0f);
                                break;
                            case 5:
                                heading = "D";
                                orientation = new Vector3(-90f, 0f, 0f);
                                break;
                            case 6:
                                heading = "NE";
                                orientation = new Vector3(0f, 0f, 315f);
                                break;
                            case 7:
                                heading = "NW";
                                orientation = new Vector3(0f, 0f, 45f);
                                break;
                            case 8:
                                heading = "SE";
                                orientation = new Vector3(0f, 0f, 225f);
                                break;
                            case 9:
                                heading = "SW";
                                orientation = new Vector3(0f, 0f, 135f);
                                break;
                            case 10:
                                heading = "UN";
                                orientation = new Vector3(45f, 0f, 0f);
                                break;
                            case 11:
                                heading = "US";
                                orientation = new Vector3(45f, 0f, 180f);
                                break;
                            case 12:
                                heading = "UE";
                                orientation = new Vector3(45f, 0f, 270f);
                                break;
                            case 13:
                                heading = "UW";
                                orientation = new Vector3(45f, 0f, 90f);
                                break;
                            case 14:
                                heading = "DN";
                                orientation = new Vector3(-45f, 0f, 0f);
                                break;
                            case 15:
                                heading = "DS";
                                orientation = new Vector3(-45f, 0f, 180f);
                                break;
                            case 16:
                                heading = "DE";
                                orientation = new Vector3(-45f, 0f, 270f);
                                break;
                            case 17:
                                heading = "DW";
                                orientation = new Vector3(-45f, 0f, 90f);
                                break;
                            default:
                                heading = "X";
                                orientation = new Vector3(0f, 0f, 0f);
                                break;
                        }

                        // Set the file name
                        string setting = this.render_targets.locations[i].setting;
                        string file_name = string.Format("{0}_{1:D7}_{2}", setting, i, heading);

                        // Render the scene
                        this.RenderSingleView(file_name, this.data_path, this.metadata_logger, position, orientation, 90f);
                    }

                    // Un-freeze the scene
                    this.ToggleFreeze();

                    // Teleport the player to an altitude of 100m
                    this.CalculateZAndTeleport(this.render_targets.locations[i].position, false, 100f);

                    // Set the weather to extra sunny and the time to 12 PM
                    this.SetWeatherTime("EXTRASUNNY", 12, 0, 0);

                    // Set the file name
                    string setting_satellite = this.render_targets.locations[i].setting;
                    string file_name_satellite = string.Format("{0}_{1:D7}", setting_satellite, i);

                    // Freeze the scene
                    this.ToggleFreeze();

                    // Render the scene
                    this.RenderSingleView(file_name_satellite, this.data_path_satellite, this.metadata_logger_satellite, null, new Vector3(-90f, 0f, 0f), 50f);

                    // Un-freeze the scene
                    this.ToggleFreeze();

                    // Mark the location as rendered
                    this.render_targets.locations[i].rendered = true;
                    this.render_targets.WriteCSV();

                    // Get the next location
                    i = this.render_targets.GetNextLocation();
                }

                // Switch to TPV, show all HUD elements, de-activate no clip mode and enable the visibility of the player model
                this.PostDataGeneration();
            }

            // F11: DRONE-VIEW DATA GENERATION
            // - Position: pre-defined
            // - Orientation: towards focus point
            // - Panorama: no
            // - Iterations: pre-defined
            if (e.KeyCode == Keys.F11)
            {
                // Set the data paths to 'drone-view' and 'satellite-view'
                this.data_path = this.data_path_orig + "drone-view\\";
                this.data_path_satellite = this.data_path_orig + "satellite-view\\";

                // Initialize RenderDoc, the metadata logger, and the render targets if not already initialized,
                // switch to FPV, hide all HUD elements, activate no clip mode and disable the visibility of the player model
                this.PreDataGeneration();

                // For each location that has not been completed yet
                int i = this.render_targets.GetNextLocation();
                while (i >= 0 && i < this.render_targets.locations.Count)
                {
                    // Teleport player to the next position and don't re-calculate the z-value
                    this.render_targets.locations[i].position = this.CalculateZAndTeleport(this.render_targets.locations[i].position, false, 0f);
                    this.render_targets.WriteCSV();

                    // Set the weather to extra sunny and the time to 12 PM
                    this.SetWeatherTime("EXTRASUNNY", 12, 0, 0);

                    // Freeze the scene
                    this.ToggleFreeze();

                    // For each of the 64 different viewing angles
                    for (int j = 0; j < 64; j++)
                    {
                        // Set the distance to the original camera position
                        float distance = 50.0f;
                        if (j >= 32) distance = 75.0f;

                        // Calculate the new position
                        float angle = (2 * (float)Math.PI / 32.0f) * ((float)(j % 32));
                        float pos_x = this.render_targets.locations[i].position.X + (float)(-Math.Sin(angle) * distance);
                        float pos_y = this.render_targets.locations[i].position.Y + (float)(-Math.Cos(angle) * distance);
                        float pos_z = this.render_targets.locations[i].position.Z + distance;
                        Vector3 position = new Vector3(pos_x, pos_y, pos_z);

                        // Calculate the new orientation
                        Vector3 direction = Vector3.Normalize(this.render_targets.locations[i].position - position);
                        float rot_x = (float)Math.Asin(direction.Z) * (180.0f / (float)Math.PI);
                        float rot_y = 0.0f;
                        float rot_z = (float)Math.Atan2(direction.X, direction.Y) * (-180.0f / (float)Math.PI);
                        Vector3 orientation = new Vector3(rot_x, rot_y, rot_z);

                        // Set the heading tag
                        string heading = string.Format("{0:D2}_{1:D2}", (int)distance, j);

                        // Set the file name
                        string setting = this.render_targets.locations[i].setting;
                        string file_name = string.Format("{0}_{1:D7}_{2}", setting, i, heading);

                        // Render the scene
                        this.RenderSingleView(file_name, this.data_path, this.metadata_logger, position, orientation, 50f);
                    }

                    // Un-freeze the scene
                    this.ToggleFreeze();

                    // Teleport the player to an altitude of 100m
                    this.CalculateZAndTeleport(this.render_targets.locations[i].position, false, 100f);

                    // Set the weather to extra sunny and the time to 12 PM
                    this.SetWeatherTime("EXTRASUNNY", 12, 0, 0);

                    // Set the file name
                    string setting_satellite = this.render_targets.locations[i].setting;
                    string file_name_satellite = string.Format("{0}_{1:D7}", setting_satellite, i);

                    // Freeze the scene
                    this.ToggleFreeze();

                    // Render the scene
                    this.RenderSingleView(file_name_satellite, this.data_path_satellite, this.metadata_logger_satellite, null, new Vector3(-90f, 0f, 0f), 50f);

                    // Un-freeze the scene
                    this.ToggleFreeze();

                    // Mark the location as rendered
                    this.render_targets.locations[i].rendered = true;
                    this.render_targets.WriteCSV();

                    // Get the next location
                    i = this.render_targets.GetNextLocation();
                }

                // Switch to TPV, show all HUD elements, de-activate no clip mode and enable the visibility of the player model
                this.PostDataGeneration();
            }

            // F12: Trigger the RenderDoc frame capture
            if (e.KeyCode == Keys.F12)
            {
                // Reserved for RenderDoc
            }
        }
    }
}
