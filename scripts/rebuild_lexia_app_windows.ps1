param(
    [switch]$LocalQdrant
)

$ErrorActionPreference = 'Stop'

$Root = if ($env:LEXIA_ROOT) { $env:LEXIA_ROOT } else { 'D:\LexIA_2.3_DEV' }
$Py = Join-Path $Root '.venv\Scripts\python.exe'
$EntryName = if ($LocalQdrant) { 'windows_desktop_local.py' } else { 'windows_desktop.py' }
$Entry = Join-Path $Root (Join-Path 'app\ui2' $EntryName)
$AppName = if ($LocalQdrant) { 'LexIA_LocalQdrant' } else { 'LexIA' }
$ShortcutName = if ($LocalQdrant) { 'LexIA Local Qdrant.lnk' } else { 'LexIA.lnk' }
$BuildRoot = Join-Path $Root '.build_lexia_windows'
$Dist = Join-Path $BuildRoot 'dist'
$Work = Join-Path $BuildRoot 'build'
$Spec = Join-Path $BuildRoot "$AppName.spec"
$ExeOut = Join-Path $Dist "$AppName\$AppName.exe"
$InstallRoot = Join-Path $Root '.lexia_windows_app'
$InstallDir = Join-Path $InstallRoot $AppName
$ExeTarget = Join-Path $InstallDir "$AppName.exe"

function Test-PackagedInterpreter([string]$Executable, [string]$Label) {
    $Marker = Join-Path $BuildRoot ("embedded_python_" + [guid]::NewGuid().ToString('N') + '.ok')
    $PreviousMarker = $env:LEXIA_EMBEDDED_SMOKE_MARKER
    try {
        $env:LEXIA_EMBEDDED_SMOKE_MARKER = $Marker
        $Process = Start-Process -FilePath $Executable `
            -ArgumentList '--lexia-embedded-smoke-test' `
            -WorkingDirectory $Root -WindowStyle Hidden -PassThru
        if (-not $Process.WaitForExit(30000)) {
            Stop-Process -Id $Process.Id -Force -ErrorAction SilentlyContinue
            throw "$Label no terminó la prueba del Python embebido."
        }
        $Process.Refresh()
        if ($Process.ExitCode -ne 0 -or -not (Test-Path $Marker)) {
            throw (
                "$Label no puede iniciar el Python embebido " +
                "(código $($Process.ExitCode))."
            )
        }
    } finally {
        if ($null -eq $PreviousMarker) {
            Remove-Item Env:LEXIA_EMBEDDED_SMOKE_MARKER -ErrorAction SilentlyContinue
        } else {
            $env:LEXIA_EMBEDDED_SMOKE_MARKER = $PreviousMarker
        }
        Remove-Item -Force $Marker -ErrorAction SilentlyContinue
    }
}

if (-not (Test-Path $Py)) { throw "No se encontró $Py" }
if (-not (Test-Path $Entry)) { throw "No se encontró $Entry" }

$RequiredStandardsFiles = @(
    (Join-Path $Root 'app\ui2\standards_api.py'),
    (Join-Path $Root 'app\ui2\assets\standards_ui.js'),
    (Join-Path $Root 'app\ui2\assets\standards_nav_fix.js'),
    (Join-Path $Root 'app\ui2\navigator_3_3_4a.js'),
    (Join-Path $Root 'app\ui2\assets\jurisprudence_search.js'),
    (Join-Path $Root 'app\ui2\assets\search_investigation_bridge.js'),
    (Join-Path $Root 'app\ui2\assets\windows_search_results_polish.js'),
    (Join-Path $Root 'services\standards_service.py'),
    (Join-Path $Root 'services\standards_canonicalizer.py')
)
$MissingStandardsFiles = @(
    $RequiredStandardsFiles | Where-Object { -not (Test-Path $_) }
)
if ($MissingStandardsFiles.Count -gt 0) {
    throw (
        "No se puede construir LexIA Windows: faltan componentes de Estándares:`n" +
        ($MissingStandardsFiles -join "`n")
    )
}

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

# clr-loader crea el runtime .NET de pywebview mediante CFFI. PyInstaller no
# siempre detecta el import dinámico del módulo binario _cffi_backend, por lo
# que comprobamos la dependencia antes de construir y la incluimos de forma
# explícita más abajo.
if (-not (Test-PythonModule '_cffi_backend')) {
    Write-Host 'Instalando CFFI en el entorno virtual de LexIA...'
    & $Py -m pip install --quiet cffi
    if ($LASTEXITCODE -ne 0) {
        throw 'No se pudo instalar CFFI en el entorno virtual de LexIA.'
    }
}

