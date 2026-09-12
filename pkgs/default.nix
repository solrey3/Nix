# Add custom packages here.
#
# Example:
# { pkgs }:
# {
#   my-package = pkgs.callPackage ./my-package { };
# }

{ pkgs }:

{
  aether = pkgs.callPackage ./aether { };
  pi-console = pkgs.callPackage ./pi-console { };
  tensaku = pkgs.callPackage ./tensaku { };
}
