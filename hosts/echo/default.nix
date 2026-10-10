{ username, ... }:

{
  imports = [ ../../modules/home/budchris/portable.nix ];

  home = {
    inherit username;
    homeDirectory = "/home/${username}";
    stateVersion = "24.11";
  };
}
