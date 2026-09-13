{ hostname, inputs, lib, modulesPath, pkgs, ... }:

{
  imports = [
    (modulesPath + "/profiles/qemu-guest.nix")
    inputs.disko.nixosModules.disko
    ./disk-config.nix
    ../../modules/nixos/users/budchris.nix
    ../../modules/nixos/tailscale.nix
  ];

  networking = {
    hostName = hostname;
    networkmanager.enable = lib.mkForce false;
    useDHCP = false;
    useNetworkd = true;
  };

  # DigitalOcean provisioned this droplet with static public, anchor, and VPC
  # addresses. DHCP is not available on either virtio interface.
  systemd.network = {
    enable = true;
    networks = {
      "10-public" = {
        matchConfig.MACAddress = "a6:e3:09:93:83:67";
        address = [
          "143.198.8.152/20"
          "10.17.0.6/16"
        ];
        routes = [
          {
            Destination = "0.0.0.0/0";
            Gateway = "143.198.0.1";
          }
        ];
        linkConfig.RequiredForOnline = "routable";
      };
      "20-vpc" = {
        matchConfig.MACAddress = "32:49:f0:8e:a2:ea";
        address = [ "10.108.0.3/20" ];
        dns = [ "10.108.15.254" ];
        domains = [ "~." ];
        linkConfig.RequiredForOnline = "routable";
      };
    };
  };

  services = {
    resolved.enable = true;
    avahi.enable = lib.mkForce false;
  };

  users.users.budchris.openssh.authorizedKeys.keys = [
    "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAILluiwZ/efnUYTmrf0lci6jIeQwYK7RbgcxGUIthlJYe tango-install"
  ];

  boot = {
    initrd.availableKernelModules = [
      "ata_piix"
      "uhci_hcd"
      "virtio_pci"
      "virtio_scsi"
      "virtio_blk"
      "virtio_net"
    ];
    # Disko contributes /dev/vda to GRUB's mirrored boot device list.
    loader.grub.enable = true;
  };

  services.qemuGuest.enable = true;
  services.fstrim.enable = true;

  environment.systemPackages = with pkgs; [
    fastfetch
    git
    jq
    inputs.deploy-rs.packages.${pkgs.system}.default
    tmux
  ];

  system.stateVersion = "25.11";
}
