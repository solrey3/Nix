{ lib
, stdenv
, fetchurl
, autoPatchelfHook
, wrapGAppsHook4
, gtk4
, libadwaita
, libGL
, libepoxy
, fontconfig
, libxkbcommon
, gtk4-layer-shell
, wayland
}:

let
  sources = {
    x86_64-linux = {
      arch = "x86_64";
      hash = "sha256-bEX8MGES1ZDCvmJl1WPn1lfiptyF28OTCl2NHHs5zF0=";
    };
    aarch64-linux = {
      arch = "aarch64";
      hash = "sha256-J5qzrEFu1NGsoxqm9mPB9K9mfZ+I3J696Ye8bN9HZOg=";
    };
  };
  source = sources.${stdenv.hostPlatform.system};
in
stdenv.mkDerivation (finalAttrs: {
  pname = "tensaku";
  version = "0.28.0";

  src = fetchurl {
    url = "https://github.com/jondkinney/tensaku/releases/download/v${finalAttrs.version}/tensaku-v${finalAttrs.version}-${source.arch}.tar.gz";
    inherit (source) hash;
  };

  nativeBuildInputs = [
    autoPatchelfHook
    wrapGAppsHook4
  ];

  buildInputs = [
    fontconfig
    gtk4
    gtk4-layer-shell
    libadwaita
    libepoxy
    libGL
    libxkbcommon
    wayland
  ];

  sourceRoot = ".";

  installPhase = ''
    runHook preInstall
    mkdir -p "$out"
    cp -r bin share "$out/"
    runHook postInstall
  '';

  meta = {
    description = "Modern Wayland screenshot annotation tool";
    homepage = "https://github.com/jondkinney/tensaku";
    license = lib.licenses.mpl20;
    mainProgram = "tensaku";
    platforms = builtins.attrNames sources;
    sourceProvenance = [ lib.sourceTypes.binaryNativeCode ];
  };
})
