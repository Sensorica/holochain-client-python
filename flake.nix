{
    description = "Flake for Holochain client development";

    inputs = {
        holonix.url = "github:holochain/holonix?ref=main-0.6";
        nixpkgs.follows = "holonix/nixpkgs";
        flake-parts.follows = "holonix/flake-parts";
    };

    outputs = inputs: inputs.flake-parts.lib.mkFlake { inherit inputs; } {
        systems = builtins.attrNames inputs.holonix.devShells;
        perSystem = { inputs', pkgs, ... }: {
            devShells.default = pkgs.mkShell {
                inputsFrom = [ inputs'.holonix.devShells.default ];
                packages = [
                    (pkgs.python3.withPackages (python-pkgs: [
                        python-pkgs.pip
                        python-pkgs.poetry-core
                    ]))
                    pkgs.poetry
                    pkgs.nodejs_20
                    pkgs.maturin
                    pkgs.uv
                ];
                shellHook = ''
                  export PS1='\[\033[1;34m\][holonix:\w]\$\[\033[0m\] '
                '';
            };
        };
    };
}
