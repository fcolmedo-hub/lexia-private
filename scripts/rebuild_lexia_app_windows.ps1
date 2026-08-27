$ErrorActionPreference = 'Stop'

$Root = if ($env:LEXIA_ROOT) { $env:LEXIA_ROOT } else { 'D:\LexIA_2.3_DEV' }
$Py = Join-Path $Root '.venv\Scripts\python.exe'
$Entry = Join-Path $Root 'app\ui2\windows_desktop.py'
$BuildRoot = Join-Path $Root '.build_lexia_windows'
$Dist = Join-Path $BuildRoot 'dist'
$Work = Join-Path $BuildRoot 'build'
$Spec = Join-Path $BuildRoot 'LexIA.spec'
$ExeOut = Join-Path $Dist 'LexIA\LexIA.exe'
$InstallRoot = Join-Path $Root '.lexia_windows_app'
$InstallDir = Join-Path $InstallRoot 'LexIA'
$ExeTarget = Join-Path $InstallDir 'LexIA.exe'

if (-not (Test-Path $Py)) { throw "No se encontró $Py" }
if (-not (Test-Path $Entry)) { throw "No se encontró $Entry" }

New-Item -ItemType Directory -Force -Path $BuildRoot | Out-Null
Remove-Item -Recurse -Force $Dist,$Work -ErrorAction SilentlyContinue
Remove-Item -Force $Spec -ErrorAction SilentlyContinue

function Test-PythonModule([string]$ModuleName) {
    $present = $false
    $old = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        & $Py -c "import $ModuleName" *> $null
        $present = ($LASTEXITCODE -eq 0)
    } finally {
        $ErrorActionPreference = $old
    }
    return $present
}

if (-not (Test-PythonModule 'PyInstaller')) {
    Write-Host 'Instalando PyInstaller en el entorno virtual de LexIA...'
    & $Py -m pip install --quiet pyinstaller
    if ($LASTEXITCODE -ne 0) {
        throw 'No se pudo instalar PyInstaller en el entorno virtual de LexIA.'
    }
}

if (-not (Test-PythonModule 'webview')) {
    Write-Host 'Instalando pywebview en el entorno virtual de LexIA...'
    & $Py -m pip install --quiet pywebview
    if ($LASTEXITCODE -ne 0) {
        throw 'No se pudo instalar pywebview en el entorno virtual de LexIA.'
    }
}

if (-not (Test-PythonModule 'webview')) {
    throw 'pywebview sigue sin estar disponible después de la instalación.'
}

$IconArgs = @()
$IconCandidates = @(
    (Join-Path $Root 'LexIA.ico'),
    (Join-Path $Root 'assets\LexIA.ico'),
    (Join-Path $Root 'app\ui2\assets\LexIA.ico')
)
$Icon = $IconCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if ($Icon) { $IconArgs = @('--icon', $Icon) }

# ONEDIR es deliberado. El antiguo --onefile debía descomprimir pywebview y sus
# dependencias en cada arranque, añadiendo varios segundos antes de ejecutar LexIA.
# ONEDIR deja esos archivos ya desplegados y acelera sensiblemente el inicio.
$Args = @(
    '-m','PyInstaller',
    '--noconfirm',
    '--clean',
    '--onedir',
    '--windowed',
    '--name','LexIA',
    '--collect-all','webview',
    '--distpath',$Dist,
    '--workpath',$Work,
    '--specpath',$BuildRoot
) + $IconArgs + @($Entry)

& $Py @Args
if ($LASTEXITCODE -ne 0 -or -not (Test-Path $ExeOut)) {
    throw 'PyInstaller no pudo generar LexIA.exe'
}

Remove-Item -Recurse -Force $InstallDir -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $InstallRoot | Out-Null
Copy-Item -Recurse -Force (Join-Path $Dist 'LexIA') $InstallDir

# Eliminar el antiguo ejecutable onefile para evitar que un acceso viejo siga
# lanzando la versión lenta.
$LegacyExe = Join-Path $Root 'LexIA.exe'
Remove-Item -Force $LegacyExe -ErrorAction SilentlyContinue

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
Write-Host "LexIA instalada en: $ExeTarget"
Write-Host "Acceso directo creado en: $Shortcut"
Write-Host 'Modo de arranque: ONEDIR (sin extracción temporal por cada inicio).'
if (-not $Icon) {
    Write-Host 'No se encontró LexIA.ico; se usó el icono del ejecutable. Podremos reemplazarlo luego por la pluma azul.'
}
