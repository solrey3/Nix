# Workshop display arrangement

Host: **oscar**, Hyprland. Automatically selected by the LG monitor's description/serial,
not its dock connector name (currently DP-4).

| Display | Identity | Mode | Position | Scale |
| --- | --- | --- | --- | --- |
| Laptop | eDP-1 / BOE 0x0791 | 1920×1080, 60 Hz | 0,0 (left) | 1 |
| External | LG Electronics LG ULTRAWIDE 0x000759BE | 2560×1080, 60 Hz | 1920,0 (right) | 1 |

The LG is marked XWayland primary at login and on monitor connection/removal.
This lets native Linux Civilization V enumerate the ultrawide resolution correctly.
On disconnect, the laptop becomes XWayland primary. Other monitors retain preferred
mode/automatic positioning. Implementation: `modules/home/budchris/workshop.nix`.

Apply with `sudo nixos-rebuild switch --flake .#oscar`, then `hyprctl reload`
to install the new Hyprland event handlers in the current session.

Blueman is enabled through `services.blueman` when Bluetooth is enabled. This
provides its manager, tray icons, D-Bus service and policy, rather than only
launching `blueman-applet` from the compositor.
