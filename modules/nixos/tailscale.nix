{ config, pkgs, ... }:

{
  services.tailscale = {
    enable = true;
    useRoutingFeatures = "client";
  };

  environment.systemPackages = [ pkgs.tailscale ];

  networking.firewall = {
    allowedUDPPorts = [ config.services.tailscale.port ];
    trustedInterfaces = [ config.services.tailscale.interfaceName ];
    checkReversePath = "loose";
  };
}
