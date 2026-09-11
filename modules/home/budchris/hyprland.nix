{ config, lib, osConfig ? null, pkgs, ... }:

let
  enabled = osConfig != null && (osConfig.custom.desktop.environments.hyprland or false);
  isBravo = osConfig != null && osConfig.networking.hostName == "bravo";
  isQuebec = osConfig != null && osConfig.networking.hostName == "quebec";
  nvidia = osConfig != null && lib.elem "nvidia" (osConfig.services.xserver.videoDrivers or [ ]);
  # hyprpaper and hyprlock reliably decode raster images; the SVG source is
  # retained alongside this pre-rendered ultrawide wallpaper.
  wallpaper = ./wallpapers/tokyo-night.png;
  lua = lib.generators.mkLuaInline;
  exec = command: lua "hl.dsp.exec_cmd(${builtins.toJSON command})";
  workspaces = builtins.concatLists (builtins.genList
    (i:
      let ws = toString (i + 1); in [
        {
          _args = [
            "SUPER + ${ws}"
            (lua "hl.dsp.focus({ workspace = ${ws} })")
          ];
        }
        {
          _args = [
            "SUPER + SHIFT + ${ws}"
            (lua "hl.dsp.window.move({ workspace = ${ws} })")
          ];
        }
      ])
    9);
  waybarWorkspaceNumbers = builtins.genList (i: toString (i + 1)) 5;
  waybarWorkspaceStatus = pkgs.writeShellApplication {
    name = "waybar-workspace-status";
    runtimeInputs = [ pkgs.hyprland pkgs.jq ];
    text = ''
      workspace="$1"
      active="$(hyprctl activeworkspace -j | jq -r .id)"
      if [ "$active" = "$workspace" ]; then
        text="[$workspace]"
        class=active
      else
        text=" $workspace "
        class=inactive
      fi
      jq -cn --arg text "$text" --arg class "$class" '{ text: $text, class: $class }'
    '';
  };
  waybarWorkspaceSelect = pkgs.writeShellApplication {
    name = "waybar-workspace-select";
    runtimeInputs = [ pkgs.hyprland pkgs.procps ];
    text = ''
      workspace="''${1:?workspace number required}"
      case "$workspace" in
        1|2|3|4|5) ;;
        *) echo "invalid workspace: $workspace" >&2; exit 2 ;;
      esac
      hyprctl dispatch "hl.dsp.focus({ workspace = $workspace })"
      # Refresh all workspace labels immediately instead of waiting for their
      # low-frequency fallback poll.
      pkill -RTMIN+8 -x .waybar-wrapped 2>/dev/null || true
    '';
  };
