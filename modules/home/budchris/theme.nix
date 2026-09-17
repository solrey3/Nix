{ config, lib, pkgs, ... }:

let
  themeDir = "${config.xdg.cacheHome}/tokyo-night";

  dark = {
    background = "1a1b26";
    foreground = "c0caf5";
    selection = "33467c";
    black = "15161e";
    red = "f7768e";
    green = "9ece6a";
    yellow = "e0af68";
    blue = "7aa2f7";
    magenta = "bb9af7";
    cyan = "7dcfff";
    white = "a9b1d6";
    brightBlack = "414868";
    brightWhite = "c0caf5";
    warning = "ff9e64";
  };

  light = {
    background = "e1e2e7";
    foreground = "3760bf";
    selection = "b6bfe2";
    black = "b4b5b9";
    red = "f52a65";
    green = "587539";
    yellow = "8c6c3e";
    blue = "2e7de9";
    magenta = "9854f1";
    cyan = "007197";
    white = "6172b0";
    brightBlack = "a1a6c5";
    brightWhite = "3760bf";
    warning = "b15c00";
  };

  ghosttyTheme = p: ''
    background = ${p.background}
    foreground = ${p.foreground}
    selection-background = ${p.selection}
    selection-foreground = ${p.foreground}
    palette = 0=#${p.black}
    palette = 1=#${p.red}
    palette = 2=#${p.green}
    palette = 3=#${p.yellow}
    palette = 4=#${p.blue}
    palette = 5=#${p.magenta}
    palette = 6=#${p.cyan}
    palette = 7=#${p.white}
    palette = 8=#${p.brightBlack}
    palette = 9=#${p.red}
    palette = 10=#${p.green}
    palette = 11=#${p.yellow}
    palette = 12=#${p.blue}
    palette = 13=#${p.magenta}
    palette = 14=#${p.cyan}
    palette = 15=#${p.brightWhite}
  '';

  alacrittyTheme = p: pkgs.writeText "tokyo-night-alacritty.toml" ''
    [colors.primary]
    background = "#${p.background}"
    foreground = "#${p.foreground}"

    [colors.selection]
    background = "#${p.selection}"
    text = "#${p.foreground}"

    [colors.normal]
    black = "#${p.black}"
    red = "#${p.red}"
    green = "#${p.green}"
    yellow = "#${p.yellow}"
    blue = "#${p.blue}"
    magenta = "#${p.magenta}"
    cyan = "#${p.cyan}"
    white = "#${p.white}"

    [colors.bright]
    black = "#${p.brightBlack}"
    red = "#${p.red}"
    green = "#${p.green}"
    yellow = "#${p.yellow}"
    blue = "#${p.blue}"
    magenta = "#${p.magenta}"
    cyan = "#${p.cyan}"
    white = "#${p.brightWhite}"
  '';

  waybarTheme = p: pkgs.writeText "tokyo-night-waybar.css" ''
    @define-color tn_background #${p.background};
    @define-color tn_foreground #${p.foreground};
    @define-color tn_selection #${p.selection};
    @define-color tn_muted #${p.brightBlack};
    @define-color tn_accent #${p.blue};
    @define-color tn_warning #${p.warning};
  '';

  darkAlacritty = alacrittyTheme dark;
  lightAlacritty = alacrittyTheme light;
  darkWaybar = waybarTheme dark;
  lightWaybar = waybarTheme light;

  tokyoNightSet = pkgs.writeShellApplication {
    name = "tokyo-night-set";
    runtimeInputs = with pkgs; [ coreutils glib libnotify procps ];
    text = ''
      set -eu
      mode="''${1:-}"
      case "$mode" in
        dark)
          alacritty=${lib.escapeShellArg (toString darkAlacritty)}
          waybar=${lib.escapeShellArg (toString darkWaybar)}
          gtk_mode=prefer-dark
          active=7aa2f7
          inactive=414868
          ;;
        light)
          alacritty=${lib.escapeShellArg (toString lightAlacritty)}
          waybar=${lib.escapeShellArg (toString lightWaybar)}
          gtk_mode=prefer-light
          active=2e7de9
          inactive=a1a6c5
          ;;
        *)
          echo "usage: tokyo-night-set dark|light" >&2
          exit 2
          ;;
      esac

      theme_dir=${lib.escapeShellArg themeDir}
      install -Dm644 "$alacritty" "$theme_dir/alacritty.toml"
      install -Dm644 "$waybar" "$theme_dir/waybar.css"
      printf '%s\n' "$mode" > "$theme_dir/mode"

      gsettings set org.gnome.desktop.interface color-scheme "$gtk_mode" 2>/dev/null || true
      gsettings set org.gnome.desktop.interface gtk-theme \
        "$( [ "$mode" = dark ] && printf Adwaita-dark || printf Adwaita )" 2>/dev/null || true

      if command -v hyprctl >/dev/null 2>&1 && [ -n "''${HYPRLAND_INSTANCE_SIGNATURE:-}" ]; then
        # Hyprland's Lua configuration backend does not support `hyprctl
        # keyword`; apply both runtime colors through the Lua evaluator.
        hyprctl eval "hl.config({ general = { col = { active_border = \\\"rgba(''${active}ff)\\\", inactive_border = \\\"rgba(''${inactive}aa)\\\" } } })" >/dev/null || true
      fi

      pkill -SIGUSR2 waybar 2>/dev/null || true
      notify-send "Tokyo Night" "Switched to $mode mode" 2>/dev/null || true
    '';
  };

  tokyoNightToggle = pkgs.writeShellApplication {
    name = "tokyo-night-toggle";
    runtimeInputs = [ tokyoNightSet ];
    text = ''
      mode_file=${lib.escapeShellArg "${themeDir}/mode"}
      if [ -r "$mode_file" ] && [ "$(cat "$mode_file")" = dark ]; then
        exec tokyo-night-set light
      else
        exec tokyo-night-set dark
      fi
    '';
  };
in
{
  home.packages = [ tokyoNightSet tokyoNightToggle ];

  xdg.configFile = {
    "ghostty/themes/Tokyo Night Dark".text = ghosttyTheme dark;
    "ghostty/themes/Tokyo Night Light".text = ghosttyTheme light;
  };

  home.activation.initializeTokyoNight = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
    if [ ! -e ${lib.escapeShellArg "${themeDir}/mode"} ]; then
      $DRY_RUN_CMD mkdir -p ${lib.escapeShellArg themeDir}
      $DRY_RUN_CMD install -m 0644 ${darkAlacritty} ${lib.escapeShellArg "${themeDir}/alacritty.toml"}
      $DRY_RUN_CMD install -m 0644 ${darkWaybar} ${lib.escapeShellArg "${themeDir}/waybar.css"}
      $DRY_RUN_CMD printf '%s\n' dark > ${lib.escapeShellArg "${themeDir}/mode"}
    fi
  '';
}
