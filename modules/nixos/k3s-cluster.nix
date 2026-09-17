{ config, hostname, lib, pkgs, ... }:

let
  cfg = config.custom.k3sCluster;
  isBootstrap = cfg.role == "bootstrap";
  isServer = cfg.role != "agent";
in
{
  options.custom.k3sCluster = {
    enable = lib.mkEnableOption "the homelab k3s cluster";

    role = lib.mkOption {
      type = lib.types.enum [ "bootstrap" "server" "agent" ];
      description = "Bootstrap the first control-plane node, join another server, or join an agent.";
    };

    serverAddress = lib.mkOption {
      type = lib.types.str;
      default = "https://kilo:6443";
      description = "URL of the bootstrap k3s server over Tailscale MagicDNS.";
    };

    tokenFile = lib.mkOption {
      type = lib.types.path;
      default = "/var/lib/rancher/k3s/cluster-token";
      description = "Out-of-store token file used by joining nodes.";
    };

    deployWorkloads = lib.mkOption {
      type = lib.types.bool;
      default = isBootstrap;
      description = "Install the manifests in kubernetes/homelab.yaml from this server.";
    };
  };

  config = lib.mkIf cfg.enable {
    # Do not let NetworkManager interfere with interfaces managed by flannel.
    networking.networkmanager.unmanaged = [
      "interface-name:cni*"
      "interface-name:flannel*"
      "interface-name:veth*"
    ];

    services.tailscale = {
      enable = true;
      useRoutingFeatures = "client";
    };

    # Resolve the stable address assigned by Tailscale at runtime instead of
    # duplicating host-specific addresses in the repository. K3s uses that
    # address for node advertisement and flannel uses the same interface.
    systemd.services.k3s-tailscale-address = {
      description = "Prepare the Tailscale address for k3s";
      requiredBy = [ "k3s.service" ];
      before = [ "k3s.service" ];
      after = [ "tailscaled.service" ];
      requires = [ "tailscaled.service" ];
      path = [ pkgs.coreutils pkgs.tailscale ];
      serviceConfig = {
        Type = "oneshot";
        RemainAfterExit = true;
        RuntimeDirectory = "k3s-tailnet";
        RuntimeDirectoryMode = "0755";
      };
      script = ''
        set -euo pipefail
        address=""
        for _ in $(seq 1 60); do
          address="$(tailscale ip -4 2>/dev/null | head -n1 || true)"
          [[ -n "$address" ]] && break
          sleep 2
        done
        if [[ -z "$address" ]]; then
          echo "Tailscale did not provide an IPv4 address" >&2
          exit 1
        fi
        printf 'K3S_NODE_IP=%s\n' "$address" > /run/k3s-tailnet/environment
      '';
    };

    services.k3s = {
      enable = true;
      role = if isServer then "server" else "agent";
      nodeName = hostname;
      clusterInit = isBootstrap;
      serverAddr = lib.mkIf (!isBootstrap) cfg.serverAddress;
      tokenFile = lib.mkIf (!isBootstrap) cfg.tokenFile;
      environmentFile = "/run/k3s-tailnet/environment";
      gracefulNodeShutdown.enable = true;
      extraFlags = [
        "--flannel-iface=tailscale0"
      ] ++ lib.optionals isServer [
        "--tls-san=kilo"
        "--write-kubeconfig-mode=0640"
        "--write-kubeconfig-group=k3s"
      ];
      manifests = lib.mkIf cfg.deployWorkloads {
        homelab.source = ../../kubernetes/homelab.yaml;
      };
    };

    # Only tailnet peers can reach the Kubernetes API, etcd, kubelet, or
    # flannel VXLAN. CNI interfaces remain trusted for local pod traffic.
    networking.firewall = {
      allowedUDPPorts = [ 41641 ];
      interfaces.tailscale0 = {
        allowedTCPPorts = [ 6443 10250 ] ++ lib.optionals isServer [ 2379 2380 ];
        allowedUDPPorts = [ 8472 ];
      };
      trustedInterfaces = [ "cni0" "flannel.1" ];
      checkReversePath = "loose";
    };

    environment.systemPackages = with pkgs; [
      kubectl
      k3s
      kubernetes-helm
      tailscale
    ];

    users.groups.k3s = { };
    users.users.budchris.extraGroups = [ "k3s" ];

    # Make illmatic's media available on every node so the workloads can move
    # once their application-data PVCs use shared or replicated storage.
    boot.supportedFilesystems = [ "nfs" ];
    fileSystems = {
      "/mnt/illmatic/Jukebox" = {
        device = "illmatic:/volume1/Jukebox";
        fsType = "nfs";
        options = [ "_netdev" "nofail" "x-systemd.automount" "x-systemd.idle-timeout=10min" ];
      };
      "/mnt/illmatic/Movies" = {
        device = "illmatic:/volume1/Movies";
        fsType = "nfs";
        options = [ "_netdev" "nofail" "x-systemd.automount" "x-systemd.idle-timeout=10min" ];
      };
      "/mnt/illmatic/TV" = {
        device = "illmatic:/volume1/TV";
        fsType = "nfs";
        options = [ "_netdev" "nofail" "x-systemd.automount" "x-systemd.idle-timeout=10min" ];
      };
      "/mnt/illmatic/Downloads" = {
        device = "illmatic:/volume1/Downloads";
        fsType = "nfs";
        options = [ "_netdev" "nofail" "x-systemd.automount" "x-systemd.idle-timeout=10min" ];
      };
      "/mnt/illmatic/Sports" = {
        device = "illmatic:/volume1/Sports";
        fsType = "nfs";
        options = [ "_netdev" "nofail" "x-systemd.automount" "x-systemd.idle-timeout=10min" ];
      };
    };
  };
}
