from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path, PurePosixPath, PureWindowsPath
from urllib.parse import urlparse, parse_qs, unquote
from urllib import error as urllib_error
from urllib import request as urllib_request
import json
import os
import mimetypes
import sqlite3
import subprocess
import sys
import sys
import hashlib
import shutil
import tempfile
import threading
import uuid
from email.parser import BytesParser
from email.policy import default as email_policy

HERE = Path(__file__).resolve().parent
from portability import ensure_project_on_syspath
PROJECT_ROOT = ensure_project_on_syspath()
os.chdir(HERE)

from backend import LiveReadOnlyAdapter
from search_runtime import SearchRuntime

LIVE = LiveReadOnlyAdapter()
SEARCH = None

DELETE_BRIDGE_STATE = PROJECT_ROOT / "runtime" / "ui2_delete_bridge.json"

def get_search():
    global SEARCH
    if SEARCH is None:
        SEARCH = SearchRuntime()
    return SEARCH


class _DeleteBridgeError(RuntimeError):
    def __init__(self, message, status=503):
        super().__init__(message)
        self.status = int(status or 503)


def _delete_bridge_request(method, endpoint, payload=None):
    try:
        bridge = json.loads(DELETE_BRIDGE_STATE.read_text(encoding="utf-8"))
        port = int(bridge.get("port", 0) or 0)
        token = str(bridge.get("token", "") or "")
        if not (1 <= port <= 65535) or len(token) < 24:
            raise ValueError("estado incompleto")
    except Exception as exc:
        raise _DeleteBridgeError(
            "La interfaz clásica de LexIA debe permanecer abierta para eliminar. "
            "No se encontró su puente local de borrado seguro.",
            503,
        ) from exc

    bridge_root = f"http://127.0.0.1:{port}"
    raw = None
    headers = {
        "Accept": "application/json",
        "X-LexIA-Delete-Token": token,
    }
    if payload is not None:
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = urllib_request.Request(
        bridge_root + endpoint,
        data=raw,
        headers=headers,
        method=method,
    )
    try:
        with urllib_request.urlopen(request, timeout=8) as response:
            body = json.loads(response.read().decode("utf-8"))
            if not isinstance(body, dict):
                raise _DeleteBridgeError("El puente de la interfaz clásica respondió incorrectamente.")
            return body, int(response.status)
    except urllib_error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8"))
            message = str(body.get("error", "") or "")
        except Exception:
            message = ""
        raise _DeleteBridgeError(
            message or f"El servicio central rechazó la operación (HTTP {exc.code}).",
            exc.code,
        ) from exc
    except urllib_error.URLError as exc:
        raise _DeleteBridgeError(
            "La interfaz clásica de LexIA debe permanecer abierta para eliminar. "
            "No se encontró su puente local de borrado seguro.",
            503,
        ) from exc


OFFICE_PREVIEW_LOCK = threading.Lock()


def _find_soffice():
    configured = str(os.environ.get("LEXIA_SOFFICE", "") or "").strip()
    if configured:
        candidate = Path(configured).expanduser()
        if candidate.exists():
            return str(candidate)

    for command in ("soffice", "libreoffice"):
        found = shutil.which(command)
        if found:
            return found

    candidates = []

    if os.name == "nt":
        for env_name in ("ProgramFiles", "ProgramFiles(x86)"):
            base = str(os.environ.get(env_name, "") or "").strip()
            if base:
                candidates.append(Path(base) / "LibreOffice" / "program" / "soffice.exe")

        candidates.extend([
            Path(r"C:\Program Files\LibreOffice\program\soffice.exe"),
            Path(r"C:\Program Files (x86)\LibreOffice\program\soffice.exe"),
        ])

    if sys.platform == "darwin":
        candidates.extend([
            Path("/Applications/LibreOffice.app/Contents/MacOS/soffice"),
            Path.home() / "Applications" / "LibreOffice.app" / "Contents" / "MacOS" / "soffice",
        ])

    if sys.platform.startswith("linux"):
        candidates.extend([
            Path("/usr/bin/libreoffice"),
            Path("/usr/bin/soffice"),
            Path("/snap/bin/libreoffice"),
        ])

    for candidate in candidates:
        if candidate.exists():
            return str(candidate)

    return None



def _normalize_preview_locator_text(value):
    import re as _re
    import unicodedata as _ud
    text = _ud.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not _ud.combining(ch))
    text = text.lower()
    text = _re.sub(r"\s+", " ", text)
    return text.strip()


def _best_office_preview_page(pdf_path, snippet, fallback_page=None):
    """Locate the real result page inside the LibreOffice-generated PDF."""
    try:
        fallback = int(fallback_page or 0)
    except Exception:
        fallback = 0

    needle = _normalize_preview_locator_text(snippet)
    if not needle:
        return fallback if fallback > 0 else 1

    words = needle.split()
    search_words = words[:42]
    needle = " ".join(search_words).strip()
    if not needle:
        return fallback if fallback > 0 else 1

    try:
        import fitz
    except Exception:
        return fallback if fallback > 0 else 1

    try:
        doc = fitz.open(str(pdf_path))
    except Exception:
        return fallback if fallback > 0 else 1

    try:
        page_texts = []
        for idx in range(doc.page_count):
            try:
                txt = _normalize_preview_locator_text(doc.load_page(idx).get_text("text"))
            except Exception:
                txt = ""
            page_texts.append(txt)

        if len(needle) >= 24:
            for idx, txt in enumerate(page_texts):
                if needle in txt:
                    return idx + 1

        for n in (30, 24, 18, 14, 10, 7):
            if len(search_words) < n:
                continue
            candidate = " ".join(search_words[:n])
            for idx, txt in enumerate(page_texts):
                if candidate in txt:
                    return idx + 1

        important = []
        seen = set()
        for word in search_words:
            if len(word) < 3:
                continue
            if word not in seen:
                seen.add(word)
                important.append(word)

        bigrams = [
            important[i] + " " + important[i + 1]
            for i in range(len(important) - 1)
        ]

        best_page = None
        best_score = -1.0

        for idx, txt in enumerate(page_texts):
            if not txt:
                continue

            term_hits = sum(1 for word in important if word in txt)
            term_cov = term_hits / max(1, len(important))

            bigram_hits = sum(1 for bg in bigrams if bg in txt)
            bigram_cov = bigram_hits / max(1, len(bigrams)) if bigrams else 0.0

            score = (term_cov * 0.65) + (bigram_cov * 0.35)

            if fallback > 0:
                distance = abs((idx + 1) - fallback)
                score += max(0.0, 0.025 - distance * 0.001)

            if score > best_score:
                best_score = score
                best_page = idx + 1

        if best_page is not None and best_score >= 0.42:
            return best_page

        return fallback if fallback > 0 else 1
    finally:
        doc.close()


def _office_preview_pdf(requested_path):
    source = Path(
        _resolve_catalog_document(requested_path=requested_path)
    ).expanduser().resolve()

    if source.suffix.lower() not in {".doc", ".docx", ".rtf", ".odt"}:
        raise ValueError("El formato no admite conversión de vista previa.")

    soffice = _find_soffice()
    if not soffice:
        raise FileNotFoundError(
            "LibreOffice no está disponible. "
            "Defina LEXIA_SOFFICE o instale LibreOffice."
        )

    stat = source.stat()
    cache_key = hashlib.sha256(
        (
            str(source).lower()
            + "\0"
            + str(stat.st_mtime_ns)
            + "\0"
            + str(stat.st_size)
        ).encode("utf-8", errors="replace")
    ).hexdigest()

    cache_dir = (
        Path(__file__).resolve().parents[2]
        / "runtime"
        / "preview_cache"
        / "office_pdf"
    )
    cache_dir.mkdir(parents=True, exist_ok=True)

    target = cache_dir / f"{cache_key}.pdf"
    if target.exists() and target.stat().st_size > 100:
        return target

    with OFFICE_PREVIEW_LOCK:
        if target.exists() and target.stat().st_size > 100:
            return target

        work_dir = Path(
            tempfile.mkdtemp(prefix="lexia_lo_", dir=str(cache_dir))
        )
        out_dir = work_dir / "out"
        profile_dir = work_dir / "profile"
        out_dir.mkdir(parents=True, exist_ok=True)
        profile_dir.mkdir(parents=True, exist_ok=True)

        try:
            command = [
                soffice,
                f"-env:UserInstallation={profile_dir.resolve().as_uri()}",
                "--headless",
                "--convert-to",
                "pdf",
                "--outdir",
                str(out_dir),
                str(source),
            ]

            completed = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=180,
                check=False,
            )

            candidates = list(out_dir.glob("*.pdf"))
            if completed.returncode != 0 or not candidates:
                details = (
                    (completed.stderr or completed.stdout or "").strip()
                    or f"código {completed.returncode}"
                )
                raise RuntimeError(
                    "LibreOffice no pudo convertir el documento: "
                    + details[:800]
                )

            generated = candidates[0]
            if generated.stat().st_size <= 100:
                raise RuntimeError(
                    "LibreOffice generó un PDF de vista previa inválido."
                )

            temp_target = cache_dir / f".{cache_key}.tmp.pdf"
            shutil.copy2(generated, temp_target)
            temp_target.replace(target)
            return target
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)

def _lexia321_norm(value):
    import re as _re
    import unicodedata as _ud
    text = _ud.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not _ud.combining(ch))
    text = text.lower()
    text = _re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


_FILTER_TREE_LOCK = threading.RLock()
_FILTER_TREE_CACHE = {"signature": None, "summary": None, "trees": {}}


def _filter_catalog_path():
    return Path(__file__).resolve().parents[2] / "runtime" / "lexia_catalog.sqlite3"


def _filter_db_signature(db_path):
    signature = []
    for candidate in (db_path, Path(str(db_path) + "-wal")):
        try:
            stat = candidate.stat()
            signature.append((stat.st_mtime_ns, stat.st_size))
        except OSError:
            signature.append((0, 0))
    return tuple(signature)


def _filter_path_shape(path_value):
    raw = str(path_value or "").strip()
    pure_type = PureWindowsPath if "\\" in raw or (len(raw) > 1 and raw[1] == ":") else PurePosixPath
    pure = pure_type(raw)
    return pure_type, tuple(pure.parts)


def _filter_category_key(value):
    return _lexia321_norm(value).replace(" ", "")


