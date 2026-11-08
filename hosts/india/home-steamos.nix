{ ... }:

{
  imports = [ ../../modules/home/budchris/portable.nix ];

  home = {
    username = "deck";
    homeDirectory = "/home/deck";
    stateVersion = "24.11";
  };

  # SteamOS manages the OS; Home Manager only manages this user's environment.
  targets.genericLinux.enable = true;
}