in
{
  config = lib.mkIf enabled {
    home.packages = with pkgs; [
      brightnessctl
      fuzzel
      grim
      hypridle
      hyprlock
      hyprpaper
      hyprpicker
      hyprsunset
      libnotify
      playerctl
      slurp
      waybar
      wl-clipboard
    ];

    wayland.windowManager.hyprland = {
      enable = true;
      package = null;
      portalPackage = null;
      configType = "lua";
      systemd.enable = false;

      settings = {
        config = {
          input = {
            kb_layout = "us";
            follow_mouse = 1;
            touchpad = {
              natural_scroll = false;
              tap_to_click = true;
            };
          };
          general = {
            gaps_in = 5;
            gaps_out = 10;
            border_size = 2;
            col = {
              active_border = "rgba(7aa2f7ff)";
              inactive_border = "rgba(414868aa)";
            };
            layout = "dwindle";
            allow_tearing = false;
          };
          decoration = {
            rounding = 6;
            active_opacity = 1.0;
            inactive_opacity = 0.96;
            blur = { enabled = true; size = 5; passes = 2; };
            shadow.enabled = false;
          };
          animations.enabled = true;
          misc = {
            disable_hyprland_logo = true;
            disable_splash_rendering = true;
          };
        };

        monitor =
          if isQuebec then {
            output = "eDP-1";
            mode = "2880x1920@120";
            position = "auto";
            scale = 1.5;
          } else {
            output = "";
            mode = "preferred";
            position = "auto";
            scale = 1;
          };

        env = [
          { _args = [ "NIXOS_OZONE_WL" "1" ]; }
          { _args = [ "ELECTRON_OZONE_PLATFORM_HINT" "auto" ]; }
          { _args = [ "XCURSOR_SIZE" "24" ]; }
          { _args = [ "HYPRCURSOR_SIZE" "24" ]; }
        ] ++ lib.optionals nvidia [
          { _args = [ "LIBVA_DRIVER_NAME" "nvidia" ]; }
          { _args = [ "__GLX_VENDOR_LIBRARY_NAME" "nvidia" ]; }
          { _args = [ "NVD_BACKEND" "direct" ]; }
        ];

        on = {
          _args = [
            "hyprland.start"
            (lua ''
              function()
                hl.exec_cmd("${pkgs.dbus}/bin/dbus-update-activation-environment --systemd DISPLAY WAYLAND_DISPLAY XDG_CURRENT_DESKTOP XDG_SESSION_TYPE")
                hl.exec_cmd("${pkgs.systemd}/bin/systemctl --user import-environment DISPLAY WAYLAND_DISPLAY XDG_CURRENT_DESKTOP XDG_SESSION_TYPE")
                hl.exec_cmd("${pkgs.gnome-keyring}/bin/gnome-keyring-daemon --start --components=pkcs11,secrets")
                hl.exec_cmd("${pkgs.hyprpaper}/bin/hyprpaper")
                -- hyprpaper can start before its layer surface is ready. Apply
                -- the wallpaper again after startup so the desktop is never
                -- left with Hyprland's solid fallback background.
                hl.exec_cmd("${pkgs.bash}/bin/sh -c 'sleep 1; ${pkgs.hyprland}/bin/hyprctl hyprpaper wallpaper ,${wallpaper}'")
                hl.exec_cmd("${pkgs.hypridle}/bin/hypridle")
                hl.exec_cmd("${pkgs.waybar}/bin/waybar -c ${config.xdg.configHome}/waybar/config-hyprland -s ${config.xdg.configHome}/waybar/style.css")
                hl.exec_cmd("${pkgs.networkmanagerapplet}/bin/nm-applet --indicator")
                hl.exec_cmd("${pkgs.blueman}/bin/blueman-applet")
                ${lib.optionalString isBravo ''
                  hl.exec_cmd("${pkgs.bash}/bin/sh -c 'sleep 1; ${pkgs.systemd}/bin/systemctl --user restart app-synology\\x2ddrive@autostart.service'")
                ''}
              end
            '')
          ];
        };

        curve = {
          _args = [ "easeOut" { type = "bezier"; points = [ [ 0.23 1 ] [ 0.32 1 ] ]; } ];
        };
        animation = [
          { leaf = "windows"; enabled = true; speed = 4; bezier = "easeOut"; }
          { leaf = "fade"; enabled = true; speed = 3; bezier = "easeOut"; }
          { leaf = "workspaces"; enabled = true; speed = 4; bezier = "easeOut"; style = "slide"; }
        ];

        # Three-finger horizontal swipes move between adjacent workspaces.
        gesture = {
          fingers = 3;
          direction = "horizontal";
          action = "workspace";
        };

        bind = [
          { _args = [ "SUPER + RETURN" (exec "${pkgs.ghostty}/bin/ghostty") ]; }
          { _args = [ "SUPER + D" (exec "${pkgs.fuzzel}/bin/fuzzel") ]; }
          { _args = [ "SUPER + SHIFT + Q" (lua "hl.dsp.window.close()") ]; }
          { _args = [ "SUPER + SHIFT + E" (lua "hl.dsp.exit()") ]; }
          { _args = [ "SUPER + F" (lua "hl.dsp.window.fullscreen()") ]; }
          { _args = [ "SUPER + SHIFT + SPACE" (lua ''hl.dsp.window.float({ action = "toggle" })'') ]; }
          { _args = [ "SUPER + H" (lua ''hl.dsp.focus({ direction = "left" })'') ]; }
          { _args = [ "SUPER + J" (lua ''hl.dsp.focus({ direction = "down" })'') ]; }
          { _args = [ "SUPER + K" (lua ''hl.dsp.focus({ direction = "up" })'') ]; }
          { _args = [ "SUPER + L" (lua ''hl.dsp.focus({ direction = "right" })'') ]; }
          { _args = [ "SUPER + SHIFT + H" (lua ''hl.dsp.window.move({ direction = "left" })'') ]; }
          { _args = [ "SUPER + SHIFT + J" (lua ''hl.dsp.window.move({ direction = "down" })'') ]; }
          { _args = [ "SUPER + SHIFT + K" (lua ''hl.dsp.window.move({ direction = "up" })'') ]; }
          { _args = [ "SUPER + SHIFT + L" (lua ''hl.dsp.window.move({ direction = "right" })'') ]; }
          { _args = [ "SUPER + CTRL + L" (exec "${pkgs.hyprlock}/bin/hyprlock") ]; }
          { _args = [ "SUPER + SHIFT + B" (exec "${pkgs.xdg-utils}/bin/xdg-open https://www.google.com") ]; }
          { _args = [ "SUPER + SHIFT + F" (exec "${pkgs.xdg-utils}/bin/xdg-open $HOME") ]; }
          { _args = [ "SUPER + SHIFT + O" (exec "${pkgs.obsidian}/bin/obsidian") ]; }
          { _args = [ "SUPER + CTRL + S" (exec "${pkgs.localsend}/bin/localsend_app") ]; }
          { _args = [ "SUPER + SHIFT + ALT + M" (exec "${pkgs.ghostty}/bin/ghostty -e ${pkgs.cliamp}/bin/cliamp") ]; }
          { _args = [ "SUPER + SHIFT + T" (exec "tokyo-night-toggle") ]; }
          { _args = [ "SUPER + CTRL + U" (exec "${pkgs.ghostty}/bin/ghostty -e ${pkgs.dua}/bin/dua i $HOME") ]; }
          { _args = [ "PRINT" (exec "desktop-screenshot-region") ]; }
          { _args = [ "SHIFT + PRINT" (exec "desktop-screenshot-output") ]; }
          { _args = [ "CTRL + PRINT" (exec "desktop-screenshot-annotate") ]; }
        ] ++ workspaces ++ [
          { _args = [ "XF86MonBrightnessDown" (exec "${pkgs.brightnessctl}/bin/brightnessctl set 5%-") { locked = true; repeating = true; } ]; }
          { _args = [ "XF86MonBrightnessUp" (exec "${pkgs.brightnessctl}/bin/brightnessctl set +5%") { locked = true; repeating = true; } ]; }
          { _args = [ "XF86AudioLowerVolume" (exec "${pkgs.wireplumber}/bin/wpctl set-volume @DEFAULT_AUDIO_SINK@ 5%-") { locked = true; repeating = true; } ]; }
          { _args = [ "XF86AudioRaiseVolume" (exec "${pkgs.wireplumber}/bin/wpctl set-volume @DEFAULT_AUDIO_SINK@ 5%+") { locked = true; repeating = true; } ]; }
          { _args = [ "XF86AudioMute" (exec "${pkgs.wireplumber}/bin/wpctl set-mute @DEFAULT_AUDIO_SINK@ toggle") { locked = true; } ]; }
          { _args = [ "XF86AudioMicMute" (exec "${pkgs.wireplumber}/bin/wpctl set-mute @DEFAULT_AUDIO_SOURCE@ toggle") { locked = true; } ]; }
          { _args = [ "XF86AudioPlay" (exec "${pkgs.playerctl}/bin/playerctl play-pause") { locked = true; } ]; }
          { _args = [ "XF86AudioNext" (exec "${pkgs.playerctl}/bin/playerctl next") { locked = true; } ]; }
          { _args = [ "XF86AudioPrev" (exec "${pkgs.playerctl}/bin/playerctl previous") { locked = true; } ]; }
        ];
      };
    };

    xdg.configFile = {
      "hypr/hyprpaper.conf".text = ''
        preload = ${wallpaper}
        wallpaper = ,${wallpaper}
        splash = false
      '';

      "hypr/hypridle.conf".text = ''
        general {
          lock_cmd = ${pkgs.procps}/bin/pidof hyprlock || ${pkgs.hyprlock}/bin/hyprlock
          before_sleep_cmd = ${pkgs.systemd}/bin/loginctl lock-session
          after_sleep_cmd = ${pkgs.hyprland}/bin/hyprctl dispatch 'hl.dsp.dpms({ action = "on" })'
        }
        listener {
          timeout = 600
          on-timeout = ${pkgs.systemd}/bin/loginctl lock-session
        }
        listener {
          timeout = 900
          on-timeout = ${pkgs.hyprland}/bin/hyprctl dispatch 'hl.dsp.dpms({ action = "off" })'
          on-resume = ${pkgs.hyprland}/bin/hyprctl dispatch 'hl.dsp.dpms({ action = "on" })'
        }
      '';

      "hypr/hyprlock.conf".text = ''
        background {
          monitor =
          path = ${wallpaper}
          blur_passes = 2
        }
        label {
          monitor =
          text = cmd[update:1000] date +"%H:%M"
          color = rgb(c0caf5)
          font_size = 64
          position = 0, 180
          halign = center
          valign = center
        }
        label {
          monitor =
          text = cmd[update:60000] date +"%A, %B %d"
          color = rgb(a9b1d6)
          font_size = 20
          position = 0, 120
          halign = center
          valign = center
        }
        input-field {
          monitor =
          size = 320, 56
          position = 0, -20
          halign = center
          valign = center
          outline_thickness = 2
          outer_color = rgb(7aa2f7)
          inner_color = rgb(1a1b26)
          font_color = rgb(c0caf5)
          placeholder_text = Password
        }
      '';

      "waybar/config-hyprland".text = builtins.toJSON ({
        layer = "top";
        position = "top";
        height = 30;
        spacing = 8;
        # Use explicit modules because Waybar's Hyprland workspace buttons did
        # not dispatch pointer selections reliably on Quebec.
        modules-left = map (ws: "custom/workspace-${ws}") waybarWorkspaceNumbers;
        modules-center = [ "clock" ];
        modules-right = [ "tray" "network" "bluetooth" "wireplumber" "cpu" "battery" ];
        clock.format = "{:%Y-%m-%d %H:%M}";
        network = {
          "format-wifi" = "  {essid} ({signalStrength}%)";
          "format-ethernet" = "󰈀  {ipaddr}/{cidr}";
          "format-disconnected" = "󰖪  disconnected";
          "on-click" = "${pkgs.networkmanagerapplet}/bin/nm-connection-editor";
        };
        bluetooth = {
          format = " {status}";
          "format-connected" = " {device_alias}";
          "on-click" = "${pkgs.blueman}/bin/blueman-manager";
        };
        wireplumber = {
          format = "  {volume}%";
          "format-muted" = "  muted";
          "on-click" = "${pkgs.pavucontrol}/bin/pavucontrol";
        };
        cpu = { format = "CPU {usage}%"; interval = 5; };
        battery = { format = "{capacity}% {icon}"; };
        tray.spacing = 10;
      } // lib.genAttrs (map (ws: "custom/workspace-${ws}") waybarWorkspaceNumbers)
        (name:
          let ws = lib.removePrefix "custom/workspace-" name; in {
            exec = "${waybarWorkspaceStatus}/bin/waybar-workspace-status ${ws}";
            "on-click" = "${waybarWorkspaceSelect}/bin/waybar-workspace-select ${ws}";
            # Signals refresh immediately after pointer selection; this poll is
            # only a fallback for keyboard-initiated workspace changes.
            signal = 8;
            interval = 10;
            "return-type" = "json";
            tooltip = false;
          }));
    };
  };
}
