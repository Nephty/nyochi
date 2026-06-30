{
  description = "Recipe book Django app dev shell";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs {
          inherit system;
          config.allowUnfree = true;
        };
      in
      {
        devShells.default = pkgs.mkShell {
          name = "recipe-book-shell";

          buildInputs = [
            pkgs.python312
            pkgs.python312Packages.pip
            pkgs.sqlite
            pkgs.git
            pkgs.claude-code
          ];

          shellHook = ''
            if [ ! -d .venv ]; then
              python -m venv .venv
            fi
            source .venv/bin/activate
            pip install -r requirements.txt -q
            mkdir -p db
            echo "Recipe book dev shell — run: python manage.py runserver"
          '';
        };
      });
}
