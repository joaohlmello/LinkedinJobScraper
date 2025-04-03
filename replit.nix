{pkgs}: {
  deps = [
    pkgs.geckodriver
    pkgs.zlib
    pkgs.xcodebuild
    pkgs.glibcLocales
    pkgs.postgresql
    pkgs.openssl
  ];
}
