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
    device = "/dev/disk/by-uuid/3467e001-48ce-4c85-a535-3f5da6985392";
    fsType = "ext4";
    options = [ "nofail" "x-systemd.device-timeout=10s" ];
  };

  fileSystems."/mnt/archive" = {
    device = "/dev/disk/by-uuid/7AFA-F0B4";
    fsType = "exfat";
    options = [
      "nofail"
      "x-systemd.device-timeout=10s"
      "uid=${config.custom.fleet.primaryUser}"
      "gid=users"
      "umask=022"
    ];
  };

  # Export the master library read-only to alpha; alpha mounts it directly.
  services.nfs.server = {
    enable = true;
    exports = ''
      /mnt/files2/Jukebox 192.168.1.165(ro,fsid=0,sync,no_subtree_check,all_squash,anonuid=1000,anongid=100) 192.168.1.207(ro,fsid=0,sync,no_subtree_check,all_squash,anonuid=1000,anongid=100)
    '';
  };
  networking.firewall.allowedTCPPorts = [ 2049 ];
  systemd.services.nfs-server = {
    after = [ "mnt-files2.mount" ];
    requires = [ "mnt-files2.mount" ];
  };

  # Serve the master Jukebox library and play through the desktop user's
  # PipeWire session. Using the Jukebox root keeps the existing ../Music paths
  # in the sibling Playlists directory valid in MPD.
  services.mpd = {
    enable = true;
    openFirewall = true;
    user = "budchris";
    settings = {
      music_directory = "/mnt/files2/Jukebox";
      playlist_directory = "/mnt/files2/Jukebox/Playlists";
      bind_to_address = "any";
      port = 6600;
      audio_output = [
        {
          type = "pipewire";
          name = "PipeWire";
        }
      ];
      auto_update = "yes";
      zeroconf_enabled = "no";
      follow_outside_symlinks = "yes";
      follow_inside_symlinks = "yes";
    };
  };

  systemd.services.mpd = {
    after = [ "mnt-files2.mount" ];
    requires = [ "mnt-files2.mount" ];
    environment.XDG_RUNTIME_DIR = "/run/user/1000";
    serviceConfig = {
      SupplementaryGroups = [ "audio" ];
      # The first startup builds a database for the full Jukebox library.
      TimeoutStartSec = "30min";
    };
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
    defaultSession = "hyprland";
    environments = {
      cosmic = true;
      hyprland = true;
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
    strawberry
    synology-drive-client
  ];

  home-manager.users.${config.custom.fleet.primaryUser} = { pkgs, ... }:
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
      custom.desktopPolicy = {
        gtkScale = "1.5";
        restartSynology = true;
      };
      xdg.configFile."autostart/synology-drive.desktop".text = ''
        [Desktop Entry]
        Type=Application
        Name=Synology Drive Client
        Exec=${synologyDriveLauncher}
        Terminal=false
        X-GNOME-Autostart-enabled=true
      '';

      # Bravo uses its local MPD instance by default.
      xdg.configFile."rmpc/config.ron".text = lib.mkForce ''
        #![enable(implicit_some)]
        (
            address: "127.0.0.1:6600",
        )
      '';
    };

  # Change this only after reading the NixOS release notes.
  system.stateVersion = "25.11";
}
