{ pkgs, ... }:

{
  home.packages = with pkgs; [
    claude-code
    fabric-ai
    herdr
    opencode
    pi-coding-agent
  ];
}
