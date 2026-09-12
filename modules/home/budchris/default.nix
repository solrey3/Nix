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
    ./lazyvim.nix
    ./starship.nix
    ./sway.nix
    ./terminals.nix
    ./theme.nix
    ./hyprland.nix
    ./wallpaper.nix
  ];

  home = {
    username = "budchris";
    homeDirectory = "/home/budchris";
    stateVersion = "25.11";
  };

  programs.home-manager.enable = true;
}
