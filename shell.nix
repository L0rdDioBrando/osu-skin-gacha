{
  pkgs ? import <nixpkgs> { },
}:

pkgs.mkShell {
  buildInputs = with pkgs; [
    (python3.withPackages (
      ps: with ps; [
        tkinter
        customtkinter
        requests
        pillow
        pyinstaller
        beautifulsoup4
        pygame-ce
        mutagen
        pysocks
        keyring
        secretstorage
      ]
    ))
    python3
    python3Packages.tkinter
    tk
    tcl
    stdenv.cc.cc.lib
    zlib
    gnumake
  ];
  shellHook = ''
    export TCL_LIBRARY="${pkgs.tcl}/lib/tcl${pkgs.lib.versions.majorMinor pkgs.tcl.version}"
    export TK_LIBRARY="${pkgs.tk}/lib/tk${pkgs.lib.versions.majorMinor pkgs.tk.version}"
    python -m venv --system-site-packages .venv
    source .venv/bin/activate
  '';
}
