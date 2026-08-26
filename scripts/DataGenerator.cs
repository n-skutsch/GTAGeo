using GTA;
using GTA.Chrono;
using GTA.Math;
using GTA.Native;
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Text;
using System.Windows.Forms;
using Tomlyn;


namespace DataGeneration
{

    // ----------------------------------------------------------
    // Config
    // ----------------------------------------------------------

    // This class heavily depends on the 'config.toml' file of the project.
    public static class GlobalConfig
    {
        public static Config Config { get; set; } = new Config();
    }

    public class Config
    {
        public ConfigPaths Paths { get; set; } = new ConfigPaths();
        public ConfigGeneration Generation { get; set; } = new ConfigGeneration();
        public ConfigCamera Camera { get; set; } = new ConfigCamera();
        public ConfigRandom Random { get; set; } = new ConfigRandom();
        public ConfigMap Map { get; set; } = new ConfigMap();
        public ConfigPanorama Panorama { get; set; } = new ConfigPanorama();
        public List<Rotation> PanoramaRotations { get; set; } = new List<Rotation>();
        public List<Rotation> AerialViewRotations { get; set; } = new List<Rotation>();

        public void Validate()
        {
            this.Paths.ValidatePaths();
            this.Random.ValidateRandomLists();
            this.Map.ValidateMapDimensions();
            this.Panorama.ValidatePanoramaHeadings();
        }
    }

    public class ConfigPaths
    {
        public string Data { get; set; } = "";
        public string DataGroundView { get; set; } = "";
        public string DataGroundViewPano { get; set; } = "";
        public string DataDroneView { get; set; } = "";
        public string DataAerialView { get; set; } = "";
        public string DataAerialViewArea { get; set; } = "";

        public void ValidatePaths()
        {
            foreach (PropertyInfo property in typeof(ConfigPaths).GetProperties())
            {
                string propertyResolved = Environment.ExpandEnvironmentVariables((string) property.GetValue(this));
                if (propertyResolved.Contains('%')) throw new InvalidOperationException($"Unresolved environment variable in path: {propertyResolved}");
                property.SetValue(this, propertyResolved);
            }
        }
    }

    public class ConfigGeneration
    {
        public bool GenerateRGB { get; set; }
        public bool GenerateDepth { get; set; }
        public bool GenerateStencil { get; set; }
        public int Checkpoint { get; set; }
        public float Padding { get; set; }
        public float Overlap { get; set; }
        public int WaitAfterChange { get; set; }
        public string WaitForFileRGB { get; set; } = "";
        public string WaitForFileDepth { get; set; } = "";
        public string WaitForFileStencil { get; set; } = "";
    }

    public class ConfigCamera
    {
        public float GroundDroneFOV { get; set; }
        public float AerialFOV { get; set; }
        public float GSD { get; set; }
        public float MinimumDistance { get; set; }
        public float MaximumRenderDistance { get; set; }
        public int NumberOfRays { get; set; }
    }

    public class ConfigRandom
    {
        public bool RandomTime { get; set; }
        public bool RandomWeather { get; set; }
        public int NumberOfRandomLocations { get; set; }
        public List<string> WeatherTypes { get; set; } = new List<string>();
        public List<float> RotationRanges { get; set; } = new List<float>();

        public void ValidateRandomLists()
        {
            if (this.WeatherTypes.Count <= 0) throw new ArgumentException($"The 'WeatherTypes' field in the config file is invalid. It requires at least one entry.");
            if (this.RotationRanges.Count != 6) throw new ArgumentException($"The 'RotationRanges' field in the config file is invalid. It requires exactly 6 entries.");
        }
    }

    public class ConfigMap
    {
        public List<float> MapDimensions { get; set; } = new List<float>();

        public void ValidateMapDimensions()
        {
            if (this.MapDimensions.Count != 6) throw new ArgumentException($"The 'MapDimensions' field in the config file is invalid. It requires exactly 6 entries.");
        }
    }

    public class ConfigPanorama
    {
        public List<string> PanoramaHeadings { get; set; } = new List<string>();

        public void ValidatePanoramaHeadings()
        {
            if (this.PanoramaHeadings.Count != 18) throw new ArgumentException($"The 'PanoramaHeadings' field in the config file is invalid. It requires exactly 18 entries.");
        }
    }

    public class Rotation
    {
        public float X { get; set; }
        public float Y { get; set; }
        public float Z { get; set; }
    }


    // ----------------------------------------------------------
    // Logging
    // ----------------------------------------------------------

    public class MetadataLogger
    {
        private readonly string filePath;

        public MetadataLogger(string filePath)
        {
            this.filePath = Path.Combine(filePath, "metadata.csv");
            if (!File.Exists(this.filePath)) File.WriteAllText(this.filePath, "file;time;weather;position;rotation;K;Rt;FOV\n");
        }

        private static string F(float f) => f.ToString(CultureInfo.InvariantCulture);
        private static string Vector3ToString(Vector3 v) => $"[{F(v.X)},{F(v.Y)},{F(v.Z)}]";
        private static string Matrix3ToString(Matrix m) => $"[{F(m.M11)},{F(m.M12)},{F(m.M13)}," +
                                                           $"{F(m.M21)},{F(m.M22)},{F(m.M23)}," +
                                                           $"{F(m.M31)},{F(m.M32)},{F(m.M33)}]";
        private static string Matrix4ToString(Matrix m) => $"[{F(m.M11)},{F(m.M12)},{F(m.M13)},{F(m.M14)}," +
                                                           $"{F(m.M21)},{F(m.M22)},{F(m.M23)},{F(m.M24)}," +
                                                           $"{F(m.M31)},{F(m.M32)},{F(m.M33)},{F(m.M34)}," +
                                                           $"{F(m.M41)},{F(m.M42)},{F(m.M43)},{F(m.M44)}]";

        public void LogMetadata(string fileName, Camera camera)
        {
            var line = string.Join(";",
                fileName,
                GameData.GetTime(),
                GameData.GetWeather(),
                Vector3ToString(GameData.GetCameraPosition(camera)),
                Vector3ToString(GameData.GetCameraRotation(camera)),
                Matrix3ToString(GameData.GetIntrinsicMatrix(camera)),
                Matrix4ToString(GameData.GetExtrinsicMatrix(camera)),
                F(GameData.GetCameraFOV(camera)));
            File.AppendAllText(this.filePath, line + "\n");
        }

        public void SortMetadata()
        {
            if (!File.Exists(this.filePath)) throw new FileNotFoundException("Metadata file not found.", this.filePath);

            // Read all metadata from the file and only keep the latest values for each query
            string header = null;
            Dictionary<string, string> metadataDict = new Dictionary<string, string>();
            foreach (string line in File.ReadLines(filePath))
            {
                int firstSeparator = line.IndexOf(';');

                if (string.IsNullOrWhiteSpace(line)) continue;
                if (firstSeparator <= 0) continue;
                if (header == null)
                {
                    header = line;
                    continue;
                }

                string key = line.Substring(0, firstSeparator);
                metadataDict[key] = line;
            }

            // Sort the metadata by file name and write it back to the file
            string tempPath = this.filePath + ".tmp";
            using (StreamWriter csvWriter = new StreamWriter(tempPath, false))
            {
                if (header != null) csvWriter.WriteLine(header);
                foreach (string line in metadataDict.OrderBy(k => k.Key, StringComparer.Ordinal).Select(k => k.Value))
                {
                    csvWriter.WriteLine(line);
                }
            }
            File.Replace(tempPath, this.filePath, null);
        }
    }


    // ----------------------------------------------------------
    // Game Data, Modification, and Game State
    // ----------------------------------------------------------

