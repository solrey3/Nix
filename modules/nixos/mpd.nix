{ config, lib, pkgs, utils, ... }:

let
  nas = config.custom.fleet.nas;
  mount = "${nas.mountRoot}/Jukebox";
  audioUser = config.custom.fleet.primaryUser;
in
{
  # Music Player Daemon serving the Jukebox share from the NAS (illmatic).
  # Clients (e.g. rmpc) connect on port 6600 over LAN/Tailscale.

  boot.supportedFilesystems = [ "nfs" ];
  fileSystems.${mount} = {
    # Use the LAN address: the NAS export permits 192.168.1.0/24, while
    # Tailscale MagicDNS resolves bare "illmatic" to an unpermitted 100.x IP.
    device = "${nas.lanHost}:${nas.exportRoot}/Jukebox";
    fsType = "nfs";
    # No idle-timeout: unmounting/remounting mid-playback caused stalls.
    options = [ "_netdev" "nofail" "x-systemd.automount" ];
  };

  services.mpd = {
    enable = true;
    openFirewall = true;
    # The NAS export squashes non-root callers to a user with no read
    # permission, so MPD must run as root to scan the library. Root can
    # still reach the desktop user's PipeWire socket (see below).
    user = "root";
    settings = {
      music_directory = "${mount}/Music";
      playlist_directory = "${mount}/Playlists";
      bind_to_address = "any";
      port = 6600;
      audio_output = [
        {
          type = "pipewire";
          name = "PipeWire";
        }
      ];
      # inotify doesn't work over NFS anyway, and watching the whole tree
      # slowed the initial scan to a crawl. Run "mpc update" (or send an
      # update from rmpc) after adding music to the NAS.
      auto_update = "no";
      zeroconf_enabled = "no";
      # Large buffer to ride out NFS latency spikes (audible dropouts
      # otherwise: "Hit end of (available) data during resync").
      audio_buffer_size = 32768; # KiB
      buffer_before_play = "25%";
      follow_outside_symlinks = "yes";
      follow_inside_symlinks = "yes";
    };
  };

  # Resolve the account's assigned UID at runtime; NixOS may allocate it.
  systemd.services.mpd-audio-runtime = {
    requiredBy = [ "mpd.service" ];
    before = [ "mpd.service" ];
    after = [ "systemd-user-sessions.service" ];
    serviceConfig = {
      Type = "oneshot";
      RuntimeDirectory = "mpd-audio";
      RemainAfterExit = true;
    };
    script = ''
      uid="$(${pkgs.coreutils}/bin/id -u ${lib.escapeShellArg audioUser})"
      printf 'XDG_RUNTIME_DIR=/run/user/%s\n' "$uid" > /run/mpd-audio/environment
    '';
  };

  systemd.services.mpd = {
    after = [ "${utils.escapeSystemdPath mount}.automount" ];
    serviceConfig = {
      EnvironmentFile = "/run/mpd-audio/environment";
      SupplementaryGroups = [ "audio" "pipewire" ];
      # The first run scans the whole Jukebox share over NFS, which can
      # take a long time; don't let systemd kill it mid-scan.
      TimeoutStartSec = "30min";
    };
  };
}
