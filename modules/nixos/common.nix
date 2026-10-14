{ pkgs, ... }:

{
  imports = [
    ./nix.nix
    ./fleet.nix
  ];

  time.timeZone = "America/New_York";
  i18n.defaultLocale = "en_US.UTF-8";

  console.keyMap = "us";

  networking.networkmanager.enable = true;

  # Resolve <hostname>.local on the LAN via mDNS.
  services.avahi = {
    enable = true;
    nssmdns4 = true;
    publish = {
      enable = true;
      addresses = true;
    };
  };

  services.openssh = {
    enable = true;
    settings = {
      PasswordAuthentication = false;
      PermitRootLogin = "no";
    };
  };

  environment.systemPackages = with pkgs; [
    curl
    git
    ghostty.terminfo
    vim
    wget
  ];
}
