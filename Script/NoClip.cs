using GTA;
using GTA.Native;
using GTA.Math;
using System;
using System.Windows.Forms;

public class NoClip : Script
{
    private static NoClip instance;
    private bool no_clip = false;
    private readonly float[] speeds = { 0.25f, 0.5f, 1.0f, 2.0f, 4.0f, 8.0f, 16.0f };
	private int speed_level = 2;

	public NoClip()
	{
        instance = this;
        KeyDown += OnKeyDown;
        Tick += OnTick;
    }

    public static NoClip Instance => instance;

    private void OnKeyDown(object sender, KeyEventArgs e)
    {
        // F8: Toggle the No-Clip mode
        if (e.KeyCode == Keys.F8) ToggleNoClip();

        // PageUp: Increase the speed
        if (e.KeyCode == Keys.PageUp) ChangeSpeed(true);

        // PageDown: Decrease the speed
        if (e.KeyCode == Keys.PageDown) ChangeSpeed(false);
    }

    private void OnTick(object sender, EventArgs e)
    {
        // Check if NoClip is active
        if (!this.no_clip) return;

        // Get the handle of either the character or the character's car
        bool in_vehicle = Game.Player.Character.IsInVehicle();
        int handle = in_vehicle ? Game.Player.Character.CurrentVehicle.Handle : Game.Player.Character.Handle;

        // Set the heading of the player to align with the camera
        Function.Call(Hash.SET_ENTITY_HEADING, handle, GameplayCamera.Rotation.Z);
        GameplayCamera.RelativeHeading = 0f;
        Function.Call(Hash.SET_GAMEPLAY_CAM_RELATIVE_PITCH, GameplayCamera.RelativePitch, 0f);

        // Get the new position offset depending on the current input
        Vector3 offset = GetDirectionFromInput();

        // Set the new position of either the character or the character's car
        Vector3 new_position = Function.Call<Vector3>(Hash.GET_OFFSET_FROM_ENTITY_IN_WORLD_COORDS, handle, offset.X, offset.Y, offset.Z);
        Function.Call(Hash.SET_ENTITY_COORDS_NO_OFFSET, handle, new_position.X, new_position.Y, new_position.Z, true, false, false);
        Game.Player.Character.Velocity = Vector3.Zero;
    }

    public void ToggleNoClip()
    {
        // Toggle the attribute
        this.no_clip = !this.no_clip;

        // Get the entity of either the character or the character's car
        bool in_vehicle = Game.Player.Character.IsInVehicle();
        Entity entity = in_vehicle ? (Entity)Game.Player.Character.CurrentVehicle : Game.Player.Character;

        if (this.no_clip)
        {
            // Reset the speed level
            this.speed_level = 2;

            // Freeze the entity's position
            Function.Call(Hash.FREEZE_ENTITY_POSITION, entity, true);

            // Deactivate clipping
            Function.Call(Hash.SET_ENTITY_COLLISION, entity, false, false);
            Function.Call(Hash.SET_ENTITY_ALPHA, Game.Player.Character, 100);

            // Stop all animations
            Function.Call(Hash.CLEAR_PED_TASKS_IMMEDIATELY, Game.Player.Character);
            Game.Player.Character.Task.ClearAll();
        }
        else
        {
            // Reset the speed level
            this.speed_level = 2;

            // Unfreeze the entity's position
            Function.Call(Hash.FREEZE_ENTITY_POSITION, entity, false);

            // Activate clipping
            Function.Call(Hash.SET_ENTITY_COLLISION, entity, true, true);
            Function.Call(Hash.SET_ENTITY_ALPHA, Game.Player.Character, 255);

            // Stop all animations
            Function.Call(Hash.CLEAR_PED_TASKS_IMMEDIATELY, Game.Player.Character);
            Game.Player.Character.Task.ClearAll();
        }
    }

    private Vector3 GetDirectionFromInput()
    {
        // Define vectors for each direction
        Vector3 direction = Vector3.Zero;
        Vector3 vector_right = new Vector3(1, 0, 0);
        Vector3 vector_forward = new Vector3(0, 1, 0);
        Vector3 vector_up = new Vector3(0, 0, 1);

        // Estimate the direction depending on the current input
        if (Game.IsKeyPressed(Keys.W)) direction += vector_forward;
        if (Game.IsKeyPressed(Keys.S)) direction -= vector_forward;
        if (Game.IsKeyPressed(Keys.D)) direction += vector_right;
        if (Game.IsKeyPressed(Keys.A)) direction -= vector_right;
        if (Game.IsKeyPressed(Keys.Space)) direction += vector_up;
        if (Game.IsKeyPressed(Keys.ShiftKey)) direction -= vector_up;

        // Return the normalized direction multiplied by the current speed level
        return direction == Vector3.Zero ? Vector3.Zero : direction.Normalized * this.speeds[this.speed_level];
    }

    private void ChangeSpeed(bool increase)
    {
        // Increase or decrease the speed level by 1
        if (increase && this.speed_level + 1 < this.speeds.Length) this.speed_level++;
        else if (!increase && this.speed_level - 1 >= 0) this.speed_level--;
    }
}
