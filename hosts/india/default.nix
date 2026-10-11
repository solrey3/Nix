{ hostname, ... }:

{
  imports = [
    ./hardware-configuration.nix
    ../../modules/nixos/desktop.nix
    ../../modules/nixos/docker.nix
    ../../modules/nixos/laptop.nix
    ../../modules/nixos/tailscale.nix
    ../../modules/nixos/users/budchris.nix
  ];

  networking.hostName = hostname;
  boot.loader.systemd-boot.enable = true;
  boot.loader.efi.canTouchEfiVariables = true;

  # Steam Deck OLED (Galileo), booting NixOS from its SD card.
  custom.desktop = {
    defaultSession = "plasma";
    environments = {
      plasma = true;
    };
  };

  system.stateVersion = "24.05";
}
