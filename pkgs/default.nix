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
  tensaku = pkgs.callPackage ./tensaku { };
}
