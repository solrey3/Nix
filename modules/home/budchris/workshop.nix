{ config, lib, osConfig ? null, pkgs, ... }:

let
  enabled = osConfig != null
    && osConfig.networking.hostName == "oscar"
    && (osConfig.custom.desktop.environments.hyprland or false);
  description = "LG Electronics LG ULTRAWIDE 0x000759BE";
  primary = pkgs.writeShellApplication {
    name = "workshop-x11-primary";
    runtimeInputs = with pkgs; [ coreutils hyprland jq xrandr ];
    text = ''
      # XWayland can lag behind the compositor's monitor-added event.
      for _ in 1 2 3 4 5; do
        monitors=$(hyprctl monitors -j) || exit 0
        output=$(jq -r --arg description ${lib.escapeShellArg description} '
          [.[] | select(.description == $description)] | first | .name // empty
        ' <<< "$monitors")
        if [ -z "$output" ]; then
          output=$(jq -r '[.[] | select(.name == "eDP-1")] | first | .name // empty' <<< "$monitors")
        fi
        [ -n "$output" ] || exit 0
        if xrandr --output "$output" --primary; then
          exit 0
        fi
        sleep 1
      done
    '';
  };
in
{
  config = lib.mkIf enabled {
    home.packages = [ primary ];
    wayland.windowManager.hyprland.settings = {
      # Workshop: preserve connector-independent identities for both external displays.
      monitor = lib.mkForce [
        { output = ""; mode = "preferred"; position = "auto"; scale = 1; }
        { output = "eDP-1"; mode = "1920x1080@60"; position = "0x0"; scale = 1; }
        { output = "desc:${description}"; mode = "2560x1080@60"; position = "1920x0"; scale = 1; }
        { output = "desc:HP Inc. HP 25f 3CM8240RX0"; mode = "1920x1080@60"; position = "4480x0"; scale = 1; }
      ];
      on = lib.mkAfter (map (event: {
        _args = [ event (lib.generators.mkLuaInline ''
          function()
            hl.exec_cmd("${primary}/bin/workshop-x11-primary")
          end
        '') ];
      }) [ "hyprland.start" "monitor.added" "monitor.removed" ]);
    };
  };
}
