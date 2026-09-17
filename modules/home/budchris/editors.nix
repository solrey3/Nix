{ pkgs, ... }:

let
  # Use the Freedesktop Secret Service API consistently. Plasma may keep an
  # unlocked KWallet for native KDE clients, but Electron does not switch its
  # password-store implementation as sessions change.
  cursor = pkgs.writeShellScriptBin "cursor" ''
    exec ${pkgs.code-cursor}/bin/cursor --password-store=gnome-libsecret "$@"
  '';
in
{
  home.packages = [ cursor ];
}
