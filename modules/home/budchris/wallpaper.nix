{ lib, pkgs, osConfig ? null, ... }:

let
  desktopEnabled = osConfig != null && (osConfig.custom.desktop.enable or false);
  plasmaEnabled = desktopEnabled && (osConfig.custom.desktop.environments.plasma or false);
  wallpaper = ./wallpapers/quebec-wall-11-inspired.png;
  wallpaperName = "quebec-wall-11-inspired.png";
in
{
  config = lib.mkIf desktopEnabled {
    home.file."Pictures/Wallpapers/${wallpaperName}".source = wallpaper;

    # Plasma does not consume the Hyprland wallpaper or GTK dark-mode
    # configuration. Apply both defaults when Plasma finishes starting.
    xdg.configFile."autostart/tokyo-night-desktop.desktop" = lib.mkIf plasmaEnabled {
      text = ''
        [Desktop Entry]
        Type=Application
        Name=Tokyo Night desktop defaults
        Comment=Apply the dark color scheme and Quebec Wall-11-inspired wallpaper
        Exec=${pkgs.runtimeShell} -c '${pkgs.kdePackages.plasma-workspace}/bin/plasma-apply-colorscheme BreezeDark >/dev/null 2>&1 || true; ${pkgs.kdePackages.plasma-workspace}/bin/plasma-apply-wallpaperimage ${wallpaper} >/dev/null 2>&1 || true'
        Terminal=false
        X-KDE-autostart-phase=1
        X-GNOME-Autostart-enabled=true
      '';
    };
  };
}
