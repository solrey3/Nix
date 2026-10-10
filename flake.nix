{
  description = "Modular multi-host NixOS configuration";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

    home-manager = {
      url = "github:nix-community/home-manager/master";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    darwin = {
      url = "github:nix-darwin/nix-darwin/master";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    disko = {
      url = "github:nix-community/disko";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    deploy-rs = {
      url = "github:serokell/deploy-rs";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    lazyvim-starter = {
      url = "github:LazyVim/starter";
      flake = false;
    };
  };

  outputs = inputs@{ self, nixpkgs, home-manager, darwin, deploy-rs, ... }:
    let
      lib = nixpkgs.lib;
      username = "budchris";

      # Add or remove supported systems for packages/devShells here.
      systems = [ "x86_64-linux" "aarch64-linux" ];
      forAllSystems = lib.genAttrs systems;

      # A host is discovered only when its two required entry points exist, so
      # work-in-progress inventory directories do not break the whole flake.
      hostDirs = lib.filterAttrs
        (name: type:
          type == "directory"
          && builtins.pathExists ./hosts/${name}/default.nix
          && builtins.pathExists ./hosts/${name}/system.nix)
        (builtins.readDir ./hosts);

      mkHost = hostname: hostSystem:
        lib.nixosSystem {
          system = hostSystem;
          specialArgs = {
            inherit inputs self hostname username;
          };
          modules = [
            ({ ... }: { nixpkgs.overlays = [ self.overlays.default ]; })
            home-manager.nixosModules.home-manager
            ./modules/nixos/common.nix
            ./modules/nixos/home-manager.nix
            ./hosts/${hostname}
          ];
        };

      mkDarwinHost = hostname: hostSystem:
        darwin.lib.darwinSystem {
          system = hostSystem;
          specialArgs = {
            inherit inputs self hostname username;
          };
          modules = [
            home-manager.darwinModules.home-manager
            ./modules/darwin/nix-core.nix
            ./modules/darwin/system.nix
            ./modules/darwin/host-users.nix
            ./hosts/${hostname}
            ({ config, ... }: {
              home-manager = {
                useGlobalPkgs = true;
                useUserPackages = true;
                backupFileExtension = "backup";
                extraSpecialArgs = { inherit inputs; };
                users.${username} = {
                  imports = [ ./modules/home/budchris/portable.nix ];
                  home = {
                    inherit username;
                    homeDirectory = config.users.users.${username}.home;
                    stateVersion = "24.11";
                  };
                };
              };
            })
          ];
        };
    in
    {
      nixosConfigurations = lib.mapAttrs
        (hostname: _: mkHost hostname (import ./hosts/${hostname}/system.nix))
        hostDirs;

      darwinConfigurations = {
        delta = mkDarwinHost "delta" "aarch64-darwin";
        juliet = mkDarwinHost "juliet" "aarch64-darwin";
      };

      homeConfigurations.echo = home-manager.lib.homeManagerConfiguration {
        pkgs = import nixpkgs {
          system = "aarch64-linux";
          config.allowUnfree = true;
        };
        extraSpecialArgs = { inherit inputs username; };
        modules = [ ./hosts/echo ];
      };

      # Tango deploys every host over Tailscale MagicDNS. Target hosts build
      # their own closures so tango remains an orchestrator rather than a
      # cross-machine build bottleneck.
      deploy.nodes = lib.mapAttrs
        (hostname: configuration: {
          inherit hostname;
          sshUser = configuration.config.custom.fleet.primaryUser;
          remoteBuild = true;
          profiles.system = {
            user = "root";
            path = deploy-rs.lib.${configuration.pkgs.system}.activate.nixos configuration;
          };
        })
        self.nixosConfigurations;

      checks.x86_64-linux = deploy-rs.lib.x86_64-linux.deployChecks self.deploy // {
        fleet-config = import ./tests/fleet.nix {
          inherit self;
          pkgs = nixpkgs.legacyPackages.x86_64-linux;
        };
      };

      overlays.default = import ./overlays;

      packages = forAllSystems (system:
        import ./pkgs { pkgs = nixpkgs.legacyPackages.${system}; });

      formatter = forAllSystems (system: nixpkgs.legacyPackages.${system}.nixpkgs-fmt);

      devShells = forAllSystems (system:
        let pkgs = nixpkgs.legacyPackages.${system}; in
        {
          default = pkgs.mkShell {
            packages = with pkgs; [
              nil
              nixpkgs-fmt
              statix
            ];
          };
        });
    };
}
