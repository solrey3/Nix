{ pkgs, ... }:

{
  imports = [ ./tmux.nix ];

  home.packages = with pkgs; [
    # System monitoring & navigation
    btop
    htop
    fastfetch
    yazi
    nnn
    mc
    tmux
    wl-clipboard

    # Search & navigation
    fzf
    fd
    ripgrep
    zoxide
    eza
    tree

    # Command line tools
    curl
    wget
    yt-dlp
    ffmpeg
    jq
    just
    util-linux # uuidgen
    stow
    lynx
    speedtest-cli
    openssh
    tokei
    dysk

    # GNU utilities
    gnutar
    gnused
    gawk

    # Archive & file tools
    unzip
    zip
    p7zip
    rsync

    # Music
    rmpc # MPD client (connects to alpha.local:6600)

    # Fun terminal tools
    figlet
    fortune
    cowsay
    cmatrix

    # Language servers & development support
    openssl
    gcc
  ];

  # rmpc talks to the MPD server on alpha (the audio system).
  xdg.configFile."rmpc/config.ron".text = ''
    #![enable(implicit_some)]
    (
        address: "alpha.local:6600",
    )
  '';

  programs.fzf = {
    enable = true;
    enableBashIntegration = true;
    enableZshIntegration = false;
  };

  programs.zoxide = {
    enable = true;
    enableBashIntegration = true;
    enableZshIntegration = false;
    options = [ "--cmd" "cd" ];
  };

  programs.mise = {
    enable = true;
    enableBashIntegration = true;
    enableZshIntegration = false;
  };

  programs.eza = {
    enable = true;
    enableBashIntegration = true;
    enableZshIntegration = false;
    git = true;
    icons = "auto";
  };

  programs.yazi = {
    enable = true;
    shellWrapperName = "y";
    enableBashIntegration = true;
    enableZshIntegration = false;
  };

}
