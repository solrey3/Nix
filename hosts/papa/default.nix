{ hostname, ... }:

{
  imports = [
    ./hardware-configuration.nix
    ../../modules/nixos/desktop.nix
    ../../modules/nixos/docker.nix
    ../../modules/nixos/tailscale.nix
    ../../modules/nixos/users/budchris.nix
  ];

  networking.hostName = hostname;
  boot.loader.systemd-boot.enable = true;
  boot.loader.efi.canTouchEfiVariables = true;

  hardware.enableRedistributableFirmware = true;
  hardware.bluetooth = {
    enable = true;
    powerOnBoot = true;
  };
  services.fstrim.enable = true;

  # Beelink SER5 MAX: preserve the Wayland-oriented desktop role.
  custom.desktop = {
    defaultSession = "hyprland";
    environments = {
      hyprland = true;
    };
  };

  system.stateVersion = "25.05";
}
