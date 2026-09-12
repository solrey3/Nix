# NixOS Flake

A modular, multi-host configuration for NixOS, nix-darwin, and standalone Home Manager systems, including desktops, laptops, a media server, and a three-node k3s cluster. It tracks `nixos-unstable` and integrates Home Manager.

## Repository layout

```text
flake.nix                    Flake inputs and generated host outputs
hosts/
  alpha/                     Appliance music player and MPD server
  bravo/                     Desktop and media server
  charlie/                   2017 13-inch MacBook Pro running NixOS
  delta/                     M2 MacBook Air managed by nix-darwin
  echo/                      Raspberry Pi 5 standalone Home Manager profile
  foxtrot/                   Early-2013 13-inch Retina MacBook Pro running NixOS
  golf/                      Late-2011 15-inch MacBook Pro running NixOS
  india/                     Steam Deck OLED running NixOS from SD card
  juliet/                    M4 Mac mini managed by nix-darwin
  november/                  A1347 Mac mini running NixOS
  papa/                      Beelink SER5 MAX running NixOS
  oscar/                     Laptop/workstation
  quebec/                    Framework 13 laptop/workstation
  kilo/                      Bootstrap k3s control-plane node
  lima/                      Joining k3s control-plane node
  mike/                      Joining k3s control-plane node
modules/
  nixos/                     Shared NixOS services and host roles
    users/budchris.nix       User account and Home Manager integration
  darwin/                    Shared nix-darwin settings and applications
  home/budchris/             Home Manager applications and dotfiles
apps/pi-console/             Threaded Pi SDK web application source
kubernetes/homelab.yaml      Cluster media, DNS, and homepage workloads
docs/                        Installation, desktop, and cluster guides
overlays/                    Local nixpkgs overlay
pkgs/                        Local package outputs, including Pi Console
```

NixOS host directories normally contain `default.nix`, a machine-generated
`hardware-configuration.nix`, and `system.nix`. `tango` uses a declarative
Disko layout instead of a generated hardware file. Darwin hosts contain their
nix-darwin modules, while `echo` is a standalone Home Manager module.

## Hosts

| Host | Role | Main configuration |
| --- | --- | --- |
| `alpha` | Appliance music player | i3/XFCE, MPD, NFS music library, Tailscale |
| `bravo` | NVIDIA desktop and media server | Plasma, COSMIC, Hyprland, Sway, Docker, VPN tools, Jellyfin, Navidrome |
| `charlie` | 2017 13-inch MacBook Pro (MacBookPro14,1), NixOS | Sway, laptop power management, Docker, Tailscale |
| `delta` | 2022 M2 MacBook Air, macOS | nix-darwin and Home Manager; closed-clamshell external-display setup |
| `echo` | Raspberry Pi 5 | Standalone aarch64-linux Home Manager profile |
| `foxtrot` | Early-2013 13-inch Retina MacBook Pro (MacBookPro10,2), NixOS | XFCE/i3, laptop support, Docker, Tailscale |
| `golf` | Late-2011 15-inch MacBook Pro (MacBookPro8,2), NixOS | i3/XFCE, laptop support, Docker, Tailscale |
| `india` | Steam Deck OLED, NixOS on SD card | Plasma, Steam, laptop support, Docker, Tailscale |
| `juliet` | 2024 M4 Mac mini, macOS | nix-darwin and Home Manager |
| `november` | A1347 Mac mini, NixOS | XFCE/i3, Docker, Tailscale |
| `papa` | Beelink SER5 MAX, NixOS | Sway, Steam, Docker, Tailscale |
| `oscar` | Laptop/workstation | Plasma, COSMIC, Sway, laptop power management, Docker, VPN tools |
| `quebec` | Framework 13 AMD laptop/workstation | Plasma, COSMIC, Hyprland, Sway, laptop power/audio configuration, Docker, VPN tools |
| `kilo` | k3s bootstrap server and worker | Initializes the embedded-etcd cluster and deploys homelab manifests |
| `lima` | k3s server and worker | Joins the control plane initialized by `kilo` |
| `mike` | k3s server and worker | Joins the control plane initialized by `kilo` |
| `tango` | Fleet command center | deploy-rs, Tailscale, 1Password CLI, and the threaded Pi Console web UI |

Tango provisioning and command-console operations are documented in [docs/tango.md](docs/tango.md).

## Build and deploy

Build a host without activating it:

```sh
nix build .#nixosConfigurations.<hostname>.config.system.build.toplevel
```

Switch the current machine:

```sh
sudo nixos-rebuild switch --flake .#<hostname>
```

For example:

```sh
sudo nixos-rebuild switch --flake .#oscar
sudo nixos-rebuild switch --flake .#bravo
```

Apply a macOS host or Echo's standalone Home Manager profile:

```sh
sudo darwin-rebuild switch --flake .#delta
sudo darwin-rebuild switch --flake .#juliet
home-manager switch --flake .#echo
```

Deploy from tango over Tailscale with deploy-rs:

```sh
deploy .#bravo
deploy .#kilo .#lima .#mike
```