def _filter_category_component_index(parts, category):
    wanted = _filter_category_key(category)
    aliases = {wanted}
    if wanted == "legislacion":
        aliases.add("legislacion")
    for index, part in enumerate(parts[:-1]):
        if _filter_category_key(part) in aliases:
            return index
    return None


def _new_filter_node(name, folder):
    return {"name": str(name), "folder": str(folder), "count": 0, "children": {}}


def _reset_filter_cache_if_needed(signature):
    if _FILTER_TREE_CACHE["signature"] != signature:
        _FILTER_TREE_CACHE["signature"] = signature
        _FILTER_TREE_CACHE["summary"] = None
        _FILTER_TREE_CACHE["trees"] = {}


def _catalog_category_summary():
    db_path = _filter_catalog_path()
    if not db_path.exists():
        return {"total": 0, "categories": {}}

    signature = _filter_db_signature(db_path)
    with _FILTER_TREE_LOCK:
        _reset_filter_cache_if_needed(signature)
        if _FILTER_TREE_CACHE["summary"] is not None:
            return _FILTER_TREE_CACHE["summary"]

        con = sqlite3.connect(str(db_path), timeout=10)
        con.row_factory = sqlite3.Row
        try:
            rows = con.execute(
                "SELECT category, COUNT(*) AS total FROM documents "
                "WHERE COALESCE(is_deleted,0)=0 "
                "GROUP BY category ORDER BY category COLLATE NOCASE"
            ).fetchall()
        finally:
            con.close()

        categories = {}
        total = 0
        for row in rows:
            category = str(row["category"] or "Sin categoría").strip() or "Sin categoría"
            count = int(row["total"] or 0)
            total += count
            categories[category.casefold()] = {
                "value": category,
                "label": category,
                "count": count,
            }
        summary = {"total": total, "categories": categories}
        _FILTER_TREE_CACHE["summary"] = summary
        return summary


def _catalog_filter_tree(category_filter=""):
    db_path = _filter_catalog_path()
    if not db_path.exists():
        return {"total": 0, "categories": {}, "folders": {}}

    category_filter = str(category_filter or "").strip()
    cache_key = category_filter.casefold()
    signature = _filter_db_signature(db_path)
    with _FILTER_TREE_LOCK:
        _reset_filter_cache_if_needed(signature)
        cached = _FILTER_TREE_CACHE["trees"].get(cache_key)
        if cached is not None:
            return cached

        con = sqlite3.connect(str(db_path), timeout=10)
        con.row_factory = sqlite3.Row
        try:
            sql = (
                "SELECT path, category FROM documents "
                "WHERE COALESCE(is_deleted,0)=0"
            )
            params = []
            if category_filter:
                sql += " AND category = ?"
                params.append(category_filter)
            rows = con.execute(sql, params).fetchall()
        finally:
            con.close()

        categories = {}
        folders = {}
        for row in rows:
            category = str(row["category"] or "Sin categoría").strip() or "Sin categoría"
            category_key = category.casefold()
            category_node = categories.get(category_key)
            if category_node is None:
                category_node = {
                    "value": category,
                    "label": category,
                    "count": 0,
                    "roots": {},
                }
                categories[category_key] = category_node
            category_node["count"] += 1

            pure_type, parts = _filter_path_shape(row["path"])
            category_index = _filter_category_component_index(parts, category)
            if category_index is None:
                continue

            root_folder = str(pure_type(*parts[:category_index + 1]))
            root_key = root_folder.casefold()
            root = category_node["roots"].get(root_key)
            if root is None:
                root = _new_filter_node(parts[category_index], root_folder)
                category_node["roots"][root_key] = root
                folders[root_folder.casefold()] = (category_key, root)
            root["count"] += 1

            parent = root
            for offset, name in enumerate(parts[category_index + 1:-1], start=category_index + 1):
                folder = str(pure_type(*parts[:offset + 1]))
                node_key = str(name).casefold()
                node = parent["children"].get(node_key)
                if node is None:
                    node = _new_filter_node(name, folder)
                    parent["children"][node_key] = node
                    folders[folder.casefold()] = (category_key, node)
                node["count"] += 1
                parent = node

        tree = {"total": len(rows), "categories": categories, "folders": folders}
        _FILTER_TREE_CACHE["trees"][cache_key] = tree
        return tree


def _filter_option(node):
    return {
        "name": node["name"],
        "folder": node["folder"],
        "count": int(node["count"]),
        "has_children": bool(node["children"]),
    }


def _catalog_filter_options(category="", parent_folder=""):
    summary = _catalog_category_summary()
    category = str(category or "").strip()
    parent_folder = str(parent_folder or "").strip()

    ordered_categories = sorted(
        summary["categories"].values(),
        key=lambda item: (
            {"escritos": 0, "doctrina": 1, "jurisprudencia": 2, "legislacion": 3}.get(
                _filter_category_key(item["label"]), 99
            ),
            item["label"].casefold(),
        ),
    )
    categories = [
        {
            "value": item["value"],
            "label": item["label"],
            "count": int(item["count"]),
        }
        for item in ordered_categories
    ]

    options = []
    if category:
        tree = _catalog_filter_tree(category)
        category_key = category.casefold()
        category_node = tree["categories"].get(category_key)
        if category_node is None:
            raise ValueError("La categoría seleccionada ya no existe en el catálogo.")

        if parent_folder:
            found = tree["folders"].get(parent_folder.casefold())
            if found is None or found[0] != category_key:
                raise ValueError("La carpeta seleccionada no pertenece a la categoría indicada.")
            children = found[1]["children"].values()
        else:
            children = []
            for root in category_node["roots"].values():
                children.extend(root["children"].values())

        options = [_filter_option(node) for node in children]
        options.sort(key=lambda item: item["name"].casefold())

    return {
        "ok": True,
        "total": int(summary["total"]),
        "categories": categories,
        "category": category,
        "parent_folder": parent_folder,
        "options": options,
    }


def _validated_filter_folder(category, folder):
    category = str(category or "").strip()
    folder = str(folder or "").strip()
    if not folder:
        return ""
    if not category:
        raise ValueError("Debe seleccionar una categoría antes de filtrar por carpeta.")
    tree = _catalog_filter_tree(category)
    found = tree["folders"].get(folder.casefold())
    if found is None or found[0] != category.casefold():
        raise ValueError("El filtro de carpeta no pertenece al árbol activo de LexIA.")
    return found[1]["folder"]


def _filter_like_pattern(folder):
    normalized = str(folder or "").replace("\\", "/").rstrip("/")
    escaped = normalized.replace("!", "!!").replace("%", "!%").replace("_", "!_")
    return escaped + "/%"


def _filter_path_is_within(path_value, folder):
    if not folder:
        return True
    path_norm = str(path_value or "").replace("\\", "/").casefold()
    folder_norm = str(folder or "").replace("\\", "/").rstrip("/").casefold()
    return path_norm.startswith(folder_norm + "/")


def _navigator_category_roots(category):
    tree = _catalog_filter_tree(category)
    category_node = tree["categories"].get(str(category or "").casefold())
    if category_node is None:
        raise ValueError("La categoría seleccionada ya no existe en el catálogo.")
    return tree, list(category_node["roots"].values())


def _navigator_physical_within_roots(folder, roots):
    try:
        candidate = Path(folder).expanduser().resolve()
    except (OSError, RuntimeError, ValueError):
        return None
    for root in roots:
        try:
            root_path = Path(root["folder"]).expanduser().resolve()
            candidate.relative_to(root_path)
            return candidate
        except (OSError, RuntimeError, ValueError):
            continue
    return None


def _validated_navigator_folder(category, folder):
    category = str(category or "").strip()
    folder = str(folder or "").strip()
    if not folder:
        return ""
    if not category:
        raise ValueError("Debe seleccionar una categoría antes de navegar una carpeta.")

    tree, roots = _navigator_category_roots(category)
    found = tree["folders"].get(folder.casefold())
    if found is not None and found[0] == category.casefold():
        return found[1]["folder"]

    physical = _navigator_physical_within_roots(folder, roots)
    if physical is None or not physical.is_dir():
        raise ValueError("La carpeta no pertenece al árbol activo de LexIA.")
    return str(physical)


def _navigator_folder_has_children(folder):
    try:
        return any(item.is_dir() for item in Path(folder).iterdir())
    except OSError:
        return False


def _navigator_child_nodes(category, parent_folder=""):
    category = str(category or "").strip()
    parent_folder = str(parent_folder or "").strip()
    tree, roots = _navigator_category_roots(category)
    nodes = {}

    if parent_folder:
        validated_parent = _validated_navigator_folder(category, parent_folder)
        found = tree["folders"].get(validated_parent.casefold())
        catalog_children = found[1]["children"].values() if found is not None else []
        physical_parents = [validated_parent]
    else:
        catalog_children = []
        physical_parents = []
        for root in roots:
            catalog_children.extend(root["children"].values())
            physical_parents.append(root["folder"])

    for node in catalog_children:
        nodes[node["folder"].casefold()] = {
            "kind": "folder",
            "name": node["name"],
            "category": category,
            "folder": node["folder"],
            "count": int(node["count"]),
            "has_children": bool(node["children"]),
        }

    for physical_parent in physical_parents:
        try:
            children = [item for item in Path(physical_parent).iterdir() if item.is_dir()]
        except OSError:
            continue
        for child in children:
            physical = _navigator_physical_within_roots(child, roots)
            if physical is None:
                continue
            key = str(physical).casefold()
            existing = nodes.get(key)
            if existing is None:
                nodes[key] = {
                    "kind": "folder",
                    "name": physical.name,
                    "category": category,
                    "folder": str(physical),
                    "count": 0,
                    "has_children": _navigator_folder_has_children(physical),
                }
            elif not existing["has_children"]:
                existing["has_children"] = _navigator_folder_has_children(physical)

    return sorted(nodes.values(), key=lambda item: item["name"].casefold())


def _navigator_root_nodes():
    summary = _catalog_category_summary()
    ordered = sorted(
        summary["categories"].values(),
        key=lambda item: (
            {"escritos": 0, "doctrina": 1, "jurisprudencia": 2, "legislacion": 3}.get(
                _filter_category_key(item["label"]), 99
            ),
            item["label"].casefold(),
        ),
    )
    return {
        "ok": True,
        "total": int(summary["total"]),
        "nodes": [
            {
                "kind": "category",
                "name": item["label"],
                "category": item["value"],
                "folder": "",
                "count": int(item["count"]),
                "has_children": True,
            }
            for item in ordered
        ],
    }


