# Tango command center

`tango` is the DigitalOcean NixOS deployment console and private Pi web UI. Its initial public address is `143.198.8.152`; routine access should use Tailscale MagicDNS after enrollment.

## Install from the Ubuntu droplet

The install is destructive. Confirm DigitalOcean shows the system disk as `/dev/vda` before running it. The disko layout creates a GPT BIOS boot partition, encrypted 4 GiB swap, and an ext4 root filesystem using the remaining space.

The local install key is `~/.ssh/tango_install_ed25519`. Its public half must be present in `/root/.ssh/authorized_keys` on the Ubuntu droplet:

```text
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAILluiwZ/efnUYTmrf0lci6jIeQwYK7RbgcxGUIthlJYe tango-install
```

Use the DigitalOcean web console to add it if SSH access was not configured when the droplet was created. Then verify the target disk and firmware mode:

```sh
ssh -i ~/.ssh/tango_install_ed25519 root@143.198.8.152 \
  'lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINTS; test -d /sys/firmware/efi && echo UEFI || echo BIOS'
```

The checked-in layout expects `/dev/vda` and BIOS. If those differ, stop and update `hosts/tango/disk-config.nix` and the boot loader before installing.

```sh
nix run github:nix-community/nixos-anywhere -- \
  --flake path:.#tango \
  --target-host root@143.198.8.152 \
  -i ~/.ssh/tango_install_ed25519
```

After reboot:

```sh
ssh -i ~/.ssh/tango_install_ed25519 budchris@143.198.8.152
sudo tailscale up --hostname=tango
```

## Pi Console

The NixOS service runs the custom Pi SDK application on TCP 3210. That port is not opened on the public interface; it is reachable because `tailscale0` is trusted. Open:

```text
http://tango:3210
```

Each UI thread is a persistent Pi session. The target selector teaches the session to use `budchris@<target>` over Tailscale SSH, while `/srv/nixos` is tango's writable fleet checkout. The UI supports streaming responses, tool activity, aborting work, thread deletion, and mobile layouts.

Tango uses `modules/home/budchris/portable.nix` instead of the desktop Home Manager profile. This keeps browsers, compositors, graphical applications, fonts, and wallpapers out of the headless server closure while retaining the shell, Git, LazyVim, AI, and command-line tooling used for fleet maintenance.

The console uses `openai-codex/gpt-5.6-sol` at medium reasoning by default. If a run fails because the primary model is unavailable, it switches that thread to `openrouter/moonshotai/kimi-k3` at medium reasoning and continues the request from the existing conversation state.

Inspect it with:

```sh
systemctl status pi-console
journalctl -u pi-console -f
```

## Model authentication and 1Password secrets

Pi Console runs as the separate `pi-console` account and reads `/var/lib/pi-console/.pi/agent/auth.json`. If OpenAI Codex and OpenRouter were configured through Pi as `budchris`, seed the console account once without printing the credentials:

```sh
sudo install -D -o pi-console -g pi-console -m 0600 \
  /home/budchris/.pi/agent/auth.json \
  /var/lib/pi-console/.pi/agent/auth.json
sudo systemctl restart pi-console
```

The copied file is then owned and refreshed independently by the service. Alternatively, authenticate while running Pi directly as the service account.

For the OpenRouter API key, a 1Password service account can provide `OPENROUTER_API_KEY` at service startup. Place its token and an `op run` environment template in the service state directory:

```sh
sudo install -o pi-console -g pi-console -m 0700 -d /var/lib/pi-console
sudo install -o pi-console -g pi-console -m 0600 \
  /etc/pi-console/secrets.env.example /var/lib/pi-console/secrets.env.tpl
sudoedit /var/lib/pi-console/secrets.env.tpl
sudoedit /var/lib/pi-console/op-service-account.env
sudo chown pi-console:pi-console /var/lib/pi-console/{secrets.env.tpl,op-service-account.env}
sudo chmod 0600 /var/lib/pi-console/{secrets.env.tpl,op-service-account.env}
sudo systemctl restart pi-console
```

`op-service-account.env` contains one line:

```text
OP_SERVICE_ACCOUNT_TOKEN=<service-account-token>
```

Keep only `op://...` references in `secrets.env.tpl`; never put resolved API keys in the repository. OpenAI Codex OAuth remains in `/var/lib/pi-console/.pi/agent/auth.json`. If the 1Password files are absent, both providers use Pi's normal credential discovery from that file.

## Fleet deployment key

Pi Console runs as the `pi-console` service user. Give that user a dedicated SSH private key from 1Password which is authorized on each target:

```sh
sudo install -d -o pi-console -g pi-console -m 0700 /var/lib/pi-console/.ssh
# Resolve the key without echoing it to the terminal. Adjust the item reference.
sudo -u pi-console env HOME=/var/lib/pi-console bash -c '
  set -a
  source /var/lib/pi-console/op-service-account.env
  set +a
  op read "op://Homelab/Tango Deploy Key/private key"
' | sudo tee /var/lib/pi-console/.ssh/id_ed25519 >/dev/null
sudo chown pi-console:pi-console /var/lib/pi-console/.ssh/id_ed25519
sudo chmod 0600 /var/lib/pi-console/.ssh/id_ed25519
```

Test MagicDNS and key authorization:

```sh
sudo -u pi-console ssh -o StrictHostKeyChecking=accept-new budchris@bravo hostname
```

## deploy-rs

Every generated NixOS configuration is a deploy-rs node with its Tailscale hostname. Darwin and standalone Home Manager outputs are not deploy-rs nodes. Builds run on targets:

```sh
deploy .#bravo

deploy .#kilo .#lima .#mike

deploy                       # entire fleet; use deliberately
```

The target `budchris` user is trusted by Nix and has passwordless sudo through the shared user module. The k3s hardware files are machine-specific and must be regenerated after a reinstall or hardware replacement, as described in `docs/k3s-cluster.md`. Foxtrot's hardware file remains a placeholder and must not be activated as-is.