For first-time setup after a plain NixOS installation, follow [docs/initial-flake-setup.md](docs/initial-flake-setup.md). The hardware configuration must be generated on the machine where it will be used:

```sh
sudo nixos-generate-config --show-hardware-config \
  > hosts/<hostname>/hardware-configuration.nix
```

The checked-in `kilo`, `lima`, and `mike` files now contain their generated machine-specific disk UUIDs; do not reuse them on replacement hardware. `foxtrot` was a Darwin host in the archived repository, so its NixOS hardware file still contains clearly marked disk-label placeholders. Replace it with hardware generated on foxtrot before the first switch.

## Add a host

Create the host directory and platform file:

```sh
mkdir -p hosts/<hostname>
printf '"x86_64-linux"\n' > hosts/<hostname>/system.nix
cp hosts/oscar/default.nix hosts/<hostname>/default.nix
sudo nixos-generate-config --show-hardware-config \
  > hosts/<hostname>/hardware-configuration.nix
```

Then tailor `default.nix` to the machine. No explicit `flake.nix` entry is needed because host directories are discovered automatically.

## Shared NixOS configuration

All hosts receive the common module, which configures:

- NetworkManager
- OpenSSH with password and root login disabled
- US locale, Eastern time, and basic command-line tools
- flakes, other shared Nix settings, and the local overlay
- Home Manager's NixOS module

The desktop module supports Plasma 6, COSMIC, Hyprland, and Sway with SDDM. `bravo` and `quebec` enable all four; `oscar` enables Plasma, COSMIC, and Sway. All three default to Plasma. The module also configures PipeWire, portals, printing, Firefox, Steam, and desktop keyring integration.

The primary workstations (`bravo`, `oscar`, and `quebec`) additionally enable 1Password, Docker, Tailscale, Proton VPN, and WireGuard tools. Nicotine+ and Transmission run in a dedicated network namespace that fails closed unless traffic can leave through Proton VPN's `proton0` interface. Other desktop hosts use smaller role-specific combinations of Docker and Tailscale.

## Home Manager

The `budchris` account and Home Manager profile are shared by the configured hosts. The profile includes:

- Bash completion, Starship, fzf, zoxide, eza, yazi, mise, and tmux
- Neovim with the upstream LazyVim starter
- Claude Code, Fabric, OpenCode, and Cursor
- Git, Git LFS, GitHub CLI, LazyGit, and Delta
- Ghostty and Alacritty with JetBrainsMono Nerd Font
- a dedicated Google Chrome work profile
- Nextcloud, Obsidian, Picard, Quod Libet/Ex Falso, and Raspberry Pi Imager
- Nicotine+ and Transmission launchers for the VPN-only namespace
- monitoring, search, archive, media, and general command-line utilities

Ghostty is the preferred terminal through `TERMINAL` and `xdg-terminal-exec`. LazyVim plugins are installed by `lazy.nvim` on first launch. See [Hyprland keybindings](docs/hyprland-keybindings.md) and [Sway keybindings](docs/sway-keybindings.md) for the Wayland desktop controls.

## Beelink k3s cluster

`kilo`, `lima`, and `mike` form a three-control-plane k3s cluster using embedded etcd. `kilo` deploys `kubernetes/homelab.yaml`, which contains:

- Jellyfin
- Navidrome
- SABnzbd
- Pi-hole
- an nginx homelab homepage

All nodes mount the NFS exports `/Jukebox`, `/Movies`, `/TV`, `/Downloads`, and `/Sports` from the NAS at hostname `illmatic`. Navidrome reads `/Jukebox`, Jellyfin receives the media exports read-only, and SABnzbd writes to `/Downloads`. Application PVCs initially use k3s local-path storage; Jellyfin, Navidrome, and Pi-hole are pinned to `kilo`.

See [docs/k3s-cluster.md](docs/k3s-cluster.md) for hardware preparation, stable addressing, token transfer, NAS requirements, service access, and storage limitations.

## Bravo media services

`bravo` runs native NixOS services for Jellyfin and Navidrome:

- Jellyfin reads the mounted media drives and uses the NVIDIA GPU for transcoding.
- Navidrome reads music and playlists from `/mnt/archive`.

SABnzbd runs in the k3s cluster and writes downloads to the NAS-backed `/mnt/illmatic/Downloads` mount. Configure its provider credentials through the SABnzbd web interface, retain a recovery copy in 1Password, and do not commit them to this repository.

`reorganize_tv_for_jellyfin.py` migrates top-level TV release folders into Jellyfin's `Series/Season NN` layout. It performs a dry run unless passed `--apply`.

## Development and validation

Enter the development shell for `nil`, `nixpkgs-fmt`, and `statix`:

```sh
nix develop
```

Format and validate the flake:

```sh
nix fmt
nix flake check
```

The flake exports packages, formatter, and development shells for `x86_64-linux` and `aarch64-linux`. NixOS hosts currently use `x86_64-linux`; Echo uses `aarch64-linux`, and Delta and Juliet use `aarch64-darwin`.
