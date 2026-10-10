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

  # MacBookPro14,1's panel is most comfortable at a higher logical DPI.
  services.xserver.dpi = 144;
  custom.desktop = {
    defaultSession = "none+i3";
    environments = {
      i3 = true;
      sway = true;
    };
  };

  system.stateVersion = "24.05";
}
