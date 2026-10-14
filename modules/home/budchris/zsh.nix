{ pkgs, ... }:

{
  programs.zsh = {
    enable = pkgs.stdenv.hostPlatform.isDarwin;
    enableCompletion = true;

    history = {
      append = true;
      ignoreDups = true;
      ignoreSpace = true;
      save = 100000;
      size = 100000;
    };

    initContent = ''
      # Ghostty advertises TERM=xterm-ghostty. On machines without that
      # terminfo entry, programs such as tmux fail with
      # "missing or unsuitable terminal: xterm-ghostty". Fall back to the
      # widely available xterm-256color entry when the current TERM is unknown.
      case "''${TERM-}" in
        xterm-ghostty|ghostty)
          if ! { command -v infocmp >/dev/null 2>&1 && infocmp "$TERM" >/dev/null 2>&1; }; then
            export TERM=xterm-256color
          fi
          ;;
      esac

      # Up/down arrows search history using the current input as a prefix.
      # Bind both common cursor-key encodings:
      #   \e[A / \e[B = normal cursor mode
      #   \eOA / \eOB = application cursor mode, common in tmux/Konsole/etc.
      autoload -Uz up-line-or-beginning-search down-line-or-beginning-search
      zle -N up-line-or-beginning-search
      zle -N down-line-or-beginning-search
      bindkey '^[[A' up-line-or-beginning-search
      bindkey '^[[B' down-line-or-beginning-search
      bindkey '^[OA' up-line-or-beginning-search
      bindkey '^[OB' down-line-or-beginning-search

      # Ctrl-r incremental reverse history search.
      bindkey '^R' history-incremental-search-backward
    '';
  };
}
