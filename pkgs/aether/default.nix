{ lib
, stdenv
, fetchurl
, dpkg
, autoPatchelfHook
, wrapGAppsHook3
, gtk3
, glib
, webkitgtk_4_1
, libsoup_3
, gtk-layer-shell
, gst_all_1
}:

let
  sources = {
    x86_64-linux = {
      arch = "amd64";
      hash = "sha256-Xcu2k9LMzJ9uIJx2pNW+oAVklyA2diglIDK974Ix78o=";
    };
    aarch64-linux = {
      arch = "arm64";
      hash = "sha256-CzFCTYhenhCX0IeTNT0+QZaLrAfN5d36Y1TeVModlPc=";
    };
  };
  source = sources.${stdenv.hostPlatform.system};
in
stdenv.mkDerivation (finalAttrs: {
  pname = "aether";
  version = "4.29.4";

  src = fetchurl {
    url = "https://github.com/bjarneo/aether/releases/download/v${finalAttrs.version}/aether_${finalAttrs.version}_${source.arch}.deb";
    inherit (source) hash;
  };

  nativeBuildInputs = [
    autoPatchelfHook
    dpkg
    wrapGAppsHook3
  ];

  buildInputs = [
    glib
    gtk3
    gtk-layer-shell
    gst_all_1.gstreamer
    gst_all_1.gst-plugins-base
    gst_all_1.gst-plugins-good
    libsoup_3
    webkitgtk_4_1
  ];

  unpackPhase = ''
    runHook preUnpack
    dpkg-deb -x "$src" .
    runHook postUnpack
  '';

  installPhase = ''
    runHook preInstall
    mkdir -p "$out"
    cp -r usr/* "$out/"
    runHook postInstall
  '';

  meta = {
    description = "Visual wallpaper and desktop theme generator";
    homepage = "https://github.com/bjarneo/aether";
    license = lib.licenses.mit;
    mainProgram = "aether";
    platforms = builtins.attrNames sources;
    sourceProvenance = [ lib.sourceTypes.binaryNativeCode ];
  };
})