    public static class GameData
    {
        public static Vector3 GetCameraPosition(Camera camera) => camera != null ? camera.Position : GameplayCamera.Position;
        public static Vector3 GetCameraRotation(Camera camera) => camera != null ? camera.Rotation : GameplayCamera.Rotation;
        public static float GetCameraFOV(Camera camera) => camera != null ? camera.FieldOfView : GameplayCamera.FieldOfView;
        public static string GetTime() => GameClock.Now.Time.ToString();
        public static string GetWeather() => World.Weather.ToString();

        public static int[] GetResolution()
        {
            OutputArgument x = new OutputArgument();
            OutputArgument y = new OutputArgument();
            Function.Call(Hash.GET_ACTUAL_SCREEN_RESOLUTION, x, y);
            return new[] { x.GetResult<int>(), y.GetResult<int>() };
        }

        public static Matrix GetIntrinsicMatrix(Camera camera)
        {
            int[] resolution = GetResolution();
            float fov = GetCameraFOV(camera);

            float f_x = (float)(resolution[0] / (2.0 * Math.Tan(fov * Math.PI / 360.0)));
            float f_y = (float)(resolution[1] / (2.0 * Math.Tan(fov * Math.PI / 360.0)));

            float c_x = resolution[0] / 2f;
            float c_y = resolution[1] / 2f;

            Matrix K = Matrix.Zero;

            K.M11 = f_x; K.M12 = 0f;  K.M13 = c_x; K.M14 = 0f;
            K.M21 = 0f;  K.M22 = f_y; K.M23 = c_y; K.M24 = 0f;
            K.M31 = 0f;  K.M32 = 0f;  K.M33 = 1f;  K.M34 = 0f;
            K.M41 = 0f;  K.M42 = 0f;  K.M43 = 0f;  K.M44 = 1f;

            return K;
        }

        public static Matrix GetExtrinsicMatrix(Camera camera)
        {
            Vector3 position = GetCameraPosition(camera);
            Vector3 rotation = GetCameraRotation(camera);

            Matrix R = Matrix.Transpose(Matrix.RotationQuaternion(Quaternion.Euler(rotation)));

            float t_x = -(R.M11 * position.X + R.M12 * position.Y + R.M13 * position.Z);
            float t_y = -(R.M21 * position.X + R.M22 * position.Y + R.M23 * position.Z);
            float t_z = -(R.M31 * position.X + R.M32 * position.Y + R.M33 * position.Z);

            Matrix Rt = Matrix.Zero;

            Rt.M11 = R.M11; Rt.M12 = R.M12; Rt.M13 = R.M13; Rt.M14 = t_x;
            Rt.M21 = R.M21; Rt.M22 = R.M22; Rt.M23 = R.M23; Rt.M24 = t_y;
            Rt.M31 = R.M31; Rt.M32 = R.M32; Rt.M33 = R.M33; Rt.M34 = t_z;
            Rt.M41 = 0f;    Rt.M42 = 0f;    Rt.M43 = 0f;    Rt.M44 = 1f;

            return Rt;
        }

        public static float GetAerialViewCameraAltitude(Camera camera, float fov)
        {
            int[] resolution = GameData.GetResolution();
            float area = (float)Math.Min(resolution[0], resolution[1]) * GlobalConfig.Config.Camera.GSD;
            float altitude = area / (2f * (float)Math.Tan((double)fov * Math.PI / 360d));
            return altitude;
        }

        public static Camera CreateCamera(Vector3 position, Vector3 rotation, float fov)
        {
            Camera camera = Camera.Create(ScriptedCameraNameHash.DefaultScriptedCamera, position, rotation, fov, true);
            Function.Call(Hash.RENDER_SCRIPT_CAMS, true, false, 0, true, false);
            return camera;
        }

        public static void DeleteCamera(Camera camera)
        {
            if (camera == null) return;
            camera.Delete();
            Function.Call(Hash.RENDER_SCRIPT_CAMS, false, false, 0, true, false);
        }

        public static void TeleportPlayer(Vector3 newPosition, Location location, GameState gameState = null)
        {
            // Calculate the z-coordinate if it's unknown
            if (newPosition.Z == 0f)
            {
                bool groundFound = false;
                for (float z = 1000f; z >= 0f && !groundFound; z -= 200f)
                {
                    Function.Call(Hash.START_PLAYER_TELEPORT, Game.Player, newPosition.X, newPosition.Y, z, 0f, false, false, true);
                    while (Function.Call<bool>(Hash.IS_PLAYER_TELEPORT_ACTIVE)) Script.Wait(100);
                    while (!Function.Call<bool>(Hash.HAS_COLLISION_LOADED_AROUND_ENTITY, Game.Player.Character)) Script.Wait(100);

                    OutputArgument newZ = new OutputArgument();
                    groundFound = Function.Call<bool>(Hash.GET_GROUND_Z_FOR_3D_COORD, newPosition.X, newPosition.Y, z, newZ, false);

                    if (groundFound) newPosition.Z = newZ.GetResult<float>();
                }

                for (float z = 1000f; z >= 0f && !groundFound; z -= 200f)
                {
                    Function.Call(Hash.START_PLAYER_TELEPORT, Game.Player, newPosition.X, newPosition.Y, z, 0f, false, false, true);
                    while (Function.Call<bool>(Hash.IS_PLAYER_TELEPORT_ACTIVE)) Script.Wait(100);
                    while (!Function.Call<bool>(Hash.HAS_COLLISION_LOADED_AROUND_ENTITY, Game.Player.Character)) Script.Wait(100);

                    Vector3 source = new Vector3(newPosition.X, newPosition.Y, z);
                    Vector3 target = new Vector3(newPosition.X, newPosition.Y, 0f);
                    RaycastResult ray = World.Raycast(source, target, IntersectFlags.Everything, Game.Player.Character);

                    if (ray.DidHit) { newPosition.Z = ray.HitPosition.Z; groundFound = true; }
                }

                if (!groundFound) throw new Exception("The ground could not be found during teleportation.");
            }

            // Teleport the player to the ground
            Function.Call(Hash.START_PLAYER_TELEPORT, Game.Player, newPosition.X, newPosition.Y, newPosition.Z, 0f, false, false, true);
            while (Function.Call<bool>(Hash.IS_PLAYER_TELEPORT_ACTIVE)) Script.Wait(100);

            // Re-apply the No-Clip state, since the native teleport can reset the player's freeze/gravity flags
            if (gameState != null && gameState.NoClip.Active) gameState.NoClip.Refresh();

            // Update the location
            if (location != null) location.Position = newPosition;

            // Wait for the lighting to adjust
            Script.Wait(GlobalConfig.Config.Generation.WaitAfterChange);
        }

        public static float ClosestObjectToCamera(Vector3 cameraPosition, Vector3 cameraRotation)
        {
            Camera camera = Camera.Create(ScriptedCameraNameHash.DefaultScriptedCamera, cameraPosition, cameraRotation, GameData.GetCameraFOV(null), false);

            float fov = GameData.GetCameraFOV(camera);
            float tanFov = (float)Math.Tan(fov * 0.5f * Math.PI / 180.0);

            float closestDistance = float.MaxValue;
            for (int x = 0; x < GlobalConfig.Config.Camera.NumberOfRays; x++)
            {
                for (int y = 0; y < GlobalConfig.Config.Camera.NumberOfRays; y++)
                {
                    float u = ((x + 0.5f) / GlobalConfig.Config.Camera.NumberOfRays) * 2f - 1f;
                    float v = ((y + 0.5f) / GlobalConfig.Config.Camera.NumberOfRays) * 2f - 1f;

                    Vector3 dir = (camera.ForwardVector + camera.RightVector * (u * tanFov) + camera.UpVector * (v * tanFov)).Normalized;
                    RaycastResult ray = World.Raycast(cameraPosition, cameraPosition + dir * GlobalConfig.Config.Camera.MaximumRenderDistance, IntersectFlags.Everything, Game.Player.Character);

                    if (ray.DidHit)
                    {
                        float distance = ray.HitPosition.DistanceTo(cameraPosition);
                        if (distance < closestDistance) closestDistance = distance;
                    }
                }
            }
            camera.Delete();

            return closestDistance;
        }

