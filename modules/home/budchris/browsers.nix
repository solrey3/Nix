{ pkgs, ... }:

let
  googleChromeWork = pkgs.writeShellScriptBin "google-chrome-work" ''
    exec ${pkgs.google-chrome}/bin/google-chrome-stable \
      --user-data-dir="$HOME/.config/google-chrome-work" \
      --class=google-chrome-work \
      --name="Google Chrome Work" \
      "$@"
  '';
in
{
  home.packages = [
    googleChromeWork
  ];

  # Keep Firefox as the personal/default browser while retaining the separate
  # Chrome launcher for work-only browsing.
  xdg.mimeApps = {
    enable = true;
    defaultApplications = {
      "text/html" = [ "firefox.desktop" ];
      "application/xhtml+xml" = [ "firefox.desktop" ];
      "x-scheme-handler/http" = [ "firefox.desktop" ];
      "x-scheme-handler/https" = [ "firefox.desktop" ];
    };
  };

  xdg.desktopEntries.google-chrome-work = {
    name = "Google Chrome (Work)";
    genericName = "Work Web Browser";
    comment = "Google Chrome with a dedicated work-only profile";
    exec = "google-chrome-work %U";
    icon = "${pkgs.google-chrome}/share/icons/hicolor/256x256/apps/google-chrome.png";
    terminal = false;
    categories = [ "Network" "WebBrowser" ];
    mimeType = [
      "text/html"
      "text/xml"
      "application/xhtml+xml"
      "application/xml"
      "application/rss+xml"
      "application/rdf+xml"
      "image/gif"
      "image/jpeg"
      "image/png"
      "x-scheme-handler/http"
      "x-scheme-handler/https"
    ];
    settings.StartupWMClass = "google-chrome-work";
  };
}
