{ config, lib, pkgs, ... }:

let
  tcpEndpoint = builtins.match "([^:]+):([0-9]+)" config.custom.mpdAddress;
in
{
  imports = [ ./tmux.nix ./host-settings.nix ];

  # The shuffle script supports TCP; do not export a Unix socket as a TCP host.
  home.sessionVariables = lib.optionalAttrs (tcpEndpoint != null) {
    MPD_HOST = builtins.elemAt tcpEndpoint 0;
    MPD_PORT = builtins.elemAt tcpEndpoint 1;
  };

  home.packages = with pkgs; [
    # System monitoring & navigation
    btop
    htop
    fastfetch
    nnn
    mc
    tmux

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
    cowsay
    cmatrix

    # Language servers & development support
    openssl
    gcc
  ] ++ lib.optionals pkgs.stdenv.hostPlatform.isLinux [
    pkgs.openssh
    pkgs.wl-clipboard
  ];

  # rmpc talks to the MPD server on alpha (the audio system).
  xdg.configFile."rmpc/theme.ron".source = ./rmpc-theme.ron;
  xdg.configFile."rmpc/config.ron".text = ''
    #![enable(implicit_some)]
    (
        address: ${builtins.toJSON config.custom.mpdAddress},
        theme: "${config.xdg.configHome}/rmpc/theme.ron",
    )
  '';

  programs.fzf = {
    enable = true;
    enableBashIntegration = true;
    enableZshIntegration = true;
  };

  programs.zoxide = {
    enable = true;
    enableBashIntegration = true;
    enableZshIntegration = true;
    options = [ "--cmd" "cd" ];
  };

  programs.mise = {
    enable = true;
    enableBashIntegration = true;
    enableZshIntegration = true;
  };

  programs.eza = {
    enable = true;
    enableBashIntegration = true;
    enableZshIntegration = true;
    git = true;
    icons = "auto";
  };

  programs.yazi = {
    enable = true;
    shellWrapperName = "y";
    enableBashIntegration = true;
    enableZshIntegration = true;

    # Declarative equivalent of `ya pkg add yazi-rs/plugins:mount`.
    plugins.mount = pkgs.yaziPlugins.mount;
    extraPackages = lib.optionals pkgs.stdenv.hostPlatform.isLinux [
      pkgs.udisks
      pkgs.util-linux
      pkgs.ripdrag
    ];
    keymap.mgr.prepend_keymap = [
      {
        on = "M";
        run = "plugin mount";
        desc = "Mount, unmount, or eject drives";
      }
    ] ++ lib.optionals pkgs.stdenv.hostPlatform.isLinux [
      {
        on = "<C-d>";
        run = "shell --orphan -- ${lib.getExe pkgs.ripdrag} -x -- %s";
        desc = "Drag selected files out of Yazi";
      }
    ];
  };

}