        public static Vector3 TeleportPlayerRandom(GameState gameState, int timeoutMs = 30000)
        {
            DateTime start = DateTime.Now;

            Vector3 randomPosition = new Vector3(0f, 0f, 0f);
            bool validPosition = false;
            while (!validPosition)
            {
                // Check for timeout
                if ((DateTime.Now - start).TotalMilliseconds > timeoutMs) throw new TimeoutException();

                // Create a new random position
                float x = (GlobalConfig.Config.Map.MapDimensions[1] - GlobalConfig.Config.Map.MapDimensions[0]) * (float)gameState.RandomGenerator.NextDouble() + GlobalConfig.Config.Map.MapDimensions[0];
                float y = (GlobalConfig.Config.Map.MapDimensions[3] - GlobalConfig.Config.Map.MapDimensions[2]) * (float)gameState.RandomGenerator.NextDouble() + GlobalConfig.Config.Map.MapDimensions[2];
                randomPosition = new Vector3(x, y, 0f);

                // Teleport the player and check if the position is valid
                try
                {
                    GameData.TeleportPlayer(randomPosition, null, gameState);
                    if (!Game.Player.Character.IsInWater) validPosition = true;
                }
                catch (Exception)
                {
                    // Ground could not be found (e.g. open water) - try a new random position
                }
            }

            Vector3 randomRotation = new Vector3(0f, 0f, 0f);
            bool validRotation = false;
            while (!validRotation)
            {
                // Check for timeout
                if ((DateTime.Now - start).TotalMilliseconds > timeoutMs) throw new TimeoutException();

                // Create a new random rotation
                float pitch = (GlobalConfig.Config.Random.RotationRanges[1] - GlobalConfig.Config.Random.RotationRanges[0]) * (float)gameState.RandomGenerator.NextDouble() + GlobalConfig.Config.Random.RotationRanges[0];
                float roll = (GlobalConfig.Config.Random.RotationRanges[3] - GlobalConfig.Config.Random.RotationRanges[2]) * (float)gameState.RandomGenerator.NextDouble() + GlobalConfig.Config.Random.RotationRanges[2];
                float yaw = (GlobalConfig.Config.Random.RotationRanges[5] - GlobalConfig.Config.Random.RotationRanges[4]) * (float)gameState.RandomGenerator.NextDouble() + GlobalConfig.Config.Random.RotationRanges[4];
                randomRotation = new Vector3(pitch, roll, yaw);

                // Check if the rotation is valid
                if (GameData.ClosestObjectToCamera(randomPosition, randomRotation) >= GlobalConfig.Config.Camera.MinimumDistance) validRotation = true;
            }

            return randomRotation;
        }
    }

    public class VisualModifier
    {
        public bool Active = false;

        public void OnTick()
        {
            if (!this.Active) return;

            // Remove all vehicles
            foreach (Vehicle vehicle in World.GetAllVehicles()) if (vehicle.Exists()) vehicle.Delete();
            Function.Call(Hash.SET_VEHICLE_DENSITY_MULTIPLIER_THIS_FRAME, 0.0f);
            Function.Call(Hash.SET_RANDOM_VEHICLE_DENSITY_MULTIPLIER_THIS_FRAME, 0.0f);
            Function.Call(Hash.SET_PARKED_VEHICLE_DENSITY_MULTIPLIER_THIS_FRAME, 0.0f);

            // Remove all PEDs
            foreach (Ped ped in World.GetAllPeds()) if (ped.Exists()) ped.Delete();
            Function.Call(Hash.SET_PED_DENSITY_MULTIPLIER_THIS_FRAME, 0.0f);
            Function.Call(Hash.SET_SCENARIO_PED_DENSITY_MULTIPLIER_THIS_FRAME, 0.0f, 0.0f);
        }

        public void Toggle()
        {
            this.Active = !this.Active;
            if (this.Active) Function.Call(Hash.SET_TIMECYCLE_MODIFIER, "INT_NO_fogALPHA");
            else Function.Call(Hash.CLEAR_TIMECYCLE_MODIFIER);
        }
    }

    public class NoClip
    {
        public bool Active = false;
        private int SpeedLevel = 2;
        private readonly float[] speeds = { 0.25f, 0.5f, 1.0f, 2.0f, 4.0f, 8.0f, 16.0f };

        private void ResetSpeedLevel() { this.SpeedLevel = 2; }
        public void IncreaseSpeedLevel() { if (this.SpeedLevel + 1 < this.speeds.Length) this.SpeedLevel++; }
        public void DecreaseSpeedLevel() { if (this.SpeedLevel - 1 >= 0) this.SpeedLevel--; }

        private Vector3 GetDirectionFromInput()
        {
            // Define vectors for each direction
            Vector3 direction = Vector3.Zero;
            Vector3 vector_forward = GameplayCamera.Direction;
            Vector3 vector_right = GameplayCamera.RightVector;
            Vector3 vector_up = Vector3.WorldUp;

            // Estimate the direction depending on the current input
            if (Game.IsKeyPressed(Keys.W)) direction += vector_forward;
            if (Game.IsKeyPressed(Keys.S)) direction -= vector_forward;
            if (Game.IsKeyPressed(Keys.D)) direction += vector_right;
            if (Game.IsKeyPressed(Keys.A)) direction -= vector_right;
            if (Game.IsKeyPressed(Keys.Space)) direction += vector_up;
            if (Game.IsKeyPressed(Keys.ShiftKey)) direction -= vector_up;

            // Return the normalized direction multiplied by the current speed level
            return direction == Vector3.Zero ? Vector3.Zero : direction.Normalized * this.speeds[this.SpeedLevel];
        }

        public void OnTick()
        {
            if (!this.Active) return;

            // Get the handle of either the character or the character's car
            bool in_vehicle = Game.Player.Character.IsInVehicle();
            int handle = in_vehicle ? Game.Player.Character.CurrentVehicle.Handle : Game.Player.Character.Handle;

            // Get the new position offset depending on the current input and calculate the new position based on the offset
            Vector3 offset = this.GetDirectionFromInput();
            Vector3 current_position = Function.Call<Vector3>(Hash.GET_ENTITY_COORDS, handle, true);
            Vector3 new_position = current_position + offset;

            // Set the new position of either the character or the character's car
            Function.Call(Hash.SET_ENTITY_COORDS_NO_OFFSET, handle, new_position.X, new_position.Y, new_position.Z, true, false, false);
            Game.Player.Character.Velocity = Vector3.Zero;

            // If First Person View is not active set the heading of the entity to match the camera's rotation
            if (GameplayCamera.FollowPedCamViewMode != GTA.CamViewMode.FirstPerson)
            {
                if (Game.IsKeyPressed(Keys.S)) Function.Call(Hash.SET_ENTITY_HEADING, handle, GameplayCamera.Rotation.Z - 180f);
                else Function.Call(Hash.SET_ENTITY_HEADING, handle, GameplayCamera.Rotation.Z);
            }
        }

        public void Toggle()
        {
            this.Active = !this.Active;
            this.ResetSpeedLevel();

            this.Refresh();
        }

        public void Refresh()
        {
            bool in_vehicle = Game.Player.Character.IsInVehicle();
            Entity entity = in_vehicle ? (Entity)Game.Player.Character.CurrentVehicle : Game.Player.Character;

            // Toggle the freezing of the position of the player and all actions
            Function.Call(Hash.FREEZE_ENTITY_POSITION, entity, this.Active ? true : false);
            Function.Call(Hash.CLEAR_PED_TASKS_IMMEDIATELY, Game.Player.Character);
            if (this.Active) Function.Call(Hash.TASK_STAND_STILL, Game.Player.Character.Handle, -1);

            // Toggle the collisions and visibility of the player
            Function.Call(Hash.SET_ENTITY_COLLISION, entity, this.Active ? false : true, this.Active ? false : true);
            Function.Call(Hash.SET_ENTITY_HAS_GRAVITY, entity, this.Active ? false : true);
            Function.Call(Hash.SET_ENTITY_ALPHA, Game.Player.Character, this.Active ? 100 : 255);
        }
    }