def _validated_navigator_selections(selections=None, category="", folder=""):
    """Validate one or more tree selections and return a stable unique list.

    An empty list means the complete Library. ``category`` and ``folder`` are
    retained as a backward-compatible single-selection input.
    """
    if selections is None:
        legacy_category = str(category or "").strip()
        legacy_folder = str(folder or "").strip()
        raw_selections = (
            [{"category": legacy_category, "folder": legacy_folder}]
            if legacy_category or legacy_folder else []
        )
    else:
        if not isinstance(selections, list):
            raise ValueError("La selección de carpetas debe ser una lista.")
        if len(selections) > 64:
            raise ValueError("Se pueden seleccionar hasta 64 carpetas simultáneamente.")
        raw_selections = selections

    normalized = []
    seen = set()
    for item in raw_selections:
        if not isinstance(item, dict):
            raise ValueError("La selección de carpetas contiene un elemento inválido.")
        selected_category = str(item.get("category", "") or "").strip()
        selected_folder = str(item.get("folder", "") or "").strip()
        if not selected_category and not selected_folder:
            raise ValueError("La selección de carpetas contiene una ubicación vacía.")
        if selected_folder:
            selected_folder = _validated_navigator_folder(
                selected_category, selected_folder
            )
        else:
            _navigator_category_roots(selected_category)

        key = (selected_category.casefold(), selected_folder.casefold())
        if key in seen:
            continue
        seen.add(key)
        normalized.append({
            "category": selected_category,
            "folder": selected_folder,
        })
    return normalized


def _navigator_browse_documents(
    query="", category="", folder="", selections=None,
    include_subfolders=True, sort="name_asc", limit=200, offset=0,
):
    query = str(query or "").strip()
    category = str(category or "").strip()
    folder = str(folder or "").strip()
    include_subfolders = bool(include_subfolders)
    sort = str(sort or "name_asc").strip().lower()
    limit = max(1, min(int(limit or 200), 200))
    offset = max(0, int(offset or 0))
    validated_selections = _validated_navigator_selections(
        selections=selections, category=category, folder=folder
    )

    db_path = _filter_catalog_path()
    if not db_path.exists():
        raise FileNotFoundError("No existe el catálogo LexIA.")

    where = ["COALESCE(is_deleted,0)=0"]
    params = []
    if query:
        where.append("name LIKE ? COLLATE NOCASE")
        params.append("%" + query + "%")
    if validated_selections:
        selection_clauses = []
        for selected in validated_selections:
            selection_clauses.append(
                "(category = ? AND (? = '' OR "
                "REPLACE(path, '\\', '/') LIKE ? COLLATE NOCASE ESCAPE '!'))"
            )
            selected_folder = selected["folder"]
            params.extend([
                selected["category"],
                selected_folder,
                _filter_like_pattern(selected_folder) if selected_folder else "",
            ])
        where.append("(" + " OR ".join(selection_clauses) + ")")

    sort_options = {
        "name_asc": "name COLLATE NOCASE ASC,path COLLATE NOCASE ASC",
        "name_desc": "name COLLATE NOCASE DESC,path COLLATE NOCASE DESC",
        "date_desc": (
            "CASE WHEN COALESCE(updated_at,'')='' THEN 1 ELSE 0 END ASC,"
            "updated_at DESC,name COLLATE NOCASE ASC"
        ),
        "date_asc": (
            "CASE WHEN COALESCE(updated_at,'')='' THEN 1 ELSE 0 END ASC,"
            "updated_at ASC,name COLLATE NOCASE ASC"
        ),
        "size_desc": "COALESCE(size,0) DESC,name COLLATE NOCASE ASC",
        "size_asc": "COALESCE(size,0) ASC,name COLLATE NOCASE ASC",
        "type_asc": (
            "COALESCE(extension,'') COLLATE NOCASE ASC,name COLLATE NOCASE ASC"
        ),
    }
    if sort not in sort_options:
        sort = "name_asc"

    where_sql = " AND ".join(where)
    order_sql = sort_options[sort]
    con = sqlite3.connect(str(db_path), timeout=10)
    con.row_factory = sqlite3.Row
    try:
        total = int(con.execute(
            "SELECT COUNT(*) FROM documents WHERE " + where_sql,
            params,
        ).fetchone()[0] or 0)
        rows = con.execute(
            "SELECT path,name,category,extension,size,total_pages,updated_at "
            "FROM documents WHERE " + where_sql + " "
            "ORDER BY " + order_sql + " LIMIT ? OFFSET ?",
            [*params, limit, offset],
        ).fetchall()
    finally:
        con.close()

    items = []
    for row in rows:
        _, parts = _filter_path_shape(row["path"])
        items.append({
            "document_path": str(row["path"] or ""),
            "document_name": str(row["name"] or "Documento"),
            "category": str(row["category"] or ""),
            "extension": str(row["extension"] or ""),
            "size": int(row["size"] or 0),
            "total_pages": row["total_pages"],
            "updated_at": str(row["updated_at"] or ""),
            "folder_name": str(parts[-2]) if len(parts) >= 2 else "",
        })

    return {
        "ok": True,
        "query": query,
        "category": (
            validated_selections[0]["category"]
            if len(validated_selections) == 1 else ""
        ),
        "folder": (
            validated_selections[0]["folder"]
            if len(validated_selections) == 1 else ""
        ),
        "selections": validated_selections,
        "include_subfolders": include_subfolders,
        "sort": sort,
        "total": total,
        "offset": offset,
        "limit": limit,
        "items": items,
        "has_more": offset + len(items) < total,
    }


def _navigator_document_preview(path_value):
    requested = str(path_value or "").strip()
    if not requested:
        raise ValueError("Falta la ruta del documento.")

    db_path = _filter_catalog_path()
    con = sqlite3.connect(str(db_path), timeout=10)
    con.row_factory = sqlite3.Row
    try:
        row = con.execute(
            "SELECT path,name,category,extension,size,total_pages,updated_at,text_content "
            "FROM documents WHERE path=? AND COALESCE(is_deleted,0)=0 LIMIT 1",
            (requested,),
        ).fetchone()
        if row is None:
            raise FileNotFoundError("El documento ya no está activo en el catálogo.")

        fragment = None
        fragment_text = ""
        fragment_count = 0
        try:
            fragment = con.execute(
                "SELECT fragment_index,page_start,page_end FROM fragments "
                "WHERE document_path=? ORDER BY fragment_index LIMIT 1",
                (requested,),
            ).fetchone()
            fragment_count = int(con.execute(
                "SELECT COUNT(*) FROM fragments WHERE document_path=?",
                (requested,),
            ).fetchone()[0] or 0)
        except sqlite3.OperationalError:
            fragment = None
            fragment_text = ""

        if fragment is not None:
            try:
                indexed = con.execute(
                    "SELECT text_content FROM fragments_fts "
                    "WHERE document_path=? AND fragment_index=? LIMIT 1",
                    (requested, fragment["fragment_index"]),
                ).fetchone()
                if indexed is not None:
                    fragment_text = str(indexed["text_content"] or "")
            except sqlite3.OperationalError:
                try:
                    indexed = con.execute(
                        "SELECT text_content FROM fragments "
                        "WHERE document_path=? AND fragment_index=? LIMIT 1",
                        (requested, fragment["fragment_index"]),
                    ).fetchone()
                    if indexed is not None:
                        fragment_text = str(indexed["text_content"] or "")
                except sqlite3.OperationalError:
                    fragment_text = ""
    finally:
        con.close()

    text = str(fragment_text or row["text_content"] or "").strip()
    page_start = fragment["page_start"] if fragment is not None else None
    page_end = fragment["page_end"] if fragment is not None else None
    return {
        "ok": True,
        "document": {
            "path": str(row["path"] or requested),
            "name": str(row["name"] or "Documento"),
            "category": str(row["category"] or ""),
            "extension": str(row["extension"] or ""),
            "size": int(row["size"] or 0),
            "total_pages": row["total_pages"],
            "updated_at": str(row["updated_at"] or ""),
            "fragment_count": fragment_count,
            "fragment_index": int(fragment["fragment_index"] or 0) if fragment is not None else None,
            "page_start": page_start,
            "page_end": page_end,
            "text": text[:8000],
            "file_exists": Path(str(row["path"] or requested)).is_file(),
        },
    }


def _navigator_mutation_folder(category, folder="", allow_category_root=False):
    """Resolve a navigator folder to one physical, catalog-owned directory."""
    category = str(category or "").strip()
    folder = str(folder or "").strip()
    if folder:
        return str(Path(_validated_navigator_folder(category, folder)).resolve())
    if not allow_category_root:
        raise ValueError("Debe seleccionar una carpeta concreta.")
    _tree, roots = _navigator_category_roots(category)
    available = [Path(item["folder"]).resolve() for item in roots if Path(item["folder"]).is_dir()]
    if len(available) != 1:
        raise ValueError("La categoría no tiene una carpeta raíz única para esta operación.")
    return str(available[0])


def _navigator_clean_folder_name(value):
    name = str(value or "").strip()
    if not name or name in {".", ".."} or len(name) > 80:
        raise ValueError("Indicá un nombre de carpeta válido, de hasta 80 caracteres.")
    if Path(name).name != name or any(char in name for char in '<>:"/\\|?*'):
        raise ValueError("El nombre de carpeta no puede contener barras ni caracteres reservados.")
    return name


