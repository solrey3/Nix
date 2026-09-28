{ inputs, pkgs, ... }:

let
  isLinux = pkgs.stdenv.hostPlatform.isLinux;

  # Copilot's keytar module needs libraries that are not on NixOS' default
  # dynamic linker path. macOS can use the regular Nixpkgs Node executable.
  copilotNode =
    if isLinux then
      let
        libraryPath = pkgs.lib.makeLibraryPath (with pkgs; [
          glib
          libei
          libjpeg
          libpng
          libsecret
          pipewire
          stdenv.cc.cc.lib
          libx11
          libxtst
        ]);
      in
      pkgs.writeShellScriptBin "copilot-node" ''
        export LD_LIBRARY_PATH="${libraryPath}:''${LD_LIBRARY_PATH:-}"
        exec ${pkgs.nodejs}/bin/node "$@"
      ''
    else
      pkgs.nodejs;

  copilotNodeCommand =
    if isLinux
    then "${copilotNode}/bin/copilot-node"
    else "${copilotNode}/bin/node";

  nvimConfig = pkgs.runCommand "budchris-nvim-config" { } ''
    cp -r ${inputs.lazyvim-starter} $out
    chmod -R u+w $out
    mkdir -p $out/lua/plugins

    # Keep personal keymaps in this repository rather than in mutable dotfiles.
    cp ${./nvim/keymaps.lua} $out/lua/config/keymaps.lua

    cat > $out/lua/plugins/copilot-native-libs.lua <<'EOF'
    -- The native modules bundled with LazyVim's copilot.lua need shared
    -- libraries on NixOS (notably libsecret for @github/keytar). Point
    -- Copilot at a wrapped node so the LSP always starts with that library
    -- path, independent of how Neovim was launched.
    return {
      {
        "zbirenbaum/copilot.lua",
        opts = function(_, opts)
          opts.copilot_node_command = "${copilotNodeCommand}"
          return opts
        end,
      },
    }
    EOF

    cat > $out/lua/plugins/completion.lua <<'EOF'
    -- Do not interrupt typing with automatic completion suggestions. Completion
    -- remains available on demand with Ctrl-Space.
    return {
      {
        "saghen/blink.cmp",
        opts = {
          completion = {
            menu = { auto_show = false },
          },
        },
      },
    }
    EOF

    cat > $out/lua/plugins/markdown.lua <<'EOF'
    -- Use Nixpkgs' marksman. Mason's downloaded marksman is a generic
    -- dynamically linked binary and does not run on NixOS without stub-ld.
    return {
      {
        "neovim/nvim-lspconfig",
        opts = {
          servers = {
            marksman = {
              mason = false,
              cmd = { "${pkgs.marksman}/bin/marksman", "server" },
            },
          },
        },
      },
    }
    EOF
  '';
in
{
  home.sessionVariables = {
    EDITOR = "nvim";
    VISUAL = "nvim";
  };

  home.packages = (with pkgs; [
    # LazyVim/runtime helpers
    gnumake
    copilotNode
    marksman
    nodejs
    python3
    tree-sitter
  ]) ++ pkgs.lib.optionals isLinux [ pkgs.wl-clipboard ];

  programs.neovim = {
    enable = true;
    defaultEditor = true;
    viAlias = true;
    vimAlias = true;
    withNodeJs = true;
    withPython3 = true;
    withRuby = false;
  };

  # Upstream LazyVim starter template plus local plugin overrides.
  # Plugins are managed by lazy.nvim on first launch.
  xdg.configFile."nvim" = {
    source = nvimConfig;
    recursive = true;
  };

  # Pin the exact plugin revisions from the current configuration. Update this
  # file intentionally after running :Lazy update in a writable checkout.
  xdg.configFile."nvim/lazy-lock.json" = {
    force = true;
    source = ./nvim/lazy-lock.json;
  };

  # Enable LazyVim's native Copilot and Markdown extras.
  xdg.configFile."nvim/lazyvim.json" = {
    force = true;
    text = builtins.toJSON {
      extras = [
        "lazyvim.plugins.extras.ai.copilot"
        "lazyvim.plugins.extras.lang.markdown"
      ];
      install_version = 8;
      version = 8;
    };
  };
}
