{ hostname, lib, pkgs, ... }:

{
  imports = [
    ./hardware-configuration.nix
    ../../modules/nixos/1password.nix
    ../../modules/nixos/desktop.nix
    ../../modules/nixos/docker.nix
    ../../modules/nixos/laptop.nix
    ../../modules/nixos/mpd.nix
    ../../modules/nixos/users/budchris.nix
    ../../modules/nixos/vpn.nix
  ];

  networking.hostName = hostname;

  boot.loader.systemd-boot.enable = true;
  boot.loader.efi.canTouchEfiVariables = true;

  # The generated hardware config references an encrypted swap mapper that is
  # not opened at boot, causing systemd to wait for it and potentially drop to
  # emergency mode. Disable it until encrypted swap is configured explicitly.
  swapDevices = lib.mkForce [ ];

  # Framework 13 AMD AI 300: the legacy AMD ACP PDM driver exposes the
  # digital mic but records clipped/silent audio. Prefer the SOF ACP70 driver.
  boot.blacklistedKernelModules = [ "snd_acp_pci" ];
  boot.kernelModules = [ "snd_sof_amd_acp70" ];

  hardware.alsa.enablePersistence = true;
  hardware.firmware = [ pkgs.sof-firmware ];

  # Keep audio devices alive when the desktop powers down the display.
  services.pipewire.wireplumber.extraConfig."10-disable-suspend" = {
    "monitor.alsa.rules" = [
      {
        matches = [
          { "node.name" = "~alsa_input.*"; }
          { "node.name" = "~alsa_output.*"; }
        ];
        actions.update-props = {
          "session.suspend-timeout-seconds" = 0;
        };
      }
    ];
  };

  custom.desktop = {
    defaultSession = "plasma";
    environments = {
      plasma = true;
      cosmic = true;
      hyprland = true;
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
    pavucontrol
    pi-coding-agent
  ];

  # Quebec's MPD and rmpc communicate over a local Unix socket. Besides
  # avoiding an unnecessary network listener, this permits MPD to queue local
  # NAS file URIs before its initial full-library scan has completed.
  services.mpd.settings.bind_to_address = lib.mkForce "/run/mpd/socket";

  home-manager.users.budchris = { lib, ... }: {
    xdg.configFile."rmpc/config.ron".text = lib.mkForce ''
      #![enable(implicit_some)]
      (
          address: "/run/mpd/socket",
      )
    '';
  };

  # Change this only after reading the NixOS release notes.
  system.stateVersion = "25.11";
}
