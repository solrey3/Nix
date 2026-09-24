{ hostname, pkgs, ... }:

{
  imports = [
    ./hardware-configuration.nix
    ../../modules/nixos/1password.nix
    ../../modules/nixos/desktop.nix
    ../../modules/nixos/docker.nix
    ../../modules/nixos/laptop.nix
    ../../modules/nixos/users/budchris.nix
    ../../modules/nixos/vpn.nix
  ];

  networking.hostName = hostname;

  boot.loader.systemd-boot.enable = true;
  boot.loader.efi.canTouchEfiVariables = true;

  custom.desktop = {
    defaultSession = "plasma";
    environments = {
      plasma = true;
      cosmic = true;
      sway = true;
    };
  };

  i18n.extraLocaleSettings = {
    LC_ADDRESS = "en_US.UTF-8";
    LC_IDENTIFICATION = "en_US.UTF-8";
    LC_MEASUREMENT = "en_US.UTF-8";
    LC_MONETARY = "en_US.UTF-8";
    LC_NAME = "en_US.UTF-8";
    LC_NUMERIC = "en_US.UTF-8";
    LC_PAPER = "en_US.UTF-8";
    LC_TELEPHONE = "en_US.UTF-8";
    LC_TIME = "en_US.UTF-8";
  };

  environment.systemPackages = with pkgs; [
    pi-coding-agent
  ];

  # Change this only after reading the NixOS release notes.
  system.stateVersion = "25.11";
}
