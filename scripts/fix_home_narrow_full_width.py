from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "app" / "ui2" / "index.html"
SCRIPT = ROOT / "app" / "ui2" / "assets" / "home_width_runtime.js"
TAG = '<script src="assets/home_width_runtime.js?v=home-width-runtime-2"></script>'
MARK = "home_width_runtime.js"

if not INDEX.exists():
    raise SystemExit(f"ERROR: no existe {INDEX}")
if not SCRIPT.exists():
    raise SystemExit(f"ERROR: no existe {SCRIPT}")

text = INDEX.read_text(encoding="utf-8", errors="replace")
if MARK in text:
    updated = text.replace(
        '<script src="assets/home_width_runtime.js?v=home-width-runtime-1"></script>',
        TAG,
    )
    if updated != text:
        INDEX.write_text(updated, encoding="utf-8")
        print("OK: guardia runtime de ancho actualizada")
    else:
        print("OK: guardia runtime de ancho ya instalada")
else:
    backup = INDEX.with_suffix(".html.bak-home-width-runtime")
    if not backup.exists():
        backup.write_text(text, encoding="utf-8")
    if "</body>" in text:
        text = text.replace("</body>", TAG + "\n</body>", 1)
    else:
        text = text.rstrip() + "\n" + TAG + "\n"
    INDEX.write_text(text, encoding="utf-8")
    print("OK: guardia runtime instalada al final de index.html")

print("OK: en <=1199px #home usa el 100% real del viewport")
