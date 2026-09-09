{ inputs, lib, pkgs, self, ... }:

let
  piConsole = self.packages.${pkgs.system}.pi-console;
  deploy = inputs.deploy-rs.packages.${pkgs.system}.default;
  startPiConsole = pkgs.writeShellScript "start-pi-console" ''
    set -euo pipefail
    token_file=/var/lib/pi-console/op-service-account.env
    template=/var/lib/pi-console/secrets.env.tpl

    if [[ -s "$token_file" && -s "$template" ]]; then
      set -a
      # shellcheck disable=SC1090
      source "$token_file"
      set +a
      exec ${pkgs._1password-cli}/bin/op run --env-file="$template" -- ${piConsole}/bin/pi-console
    fi

    exec ${piConsole}/bin/pi-console
  '';
in
{
  users.groups = {
    pi-console = { };
    nixos-repo.members = [ "budchris" "pi-console" ];
  };
  users.users.pi-console = {
    isSystemUser = true;
    group = "pi-console";
    home = "/var/lib/pi-console";
    createHome = true;
    shell = pkgs.bashInteractive;
  };

  environment.systemPackages = [
    deploy
    pkgs._1password-cli
    pkgs.pi-coding-agent
  ];

  environment.etc."pi-console/secrets.env.example".text = ''
    # Copy to /var/lib/pi-console/secrets.env.tpl, change this 1Password
    # reference to match your vault, and chmod/chown it 0600 pi-console.
    # openai-codex OAuth remains in the console user's auth.json.
    OPENROUTER_API_KEY=op://Homelab/OpenRouter/api-key
  '';

  # tailscale0 is trusted for other fleet services, so filter the console in an
  # earlier input hook. Update these stable device addresses after re-enrollment.
  networking.nftables = {
    enable = true;
    tables.pi-console-access = {
      family = "inet";
      content = ''
        set allowed_ipv4 {
          type ipv4_addr
          elements = {
            100.88.4.72,     # iPhone 13
            100.65.222.81,   # oscar
            100.102.213.120, # quebec
            100.88.89.21     # bravo
          }
        }

        set allowed_ipv6 {
          type ipv6_addr
          elements = {
            fd7a:115c:a1e0::c301:448, # iPhone 13
            fd7a:115c:a1e0::d532:de53, # oscar
            fd7a:115c:a1e0::5232:d579, # quebec
            fd7a:115c:a1e0::1832:5918  # bravo
          }
        }

        chain input {
          type filter hook input priority -10; policy accept;
          iifname "tailscale0" tcp dport 3210 ip saddr != @allowed_ipv4 drop
          iifname "tailscale0" tcp dport 3210 ip6 saddr != @allowed_ipv6 drop
        }
      '';
    };
  };

  # Remove the emergency runtime override used during initial bring-up. The
  # service's PATH and SHELL are fully declared below, so retaining a mutable
  # /run drop-in would make the effective unit differ from this module.
  system.activationScripts.removePiConsoleRuntimeOverride = lib.stringAfter [ "etc" ] ''
    rm -f /run/systemd/system/pi-console.service.d/10-path.conf
    rmdir --ignore-fail-on-non-empty /run/systemd/system/pi-console.service.d 2>/dev/null || true
  '';

  systemd.services.pi-console-repository = {
    description = "Initialize the writable NixOS fleet repository";
    wantedBy = [ "multi-user.target" ];
    after = [ "network-online.target" ];
    wants = [ "network-online.target" ];
    before = [ "pi-console.service" ];
    serviceConfig.Type = "oneshot";
    path = [ pkgs.git pkgs.openssh pkgs.coreutils ];
    script = ''
      if [[ ! -d /srv/nixos/.git ]]; then
        rm -rf /srv/nixos
        git clone https://github.com/solrey3/NixOS-Pi /srv/nixos
        # Seed the checkout with the exact source used to install tango. This
        # keeps new/unmerged files available without overwriting later agent
        # work on every activation.
        cp -a --no-preserve=ownership ${self.outPath}/. /srv/nixos/
        chmod -R u+w /srv/nixos
      fi
      chown -R budchris:nixos-repo /srv/nixos
      chmod -R u+rwX,g+rwX /srv/nixos
    '';
  };

  systemd.services.pi-console = {
    description = "Threaded Pi SDK command center";
    wantedBy = [ "multi-user.target" ];
    requires = [ "pi-console-repository.service" ];
    after = [ "pi-console-repository.service" "tailscaled.service" ];
    environment = {
      HOME = "/var/lib/pi-console";
      PI_CONSOLE_HOST = "0.0.0.0";
      PI_CONSOLE_PORT = "3210";
      PI_CONSOLE_STATE_DIR = "/var/lib/pi-console";
      PI_CONSOLE_CWD = "/srv/nixos";
      PI_CONSOLE_TARGETS = "tango,alpha,bravo,kilo,lima,mike,oscar,quebec";
      PI_CONSOLE_PRIMARY_PROVIDER = "openai-codex";
      PI_CONSOLE_PRIMARY_MODEL = "gpt-5.6-sol";
      PI_CONSOLE_PRIMARY_THINKING = "medium";
      PI_CONSOLE_BACKUP_PROVIDER = "openrouter";
      PI_CONSOLE_BACKUP_MODEL = "moonshotai/kimi-k3";
      PI_CONSOLE_BACKUP_THINKING = "medium";
      SHELL = "${pkgs.bash}/bin/sh";
    };
    # Include explicit bin paths so API command runners that spawn plain `sh`
    # can resolve it even in the service's restricted environment.
    path = [ pkgs.bash pkgs.coreutils deploy pkgs.git pkgs.nix pkgs.openssh pkgs._1password-cli pkgs.tailscale ];
    serviceConfig = {
      User = "pi-console";
      Group = "pi-console";
      StateDirectory = "pi-console";
      StateDirectoryMode = "0700";
      WorkingDirectory = "/srv/nixos";
      ExecStart = startPiConsole;
      Restart = "on-failure";
      RestartSec = 3;
      # Keep runaway agent tools from exhausting the whole 8 GiB droplet.
      MemoryHigh = "5G";
      MemoryMax = "6G";
      MemorySwapMax = "2G";
      TasksMax = 2048;
      OOMPolicy = "continue";
      SupplementaryGroups = [ "nixos-repo" ];
      UMask = "0007";
      NoNewPrivileges = true;
      PrivateTmp = true;
      ProtectSystem = "strict";
      ProtectHome = true;
      ReadWritePaths = [ "/srv/nixos" "/var/lib/pi-console" ];
    };
  };

  # Port 3210 is intentionally absent from allowedTCPPorts: the public droplet
  # NIC cannot reach it, and the nftables allowlist limits Tailscale access.
}