if (-not (Test-PythonModule '_cffi_backend')) {
    throw '_cffi_backend sigue sin estar disponible después de instalar CFFI.'
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
    '--name',$AppName,
    '--collect-all','webview',
    '--hidden-import','_cffi_backend',
    '--distpath',$Dist,
    '--workpath',$Work,
    '--specpath',$BuildRoot
) + $IconArgs + @($Entry)

& $Py @Args
if ($LASTEXITCODE -ne 0 -or -not (Test-Path $ExeOut)) {
    throw "PyInstaller no pudo generar $AppName.exe"
}

$InternalDir = Join-Path (Join-Path $Dist $AppName) '_internal'
$BundledCffiBackend = @(
    Get-ChildItem -Path $InternalDir -Filter '_cffi_backend*.pyd' -File -ErrorAction SilentlyContinue
)
if ($BundledCffiBackend.Count -eq 0) {
    throw (
        'El build de LexIA está incompleto: PyInstaller no incluyó ' +
        '_cffi_backend. No se reemplazó la instalación actual.'
    )
}

# Never replace a usable installation with a package whose embedded Python is
# incomplete. This catches missing/corrupt base_library.zip or python*.dll.
Test-PackagedInterpreter $ExeOut 'El paquete recién construido'

# A closed pywebview window can leave LexIA.exe alive briefly. The old script
# silently ignored a failed directory deletion and then copied over it, which
# could produce a mixed ONEDIR installation that fails before Python starts.
Get-Process -Name $AppName -ErrorAction SilentlyContinue | ForEach-Object {
    try {
        if ($_.Path -and ([IO.Path]::GetFullPath($_.Path) -eq [IO.Path]::GetFullPath($ExeTarget))) {
            Stop-Process -Id $_.Id -Force -ErrorAction Stop
            $_.WaitForExit(10000)
        }
    } catch {
        throw "No se pudo cerrar la instalación anterior de LexIA: $($_.Exception.Message)"
    }
}

New-Item -ItemType Directory -Force -Path $InstallRoot | Out-Null
$BackupDir = "$InstallDir.backup-rebuild"
Remove-Item -Recurse -Force $BackupDir -ErrorAction SilentlyContinue
if (Test-Path $InstallDir) {
    Move-Item -Path $InstallDir -Destination $BackupDir -ErrorAction Stop
}

try {
    Copy-Item -Recurse -Force (Join-Path $Dist $AppName) $InstallDir
    Test-PackagedInterpreter $ExeTarget 'La instalación copiada'
    Remove-Item -Recurse -Force $BackupDir -ErrorAction SilentlyContinue
} catch {
    Remove-Item -Recurse -Force $InstallDir -ErrorAction SilentlyContinue
    if (Test-Path $BackupDir) {
        Move-Item -Path $BackupDir -Destination $InstallDir -ErrorAction Stop
    }
    throw
}

# Eliminar el antiguo ejecutable onefile para evitar que un acceso viejo siga
# lanzando la versión lenta.
$LegacyExe = Join-Path $Root 'LexIA.exe'
Remove-Item -Force $LegacyExe -ErrorAction SilentlyContinue

$Desktop = [Environment]::GetFolderPath('Desktop')
$Shortcut = Join-Path $Desktop $ShortcutName
$Shell = New-Object -ComObject WScript.Shell
$Link = $Shell.CreateShortcut($Shortcut)
$Link.TargetPath = $ExeTarget
$Link.WorkingDirectory = $Root
if ($Icon) {
    $Link.IconLocation = "$Icon,0"
} else {
    $Link.IconLocation = "$ExeTarget,0"
}
$Link.Description = if ($LocalQdrant) { 'LexIA - Qdrant local experimental' } else { 'LexIA' }
$Link.Save()

Write-Host ''
Write-Host "LexIA instalada en: $ExeTarget"
Write-Host "Acceso directo creado en: $Shortcut"
Write-Host 'Modo de arranque: ONEDIR (sin extracción temporal por cada inicio).'
if ($LocalQdrant) {
    Write-Host 'Modo Qdrant: LOCAL embebido experimental. No usa Docker Desktop.'
    Write-Host 'IMPORTANTE: requiere reconstruir el índice vectorial local antes de comparar búsquedas.'
}
if (-not $Icon) {
    Write-Host 'No se encontró LexIA.ico; se usó el icono del ejecutable. Podremos reemplazarlo luego por la pluma azul.'
}
