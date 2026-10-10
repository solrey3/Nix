{ config, lib, pkgs, ... }:

let
  cfg = config.custom.vpnApps;
  prefixLength = lib.toInt (lib.last (lib.splitString "/" cfg.subnet));
  user = config.users.users.${cfg.user};
  vpnNamespace = "vpn-apps";
  vpnHostInterface = "vpn-apps-host";
  vpnPeerInterface = "vpn-apps-peer";
  vpnAppLaunch = pkgs.writeShellScriptBin "vpn-app-launch" ''
    set -euo pipefail
    if [[ "$#" -lt 1 ]]; then
      echo "Usage: vpn-app-launch {nicotine|transmission} [arguments...]" >&2
      exit 2
    fi
    app="$1"
    shift
    # Check only the configured VPN interface; never fall back to a LAN route.
    if ! ${pkgs.iproute2}/bin/ip -4 address show dev ${lib.escapeShellArg cfg.interface} scope global 2>/dev/null \
      | ${pkgs.gnugrep}/bin/grep -q 'inet '; then
      echo "VPN is not active (${cfg.interface} has no IPv4 address)." >&2
      exit 1
    fi
    case "$app" in
      nicotine) command=("${pkgs.nicotine-plus}/bin/nicotine" "$@") ;;
      transmission) command=("${pkgs.transmission_4-gtk}/bin/transmission-gtk" "$@") ;;
      *) echo "Unsupported VPN app: $app" >&2; exit 2 ;;
    esac
    exec ${pkgs.iproute2}/bin/ip netns exec ${vpnNamespace} \
      ${pkgs.util-linux}/bin/setpriv \
        --reuid=${lib.escapeShellArg cfg.user} --regid=${lib.escapeShellArg user.group} --init-groups -- \
        ${pkgs.coreutils}/bin/env \
          HOME=${lib.escapeShellArg user.home} USER=${lib.escapeShellArg cfg.user} LOGNAME=${lib.escapeShellArg cfg.user} \
          "''${command[@]}"
  '';
in
{
  options.custom.vpnApps = {
    user = lib.mkOption {
      type = lib.types.strMatching "[a-z_][a-z0-9_-]*";
      default = config.custom.fleet.primaryUser;
      description = "Account used to run the allowlisted VPN applications.";
    };
    interface = lib.mkOption {
      type = lib.types.strMatching "[a-zA-Z0-9_.-]+";
      default = "proton0";
      description = "Only interface permitted to carry VPN application traffic.";
    };
    subnet = lib.mkOption {
      type = lib.types.strMatching "[0-9.]+/[0-9]+";
      default = "10.231.0.0/30";
      description = "Private namespace subnet; must contain both configured addresses.";
    };
    hostAddress = lib.mkOption {
      type = lib.types.strMatching "[0-9.]+";
      default = "10.231.0.1";
      description = "Host-side namespace gateway address.";
    };
    peerAddress = lib.mkOption {
      type = lib.types.strMatching "[0-9.]+";
      default = "10.231.0.2";
      description = "Namespace-side address.";
    };
    dns = lib.mkOption {
      type = lib.types.strMatching "[0-9.]+";
      default = "1.1.1.1";
      description = "DNS server reached exclusively through the VPN.";
    };
  };

  config = {
    assertions = [{
      assertion = prefixLength >= 1 && prefixLength <= 32;
      message = "custom.vpnApps.subnet must have an IPv4 prefix length between 1 and 32.";
    }];
    environment.systemPackages = with pkgs; [ proton-vpn tailscale vpnAppLaunch wireguard-tools ];
    services.gnome.gnome-keyring.enable = true;
    boot.kernel.sysctl."net.ipv4.ip_forward" = 1;

    systemd.services.vpn-apps-namespace = {
      description = "VPN-only network namespace for P2P applications";
      wantedBy = [ "multi-user.target" ];
      before = [ "network-online.target" ];
      serviceConfig = {
        Type = "oneshot";
        RemainAfterExit = true;
      };
      path = [ pkgs.iproute2 ];
      script = ''
        set -e
        mkdir -p /etc/netns/${vpnNamespace}
        printf 'nameserver %s\n' ${lib.escapeShellArg cfg.dns} > /etc/netns/${vpnNamespace}/resolv.conf
        ip netns add ${vpnNamespace}
        ip link add ${vpnHostInterface} type veth peer name ${vpnPeerInterface}
        ip link set ${vpnPeerInterface} netns ${vpnNamespace}
        ip address add ${lib.escapeShellArg "${cfg.hostAddress}/${toString prefixLength}"} dev ${vpnHostInterface}
        ip link set ${vpnHostInterface} up
        ip -n ${vpnNamespace} link set lo up
        ip -n ${vpnNamespace} address add ${lib.escapeShellArg "${cfg.peerAddress}/${toString prefixLength}"} dev ${vpnPeerInterface}
        ip -n ${vpnNamespace} link set ${vpnPeerInterface} up
        ip -n ${vpnNamespace} route add default via ${lib.escapeShellArg cfg.hostAddress}
      '';
      preStop = ''
        ip netns delete ${vpnNamespace} 2>/dev/null || true
        rm -rf /etc/netns/${vpnNamespace}
      '';
    };

    # Preserve session sockets while allowing only the immutable application helper.
    security.sudo.extraConfig = ''
      Defaults!/run/current-system/sw/bin/vpn-app-launch env_keep += "DISPLAY WAYLAND_DISPLAY XDG_RUNTIME_DIR DBUS_SESSION_BUS_ADDRESS XAUTHORITY"
      ${cfg.user} ALL=(root) NOPASSWD: /run/current-system/sw/bin/vpn-app-launch *
    '';

    networking.nftables = {
      enable = true;
      tables = {
        vpn-apps-filter = {
          family = "inet";
          content = ''
            chain forward {
              type filter hook forward priority -10; policy accept;
              iifname "${vpnHostInterface}" oifname != "${cfg.interface}" drop
            }
          '';
        };
        vpn-apps-nat = {
          family = "ip";
          content = ''
            chain postrouting {
              type nat hook postrouting priority srcnat; policy accept;
              ip saddr ${cfg.subnet} oifname "${cfg.interface}" masquerade
            }
          '';
        };
      };
    };
    services.tailscale = {
      enable = true;
      useRoutingFeatures = "client";
    };
    networking.firewall = {
      allowedUDPPorts = [ config.services.tailscale.port ];
      trustedInterfaces = [ config.services.tailscale.interfaceName ];
      checkReversePath = "loose";
      extraForwardRules = ''
        iifname "${vpnHostInterface}" oifname "${cfg.interface}" accept
        iifname "${cfg.interface}" oifname "${vpnHostInterface}" ct state established,related accept
      '';
    };
  };
}
