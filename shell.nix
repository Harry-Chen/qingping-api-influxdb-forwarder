with import <nixpkgs> {};

let python-packages = ps: with ps; [
  influxdb
  requests
  schedule
  func-timeout
];

in

mkShell {
  packages = [
    (python3.withPackages python-packages)
  ];
}

