{
  description = "Skin Gacha";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-26.05";
    uv2nix.url = "github:pyproject-nix/uv2nix";
    pyproject-nix.url = "github:pyproject-nix/pyproject.nix";
    pyproject-build-systems.url = "github:pyproject-nix/build-system-pkgs";
  };

  outputs =
    {
      self,
      nixpkgs,
      uv2nix,
      pyproject-nix,
      pyproject-build-systems,
      ...
    }:
    let
      supportedSystems = [
        "x86_64-linux"
      ];
      forEachSupportedSystem =
        f:
        nixpkgs.lib.genAttrs supportedSystems (
          system:
          let
            pkgs = import nixpkgs { inherit system; };
            tclLib = "${pkgs.tcl}/lib/tcl${pkgs.lib.versions.majorMinor pkgs.tcl.version}";
            tkLib = "${pkgs.tk}/lib/tk${pkgs.lib.versions.majorMinor pkgs.tk.version}";
            tkinterPath = "${pkgs.python3Packages.tkinter}/${pkgs.python3.sitePackages}";
          in
          f {
            inherit
              pkgs
              tclLib
              tkLib
              tkinterPath
              ;
          }
        );
    in
    {
      devShells = forEachSupportedSystem (
        {
          pkgs,
          tclLib,
          tkLib,
          tkinterPath,
        }:
        {
          default = pkgs.mkShell {
            packages = with pkgs; [
              tk
              tcl
              stdenv.cc.cc.lib
              zlib
              gnumake
              uv
            ];

            shellHook = ''
              python3 -m venv .venv
              unset PYTHONPATH
              export TCL_LIBRARY="${tclLib}"
              export TK_LIBRARY="${tkLib}"
              export PYTHONPATH="${tkinterPath}"
            '';
          };
        }
      );

      packages = forEachSupportedSystem (
        {
          pkgs,
          tclLib,
          tkLib,
          tkinterPath,
        }:
        {
          default = pkgs.stdenv.mkDerivation {
            pname = "skin-gacha";
            version = "0.5.0";
            src = ./.;

            nativeBuildInputs = with pkgs; [
              makeWrapper
              python3
            ];

            installPhase = ''
              python3 -m venv .venv
              mkdir -p $out/bin
              makeWrapper $out/bin/python $out/bin/skin-gacha \
                --add-flags "$src/main.py" \
                --prefix PYTHONPATH : "${tkinterPath}:$src" \
                --set TCL_LIBRARY "${tclLib}" \
                --set TK_LIBRARY "${tkLib}"
            '';
          };
        }
      );
    };
}
