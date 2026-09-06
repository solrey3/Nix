{ config, lib, pkgs, ... }:

let
  cfg = config.custom.desktop;
in
{
  imports = [ ./firefox.nix ];

  options.custom.desktop = {
    enable = lib.mkEnableOption "desktop environments" // {
      default = true;
    };

    defaultSession = lib.mkOption {
      type = lib.types.str;
      default = "plasma";
      description = "Default session selected by the display manager.";
    };

    environments = {
      plasma = lib.mkEnableOption "KDE Plasma 6" // { default = true; };
      cosmic = lib.mkEnableOption "COSMIC";
      hyprland = lib.mkEnableOption "Hyprland";
      sway = lib.mkEnableOption "Sway";
    };
  };

  config = lib.mkIf cfg.enable {
    services.xserver.enable = true;

    services.displayManager.sddm = {
      enable = true;
      wayland.enable = true;
    };

    services.displayManager.defaultSession = cfg.defaultSession;

    # Unlock secret stores during graphical login so GNOME/libsecret apps,
    # KDE apps, Proton VPN, browsers, etc. do not show keyring prompts.
    services.gnome.gnome-keyring.enable = true;
    # 1Password remains the vault/optional SSH agent. Disable GCR's SSH agent
    # so it cannot replace the selected SSH_AUTH_SOCK. Plasma-capable systems
    # still unlock KWallet through PAM for native KDE clients, while Electron
    # and non-KDE sessions consistently use the libsecret API.
    services.gnome.gcr-ssh-agent.enable = false;
    environment.systemPackages = with pkgs; [
      nextcloud-client
      obsidian
      seahorse
    ];
    security.pam.services = {
      login.enableGnomeKeyring = true;
      sddm.enableGnomeKeyring = true;
      # Keep the Plasma wallet unlocked for native KDE clients. Disabling PAM
      # here leaves an existing wallet locked and causes prompts after login.
      sddm.kwallet.enable = lib.mkIf cfg.environments.plasma true;
    };

    services.desktopManager.plasma6.enable = cfg.environments.plasma;

    services.desktopManager.cosmic.enable = cfg.environments.cosmic;

    programs.hyprland = lib.mkIf cfg.environments.hyprland {
      enable = true;
      # Quebec may retain graphical-session.target after switching from Sway,
      # which makes UWSM refuse to launch Hyprland. Use the direct SDDM session.
      withUWSM = false;
    };

    programs.sway = lib.mkIf cfg.environments.sway {
      enable = true;
      wrapperFeatures.gtk = true;
      extraPackages = with pkgs; [
        foot
        grim
        slurp
        wmenu
        brightnessctl
        swaybg
        swayidle
        swaylock
        waybar
        wl-clipboard
      ];
    };

    services.xserver.xkb = {
      layout = "us";
      variant = "";
    };

    services.printing.enable = true;

    security.rtkit.enable = true;
    services.pulseaudio.enable = false;
    services.pipewire = {
      enable = true;
      alsa.enable = true;
      alsa.support32Bit = true;
      pulse.enable = true;
    };

    xdg.portal.enable = true;

    programs.steam = {
      enable = true;
      remotePlay.openFirewall = true;
      dedicatedServer.openFirewall = true;
    };
  };
}
