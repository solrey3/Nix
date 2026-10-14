{ lib, username, ... }:

{
  options.custom.fleet = {
    primaryUser = lib.mkOption {
      type = lib.types.strMatching "[a-z_][a-z0-9_-]*";
      default = username;
      description = "Primary interactive and deployment account.";
    };
    headless = lib.mkEnableOption "the portable, headless Home Manager profile";
    nas = {
      host = lib.mkOption {
        type = lib.types.str;
        default = "illmatic";
        description = "NAS hostname for cluster NFS mounts.";
      };
      lanHost = lib.mkOption {
        type = lib.types.str;
        default = "illmatic.local";
        description = "LAN NAS hostname for exports restricted to LAN clients.";
      };
      exportRoot = lib.mkOption {
        type = lib.types.str;
        default = "/volume1";
        description = "NAS NFS export root.";
      };
      mountRoot = lib.mkOption {
        type = lib.types.str;
        default = "/mnt/illmatic";
        description = "Local root for mounted NAS shares.";
      };
    };
  };
}
