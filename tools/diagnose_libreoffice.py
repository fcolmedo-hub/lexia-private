import json
from services.libreoffice_locator import diagnostic
print(json.dumps(diagnostic(), ensure_ascii=False, indent=2))
