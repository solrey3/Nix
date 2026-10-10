{ self, pkgs }:

let
  alternate = self.nixosConfigurations.kilo.extendModules {
    modules = [{
      custom.fleet = {
        primaryUser = "testuser";
        headless = true;
        nas = {
          host = "nas.example";
          exportRoot = "/exports";
          mountRoot = "/srv/media \"test\"";
        };
      };
      custom.k3sCluster = {
        endpointHost = "control.example";
        workloadSelector = { "homelab/storage" = "media"; };
        mediaUID = 2000;
        mediaGID = 200;
        serviceURLs.jellyfin = "https://media.example/?a=1&b=\"two\"";
      };
    }];
  };
  workstation = self.nixosConfigurations.oscar.extendModules {
    modules = [{
      custom.fleet.primaryUser = "testuser";
      users.users.testuser.home = "/srv/test-home";
      custom.vpnApps.interface = "test-vpn";
    }];
  };
  endpointOnly = self.nixosConfigurations.kilo.extendModules {
    modules = [{ custom.k3sCluster.endpointHost = "control.example"; }];
  };
  cfg = alternate.config;
  workstationCfg = workstation.config;
  lib = pkgs.lib;
  desktopDefaults = {
    alpha = "none+i3";
    charlie = "none+i3";
    foxtrot = "none+i3";
    golf = "none+i3";
    november = "none+i3";
    bravo = "hyprland";
    oscar = "hyprland";
    papa = "hyprland";
    quebec = "hyprland";
    india = "plasma";
  };
  python = pkgs.python3.withPackages (ps: [ ps.pyyaml ]);
in
assert lib.all (host:
  let config = self.nixosConfigurations.${host}.config;
  in config.services.displayManager.defaultSession == desktopDefaults.${host}
    && (if desktopDefaults.${host} == "none+i3"
        then config.services.xserver.windowManager.i3.enable
        else if desktopDefaults.${host} == "hyprland"
        then config.programs.hyprland.enable
        else config.services.desktopManager.plasma6.enable)
) (builtins.attrNames desktopDefaults);
assert lib.all (host:
  self.nixosConfigurations.${host}.config.services.desktopManager.plasma6.enable == (host == "india")
) (builtins.attrNames self.nixosConfigurations);
assert lib.all (host:
  !self.nixosConfigurations.${host}.config.programs.sway.enable
) (builtins.attrNames self.nixosConfigurations);
assert cfg.services.k3s.serverAddr == ""; # Bootstrap does not join itself.
assert endpointOnly.config.custom.k3sCluster.workloadSelector == { "kubernetes.io/hostname" = "kilo"; };
assert builtins.elem "--tls-san=control.example" cfg.services.k3s.extraFlags;
assert cfg.custom.k3sCluster.serverAddress == "https://control.example:6443";
assert cfg.fileSystems."/srv/media \"test\"/Jukebox".device == "nas.example:/exports/Jukebox";
assert cfg.home-manager.users.testuser.home.username == "testuser";
assert cfg.home-manager.users.testuser.home.homeDirectory == cfg.users.users.testuser.home;
assert builtins.elem "testuser" cfg.nix.settings.trusted-users;
assert lib.hasInfix "testuser ALL=" workstationCfg.security.sudo.extraConfig;
assert lib.hasInfix ''oifname != "test-vpn" drop'' workstationCfg.networking.nftables.tables.vpn-apps-filter.content;
assert workstationCfg.home-manager.users.testuser.home.homeDirectory == "/srv/test-home";
assert lib.hasInfix "id -u" self.nixosConfigurations.alpha.config.systemd.services.mpd-audio-runtime.script;
assert !(lib.hasInfix "/run/user/1000" self.nixosConfigurations.alpha.config.systemd.services.mpd-audio-runtime.script);
pkgs.runCommand "fleet-config-tests" { nativeBuildInputs = [ python ]; } ''
  python ${./check_fleet.py} \
    ${self.nixosConfigurations.kilo.config.services.k3s.manifests.homelab.source} \
    ${cfg.services.k3s.manifests.homelab.source}
  cp ${../reorganize_tv_for_jellyfin.py} reorganize_tv_for_jellyfin.py
  mkdir tests
  cp ${./test_tv_root.py} tests/test_tv_root.py
  python -m unittest discover -s tests -v
  touch "$out"
''
