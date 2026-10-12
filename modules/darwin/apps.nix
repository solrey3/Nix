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
    brews = [
      "curl"
      "navidrome"
      "neovim"
      "node"
      "wget"
      "yarn"
    ];
    casks = [
      "1password"
      "aerospace"
      "alacritty"
      "anki"
      "brave-browser"
      "discord"
      "ghostty"
      "google-chrome"
      "ledger-live"
      "ledger-wallet"
      "librewolf"
      "mixxx"
      "musicbrainz-picard"
      "nextcloud"
      "obsidian"
      "protonvpn"
      "raspberry-pi-imager"
      "raycast"
      "signal"
      "soulseek"
      "steam"
      "synology-drive"
      "telegram"
      "transmission"
      "vscodium"
      "vlc"
      "wezterm"
      "whatsapp"
      "zen"
    ];
  };
}
