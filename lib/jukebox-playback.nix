# No nixpkgs, Home Manager, derivation or executable dependency.
{ sourceRevision ? null, lockFile, payloadDirectory }:
let
  names = [ "90-playback.conf" "playback.env" ];
  entries = builtins.readDir payloadDirectory;
  env = builtins.readFile (payloadDirectory + "/playback.env");
  dropin = builtins.readFile (payloadDirectory + "/90-playback.conf");
  envMatch = builtins.match "MPD_ZONES='([^']*)'\nNAVIDROME_URL=\n" env;
  filesDirectory = builtins.path { path = payloadDirectory; name = "bravo-jukebox-playback-files"; };
  text = {
    "playback.env" = env;
    "90-playback.conf" = dropin;
  };
  targets = {
    "playback.env" = ".config/jukebox/playback.env";
    "90-playback.conf" = ".config/systemd/user/jukebox-manager.service.d/90-playback.conf";
  };
  manifest = {
    schema = 1;
    publisherSchema = 1;
    role = "bravo";
    account = "budchris";
    configHome = ".config";
    inherit sourceRevision filesDirectory;
    lockSha256 = builtins.hashString "sha256" (builtins.readFile lockFile);
    files = map (name: {
      inherit name;
      target = targets.${name};
      sha256 = builtins.hashString "sha256" text.${name};
      size = builtins.stringLength text.${name};
    }) names;
  };
in
assert builtins.attrNames entries == names;
assert builtins.all (name: entries.${name} == "regular") names;
assert envMatch != null;
assert builtins.fromJSON (builtins.head envMatch) == { bravo = { host = "127.0.0.1"; port = 6600; musicPrefix = "Music/"; }; };
assert dropin == "[Service]\nEnvironmentFile=%h/.config/jukebox/playback.env\n";
assert builtins.all (name: builtins.stringLength text.${name} <= 4096) names;
assert sourceRevision == null || builtins.match "[0-9a-f]{40}" sourceRevision != null;
{
  inherit manifest;
  # toJSON preserves filesDirectory's store context: this file roots the payload.
  manifestFile = builtins.toFile "bravo-jukebox-playback-manifest.json" (builtins.toJSON manifest);
}
