{
  description = "Recipe book Django app";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    (flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs {
          inherit system;
          config.allowUnfree = true;
        };
        lib = pkgs.lib;
        python = pkgs.python312;

        pythonEnv = python.withPackages (ps: [
          ps.django
          ps.gunicorn
          ps.whitenoise
        ]);

        # Source filtered to exclude dev/build cruft from the Nix store.
        src = lib.cleanSourceWith {
          src = ./.;
          filter = path: _type:
            let base = baseNameOf path; in
            !(lib.elem base [
              ".venv" ".git" ".direnv" "staticfiles" "result"
              "__pycache__" "db.sqlite3" "node_modules" ".idea"
            ]);
        };

        # Derivation that collects static files (Django admin CSS/JS) at build time.
        appSrc = pkgs.stdenv.mkDerivation {
          pname = "recipe-book-app";
          version = "0.1.0";
          inherit src;
          nativeBuildInputs = [ pythonEnv ];
          dontConfigure = true;

          buildPhase = ''
            runHook preBuild
            export HOME=$TMPDIR
            export DJANGO_SETTINGS_MODULE=config.settings
            export DJANGO_DEBUG=False
            export DJANGO_SECRET_KEY=build-time-only-not-secret
            export RECIPE_BOOK_STATIC_ROOT=$PWD/staticfiles
            python manage.py collectstatic --noinput
            runHook postBuild
          '';

          installPhase = ''
            runHook preInstall
            mkdir -p $out/share/recipe-book
            cp -r accounts config find_recipes grocery ingredients \
                  recipes shops tags templates manage.py staticfiles \
                  $out/share/recipe-book/
            runHook postInstall
          '';
        };

        appHome = "${appSrc}/share/recipe-book";

        # Shell preamble shared by both wrappers. Env vars are overridable so
        # the systemd service (or a manual run) can point to a writable state dir.
        commonEnv = ''
          export DJANGO_SETTINGS_MODULE=config.settings
          export PYTHONPATH=${appHome}''${PYTHONPATH:+:$PYTHONPATH}
          export RECIPE_BOOK_STATIC_ROOT=''${RECIPE_BOOK_STATIC_ROOT:-${appHome}/staticfiles}
          export RECIPE_BOOK_STATE_DIR=''${RECIPE_BOOK_STATE_DIR:-$PWD}
          export RECIPE_BOOK_DB_PATH=''${RECIPE_BOOK_DB_PATH:-$RECIPE_BOOK_STATE_DIR/db.sqlite3}
        '';

        manageBin = pkgs.writeShellApplication {
          name = "recipe-book-manage";
          runtimeInputs = [ pythonEnv ];
          text = ''
            ${commonEnv}
            exec python ${appHome}/manage.py "$@"
          '';
        };

        # Runs migrations then starts gunicorn; WhiteNoise serves static files.
        serverBin = pkgs.writeShellApplication {
          name = "recipe-book-server";
          runtimeInputs = [ pythonEnv ];
          text = ''
            ${commonEnv}
            export DJANGO_DEBUG=''${DJANGO_DEBUG:-False}
            BIND=''${RECIPE_BOOK_BIND:-0.0.0.0:8000}
            WORKERS=''${RECIPE_BOOK_WORKERS:-3}

            mkdir -p "$RECIPE_BOOK_STATE_DIR"
            echo "recipe-book: migrating (db: $RECIPE_BOOK_DB_PATH)"
            python ${appHome}/manage.py migrate --noinput
            echo "recipe-book: serving on $BIND ($WORKERS workers)"
            exec gunicorn config.wsgi:application \
              --chdir ${appHome} --bind "$BIND" --workers "$WORKERS"
          '';
        };

        recipeBook = pkgs.symlinkJoin {
          name = "recipe-book-0.1.0";
          paths = [ serverBin manageBin ];
        };
      in
      {
        packages = {
          default = recipeBook;
          recipe-book = recipeBook;
          app = appSrc;
          pythonEnv = pythonEnv;
        };

        # `nix run`           → boots the server (auto-migrates on startup)
        # `nix run .#manage -- createsuperuser` → manage.py passthrough
        apps = {
          default = {
            type = "app";
            program = "${recipeBook}/bin/recipe-book-server";
          };
          manage = {
            type = "app";
            program = "${recipeBook}/bin/recipe-book-manage";
          };
        };

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
      }))

    // {
      # NixOS module — add to your server's configuration.nix:
      #   inputs.recipe-book.url = "github:you/recipe-book";
      #   imports = [ inputs.recipe-book.nixosModules.default ];
      #   services.recipeBook.enable = true;
      nixosModules.default = { config, pkgs, lib, ... }:
        let cfg = config.services.recipeBook;
        in {
          options.services.recipeBook = {
            enable = lib.mkEnableOption "Recipe book Django app";
            package = lib.mkOption {
              type = lib.types.package;
              default = self.packages.${pkgs.stdenv.hostPlatform.system}.default;
              description = "The recipe-book package to run.";
            };
            bind = lib.mkOption {
              type = lib.types.str;
              default = "127.0.0.1:8000";
              description = "host:port gunicorn binds to.";
            };
            workers = lib.mkOption {
              type = lib.types.int;
              default = 3;
            };
            allowedHosts = lib.mkOption {
              type = lib.types.listOf lib.types.str;
              default = [ "localhost" "127.0.0.1" ];
              description = "Django ALLOWED_HOSTS (comma-joined into the env var).";
            };
            secretKeyFile = lib.mkOption {
              type = lib.types.nullOr lib.types.path;
              default = null;
              description = "Path to a file containing the Django SECRET_KEY.";
            };
          };

          config = lib.mkIf cfg.enable {
            systemd.services.recipe-book = {
              description = "Recipe book";
              wantedBy = [ "multi-user.target" ];
              after = [ "network.target" ];
              environment = {
                DJANGO_DEBUG = "False";
                ALLOWED_HOSTS = lib.concatStringsSep "," cfg.allowedHosts;
                RECIPE_BOOK_BIND = cfg.bind;
                RECIPE_BOOK_WORKERS = toString cfg.workers;
                RECIPE_BOOK_STATE_DIR = "/var/lib/recipe-book";
                RECIPE_BOOK_DB_PATH = "/var/lib/recipe-book/db.sqlite3";
              };
              serviceConfig = {
                ExecStart = pkgs.writeShellScript "recipe-book-start" ''
                  ${lib.optionalString (cfg.secretKeyFile != null) ''
                    DJANGO_SECRET_KEY="$(cat ${cfg.secretKeyFile})"
                    export DJANGO_SECRET_KEY
                  ''}
                  exec ${cfg.package}/bin/recipe-book-server
                '';
                DynamicUser = true;
                StateDirectory = "recipe-book";
                Restart = "on-failure";
                RestartSec = 2;
              };
            };
          };
        };
    };
}
