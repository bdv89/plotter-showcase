{ pkgs ? import <nixpkgs> {} }:

let
  pythonEnv = pkgs.python313.withPackages (ps: with ps; [
    pyqt5
    pandas
    numpy
    matplotlib
    openpyxl
    pyarrow
    scipy
  ]);
in
pkgs.mkShell {
  buildInputs = [
    pythonEnv
    pkgs.qt5.qtwayland
  ];

  shellHook = ''
    export QT_QPA_PLATFORM=wayland
    export QT_PLUGIN_PATH="${pkgs.qt5.qtwayland}/${pkgs.qt5.qtbase.qtPluginPrefix}:${pkgs.qt5.qtbase.bin}/${pkgs.qt5.qtbase.qtPluginPrefix}"
  '';
}
