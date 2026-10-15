{ config, hostname, lib, pkgs, ... }:

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

  # Read the master Jukebox on bravo directly; no local copy or NAS sync.
  fileSystems."/mnt/bravo/Jukebox" = {
    device = "192.168.1.4:/";
    fsType = "nfs4";
    options = [ "_netdev" "nofail" "x-systemd.automount" "ro" ];
  };

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

  # Hyprland handles the panel when the lid moves; do not suspend before
  # the external display can take over in clamshell mode.
  services.logind.settings.Login.HandleLidSwitch = "ignore";

  custom.desktop = {
    defaultSession = "hyprland";
    environments = {
      cosmic = true;
      hyprland = true;
    };
  };

  # Goodix 27c6:609c fingerprint reader. fprintd enables fingerprint PAM
  # authentication for SDDM/login. Hyprlock uses fprintd directly so password
  # entry remains usable
  # while it scans in parallel.
  services.fprintd.enable = true;
  programs.hyprlock.enable = true;
  security.pam.services.hyprlock.fprintAuth = false;

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

  # Keep MPD local to Quebec while serving music and playlists from bravo.
  # The Jukebox root resolves playlists' ../Music entries against Music/.
  services.mpd.settings = {
    bind_to_address = lib.mkForce "/run/mpd/socket";
    music_directory = lib.mkForce "/mnt/bravo/Jukebox";
    playlist_directory = lib.mkForce "/mnt/bravo/Jukebox/Playlists";
  };
  systemd.services.mpd.after = lib.mkForce [ "mnt-bravo-Jukebox.automount" ];

  home-manager.users.${config.custom.fleet.primaryUser} = {
    custom.mpdAddress = "/run/mpd/socket";
    custom.desktopPolicy = {
      output = "eDP-1";
      mode = "2880x1920@120";
      scale = 1.5;
      terminalOpacity = "1.0";
    };
  };

  # Change this only after reading the NixOS release notes.
  system.stateVersion = "25.11";
}
