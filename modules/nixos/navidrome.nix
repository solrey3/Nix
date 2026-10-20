{ ... }:

{
  services.navidrome = {
    enable = true;
    openFirewall = true;
    settings = {
      Address = "0.0.0.0";
      Port = 4533;

      # Use the master Jukebox root so Navidrome can import playlists from
      # Playlists/ while resolving their ../Music/... entries.
      MusicFolder = "/mnt/files2/Jukebox";
      AutoImportPlaylists = true;
      PlaylistsPath = "Playlists/**";

      EnableInsightsCollector = false;
    };
  };

  # Navidrome reads from the master Jukebox library.
  systemd.services.navidrome = {
    after = [ "mnt-files2.mount" ];
    requires = [ "mnt-files2.mount" ];
  };
}
