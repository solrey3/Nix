{ osConfig ? null, pkgs, ... }:

let
  terminalFont = "JetBrainsMono Nerd Font Mono";
  ghosttyFontSize = if osConfig != null && osConfig.networking.hostName == "quebec" then 12 else 9;
in
{
  home.sessionVariables = {
    TERMINAL = "ghostty";
    # Keep terminal launchers from using a stale SHELL value from an old session.
    SHELL = "/run/current-system/sw/bin/bash";
  };

  home.packages = with pkgs; [
    alacritty
    ghostty
    ghostty.terminfo
    xdg-terminal-exec
  ];

  # Put Ghostty's terminfo in ncurses' default per-user lookup path too.
  # This keeps tmux working even in shells that do not have Home Manager's
  # TERMINFO/TERMINFO_DIRS session variables loaded yet.
  home.file.".terminfo/x/xterm-ghostty".source = "${pkgs.ghostty.terminfo}/share/terminfo/x/xterm-ghostty";

  # Used by xdg-terminal-exec. The first available terminal is preferred.
  xdg.configFile."xdg-terminals.list".text = ''
    com.mitchellh.ghostty.desktop
    org.alacritty.Alacritty.desktop
  '';

  # Used by COSMIC's Default Apps settings for the terminal category.
  xdg.configFile."cosmic/com.system76.CosmicSettings.Shortcuts/v1/system_actions".text = ''
    {
      Terminal: "${pkgs.ghostty}/bin/ghostty",
    }
  '';

  xdg.mimeApps = {
    enable = true;
    defaultApplications = {
      "application/x-terminal-emulator" = [ "com.mitchellh.ghostty.desktop" ];
      "x-scheme-handler/terminal" = [ "com.mitchellh.ghostty.desktop" ];
    };
  };

  xdg.configFile."ghostty/config".text = ''
    theme = dark:Tokyo Night Dark,light:Tokyo Night Light
    font-family = ${terminalFont}
    font-size = ${toString ghosttyFontSize}
    # Slight transparency keeps text readable while letting the wallpaper show.
    background-opacity = 0.80
    gtk-titlebar = false
    confirm-close-surface = false
    # Use a widely available TERM so tmux also works on remote hosts that do
    # not have Ghostty's xterm-ghostty terminfo installed.
    term = xterm-256color
    command = /run/current-system/sw/bin/bash
  '';

  xdg.configFile."foot/foot.ini".text = ''
    font=${terminalFont}:size=11
  '';

  xdg.configFile."alacritty/alacritty.toml".text = ''
    [general]
    live_config_reload = true
    import = [ "/home/budchris/.cache/tokyo-night/alacritty.toml" ]

    [window]
    dynamic_title = true

    [terminal.shell]
    program = "/run/current-system/sw/bin/bash"

    [font]
    size = 11.0

    [font.normal]
    family = "${terminalFont}"
    style = "Regular"

    [font.bold]
    family = "${terminalFont}"
    style = "Bold"

    [font.italic]
    family = "${terminalFont}"
    style = "Italic"

    [font.bold_italic]
    family = "${terminalFont}"
    style = "Bold Italic"
  '';
}
