# Workshop display arrangement

Host: **oscar**, Hyprland. External displays are matched by description/serial,
not their dock connector names, which can change when reconnecting.

| Display | Identity | Mode | Position | Scale |
| --- | --- | --- | --- | --- |
| Laptop | eDP-1 / BOE 0x0791 | 1920×1080, 60 Hz | 0,0 (left) | 1 |
| LG ultrawide | LG Electronics LG ULTRAWIDE 0x000759BE | 2560×1080, 60 Hz | 1920,0 (center) | 1 |
| HP 25f | HP Inc. HP 25f 3CM8240RX0 | 1920×1080, 60 Hz | 4480,0 (right) | 1 |

Default workspaces run left-to-right: **1** on the laptop, **2** on the LG,
and **3** on the HP. These workspaces are persistent and bound to display identities.

The LG is marked XWayland primary at login and on monitor connection/removal.
This lets native Linux Civilization V enumerate the ultrawide resolution correctly.
On disconnect, the laptop becomes XWayland primary. Other monitors retain preferred
mode/automatic positioning. Implementation: `modules/home/budchris/workshop.nix`.

Apply with `sudo nixos-rebuild switch --flake .#oscar`, then `hyprctl reload`
to install the new Hyprland event handlers in the current session.

Blueman is enabled through `services.blueman` when Bluetooth is enabled. This
provides its manager, tray icons, D-Bus service and policy, rather than only
launching `blueman-applet` from the compositor.
