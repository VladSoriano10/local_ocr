# Descarga explicita, solo al ejecutar este script. No modifica archivos de Windows.
$ErrorActionPreference = 'Stop'
$destination = Join-Path $env:LOCALAPPDATA 'LocalOCR\tessdata'
New-Item -ItemType Directory -Force -Path $destination | Out-Null
foreach ($language in @('spa', 'eng', 'osd')) {
    $target = Join-Path $destination "$language.traineddata"
    if (Test-Path -LiteralPath $target) {
        Write-Host "Ya existe: $target (no se sobrescribe)"
        continue
    }
    $temporary = "$target.download"
    $url = "https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/main/$language.traineddata"
    Write-Host "Descargando $language desde el repositorio oficial de Tesseract..."
    Invoke-WebRequest -Uri $url -OutFile $temporary
    if ((Get-Item -LiteralPath $temporary).Length -lt 100000) {
        throw "La descarga de $language no parece valida. No se utilizara."
    }
    Move-Item -LiteralPath $temporary -Destination $target
}
Write-Host "Listo. En Ajustes de Local OCR, selecciona esta carpeta como tessdata:"
Write-Host $destination
