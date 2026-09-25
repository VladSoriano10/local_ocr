# VladTor · Local OCR

Aplicación de escritorio en español para Windows. Genera un **PDF con texto seleccionable y un Markdown** a partir de PDF o Word, y prepara **proyectos de código como contexto Markdown para LLM**. El procesamiento es local: sin APIs de IA, cuentas, tokens de pago ni subida de archivos.

Primera versión funcional: **0.1.0**, con interfaz **Dualidad**. No es una página web ni requiere un servidor. La instalación inicial descarga dependencias; después funciona sin internet si los componentes e idiomas necesarios están instalados.

## Qué incluye

| Entrada | Salida | Tratamiento |
| --- | --- | --- |
| PDF con texto, sin imágenes | Copia del PDF + `.md` | Conserva el PDF sin repetir OCR |
| PDF escaneado | PDF buscable + `.md` | OCR local con Tesseract y OCRmyPDF |
| PDF mixto | PDF buscable + `.md` | El modo automático conserva texto nativo y reconoce texto de imágenes |
| Word `.docx` o `.doc` | PDF buscable + `.md` | Convierte con LibreOffice y aplica el mismo flujo PDF/OCR |
| Carpeta de código | Markdown completo o dividido, resumen e informe | Filtra, permite seleccionar y organiza código sin ejecutarlo |

Arrastrar documentos, lotes, español/inglés, imágenes opcionales, detección básica de tablas, selección por árbol, vista previa de código, cancelación, diagnóstico de dependencias y botón para abrir resultados. Todo se publica en carpetas nuevas; no se sobrescriben originales ni resultados anteriores.

## Interfaz Dualidad y punto de control

La interfaz toma la idea de ángeles y demonios: alas con plumas y halo azul/dorado para documentos, membrana y cuerno en rojo/cobre para proyectos, y violeta para ajustes. Es una aplicación nativa; el diseño no descarga fuentes, scripts ni estilos desde internet.

- **Documentos OCR:** configuración a la izquierda, cola y vista del Markdown generado a la derecha. Puedes abrir el PDF, abrir el Markdown o copiar el texto visible. La vista se limita a 100.000 caracteres; el archivo completo se conserva en disco.
- **Proyectos de código:** árbol seleccionable, vista previa y límite estimado por parte.
- **Ajustes y diagnóstico:** consulta real de componentes e idiomas. El registro de operaciones se puede desplegar.