def _navigator_operation_payload(body):
    if not isinstance(body, dict):
        raise ValueError("La operación del navegador es inválida.")
    operation = str(body.get("operation", "") or "").strip().lower()
    if operation == "create_folder":
        category = str(body.get("category", "") or "").strip()
        return {
            "operation": operation,
            "category": category,
            "parent": _navigator_mutation_folder(category, body.get("parent", ""), True),
            "name": _navigator_clean_folder_name(body.get("name", "")),
        }
    if operation == "delete_folder":
        category = str(body.get("category", "") or "").strip()
        return {
            "operation": operation,
            "category": category,
            "folder": _navigator_mutation_folder(category, body.get("folder", ""), False),
        }
    if operation == "move_folder":
        source_category = str(body.get("source_category", "") or "").strip()
        destination_category = str(body.get("destination_category", "") or "").strip()
        source = _navigator_mutation_folder(source_category, body.get("source_folder", ""), False)
        destination = _navigator_mutation_folder(destination_category, body.get("destination_folder", ""), True)
        if Path(source).resolve() == Path(destination).resolve():
            raise ValueError("La carpeta de destino debe ser distinta de la carpeta que se mueve.")
        return {
            "operation": operation,
            "source_category": source_category,
            "destination_category": destination_category,
            "source": source,
            "destination": destination,
        }
    if operation in {"move_files", "delete_files"}:
        raw_paths = body.get("paths") or []
        if not isinstance(raw_paths, list) or not raw_paths:
            raise ValueError("Seleccioná al menos un archivo.")
        if len(raw_paths) > 100:
            raise ValueError("Se pueden procesar hasta 100 archivos por operación.")
        paths, seen = [], set()
        for raw_path in raw_paths:
            resolved = _resolve_catalog_document(requested_path=str(raw_path or ""))
            if resolved.casefold() not in seen:
                seen.add(resolved.casefold())
                paths.append(resolved)
        payload = {"operation": operation, "paths": paths}
        if operation == "move_files":
            category = str(body.get("destination_category", "") or "").strip()
            payload.update({
                "destination_category": category,
                "destination": _navigator_mutation_folder(category, body.get("destination_folder", ""), True),
            })
        return payload
    raise ValueError("Operación de navegador no reconocida.")


def _search_filename_rows(query: str, limit: int = 100, category=None, folder=None):
    q = str(query or "").strip()
    if not q:
        return []

    normalized_query = _lexia321_norm(q)
    terms = [t for t in normalized_query.split() if t]
    if not terms:
        return []

    project_root = Path(__file__).resolve().parents[2]
    db = project_root / "runtime" / "lexia_catalog.sqlite3"
    if not db.exists():
        return []

    con = sqlite3.connect(str(db))
    con.row_factory = sqlite3.Row
    try:
        sql = (
            "SELECT path, name, category, updated_at "
            "FROM documents WHERE COALESCE(is_deleted,0)=0"
        )
        params = []
        category = str(category or "").strip() or None
        folder = _validated_filter_folder(category, folder)
        if category:
            sql += " AND category = ?"
            params.append(category)
        if folder:
            sql += (
                " AND REPLACE(path, '\\', '/') LIKE ? "
                "COLLATE NOCASE ESCAPE '!'"
            )
            params.append(_filter_like_pattern(folder))
        rows = con.execute(sql, params).fetchall()

        matched = []
        for row in rows:
            norm_name = _lexia321_norm(row["name"])
            if not all(term in norm_name for term in terms):
                continue

            if norm_name == normalized_query:
                quality = 0
            elif norm_name.startswith(normalized_query):
                quality = 1
            elif normalized_query in norm_name:
                quality = 2
            else:
                quality = 3

            matched.append({
                "document_path": row["path"],
                "document_name": row["name"],
                "category": row["category"],
                "updated_at": row["updated_at"],
                "_quality": quality,
            })

        matched.sort(
            key=lambda r: (
                r["_quality"],
                _lexia321_norm(r["document_name"]),
                str(r["document_path"]).lower(),
            )
        )

        out = matched[:max(1, int(limit))]
        for item in out:
            item.pop("_quality", None)
        return out
    finally:
        con.close()

def _record_ui2_search_history(query: str, mode: str):
    value = str(query or "").strip()
    search_mode = str(mode or "").strip().lower()
    if not value or search_mode not in ("filename", "professional"):
        return
    project_root = Path(__file__).resolve().parents[2]
    db = project_root / "runtime" / "search_history.sqlite3"
    con = sqlite3.connect(str(db), timeout=5)
    try:
        con.execute(
            "CREATE TABLE IF NOT EXISTS ui2_search_history_v2 ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "mode TEXT NOT NULL, query TEXT NOT NULL, "
            "created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
        )
        con.execute(
            "INSERT INTO ui2_search_history_v2(mode,query,created_at) "
            "VALUES (?,?,CURRENT_TIMESTAMP)",
            (search_mode, value),
        )
        con.commit()
    finally:
        con.close()


def _search_history_items(mode: str, limit: int = 10):
    search_mode = str(mode or "").strip().lower()
    if search_mode not in ("filename", "professional"):
        return []
    project_root = Path(__file__).resolve().parents[2]
    db = project_root / "runtime" / "search_history.sqlite3"
    if not db.exists():
        return []
    con = sqlite3.connect(str(db))
    con.row_factory = sqlite3.Row
    try:
        try:
            rows = con.execute(
                "SELECT query,MAX(id) AS last_id "
                "FROM ui2_search_history_v2 "
                "WHERE mode=? AND TRIM(query)<>'' "
                "GROUP BY query ORDER BY last_id DESC LIMIT ?",
                (search_mode, int(limit)),
            ).fetchall()
        except sqlite3.Error:
            return []
        return [
            {"query": str(r["query"]).strip()}
            for r in rows
            if str(r["query"] or "").strip()
        ]
    finally:
        con.close()

def _normalize_preview_words(text):
    import re as _re
    words = _re.findall(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9]{4,}", str(text or "").lower())
    stop = {
        "para","como","esta","este","estos","estas","desde","hasta","sobre",
        "entre","porque","cuando","donde","cual","cuales","tambien","mediante",
        "documento","pagina","paginas","archivo"
    }
    out=[]
    seen=set()
    for w in words:
        if w in stop or w in seen:
            continue
        seen.add(w)
        out.append(w)
        if len(out) >= 60:
            break
    return out


def _resolve_catalog_document(requested_path="", name="", snippet=""):
    project_root = Path(__file__).resolve().parents[2]
    db = project_root / "runtime" / "lexia_catalog.sqlite3"
    if not db.exists():
        raise FileNotFoundError("No existe el catálogo LexIA.")

    requested = str(requested_path or "").strip()
    requested_obj = Path(requested).expanduser() if requested else None

    con = sqlite3.connect(str(db))
    con.row_factory = sqlite3.Row
    try:
        if requested:
            row = con.execute(
                "SELECT path,name FROM documents WHERE path=? "
                "AND COALESCE(is_deleted,0)=0 LIMIT 1",
                (requested,),
            ).fetchone()
            if row is not None and Path(row["path"]).exists():
                return str(Path(row["path"]).resolve())

        clean_name = str(name or "").strip()
        if not clean_name and requested_obj is not None:
            clean_name = requested_obj.name
        if not clean_name:
            raise FileNotFoundError("El resultado no contiene un nombre de archivo.")

        rows = con.execute(
            "SELECT path,name,text_content FROM documents "
            "WHERE name=? COLLATE NOCASE AND COALESCE(is_deleted,0)=0",
            (clean_name,),
        ).fetchall()

        existing = [r for r in rows if Path(r["path"]).exists()]
        if not existing:
            raise FileNotFoundError("Archivo no encontrado.")
        if len(existing) == 1:
            return str(Path(existing[0]["path"]).resolve())

        words = _normalize_preview_words(snippet)
        if words:
            scored=[]
            for row in existing:
                text = str(row["text_content"] or "").lower()
                score = sum(1 for w in words if w in text)
                scored.append((score, row))
            scored.sort(key=lambda x:x[0], reverse=True)
            best_score, best_row = scored[0]
            second_score = scored[1][0] if len(scored) > 1 else -1
            if best_score >= 3 and best_score > second_score:
                return str(Path(best_row["path"]).resolve())

        raise RuntimeError(
            f"Hay {len(existing)} archivos activos llamados '{clean_name}' "
            "y no fue posible determinar con seguridad cuál corresponde al resultado."
        )
    finally:
        con.close()


