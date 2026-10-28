# Evaluation-only dependency isolation test. Poison every package/fleet input;
# selecting the dedicated data output must not force any of them.
let
  poison = throw "public playback artifact forced an unrelated flake input";
  output = (import ../flake.nix).outputs {
    self.rev = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
    nixpkgs = poison;
    home-manager = poison;
    darwin = poison;
    deploy-rs = poison;
  };
  artifact = output.jukeboxConfigurations.bravo;
in
assert !(artifact ? drvPath);
assert artifact.manifest.schema == 1;
assert artifact.manifest.sourceRevision == "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
assert builtins.length artifact.manifest.files == 2;
assert builtins.all (f: f.size > 0 && f.size <= 4096) artifact.manifest.files;
{
  inherit (artifact) manifest manifestFile;
  isolatedFromPackageInputs = true;
}
