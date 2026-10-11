# Host settings and update validation

Keep declarative host values in Nix options rather than reading the build
machine's environment with `builtins.getEnv`. Runtime scripts may use environment
variables or look up assigned values such as UIDs and Tailscale addresses.

## Shared account and storage

`flake.nix` defines the default `username` once for NixOS, Darwin, and standalone
Home Manager. NixOS hosts can override `custom.fleet.primaryUser`; account homes,
trusted users, deployment SSH users, VPN application identity, and relevant host
Home Manager overrides follow that setting. Renaming an existing account requires
an explicit home/data migration; changing the option does not move files.

`custom.fleet.headless = true` selects the portable Home Manager profile.

NAS options under `custom.fleet.nas`:

- `host`: cluster NFS hostname (default `illmatic`).
- `lanHost`: MPD's LAN-only NFS hostname (default `illmatic.local`). Keep these
  separate: the NAS currently restricts MPD's export to LAN clients.
- `exportRoot`: remote export root (default `/volume1`).
- `mountRoot`: local mount root (default `/mnt/illmatic`).

MPD resolves the primary user's UID at service startup for its PipeWire socket;
no UID 1000 assumption is required. Cache paths use Home Manager's `xdg.cacheHome`.

## Desktop and MPD clients

Home Manager's `custom.desktopPolicy` controls `output`, `mode`, `scale`,
`terminalOpacity`, optional `gtkScale`, and `restartSynology`.
Set policy on the host's Home Manager user, not by matching hostnames in shared
modules. Display connectors and scaling remain explicit hardware preferences.

`custom.mpdAddress` configures rmpc's TCP endpoint or Unix socket. For the
standalone `mpd-album-shuffle` script, TCP settings also populate its existing
`MPD_HOST`/`MPD_PORT` environment variables. CLI arguments take precedence; Unix
socket settings are not exported as TCP hosts.

The TV reorganization script accepts `TV_ROOT`; its `--root` argument takes
precedence. It still defaults to dry-run.

## VPN namespace

`custom.vpnApps` exposes `user`, `interface`, `subnet`, `hostAddress`,
`peerAddress`, and `dns`. Both addresses must belong to the configured subnet;
interface prefix lengths are derived from that subnet. The interface is an explicit
allowlist: the launcher, forwarding filter, and NAT all use it. Never replace
this with discovery of the current default route. Changing these settings may
require restarting the namespace service after stopping its applications.

## Cluster workloads

`custom.k3sCluster.endpointHost` supplies the default join URL and TLS SAN.
`serverAddress` and `tlsSANs` can be overridden independently when necessary;
ensure that the certificate names cover the join URL.

Other configurable settings:

- `workloadSelector`: defaults to pinning stateful workloads to `kilo`.
- `serviceURLs`: `jellyfin`, `navidrome`, `sabnzbd`, and `pihole` dashboard links.
- `mediaUID`/`mediaGID`: NAS-compatible SABnzbd ownership, default 1000/100.
  These are storage ownership policy, not dynamically inferred desktop IDs.

Nix renders `kubernetes/homelab.yaml.in` into the k3s manifest. The template is
not directly suitable for `kubectl apply`. Build the rendered manifest with:

```sh
nix build .#nixosConfigurations.kilo.config.services.k3s.manifests.homelab.source
```

Do not move selectors while PVCs use node-local storage. Changing the NAS mount
root must be coordinated across all cluster hosts and workloads. Leave disk
UUIDs, LUKS IDs, public authorized keys, `stateVersion`, and Tango's provisioned
static network values explicit.

## Before every update PR

Run from the repository root:

```sh
./scripts/check-updates
```

This updates `flake.lock`, runs `nix flake check` (including the generated
manifest and environment/CLI tests), and evaluates both Darwin configurations
and standalone Home Manager. Review lock-file changes and commit only relevant
files. Do not open a PR while validation fails.

For deployment, first build the intended host:

```sh
nix build .#nixosConfigurations.HOST.config.system.build.toplevel
sudo nixos-rebuild switch --flake .#HOST
```

A rebuild is not required just to refactor or validate configuration. Keep
unrelated local changes out of the PR and avoid activating other hosts' configs.
