# Beelink k3s cluster

The three EQR5 hosts form an HA [k3s](https://k3s.io/) control plane:

- `kilo`: initializes embedded etcd and deploys cluster manifests
- `lima`, `mike`: join as control-plane/worker servers

All three servers can run workloads. Jellyfin, Navidrome, SABnzbd, Pi-hole, and an nginx homepage are deployed by `kilo`. Jellyfin, Navidrome, and Pi-hole are explicitly pinned to `kilo`; all stateful workloads use node-local `local-path` volumes initially.

## 1. Prepare host configuration

The checked-in hardware files were generated on the current `kilo`, `lima`, and `mike` machines and contain machine-specific filesystem and encryption UUIDs. Review them before deployment and never reuse one for replacement hardware. Regenerate the appropriate file whenever a node is reinstalled or replaced:

```sh
sudo nixos-generate-config --show-hardware-config > hosts/HOST/hardware-configuration.nix
```

Enroll all three machines in the same tailnet with MagicDNS enabled. The default cluster endpoint is `https://kilo:6443`. K3s advertises each node's Tailscale IPv4 address and binds flannel to `tailscale0`; the host firewall permits the API, etcd, kubelet, and VXLAN ports only on that interface. LAN DHCP reservations are still recommended for ordinary host and media-service access, but cluster control-plane traffic does not use them.

The cluster mounts NFS exports from the NAS at hostname `illmatic` on every node. Ensure that name resolves from all three hosts and that the NAS exports `/Jukebox`, `/Movies`, `/TV`, `/Downloads`, and `/Sports` to them. Navidrome receives `/Jukebox`, Jellyfin receives the media paths read-only, and SABnzbd writes to `/Downloads`. The host mount points are under `/mnt/illmatic`.

## 2. Bootstrap kilo

Deploy kilo first:

```sh
sudo nixos-rebuild switch --flake .#kilo
sudo tailscale up --hostname=kilo
sudo systemctl restart k3s
sudo systemctl status k3s
sudo k3s kubectl get nodes
```

Kilo creates the join token at `/var/lib/rancher/k3s/server/node-token`.

## 3. Join lima and mike

Copy kilo's token to each joining node without putting it in Git or the Nix store:

```sh
# Run on kilo; replace HOST twice (lima, then mike).
sudo cp /var/lib/rancher/k3s/server/node-token /tmp/k3s-cluster-token
sudo chown "$USER" /tmp/k3s-cluster-token
scp /tmp/k3s-cluster-token budchris@HOST:/tmp/
ssh budchris@HOST 'sudo install -D -m 0600 -o root -g root /tmp/k3s-cluster-token /var/lib/rancher/k3s/cluster-token && rm /tmp/k3s-cluster-token'
rm /tmp/k3s-cluster-token
```

Then deploy and enroll both nodes:

```sh
sudo nixos-rebuild switch --flake .#lima
sudo tailscale up --hostname=lima
sudo systemctl restart k3s

sudo nixos-rebuild switch --flake .#mike
sudo tailscale up --hostname=mike
sudo systemctl restart k3s
```

Verify from kilo:

```sh
sudo k3s kubectl get nodes -o wide
sudo k3s kubectl get pods -A
```

The `budchris` user belongs to the `k3s` group. Log out/in after the first switch, then use:

```sh
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
kubectl get nodes
```

## 4. Pi-hole password and service addresses

The Pi-hole deployment requires the `network/pihole-admin` Secret and will not start without it. Store the password in 1Password, then stream it directly into Kubernetes without printing it or placing it in shell history. Adjust the item reference to the actual vault item:

```sh
op read 'op://Homelab/Pi-hole/password' | \
  kubectl -n network create secret generic pihole-admin \
    --from-file=password=/dev/stdin --dry-run=client -o yaml | \
  kubectl apply -f -
```

Kubernetes starts the waiting pod after the Secret appears. The same command safely updates the Secret during password rotation; restart the deployment after a rotation so the container reads the new value.

Discover service addresses:

```sh
kubectl get services -A
```

Default ports are:

- nginx homelab homepage: `8082` (Traefik owns port `80`)
- Jellyfin: `8096`
- Navidrome: `4533`
- SABnzbd: `8080`
- Pi-hole admin: `8081`
- Pi-hole DNS: TCP/UDP `53`

Point the router's LAN DNS setting at kilo's reserved address only after Pi-hole reports Ready. Keep a fallback/rescue DNS plan so a cluster outage does not lock you out of the network.

## Storage and availability notes

The bundled workloads are a useful initial deployment, not fully HA storage. Their PVCs use k3s's local-path provisioner. Jellyfin, Navidrome, and Pi-hole are pinned to `kilo`; SABnzbd becomes tied to the node where its local-path volume is provisioned. Back up the application volumes under `/var/lib/rancher/k3s/storage` and the media source independently.

For workload failover, install replicated storage (for example Longhorn) or use NAS-backed persistent volumes, then remove the `nodeSelector` entries from `kubernetes/homelab.yaml`. Pi-hole itself remains a single replica; a second independent DNS instance is recommended before making it the network's only resolver.
