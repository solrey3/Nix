{ lib, ... }:

{
  options.custom = {
    mpdAddress = lib.mkOption {
      type = lib.types.str;
      default = "alpha.local:6600";
      description = "MPD endpoint for rmpc (host:port or Unix socket).";
    };
    desktopPolicy = {
      output = lib.mkOption {
        type = lib.types.str;
        default = "";
        description = "Output connector; empty uses compositor defaults.";
      };
      mode = lib.mkOption {
        type = lib.types.str;
        default = "preferred";
        description = "Output mode in WIDTHxHEIGHT@REFRESH form, without Hz.";
      };
      scale = lib.mkOption {
        type = lib.types.float;
        default = 1.0;
        description = "Output scale.";
      };
      terminalOpacity = lib.mkOption {
        type = lib.types.str;
        default = "0.80";
        description = "Ghostty background opacity.";
      };
      gtkScale = lib.mkOption {
        type = lib.types.nullOr lib.types.str;
        default = null;
        description = "Optional GTK scale override.";
      };
      restartSynology = lib.mkEnableOption "restarting Synology Drive after Hyprland login";
    };
  };
}
