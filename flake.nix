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
          nativeBuildInputs = [
            pkgs.makeWrapper
            pkgs.python313Packages.tkinter
          ];
          dependencies = with pkgs.python3Packages; [
            tkinter
          ];
          makeWrapperArgs = [
            "--set TCL_LIBRARY ${pkgs.tcl}/lib/tcl${pkgs.lib.versions.majorMinor pkgs.tcl.version}"
            "--set TK_LIBRARY ${pkgs.tk}/lib/tk${pkgs.lib.versions.majorMinor pkgs.tk.version}"
          ];
          installPhase = ''
            mkdir -p $out/share/skin-gacha $out/bin
            cp -r main.py assets modules $out/share/skin-gacha/
            makeWrapper ${virtualenv}/bin/python $out/bin/skin-gacha \
              --add-flags "$out/share/skin-gacha/main.py" \
              --chdir "$out/share/skin-gacha"
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
