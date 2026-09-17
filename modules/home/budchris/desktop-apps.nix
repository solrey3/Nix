{ lib, osConfig ? null, pkgs, ... }:

let
  isDesktop = osConfig != null && (
    (osConfig.custom.desktop.enable or false)
      || (osConfig.services.xserver.desktopManager.xfce.enable or false)
  );
  # These launchers enter the system-managed VPN-only network namespace.  The
  # actual applications cannot fall back to the normal network if proton0 goes
  # away.
  vpnAppLaunchers = pkgs.writeShellScriptBin "nicotine" ''
    exec /run/wrappers/bin/sudo -n /run/current-system/sw/bin/vpn-app-launch nicotine "$@"
  '';
  transmissionVpnLauncher = pkgs.writeShellScriptBin "transmission-gtk" ''
    exec /run/wrappers/bin/sudo -n /run/current-system/sw/bin/vpn-app-launch transmission "$@"
  '';
  desktopKeyringCheck = pkgs.writeShellApplication {
    name = "desktop-keyring-check";
    runtimeInputs = with pkgs; [ gawk procps systemd ];
    text = ''
      set -eu
      owner=$(busctl --user --no-pager --no-legend list 2>/dev/null |
        awk '$1 == "org.freedesktop.secrets" { print $2; exit }')
      if [ -z "$owner" ] || [ "$owner" = "-" ]; then
        echo "No org.freedesktop.secrets owner is available." >&2
        exit 1
      fi
      echo "Secret Service owner: $owner"
      echo "Keyring processes:"
      ps -u "$USER" -o pid=,comm= | awk '$2 ~ /^(gnome-keyring-d|kwalletd[0-9]*)$/ { print }'
    '';
  };
in
{
  home.packages = lib.optionals isDesktop
    (with pkgs; [
      # Lightweight Omarchy-inspired tools selected for this fleet. These are
      # independent applications; the Omarchy shell and application bundle are
      # deliberately not included.
      aether
      cliamp
      desktopKeyringCheck
      dua
      imv
      libreoffice
      localsend
      mpv
      tensaku
      xournalpp
    ]) ++ (with pkgs; [
    nextcloud-client
    nicotine-plus
    obsidian
    picard
    quodlibet # Also provides Ex Falso.
    rpi-imager
    transmission_4-gtk

    # Take precedence over the applications' unconfined executables while
    # retaining their desktop files, icons, and other resources.
    (lib.hiPrio vpnAppLaunchers)
    (lib.hiPrio transmissionVpnLauncher)
  ]);
}