    public class GameState
    {
        public bool TrainerActive = false;
        private bool fpvActive = false;
        private bool freezeActive = false;

        public readonly Random RandomGenerator = new Random();

        public VisualModifier VisualModifier = new VisualModifier();
        public NoClip NoClip = new NoClip();

        public void ToggleTrainer() => this.TrainerActive = !this.TrainerActive;
        public void ToggleVisualModifier() => this.VisualModifier.Toggle();
        public void ToggleNoClip() => this.NoClip.Toggle();

        public GameState(string pathConfig)
        {
            string toml = File.ReadAllText(pathConfig);
            GlobalConfig.Config = TomlSerializer.Deserialize<Config>(toml);
            GlobalConfig.Config.Validate();
        }

        public void ToggleFpv()
        {
            this.fpvActive = !this.fpvActive;
            Game.Player.Character.IsVisible = !this.fpvActive;

            // Toggle the view between FPV and TPV
            Function.Call(Hash.SET_FOLLOW_PED_CAM_VIEW_MODE, this.fpvActive ? 4 : 2);

            // Toggle the visibility of the UI
            Function.Call(Hash.DISPLAY_HUD, !this.fpvActive);
            Function.Call(Hash.DISPLAY_RADAR, !this.fpvActive);
            Function.Call(Hash.DISPLAY_AREA_NAME, !this.fpvActive);
            Function.Call(Hash.SET_POLICE_RADAR_BLIPS, !this.fpvActive);

            // Toggle the visibility of the player
            if (Game.Player.Character.IsInVehicle()) Game.Player.Character.CurrentVehicle.IsVisible = !this.fpvActive;
            Function.Call(Hash.SET_ENTITY_ALPHA, Game.Player.Character, this.fpvActive ? 0 : 255);
        }

        public void ToggleFreeze()
        {
            this.freezeActive = !this.freezeActive;

            // Toggle the freezing of the position of all vehicles and PEDs
            foreach (Vehicle vehicle in World.GetAllVehicles()) Function.Call(Hash.FREEZE_ENTITY_POSITION, vehicle, this.freezeActive);
            foreach (Ped ped in World.GetAllPeds()) if (ped != Game.Player.Character) Function.Call(Hash.FREEZE_ENTITY_POSITION, ped, this.freezeActive);

            // Toggle the time scale across the whole game 
            Game.TimeScale = this.freezeActive ? 0f : 1f;
        }

        public void EnableFpv() { if (!this.fpvActive) this.ToggleFpv(); }
        public void DisableFpv() { if (this.fpvActive) this.ToggleFpv(); }
        public void EnableVisualModifier() { if (!this.VisualModifier.Active) this.VisualModifier.Toggle(); }
        public void DisableVisualModifier() { if (this.VisualModifier.Active) this.VisualModifier.Toggle(); }
        public void EnableFreeze() { if (!this.freezeActive) this.ToggleFreeze(); }
        public void DisableFreeze() { if (this.freezeActive) this.ToggleFreeze(); }
        public void EnableNoClip() { if (!this.NoClip.Active) this.NoClip.Toggle(); }
        public void DisableNoClip() { if (this.NoClip.Active) this.NoClip.Toggle(); }

        public void SetTime(int h, int m, int s)
        {
            Function.Call(Hash.SET_CLOCK_TIME, h, m, s);
        }

        public void SetTime()
        {
            int h, m, s;
            if (GlobalConfig.Config.Random.RandomTime)
            {
                h = this.RandomGenerator.Next(6, 18);
                m = this.RandomGenerator.Next(60);
                s = this.RandomGenerator.Next(60);
            }
            else
            {
                h = 11;
                m = 0;
                s = 0;
            }
            Function.Call(Hash.SET_CLOCK_TIME, h, m, s);
        }

        public void SetWeather(string weather)
        {
            Function.Call(Hash.SET_WEATHER_TYPE_NOW_PERSIST, weather);
        }

        public void SetWeather()
        {
            string weather = "EXTRASUNNY";
            if (GlobalConfig.Config.Random.RandomWeather)
            {
                int idx = this.RandomGenerator.Next(GlobalConfig.Config.Random.WeatherTypes.Count);
                weather = GlobalConfig.Config.Random.WeatherTypes[idx];
            }
            this.SetWeather(weather);
        }
    }


    // ----------------------------------------------------------
    // Data Generation
    // ----------------------------------------------------------

    public enum LocationSetting { Urban, Rural, Drone }

    public static class LocationSettingExtensions
    {
        public static LocationSetting Parse(string value)
        {
            switch (value)
            {
                case "urban": return LocationSetting.Urban;
                case "rural": return LocationSetting.Rural;
                case "drone": return LocationSetting.Drone;
                default: throw new ArgumentException($"Invalid setting value: '{value}'. Expected 'urban', 'rural', or 'drone'.");
            }
        }

        public static string ToFileString(this LocationSetting setting)
        {
            switch (setting)
            {
                case LocationSetting.Urban: return "urban";
                case LocationSetting.Rural: return "rural";
                case LocationSetting.Drone: return "drone";
                default: throw new ArgumentOutOfRangeException(nameof(setting));
            }
        }
    }

    public class Location
    {
        private LocationSetting setting;
        private Vector3 position;
        private Vector3 rotation;
        private float fov;
        private bool rendered;

        public Location(LocationSetting setting, float x, float y, float z, float rotX, float rotY, float rotZ, float fov, bool rendered)
        {
            this.Setting = setting;
            this.Position = new Vector3(x, y, z);
            this.Rotation = new Vector3(rotX, rotY, rotZ);
            this.Fov = fov;
            this.Rendered = rendered;
        }

        public LocationSetting Setting
        {
            get => this.setting;
            set => this.setting = value;
        }
        public Vector3 Position
        {
            get => this.position;
            set
            {
                if (value.X < GlobalConfig.Config.Map.MapDimensions[0] || value.X > GlobalConfig.Config.Map.MapDimensions[1]) throw new ArgumentException("The 'x' field in the render targets file is invalid.");
                if (value.Y < GlobalConfig.Config.Map.MapDimensions[2] || value.Y > GlobalConfig.Config.Map.MapDimensions[3]) throw new ArgumentException("The 'y' field in the render targets file is invalid.");
                if (value.Z < GlobalConfig.Config.Map.MapDimensions[4] || value.Z > GlobalConfig.Config.Map.MapDimensions[5]) throw new ArgumentException("The 'z' field in the render targets file is invalid.");
                this.position = value;
            }
        }
        public Vector3 Rotation
        {
            get => this.rotation;
            set
            {
                if (value.X < -360f || value.X > 360f) throw new ArgumentException("The 'rot_x' field in the render targets file is invalid.");
                if (value.Y < -360f || value.Y > 360f) throw new ArgumentException("The 'rot_y' field in the render targets file is invalid.");
                if (value.Z < -360f || value.Z > 360f) throw new ArgumentException("The 'rot_z' field in the render targets file is invalid.");
                this.rotation = value;
            }
        }
        public float Fov
        {
            get => this.fov;
            set
            {
                if (value < 0f || value > 180f) throw new ArgumentException("The 'fov' field in the render targets file is invalid.");
                this.fov = value;
            }
        }
        public bool Rendered
        {
            get => this.rendered;
            set => this.rendered = value;
        }
    }

    public class RenderTargets
    {
        private int index = -1;
        private int counter = 0;
        private readonly string filePath;
        public List<Location> Locations;

        public RenderTargets(string filePath)
        {
            this.filePath = filePath;
            this.Locations = new List<Location>();
            this.LoadLocationsFromFile();
        }

