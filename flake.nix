{
  description = "Skin Gacha";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-26.05";
    uv2nix.url = "github:pyproject-nix/uv2nix";
    pyproject-nix.url = "github:pyproject-nix/pyproject.nix";
    pyproject-build-systems.url = "github:pyproject-nix/build-system-pkgs";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs =
    {
      self,
      nixpkgs,
      uv2nix,
      pyproject-nix,
      pyproject-build-systems,
      flake-utils,
      ...
    }:
    flake-utils.lib.eachDefaultSystem (
      system:
      let
        pkgs = import nixpkgs { inherit system; };
        workspace = uv2nix.lib.workspace.loadWorkspace { workspaceRoot = ./.; };

        uvOverlay = workspace.mkPyprojectOverlay {
          sourcePreference = "wheel";
        };

        pythonSet =
          (pkgs.callPackage pyproject-nix.build.packages {
            python = pkgs.python3;
          }).overrideScope
            (
              pkgs.lib.composeManyExtensions [
                pyproject-build-systems.overlays.default
                uvOverlay
              ]
            );

        virtualenv = pythonSet.mkVirtualEnv "dev-env" workspace.deps.all;
      in
      {
        packages.default = pkgs.stdenv.mkDerivation {
          pname = "skin-gacha";
          version = "0.5.0";
          src = ./.;
          dontBuild = true;
          dontConfigure = true;

          nativeBuildInputs = [ pkgs.makeWrapper ];

          installPhase = ''
            mkdir -p $out/share/osu-gacha
            mkdir -p $out/bin
            cp -r main.py assets $out/share/osu-gacha/
            makeWrapper ${virtualenv}/bin/python $out/bin/osu-gacha \
              --add-flags "$out/share/osu-gacha/main.py" \
              --chdir "$out/share/osu-gacha" \
              --prefix PYTHONPATH : "${pkgs.python3Packages.tkinter}/${pkgs.python3.sitePackages}:$out/share/osu-gacha" \
              --set TCL_LIBRARY "${pkgs.tcl}/lib/tcl${pkgs.lib.versions.majorMinor pkgs.tcl.version}" \
              --set TK_LIBRARY "${pkgs.tk}/lib/tk${pkgs.lib.versions.majorMinor pkgs.tk.version}"
          '';
        };
        devShells.default = pkgs.mkShell {
          packages = [
            pkgs.gnumake
            pkgs.ninja
            virtualenv
            pkgs.uv
          ];
        };
      }
    );
}