def _catalog_document_details(path_value):
    """Return verified catalog and filesystem metadata for one active document."""
    project_root = Path(__file__).resolve().parents[2]
    db = project_root / "runtime" / "lexia_catalog.sqlite3"
    if not db.exists():
        raise FileNotFoundError("No existe el catálogo LexIA.")

    requested = str(path_value or "").strip()
    if not requested:
        raise ValueError("Falta la ubicación del documento.")

    file_path = Path(requested).expanduser().resolve()

    con = sqlite3.connect(str(db))
    con.row_factory = sqlite3.Row
    try:
        row = con.execute(
            "SELECT path,name,category,extension,size,modified_ns,content_hash,"
            "vector_indexed_hash,LENGTH(text_content) AS text_characters,"
            "extraction_error,metadata_json,extraction_method,ocr_pages,"
            "total_pages,duplicate_of,updated_at "
            "FROM documents WHERE path IN (?, ?) "
            "AND COALESCE(is_deleted,0)=0 LIMIT 1",
            (requested, str(file_path)),
        ).fetchone()

        if row is None:
            raise PermissionError(
                "El documento no pertenece al catálogo activo de LexIA."
            )

        catalog_path = str(row["path"] or requested)
        stored_path = Path(catalog_path).expanduser()
        exists = stored_path.exists() and stored_path.is_file()
        stat = stored_path.stat() if exists else None

        fragments = con.execute(
            "SELECT COUNT(*) AS total, MIN(page_start) AS first_page, "
            "MAX(page_end) AS last_page FROM fragments WHERE document_path=?",
            (catalog_path,),
        ).fetchone()

        raw_metadata = {}
        try:
            candidate = json.loads(str(row["metadata_json"] or "{}"))
            if isinstance(candidate, dict):
                raw_metadata = candidate
        except Exception:
            raw_metadata = {}

        aliases = (
            ("Tribunal", ("tribunal", "court")),
            ("Organismo", ("organismo", "agency", "body")),
            ("Jurisdicción", ("jurisdiccion", "jurisdicción", "jurisdiction")),
            ("Fecha del documento", ("fecha", "fecha_documento", "document_date")),
            ("Fuente", ("fuente", "source")),
        )
        normalized_metadata = {
            str(key).strip().lower(): value
            for key, value in raw_metadata.items()
            if value not in (None, "", [], {})
        }
        extra_metadata = []
        for label, keys in aliases:
            value = next(
                (normalized_metadata[key] for key in keys if key in normalized_metadata),
                None,
            )
            if value not in (None, "", [], {}):
                if isinstance(value, (dict, list)):
                    value = json.dumps(value, ensure_ascii=False)
                extra_metadata.append({"label": label, "value": str(value)[:500]})

        content_hash = str(row["content_hash"] or "")
        vector_hash = str(row["vector_indexed_hash"] or "")
        text_characters = int(row["text_characters"] or 0)
        extraction_error = str(row["extraction_error"] or "").strip()

        if extraction_error:
            index_status = "Con error de extracción"
        elif text_characters <= 0:
            index_status = "Sin texto extraído"
        elif vector_hash and content_hash and vector_hash == content_hash:
            index_status = "Indexado"
        elif vector_hash:
            index_status = "Índice desactualizado"
        else:
            index_status = "Pendiente de indexación"

        return {
            "name": str(row["name"] or stored_path.name),
            "path": catalog_path,
            "directory": str(stored_path.parent),
            "folder": stored_path.parent.name,
            "category": str(row["category"] or "Sin categoría"),
            "extension": str(row["extension"] or stored_path.suffix or "").lower(),
            "size": int(stat.st_size if stat is not None else (row["size"] or 0)),
            "exists": bool(exists),
            "physical_modified_ms": (
                int(stat.st_mtime_ns // 1_000_000) if stat is not None else None
            ),
            "catalog_updated_at": str(row["updated_at"] or ""),
            "total_pages": (
                int(row["total_pages"]) if row["total_pages"] is not None else None
            ),
            "ocr_pages": int(row["ocr_pages"] or 0),
            "fragment_count": int(fragments["total"] or 0),
            "first_indexed_page": (
                int(fragments["first_page"])
                if fragments["first_page"] is not None else None
            ),
            "last_indexed_page": (
                int(fragments["last_page"])
                if fragments["last_page"] is not None else None
            ),
            "text_characters": text_characters,
            "extraction_method": str(row["extraction_method"] or "native"),
            "extraction_error": extraction_error or None,
            "index_status": index_status,
            "vector_indexed": bool(
                vector_hash and content_hash and vector_hash == content_hash
            ),
            "duplicate_of": str(row["duplicate_of"] or "") or None,
            "extra_metadata": extra_metadata,
        }
    finally:
        con.close()


# >>> LEXIA UI2 3.2.4o CLASSIC CORE DELETE BRIDGE
def _start_core_document_delete(path_value, confirmed_name):
    payload, _ = _delete_bridge_request(
        "POST",
        "/api/delete-file",
        {
            "path": str(path_value or ""),
            "confirm_name": str(confirmed_name or ""),
        },
    )
    return payload


def _core_document_delete_state():
    payload, _ = _delete_bridge_request("GET", "/api/delete-file-status")
    return payload


def _core_import_files(destination, sources):
    payload, _ = _delete_bridge_request(
        "POST", "/api/import-files",
        {"destination": str(destination or ""), "sources": sources},
    )
    return payload


def _core_study_document(path, objective, instruction, document_type):
    payload, _ = _delete_bridge_request(
        "POST", "/api/study-document",
        {"path": str(path or ""), "objective": objective, "instruction": instruction, "document_type": document_type},
    )
    return payload


def _core_research_start(payload):
    response, _ = _delete_bridge_request("POST", "/api/research-start", payload)
    return response


def _core_research_status():
    response, _ = _delete_bridge_request("GET", "/api/research-status")
    return response


def _core_research_result():
    response, _ = _delete_bridge_request("GET", "/api/research-result")
    return response


def _core_research_candidates_start(payload):
    response, _ = _delete_bridge_request("POST", "/api/research-candidates-start", payload)
    return response


def _core_research_candidates_cancel(payload):
    response, _ = _delete_bridge_request("POST", "/api/research-candidates-cancel", payload)
    return response


def _core_research_candidates_pause(payload):
    response, _ = _delete_bridge_request("POST", "/api/research-candidates-pause", payload)
    return response


def _core_research_candidates_resume(payload):
    response, _ = _delete_bridge_request("POST", "/api/research-candidates-resume", payload)
    return response


def _core_research_candidates_status():
    response, _ = _delete_bridge_request("GET", "/api/research-candidates-status")
    return response


def _core_research_candidates_result():
    response, _ = _delete_bridge_request("GET", "/api/research-candidates-result")
    return response


def _core_research_package_start(payload):
    response, _ = _delete_bridge_request("POST", "/api/research-package-start", payload)
    return response


def _core_research_package_status():
    response, _ = _delete_bridge_request("GET", "/api/research-package-status")
    return response


def _core_research_package_result():
    response, _ = _delete_bridge_request("GET", "/api/research-package-result")
    return response



def _core_navigator_operation(payload):
    response, _ = _delete_bridge_request("POST", "/api/navigator-operation", payload)
    return response


def _core_navigator_operation_status():
    response, _ = _delete_bridge_request("GET", "/api/navigator-operation-status")
    return response


def _core_study_start(payload):
    response, _ = _delete_bridge_request("POST", "/api/study-start", payload)
    return response


def _core_study_status():
    response, _ = _delete_bridge_request("GET", "/api/study-status")
    return response


def _core_study_result():
    response, _ = _delete_bridge_request("GET", "/api/study-result")
    return response


def _direct_import_files(category, destination, sources):
    validated = Path(_validated_navigator_folder(category, destination)).resolve()
    imported, skipped, errors = [], [], []
    for item in sources:
        clean_name = Path(str(item.get("name", "") or "")).name
        target = (validated / clean_name).resolve()
        try:
            target.relative_to(validated)
            if target.exists():
                skipped.append(str(target))
                continue
            temporary = validated / ("." + uuid.uuid4().hex + "_" + clean_name + ".lexia-importing")
            try:
                shutil.copyfile(item["path"], temporary)
                os.replace(temporary, target)
            finally:
                temporary.unlink(missing_ok=True)
            imported.append(str(target))
        except Exception as exc:
            errors.append(clean_name + ": " + str(exc))
    return {
        "ok": True, "imported": imported, "skipped": skipped, "errors": errors,
        "destination": str(validated), "autosync_mode": "existing_classic_watcher",
    }


def _read_navigator_import(handler):
    content_type = str(handler.headers.get("Content-Type", "") or "")
    length = int(handler.headers.get("Content-Length", "0") or 0)
    if "multipart/form-data" not in content_type.lower():
        raise ValueError("La importación requiere archivos multipart.")
    if length <= 0 or length > 268435456:
        raise ValueError("La importación supera el límite de 256 MB.")
    raw = handler.rfile.read(length)
    message = BytesParser(policy=email_policy).parsebytes(
        ("Content-Type: " + content_type + "\r\nMIME-Version: 1.0\r\n\r\n").encode("utf-8") + raw
    )
    destination = ""
    category = ""
    uploads = []
    staging = PROJECT_ROOT / "runtime" / "ui2_import_staging" / uuid.uuid4().hex
    staging.mkdir(parents=True, exist_ok=False)
    allowed = {".pdf", ".doc", ".docx", ".odt", ".txt"}
    try:
        for part in message.iter_parts():
            field = str(part.get_param("name", header="content-disposition") or "")
            if field == "destination":
                destination = part.get_payload(decode=True).decode("utf-8").strip()
            elif field == "category":
                category = part.get_payload(decode=True).decode("utf-8").strip()
            elif field == "files":
                supplied = str(part.get_filename() or "")
                clean_name = Path(supplied).name
                extension = Path(clean_name).suffix.lower()
                if not clean_name or clean_name != supplied or extension not in allowed:
                    raise ValueError("Nombre o extensión no admitidos: " + supplied)
                target = staging / (uuid.uuid4().hex + "_" + clean_name)
                target.write_bytes(part.get_payload(decode=True) or b"")
                uploads.append({"path": str(target), "name": clean_name})
        if not category or not destination or not uploads:
            raise ValueError("Falta la carpeta de destino o los archivos.")
        return category, destination, uploads, staging
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
# <<< LEXIA UI2 3.2.4o CLASSIC CORE DELETE BRIDGE


def _lexia321_enrich_search_results(results):
    if not isinstance(results, list) or not results:
        return results

    project_root = Path(__file__).resolve().parents[2]
    db = project_root / "runtime" / "lexia_catalog.sqlite3"
    if not db.exists():
        return results

    path_to_items = {}
    for item in results:
        if not isinstance(item, dict):
            continue
        path = str(item.get("document_path") or "").strip()
        if path:
            path_to_items.setdefault(path, []).append(item)

    con = sqlite3.connect(str(db))
    con.row_factory = sqlite3.Row
    try:
        # 1) Resolver todas las rutas en consultas por lotes.
        unique_paths = list(path_to_items.keys())
        for start in range(0, len(unique_paths), 700):
            batch = unique_paths[start:start + 700]
            if not batch:
                continue
            placeholders = ",".join("?" for _ in batch)
            rows = con.execute(
                "SELECT path, category, updated_at "
                "FROM documents "
                "WHERE COALESCE(is_deleted,0)=0 "
                f"AND path IN ({placeholders})",
                batch,
            ).fetchall()

            for row in rows:
                for item in path_to_items.get(row["path"], []):
                    if not item.get("category"):
                        item["category"] = row["category"]
                    item["updated_at"] = row["updated_at"]

        # 2) Sólo para resultados cuya ruta histórica no resolvió:
        #    buscar nombres en lotes, sin ejecutar un SELECT por resultado.
        missing = [
            item for item in results
            if isinstance(item, dict) and not item.get("updated_at")
        ]

        names = list(dict.fromkeys(
            str(item.get("document_name") or "").strip()
            for item in missing
            if str(item.get("document_name") or "").strip()
        ))

        name_map = {}
        for start in range(0, len(names), 700):
            batch = names[start:start + 700]
            if not batch:
                continue
            placeholders = ",".join("?" for _ in batch)
            rows = con.execute(
                "SELECT name, path, category, updated_at "
                "FROM documents "
                "WHERE COALESCE(is_deleted,0)=0 "
                f"AND name IN ({placeholders})",
                batch,
            ).fetchall()

            for row in rows:
                key = str(row["name"] or "").lower()
                name_map.setdefault(key, []).append(row)

        for item in missing:
            key = str(item.get("document_name") or "").strip().lower()
            candidates = name_map.get(key, [])
            if len(candidates) == 1:
                row = candidates[0]
                if not item.get("category"):
                    item["category"] = row["category"]
                item["updated_at"] = row["updated_at"]

        return results
    finally:
        con.close()


# >>> LEXIA CONTENT SEARCH 2.1 MATCH-CENTERED
# >>> LEXIA CONTENT SEARCH 2.0 FTS5-FIRST
_CONTENT_SEARCH_STOPWORDS = {
    "a","al","algo","ante","bajo","con","contra","cual","cuales","como","de","del",
    "desde","donde","dos","el","ella","ellas","ellos","en","entre","era","es","esa",
    "ese","eso","esta","este","esto","estos","estas","fue","ha","hay","la","las","lo",
    "los","mas","más","mediante","no","o","para","pero","por","porque","que","qué",
    "se","si","sin","sobre","su","sus","un","una","uno","unos","unas","y"
}


def _content_search_terms(query):
    import re as _re
    raw = str(query or "").strip()
    phrases = [
        p.strip()
        for p in _re.findall(r'"([^"]+)"', raw)
        if p.strip()
    ]
    without_phrases = _re.sub(r'"[^"]+"', " ", raw)

    tokens = _re.findall(
        r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9][A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9._/-]*",
        without_phrases,
    )
    terms = []
    seen = set()
    for token in tokens:
        value = token.strip("._/-").lower()
        if not value or value in _CONTENT_SEARCH_STOPWORDS:
            continue
        if len(value) == 1 and not value.isdigit():
            continue
        if value not in seen:
            seen.add(value)
            terms.append(value)

    return raw, phrases, terms