        private void LoadLocationsFromFile()
        {
            if (!File.Exists(this.filePath)) throw new FileNotFoundException("Render targets file not found.", this.filePath);

            using (StreamReader reader = new StreamReader(this.filePath, new UTF8Encoding(false)))
            {
                string line;
                bool isFirstLine = true;
                while ((line = reader.ReadLine()) != null)
                {
                    // Skip the first line and any empty lines
                    if (isFirstLine)
                    {
                        isFirstLine = false;
                        continue;
                    }
                    if (string.IsNullOrWhiteSpace(line)) continue;

                    // Read the contents of the line and skip any lines with missing information
                    string[] values = line.Split(';');
                    if (values.Length != 9) continue;

                    // Parse the setting
                    LocationSetting setting;
                    try
                    {
                        setting = LocationSettingExtensions.Parse(values[0]);
                    }
                    catch (ArgumentException)
                    {
                        continue;
                    }

                    // Parse the values and skip any lines containing unparsable values
                    CultureInfo cultureInfo = CultureInfo.InvariantCulture;
                    if (!float.TryParse(values[1], NumberStyles.Float, cultureInfo, out float x) ||
                        !float.TryParse(values[2], NumberStyles.Float, cultureInfo, out float y) ||
                        !float.TryParse(values[3], NumberStyles.Float, cultureInfo, out float z) ||
                        !float.TryParse(values[4], NumberStyles.Float, cultureInfo, out float rotX) ||
                        !float.TryParse(values[5], NumberStyles.Float, cultureInfo, out float rotY) ||
                        !float.TryParse(values[6], NumberStyles.Float, cultureInfo, out float rotZ) ||
                        !float.TryParse(values[7], NumberStyles.Float, cultureInfo, out float fov) ||
                        !bool.TryParse(values[8], out bool rendered))
                    {
                        continue;
                    }

                    // Add the location to the list
                    Location location = new Location(setting, x, y, z, rotX, rotY, rotZ, fov, rendered);
                    this.Locations.Add(location);
                }
            }
        }

        public void WriteLocationsToFile()
        {
            var lines = new List<string>
            {
                "setting;x;y;z;rot_x;rot_y;rot_z;fov;rendered"
            };

            foreach (var location in this.Locations)
            {
                lines.Add(string.Join(";",
                    location.Setting.ToFileString(),
                    location.Position.X.ToString(CultureInfo.InvariantCulture),
                    location.Position.Y.ToString(CultureInfo.InvariantCulture),
                    location.Position.Z.ToString(CultureInfo.InvariantCulture),
                    location.Rotation.X.ToString(CultureInfo.InvariantCulture),
                    location.Rotation.Y.ToString(CultureInfo.InvariantCulture),
                    location.Rotation.Z.ToString(CultureInfo.InvariantCulture),
                    location.Fov.ToString(CultureInfo.InvariantCulture),
                    location.Rendered.ToString()
                ));
            }

            File.WriteAllLines(this.filePath, lines, new UTF8Encoding(false));
        }

        public int GetNextLocation(LocationSetting[] settings)
        {
            for (int i = 0; i < this.Locations.Count; i++)
            {
                int idx = (i + this.index + 1) % this.Locations.Count;
                if (!this.Locations[idx].Rendered && settings.Any(setting => this.Locations[idx].Setting == setting))
                {
                    this.index = idx;
                    return idx;
                }
            }
            return -1;
        }

        public int GetNextLocation(DataGenerator.GroundViewOption groundView)
        {
            if (groundView == DataGenerator.GroundViewOption.Drone) return this.GetNextLocation(new[] { LocationSetting.Drone });
            else return this.GetNextLocation(new[] { LocationSetting.Urban, LocationSetting.Rural });
        }

        public void SaveCheckpoint(MetadataLogger metadataLogger, bool force)
        {
            this.counter++;
            if (this.counter >= GlobalConfig.Config.Generation.Checkpoint || force)
            {
                this.counter = 0;
                this.WriteLocationsToFile();
                metadataLogger.SortMetadata();
            }
        }
    }

    public static class DataGenerator
    {
        public enum LocationOption { Current, MapBased, Random }
        public enum GroundViewOption { SingleView, Panorama, Drone, None }
        public enum AerialViewOption { Corresponding, Overlapping, None }

        private static string WaitForCompleteCapture(string directory, string baseName, int stableChecks = 5, int intervalMs = 200, int timeoutMs = 30000)
        {
            DateTime start = DateTime.Now;
            string file = null;

            // Wait until file appears
            while (file == null)
            {
                // Check for timeout
                if ((DateTime.Now - start).TotalMilliseconds > timeoutMs) throw new TimeoutException($"Timed out waiting for capture file matching '{baseName}_frame*.rdc' in '{directory}'.");

                // Check if the file has been created
                if (Directory.Exists(directory))
                {
                    string[] matches = Directory.GetFiles(directory, $"{baseName}_frame*.rdc");
                    if (matches.Length == 1)
                    {
                        file = matches[0];
                    }
                    else if (matches.Length > 1)
                    {
                        throw new InvalidOperationException($"Found {matches.Length} files matching '{baseName}_frame*.rdc' in '{directory}', expected exactly 1. Check for stale .rdc files from a previous run.");
                    }
                }

                if (file == null) Script.Wait(intervalMs);
            }

            long previousSize = -1;
            int stableCount = 0;

            // Wait until size stabilizes
            while (stableCount < stableChecks)
            {
                // Check for timeout
                if ((DateTime.Now - start).TotalMilliseconds > timeoutMs) throw new TimeoutException();

                // Check if the size has changed
                long size = new FileInfo(file).Length;
                if (size == previousSize) stableCount++;
                else
                {
                    stableCount = 0;
                    previousSize = size;
                }
                Script.Wait(intervalMs);
            }

            return file;
        }

        private static void WaitForFile(string filePath, int intervalMs = 200, int timeoutMs = 30000)
        {
            DateTime start = DateTime.Now;

            while (!File.Exists(filePath))
            {
                if ((DateTime.Now - start).TotalMilliseconds > timeoutMs) throw new TimeoutException();
                else Script.Wait(intervalMs);
            }
        }

        private static void RenderSingleView(RenderDoc renderDoc, MetadataLogger metadataLogger, string dataPath, string fileName, Vector3? cameraPosition, Vector3? cameraRotation, float? fov, bool waitForDepth = true, bool waitForStencil = true)
        {
            // Create the directory for the data if it doesn't exist yet
            Directory.CreateDirectory(dataPath);

            // Get the current camera position, rotation, and FOV if not given as parameter
            if (cameraPosition == null) cameraPosition = GameData.GetCameraPosition(null);
            if (cameraRotation == null) cameraRotation = GameData.GetCameraRotation(null);
            if (fov == null) fov = GameData.GetCameraFOV(null);

            // Create a new camera
            Camera camera = GameData.CreateCamera(cameraPosition.Value, cameraRotation.Value, fov.Value);

            // Wait for the meshes to load completely before capturing
            Script.Wait(GlobalConfig.Config.Generation.WaitAfterChange);

            try
            {
                // Trigger the frame capture using RenderDoc
                string path = Path.Combine(dataPath, fileName);
                string pathTmp = path + "_tmp";
                renderDoc.API.SetCaptureFilePathTemplate(pathTmp);
                renderDoc.API.TriggerCapture();

                // Wait for the file to be saved, then rename it
                string directory = Path.GetDirectoryName(pathTmp);
                string baseName = Path.GetFileName(pathTmp);
                string rdcFileTmp = WaitForCompleteCapture(directory, baseName);
                string rdcFile = path + ".rdc";
                File.Move(rdcFileTmp, rdcFile);

                // Wait for the capturing and post-processing
                if (GlobalConfig.Config.Generation.GenerateRGB)
                {
                    string filePathRGB = Path.Combine(dataPath, string.Format("{0}{1}", fileName, GlobalConfig.Config.Generation.WaitForFileRGB));
                    WaitForFile(filePathRGB);
                }
                if (GlobalConfig.Config.Generation.GenerateDepth && waitForDepth)
                {
                    string filePathDepth = Path.Combine(dataPath, string.Format("{0}{1}", fileName, GlobalConfig.Config.Generation.WaitForFileDepth));
                    WaitForFile(filePathDepth);
                }
                if (GlobalConfig.Config.Generation.GenerateStencil && waitForStencil)
                {
                    string filePathStencil = Path.Combine(dataPath, string.Format("{0}{1}", fileName, GlobalConfig.Config.Generation.WaitForFileStencil));
                    WaitForFile(filePathStencil);
                }

                // Log the metadata
                string dataPathRelative = new DirectoryInfo(dataPath).Name;
                metadataLogger.LogMetadata(Path.Combine(dataPathRelative, fileName), camera);
            }
            finally
            {
                // Delete the camera
                GameData.DeleteCamera(camera);
            }
        }

