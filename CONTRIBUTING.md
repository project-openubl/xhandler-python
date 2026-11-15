# Contribuir a xhandler-python

## Requisitos

- Python 3.10 o superior y [uv](https://docs.astral.sh/uv/).
- Para cambiar el núcleo: un checkout de
  [xhandler-rust](https://github.com/project-openubl/xhandler-rust) junto a este (revisa
  [su CONTRIBUTING.md](https://github.com/project-openubl/xhandler-rust/blob/main/CONTRIBUTING.md)).

## Comandos

```shell
uv sync
make test                                          # uv run pytest
make lint                                          # ruff check, ruff format --check, mypy
uv run pytest tests/test_xsender.py -k token       # un archivo, los tests que coinciden con un nombre
XHANDLER_E2E=true uv run pytest tests/test_e2e.py  # crea, firma y envía una factura a la SUNAT beta
```

## Hacer un cambio

- Crear, firmar, armar las peticiones a la SUNAT y leer sus respuestas ocurre en el núcleo de
  Rust (`src/xhandler/_core/xhandler.wasm`). Esos cambios van en xhandler-rust; luego aquí:

  ```shell
  make sync RUST_REPO=../xhandler-rust   # el núcleo de tu checkout, para desarrollar
  make sync CORE=6.0.0-alpha.1           # el núcleo de una versión de xhandler-rust
  ```

  `make sync` copia el núcleo, los modelos (`src/xhandler/xbuilder/models.py`) y el corpus de
  conformidad (`testdata/conformance/`). No los edites a mano. La versión del paquete es la del
  núcleo, y una versión solo se publica con el núcleo de la versión igual de xhandler-rust:
  `make verify-core` lo comprueba.
  Estos comandos descargan el `core.sh` de xhandler-rust (`xhandler-wasm/core.sh`) del tag del
  núcleo; `CORE_SH=<ruta>` usa una copia local, p. ej. al cambiarlo allá.
- En Python está lo que necesita IO: el cliente HTTP (httpx), los reintentos y el caché de tokens
  (`src/xhandler/xsender/`).
- Los nombres (`FileSender`, `SunatClient`, `SigningKey`...) se mantienen iguales en Go, Python y
  Java.

## Pull requests

- Título con [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`,
  `docs:`...); los cambios incompatibles llevan `!`.
- Deben pasar `lint` y `test` (Python 3.10 a 3.14 en Linux; macOS y Windows).

Al contribuir aceptas que tus contribuciones se distribuyan bajo la
[Apache License, Version 2.0](https://www.apache.org/licenses/LICENSE-2.0).