def _fts_quote(value):
    return '"' + str(value).replace('"', '""') + '"'


def _content_norm(value):
    import re as _re
    import unicodedata as _ud
    text = _ud.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not _ud.combining(ch))
    text = text.lower()
    text = _re.sub(r"\s+", " ", text)
    return text.strip()


def _content_search_v2(
    query, limit=20, category=None, folder=None, semantic_fallback=False,
):
    """Fast FTS5 content retrieval over LexIA's existing fragments index.

    Priority:
      1) exact phrase / explicitly quoted phrases,
      2) all meaningful query terms (AND),
      3) partial lexical matches (OR),
      4) optional semantic filler only when it is explicitly requested.
    """
    from time import perf_counter
    started = perf_counter()

    raw, phrases, terms = _content_search_terms(query)
    if not raw:
        raise ValueError("La consulta está vacía.")

    limit = max(1, min(int(limit or 20), 50))
    # A modest candidate pool is enough for the visible result list and avoids
    # normalizing hundreds of long fragments on every keystroke/search.
    wanted = max(limit * 4, 80)
    category = str(category or "").strip() or None
    if category in {"Todos", "Todas"}:
        category = None
    folder = _validated_filter_folder(category, folder)

    project_root = Path(__file__).resolve().parents[2]
    db_path = project_root / "runtime" / "lexia_catalog.sqlite3"
    if not db_path.exists():
        raise FileNotFoundError("No existe el catálogo LexIA.")

    # If the user did not quote anything, the full query itself is still an
    # important legal phrase candidate. This strongly favors literal formulations
    # such as "solve et repete", "plazo razonable", "acción de repetición", etc.
    auto_phrase = ""
    raw_words = [w for w in raw.split() if w]
    if not phrases and 2 <= len(raw_words) <= 12:
        auto_phrase = raw

    stages = []
    if phrases:
        stages.append(("phrase", " AND ".join(_fts_quote(p) for p in phrases)))
    elif auto_phrase:
        stages.append(("phrase", _fts_quote(auto_phrase)))

    if terms:
        stages.append(("and", " AND ".join(_fts_quote(t) for t in terms)))
        if len(terms) > 1:
            stages.append(("or", " OR ".join(_fts_quote(t) for t in terms)))

    if not stages:
        stages.append(("phrase", _fts_quote(raw)))

    normalized_raw = _content_norm(raw)
    normalized_terms = [_content_norm(t) for t in terms if t]
    normalized_phrases = [_content_norm(p) for p in phrases if p]

    candidates = {}
    con = sqlite3.connect(str(db_path), timeout=10)
    con.row_factory = sqlite3.Row
    try:
        # Verify that the FTS table is really present and populated.
        fts_exists = con.execute(
            "SELECT 1 FROM sqlite_master "
            "WHERE type='table' AND name='fragments_fts'"
        ).fetchone()
        if not fts_exists:
            raise RuntimeError("El índice FTS5 fragments_fts no existe.")

        for stage_index, (stage_name, match_query) in enumerate(stages):
            params = [match_query]
            category_sql = ""
            if category:
                category_sql = " AND f.category = ? "
                params.append(category)
            folder_sql = ""
            if folder:
                folder_sql = (
                    " AND REPLACE(f.document_path, '\\', '/') LIKE ? "
                    "COLLATE NOCASE ESCAPE '!' "
                )
                params.append(_filter_like_pattern(folder))
            params.append(wanted)

            sql = (
                "SELECT "
                " f.document_path, f.fragment_index, f.category, "
                " f.document_name, f.text_content, "
                " snippet(fragments_fts, 4, '', '', ' … ', 64) AS match_snippet, "
                " fr.page_start, fr.page_end, "
                " bm25(fragments_fts, 1.0) AS lexical_bm25 "
                "FROM fragments_fts AS f "
                "LEFT JOIN fragments AS fr "
                " ON fr.document_path=f.document_path "
                " AND fr.fragment_index=CAST(f.fragment_index AS INTEGER) "
                "LEFT JOIN documents AS d ON d.path=f.document_path "
                "WHERE fragments_fts MATCH ? "
                + category_sql +
                folder_sql +
                " AND COALESCE(d.is_deleted,0)=0 "
                "ORDER BY lexical_bm25 ASC "
                "LIMIT ?"
            )

            try:
                rows = con.execute(sql, params).fetchall()
            except sqlite3.OperationalError:
                # A malformed punctuation-heavy query should never break search.
                continue

            for row_position, row in enumerate(rows):
                path = str(row["document_path"] or "")
                frag_index = int(row["fragment_index"] or 0)
                key = (path, frag_index)

                text = str(row["text_content"] or "")
                match_snippet = str(row["match_snippet"] or "").strip()
                normalized = _content_norm(text)
                coverage = sum(1 for t in normalized_terms if t and t in normalized)
                all_terms = bool(normalized_terms) and coverage == len(normalized_terms)
                full_phrase = bool(normalized_raw) and normalized_raw in normalized
                quoted_hits = sum(
                    1 for p in normalized_phrases if p and p in normalized
                )

                # Stable, interpretable legal ranking. Stage weight dominates:
                # exact phrase > AND > OR. Lexical BM25 then breaks ties.
                stage_bonus = {"phrase": 10000, "and": 6000, "or": 2000}[stage_name]
                score = float(stage_bonus)
                if full_phrase:
                    score += 5000
                score += quoted_hits * 2500
                if all_terms:
                    score += 2000
                score += coverage * 350
                score -= row_position * 0.5

                try:
                    bm25_value = float(row["lexical_bm25"] or 0.0)
                    # FTS5 bm25 is lower/better and frequently negative.
                    score += max(-500.0, min(500.0, -bm25_value * 100.0))
                except Exception:
                    pass

                previous = candidates.get(key)
                if previous is None or score > previous["_rank_score"]:
                    candidates[key] = {
                        "document_path": path,
                        "document_name": str(
                            row["document_name"] or Path(path).name or "Documento"
                        ),
                        "category": str(row["category"] or ""),
                        "text": match_snippet or text,
                        "page_start": row["page_start"],
                        "page_end": row["page_end"],
                        "lexical_rank": stage_index + 1,
                        "semantic_rank": None,
                        "_rank_score": score,
                        "_source": "fts5",
                    }

            # Enough strong phrase/AND hits: don't let broad OR noise swamp them.
            strong_count = sum(
                1 for item in candidates.values()
                if item["_rank_score"] >= 6000
            )
            if strong_count >= limit and stage_name in {"phrase", "and"}:
                break
    finally:
        con.close()

    ordered = sorted(
        candidates.values(),
        key=lambda item: (
            -item["_rank_score"],
            str(item["document_name"]).lower(),
            int(item.get("page_start") or 0),
        ),
    )

    # Prefer diversity: at most 3 fragments from the same document in the first pass.
    selected = []
    per_document = {}
    used_keys = set()
    for item in ordered:
        path = item["document_path"]
        if per_document.get(path, 0) >= 3:
            continue
        key = (path, item.get("page_start"), item["text"][:120])
        if key in used_keys:
            continue
        used_keys.add(key)
        selected.append(item)
        per_document[path] = per_document.get(path, 0) + 1
        if len(selected) >= limit:
            break

    # Qdrant/embeddings may take seconds to initialize. The normal Contenido
    # action is deliberately FTS5-only; semantic filling remains available for
    # an explicit future action without blocking ordinary legal searches.
    if semantic_fallback and len(selected) < limit:
        try:
            semantic_payload = get_search().search(
                query=raw,
                limit=max(limit * 8, 100) if folder else max(limit * 2, 20),
                category=category,
            )
            semantic_rows = (
                semantic_payload.get("results", [])
                if isinstance(semantic_payload, dict)
                else []
            )
            seen_paths_text = {
                (x["document_path"], _content_norm(x["text"])[:180])
                for x in selected
            }
            sem_rank = 0
            for row in semantic_rows:
                if not isinstance(row, dict):
                    continue
                path = str(row.get("document_path") or row.get("path") or "")
                if folder and not _filter_path_is_within(path, folder):
                    continue
                text = str(
                    row.get("text")
                    or row.get("snippet")
                    or row.get("content")
                    or ""
                )
                key = (path, _content_norm(text)[:180])
                if not path or key in seen_paths_text:
                    continue
                sem_rank += 1
                selected.append({
                    "document_path": path,
                    "document_name": str(
                        row.get("document_name")
                        or row.get("name")
                        or row.get("title")
                        or Path(path).name
                        or "Documento"
                    ),
                    "category": str(row.get("category") or ""),
                    "text": text,
                    "page_start": row.get("page_start"),
                    "page_end": row.get("page_end"),
                    "lexical_rank": None,
                    "semantic_rank": sem_rank,
                    "_rank_score": 500.0 - sem_rank,
                    "_source": "semantic",
                })
                seen_paths_text.add(key)
                if len(selected) >= limit:
                    break
        except Exception:
            pass

    results = []
    for rank, item in enumerate(selected[:limit], start=1):
        source = item.pop("_source", "fts5")
        raw_score = float(item.pop("_rank_score", 0.0))
        # UI score is descriptive, not a probability.
        if source == "fts5":
            display_score = min(99.9, 70.0 + min(29.9, raw_score / 500.0))
        else:
            display_score = max(1.0, min(69.9, raw_score / 10.0))
        item["rank"] = rank
        item["score"] = round(display_score, 1)
        results.append(item)

    return {
        "ok": True,
        "query": raw,
        "results": results,
        "elapsed_seconds": round(perf_counter() - started, 4),
        "service": "LexIA Content Search 2.1",
        "search_strategy": "fts5_match_centered_hybrid",
    }
