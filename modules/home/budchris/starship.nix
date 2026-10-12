{ pkgs, ... }:

{
  programs.starship = {
    enable = true;
    enableBashIntegration = true;
    enableZshIntegration = pkgs.stdenv.hostPlatform.isDarwin;

    settings = {
      add_newline = true;
      format = "$all$character";

      character = {
        success_symbol = "[❯](bold green)";
        error_symbol = "[❯](bold red)";
        vimcmd_symbol = "[❮](bold green)";
      };

      directory = {
        truncation_length = 3;
        truncate_to_repo = true;
      };

      git_branch.symbol = " ";
      nix_shell.symbol = " ";
      docker_context.symbol = " ";
    };
  };
}
