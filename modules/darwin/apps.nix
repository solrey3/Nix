{ pkgs, ... }:

{
  environment.systemPackages = with pkgs; [
    fastfetch
    git
    just
    vim
  ];

  # Homebrew itself must be installed once outside Nix. nix-darwin then keeps
  # the workstation applications aligned on delta and juliet.
  homebrew = {
    enable = true;
    onActivation = {
      autoUpdate = false;
      cleanup = "zap";
    };
    taps = [ "homebrew/services" ];
    brews = [ "node" "wget" ];
    casks = [
      "1password"
      "alacritty"
      "brave-browser"
      "ghostty"
      "google-chrome"
      "nextcloud"
      "obsidian"
      "protonvpn"
      "signal"
      "synology-drive"
      "vscodium"
      "vlc"
      "wezterm"
    ];
  };
}
