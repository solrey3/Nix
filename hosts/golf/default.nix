{ config, hostname, lib, ... }:

{
  imports = [
    ./hardware-configuration.nix
    ../../modules/nixos/docker.nix
    ../../modules/nixos/laptop.nix
    ../../modules/nixos/xfce4.nix
    ../../modules/nixos/tailscale.nix
    ../../modules/nixos/users/budchris.nix
  ];

  networking.hostName = hostname;

  # Use the same XFCE-backed i3 session and keybindings as alpha.
  home-manager.users.${config.custom.fleet.primaryUser} = { ... }: {
    xdg.configFile."i3/config".source = ./config/i3/config;
  };
  boot.loader.systemd-boot.enable = true;
  boot.loader.efi.canTouchEfiVariables = true;

  # Late-2011 MacBookPro8,2. The generated hardware file supplies broadcom_sta.
  # That unmaintained driver is insecure, but it is retained deliberately to
  # match this machine's currently working internal Wi-Fi configuration.
  nixpkgs.config.allowInsecurePredicate = pkg: lib.getName pkg == "broadcom-sta";

  system.stateVersion = "24.05";
}
