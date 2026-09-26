{ lib, osConfig ? null, pkgs, ... }:

let
  enabled = osConfig != null && (osConfig.custom.desktop.environments.hyprland or false);

  quickshellRegisterTrayItems = pkgs.writeShellApplication {
    name = "quickshell-register-tray-items";
    runtimeInputs = with pkgs; [ coreutils systemd ];
    text = ''
      # Some AppIndicator clients, notably Proton VPN, do not re-register when
      # the StatusNotifierWatcher changes while they are already running.
      # Register their well-known item names whenever Quickshell starts.
      for _ in $(seq 1 10); do
        registered=false
        while read -r service _; do
          case "$service" in
            org.kde.StatusNotifierItem-*)
              busctl --user call \
                org.kde.StatusNotifierWatcher \
                /StatusNotifierWatcher \
                org.kde.StatusNotifierWatcher \
                RegisterStatusNotifierItem s "$service" >/dev/null 2>&1 || true
              registered=true
              ;;
          esac
        done < <(busctl --user list --no-pager --no-legend 2>/dev/null || true)

        "$registered" && exit 0
        sleep 1
      done
    '';
  };

  quickshellToggle = pkgs.writeShellApplication {
    name = "quickshell-toggle";
    runtimeInputs = with pkgs; [ gnugrep quickshell ];
    text = ''
      if qs list -c budchris 2>/dev/null | grep -q '^Instance '; then
        qs kill -c budchris
      else
        qs -d -n -c budchris
      fi
    '';
  };

  quickshellSystemStats = pkgs.writeShellApplication {
    name = "quickshell-system-stats";
    runtimeInputs = with pkgs; [ coreutils gawk ];
    text = ''
      read -r _ user nice system idle iowait irq softirq steal _ < /proc/stat
      total=$((user + nice + system + idle + iowait + irq + softirq + steal))
      idle_total=$((idle + iowait))

      mem_total=$(awk '/^MemTotal:/ { print $2 * 1024 }' /proc/meminfo)
      mem_available=$(awk '/^MemAvailable:/ { print $2 * 1024 }' /proc/meminfo)
      read -r disk_size disk_used < <(df --output=size,used -B1 / | awk 'NR == 2 { print $1, $2 }')
      kernel=$(uname -r)

      printf '%s\t%s\t%.0f\t%.0f\t%s\t%s\t%s\n' \
        "$total" "$idle_total" "$mem_total" "$mem_available" \
        "$disk_size" "$disk_used" "$kernel"
    '';
  };
in
{
  config = lib.mkIf enabled {
    home.packages = [
      # Quickshell resolves StatusNotifier icon names through the first hicolor
      # directory in XDG_DATA_DIRS.  Include its index in the user profile so
      # application-provided icons (such as Telegram's symbolic icon) resolve.
      pkgs.hicolor-icon-theme
      pkgs.quickshell
      quickshellRegisterTrayItems
      quickshellSystemStats
      quickshellToggle
    ];

    xdg.configFile."quickshell/budchris" = {
      source = ./quickshell;
      recursive = true;
    };
  };
}
