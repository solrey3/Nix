{ lib, pkgs, osConfig ? null, ... }:

let
  hostName = osConfig.networking.hostName or "";
  isBravo = hostName == "bravo";
  isQuebec = hostName == "quebec";
  quebecWallpaper = ./wallpapers/quebec-wall-11-inspired.svg;

  swayLaptopPowerProfile = pkgs.writeShellScript "sway-laptop-power-profile" ''
    set -eu

    has_battery() {
      compgen -G /sys/class/power_supply/BAT* >/dev/null
    }

    on_ac_power() {
      for supply in /sys/class/power_supply/*; do
        [ -r "$supply/type" ] || continue
        [ -r "$supply/online" ] || continue
        case "$(cat "$supply/type")" in
          Mains|USB|USB_C|USB_PD)
            [ "$(cat "$supply/online")" = "1" ] && return 0
            ;;
        esac
      done
      return 1
    }

    set_profile() {
      current="$(${pkgs.power-profiles-daemon}/bin/powerprofilesctl get 2>/dev/null || true)"
      [ "$current" = "$1" ] || ${pkgs.power-profiles-daemon}/bin/powerprofilesctl set "$1" || true
    }

    apply_profile() {
      has_battery || exit 0
      if on_ac_power; then
        set_profile balanced
      else
        set_profile power-saver
      fi
    }

    apply_profile
    [ "''${1:-}" = "--watch" ] || exit 0

    while sleep 30; do
      apply_profile
    done
  '';

  swayPowerProfileCycle = pkgs.writeShellScript "sway-power-profile-cycle" ''
    set -eu
    current="$(${pkgs.power-profiles-daemon}/bin/powerprofilesctl get 2>/dev/null || echo balanced)"
    case "$current" in
      power-saver) next=balanced ;;
      balanced) next=performance ;;
      *) next=power-saver ;;
    esac
    ${pkgs.power-profiles-daemon}/bin/powerprofilesctl set "$next"
  '';

  swayIdleSuspend = pkgs.writeShellScript "sway-idle-suspend" ''
    # Quebec may turn its display off while playing music, but must not suspend
    # on AC power. Preserve the normal idle suspend behavior on battery and on
    # other hosts.
    if ${lib.boolToString isQuebec}; then
      for supply in /sys/class/power_supply/*; do
        [ -r "$supply/type" ] || continue
        [ -r "$supply/online" ] || continue
        case "$(cat "$supply/type")" in
          Mains|USB|USB_C|USB_PD)
            [ "$(cat "$supply/online")" = "1" ] && exit 0
            ;;
        esac
      done
    fi
    exec ${pkgs.systemd}/bin/systemctl suspend
  '';

  swayWaybarToggle = pkgs.writeShellScript "sway-waybar-toggle" ''
    ${pkgs.procps}/bin/pkill waybar || exec ${pkgs.waybar}/bin/waybar
  '';

  screenshotRegion = pkgs.writeShellScriptBin "desktop-screenshot-region" ''
    set -eu
    dir="$HOME/Pictures/Screenshots"
    mkdir -p "$dir"
    file="$dir/$(date +%Y-%m-%d_%H-%M-%S).png"
    geometry="$(${pkgs.slurp}/bin/slurp)"
    ${pkgs.grim}/bin/grim -g "$geometry" "$file"
    ${pkgs.wl-clipboard}/bin/wl-copy < "$file"
    ${pkgs.libnotify}/bin/notify-send "Screenshot copied" "$file"
  '';

  screenshotOutput = pkgs.writeShellScriptBin "desktop-screenshot-output" ''
    set -eu
    dir="$HOME/Pictures/Screenshots"
    mkdir -p "$dir"
    file="$dir/$(date +%Y-%m-%d_%H-%M-%S).png"
    ${pkgs.grim}/bin/grim "$file"
    ${pkgs.wl-clipboard}/bin/wl-copy < "$file"
    ${pkgs.libnotify}/bin/notify-send "Screenshot copied" "$file"
  '';

  screenshotAnnotate = pkgs.writeShellScriptBin "desktop-screenshot-annotate" ''
    set -eu
    dir="$HOME/Pictures/Screenshots"
    mkdir -p "$dir"
    file="$dir/$(date +%Y-%m-%d_%H-%M-%S).png"
    geometry="$(${pkgs.slurp}/bin/slurp)"
    ${pkgs.grim}/bin/grim -g "$geometry" "$file"
    exec ${pkgs.tensaku}/bin/tensaku "$file"
  '';

  swayAppKeys = ''
    ### Shared desktop application bindings
    bindsym $mod+Shift+b exec ${pkgs.xdg-utils}/bin/xdg-open https://www.google.com
    bindsym $mod+Shift+f exec ${pkgs.xdg-utils}/bin/xdg-open "$HOME"
    bindsym $mod+Shift+o exec ${pkgs.obsidian}/bin/obsidian
    bindsym $mod+Ctrl+s exec ${pkgs.localsend}/bin/localsend_app
    bindsym $mod+Shift+Mod1+m exec ${pkgs.ghostty}/bin/ghostty -e ${pkgs.cliamp}/bin/cliamp
    bindsym $mod+Shift+t exec tokyo-night-toggle
    bindsym $mod+Ctrl+u exec ${pkgs.ghostty}/bin/ghostty -e ${pkgs.dua}/bin/dua i "$HOME"
    bindsym Print exec desktop-screenshot-region
    bindsym Shift+Print exec desktop-screenshot-output
    bindsym Ctrl+Print exec desktop-screenshot-annotate
  '';

  swayStatusBar = ''
    bar {
        position top

        # When the status_command prints a new line to stdout, swaybar updates.
        # The default just shows the current date and time.
        status_command while date +'%Y-%m-%d %X'; do sleep 1; done

        colors {
            statusline #ffffff
            background #323232
            inactive_workspace #32323200 #32323200 #5c5c5c
        }
    }
  '';

  quebecSwayWallpaperAutostart = lib.optionalString isQuebec ''
    exec_always ${pkgs.runtimeShell} -lc '${pkgs.procps}/bin/pkill -x swaybg || true; exec ${pkgs.swaybg}/bin/swaybg -i ${quebecWallpaper} -m fill'
  '';

  swayLock =
    if isQuebec then
      "${pkgs.swaylock}/bin/swaylock -f -i ${quebecWallpaper} -s fill"
    else
      "${pkgs.swaylock}/bin/swaylock -f -c 111111";

  swayAutostart = ''
    # Export Wayland/Sway environment variables into the D-Bus session and
    # systemd user manager so that services (including gnome-keyring's
    # secrets component) can locate the Wayland display.
    exec ${pkgs.dbus}/bin/dbus-update-activation-environment --systemd DISPLAY WAYLAND_DISPLAY SWAYSOCK XDG_CURRENT_DESKTOP=sway
    # Start the GNOME Keyring daemon. PAM (via sddm.enableGnomeKeyring)
    # already unlocks the keyring at login; this just ensures the daemon
    # is running so libsecret clients (Cursor, browsers, …) can connect.
    exec ${pkgs.gnome-keyring}/bin/gnome-keyring-daemon --start --components=pkcs11,secrets
  '' + ''
    # Status bar and system tray. Waybar's tray hosts NetworkManager, Proton VPN,
    # Bluetooth, and other StatusNotifier/AppIndicator applications.
    exec_always ${pkgs.runtimeShell} -lc '${pkgs.procps}/bin/pkill waybar || true; exec ${pkgs.waybar}/bin/waybar'
    exec_always ${pkgs.runtimeShell} -lc '${pkgs.procps}/bin/pkill -x swayidle || true; exec ${pkgs.swayidle}/bin/swayidle -w timeout 300 "${pkgs.brightnessctl}/bin/brightnessctl -s set 10%" resume "${pkgs.brightnessctl}/bin/brightnessctl -r" timeout 600 "${swayLock}" timeout 900 "${pkgs.sway}/bin/swaymsg output * power off" resume "${pkgs.sway}/bin/swaymsg output * power on" timeout 1800 "${swayIdleSuspend}" before-sleep "${swayLock}" lock "${swayLock}"'
    exec_always ${pkgs.runtimeShell} -lc '${pkgs.procps}/bin/pkill -f "[s]way-laptop-power-profile" || true; exec ${swayLaptopPowerProfile} --watch'
    ${quebecSwayWallpaperAutostart}exec ${pkgs.networkmanagerapplet}/bin/nm-applet --indicator
    exec ${pkgs.blueman}/bin/blueman-applet
    exec ${pkgs.proton-vpn}/bin/protonvpn-app --start-minimized
  '';

  swayKeyboardLogout = ''
    set $mode_logout Log out? Enter = yes, Escape = no
    bindsym $mod+Shift+e mode "$mode_logout"

    mode "$mode_logout" {
        bindsym Return exec swaymsg exit, mode "default"
        bindsym Escape mode "default"
    }
  '';

  swayDisplay = ''

### Built-in display density
# Native 2880x1920 panel at 1.5x gives a 1920x1280 logical workspace
# instead of the default 2x-scaled 1440x960 workspace.
output eDP-1 mode 2880x1920@120Hz scale 1.5
'';

  swayTrackpad = ''

### Desktop-like trackpad behavior
# Match COSMIC/Plasma defaults more closely: tap-to-click, multi-finger tap
# clicks, traditional two-finger scrolling, clickfinger right/middle click, and
# click-to-focus instead of focusing windows just by brushing the trackpad.
input type:touchpad {
    tap enabled
    # 1-finger tap = left click, 2-finger tap = right click,
    # 3-finger tap = middle click.
    tap_button_map lrm
    drag enabled
    drag_lock disabled
    # Keep taps responsive even immediately after typing/using the pointing stick.
    dwt disabled
    dwtp disabled
    natural_scroll disabled
    scroll_method two_finger
    click_method clickfinger
    middle_emulation enabled
    pointer_accel 0.25
    accel_profile adaptive
}

focus_follows_mouse no
mouse_warping none

# Touchpad gestures similar to modern desktop environments.
bindgesture swipe:3:left workspace next
bindgesture swipe:3:right workspace prev
bindgesture swipe:3:up exec $menu
bindgesture swipe:3:down scratchpad show
'';

  swayLaptopKeys = ''

### Laptop controls
bindsym XF86MonBrightnessDown exec ${pkgs.brightnessctl}/bin/brightnessctl set 5%-
bindsym XF86MonBrightnessUp exec ${pkgs.brightnessctl}/bin/brightnessctl set +5%
bindsym XF86AudioMute exec ${pkgs.wireplumber}/bin/wpctl set-mute @DEFAULT_AUDIO_SINK@ toggle
bindsym XF86AudioLowerVolume exec ${pkgs.wireplumber}/bin/wpctl set-volume @DEFAULT_AUDIO_SINK@ 5%-
bindsym XF86AudioRaiseVolume exec ${pkgs.wireplumber}/bin/wpctl set-volume @DEFAULT_AUDIO_SINK@ 5%+
bindsym XF86AudioMicMute exec ${pkgs.wireplumber}/bin/wpctl set-mute @DEFAULT_AUDIO_SOURCE@ toggle
bindsym $mod+Ctrl+l exec ${swayLock}
bindsym XF86Sleep exec ${pkgs.systemd}/bin/systemctl suspend
'';
in
{
  # Bravo's desktop needs larger GTK UI elements. Keep this host-specific so
  # the shared Home Manager profile does not scale every Sway/Hyprland host.
  home.sessionVariables = lib.optionalAttrs isBravo {
    GDK_SCALE = "1.5";
  };

  home.packages = with pkgs; [
    blueman
    networkmanagerapplet
    proton-vpn
    screenshotAnnotate
    screenshotOutput
    screenshotRegion
    wdisplays
  ];

  xdg.configFile."sway/config".text = builtins.replaceStrings
    [
      "set $term foot"
      "bindsym $mod+Shift+e exec swaynag -t warning -m 'You pressed the exit shortcut. Do you really want to exit sway? This will end your Wayland session.' -B 'Yes, exit sway' 'swaymsg exit'"
      "bindsym $mod+Shift+c reload"
      swayStatusBar
    ]
    [
      "set $term ${pkgs.ghostty}/bin/ghostty${swayDisplay}${swayTrackpad}${swayLaptopKeys}"
      swayKeyboardLogout
      "bindsym $mod+Shift+c exec ${swayWaybarToggle}"
      "${swayAutostart}${swayAppKeys}"
    ]
    (builtins.readFile "${pkgs.sway-unwrapped}/etc/sway/config");

  xdg.configFile."waybar/config".text = ''
    {
      "layer": "top",
      "position": "top",
      "height": 30,
      "spacing": 8,
      "modules-left": ["sway/workspaces", "sway/mode"],
      "modules-center": ["clock"],
      "modules-right": ["tray", "network", "bluetooth", "pulseaudio", "power-profiles-daemon", "battery"],
      "tray": {
        "icon-size": 18,
        "spacing": 10
      },
      "network": {
        "format-wifi": "  {essid} ({signalStrength}%)",
        "format-ethernet": "󰈀  {ipaddr}/{cidr}",
        "format-disconnected": "󰖪  disconnected",
        "tooltip-format": "{ifname}: {ipaddr}/{cidr}",
        "on-click": "${pkgs.networkmanagerapplet}/bin/nm-connection-editor"
      },
      "bluetooth": {
        "format": " {status}",
        "format-connected": " {device_alias}",
        "format-disabled": " disabled",
        "format-off": " off",
        "on-click": "${pkgs.blueman}/bin/blueman-manager"
      },
      "pulseaudio": {
        "format": "  {volume}%",
        "format-muted": "  muted",
        "on-click": "${pkgs.pavucontrol}/bin/pavucontrol"
      },
      "power-profiles-daemon": {
        "format": "{icon} {profile}",
        "tooltip-format": "Power profile: {profile}\nDriver: {driver}",
        "format-icons": {
          "performance": "",
          "balanced": "",
          "power-saver": ""
        },
        "on-click": "${swayPowerProfileCycle}"
      },
      "battery": {
        "format": "{capacity}% {icon}",
        "format-charging": "{capacity}% 󰂄",
        "format-plugged": "{capacity}% 󰚥",
        "states": {
          "warning": 30,
          "critical": 15
        },
        "format-icons": ["󰂎", "󰁺", "󰁻", "󰁼", "󰁽", "󰁾", "󰁿", "󰂀", "󰂁", "󰂂", "󰁹"]
      },
      "clock": {
        "format": "{:%Y-%m-%d %H:%M}"
      }
    }
  '';

  xdg.configFile."waybar/style.css".text = ''
    @import url("file:///home/budchris/.cache/tokyo-night/waybar.css");

    * {
      border: none;
      border-radius: 0;
      font-family: "JetBrainsMono Nerd Font Mono", monospace;
      font-size: 12px;
      min-height: 0;
    }

    window#waybar {
      background: @tn_background;
      color: @tn_foreground;
    }

    #workspaces button,
    #mode,
    #clock,
    #tray,
    #network,
    #bluetooth,
    #pulseaudio,
    #battery {
      padding: 0 10px;
    }

    #workspaces button {
      color: @tn_foreground;
    }

    #workspaces button.focused,
    #workspaces button.active {
      background: @tn_selection;
      color: @tn_foreground;
    }

    #network.disconnected,
    #bluetooth.disabled,
    #bluetooth.off,
    #pulseaudio.muted,
    #power-profiles-daemon.power-saver,
    #battery.warning,
    #battery.critical {
      color: @tn_warning;
    }
  '';
}
