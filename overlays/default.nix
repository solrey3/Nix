# Add custom overlays here.
#
# Example:
# final: prev: {
#   my-package = prev.callPackage ../pkgs/my-package { };
# }

final: prev: {
  aether = final.callPackage ../pkgs/aether { };
  cliamp = prev.cliamp.overrideAttrs (old: {
    patches = (old.patches or [ ]) ++ [
      ../pkgs/cliamp/jellyfin-pagination.patch
    ];
  });
  tensaku = final.callPackage ../pkgs/tensaku { };
}