La interfaz anterior está conservada en la rama [checkpoint/interfaz-original](https://github.com/VladSoriano10/local_ocr/tree/checkpoint/interfaz-original). Puedes abrir esa rama y descargar su ZIP para compararla sin reemplazar la versión nueva. El punto de control contiene el programa completo.

[Comparación visual de ambas interfaces](docs/interfaz.md).

## Opción 1 — Usar el ejecutable de Windows

1. En GitHub abre **Actions → Compilar Windows**.
2. Abre una ejecución **correcta** y descarga el artefacto **LocalOCR-Windows-x64** al final de la página. Los artefactos se conservan 14 días; puedes volver a ejecutar con **Run workflow**.
3. Extrae **todo** el ZIP en una carpeta y abre `LocalOCR.exe`. No muevas solo el `.exe`: necesita `_internal`.
4. Instala Tesseract para escaneos y LibreOffice para Word como se indica abajo. El ejecutable contiene Python y las bibliotecas Python, **no** esos dos programas externos.

Esta compilación no tiene firma de un editor verificado. Descárgala solo de este repositorio y comprueba el origen; no desactives el antivirus. El ZIP se publica únicamente si pasan las pruebas, incluida una conversión OCR con el ejecutable empaquetado.

## Opción 2 — Ejecutar desde el código

No tienes que cerrar tu proyecto actual en VS Code. Puedes descargar el ZIP del repositorio y ejecutar los `.bat`, o abrir esta carpeta en otra ventana.

1. Instala **Python 3.12 de 64 bits** desde [python.org](https://www.python.org/downloads/windows/), incluido Python Launcher (`py`).
2. Descarga el repositorio con **Code → Download ZIP** y extrae su contenido.
3. Haz doble clic en `Instalar.bat`. Crea un entorno `.venv` dentro de esta carpeta e instala dependencias, sin alterar tus otros proyectos.
4. Haz doble clic en `Iniciar.bat`. Si hay un error al abrir, usa `Iniciar_con_registro.bat` para ver el mensaje.

Desde una terminal, el equivalente es:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m local_ocr
```

### Componentes externos para documentos

**Tesseract OCR de 64 bits** y **LibreOffice** se instalan una sola vez. En Windows con winget:

```powershell
winget install -e --id tesseract-ocr.tesseract
winget install -e --id TheDocumentFoundation.LibreOffice
```

Si winget no encuentra un paquete, utiliza las rutas de instalación oficiales: [Tesseract](https://tesseract-ocr.github.io/tessdoc/Installation.html) y [LibreOffice](https://www.libreoffice.org/download/download-libreoffice/). Reinicia la aplicación después de instalar. También puedes indicar `tesseract.exe` y `soffice.exe` desde **Ajustes y diagnóstico**.

Para español hace falta `spa.traineddata`; para inglés, `eng.traineddata`; y para corregir orientación, `osd.traineddata`. Ejecuta este script opcional desde PowerShell dentro de la carpeta del repositorio:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\descargar_idiomas.ps1
```

El script descarga los tres idiomas desde el repositorio oficial de Tesseract a `%LOCALAPPDATA%\LocalOCR\tessdata`, sin sobrescribir los existentes. También crea `configs\hocr`, requerido por OCRmyPDF; las primeras versiones omitían ese archivo. La aplicación repara automáticamente esa configuración si la carpeta permite escritura. Selecciona esa carpeta en **Ajustes → Carpeta de idiomas tessdata**. En el ZIP del ejecutable el script está en la carpeta principal: usa `-File .\descargar_idiomas.ps1`.

Pulsa **Comprobar componentes e idiomas**. Deben aparecer `spa`, `eng` y, si activas rotación, `osd`. El módulo de código y los PDF puramente textuales no necesitan Tesseract. OCRmyPDF 17 se utiliza con salida PDF normal, no PDF/A; no se requiere Ghostscript para este flujo al usar pypdfium2.

## Documentos

1. Agrega o arrastra los PDF/Word.
2. Elige idioma y carpeta de salida.
3. Conserva el modo **Automático** salvo que tengas una razón para cambiarlo.
4. Pulsa **Generar PDF + Markdown** y revisa los avisos.

Cada documento genera una carpeta independiente con `nombre_OCR.pdf`, `nombre.md`, `informe.json` y, si corresponde, `ocr_motor.log` e `imagenes/`. El informe señala páginas sin texto recuperable. El avance muestra etapas y páginas durante la extracción; durante el OCR se muestra actividad sin inventar un porcentaje.

### Modos

- **Automático:** rehace capas OCR y reconoce imágenes conservando el texto nativo. Puede volver a analizar un PDF que ya tenía OCR.
- **Solo páginas sin texto:** más rápido, pero omite las imágenes en páginas que ya tienen texto. La aplicación lo advierte.
- **Forzar:** rasteriza todas las páginas y hace OCR completo. Sirve para texto con codificación dañada; puede perder propiedades de vectores o formularios. Requiere confirmación. Solo aquí se permite enderezar escaneos.

La corrección de orientación es opcional y puede girar páginas. El preprocesamiento no realiza limpieza destructiva de fondos por defecto. 300 DPI es el valor inicial; 400 DPI aumenta tiempo y recursos y no recupera detalles ausentes de un escaneo pobre.

### Límites de fidelidad

- OCR no es perfecto: revisa nombres, cifras, tildes, documentos borrosos y escritura manuscrita.
- Markdown se extrae del **PDF final también para Word**, para incluir el OCR de imágenes. No es una reconstrucción exacta de estilos semánticos de DOCX.
- Títulos y tablas se deducen de la disposición y el texto. Tablas escaneadas complejas, columnas, fórmulas, notas y orden de lectura pueden requerir corrección. No se genera LaTeX fiable ni descripciones de ilustraciones.
- Las tablas exportadas usan encabezados genéricos para no interpretar la primera fila como un título cuando podría ser dato.
- Las imágenes opcionales son elementos raster embebidos. No se exportan escaneos que ocupan casi toda la página ni todos los dibujos vectoriales.
- LibreOffice puede cambiar saltos, fuentes o maquetación frente a Microsoft Word. Instala las fuentes del documento y revisa el PDF resultante.
- Los PDF cifrados o con campos de firma digital se rechazan. No se eliminan contraseñas ni se invalidan firmas. No admite `.docm`.
- Límite inicial: 512 MB por documento y 2.000 páginas. Divide documentos mayores. El procesamiento puede necesitar espacio temporal considerable.
- Solo procesa documentos de confianza. El aislamiento de procesos mantiene la interfaz fluida, **no es un sandbox de seguridad**. No hay telemetría ni llamadas de red en el código de procesamiento; los documentos con referencias externas y las aplicaciones externas tienen sus propios riesgos.

## Proyectos de código para LLM

1. Selecciona la carpeta del proyecto y pulsa **Analizar proyecto**.
2. Revisa el árbol, la vista previa y los archivos omitidos.
3. Marca solo los archivos relevantes para la pregunta que harás al LLM.
4. Ajusta los tokens estimados por parte y pulsa **Exportar a Markdown**.

Funciona con cualquier archivo de texto legible, aunque su lenguaje sea desconocido. Incluye etiquetas de bloques para lenguajes comunes. No compila, instala dependencias ni ejecuta el proyecto.

Se excluyen por defecto `.git`, `node_modules`, `vendor`, `.venv`, `dist`, `build`, `bin`, `obj`, cachés, binarios, minificados, logs, `.env*`, certificados y nombres comunes de credenciales. Se respetan `.gitignore` raíz y anidados; no se leen configuraciones globales de Git. No se siguen symlinks ni junctions. Los lockfiles son opcionales; los manifiestos de dependencias sí se pueden incluir.

La detección de posibles claves o contraseñas excluye **el archivo completo**, no reemplaza silenciosamente su contenido. Puede tener falsos positivos y falsos negativos. No sustituye una revisión de seguridad: **revisa el Markdown antes de subirlo a un LLM**. La app nunca hace esa subida por ti. Si el archivo cambia después del análisis, la exportación se detiene y pide analizar de nuevo.

Salidas:

- `proyecto_completo.md` si todo cabe; en caso contrario `parte_001.md`, `parte_002.md`, etc. No duplica innecesariamente el proyecto completo cuando lo divide.
- `resumen_proyecto.md`: listado, lenguajes detectados e instrucciones. **No es un resumen semántico con IA** ni adivina la arquitectura.
- `informe.json`: archivos incluidos, hashes SHA-256, exclusiones y tamaño estimado de las partes.

Se conservan texto, comentarios e indentación. Los archivos demasiado grandes se dividen por líneas cuando es posible; cada fragmento indica sus offsets de caracteres. Los fences Markdown se adaptan para contener archivos que ya tienen bloques de código.

**Markdown por sí solo no reduce tokens**; incluso añade encabezados. El ahorro viene de seleccionar contexto y eliminar material irrelevante. La cuenta `ceil(bytes UTF-8 / 3)` es una heurística local, no el tokenizador del modelo. El límite configurado se aplica a esa estimación incluyendo el formato, no garantiza caber en el contexto real. Reserva margen para instrucciones, historial y respuesta. Las cifras de la lista no incluyen encabezados de exportación.

Límites iniciales: 1 MB por archivo (configurable hasta 20 MB), 30 MB totales y 10.000 archivos incluidos. Si el proyecto es muy grande, selecciona un módulo. Los notebooks se incluyen como JSON sin limpiar sus salidas; es preferible seleccionar una versión `.py` sin resultados sensibles.

## Desarrollo y pruebas

Estructura principal: `src/local_ocr/gui.py` (interfaz), `appearance.py` (estilo y emblema vectorial), `documents.py` (PDF/Word), `projects.py` (contexto de código), `worker.py` (proceso independiente), `dependencies.py` (diagnóstico) y `common.py` (cancelación y salidas transaccionales).

```powershell
.venv\Scripts\python.exe -m pip install ".[dev,build]"
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean local_ocr.spec
```

Las pruebas de integración usan Tesseract en inglés y LibreOffice cuando están instalados; se marcan como omitidas si faltan. Cubren OCR real, páginas mixtas, Word con imagen, texto buscable, preservación visual de muestras, firmas, cifrado, exclusiones, cambios concurrentes, fragmentación, cancelación y el flujo de interfaz. `scripts/smoke_frozen.py` comprueba el ejecutable empaquetado con OCR real. No sustituyen pruebas de todos tus documentos ni de todas las versiones de Windows.

Linux para desarrollo: instala `tesseract-ocr`, `tesseract-ocr-spa`, `libreoffice-writer` y las bibliotecas Qt de tu distribución. Luego usa Python 3.12, `python -m venv .venv`, `pip install -r requirements.txt`, `pip install -e '.[dev]'` y `python -m local_ocr`. PyInstaller no hace compilación cruzada: el ejecutable Windows se construye en Windows con GitHub Actions.

## Referencias y licencias

Consulta [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). El repositorio no asigna automáticamente una licencia al código propio del usuario.

- [OCRmyPDF: instalación](https://ocrmypdf.readthedocs.io/en/stable/installation.html), [modos y limitaciones](https://ocrmypdf.readthedocs.io/en/stable/advanced.html).
- [Tesseract](https://tesseract-ocr.github.io/tessdoc/) y [modelos tessdata_fast](https://github.com/tesseract-ocr/tessdata_fast).
- [PyMuPDF](https://pymupdf.readthedocs.io/), [PySide6](https://doc.qt.io/qtforpython-6/) y [PyInstaller](https://pyinstaller.org/).

## Mejoras futuras

Visor del PDF dentro de la app, edición de texto antes de exportar, mejores heurísticas multicolumna, fórmulas/tablas complejas, tokenizadores específicos, instalador único y firma de ejecutables no están implementados en esta versión. No se prometen porcentajes de precisión ni reducción de tokens fija.
