param(
    [string]$Root = (Join-Path $PSScriptRoot '..')
)

$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path $Root).Path
$Pythonw = Join-Path $Root '.venv\Scripts\pythonw.exe'
$Entry = Join-Path $Root 'app\ui2\windows_desktop_fast.py'
$EncodedIcon = Join-Path $Root 'assets\LexIA.ico.b64'
$IconDir = Join-Path ([Environment]::GetFolderPath('LocalApplicationData')) 'LexIA'
$Icon = Join-Path $IconDir 'LexIA.ico'
$AppId = 'LexIA.Desktop'

if (-not (Test-Path $Pythonw)) {
    throw "No se encontró el intérprete estable: $Pythonw"
}
if (-not (Test-Path $Entry)) {
    throw "No se encontró el launcher rápido: $Entry"
}
if (-not (Test-Path $EncodedIcon)) {
    throw "No se encontró el icono codificado: $EncodedIcon"
}

New-Item -ItemType Directory -Force -Path $IconDir | Out-Null
$RawIcon = (Get-Content -Raw -Path $EncodedIcon).Trim()
[IO.File]::WriteAllBytes($Icon, [Convert]::FromBase64String($RawIcon))

if (-not ('LexIA.ShortcutIdentity' -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;

namespace LexIA {
    public static class ShortcutIdentity {
        [StructLayout(LayoutKind.Sequential, Pack = 4)]
        private struct PROPERTYKEY {
            public Guid fmtid;
            public uint pid;

            public PROPERTYKEY(Guid formatId, uint propertyId) {
                fmtid = formatId;
                pid = propertyId;
            }
        }

        [StructLayout(LayoutKind.Explicit, Size = 16)]
        private struct PROPVARIANT {
            [FieldOffset(0)]
            public ushort vt;

            [FieldOffset(8)]
            public IntPtr pointerValue;
        }

        [ComImport]
        [Guid("886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99")]
        [InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
        private interface IPropertyStore {
            [PreserveSig] int GetCount(out uint propertyCount);
            [PreserveSig] int GetAt(uint propertyIndex, out PROPERTYKEY key);
            [PreserveSig] int GetValue(ref PROPERTYKEY key, out PROPVARIANT value);
            [PreserveSig] int SetValue(ref PROPERTYKEY key, ref PROPVARIANT value);
            [PreserveSig] int Commit();
        }

        [DllImport("shell32.dll", CharSet = CharSet.Unicode, PreserveSig = false)]
        private static extern void SHGetPropertyStoreFromParsingName(
            string path,
            IntPtr bindContext,
            uint flags,
            ref Guid interfaceId,
            [Out, MarshalAs(UnmanagedType.Interface)] out IPropertyStore propertyStore
        );

        [DllImport("ole32.dll")]
        private static extern int PropVariantClear(ref PROPVARIANT value);

        public static void SetAppUserModelId(string shortcutPath, string appId) {
            Guid interfaceId = typeof(IPropertyStore).GUID;
            IPropertyStore store;
            SHGetPropertyStoreFromParsingName(
                shortcutPath,
                IntPtr.Zero,
                0x2,
                ref interfaceId,
                out store
            );

            PROPERTYKEY key = new PROPERTYKEY(
                new Guid("9F4C2855-9F79-4B39-A8D0-E1D42DE1D5F3"),
                5
            );
            PROPVARIANT value = new PROPVARIANT {
                vt = 31,
                pointerValue = Marshal.StringToCoTaskMemUni(appId)
            };

            try {
                Marshal.ThrowExceptionForHR(store.SetValue(ref key, ref value));
                Marshal.ThrowExceptionForHR(store.Commit());
            }
            finally {
                PropVariantClear(ref value);
                Marshal.FinalReleaseComObject(store);
            }
        }
    }
}
'@
}

function New-LexIAShortcut([string]$ShortcutPath) {
    $Shell = New-Object -ComObject WScript.Shell
    try {
        $Link = $Shell.CreateShortcut($ShortcutPath)
        $Link.TargetPath = $Pythonw
        $Link.Arguments = '"' + $Entry + '"'
        $Link.WorkingDirectory = $Root
        $Link.IconLocation = "$Icon,0"
        $Link.Description = 'LexIA'
        $Link.Save()
    }
    finally {
        if ($Link) {
            [Runtime.InteropServices.Marshal]::FinalReleaseComObject($Link) | Out-Null
        }
        [Runtime.InteropServices.Marshal]::FinalReleaseComObject($Shell) | Out-Null
    }
    [LexIA.ShortcutIdentity]::SetAppUserModelId($ShortcutPath, $AppId)
}

$DesktopShortcut = Join-Path ([Environment]::GetFolderPath('Desktop')) 'LexIA.lnk'
$ProgramsShortcut = Join-Path ([Environment]::GetFolderPath('Programs')) 'LexIA.lnk'

New-LexIAShortcut $DesktopShortcut
New-LexIAShortcut $ProgramsShortcut

Write-Host ''
Write-Host 'Accesos directos LexIA corregidos.'
Write-Host "Escritorio: $DesktopShortcut"
Write-Host "Menú Inicio: $ProgramsShortcut"
Write-Host "Destino estable: $Pythonw"
Write-Host "Launcher: $Entry"
Write-Host "AppUserModelID: $AppId"
Write-Host ''
Write-Host 'Desanclá el icono anterior y anclá LexIA desde el menú Inicio.'
