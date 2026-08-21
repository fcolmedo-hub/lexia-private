from __future__ import annotations
import os, platform, shutil
from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True, slots=True)
class LibreOfficeStatus:
    found: bool
    executable: str | None
    source: str
    platform: str
    checked_paths: tuple[str, ...]

def _candidate_paths():
    system = (platform.system() or "").casefold()
    if system == "windows":
        pf = os.environ.get("ProgramFiles", r"C:\Program Files")
        pfx = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
        local = os.environ.get("LOCALAPPDATA", "")
        paths = [
            Path(pf) / "LibreOffice/program/soffice.exe",
            Path(pfx) / "LibreOffice/program/soffice.exe",
        ]
        if local:
            paths.append(
                Path(local) / "Programs/LibreOffice/program/soffice.exe"
            )
        return paths
    if system == "darwin":
        return [
            Path("/Applications/LibreOffice.app/Contents/MacOS/soffice"),
            Path("~/Applications/LibreOffice.app/Contents/MacOS/soffice").expanduser(),
        ]
    return [
        Path("/usr/bin/soffice"),
        Path("/usr/local/bin/soffice"),
        Path("/snap/bin/libreoffice"),
        Path("/var/lib/flatpak/exports/bin/org.libreoffice.LibreOffice"),
    ]

def locate_libreoffice(candidates=None):
    checked = []
    configured = os.environ.get("LEXIA_LIBREOFFICE_PATH", "").strip()
    if configured:
        p = Path(configured).expanduser()
        checked.append(str(p))
        if p.is_file():
            return LibreOfficeStatus(
                True, str(p.resolve()), "LEXIA_LIBREOFFICE_PATH",
                platform.system(), tuple(checked)
            )
    for command in ("soffice", "libreoffice"):
        found = shutil.which(command)
        if found:
            return LibreOfficeStatus(
                True, str(Path(found).resolve()), f"PATH:{command}",
                platform.system(), tuple(checked)
            )
    for candidate in (candidates or _candidate_paths()):
        p = Path(candidate).expanduser()
        checked.append(str(p))
        if p.is_file():
            return LibreOfficeStatus(
                True, str(p.resolve()), "standard_location",
                platform.system(), tuple(checked)
            )
    return LibreOfficeStatus(
        False, None, "not_found", platform.system(), tuple(checked)
    )

def ensure_libreoffice_on_path():
    status = locate_libreoffice()
    if not status.found or not status.executable:
        return status
    folder = str(Path(status.executable).parent)
    current = os.environ.get("PATH", "")
    parts = [p for p in current.split(os.pathsep) if p]
    normalized = {
        os.path.normcase(os.path.abspath(p)) for p in parts
    }
    target = os.path.normcase(os.path.abspath(folder))
    if target not in normalized:
        os.environ["PATH"] = folder + os.pathsep + current
    os.environ.setdefault("LEXIA_LIBREOFFICE_PATH", status.executable)
    return status

def diagnostic():
    status = ensure_libreoffice_on_path()
    return {
        "found": status.found,
        "executable": status.executable,
        "source": status.source,
        "platform": status.platform,
        "checked_paths": list(status.checked_paths),
        "soffice_in_path": shutil.which("soffice"),
        "libreoffice_in_path": shutil.which("libreoffice"),
    }
