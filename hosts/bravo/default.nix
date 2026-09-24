{ config, hostname, lib, pkgs, ... }:

{
  imports = [
    ./hardware-configuration.nix
    ../../modules/nixos/1password.nix
    ../../modules/nixos/desktop.nix
    ../../modules/nixos/docker.nix
    ../../modules/nixos/jellyfin.nix
    ../../modules/nixos/navidrome.nix
    ../../modules/nixos/users/budchris.nix
    ../../modules/nixos/vpn.nix
  ];

  networking.hostName = hostname;

  boot.loader.systemd-boot.enable = true;
  boot.loader.efi.canTouchEfiVariables = true;

  # ASUS TUF X570-PLUS GAMING (Wi-Fi) desktop support.
  hardware.enableRedistributableFirmware = true;
  hardware.bluetooth = {
    enable = true;
    powerOnBoot = true;
  };
  services.fwupd.enable = true;
  services.fstrim.enable = true;

  fileSystems."/mnt/files1" = {
    device = "/dev/disk/by-uuid/7a94cb85-8e89-4192-91f4-e5aa93ac9757";
    fsType = "auto";
    options = [ "nofail" "x-systemd.device-timeout=10s" ];
  };

  fileSystems."/mnt/files2" = {
    device = "/dev/disk/by-uuid/26B66CBAB66C8BDD";
    fsType = "auto";
    options = [ "nofail" "x-systemd.device-timeout=10s" ];
  };

  fileSystems."/mnt/archive" = {
    device = "/dev/disk/by-uuid/7AFA-F0B4";
    fsType = "exfat";
    options = [
      "nofail"
      "x-systemd.device-timeout=10s"
      "uid=budchris"
      "gid=users"
      "umask=022"
    ];
  };

  # NVIDIA GeForce RTX 3070.
  services.xserver.videoDrivers = [ "nvidia" ];
  hardware.graphics.enable = true;
  hardware.nvidia = {
    modesetting.enable = true;
    powerManagement.enable = true;
    nvidiaSettings = true;
    open = false;
    package = config.boot.kernelPackages.nvidiaPackages.stable;
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
    synology-drive-client
  ];

  home-manager.users.budchris = { pkgs, ... }:
    let
      synologyRoot = "${pkgs.synology-drive-client}/opt/Synology/SynologyDrive";
      synologyDriveLauncher = pkgs.writeShellScript "synology-drive-launcher" ''
        runtime="$HOME/.SynologyDrive/SynologyDrive.app"
        source_marker="$runtime/.nix-source"

        if ! ${pkgs.gnugrep}/bin/grep -Fqx ${lib.escapeShellArg synologyRoot} "$source_marker" 2>/dev/null; then
          ${pkgs.coreutils}/bin/rm -rf "$runtime"
          ${pkgs.coreutils}/bin/mkdir -p "$HOME/.SynologyDrive"
          ${pkgs.coreutils}/bin/cp -a ${lib.escapeShellArg "${synologyRoot}/package/cloudstation"} "$runtime"
          ${pkgs.coreutils}/bin/chmod -R u+w "$runtime"
          ${pkgs.coreutils}/bin/printf '%s\n' ${lib.escapeShellArg synologyRoot} > "$source_marker"
        fi

        ${pkgs.coreutils}/bin/rm -f "$HOME/.SynologyDrive/ui.pid"
        export LD_LIBRARY_PATH=${lib.escapeShellArg "${synologyRoot}/lib"}
        export QT_QPA_PLATFORM=xcb
        unset QT_PLUGIN_PATH
        exec "$runtime/bin/cloud-drive-ui"
      '';
    in
    {
      xdg.configFile."autostart/synology-drive.desktop".text = ''
        [Desktop Entry]
        Type=Application
        Name=Synology Drive Client
        Exec=${synologyDriveLauncher}
        Terminal=false
        X-GNOME-Autostart-enabled=true
      '';
    };

  # Change this only after reading the NixOS release notes.
  system.stateVersion = "25.11";
}
