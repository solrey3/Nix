# Civilization V Enhanced User Interface (native Linux Steam build)

EUI is a DLC-style UI replacement, not a Steam Workshop mod. On this native Linux setup, v1.30p crashed when restarting or returning to the main menu even without mods; v1.29i is installed for testing instead. Download the ZIP from [CivFanatics](https://forums.civfanatics.com/resources/civ5-enhanced-user-interface.24303/) (the author's distribution page); do not commit or redistribute its contents. Quit Civ V before installing, then run:

```sh
./scripts/install-civ5-eui ~/Downloads/EUI*.zip
```

The installer replaces the previous EUI installation under `~/.local/share/Steam/steamapps/common/Sid Meier's Civilization V/steamassets/assets/dlc/ui_bc1`, lowercases all DLC filenames for Linux, installs EUI/CSL translations under `~/.local/share/Aspyr/Sid Meier's Civilization 5/Text`, and clears only the game's cache (not saves or mods). A different native Steam library can be selected with `--game-dir`. Steam file verification may remove EUI; rerun the installer afterward. To uninstall, remove `ui_bc1` and the `eui_text_*.xml` and `csl_text_*.xml` files from those paths and clear the game cache.

EUI doesn't appear in the DLC menu. On this machine, v1.29i works without mods, but Really Advanced Setup v15 produced missing tech-tree icons and Lua errors. Disabling EUI's TechTree was tested but broke Choose Research, so it has been restored. Avoid that partial-disable workaround; use EUI without Really Advanced Setup until the incompatibility is fixed. If a UI-changing mod conflicts, disable that mod or its corresponding EUI component; keep EUI's core/art files. EUI requires Civ V 1.0.3.144 or later. These paths apply to the native Linux version, **not** the Windows version under Proton.
