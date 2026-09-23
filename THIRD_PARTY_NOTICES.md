# Componentes de terceros

Local OCR utiliza componentes independientes, cada uno bajo su propia licencia. Sus avisos y archivos de licencia deben conservarse al redistribuirlos. Esta lista identifica componentes principales, no sustituye sus textos completos ni es un dictamen legal.

| Componente | Información oficial |
| --- | --- |
| PyMuPDF y MuPDF | [Licenciamiento AGPL/comercial](https://pymupdf.readthedocs.io/en/latest/about.html#license-and-copyright) |
| PySide6 y Qt | [Licencias Qt for Python](https://doc.qt.io/qtforpython-6/licenses.html) |
| OCRmyPDF | [Licencia del proyecto](https://github.com/ocrmypdf/OCRmyPDF/blob/main/LICENSE) |
| Tesseract y modelos | [Repositorio oficial](https://github.com/tesseract-ocr/tesseract), [modelos](https://github.com/tesseract-ocr/tessdata_fast) |
| LibreOffice | [Licencias](https://www.libreoffice.org/about-us/licenses/) |
| pathspec | [Repositorio oficial](https://github.com/cpburnz/python-pathspec) |
| PyInstaller | [Licencia](https://pyinstaller.org/en/stable/license.html) |

Tesseract y LibreOffice no están redistribuidos dentro del ejecutable generado por este repositorio; el usuario los instala aparte. El empaquetado incorpora bibliotecas Python y sus metadatos. Antes de publicar o distribuir una versión a terceros, revisa las condiciones de todos los componentes y decide la licencia del código propio. No se ha elegido una licencia por el propietario del repositorio.
