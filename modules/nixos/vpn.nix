{ pkgs, ... }:

let
  vpnNamespace = "vpn-apps";
  vpnHostInterface = "vpn-apps-host";
  vpnPeerInterface = "vpn-apps-peer";

  vpnNamespaceCleanup = ''
    # Delete the veth pair even if an app still holds the old namespace open.
    ip link delete ${vpnHostInterface} 2>/dev/null || true
    ip link delete ${vpnPeerInterface} 2>/dev/null || true
    ip netns delete ${vpnNamespace} 2>/dev/null || true
    rm -rf /etc/netns/${vpnNamespace}
  '';

  vpnAppLaunch = pkgs.writeShellScriptBin "vpn-app-launch" ''
    set -euo pipefail

    if [[ "$#" -lt 1 ]]; then
      echo "Usage: vpn-app-launch {nicotine|transmission} [arguments...]" >&2
      exit 2
    fi

    app="$1"
    shift

    # Refuse to launch without Proton VPN. The namespace firewall below also
    # prevents leaks if the interface disappears while an app is running.
    if ! ${pkgs.iproute2}/bin/ip -4 address show dev proton0 scope global 2>/dev/null \
      | ${pkgs.gnugrep}/bin/grep -q 'inet '; then
      echo "Proton VPN is not active (proton0 has no IPv4 address)." >&2
      exit 1
    fi

    case "$app" in
      nicotine)
        command=("${pkgs.nicotine-plus}/bin/nicotine" "$@")
        ;;
      transmission)
        command=("${pkgs.transmission_4-gtk}/bin/transmission-gtk" "$@")
        ;;
      *)
        echo "Unsupported VPN app: $app" >&2
        exit 2
        ;;
    esac

    exec ${pkgs.iproute2}/bin/ip netns exec ${vpnNamespace} \
      ${pkgs.util-linux}/bin/setpriv \
        --reuid=budchris --regid=users --init-groups -- \
        ${pkgs.coreutils}/bin/env \
          HOME=/home/budchris USER=budchris LOGNAME=budchris \
          "''${command[@]}"
  '';
in
{
  environment.systemPackages = with pkgs; [
    proton-vpn
    tailscale
    vpnAppLaunch
    wireguard-tools
  ];

  # Proton VPN integrates with NetworkManager and stores secrets in a keyring.
  services.gnome.gnome-keyring.enable = true;

  # Nicotine+ and Transmission run in this namespace. Its only permitted
  # forwarded path is through Proton's WireGuard interface, proton0.
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
      set -ex
      # Recover from stale state left by an interrupted or failed startup.
      ${vpnNamespaceCleanup}
      mkdir -p /etc/netns/${vpnNamespace}
      printf 'nameserver 1.1.1.1\n' > /etc/netns/${vpnNamespace}/resolv.conf

      ip netns add ${vpnNamespace}
      ip link add ${vpnHostInterface} type veth peer name ${vpnPeerInterface}
      ip link set ${vpnPeerInterface} netns ${vpnNamespace}

      ip address add 10.231.0.1/30 dev ${vpnHostInterface}
      ip link set ${vpnHostInterface} up
      ip -n ${vpnNamespace} link set lo up
      ip -n ${vpnNamespace} address add 10.231.0.2/30 dev ${vpnPeerInterface}
      ip -n ${vpnNamespace} link set ${vpnPeerInterface} up
      ip -n ${vpnNamespace} route add default via 10.231.0.1
    '';
    # ExecStopPost also runs when ExecStart fails partway through setup.
    postStop = vpnNamespaceCleanup;
  };

  # The immutable helper only permits the two explicitly listed applications.
  # Keep the desktop session's Unix-socket environment when crossing sudo.
  security.sudo.extraConfig = ''
    Defaults!/run/current-system/sw/bin/vpn-app-launch env_keep += "DISPLAY WAYLAND_DISPLAY XDG_RUNTIME_DIR DBUS_SESSION_BUS_ADDRESS XAUTHORITY"
    budchris ALL=(root) NOPASSWD: /run/current-system/sw/bin/vpn-app-launch *
  '';

  networking.nftables = {
    enable = true;
    tables = {
      vpn-apps-filter = {
        family = "inet";
        content = ''
          chain forward {
            type filter hook forward priority -10; policy accept;
            iifname "${vpnHostInterface}" oifname != "proton0" drop
          }
        '';
      };
      vpn-apps-nat = {
        family = "ip";
        content = ''
          chain postrouting {
            type nat hook postrouting priority srcnat; policy accept;
            ip saddr 10.231.0.0/30 oifname "proton0" masquerade
          }
        '';
      };
    };
  };

  services.tailscale = {
    enable = true;
    useRoutingFeatures = "client";
  };

  # Allow Tailscale peer traffic and make exit nodes/subnet routes work cleanly.
  networking.firewall = {
    allowedUDPPorts = [ 41641 ];
    trustedInterfaces = [ "tailscale0" ];
    checkReversePath = "loose";
    extraForwardRules = ''
      iifname "${vpnHostInterface}" oifname "proton0" accept
      iifname "proton0" oifname "${vpnHostInterface}" ct state established,related accept
    '';
  };
}
