{ osConfig, ... }:

{
  imports = [
    ./ai.nix
    ./bash.nix
    ./browsers.nix
    ./cli-tools.nix
    ./desktop-apps.nix
    ./docker.nix
    ./editors.nix
    ./fonts.nix
    ./git.nix
    ./hyprland.nix
    ./quickshell.nix
    ./lazyvim.nix
    ./starship.nix
    ./sway.nix
    ./terminals.nix
    ./theme.nix
    ./wallpaper.nix
  ];

  home = {
    username = osConfig.custom.fleet.primaryUser;
    homeDirectory = osConfig.users.users.${osConfig.custom.fleet.primaryUser}.home;
    stateVersion = "25.11";
  };

  programs.home-manager.enable = true;
}
