{ pkgs, ... }:

{
  imports = [
    ./ai.nix
    ./bash.nix
    ./cli-tools.nix
    ./git.nix
    ./lazyvim.nix
    ./starship.nix
  ];

  programs.home-manager.enable = true;
  programs.zsh.enable = pkgs.stdenv.hostPlatform.isDarwin;
}
