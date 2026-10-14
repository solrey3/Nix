{ ... }:

{
  imports = [
    ./ai.nix
    ./bash.nix
    ./cli-tools.nix
    ./git.nix
    ./lazyvim.nix
    ./starship.nix
    ./zsh.nix
  ];

  programs.home-manager.enable = true;
}
