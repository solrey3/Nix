{ config, hostname, lib, pkgs, ... }:

let
  cfg = config.custom.k3sCluster;
  isBootstrap = cfg.role == "bootstrap";
  isServer = cfg.role != "agent";
  nas = config.custom.fleet.nas;
  tailnetInterface = config.services.tailscale.interfaceName;
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
      default = "https://${cfg.endpointHost}:6443";
      description = "URL of the bootstrap k3s server over Tailscale MagicDNS.";
    };

    endpointHost = lib.mkOption {
      type = lib.types.str;
      default = "kilo";
      description = "Stable cluster endpoint hostname, shared by the URL and TLS SANs.";
    };

    tlsSANs = lib.mkOption {
      type = lib.types.listOf lib.types.str;
      default = [ cfg.endpointHost ];
      description = "Names included in every server's API certificate.";
    };

    workloadSelector = lib.mkOption {
      type = lib.types.attrsOf lib.types.str;
      default = { "kubernetes.io/hostname" = config.services.k3s.nodeName; };
      description = "Selector for workloads with node-local PVCs; defaults to the deploying node, independent of endpoint DNS.";
    };

    serviceURLs = lib.mapAttrs
      (name: port: lib.mkOption {
        type = lib.types.str;
        default = "http://${cfg.endpointHost}.local:${port}";
        description = "Dashboard URL for ${name}; override for ingress DNS.";
      })
      {
        jellyfin = "8096";
        navidrome = "4533";
        sabnzbd = "8080";
        pihole = "8081/admin";
      };

    mediaUID = lib.mkOption {
      type = lib.types.ints.unsigned;
      default = 1000;
      description = "NAS-compatible SABnzbd file owner UID (not necessarily the desktop UID).";
    };

    mediaGID = lib.mkOption {
      type = lib.types.ints.unsigned;
      default = 100;
      description = "NAS-compatible SABnzbd file owner GID.";
    };

    tokenFile = lib.mkOption {
      type = lib.types.path;
      default = "/var/lib/rancher/k3s/cluster-token";
      description = "Out-of-store token file used by joining nodes.";
    };

    deployWorkloads = lib.mkOption {
      type = lib.types.bool;
      default = isBootstrap;
      description = "Render and install kubernetes/homelab.yaml.in from this server.";
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
        "--flannel-iface=${tailnetInterface}"
      ] ++ lib.optionals isServer (map (san: "--tls-san=${san}") cfg.tlsSANs) ++ lib.optionals isServer [
        "--write-kubeconfig-mode=0640"
        "--write-kubeconfig-group=k3s"
      ];
      manifests = lib.mkIf cfg.deployWorkloads {
        homelab.source = pkgs.writeText "homelab.yaml" (lib.replaceStrings
          [
            "@NODE_SELECTOR@"
            "@JUKEBOX_PATH@"
            "@MOVIES_PATH@"
            "@TV_PATH@"
            "@SPORTS_PATH@"
            "@DOWNLOADS_PATH@"
            "@MEDIA_UID@"
            "@MEDIA_GID@"
            "@JELLYFIN_URL@"
            "@NAVIDROME_URL@"
            "@SABNZBD_URL@"
            "@PIHOLE_URL@"
          ]
          ([ (builtins.toJSON cfg.workloadSelector) ]
            ++ map (share: builtins.toJSON "${nas.mountRoot}/${share}") [ "Jukebox" "Movies" "TV" "Sports" "Downloads" ]
            ++ [ (toString cfg.mediaUID) (toString cfg.mediaGID) ]
            ++ map lib.escapeXML [ cfg.serviceURLs.jellyfin cfg.serviceURLs.navidrome cfg.serviceURLs.sabnzbd cfg.serviceURLs.pihole ])
          (builtins.readFile ../../kubernetes/homelab.yaml.in));
      };
    };

    # Only tailnet peers can reach the Kubernetes API, etcd, kubelet, or
    # flannel VXLAN. CNI interfaces remain trusted for local pod traffic.
    networking.firewall = {
      allowedUDPPorts = [ config.services.tailscale.port ];
      interfaces.${tailnetInterface} = {
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
    users.users.${config.custom.fleet.primaryUser}.extraGroups = [ "k3s" ];

    # Make illmatic's media available on every node so the workloads can move
    # once their application-data PVCs use shared or replicated storage.
    boot.supportedFilesystems = [ "nfs" ];
    fileSystems = lib.listToAttrs (map
      (share: {
        name = "${nas.mountRoot}/${share}";
        value = {
          device = "${nas.host}:${nas.exportRoot}/${share}";
          fsType = "nfs";
          options = [ "_netdev" "nofail" "x-systemd.automount" "x-systemd.idle-timeout=10min" ];
        };
      }) [ "Jukebox" "Movies" "TV" "Downloads" "Sports" ]);
  };
}
