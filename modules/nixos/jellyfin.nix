{ ... }:

{
  services.jellyfin = {
    enable = true;
    openFirewall = true;

    # Use the NVIDIA GPU for transcoding on bravo.
    hardwareAcceleration = {
      enable = true;
      type = "nvenc";
      device = "/dev/dri/renderD128";
    };

    # Seed Jellyfin's encoding.xml from this NixOS config on service start.
    forceEncodingConfig = true;
    transcoding = {
      enableHardwareEncoding = true;
      hardwareDecodingCodecs = {
        h264 = true;
        hevc = true;
        hevc10bit = true;
        mpeg2 = true;
        vc1 = true;
        vp8 = true;
        vp9 = true;
      };
      hardwareEncodingCodecs.hevc = true;
    };
  };

  # Let Jellyfin access GPU render/video devices for hardware transcoding.
  users.users.jellyfin.extraGroups = [ "video" "render" ];

  # The media libraries live on mounted data drives; /mnt/archive is backup-only.
  systemd.services.jellyfin = {
    after = [ "mnt-files1.mount" "mnt-files2.mount" ];
    requires = [ "mnt-files1.mount" "mnt-files2.mount" ];
    serviceConfig.DeviceAllow = [
      "/dev/nvidia0 rw"
      "/dev/nvidiactl rw"
      "/dev/nvidia-modeset rw"
      "/dev/nvidia-uvm rw"
      "/dev/nvidia-uvm-tools rw"
    ];
  };
}