        private static void RenderPanoramaViews(RenderDoc renderDoc, MetadataLogger metadataLogger, string dataPath, string fileName, Vector3? cameraPositionOrNull)
        {
            // Get the current camera position if not given as parameter
            if (cameraPositionOrNull == null) cameraPositionOrNull = GameData.GetCameraPosition(null);
            Vector3 cameraPosition = (Vector3)cameraPositionOrNull;

            // The first 6 views (N, S, E, W, U, D) carry RGB, depth, and stencil. The remaining 12 views only add
            // RGB for the panorama and are therefore only rendered if RGB is generated
            int numberOfViews = GlobalConfig.Config.Generation.GenerateRGB ? 18 : 6;

            // Iterate over the views, set the headings and camera rotations, and render the views
            for (int i = 0; i < numberOfViews; i++)
            {
                string heading = GlobalConfig.Config.Panorama.PanoramaHeadings[i];
                Rotation rot = GlobalConfig.Config.PanoramaRotations[i];
                Vector3 cameraRotation = new Vector3(rot.X, rot.Y, rot.Z);
                bool waitForDepthStencil = i < 6;
                RenderSingleView(renderDoc, metadataLogger, dataPath, fileName + heading, cameraPosition, cameraRotation, 90f, waitForDepthStencil, waitForDepthStencil);
            }
        }

        private static void RenderDroneViews(RenderDoc renderDoc, MetadataLogger metadataLogger, string dataPath, string fileName, Vector3? buildingPositionOrNull)
        {
            // Get the current camera position if not given as parameter
            if (buildingPositionOrNull == null) buildingPositionOrNull = GameData.GetCameraPosition(null);
            Vector3 buildingPosition = (Vector3)buildingPositionOrNull;

            // Iterate over all 64 views, set the headings, camera positions, and camera rotations, and render the views
            for (int i = 0; i < 64; i++)
            {
                // Set the distance to the building position
                float distance = 50f;
                if (i >= 32) distance = 75f;

                // Calculate the camera position
                float angle = (2 * (float)Math.PI / 32f) * ((float)(i % 32));
                float posX = buildingPosition.X + (float)(-Math.Sin(angle) * distance);
                float posY = buildingPosition.Y + (float)(-Math.Cos(angle) * distance);
                float posZ = buildingPosition.Z + distance;
                Vector3 cameraPosition = new Vector3(posX, posY, posZ);

                // Calculate the camera rotation
                Vector3 direction = Vector3.Normalize(buildingPosition - cameraPosition);
                float pitch = (float)(Math.Asin(direction.Z) * (180d / Math.PI));
                float roll = 0f;
                float yaw = (float)(Math.Atan2(direction.X, direction.Y) * (-180d / Math.PI));
                Vector3 cameraRotation = new Vector3(pitch, roll, yaw);

                // Set the heading tag
                string heading = string.Format("_{0:D2}_{1:D2}", (int)distance, i);

                // Render the view
                RenderSingleView(renderDoc, metadataLogger, dataPath, fileName + heading, cameraPosition, cameraRotation, GlobalConfig.Config.Camera.GroundDroneFOV);
            }
        }

        private static void RenderAerialViews(RenderDoc renderDoc, MetadataLogger metadataLogger, string dataPath, string fileName, Vector3? cameraPositionOrNull, IEnumerable<int> indices = null)
        {
            // Get the current camera position if not given as parameter
            if (cameraPositionOrNull == null) cameraPositionOrNull = GameData.GetCameraPosition(null);
            Vector3 cameraPosition = (Vector3)cameraPositionOrNull;

            // Render all 5 aerial-views (1 nadir and 4 oblique) unless a specific subset of indices is given
            if (indices == null) indices = Enumerable.Range(0, 5);

            // Iterate over the aerial-views, set the headings and camera rotations, and render the views
            foreach (int i in indices)
            {
                string heading = string.Format("_{0:D2}", i);
                Rotation rot = GlobalConfig.Config.AerialViewRotations[i];
                Vector3 cameraRotation = new Vector3(rot.X, rot.Y, rot.Z);
                RenderSingleView(renderDoc, metadataLogger, dataPath, fileName + heading, cameraPosition, cameraRotation, GlobalConfig.Config.Camera.AerialFOV);
            }
        }

        private class AreaBounds
        {
            public float MinX, MaxX, MinY, MaxY, MinZ, MaxZ;

            public AreaBounds()
            {
                this.MinX = GlobalConfig.Config.Map.MapDimensions[1];
                this.MaxX = GlobalConfig.Config.Map.MapDimensions[0];
                this.MinY = GlobalConfig.Config.Map.MapDimensions[3];
                this.MaxY = GlobalConfig.Config.Map.MapDimensions[2];
                this.MinZ = GlobalConfig.Config.Map.MapDimensions[5];
                this.MaxZ = GlobalConfig.Config.Map.MapDimensions[4];
            }

            public void Update(Vector3 pos)
            {
                this.MinX = Math.Min(MinX, pos.X);
                this.MaxX = Math.Max(MaxX, pos.X);
                this.MinY = Math.Min(MinY, pos.Y);
                this.MaxY = Math.Max(MaxY, pos.Y);
                this.MinZ = Math.Min(MinZ, pos.Z);
                this.MaxZ = Math.Max(MaxZ, pos.Z);
            }
        }

