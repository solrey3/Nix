{ config, lib, ... }:

{
  # Keep these bindings alongside the declarative Hyprland configuration so
  # Home Manager regenerates them on every activation.
  wayland.windowManager.hyprland.settings.bind =
    lib.mkIf config.wayland.windowManager.hyprland.enable (lib.mkAfter [
      {
        _args = [
          "SUPER + mouse:272"
          (lib.generators.mkLuaInline "hl.dsp.window.drag()")
          { mouse = true; }
        ];
      }
      {
        _args = [
          "SUPER + mouse:273"
          (lib.generators.mkLuaInline "hl.dsp.window.resize()")
          { mouse = true; }
        ];
      }
    ]);
}
