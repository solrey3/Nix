{ hostname, lib, pkgs, ... }:

{
  # Tango is a headless deployment console; keep browsers, compositors, GUI
  # applications, fonts, and wallpapers out of its user environment.
  home-manager.users.budchris =
    if hostname == "tango" then
      {
        imports = [ ../../home/budchris/portable.nix ];
        home = {
          username = "budchris";
          homeDirectory = "/home/budchris";
          stateVersion = "25.11";
        };
      }
    else
      import ../../home/budchris;

  security.sudo.wheelNeedsPassword = false;

  users.users.budchris = {
    isNormalUser = true;
    description = "Buddha Christ";
    extraGroups = [ "docker" "networkmanager" "wheel" ];
    shell = pkgs.bashInteractive;
    openssh.authorizedKeys.keys = [
      "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIGE9cz0z+9ynqZREVYHDCcj68gbpJLZ3TbXNzLRPQrvV sancho@panza"
      "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIDo0tT2bX049ZCRXwWBJAca2PzfSRAd4magQU/6yZMQA budchris@quebec"
      "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIFdNJeN48PBRxNZL85RhQxTLLyDMVWwPf6RGqA4x5egf budchris@oscar"
      "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIEwLrjfTnFp1loaFmLE3v15E1ae9izzWMxpRktYvAqqb budchris@bravo"
      "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIIoDM7eW9Bq407BN4ZtYMy3CZq0BWqKyEh7GAy6/ydde pi-console@tango"
      "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIJVzu8in7Il2n2bVoSKT8OoG+f2ecKtvOZOprTCdQKiQ budchris@tango"
    ];
    packages = lib.optionals (hostname != "tango") [
      pkgs.kdePackages.kate
    ];
  };
}
