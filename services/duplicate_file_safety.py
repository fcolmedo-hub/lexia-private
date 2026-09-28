"""Physical-file checks shared by duplicate listing, deletion and relocation."""
from pathlib import Path
import os


def duplicate_problem(path, original) -> str:
    path, original = Path(path), Path(original)
    try:
        if not path.is_file():
            return 'El archivo de esta ubicación ya no existe.'
        if not original.is_file():
            return 'El supuesto original ya no está en su ubicación. Puede ser un archivo movido.'
        if path.resolve() == original.resolve() or path.samefile(original):
            return 'Ambas rutas corresponden al mismo archivo.'
    except OSError:
        return 'No se pudieron comprobar las dos ubicaciones.'
    return ''


def require_identical_files(path, original) -> None:
    problem = duplicate_problem(path, original)
    if problem:
        raise ValueError(problem + ' No se eliminó el archivo.')
    def fingerprint(s):
        return s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns
    path, original = Path(path), Path(original)
    with path.open('rb') as left, original.open('rb') as right:
        a, b = os.fstat(left.fileno()), os.fstat(right.fileno())
        if a.st_size != b.st_size or (a.st_dev, a.st_ino) == (b.st_dev, b.st_ino):
            raise ValueError('No son dos archivos distintos con contenido idéntico. No se eliminó el archivo.')
        while True:
            x, y = left.read(1024 * 1024), right.read(1024 * 1024)
            if x != y:
                raise ValueError('Los contenidos son diferentes. No se eliminó el archivo.')
            if not x:
                break
        if fingerprint(a) != fingerprint(path.stat()) or fingerprint(b) != fingerprint(original.stat()):
            raise ValueError('Un archivo cambió durante la comprobación. No se eliminó el archivo.')