# <<< LEXIA CONTENT SEARCH 2.0 FTS5-FIRST

def _maintenance_snapshot():
    """Read live maintenance state from the process that owns LexIA."""
    response, _ = _delete_bridge_request("GET", "/api/maintenance-snapshot")
    return response


def _maintenance_create_backup():
    """Create an operational backup through the live LexIA service."""
    response, _ = _delete_bridge_request(
        "POST", "/api/maintenance-action", {"action": "backup"}
    )
    return response


def _maintenance_action(body):
    """Run an explicit action in the process that owns the services."""
    response, _ = _delete_bridge_request(
        "POST", "/api/maintenance-action", body
    )
    return response


class Handler(SimpleHTTPRequestHandler):
    def _json(self, payload, status=200):
        raw = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.end_headers()
        self.wfile.write(raw)

    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/api/maintenance-action":
            try:
                length = int(self.headers.get("Content-Length", "0") or 0)
                raw = self.rfile.read(length) if length else b"{}"
                body = json.loads(raw.decode("utf-8"))
                if not isinstance(body, dict):
                    raise ValueError("La solicitud debe ser un objeto JSON.")
                return self._json(_maintenance_action(body))
            except _DeleteBridgeError as exc:
                return self._json({"ok": False, "error": str(exc)}, exc.status)
            except (ValueError, FileNotFoundError, PermissionError, RuntimeError) as exc:
                return self._json({"ok": False, "error": str(exc)}, 409)
            except Exception as exc:
                return self._json({"ok": False, "error": str(exc)}, 500)
        if path == "/api/maintenance-backup":
            try:
                return self._json(_maintenance_create_backup())
            except _DeleteBridgeError as exc:
                return self._json({"ok": False, "error": str(exc)}, exc.status)
            except Exception as exc:
                return self._json({"ok": False, "error": str(exc)}, 500)
        if path in {"/api/research-start", "/api/study-start", "/api/research-candidates-start", "/api/research-candidates-cancel", "/api/research-candidates-pause", "/api/research-candidates-resume", "/api/research-package-start", "/api/navigator-operation"}:
            try:
                length = int(self.headers.get("Content-Length", "0") or 0)
                raw = self.rfile.read(length) if length else b"{}"
                body = json.loads(raw.decode("utf-8"))
                if path == "/api/navigator-operation":
                    return self._json(_core_navigator_operation(_navigator_operation_payload(body)), 202)
                payload = {
                    "/api/research-start": _core_research_start,
                    "/api/study-start": _core_study_start,
                    "/api/research-candidates-start": _core_research_candidates_start,
                    "/api/research-candidates-cancel": _core_research_candidates_cancel,
                    "/api/research-candidates-pause": _core_research_candidates_pause,
                    "/api/research-candidates-resume": _core_research_candidates_resume,
                    "/api/research-package-start": _core_research_package_start,
                }[path](body)
                return self._json(payload, 202)
            except _DeleteBridgeError as exc:
                return self._json({"ok": False, "error": str(exc)}, exc.status)
            except (ValueError, FileNotFoundError, PermissionError, RuntimeError) as exc:
                return self._json({"ok": False, "error": str(exc)}, 409)
            except Exception as exc:
                return self._json({"ok": False, "error": str(exc)}, 500)

        if path == "/api/study-document":
            try:
                length = int(self.headers.get("Content-Length", "0") or 0)
                raw = self.rfile.read(length) if length else b"{}"
                body = json.loads(raw.decode("utf-8"))
                return self._json(_core_study_document(
                    body.get("path", ""), body.get("objective", ""),
                    body.get("instruction", ""), body.get("document_type", ""),
                ))
            except _DeleteBridgeError as exc:
                return self._json({"ok": False, "error": str(exc)}, exc.status)
            except (ValueError, FileNotFoundError, PermissionError) as exc:
                return self._json({"ok": False, "error": str(exc)}, 409)
            except Exception as exc:
                return self._json({"ok": False, "error": str(exc)}, 500)

        if path == "/api/navigator-import":
            staging = None
            try:
                category, destination, sources, staging = _read_navigator_import(self)
                try:
                    payload = _core_import_files(destination, sources)
                except _DeleteBridgeError as exc:
                    if exc.status != 404:
                        raise
                    payload = _direct_import_files(category, destination, sources)
                return self._json(payload)
            except _DeleteBridgeError as exc:
                return self._json({"ok": False, "error": str(exc)}, exc.status)
            except (ValueError, FileNotFoundError, PermissionError) as exc:
                return self._json({"ok": False, "error": str(exc)}, 409)
            except Exception as exc:
                return self._json({"ok": False, "error": str(exc)}, 500)
            finally:
                if staging is not None:
                    shutil.rmtree(staging, ignore_errors=True)

        if path == "/api/search-history-record":
            try:
                length = int(self.headers.get("Content-Length", "0") or 0)
                raw = self.rfile.read(length) if length else b"{}"
                body = json.loads(raw.decode("utf-8"))
                query = str(body.get("query", "") or "").strip()
                mode = str(body.get("mode", "") or "").strip().lower()
                _record_ui2_search_history(query, mode)
                return self._json({"ok": True, "query": query, "mode": mode})
            except Exception as exc:
                return self._json({"ok": False, "error": str(exc)}, 500)

        if path == "/api/search-result-meta":
            try:
                length = int(self.headers.get("Content-Length", "0") or 0)
                raw = self.rfile.read(length) if length else b"{}"
                body = json.loads(raw.decode("utf-8"))
                items = body.get("items") or []
                enriched = _lexia321_enrich_search_results(items)
                return self._json({"ok": True, "items": enriched})
            except Exception as exc:
                return self._json({"ok": False, "error": str(exc)}, 500)


        if path == "/api/resolve-document":
            try:
                length = int(self.headers.get("Content-Length", "0") or 0)
                raw = self.rfile.read(length) if length else b"{}"
                body = json.loads(raw.decode("utf-8"))
                resolved = _resolve_catalog_document(
                    body.get("path", ""),
                    body.get("name", ""),
                    body.get("snippet", ""),
                )
                return self._json({"ok": True, "path": resolved})
            except Exception as exc:
                return self._json({"ok": False, "error": str(exc)}, 409)

        if path == "/api/file-details":
            try:
                length = int(self.headers.get("Content-Length", "0") or 0)
                raw = self.rfile.read(length) if length else b"{}"
                body = json.loads(raw.decode("utf-8"))
                details = _catalog_document_details(body.get("path", ""))
                return self._json({"ok": True, "details": details})
            except (FileNotFoundError, PermissionError, ValueError) as exc:
                return self._json({"ok": False, "error": str(exc)}, 404)
            except Exception as exc:
                return self._json({"ok": False, "error": str(exc)}, 500)

        if path == "/api/delete-file":
            try:
                length = int(self.headers.get("Content-Length", "0") or 0)
                raw = self.rfile.read(length) if length else b"{}"
                body = json.loads(raw.decode("utf-8"))
                payload = _start_core_document_delete(
                    body.get("path", ""),
                    body.get("confirm_name", ""),
                )
                return self._json(payload, 202)
            except _DeleteBridgeError as exc:
                return self._json({"ok": False, "error": str(exc)}, exc.status)
            except Exception as exc:
                return self._json({"ok": False, "error": str(exc)}, 500)


        if path == "/api/navigator-documents":
            try:
                length = int(self.headers.get("Content-Length", "0") or 0)
                raw = self.rfile.read(length) if length else b"{}"
                body = json.loads(raw.decode("utf-8"))
                payload = _navigator_browse_documents(
                    query=body.get("query", ""),
                    category=body.get("category", ""),
                    folder=body.get("folder", ""),
                    selections=body.get("selections"),
                    include_subfolders=body.get("include_subfolders", True),
                    sort=body.get("sort", "name_asc"),
                    limit=body.get("limit", 200),
                    offset=body.get("offset", 0),
                )
                return self._json(payload)
            except (ValueError, FileNotFoundError) as exc:
                return self._json({"ok": False, "error": str(exc)}, 409)
            except Exception as exc:
                return self._json({"ok": False, "error": str(exc)}, 500)


        if path == "/api/navigator-preview":
            try:
                length = int(self.headers.get("Content-Length", "0") or 0)
                raw = self.rfile.read(length) if length else b"{}"
                body = json.loads(raw.decode("utf-8"))
                return self._json(_navigator_document_preview(body.get("path", "")))
            except FileNotFoundError as exc:
                return self._json({"ok": False, "error": str(exc)}, 404)
            except ValueError as exc:
                return self._json({"ok": False, "error": str(exc)}, 400)
            except Exception as exc:
                return self._json({"ok": False, "error": str(exc)}, 500)


        if path == "/api/search-filename":
            try:
                length = int(self.headers.get("Content-Length", "0") or 0)
                raw = self.rfile.read(length) if length else b"{}"
                body = json.loads(raw.decode("utf-8"))
                query = str(body.get("query", "") or "").strip()
                limit = int(body.get("limit", 50) or 50)
                category = str(body.get("category", "") or "").strip() or None
                folder = str(body.get("folder", "") or "").strip() or None
                results = _search_filename_rows(query, limit, category, folder)
                return self._json({
                    "ok": True,
                    "query": query,
                    "results": results,
                    "category": category,
                    "folder": folder,
                })
            except Exception as exc:
                return self._json({"ok": False, "error": str(exc)}, 500)


        if path == "/api/open-file":
            try:
                length = int(
                    self.headers.get(
                        "Content-Length",
                        "0"
                    ) or 0
                )

                raw = (
                    self.rfile.read(length)
                    if length
                    else b"{}"
                )

                body = json.loads(
                    raw.decode("utf-8")
                )

                file_path = Path(
                    str(
                        body.get(
                            "path",
                            ""
                        ) or ""
                    )
                ).expanduser().resolve()

                if (
                    not file_path.exists()
                    or not file_path.is_file()
                ):
                    return self._json(
                        {
                            "ok": False,
                            "error":
                            "Archivo no encontrado",
                        },
                        404,
                    )

                if os.name == "nt":

                    os.startfile(
                        str(file_path)
                    )

                elif sys.platform == "darwin":

                    subprocess.Popen(
                        [
                            "open",
                            str(file_path),
                        ]
                    )

                else:

                    subprocess.Popen(
                        [
                            "xdg-open",
                            str(file_path),
                        ]
                    )

                return self._json(
                    {
                        "ok": True,
                        "path": str(file_path),
                    }
                )

            except Exception as exc:

                return self._json(
                    {
                        "ok": False,
                        "error": str(exc),
                    },
                    500,
                )


        if path != "/api/search":
            return self._json(
                {
                    "ok": False,
                    "error":
                    "Ruta no encontrada",
                },
                404,
            )

        try:
            length = int(self.headers.get("Content-Length", "0") or 0)
            raw = self.rfile.read(length) if length else b"{}"
            body = json.loads(raw.decode("utf-8"))
            query = str(body.get("query", "") or "").strip()
            category = str(body.get("category", "") or "").strip() or None
            folder = str(body.get("folder", "") or "").strip() or None
            limit = int(body.get("limit", 20) or 20)

            result = _content_search_v2(
                query=query,
                limit=limit,
                category=category,
                folder=folder,
                semantic_fallback=bool(body.get("semantic_fallback", False)),
            )
            return self._json(result)
        except Exception as exc:
            return self._json(
                {"ok": False, "error": str(exc), "service": "LexIA Professional Search"},
                500,
            )

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/maintenance":
            try:
                return self._json(_maintenance_snapshot())
            except _DeleteBridgeError as exc:
                return self._json({"ok": False, "error": str(exc)}, exc.status)
            except Exception as exc:
                return self._json({"ok": False, "error": str(exc)}, 500)
        if path in {"/api/research-status", "/api/research-result", "/api/study-status", "/api/study-result", "/api/research-candidates-status", "/api/research-candidates-result", "/api/research-package-status", "/api/research-package-result", "/api/navigator-operation-status"}:
            try:
                payload = {
                    "/api/research-status": _core_research_status,
                    "/api/research-result": _core_research_result,
                    "/api/study-status": _core_study_status,
                    "/api/study-result": _core_study_result,
                    "/api/research-candidates-status": _core_research_candidates_status,
                    "/api/research-candidates-result": _core_research_candidates_result,
                    "/api/research-package-status": _core_research_package_status,
                    "/api/research-package-result": _core_research_package_result,
                    "/api/navigator-operation-status": _core_navigator_operation_status,
                }[path]()
                return self._json(payload)
            except _DeleteBridgeError as exc:
                return self._json({"ok": False, "error": str(exc)}, exc.status)

        if path == "/api/navigator-children":
            try:
                params = parse_qs(urlparse(self.path).query)
                category = str((params.get("category") or [""])[0] or "").strip()
                parent = str((params.get("parent") or [""])[0] or "").strip()
                if not category:
                    return self._json(_navigator_root_nodes())
                return self._json({
                    "ok": True,
                    "category": category,
                    "parent": parent,
                    "nodes": _navigator_child_nodes(category, parent),
                })
            except ValueError as exc:
                return self._json({"ok": False, "error": str(exc)}, 409)
            except Exception as exc:
                return self._json({"ok": False, "error": str(exc)}, 500)

        if path == "/api/filter-options":
            try:
                params = parse_qs(urlparse(self.path).query)
                category = str((params.get("category") or [""])[0] or "").strip()
                parent = str((params.get("parent") or [""])[0] or "").strip()
                return self._json(_catalog_filter_options(category, parent))
            except ValueError as exc:
                return self._json({"ok": False, "error": str(exc)}, 409)
            except Exception as exc:
                return self._json({"ok": False, "error": str(exc)}, 500)

        if path == "/api/delete-file-status":
            try:
                payload = _core_document_delete_state()
                return self._json(payload)
            except _DeleteBridgeError as exc:
                return self._json({"ok": False, "error": str(exc)}, exc.status)
            except Exception as exc:
                return self._json({"ok": False, "error": str(exc)}, 500)

        if path == "/api/catalog-text-preview":
            try:
                query = parse_qs(urlparse(self.path).query)
                requested = str((query.get("path") or [""])[0] or "").strip()
                if not requested:
                    return self._json({"ok": False, "error": "Falta path"}, 400)

                project_root = Path(__file__).resolve().parents[2]
                db = project_root / "runtime" / "lexia_catalog.sqlite3"
                file_path = Path(requested).expanduser().resolve()

                con = sqlite3.connect(str(db))
                con.row_factory = sqlite3.Row
                try:
                    row = con.execute(
                        "SELECT text_content,name FROM documents "
                        "WHERE path=? AND COALESCE(is_deleted,0)=0 LIMIT 1",
                        (str(file_path),),
                    ).fetchone()
                finally:
                    con.close()

                if row is None:
                    return self._json(
                        {"ok": False, "error": "Documento no encontrado en el catálogo"},
                        404,
                    )

                text = str(row["text_content"] or "").strip()
                if not text:
                    return self._json(
                        {"ok": False, "error": "LexIA no tiene texto extraído para este documento"},
                        422,
                    )

                return self._json({
                    "ok": True,
                    "name": str(row["name"] or file_path.name),
                    "path": str(file_path),
                    "text": text[:600000],
                })
            except Exception as exc:
                return self._json({"ok": False, "error": str(exc)}, 500)


        if path == "/api/search-history":
            try:
                params = parse_qs(urlparse(self.path).query)
                mode = str((params.get("mode") or [""])[0] or "").strip().lower()
                return self._json({"ok": True, "mode": mode, "items": _search_history_items(mode, 10)})
            except Exception as exc:
                return self._json({"ok": False, "error": str(exc)}, 500)


        if path == "/api/office-preview-page":
            try:
                query = parse_qs(urlparse(self.path).query)
                requested = str((query.get("path") or [""])[0] or "").strip()
                snippet = str((query.get("snippet") or [""])[0] or "")
                fallback = str((query.get("fallback") or [""])[0] or "").strip()

                if not requested:
                    return self._json({"ok": False, "error": "Falta path"}, 400)

                pdf_path = _office_preview_pdf(requested)
                actual_page = _best_office_preview_page(
                    pdf_path,
                    snippet,
                    fallback_page=fallback,
                )

                return self._json({
                    "ok": True,
                    "page": int(actual_page or 1),
                    "fallback_page": int(fallback) if fallback.isdigit() else None,
                })
            except FileNotFoundError as exc:
                return self._json({"ok": False, "error": str(exc)}, 503)
            except (ValueError, PermissionError) as exc:
                return self._json({"ok": False, "error": str(exc)}, 400)
            except Exception as exc:
                return self._json({"ok": False, "error": str(exc)}, 500)


        if path == "/api/office-preview-pdf":
            try:
                query = parse_qs(urlparse(self.path).query)
                requested = str((query.get("path") or [""])[0] or "").strip()
                if not requested:
                    return self._json({"ok": False, "error": "Falta path"}, 400)

                pdf_path = _office_preview_pdf(requested)
                data = pdf_path.read_bytes()

                self.send_response(200)
                self.send_header("Content-Type", "application/pdf")
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Content-Disposition", 'inline; filename="lexia-office-preview.pdf"')
                self.send_header("Cache-Control", "private, max-age=3600")
                self.end_headers()
                self.wfile.write(data)
                return
            except FileNotFoundError as exc:
                return self._json({"ok": False, "error": str(exc)}, 503)
            except (ValueError, PermissionError) as exc:
                return self._json({"ok": False, "error": str(exc)}, 400)
            except Exception as exc:
                return self._json({"ok": False, "error": str(exc)}, 500)


        if path == "/api/file-preview":
            try:
                query = parse_qs(urlparse(self.path).query)
                requested = str((query.get("path") or [""])[0] or "").strip()
                if not requested:
                    return self._json({"ok": False, "error": "Falta path"}, 400)

                file_path = Path(requested).expanduser().resolve()
                if not file_path.exists() or not file_path.is_file():
                    return self._json({"ok": False, "error": "Archivo no encontrado"}, 404)

                project_root = Path(__file__).resolve().parents[2]
                catalog_path = project_root / "runtime" / "lexia_catalog.sqlite3"
                allowed = False

                if catalog_path.exists():
                    con = sqlite3.connect(str(catalog_path))
                    try:
                        resolved = str(file_path)
                        original = requested
                        try:
                            row = con.execute(
                                "SELECT 1 FROM documents WHERE path IN (?, ?) AND COALESCE(is_deleted, 0)=0 LIMIT 1",
                                (resolved, original),
                            ).fetchone()
                        except sqlite3.OperationalError:
                            row = con.execute(
                                "SELECT 1 FROM documents WHERE path IN (?, ?) LIMIT 1",
                                (resolved, original),
                            ).fetchone()
                        allowed = row is not None
                    finally:
                        con.close()

                if not allowed:
                    return self._json({"ok": False, "error": "Archivo fuera del catalogo LexIA"}, 403)

                suffix = file_path.suffix.lower()
                safe_text = {".txt",".log",".csv",".json",".xml",".md",".py",".js",".css",".html",".htm"}
                safe_image = {".png",".jpg",".jpeg",".gif",".webp",".bmp",".svg"}

                if suffix == ".pdf":
                    content_type = "application/pdf"
                elif suffix in safe_image:
                    content_type = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
                elif suffix in safe_text:
                    content_type = "text/plain; charset=utf-8"
                else:
                    return self._json({"ok": False, "error": "Formato sin vista previa integrada"}, 415)

                data = file_path.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Content-Disposition", f'inline; filename="{file_path.name}"')
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(data)
                return
            except Exception as exc:
                return self._json({"ok": False, "error": str(exc)}, 500)

        if path == "/api/live":
            try:
                return self._json(LIVE.snapshot())
            except Exception as exc:
                return self._json({"ok": False, "read_only": True, "error": str(exc)}, 500)
        if path == "/api/health":
            return self._json({
                "ok": True,
                "mode": "live-guarded",
                "service": "LexIA UI2",
                "delete_service": "classic-process-bridge",
                "secondary_autosync": False,
            })
        return super().do_GET()

    def end_headers(self):
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        super().end_headers()

if __name__ == "__main__":
    host = "127.0.0.1"
    port = int(os.environ.get("LEXIA_UI2_PORT", "8512"))
    print(f"LexIA UI2 3.3.0i: http://{host}:{port}")
    print("Eliminar usa el servicio vivo de la interfaz clásica. Sin AutoSync secundario.")
    print("Filtros dinámicos: categorías y carpetas reales del catálogo.")
    print("Navegador: vista previa por hover, menú flotante y prioridad al listado.")
    ThreadingHTTPServer((host, port), Handler).serve_forever()
