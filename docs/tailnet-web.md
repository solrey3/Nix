# Private HTTPS for homelab web applications

Desired endpoints (Tailscale connected, subject to tailnet access policy):

- https://jellyfin.tail32b131.ts.net
- https://navidrome.tail32b131.ts.net
- https://sabnzbd.tail32b131.ts.net
- https://pihole.tail32b131.ts.net/admin/

The Tailscale Kubernetes operator provisions one standalone ingress proxy per
application and manages HTTPS certificates. No Funnel is enabled. TLS terminates
at the proxy; proxy-to-application traffic stays HTTP inside the cluster.
Application authentication remains enabled. Certificate hostnames appear in public
certificate transparency logs, but the services are not publicly reachable.

The rendered `kubernetes/homelab.yaml.in` removes LAN LoadBalancer/NodePort access to the three
media web services and removes only the HTTP port from Pi-hole's LoadBalancer.
Pi-hole LAN DNS (TCP/UDP 53) and the nginx homepage (8082) are unchanged.
Cluster administrators and cluster workloads can still reach the internal HTTP
services; this is not namespace isolation via NetworkPolicy.

## 1. Tailscale admin setup

In https://login.tailscale.com/admin/dns, enable MagicDNS and HTTPS certificates.

Merge these entries into the existing access policy; do not replace existing
cluster rules or replace the entire `grants` list. These are additional permissions,
not a complete policy: SSH/management and inter-node k3s traffic must remain
permitted. Replacing existing grants with only TCP 443 breaks the cluster.
Do not add a new blanket allow-all rule:

```json
{
  "tagOwners": {
    "tag:k8s-operator": ["autogroup:admin"],
    "tag:k8s": ["tag:k8s-operator"]
  },
  "grants": [
    {
      "src": ["autogroup:member"],
      "dst": ["tag:k8s"],
      "ip": ["tcp:443"]
    }
  ]
}
```

This allows tailnet members to access the four HTTPS endpoints. Replace the source
with a narrower user/group if desired. Grants are additive: existing broad access
rules must be reviewed separately if you want to restrict particular tailnet users.
Do not grant Funnel permissions for these proxies.

Create an OAuth client under **Settings → Trust credentials** (OAuth clients in
older consoles), tagged `tag:k8s-operator`, with write access to:

- General → Services
- Devices → Core
- Keys → Auth Keys

Keep the credentials in 1Password. Do not paste them into chat, commit them, put
them in Helm values, or pass the secret as a command-line argument.

## 2. Provision the secret

On `kilo`, run the following interactively. The secret is read through stdin and
never written to a local file or included in command arguments:

```sh
set -o pipefail
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
kubectl create namespace tailscale --dry-run=client -o yaml | kubectl apply -f -
read -r -p 'OAuth client ID: ' CLIENT_ID
systemd-ask-password 'Tailscale OAuth client secret:' | tr -d '\n' | \
  kubectl -n tailscale create secret generic operator-oauth \
    --from-literal=client_id="$CLIENT_ID" \
    --from-file=client_secret=/dev/stdin \
    --dry-run=client -o yaml | kubectl apply -f -
unset CLIENT_ID
```

The secret remains in Kubernetes/etcd and backups; protect these accordingly.

## 3. Stage and verify before removing LAN web access

From a checkout on kilo, install the operator and ingresses **without applying the
changed homelab services yet**:

```sh
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
kubectl apply -f kubernetes/tailscale-operator.yaml
kubectl -n tailscale rollout status deployment/operator --timeout=300s
kubectl apply -f kubernetes/tailnet-web.yaml
kubectl get ingress -A
kubectl -n tailscale get pods
```

If the deployment does not yet exist, wait for k3s's Helm install job to finish and
retry the rollout command. Approve the operator/proxy machines in Tailscale if the
tailnet requires device approval. Check `kubectl -n kube-system get helmchart` and
`kubectl -n tailscale logs deployment/operator` if installation stalls.

In SABnzbd's existing UI, add `sabnzbd.tail32b131.ts.net` to its hostname whitelist
(Config → General → Host Whitelist) if required. Keep hostname protection enabled.

From a Tailscale-connected client, open every endpoint and verify login, Jellyfin
playback, Navidrome playback, SABnzbd access, and Pi-hole administration. A curl
check must succeed with normal certificate validation (do not use `-k`).

## 4. Cut over and persist

Only after all HTTPS endpoints work, deploy kilo's updated NixOS configuration:

```sh
sudo nixos-rebuild switch --flake .#kilo
```

The k3s module installs all three manifests persistently. Ensure new files are
included in the flake source (Git flakes omit untracked files). Do not rebuild
before credentials and verification are complete: the new homelab manifest removes
LAN HTTP access immediately.

Confirm `kubectl -n media get svc` shows `ClusterIP` for Jellyfin, Navidrome, and
SABnzbd, and `kubectl -n network get svc pihole` exposes only TCP/UDP 53. Verify
old LAN URLs and old NodePorts no longer connect on **all three nodes**, and verify
Pi-hole DNS still works from a LAN client. New HTTPS URLs should fail from a
LAN-only client with Tailscale disconnected (and no tailnet subnet routing).

The homepage ConfigMap links use the new URLs; kubelet propagates that mounted
ConfigMap asynchronously. Client apps/bookmarks must also use the new URLs.

For emergency recovery, restore the three services to `LoadBalancer` and Pi-hole's
HTTP service port to 8081 in the declarative manifest, then redeploy kilo. This
intentionally restores LAN web exposure; do not disable TLS verification instead.

## Live cutover: 2026-10-25

- OAuth credentials were read from the 1Password item `Tailscale Credential` and
  provisioned directly into `tailscale/operator-oauth` without displaying them.
- Operator 1.104.2 and all four standalone ingress proxies are running.
- All four HTTPS URLs returned HTTP 200 with certificate verification enabled.
- SABnzbd's persisted hostname whitelist includes its new full MagicDNS name.
- All 24 checks of old web ports and NodePorts across the three LAN node addresses
  were closed/unreachable from kilo. Pi-hole answered DNS queries over TCP and UDP.
- Media/application pods were not restarted. Login and media playback still need
  user verification; these checks verified HTTP access, not authenticated sessions.
- The existing unrestricted tailnet grant was restored after an HTTPS-only grant
  accidentally blocked SSH and inter-node traffic. Access is currently allowed to
  all tailnet peers; do not replace cluster/management rules when tightening it.

The user subsequently confirmed the new endpoints work.

To avoid deploying unrelated NixOS changes, the live cutover updated the manifests
in `/var/lib/rancher/k3s/server/manifests` directly. The homelab manifest preserves
all pre-existing application definitions and changes only the web services and
homepage links. Its former Nix-store symlink and contents were backed up outside
the watched directory at:

`/var/lib/rancher/k3s/manifest-backups/tailnet-web-20261025/`

These files survive reboot, but the installed NixOS generation still references
the old homelab manifest. **The next NixOS deployment must include this repository's
updated k3s module and all three manifests.** Switching to an old configuration
can restore LAN HTTP exposure. No full NixOS rebuild was performed during cutover.

References:
- https://tailscale.com/docs/kubernetes-operator/install-operator
- https://tailscale.com/docs/kubernetes-operator/ingress
