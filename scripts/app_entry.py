"""Entrada absoluta para PyInstaller; los imports del paquete conservan su contexto."""

from local_ocr.__main__ import main

if __name__ == "__main__":
    raise SystemExit(main())
