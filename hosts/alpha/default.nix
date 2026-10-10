{ config, hostname, pkgs, ... }:

{
  imports = [
    ./hardware-configuration.nix
    ../../modules/nixos/docker.nix
    ../../modules/nixos/mpd.nix
    ../../modules/nixos/nvidia-legacy_470.nix
    ../../modules/nixos/users/budchris.nix
    ../../modules/nixos/xfce4.nix
  ];

  networking.hostName = hostname;

  boot.loader.systemd-boot.enable = true;
  boot.loader.efi.canTouchEfiVariables = true;

  hardware.enableRedistributableFirmware = true;
  hardware.bluetooth = {
    enable = true;
    powerOnBoot = true;
  };
  services.fwupd.enable = true;
  services.fstrim.enable = true;

  # Alpha is an appliance music player: log straight into the desktop so
  # PipeWire/WirePlumber are always available for MPD's audio output.
  services.displayManager.autoLogin = {
    enable = true;
    user = config.custom.fleet.primaryUser;
  };

  # Alpha is an always-on music PC: never suspend/hibernate/idle-sleep,
  # because HDMI/desktop audio drops when the machine or display goes to sleep.
  powerManagement.enable = false;

  systemd.targets = {
    sleep.enable = false;
    suspend.enable = false;
    hibernate.enable = false;
    hybrid-sleep.enable = false;
  };

  systemd.sleep.settings.Sleep = {
    AllowSuspend = false;
    AllowHibernation = false;
    AllowHybridSleep = false;
    AllowSuspendThenHibernate = false;
  };

  services.logind.settings.Login = {
    HandleLidSwitch = "ignore";
    HandleLidSwitchExternalPower = "ignore";
    HandleLidSwitchDocked = "ignore";
    IdleAction = "ignore";
    IdleActionSec = "infinity";
  };

  # Disable X11 screen blanking/DPMS at the X server and display-manager levels
  # too. i3 also enforces this after login in hosts/alpha/config/i3/config.
  services.xserver.serverFlagsSection = ''
    Option "BlankTime" "0"
    Option "StandbyTime" "0"
    Option "SuspendTime" "0"
    Option "OffTime" "0"
  '';

  services.xserver.displayManager.setupCommands = ''
    ${pkgs.xset}/bin/xset s off -dpms s noblank || true
  '';

  # Keep PipeWire/WirePlumber from suspending idle audio nodes,
  # which can cut off music playback when the screen blanks.
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

  services.tailscale = {
    enable = true;
    useRoutingFeatures = "client";
  };

  networking.firewall = {
    allowedUDPPorts = [ 41641 ];
    trustedInterfaces = [ "tailscale0" ];
    checkReversePath = "loose";
  };

  environment.systemPackages = with pkgs; [
    pavucontrol
    tailscale
  ];

  # Alpha-specific home-manager settings (shared config lives in
  # modules/home/budchris).
  home-manager.users.${config.custom.fleet.primaryUser} = { ... }: {
    # Manage the i3 config declaratively (Super is the modifier).
    xdg.configFile."i3/config".source = ./config/i3/config;

    # xfce4-power-manager is pulled in by the XFCE desktop module and can be
    # autostarted by dex in the i3 session. Override it so it cannot re-enable
    # display sleep/suspend policies behind MPD's back.
    xdg.configFile."autostart/xfce4-power-manager.desktop".text = ''
      [Desktop Entry]
      Type=Application
      Name=Power Manager
      Hidden=true
    '';
  };

  # Change this only after reading the NixOS release notes.
  system.stateVersion = "24.05";
}
