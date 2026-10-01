# Tango command center

`tango` is the DigitalOcean NixOS deployment console. Its initial public address is `143.198.8.152`; routine access should use Tailscale MagicDNS after enrollment.

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

## Command-line administration

Tango uses `modules/home/budchris/portable.nix` instead of the desktop Home Manager profile. This keeps browsers, compositors, graphical applications, fonts, and wallpapers out of the headless server closure while retaining the shell, Git, LazyVim, AI, and command-line tooling used for fleet maintenance.

After a fresh installation, create the writable fleet checkout:

```sh
sudo git clone https://github.com/solrey3/Nix.git /srv/nixos
sudo chown -R budchris:users /srv/nixos
cd /srv/nixos
```

Use Pi interactively from this checkout when agent assistance is needed. Keep model credentials in the user's normal Pi configuration and secrets in 1Password.

## deploy-rs

Every generated NixOS configuration is a deploy-rs node with its Tailscale hostname. Darwin and standalone Home Manager outputs are not deploy-rs nodes. Builds run on targets:

```sh
deploy .#bravo

deploy .#kilo .#lima .#mike

deploy                       # entire fleet; use deliberately
```

The target `budchris` user is trusted by Nix and has passwordless sudo through the shared user module. The k3s hardware files are machine-specific and must be regenerated after a reinstall or hardware replacement, as described in `docs/k3s-cluster.md`. Foxtrot's hardware file remains a placeholder and must not be activated as-is.
