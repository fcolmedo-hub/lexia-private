$ErrorActionPreference = 'Stop'

$Root = if ($env:LEXIA_ROOT) { $env:LEXIA_ROOT } else { 'D:\LexIA_2.3_DEV' }
$Py = Join-Path $Root '.venv\Scripts\python.exe'
$Entry = Join-Path $Root 'app\ui2\windows_desktop.py'
$BuildRoot = Join-Path $Root '.build_lexia_windows'
$Dist = Join-Path $BuildRoot 'dist'
$Work = Join-Path $BuildRoot 'build'
$Spec = Join-Path $BuildRoot 'LexIA.spec'
$ExeOut = Join-Path $Dist 'LexIA.exe'
$ExeTarget = Join-Path $Root 'LexIA.exe'

if (-not (Test-Path $Py)) { throw "No se encontró $Py" }
if (-not (Test-Path $Entry)) { throw "No se encontró $Entry" }

New-Item -ItemType Directory -Force -Path $BuildRoot | Out-Null
Remove-Item -Recurse -Force $Dist,$Work -ErrorAction SilentlyContinue
Remove-Item -Force $Spec -ErrorAction SilentlyContinue

# No usamos una llamada fallida bajo ErrorActionPreference=Stop porque PowerShell
# convierte el stderr de python.exe en NativeCommandError antes de poder revisar
# $LASTEXITCODE. Comprobamos el módulo de forma silenciosa y, si falta, lo instalamos.
$PyInstallerPresent = $false
$OldErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
try {
    & $Py -c "import PyInstaller" *> $null
    $PyInstallerPresent = ($LASTEXITCODE -eq 0)
} finally {
    $ErrorActionPreference = $OldErrorActionPreference
}

if (-not $PyInstallerPresent) {
    Write-Host 'Instalando PyInstaller en el entorno virtual de LexIA...'
    & $Py -m pip install --quiet pyinstaller
    if ($LASTEXITCODE -ne 0) {
        throw 'No se pudo instalar PyInstaller en el entorno virtual de LexIA.'
    }
}

$IconArgs = @()
$IconCandidates = @(
    (Join-Path $Root 'LexIA.ico'),
    (Join-Path $Root 'assets\LexIA.ico'),
    (Join-Path $Root 'app\ui2\assets\LexIA.ico')
)
$Icon = $IconCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if ($Icon) { $IconArgs = @('--icon', $Icon) }

$Args = @(
    '-m','PyInstaller',
    '--noconfirm',
    '--clean',
    '--onefile',
    '--windowed',
    '--name','LexIA',
    '--hidden-import','webview',
    '--hidden-import','webview.platforms.edgechromium',
    '--distpath',$Dist,
    '--workpath',$Work,
    '--specpath',$BuildRoot
) + $IconArgs + @($Entry)

& $Py @Args
if ($LASTEXITCODE -ne 0 -or -not (Test-Path $ExeOut)) {
    throw 'PyInstaller no pudo generar LexIA.exe'
}

Copy-Item -Force $ExeOut $ExeTarget

$Desktop = [Environment]::GetFolderPath('Desktop')
$Shortcut = Join-Path $Desktop 'LexIA.lnk'
$Shell = New-Object -ComObject WScript.Shell
$Link = $Shell.CreateShortcut($Shortcut)
$Link.TargetPath = $ExeTarget
$Link.WorkingDirectory = $Root
if ($Icon) {
    $Link.IconLocation = "$Icon,0"
} else {
    $Link.IconLocation = "$ExeTarget,0"
}
$Link.Description = 'LexIA'
$Link.Save()

Write-Host ''
Write-Host "LexIA.exe instalada en: $ExeTarget"
Write-Host "Acceso directo creado en: $Shortcut"
if (-not $Icon) {
    Write-Host 'No se encontró LexIA.ico; se usó el icono del ejecutable. Podremos reemplazarlo luego por la pluma azul.'
}