        private static void GenerateOverlappingAerialViews(RenderDoc renderDoc, MetadataLogger metadataLogger, RenderTargets renderTargets, string dataPath, GameState gameState)
        {
            // Create the directory for the data if it doesn't exist yet
            Directory.CreateDirectory(dataPath);

            // Get the area bounds for each setting
            Dictionary<LocationSetting, AreaBounds> areaBoundsBySetting = new Dictionary<LocationSetting, AreaBounds>()
            {
                [LocationSetting.Urban] = new AreaBounds(),
                [LocationSetting.Rural] = new AreaBounds(),
                [LocationSetting.Drone] = new AreaBounds()
            };
            foreach (var location in renderTargets.Locations)
            {
                if (!location.Rendered) continue;
                if (!areaBoundsBySetting.TryGetValue(location.Setting, out var areaBounds)) continue;
                areaBounds.Update(location.Position);
                areaBoundsBySetting[location.Setting] = areaBounds;
            }

            // Calculate the area and altitude
            int[] resolution = GameData.GetResolution();
            float area = (float)Math.Min(resolution[0], resolution[1]) * GlobalConfig.Config.Camera.GSD;
            float altitudeBase = area / (2f * (float)Math.Tan((double)GlobalConfig.Config.Camera.AerialFOV * Math.PI / 360d));
            float step = area * (1f - GlobalConfig.Config.Generation.Overlap);

            // Iterate over all settings
            foreach (KeyValuePair<LocationSetting, AreaBounds> settingAndAreaBounds in areaBoundsBySetting)
            {
                LocationSetting setting = settingAndAreaBounds.Key;
                AreaBounds areaBounds = settingAndAreaBounds.Value;

                // Skip the settings with no locations
                if (areaBounds.MinX == GlobalConfig.Config.Map.MapDimensions[0]) continue;

                // Calculate the altitude and center of the area
                float altitudeArea = altitudeBase + areaBounds.MinZ;
                Vector2 center = new Vector2((areaBounds.MinX + areaBounds.MaxX) * 0.5f, (areaBounds.MinY + areaBounds.MaxY) * 0.5f);

                // Calculate the starting point for the survey flight
                float startX = center.X;
                while (startX > (areaBounds.MinX - area)) startX -= GlobalConfig.Config.Generation.Padding * step;
                float startY = center.Y;
                while (startY > (areaBounds.MinY - area)) startY -= GlobalConfig.Config.Generation.Padding * step;

                // Enable No-Clip and FPV
                gameState.EnableNoClip();
                gameState.EnableFpv();

                Vector3 groundPosition = new Vector3(startX, startY, 0f);

                try
                {
                    // Render all overlapping aerial-view images
                    for (float x = startX; x < areaBounds.MaxX + GlobalConfig.Config.Generation.Padding * area; x += step)
                    {
                        for (float y = startY; y < areaBounds.MaxY + area; y += step)
                        {
                            string fileName = String.Format("{0}_{1}_{2}", setting.ToFileString(), (int)x, (int)y);

                            // Determine which of the 5 aerial-views (1 nadir and 4 oblique) still need to be generated
                            List<int> missingIndices = new List<int>();
                            for (int i = 0; i < 5; i++)
                            {
                                bool generated = true;
                                string filePathId = Path.Combine(dataPath, String.Format("{0}_{1:D2}", fileName, i));
                                if (GlobalConfig.Config.Generation.GenerateRGB && !File.Exists(filePathId + GlobalConfig.Config.Generation.WaitForFileRGB)) generated = false;
                                if (GlobalConfig.Config.Generation.GenerateDepth && !File.Exists(filePathId + GlobalConfig.Config.Generation.WaitForFileDepth)) generated = false;
                                if (GlobalConfig.Config.Generation.GenerateStencil && !File.Exists(filePathId + GlobalConfig.Config.Generation.WaitForFileStencil)) generated = false;
                                if (!generated) missingIndices.Add(i);
                            }
                            if (missingIndices.Count == 0) continue;

                            // Change the position of the player
                            groundPosition = new Vector3(x, y, 0f);
                            Vector3 cameraPosition = new Vector3(x, y, altitudeArea);

                            // Set the time and weather
                            gameState.SetTime(11, 0, 0);
                            gameState.SetWeather("EXTRASUNNY");
                            Script.Wait(GlobalConfig.Config.Generation.WaitAfterChange);

                            // Move the player to the camera position so that meshes further away are loaded
                            GameData.TeleportPlayer(cameraPosition, null, gameState);

                            // Enable scene freeze and visual modifier
                            gameState.EnableVisualModifier();
                            gameState.EnableFreeze();

                            try
                            {
                                // Render the missing aerial-views (1 nadir and 4 oblique)
                                RenderAerialViews(renderDoc, metadataLogger, dataPath, fileName, cameraPosition, missingIndices);
                            }
                            finally
                            {
                                // Disable scene freeze and visual modifier
                                gameState.DisableFreeze();
                                gameState.DisableVisualModifier();
                            }
                        }
                    }
                }
                finally
                {
                    // Move the player back to the ground
                    GameData.TeleportPlayer(groundPosition, null, gameState);

                    // Disable No-Clip and FPV
                    gameState.DisableNoClip();
                    gameState.DisableFpv();
                }
            }
        }

        public static void GenerateData(LocationOption location, GroundViewOption groundView, AerialViewOption aerialView, GameState gameState)
        {
            // Don't start the data generation if the trainer is opened
            if (gameState.TrainerActive) return;

            // Initialize RenderDoc and MetdataLogger
            RenderDoc renderDoc = new RenderDoc(GlobalConfig.Config.Paths.Data);
            MetadataLogger metadataLogger = new MetadataLogger(GlobalConfig.Config.Paths.Data);

            // Only initialize the RenderTargets if map-based locations are used
            RenderTargets renderTargets = null;
            if (location == LocationOption.MapBased) renderTargets = new RenderTargets(Path.Combine(GlobalConfig.Config.Paths.Data, "render_targets.csv"));

            // If overlapping aerial-view images are to be generated, skip the rest of the data generation steps
            if (aerialView == AerialViewOption.Overlapping)
            {
                GenerateOverlappingAerialViews(renderDoc, metadataLogger, renderTargets, GlobalConfig.Config.Paths.DataAerialViewArea, gameState);
                return;
            }

            // Set the data paths for the ground-view images
            string dataPathGroundView = GlobalConfig.Config.Paths.DataGroundView;
            if (groundView == GroundViewOption.Panorama) dataPathGroundView = GlobalConfig.Config.Paths.DataGroundViewPano;
            else if (groundView == GroundViewOption.Drone) dataPathGroundView = GlobalConfig.Config.Paths.DataDroneView;

            // Get the index of the first location
            int i = 0;
            if (location == LocationOption.MapBased && groundView != GroundViewOption.None) i = renderTargets.GetNextLocation(groundView);
            else if (location == LocationOption.Random && groundView != GroundViewOption.None) i = GlobalConfig.Config.Random.NumberOfRandomLocations - 1;

            // Enable No-Clip and FPV
            gameState.EnableNoClip();
            gameState.EnableFpv();

            try
            {
                // Iterate over all locations that have not been rendered yet
                while (i >= 0)
                {
                    // Set the file name
                    string fileName = DateTime.Now.ToString("yyyyMMdd-HHmmss");
                    if (location == LocationOption.MapBased) fileName = string.Format("{0}_{1:D7}", renderTargets.Locations[i].Setting.ToFileString(), i);

                    if (groundView != GroundViewOption.None)
                    {
                        // Set the time and weather
                        gameState.SetTime();
                        gameState.SetWeather();
                        Script.Wait(GlobalConfig.Config.Generation.WaitAfterChange);

                        // Change the position of the player
                        Vector3 randomRotation = new Vector3(0f, 0f, 0f);
                        if (location == LocationOption.MapBased) GameData.TeleportPlayer(renderTargets.Locations[i].Position, renderTargets.Locations[i], gameState);
                        else if (location == LocationOption.Random) randomRotation = GameData.TeleportPlayerRandom(gameState);

                        // Enable scene freeze
                        gameState.EnableFreeze();

                        try
                        {
                            // Render all views
                            if (groundView == GroundViewOption.Panorama)
                                RenderPanoramaViews(renderDoc, metadataLogger, dataPathGroundView, fileName, null);
                            else if (groundView == GroundViewOption.Drone)
                                RenderDroneViews(renderDoc, metadataLogger, dataPathGroundView, fileName, null);
                            else if (groundView == GroundViewOption.SingleView && location == LocationOption.MapBased)
                                RenderSingleView(renderDoc, metadataLogger, dataPathGroundView, fileName, null, renderTargets.Locations[i].Rotation, renderTargets.Locations[i].Fov);
                            else if (groundView == GroundViewOption.SingleView && location == LocationOption.Random)
                                RenderSingleView(renderDoc, metadataLogger, dataPathGroundView, fileName, null, randomRotation, null);
                            else
                                RenderSingleView(renderDoc, metadataLogger, dataPathGroundView, fileName, null, null, null);
                        }
                        finally
                        {
                            // Disable scene freeze
                            gameState.DisableFreeze();
                        }
                    }

                    if (aerialView == AerialViewOption.Corresponding)
                    {
                        // Set the time and weather
                        gameState.SetTime(11, 0, 0);
                        gameState.SetWeather("EXTRASUNNY");
                        Script.Wait(GlobalConfig.Config.Generation.WaitAfterChange);

                        // Calculate the altitude for the aerial-view camera and set the rotation to the nadir view
                        Vector3 groundPosition = Game.Player.Character.Position;
                        Vector3 cameraPosition = GameData.GetCameraPosition(null);
                        cameraPosition.Z += GameData.GetAerialViewCameraAltitude(null, GlobalConfig.Config.Camera.AerialFOV);
                        Rotation rot = GlobalConfig.Config.AerialViewRotations[0];
                        Vector3 cameraRotation = new Vector3(rot.X, rot.Y, rot.Z);

                        // Move the player to the camera position so that meshes further away are loaded
                        GameData.TeleportPlayer(cameraPosition, null, gameState);

                        // Enable scene freeze and visual modifier
                        gameState.EnableVisualModifier();
                        gameState.EnableFreeze();

                        try
                        {
                            // Render the aerial-view
                            RenderSingleView(renderDoc, metadataLogger, GlobalConfig.Config.Paths.DataAerialView, fileName, cameraPosition, cameraRotation, GlobalConfig.Config.Camera.AerialFOV);
                        }
                        finally
                        {
                            // Disable scene freeze and visual modifier
                            gameState.DisableFreeze();
                            gameState.DisableVisualModifier();

                            // Move the player back to the ground
                            GameData.TeleportPlayer(groundPosition, null, gameState);
                        }
                    }

                    // Mark the location as rendered, save the locations to the file, and sort the metadata
                    if (location == LocationOption.MapBased && groundView != GroundViewOption.None)
                    {
                        renderTargets.Locations[i].Rendered = true;
                        renderTargets.SaveCheckpoint(metadataLogger, false);
                    }

                    // Get the index of the first location
                    if (location == LocationOption.MapBased && groundView != GroundViewOption.None) i = renderTargets.GetNextLocation(groundView);
                    else i--;
                }
            }
            finally
            {
                // Disable No-Clip and FPV
                gameState.DisableNoClip();
                gameState.DisableFpv();
            }
            
            // Save the render targets to the file and sort the metadata
            if (location == LocationOption.MapBased && groundView != GroundViewOption.None) renderTargets.SaveCheckpoint(metadataLogger, true);
        }
    }


    // ----------------------------------------------------------
    // Main Script
    // ----------------------------------------------------------

    public class GameInterface : Script
    {
        private readonly GameState gameState;

        public GameInterface()
        {
            this.gameState = new GameState("config.toml");

            Tick += OnTick;
            KeyDown += OnKeyDown;
        }

        private void OnTick(object sender, EventArgs e)
        {
            this.gameState.VisualModifier.OnTick();
            this.gameState.NoClip.OnTick();

            // Disable all phone interactions
            Function.Call(Hash.TERMINATE_ALL_SCRIPTS_WITH_THIS_NAME, "cellphone_controller");

            // Disable controls like looking backwards, attack moves, the weapon wheel, and character changes
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
            Game.Player.Character.Weapons.Select(WeaponHash.Unarmed);

            // Make the player invincible and disable police
            Function.Call(Hash.SET_PLAYER_INVINCIBLE, Game.Player, true);
            Function.Call(Hash.SET_POLICE_IGNORE_PLAYER, Game.Player, true);
            Function.Call(Hash.SET_EVERYONE_IGNORE_PLAYER, Game.Player, true);
            Function.Call(Hash.SET_MAX_WANTED_LEVEL, 0);
            Function.Call(Hash.CLEAR_PLAYER_WANTED_LEVEL, Game.Player);
        }

        private void OnKeyDown(object sender, KeyEventArgs e)
        {
            // PageUp: Increase the movement speed in NoClip mode
            if (e.KeyCode == Keys.PageUp) this.gameState.NoClip.IncreaseSpeedLevel();

            // PageDown: Decrease the movement speed in NoClip mode
            if (e.KeyCode == Keys.PageDown) this.gameState.NoClip.DecreaseSpeedLevel();

            // F4: Toggle the trainer
            if (e.KeyCode == Keys.F4) this.gameState.ToggleTrainer();

            // F5: Open the console
            // Reserved for ScriptHookVDotNet console

            // F6: Toggle the view
            if (e.KeyCode == Keys.F6) this.gameState.ToggleFpv();

            // F7: Toggle the visual modifier
            if (e.KeyCode == Keys.F7) this.gameState.ToggleVisualModifier();

            // F8: Toggle the scene freeze
            if (e.KeyCode == Keys.F8) this.gameState.ToggleFreeze();

            // F9: Toggle the No-Clip mode
            if (e.KeyCode == Keys.F9) this.gameState.ToggleNoClip();

            // F10: Destroy all cameras
            if (e.KeyCode == Keys.F10)
            {
                Function.Call(Hash.DESTROY_ALL_CAMS, true);
                Function.Call(Hash.RENDER_SCRIPT_CAMS, false, false, 0, true, false);
            }

            // F12: Trigger the RenderDoc frame capture
            // Reserved for RenderDoc

            // NumPad1: Data Generation: current location - ground-view panorama and corresponding aerial-view image
            if (e.KeyCode == Keys.NumPad1) DataGenerator.GenerateData(DataGenerator.LocationOption.Current, DataGenerator.GroundViewOption.Panorama, DataGenerator.AerialViewOption.Corresponding, this.gameState);

            // NumPad2: Data Generation: map-based locations - ground-view panoramas and corresponding aerial-view images
            if (e.KeyCode == Keys.NumPad2) DataGenerator.GenerateData(DataGenerator.LocationOption.MapBased, DataGenerator.GroundViewOption.Panorama, DataGenerator.AerialViewOption.Corresponding, this.gameState);

            // NumPad3: Data Generation: random locations - ground-view panoramas and corresponding aerial-view images
            if (e.KeyCode == Keys.NumPad3) DataGenerator.GenerateData(DataGenerator.LocationOption.Random, DataGenerator.GroundViewOption.Panorama, DataGenerator.AerialViewOption.Corresponding, this.gameState);

            // NumPad4: Data Generation: current location - drone-view images and corresponding aerial-view image
            if (e.KeyCode == Keys.NumPad4) DataGenerator.GenerateData(DataGenerator.LocationOption.Current, DataGenerator.GroundViewOption.Drone, DataGenerator.AerialViewOption.Corresponding, this.gameState);

            // NumPad5: Data Generation: map-based locations - drone-view images and corresponding aerial-view images
            if (e.KeyCode == Keys.NumPad5) DataGenerator.GenerateData(DataGenerator.LocationOption.MapBased, DataGenerator.GroundViewOption.Drone, DataGenerator.AerialViewOption.Corresponding, this.gameState);

            // NumPad6: Data Generation: map-based locations - overlapping aerial-view images
            if (e.KeyCode == Keys.NumPad6) DataGenerator.GenerateData(DataGenerator.LocationOption.MapBased, DataGenerator.GroundViewOption.None, DataGenerator.AerialViewOption.Overlapping, this.gameState);

            // NumPad7: Data Generation: current location - ground-view image and corresponding aerial-view image
            if (e.KeyCode == Keys.NumPad7) DataGenerator.GenerateData(DataGenerator.LocationOption.Current, DataGenerator.GroundViewOption.SingleView, DataGenerator.AerialViewOption.Corresponding, this.gameState);

            // NumPad8: Data Generation: map-based locations - ground-view images and corresponding aerial-view images
            if (e.KeyCode == Keys.NumPad8) DataGenerator.GenerateData(DataGenerator.LocationOption.MapBased, DataGenerator.GroundViewOption.SingleView, DataGenerator.AerialViewOption.Corresponding, this.gameState);

            // NumPad9: Data Generation: random locations - ground-view images and corresponding aerial-view images
            if (e.KeyCode == Keys.NumPad9) DataGenerator.GenerateData(DataGenerator.LocationOption.Random, DataGenerator.GroundViewOption.SingleView, DataGenerator.AerialViewOption.Corresponding, this.gameState);
        }
    }

}