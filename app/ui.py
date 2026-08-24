from config.settings import SETTINGS
import html
import json
import time
import uuid
from urllib.parse import urlencode
import os
import re
import tempfile
import threading
from datetime import time as clock_time
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components
import fitz

from services.application import LexIAApplication
from services.ui2_delete_bridge import start_ui2_delete_bridge
# >>> LEXIA HORA ARGENTINA UI 1.0
from services.timezone_service import format_argentina_datetime
# <<< LEXIA HORA ARGENTINA UI 1.0
from services.rejected_document_service import (
    RejectedDocumentService,
)


st.set_page_config(
    page_title="LexIA Context Builder",
    page_icon="⚖️",
    layout="wide",
)


@st.cache_resource(show_spinner=False)
def get_application() -> LexIAApplication:
    return LexIAApplication()


_LIBRARY_FOLDER_TREE_COMPONENT = components.declare_component(
    "lexia_library_folder_tree",
    path=str(
        Path(__file__).resolve().parent
        / "components"
        / "lexia_folder_tree"
    ),
)


def _library_folder_tree(
    nodes: list[dict],
    selected: list[str],
    *,
    key: str,
) -> list[str] | None:
    value = _LIBRARY_FOLDER_TREE_COMPONENT(
        nodes=nodes,
        selected=selected,
        height=380,
        storage_key="lexia-library-folder-tree-expanded",
        default=selected,
        key=key,
    )
    if value is None:
        return None
    return list(value)


app = get_application()
start_ui2_delete_bridge(app)


def _start_autosync_in_background(application: LexIAApplication) -> None:
    """No bloquea el primer render de Streamlit esperando Qdrant.

    Construir AutoSync crea el índice vectorial y puede esperar la conexión a
    Qdrant. Esa tarea es necesaria, pero no debe dejar la interfaz clásica en
    blanco antes de que el usuario pueda ver sus menús.
    """
    def runner() -> None:
        try:
            application.autosync.start()
        except Exception:
            # El error queda en la salida de Streamlit. La UI permanece
            # disponible para que el usuario pueda consultar Configuración.
            import logging
            logging.getLogger("lexia.startup").exception(
                "No se pudo iniciar AutoSync en segundo plano"
            )

    threading.Thread(
        target=runner,
        name="LexIA-AutoSync-Startup",
        daemon=True,
    ).start()


def _catalog_revision() -> tuple[tuple[str, int, int], ...]:
    database = Path(SETTINGS.catalog_path)
    if not database.is_absolute():
        database = (
            Path(__file__).resolve().parents[1] / database
        ).resolve()
    related = (
        database,
        Path(str(database) + "-wal"),
        Path(str(database) + "-shm"),
    )
    revision = []
    for path in related:
        try:
            stat = path.stat()
            revision.append(
                (path.name, int(stat.st_size), int(stat.st_mtime_ns))
            )
        except OSError:
            revision.append((path.name, 0, 0))
    return tuple(revision)


@st.cache_data(show_spinner=False, max_entries=8)
def _cached_catalog_stats(
    revision: tuple[tuple[str, int, int], ...],
) -> dict[str, int]:
    del revision
    return app.catalog.stats()


@st.cache_data(show_spinner=False, max_entries=8)
def _cached_category_counts(
    revision: tuple[tuple[str, int, int], ...],
) -> dict[str, int]:
    del revision
    return app.catalog.category_counts()


@st.cache_data(show_spinner=False, max_entries=4)
def _cached_folder_counts(
    revision: tuple[tuple[str, int, int], ...],
) -> dict[str, int]:
    del revision
    return app.catalog.folder_counts()

if "navigation_target" not in st.session_state:
    st.session_state.navigation_target = None

if "autosync_started" not in st.session_state:
    _start_autosync_in_background(app)
    st.session_state.autosync_started = True

if "document_inspection" not in st.session_state:
    st.session_state.document_inspection = None

if "context_package" not in st.session_state:
    st.session_state.context_package = None

if "last_saved_paths" not in st.session_state:
    st.session_state.last_saved_paths = None

if "context_query_value" not in st.session_state:
    st.session_state.context_query_value = ""

if "context_facts_value" not in st.session_state:
    st.session_state.context_facts_value = ""

if "context_objective_value" not in st.session_state:
    st.session_state.context_objective_value = "Investigación jurídica"

if "context_additional_value" not in st.session_state:
    st.session_state.context_additional_value = ""

if "context_max_sources_value" not in st.session_state:
    st.session_state.context_max_sources_value = 14


def clipboard_button(text: str) -> None:
    payload = json.dumps(text, ensure_ascii=False)

    components.html(
        f"""
        <button id="copy"
            style="
                padding:10px 16px;
                border:0;
                border-radius:7px;
                cursor:pointer;
                font-weight:600;
            ">
            Copiar mensaje para ChatGPT
        </button>
        <span id="state" style="margin-left:10px"></span>
        <script>
        const text = {payload};
        document.getElementById('copy').onclick = async () => {{
            try {{
                await navigator.clipboard.writeText(text);
                document.getElementById('state').innerText = 'Copiado';
            }} catch (error) {{
                document.getElementById('state').innerText =
                    'Utilizá el botón de descarga';
            }}
        }};
        </script>
        """,
        height=55,
    )



def _extract_first_page(page_label: str) -> int:
    match = re.search(r"(\d+)", str(page_label or ""))
    return int(match.group(1)) if match else 1


def _open_local_path(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"No existe el archivo: {path}")

    if os.name == "nt":
        os.startfile(str(path))
        return

    import subprocess
    import sys

    command = (
        ["open", str(path)]
        if sys.platform == "darwin"
        else ["xdg-open", str(path)]
    )
    subprocess.Popen(command)


def _configured_local_path(value) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = (Path(__file__).resolve().parents[1] / path)
    return path.resolve()


def _validate_openable_file(path_value) -> Path:
    candidate = _configured_local_path(path_value)
    allowed_roots = [
        _configured_local_path(SETTINGS.library_path),
        _configured_local_path(SETTINGS.rejected_documents_path),
        _configured_local_path(SETTINGS.exports_path),
        _configured_local_path(SETTINGS.runtime_path),
    ]

    allowed = False
    for root in allowed_roots:
        try:
            candidate.relative_to(root)
            allowed = True
            break
        except ValueError:
            continue

    if not allowed:
        raise PermissionError(
            "LexIA bloqueó la apertura de una ruta fuera de sus carpetas autorizadas."
        )
    if not candidate.exists() or not candidate.is_file():
        raise FileNotFoundError(f"No existe el archivo: {candidate}")
    return candidate


_file_link_counter = 0


def _render_file_link(
    path_value,
    label=None,
    caption=None,
    *,
    key_suffix=None,
) -> None:
    global _file_link_counter
    if not path_value:
        return
    path = Path(path_value)
    visible = str(label or path.name or path)
    key_seed = (
        f"{path}|{visible}|"
        f"{st.session_state.get('lexia_current_page', '')}"
    )
    if key_suffix is None:
        _file_link_counter += 1
        key_seed += f"|occurrence:{_file_link_counter}"
    else:
        key_seed += f"|context:{key_suffix}"
    key = "open_file_" + uuid.uuid5(
        uuid.NAMESPACE_URL,
        key_seed,
    ).hex
    if st.button(f"📄 {visible}", key=key, type="secondary"):
        try:
            _open_local_path(_validate_openable_file(path))
        except Exception as error:
            st.error(str(error))
    if caption:
        st.caption(str(caption))


def _render_document_inspection(inspection) -> None:
    """Muestra el diagnostico de un documento sin abandonar Biblioteca."""
    if inspection.overall_status == "Correcto":
        st.success(f"Estado general: {inspection.overall_status}")
    elif inspection.searchable:
        st.warning(f"Estado general: {inspection.overall_status}")
    else:
        st.error(f"Estado general: {inspection.overall_status}")

    col1, col2, col3 = st.columns(3)
    col1.metric("Texto", f"{inspection.text_chars:,} caracteres")
    col2.metric("Fragmentos", inspection.fragment_count)
    col3.metric(
        "Vectores",
        inspection.vector_count
        if inspection.vector_count >= 0
        else "No verificado",
    )

    for row in inspection.status_rows():
        icon = "✅" if row["correcto"] else "⚠️"
        st.markdown(
            f"{icon} **{row['componente']}** — {row['detalle']}"
        )

    with st.expander("Datos del documento"):
        _render_file_link(inspection.path, inspection.name)
        st.write(
            {
                "Nombre": inspection.name,
                "Ruta": inspection.path,
                "Categoría": inspection.category,
                "Extensión": inspection.extension,
                "Tamaño": inspection.size,
                "Páginas": inspection.total_pages,
                "Páginas OCR": inspection.ocr_pages,
                "Método de extracción": inspection.extraction_method,
                "Última actualización": format_argentina_datetime(inspection.updated_at),
                "Hash": inspection.content_hash,
                "Duplicado de": inspection.duplicate_of or None,
            }
        )

    if inspection.extraction_error:
        st.error("Error de extracción: " + inspection.extraction_error)

    if inspection.knowledge:
        st.markdown("### Conocimiento detectado")
        concepts = inspection.knowledge.get("concepts", [])
        citations = inspection.knowledge.get("citations", [])

        if concepts:
            st.write("**Conceptos:** " + ", ".join(concepts))

        if citations:
            with st.expander(f"Citas detectadas ({len(citations)})"):
                for citation in citations:
                    st.write(f"- {citation}")

        st.write(
            {
                "Tribunal": inspection.knowledge.get("court", ""),
                "Jurisdicción": inspection.knowledge.get(
                    "jurisdiction", ""
                ),
                "Fecha": inspection.knowledge.get("decision_date", ""),
                "Tipo": inspection.knowledge.get("document_type", ""),
                "Materia": inspection.knowledge.get("matter", ""),
            }
        )


def _render_document_delete_control(path_value, name_value) -> None:
    path_text = str(Path(path_value).resolve())
    name_text = str(name_value or Path(path_text).name)
    token = uuid.uuid5(uuid.NAMESPACE_URL, path_text).hex
    target = st.session_state.get("secure_delete_target")

    if st.button(
        "🗑️ Eliminar",
        key=f"secure_delete_open_{token}",
        help="Elimina el archivo, su texto, fragmentos, Knowledge, OCR y vectores.",
    ):
        st.session_state.secure_delete_target = {
            "path": path_text,
            "name": name_text,
        }
        st.rerun()

    target = st.session_state.get("secure_delete_target")
    if not target or target.get("path") != path_text:
        return

    with st.expander(f"Confirmar eliminacion de {name_text}", expanded=True):
        st.error(
            "La eliminacion es irreversible. Desapareceran el archivo, "
            "el texto, los fragmentos, Knowledge, OCR y todos sus vectores."
        )
        confirm_col, cancel_col = st.columns(2)
        if confirm_col.button(
            "Confirmar eliminacion",
            type="primary",
            key=f"secure_delete_confirm_{token}",
            use_container_width=True,
        ):
            try:
                if not app.secure_document_deletion.start_delete(path_text):
                    raise RuntimeError("Hay otro trabajo activo. Espera a que termine.")
                st.session_state.secure_delete_notice = (
                    "Eliminacion iniciada en segundo plano. Podes cambiar de menu."
                )
                st.session_state.secure_delete_target = None
                st.session_state.document_inspection = None
                st.session_state.inspector_matches = [
                    item for item in st.session_state.get("inspector_matches", [])
                    if item.get("path") != path_text
                ]
                st.session_state._inspector_folder_cache_token = None
                st.rerun()
            except Exception as error:
                st.error(str(error))

        if cancel_col.button(
            "Cancelar",
            key=f"secure_delete_cancel_{token}",
            use_container_width=True,
        ):
            st.session_state.secure_delete_target = None
            st.rerun()


def _render_file_table(items) -> None:
    page_size = 25
    pages = max(1, (len(items) + page_size - 1) // page_size)
    page = st.number_input("Página", 1, pages, 1, key="library_file_page")
    start = (int(page) - 1) * page_size
    for item in items[start:start + page_size]:
        path_text = str(Path(item["path"]).resolve())
        token = uuid.uuid5(uuid.NAMESPACE_URL, path_text).hex
        _render_file_link(
            item["path"], item["name"], item.get("category", "")
        )
        st.caption(item["path"])
        verify_col, delete_col = st.columns(2)
        verify_requested = verify_col.button(
            "🔎 Verificar documento",
            key=f"library_verify_document_{token}",
            use_container_width=True,
        )
        with delete_col:
            _render_document_delete_control(item["path"], item["name"])

        if verify_requested:
            try:
                with st.spinner("Verificando documento..."):
                    st.session_state.document_inspection = (
                        app.document_inspector.inspect(path_text)
                    )
                st.session_state.library_inspection_path = path_text
            except Exception as error:
                st.session_state.document_inspection = None
                st.session_state.library_inspection_path = None
                st.error(str(error))

        inspection = st.session_state.get("document_inspection")
        selected_inspection_path = st.session_state.get(
            "library_inspection_path"
        )
        if inspection and selected_inspection_path == path_text:
            st.divider()
            _render_document_inspection(inspection)
            if st.button(
                "Cerrar verificación",
                key=f"library_close_inspection_{token}",
                use_container_width=True,
            ):
                st.session_state.document_inspection = None
                st.session_state.library_inspection_path = None
                st.rerun()
            st.divider()


def _render_pdf_viewer(path: Path, page_number: int) -> None:
    if path.suffix.lower() != ".pdf":
        st.info(
            "El visor integrado está disponible únicamente para archivos PDF."
        )
        return

    if not path.exists():
        st.error(f"No se encontró el archivo: {path}")
        return

    try:
        document = fitz.open(path)

        try:
            total_pages = len(document)

            if total_pages == 0:
                st.warning("El PDF no contiene páginas visibles.")
                return

            safe_page = max(1, min(int(page_number or 1), total_pages))
            page = document[safe_page - 1]
            pixmap = page.get_pixmap(
                matrix=fitz.Matrix(1.7, 1.7),
                alpha=False,
            )

            st.image(
                pixmap.tobytes("png"),
                caption=(
                    f"{path.name} — página {safe_page} de {total_pages}"
                ),
                use_container_width=True,
            )

            if safe_page != page_number:
                st.caption(
                    "La página solicitada estaba fuera del rango del PDF; "
                    f"se mostró la página {safe_page}."
                )

        finally:
            document.close()

    except Exception as error:
        st.error(
            "No fue posible renderizar esta página dentro de LexIA. "
            f"Detalle: {error}"
        )


def build_chatgpt_message(package) -> str:
    objective = str(
        getattr(package, "objective", "Investigación jurídica")
        or "Investigación jurídica"
    ).strip().lower()

    if "redacción" in objective or "redaccion" in objective:
        return (
            "Redactá directamente el escrito jurídico solicitado utilizando "
            "el archivo adjunto.\n\n"
            "El archivo ya contiene la consulta, los hechos, el objetivo, "
            "las instrucciones de trabajo y las fuentes seleccionadas por LexIA.\n\n"
            "No describas el archivo.\n"
            "No me preguntes qué quiero hacer con él.\n"
            "No resumas su contenido.\n\n"
            "Comenzá directamente con la redacción solicitada, respetando "
            "las instrucciones contenidas en el propio archivo."
        )

    if "abogado contrario" in objective:
        return (
            "Analizá el archivo adjunto y asumí la mejor posición jurídica "
            "posible de la contraparte.\n\n"
            "El archivo ya contiene la consulta, los hechos, el objetivo, "
            "las instrucciones de trabajo y las fuentes seleccionadas por LexIA.\n\n"
            "No describas el archivo.\n"
            "No me preguntes qué quiero hacer con él.\n"
            "No resumas su contenido.\n\n"
            "Comenzá directamente con el análisis adversarial solicitado."
        )

    if "jurisprudencia" in objective:
        return (
            "Analizá directamente la jurisprudencia contenida en el archivo adjunto.\n\n"
            "El archivo ya contiene el objetivo, las instrucciones de trabajo "
            "y las fuentes seleccionadas por LexIA.\n\n"
            "No describas el archivo.\n"
            "No me preguntes qué quiero hacer con él.\n"
            "No resumas el archivo como objeto.\n\n"
            "Comenzá directamente con el análisis jurídico solicitado."
        )

    return (
        "Respondé directamente la consulta jurídica contenida en el archivo adjunto.\n\n"
        "El archivo ya contiene:\n\n"
        "• la consulta;\n"
        "• los hechos;\n"
        "• el objetivo;\n"
        "• las instrucciones de trabajo;\n"
        "• las fuentes seleccionadas.\n\n"
        "No describas el archivo.\n"
        "No me preguntes qué quiero hacer con él.\n"
        "No resumas el contenido del archivo.\n\n"
        "Comenzá directamente con el informe jurídico solicitado, respetando "
        "las instrucciones contenidas en el propio archivo."
    )


def _context_source_widget_key(package, number: int, source) -> str:
    seed = (
        f"{package.created_at}|{number}|{source.document_path}|"
        f"{getattr(source, 'fragment_index', number)}"
    )
    return "context_source_include_" + uuid.uuid5(
        uuid.NAMESPACE_URL,
        seed,
    ).hex


def _render_context_source_curator(package):
    if not package.sources:
        return package

    st.markdown("### Revisar fuentes antes de enviar a ChatGPT")
    st.caption(
        "Todas están incluidas inicialmente. Desmarcá las que no tengan "
        "relación con la consulta; el Contexto.txt se reconstruye sin "
        "repetir la búsqueda ni recalcular embeddings."
    )

    widget_keys = [
        _context_source_widget_key(package, number, source)
        for number, source in enumerate(package.sources, start=1)
    ]

    def _set_all_context_sources(value: bool) -> None:
        for widget_key in widget_keys:
            st.session_state[widget_key] = value

    select_col, discard_col = st.columns(2)
    select_col.button(
        "Incluir todas",
        use_container_width=True,
        key=f"context_sources_all_{package.created_at}",
        on_click=_set_all_context_sources,
        args=(True,),
    )
    discard_col.button(
        "Descartar todas",
        use_container_width=True,
        key=f"context_sources_none_{package.created_at}",
        on_click=_set_all_context_sources,
        args=(False,),
    )

    selected_indices: list[int] = []
    selected_number = 0

    for original_index, source in enumerate(package.sources):
        proposal_number = original_index + 1
        include_source = st.checkbox(
            (
                f"Incluir propuesta {proposal_number}: "
                f"{source.document_name} — {source.page_label}"
            ),
            value=True,
            key=widget_keys[original_index],
        )
        if include_source:
            selected_number += 1
            selected_indices.append(original_index)
            status_label = f"se enviará como [FUENTE {selected_number}]"
        else:
            status_label = "descartada"

        with st.expander(
            f"Propuesta {proposal_number} · {status_label} · "
            f"{source.document_name}"
        ):
            source_path = Path(source.document_path)
            page_number = _extract_first_page(source.page_label)
            metadata = getattr(source, "metadata", {}) or {}
            summary = (
                metadata.get("summary")
                or metadata.get("abstract")
                or source.text
            )

            st.markdown(f"**Categoría:** {source.category}")
            st.markdown(f"**Ubicación:** {source.page_label}")
            st.markdown("**Documento:**")
            _render_file_link(
                source_path,
                source.document_name,
                key_suffix=f"context_source_{package.created_at}_{proposal_number}",
            )
            st.markdown("**Resumen o extracto recuperado:**")
            st.write(summary)

            action1, action2, action3 = st.columns(3)
            if action1.button(
                "📄 Abrir documento",
                key=f"open_doc_{package.created_at}_{proposal_number}",
                use_container_width=True,
            ):
                try:
                    _open_local_path(source_path)
                except Exception as error:
                    st.error(str(error))

            if action2.button(
                "📂 Abrir carpeta",
                key=f"open_folder_{package.created_at}_{proposal_number}",
                use_container_width=True,
            ):
                try:
                    _open_local_path(source_path.parent)
                except Exception as error:
                    st.error(str(error))

            viewer_key = (
                f"viewer_{package.created_at}_{proposal_number}"
            )
            if action3.button(
                "👁 Ver página",
                key=f"show_pdf_{package.created_at}_{proposal_number}",
                use_container_width=True,
            ):
                st.session_state[viewer_key] = not st.session_state.get(
                    viewer_key,
                    False,
                )

            st.code(str(source_path), language=None)
            if st.session_state.get(viewer_key, False):
                st.markdown(
                    f"#### Vista del documento — página {page_number}"
                )
                _render_pdf_viewer(source_path, page_number)

    if not selected_indices:
        st.error(
            "Seleccioná al menos una fuente. Mientras todas estén "
            "descartadas, LexIA no permite descargar el contexto."
        )
        return None

    curated_package = app.context_builder.curate_package(
        package,
        selected_indices,
    )
    st.info(
        f"Fuentes incluidas: {curated_package.selected_count} de "
        f"{len(package.sources)}. Las referencias fueron renumeradas."
    )
    return curated_package


def show_package(package) -> None:
    package = _render_context_source_curator(package)
    if package is None:
        return

    curation_signature = uuid.uuid5(
        uuid.NAMESPACE_URL,
        "|".join(
            f"{source.document_path}:"
            f"{getattr(source, 'fragment_index', index)}"
            for index, source in enumerate(package.sources)
        ),
    ).hex

    st.success(
        f"Investigación preparada: "
        f"{package.selected_count} fuentes seleccionadas · "
        f"{package.character_count:,} caracteres"
    )

    message = build_chatgpt_message(package)

    # El botón principal copia únicamente la instrucción corta.
    # El contexto largo se descarga y se adjunta por separado.
    clipboard_button(message)

    col1, col2, col3 = st.columns(3)
    col1.download_button(
        "Descargar Contexto.txt",
        data=package.content.encode("utf-8"),
        file_name="Contexto.txt",
        mime="text/plain",
        use_container_width=True,
    )
    col2.download_button(
        "Descargar Mensaje_ChatGPT.txt",
        data=message.encode("utf-8"),
        file_name="Mensaje_ChatGPT.txt",
        mime="text/plain",
        use_container_width=True,
    )
    col3.link_button(
        "Abrir ChatGPT",
        "https://chatgpt.com/",
        use_container_width=True,
    )

    st.info(
        "1. Revisá y marcá las fuentes. "
        "2. Descargá Contexto.txt. "
        "3. Abrí ChatGPT y adjuntá Contexto.txt. "
        "4. Copiá y pegá el mensaje corto. "
        "5. Enviá el mensaje y el archivo juntos."
    )

    with st.expander(
        "Ver mensaje corto para ChatGPT",
        expanded=False,
    ):
        st.text_area(
            "Mensaje",
            value=message,
            height=230,
            key=f"chatgpt_message_{package.created_at}",
        )

    with st.expander(
        "Ver y editar el expediente",
        expanded=False,
    ):
        st.text_area(
            "Contenido",
            value=package.content,
            height=700,
            key=f"context_{package.created_at}_{curation_signature}",
        )


with st.sidebar:
    st.title("LexIA")

    return_page = st.session_state.pop(
        "_return_page_after_open",
        None,
    )
    if return_page:
        if return_page == "Centro de actividad":
            return_page = "Actividad"
        st.session_state["main_navigation"] = return_page

    if st.session_state.get("main_navigation") == "Centro de actividad":
        st.session_state["main_navigation"] = "Actividad"

    page = st.radio(
        "Navegación",
        [
            "Inicio",
            "Preparar documento",
            "Biblioteca",
            "Casos",
            "Actividad",
            "OCR pendientes",
            "Configuración",
            "Acerca de LexIA",
        ],
        label_visibility="collapsed",
        key="main_navigation",
    )
    st.session_state.lexia_current_page = page

    if st.session_state.navigation_target:
        page = st.session_state.navigation_target
        st.session_state.navigation_target = None

    # LexIA Final UX 3.3: la barra lateral sólo navega. Los contadores y la
    # barra de progreso viven en Inicio, Biblioteca y Actividad.
    # Esto elimina consultas SQLite y reruns globales al cambiar de menú.
    # Compatibilidad histórica: sidebar_busy, sidebar_fragment,
    # key_suffix="sidebar_sync_current" y key_suffix="sidebar_ocr_current".


if page == "Inicio":
    st.title("LexIA Context Builder")
    st.subheader(
        "Tu biblioteca local prepara el expediente; "
        "ChatGPT realiza el análisis."
    )

    home_stats = _cached_catalog_stats(_catalog_revision())
    home_documents, home_fragments = st.columns(2)
    home_documents.metric(
        "Documentos disponibles",
        f"{home_stats['documents']:,}",
    )
    home_fragments.metric(
        "Fragmentos disponibles",
        f"{home_stats['fragments']:,}",
    )

    st.markdown(
        """
### Flujo

1. Escribí la consulta y los hechos.
2. Elegí el objetivo.
3. LexIA busca y selecciona las fuentes.
4. Genera un mensaje listo para ChatGPT.
5. Copialo, abrí ChatGPT y pegalo.

No requiere API ni LM Studio.
"""
    )


elif page == "Preparar documento":
    # lexia_unified_workspaces_1_7: contexto + documentos
    st.title("Preparar documento")
    st.caption(
        "Investigá en la biblioteca o prepará documentos propios para ChatGPT."
    )
    prepare_mode = st.radio(
        "Modo de preparación",
        ["Investigar en la biblioteca", "Analizar documentos"],
        horizontal=True,
        key="unified_prepare_mode",
        label_visibility="collapsed",
    )

    if prepare_mode == "Investigar en la biblioteca":

        with st.expander("Historial de consultas", expanded=False):
            history_search = st.text_input(
                "Buscar en el historial",
                key="context_history_search",
                placeholder="Buscar por consulta, hechos o indicación adicional",
            )

            history_rows = app.context_query_history.list_recent(
                limit=100,
                search=history_search,
            )

            if not history_rows:
                st.info("Todavía no hay consultas guardadas.")
            else:
                for item in history_rows:
                    title = str(item["query"]).strip()
                    if len(title) > 110:
                        title = title[:107] + "..."

                    with st.expander(
                        f"{item['created_at']} — {title}",
                        expanded=False,
                    ):
                        st.markdown(f"**Objetivo:** {item['objective']}")

                        if item["facts"]:
                            st.markdown("**Hechos:**")
                            st.write(item["facts"])

                        if item["additional_instruction"]:
                            st.markdown("**Información adicional:**")
                            st.write(item["additional_instruction"])

                        actions = st.columns(2)

                        if actions[0].button(
                            "Cargar",
                            key=f"load_context_history_{item['id']}",
                            use_container_width=True,
                        ):
                            st.session_state.context_query_value = item["query"]
                            st.session_state.context_facts_value = item["facts"]
                            st.session_state.context_objective_value = item["objective"]
                            st.session_state.context_additional_value = (
                                item["additional_instruction"]
                            )
                            st.session_state.context_max_sources_value = int(
                                item["max_sources"]
                            )
                            st.session_state.context_package = None
                            st.rerun()

                        if actions[1].button(
                            "Eliminar",
                            key=f"delete_context_history_{item['id']}",
                            use_container_width=True,
                        ):
                            app.context_query_history.delete(item["id"])
                            st.rerun()

        query = st.text_area(
            "Consulta jurídica",
            height=150,
            value=st.session_state.context_query_value,
            key="context_query_input",
            placeholder=(
                "Ej.: ¿La demora municipal en resolver una habilitación "
                "configura responsabilidad estatal por actividad ilegítima?"
            ),
        )

        facts = st.text_area(
            "Hechos del caso",
            height=220,
            value=st.session_state.context_facts_value,
            key="context_facts_input",
        )

        objective_options = [
            "Investigación jurídica",
            "Construcción de argumentos",
            "Abogado contrario",
            "Redacción de escrito",
            "Análisis de jurisprudencia",
            "Comparación de criterios",
            "Estrategia procesal",
        ]

        selected_objective = (
            st.session_state.context_objective_value
            if st.session_state.context_objective_value in objective_options
            else objective_options[0]
        )

        objective = st.selectbox(
            "Objetivo",
            objective_options,
            index=objective_options.index(selected_objective),
            key="context_objective_input",
        )

        additional = st.text_area(
            "Indicación adicional",
            height=110,
            value=st.session_state.context_additional_value,
            key="context_additional_input",
            placeholder=(
                "Ej.: priorizá jurisprudencia de la CSJN y distinguí "
                "actividad legítima e ilegítima."
            ),
        )

        max_sources = st.slider(
            "Máximo de fuentes",
            min_value=6,
            max_value=20,
            value=max(
                6,
                min(20, int(st.session_state.context_max_sources_value)),
            ),
            key="context_max_sources_input",
        )

        context_job_state = app.context_build_jobs.state()
        context_job_running = (
            context_job_state.get("phase")
            in app.context_build_jobs.RUNNING_PHASES
        )

        if st.button(
            "Generar mensaje para ChatGPT",
            type="primary",
            disabled=context_job_running,
        ):
            if not query.strip():
                st.warning("Ingresá una consulta.")
            else:
                st.session_state.context_query_value = query
                st.session_state.context_facts_value = facts
                st.session_state.context_objective_value = objective
                st.session_state.context_additional_value = additional
                st.session_state.context_max_sources_value = max_sources

                try:
                    app.context_build_jobs.start_job(
                        query=query,
                        facts=facts,
                        objective=objective,
                        additional_instruction=additional,
                        max_sources=max_sources,
                    )
                    st.success(
                        "Investigación iniciada en segundo plano. "
                        "Podés seguir usando otras secciones de LexIA."
                    )
                    st.rerun()
                except Exception as error:
                    st.error(str(error))

        def _render_context_job_status():
            job_state = app.context_build_jobs.state()
            phase = job_state.get("phase", "idle")

            if phase in app.context_build_jobs.RUNNING_PHASES:
                st.info(
                    "La investigación continúa en segundo plano. "
                    "Podés navegar por LexIA sin interrumpirla."
                )
                st.progress(
                    int(job_state.get("percentage", 0) or 0),
                    text=str(job_state.get("status", "")),
                )
                if job_state.get("started_at"):
                    st.caption(
                        "Iniciada: " + str(job_state["started_at"])
                    )

            elif phase == "completed":
                result = app.context_build_jobs.result()
                if result is not None:
                    st.success(
                        "Investigación terminada en "
                        f"{result.elapsed_seconds:.2f} s."
                    )

                    refresh_key = (
                        "context_completed_refresh_"
                        + result.job_id
                    )
                    if not st.session_state.get(refresh_key, False):
                        st.session_state[refresh_key] = True
                        st.rerun()

            elif phase == "error":
                st.error(
                    str(
                        job_state.get("error")
                        or "La investigación produjo un error."
                    )
                )

        context_fragment = getattr(
            st,
            "fragment",
            getattr(st, "experimental_fragment", None),
        )

        if context_fragment is not None and context_job_running:
            _live_context_job = context_fragment(
                run_every="1s"
            )(_render_context_job_status)
            _live_context_job()
        else:
            _render_context_job_status()
            if context_job_running:
                st.caption(
                    "El trabajo continúa en segundo plano. "
                    "Volvé a esta pantalla para consultar su estado."
                )


        report = app.performance_profiler.last_report_dict()

        if report:
            with st.expander(
                "Informe de rendimiento",
                expanded=True,
            ):
                total = float(
                    report.get(
                        "total_seconds",
                        0,
                    )
                )
                metrics = report.get(
                    "metrics",
                    {},
                )
                stages = report.get(
                    "stages",
                    [],
                )

                col1, col2, col3, col4 = st.columns(4)
                col1.metric(
                    "Tiempo total",
                    f"{total:.2f} s",
                )
                col2.metric(
                    "Consultas ejecutadas",
                    metrics.get(
                        "search_query_count",
                        0,
                    ),
                )
                col3.metric(
                    "Candidatos",
                    metrics.get(
                        "candidates_recovered",
                        0,
                    ),
                )
                col4.metric(
                    "Memoria pico",
                    (
                        f"{float(report.get('peak_memory_mb', 0)):.1f} MB"
                    ),
                )

                duplicate_seconds = float(
                    metrics.get(
                        "possible_duplicate_work_seconds",
                        0,
                    )
                )
                duplicate_percent = float(
                    metrics.get(
                        "possible_duplicate_work_percent",
                        0,
                    )
                )

                if duplicate_seconds > 0:
                    st.warning(
                        "Segunda pasada del Context Builder: "
                        f"{duplicate_seconds:.2f} s "
                        f"({duplicate_percent:.1f}% del total)."
                    )

                st.markdown("#### Etapas")

                for stage in stages:
                    seconds = float(
                        stage.get(
                            "seconds",
                            0,
                        )
                    )
                    percentage = (
                        seconds / total * 100
                        if total > 0
                        else 0
                    )
                    st.markdown(
                        f"**{stage.get('name', '')}** — "
                        f"{seconds:.3f} s "
                        f"({percentage:.1f}%)"
                    )

                report_path = (
                    SETTINGS.runtime_path
                    / "performance_reports"
                    / (
                        report["report_id"]
                        + ".json"
                    )
                )

                if report_path.exists():
                    st.download_button(
                        "Descargar informe JSON",
                        data=report_path.read_bytes(),
                        file_name=report_path.name,
                        mime="application/json",
                    )

        completed_context_job = app.context_build_jobs.result()

        if completed_context_job is not None:
            show_package(completed_context_job.package)




    else:
        st.caption(
            "Subí un PDF, DOC, DOCX o TXT. LexIA extrae el texto y genera "
            "un Contexto.txt para adjuntar en ChatGPT junto con un mensaje corto."
        )

        uploaded_files = st.file_uploader(
            "Documentos",
            type=["pdf", "doc", "docx", "txt"],
            accept_multiple_files=True,
            key="prepare_document_upload",
        )

        if uploaded_files:
            st.caption(
                f"{len(uploaded_files)} documento(s) seleccionado(s). "
                "Se generará un único Contexto.txt."
            )

        if st.button(
            "📂 Abrir carpeta de documentos",
            key="open_lexia_documents_folder",
            use_container_width=True,
        ):
            try:
                _open_local_path(SETTINGS.library_path)
            except Exception as error:
                st.error(str(error))

        document_type = st.selectbox(
            "Tipo de documento",
            [
                "Detección automática",
                "Fallo judicial",
                "Demanda",
                "Contestación de demanda",
                "Recurso",
                "Dictamen",
                "Contrato",
                "Informe o pericia",
                "Otro documento jurídico",
            ],
            key="prepare_document_type",
        )

        document_objective = st.selectbox(
            "Objetivo",
            [
                "Análisis de jurisprudencia",
                "Investigación jurídica",
                "Construcción de argumentos",
                "Abogado contrario",
                "Redacción de escrito",
                "Comparación de criterios",
                "Estrategia procesal",
            ],
            key="prepare_document_objective",
        )

        document_instruction = st.text_area(
            "Indicación adicional",
            value=(
                "Resumí y explicá el documento. Identificá sus fundamentos, "
                "fortalezas, debilidades, citas relevantes y utilidad práctica."
            ),
            height=140,
            key="prepare_document_instruction",
        )

        if st.button(
            "Preparar para ChatGPT",
            type="primary",
            disabled=not uploaded_files,
            key="prepare_document_button",
        ):
            temp_documents = []
            temp_paths = []

            progress = st.progress(
                10,
                text="Preparando los documentos...",
            )

            try:
                for uploaded in uploaded_files:
                    suffix = Path(uploaded.name).suffix

                    with tempfile.NamedTemporaryFile(
                        delete=False,
                        suffix=suffix,
                    ) as temp_file:
                        temp_file.write(
                            uploaded.getbuffer()
                        )
                        temp_path = Path(temp_file.name)

                    temp_paths.append(temp_path)
                    temp_documents.append(
                        (temp_path, uploaded.name)
                    )

                progress.progress(
                    45,
                    text="Extrayendo el contenido de los documentos...",
                )

                package = (
                    app.context_builder
                    .build_documents_package(
                        documents=temp_documents,
                        objective=document_objective,
                        instruction=document_instruction,
                        document_type=document_type,
                    )
                )

                package.title = (
                    "Analisis_"
                    + str(len(uploaded_files))
                    + "_documentos"
                )

                progress.progress(
                    80,
                    text="Construyendo el Contexto.txt...",
                )

                paths = app.context_builder.save(package)

                st.session_state.context_package = package
                st.session_state.last_saved_paths = paths

                progress.progress(
                    100,
                    text=(
                        f"{len(uploaded_files)} documentos "
                        "preparados para ChatGPT."
                    ),
                )

            except Exception as error:
                progress.empty()
                st.error(str(error))

            finally:
                for temp_path in temp_paths:
                    temp_path.unlink(missing_ok=True)

        if st.session_state.context_package:
            show_package(st.session_state.context_package)


elif page == "Casos":
    st.title("Casos")

    cases = app.cases.list_cases()

    with st.expander("Crear caso"):
        name = st.text_input("Nombre del caso")
        description = st.text_area("Descripción")

        if (
            st.button("Crear caso")
            and name.strip()
        ):
            app.cases.create_case(
                name,
                description,
            )
            st.rerun()

    if not cases:
        st.info("Todavía no hay casos.")
    else:
        options = {
            f"{case['name']} — #{case['id']}": case
            for case in cases
        }

        label = st.selectbox(
            "Caso",
            list(options),
        )
        case = options[label]

        notes = st.text_area(
            "Notas",
            value=case["notes"],
            height=350,
        )

        if st.button("Guardar notas"):
            app.cases.update_notes(
                case["id"],
                notes,
            )
            st.success("Notas guardadas.")

        outputs = app.cases.list_outputs(
            case["id"]
        )

        if outputs:
            st.markdown("### Resultados guardados")
            for output in outputs:
                with st.expander(
                    f"{output['title']} — "
                    f"{output['created_at']}"
                ):
                    st.markdown(output["content"])

elif page == "Actividad":
    def _render_activity_center_live():
        st.title("Actividad")
        st.caption(
            "Estado actual de la biblioteca, la indexación y la cola OCR."
        )
        if st.button(
            "Actualizar estado",
            key="activity_center_manual_refresh",
        ):
            st.rerun()

        snapshot = app.activity_center.snapshot(
            recent_limit=20,
            error_limit=20,
        )
        sync_config = app.autosync.configuration()
        st.caption(
            "Modo de sincronización: "
            + str(sync_config.get("mode", "automatic"))
            + (
                " · Hora: " + str(sync_config.get("schedule_time", "03:00"))
                if sync_config.get("mode") == "scheduled"
                else ""
            )
        )

        context_service = getattr(app, "_context_build_jobs", None)
        context_state = (
            context_service.state()
            if context_service is not None
            else {"phase": "idle"}
        )
        context_running_phases = (
            context_service.RUNNING_PHASES
            if context_service is not None
            else set()
        )
        sync_stage_labels = {
            "waiting": ("⏳", "Preparando actualización"),
            "scanning": ("🔍", "Analizando y preparando documentos"),
            "indexing": ("⚙️", "Indexando vectores"),
            "knowledge": ("🧠", "Actualizando Knowledge"),
        }

        if snapshot.sync_phase in sync_stage_labels:
            stage_icon, stage_label = sync_stage_labels[snapshot.sync_phase]
            st.markdown(f"### {stage_icon} {stage_label}")
            sync_total = max(0, snapshot.sync_total)
            sync_processed = max(0, snapshot.sync_processed)
            sync_current = snapshot.sync_current_file
            if sync_total > 0:
                sync_position = min(
                    sync_total,
                    sync_processed
                    + (
                        1
                        if sync_current and sync_processed < sync_total
                        else 0
                    ),
                )
                sync_remaining = max(0, sync_total - sync_position)
                st.progress(
                    int(sync_position / sync_total * 100),
                    text=f"Documento {sync_position}/{sync_total}",
                )
                st.caption(
                    f"Faltan {sync_remaining} documento(s) en esta etapa."
                )
            else:
                st.progress(
                    max(0, min(100, snapshot.sync_percentage)),
                    text=snapshot.sync_status,
                )
        elif snapshot.ocr_running:
            st.markdown("### 🟡 OCR en ejecución")
            ocr_total = max(1, snapshot.ocr_total)
            ocr_processed = max(0, snapshot.ocr_processed)
            ocr_position = min(
                ocr_total,
                ocr_processed
                + (
                    1
                    if snapshot.ocr_current_file
                    and ocr_processed < ocr_total
                    else 0
                ),
            )
            st.progress(
                int(ocr_position / ocr_total * 100),
                text=f"Documento OCR {ocr_position}/{ocr_total}",
            )
            st.caption(
                f"Faltan {max(0, ocr_total - ocr_position)} "
                "documento(s) OCR."
            )
        elif context_state.get("phase") in context_running_phases:
            st.markdown("### 🔎 Construyendo contexto")
            st.progress(
                int(context_state.get("percentage", 0) or 0),
                text=str(context_state.get("status", "")),
            )
        elif snapshot.sync_phase == "error" or snapshot.ocr_errors:
            st.error("La actividad requiere atención.")
        else:
            st.success("Biblioteca al día. No hay tareas en ejecución.")

        st.markdown("### Actualización manual")
        st.caption(
            "Usá esta opción si agregaste, moviste o eliminaste documentos "
            "mientras LexIA estaba cerrada."
        )

        busy_sync = snapshot.ocr_running or snapshot.sync_phase in {
            "waiting", "scanning", "indexing", "knowledge",
        }
        analyze_col, apply_col = st.columns(2)
        if analyze_col.button(
            "Analizar cambios",
            use_container_width=True,
            disabled=busy_sync,
        ):
            st.session_state.reconciliation_preview = (
                app.autosync.preview_reconciliation()
            )
            st.rerun()

        preview = st.session_state.get("reconciliation_preview")
        preview_total_work = (
            int(preview.get("total_work", 0) or 0)
            if preview
            else 0
        )
        if apply_col.button(
            "Actualizar biblioteca",
            type="primary",
            use_container_width=True,
            disabled=(
                busy_sync
                or not preview
                or preview_total_work <= 0
            ),
        ):
            result = app.autosync.sync_now()
            st.session_state.reconciliation_preview = None
            st.success(result["status"])
            st.rerun()

        if preview:
            pending_vectors = int(
                preview.get("pending_vectors", 0) or 0
            )
            pending_relocations = int(
                preview.get("pending_vector_relocations", 0) or 0
            )
            st.info(
                f"Nuevos: {len(preview['new'])} · "
                f"Modificados: {len(preview['modified'])} · "
                f"Eliminados: {len(preview['deleted'])} · "
                f"Vectores pendientes: {pending_vectors} · "
                f"Relocalizaciones pendientes: {pending_relocations}"
            )
            if preview_total_work <= 0:
                st.success(
                    "No hay cambios físicos ni tareas internas pendientes."
                )
            else:
                if (
                    int(preview.get("total_changes", 0) or 0) == 0
                    and (pending_vectors or pending_relocations)
                ):
                    st.warning(
                        "No hay cambios de archivos, pero LexIA tiene trabajo "
                        "vectorial pendiente. Actualizar biblioteca completará "
                        "esas tareas."
                    )
                with st.expander("Ver cambios detectados"):
                    for label, key in (
                        ("Nuevos", "new"),
                        ("Modificados", "modified"),
                        ("Eliminados", "deleted"),
                    ):
                        st.markdown(f"**{label}**")
                        for changed_path in preview[key][:100]:
                            st.code(changed_path, language=None)

        if snapshot.sync_phase == "indexing" and st.button(
            "Detener indexacion",
            use_container_width=True,
        ):
            app.autosync.request_stop_indexing()
            st.warning("La indexacion se detendra al finalizar el lote actual.")

        st.divider()

        col1, col2, col3 = st.columns(3)

        col1.metric(
            "Documentos",
            snapshot.documents_total,
        )
        col2.metric(
            "OCR pendientes",
            snapshot.ocr_pending,
        )
        col3.metric(
            "Estado",
            snapshot.sync_phase or "idle",
        )

        if snapshot.sync_current_file:
            st.info("Archivo actual")
            _render_file_link(
                snapshot.sync_current_file,
                Path(snapshot.sync_current_file).name,
                key_suffix="activity_sync_current",
            )

        recent_tab, errors_tab = st.tabs(
            [
                "Documentos recientes",
                "Errores y pendientes",
            ]
        )

        with recent_tab:
            if not snapshot.recent_documents:
                st.info(
                    "Todavía no hay actividad documental reciente."
                )
            else:
                for item_index, item in enumerate(snapshot.recent_documents):
                    status = item.get(
                        "category",
                        "Sin clasificar",
                    )
                    method = item.get(
                        "extraction_method",
                        "",
                    )
                    pages = item.get("total_pages")
                    detail = status

                    if method:
                        detail += f" · {method}"

                    if pages:
                        detail += f" · {pages} páginas"

                    _render_file_link(
                        item["path"],
                        item["name"],
                        caption=detail,
                        key_suffix=f"activity_recent_{item_index}",
                    )
                    st.code(item["path"], language=None)
                    st.caption(
                        "Actualizado: "
                        + format_argentina_datetime(
                            item.get("updated_at", "")
                        )
                    )
                    st.divider()

        with errors_tab:
            if not snapshot.recent_errors:
                st.success(
                    "No hay errores registrados."
                )
            else:
                for item_index, item in enumerate(snapshot.recent_errors):
                    st.error(
                        f"{item.get('name', 'Documento')}: "
                        f"{item.get('error', 'Error')}"
                    )
                    if item.get("path"):
                        _render_file_link(
                            item["path"],
                            item.get("name", "Documento"),
                            caption=item.get("source", ""),
                            key_suffix=f"activity_error_{item_index}",
                        )



    _activity_fragment = getattr(
        st,
        "fragment",
        getattr(st, "experimental_fragment", None),
    )

    activity_sync_state = app.autosync.state()
    activity_ocr_state = app.ocr_queue.state()
    activity_context_service = getattr(app, "_context_build_jobs", None)
    activity_context_state = (
        activity_context_service.state()
        if activity_context_service is not None
        else {"phase": "idle"}
    )
    activity_busy = (
        activity_sync_state.get("phase")
        in {"waiting", "scanning", "indexing", "knowledge"}
        or bool(activity_ocr_state.get("running"))
        or (
            activity_context_service is not None
            and activity_context_state.get("phase")
            in activity_context_service.RUNNING_PHASES
        )
    )

    if _activity_fragment is not None and activity_busy:
        _live_activity_center = _activity_fragment(
            run_every="2s"
        )(_render_activity_center_live)
        _live_activity_center()
    else:
        _render_activity_center_live()
    if _activity_fragment is None and activity_busy:
        st.caption(
            "El refresco automático de Actividad "
            "requiere una versión reciente de Streamlit."
        )

elif page == "Biblioteca":
    # lexia_unified_workspaces_1_7: biblioteca + inspector
    st.title("Biblioteca")
    deletion_notice = st.session_state.pop("secure_delete_notice", None)
    if deletion_notice:
        st.success(deletion_notice)
    deletion_state = app.secure_document_deletion.state()
    deletion_finished_at = float(
        deletion_state.get("finished_at", 0) or 0
    )
    deletion_state_is_recent = (
        deletion_finished_at > 0
        and 0 <= time.time() - deletion_finished_at <= 30
    )
    if deletion_state.get("status") == "running":
        st.info(
            f"Eliminando {deletion_state.get('name', 'documento')}: "
            f"{deletion_state.get('stage', '')}"
        )
    elif (
        deletion_state.get("status") == "completed"
        and deletion_state_is_recent
    ):
        result = deletion_state.get("result", {})
        st.success(
            f"{result.get('name', 'Documento')} eliminado: "
            f"{result.get('fragments_deleted', 0)} fragmentos y "
            f"{result.get('vectors_deleted', 0)} vectores retirados."
        )
    elif (
        deletion_state.get("status") in {"error", "interrupted"}
        and deletion_state_is_recent
    ):
        st.error(deletion_state.get("error", "La eliminacion no se completo."))
    # Biblioteca unificada 2.5: Documentos es la unica vista visible.
    # La verificacion se abre bajo demanda dentro de cada resultado.
    # Compatibilidad con la prueba historica 1.7: "Inspeccionar documento"
    # ahora esta integrado en Documentos y ya no es una vista seleccionable.
    library_mode = "Documentos"

    if library_mode == "Documentos":
        st.caption(
            "LexIA incorpora automáticamente los documentos nuevos "
            "que copies dentro de la carpeta data."
        )

        library_catalog_revision = _catalog_revision()
        library_stats = _cached_catalog_stats(library_catalog_revision)
        library_documents_metric, library_fragments_metric = st.columns(2)
        library_documents_metric.metric(
            "Documentos",
            f"{library_stats['documents']:,}",
        )
        library_fragments_metric.metric(
            "Fragmentos",
            f"{library_stats['fragments']:,}",
        )



        with st.expander("➕ Importar documentos", expanded=False):
            # >>> LEXIA FASE D IMPORTER CURRENT UI 1.1
            from services.library_tree_manager import LibraryTreeManager

            st.caption(
                "Seleccioná uno o varios documentos y su ubicación en el árbol. "
                "La carpeta física determina su clasificación."
            )

            library_root = _configured_local_path(SETTINGS.library_path)
            tree_manager = LibraryTreeManager(library_root)

            import_category = st.selectbox(
                "Categoría",
                tree_manager.categories(),
                key="library_tree_import_category",
            )

            selected_levels = []
            create_mode = False

            for level_index in range(4):
                label = f"Subcategoría {level_index + 1}"

                if create_mode:
                    new_name = st.text_input(
                        label + " (nueva)",
                        key=f"library_tree_import_new_{level_index}",
                        placeholder="Dejar vacío para terminar aquí",
                    ).strip()
                    if not new_name:
                        break
                    selected_levels.append(new_name)
                    continue

                children = tree_manager.children(import_category, selected_levels)
                options = ["— Terminar aquí —"] + children + ["➕ Crear nueva…"]

                selected = st.selectbox(
                    label,
                    options,
                    key=f"library_tree_import_level_{level_index}",
                )

                if selected == "— Terminar aquí —":
                    break

                if selected == "➕ Crear nueva…":
                    new_name = st.text_input(
                        label + " (nombre nuevo)",
                        key=f"library_tree_import_new_{level_index}",
                    ).strip()
                    if not new_name:
                        break
                    selected_levels.append(new_name)
                    create_mode = True
                else:
                    selected_levels.append(selected)

            destination = tree_manager.folder(import_category, selected_levels)
            relative_destination = destination.relative_to(library_root).as_posix()
            st.info("Destino: " + relative_destination)

            import_files = st.file_uploader(
                "Documentos a importar",
                type=["pdf", "doc", "docx", "odt", "txt"],
                accept_multiple_files=True,
                key="library_tree_import_files",
            )

            if st.button(
                "Importar a esta ubicación",
                type="primary",
                use_container_width=True,
                disabled=not import_files,
                key="library_tree_import_button",
            ):
                try:
                    destination = tree_manager.ensure_path(import_category, selected_levels)
                except Exception as error:
                    st.error(f"No se pudo crear la carpeta de destino: {error}")
                    destination = None

                if destination is not None:
                    staging = SETTINGS.runtime_path / "import_staging"
                    staging.mkdir(parents=True, exist_ok=True)

                    imported = []
                    skipped = []
                    errors = []
                    allowed_extensions = {".pdf", ".doc", ".docx", ".odt", ".txt"}

                    for uploaded in import_files:
                        clean_name = Path(uploaded.name).name
                        extension = Path(clean_name).suffix.lower()

                        if (
                            not clean_name
                            or clean_name != uploaded.name
                            or extension not in allowed_extensions
                        ):
                            errors.append(
                                f"Nombre o extensión no admitidos: {uploaded.name}"
                            )
                            continue

                        target = (destination / clean_name).resolve()
                        try:
                            target.relative_to(destination)
                        except ValueError:
                            errors.append(f"Ruta no admitida: {uploaded.name}")
                            continue

                        if target.exists():
                            skipped.append(str(target))
                            continue

                        temporary = staging / (
                            f"{uuid.uuid4().hex}_{clean_name}.lexia-importing"
                        )

                        try:
                            temporary.write_bytes(uploaded.getbuffer())
                            os.replace(temporary, target)
                            imported.append(str(target))
                        except Exception as error:
                            temporary.unlink(missing_ok=True)
                            errors.append(f"{clean_name}: {error}")

                    st.session_state.library_import_result = {
                        "imported": imported,
                        "skipped": skipped,
                        "errors": errors,
                        "category": import_category,
                        "destination": relative_destination,
                    }

                    if imported:
                        app.autosync.reconcile_paths(imported)

            import_result = st.session_state.get("library_import_result")
            if import_result:
                imported = import_result.get("imported", [])
                skipped = import_result.get("skipped", [])
                errors = import_result.get("errors", [])

                if imported:
                    st.success(
                        f"{len(imported)} documento(s) importado(s) en "
                        f"{import_result.get('destination', '')}. "
                        "AutoSync los incorporará automáticamente."
                    )
                    for imported_path in imported:
                        _render_file_link(imported_path, Path(imported_path).name)

                if skipped:
                    st.warning(
                        f"{len(skipped)} archivo(s) omitido(s) porque ya existían."
                    )
                    for skipped_path in skipped:
                        st.caption(skipped_path)

                for error in errors:
                    st.error(error)
            # <<< LEXIA FASE D IMPORTER CURRENT UI 1.1

        allowed_library_categories = [
            "Escritos", "Doctrina", "Jurisprudencia", "Legislacion",
        ]
        category_counts = _cached_category_counts(
            library_catalog_revision
        )
        library_folder_counts = _cached_folder_counts(
            library_catalog_revision
        )
        # Conserva el contrato histórico 2.8 para las pruebas y para cualquier
        # extensión que aún consulte estas claves. La fuente real sigue siendo
        # el nuevo caché vinculado a la revisión de SQLite.
        library_folder_cache_version = "2.8"
        if (
            st.session_state.get("_library_folder_cache_version")
            != library_folder_cache_version
            or not st.session_state.get("_library_folder_counts_cache")
            or st.session_state.get("_library_folder_cache_token")
            != library_catalog_revision
        ):
            st.session_state._library_folder_counts_cache = (
                library_folder_counts
            )
            st.session_state._library_folder_cache_token = (
                library_catalog_revision
            )
            st.session_state._library_folder_cache_version = (
                library_folder_cache_version
            )
        library_folder_paths = sorted(
            library_folder_counts, key=lambda value: str(value).lower()
        )
        library_root = _configured_local_path(SETTINGS.library_path)
        library_relative_folders: list[tuple[str, Path]] = []
        for folder_path in library_folder_paths:
            folder = Path(folder_path).resolve()
            try:
                relative = folder.relative_to(library_root)
            except ValueError:
                # No se exponen rutas externas a la biblioteca configurada.
                continue
            library_relative_folders.append((folder_path, relative))

        library_relative_by_path = dict(library_relative_folders)
        library_visible_folders = [
            path for path, relative in library_relative_folders
            if relative.parts and relative.parts[0] in allowed_library_categories
        ]
        library_path_by_parts = {
            library_relative_by_path[path].parts: path
            for path in library_visible_folders
        }
        library_children_by_parent: dict[str | None, list[str]] = {}
        for folder_path in library_visible_folders:
            relative = library_relative_by_path[folder_path]
            parent_path = (
                library_path_by_parts.get(relative.parts[:-1])
                if len(relative.parts) > 1
                else None
            )
            library_children_by_parent.setdefault(parent_path, []).append(
                folder_path
            )

        category_order = {
            name: index
            for index, name in enumerate(allowed_library_categories)
        }

        def _library_folder_sort_key(folder_path: str) -> tuple:
            relative = library_relative_by_path[folder_path]
            top_name = relative.parts[0] if relative.parts else ""
            return (
                category_order.get(top_name, len(category_order)),
                tuple(part.casefold() for part in relative.parts),
            )

        def _build_library_folder_nodes(
            parent_path: str | None = None,
        ) -> list[dict]:
            nodes: list[dict] = []
            for folder_path in sorted(
                library_children_by_parent.get(parent_path, []),
                key=_library_folder_sort_key,
            ):
                relative = library_relative_by_path[folder_path]
                nodes.append(
                    {
                        "id": folder_path,
                        "path": folder_path,
                        "label": relative.name,
                        "count": int(
                            library_folder_counts.get(folder_path, 0) or 0
                        ),
                        "children": _build_library_folder_nodes(folder_path),
                    }
                )
            return nodes

        library_folder_tree_nodes = _build_library_folder_nodes()
        # Compatibilidad con la prueba histórica 2.2: library_top_names era
        # la lista superior del árbol anterior; ahora esa información está
        # contenida en library_folder_tree_nodes.
        # Compatibilidad 2.7: library_folder_labels fue reemplazado por los
        # nodos jerárquicos del componente liviano.

        def _clear_library_filters() -> None:
            st.session_state.library_folder_tree_selection = []
            # Compatibilidad con el selector plano anterior:
            st.session_state.library_folder_multiselect = []
            st.session_state.library_document_query = ""
            st.session_state.library_category_filter = "Todas las categorías"
            st.session_state.library_filtered_documents = None

        with st.form("library_documents_filter_form"):
            st.markdown("#### Buscar documentos")
            search_col, category_col = st.columns([2, 1])
            library_query = search_col.text_input(
                "Nombre del archivo",
                placeholder="Ej.: Alberdi.pdf",
                key="library_document_query",
            )
            selected_category_label = category_col.selectbox(
                "Categoría",
                ["Todas las categorías"] + allowed_library_categories,
                key="library_category_filter",
            )

            st.markdown("#### Carpetas")
            if not library_visible_folders:
                st.caption("No se encontraron carpetas documentales.")
                selected_library_folders: list[str] = []
            else:
                stored_tree_selection = st.session_state.get(
                    "library_folder_tree_selection"
                ) or []
                if not isinstance(
                    stored_tree_selection,
                    (list, tuple, set),
                ):
                    stored_tree_selection = []
                current_tree_selection = [
                    path
                    for path in stored_tree_selection
                    if path in library_visible_folders
                ]
                component_tree_selection = _library_folder_tree(
                    library_folder_tree_nodes,
                    current_tree_selection,
                    key="library_folder_tree_component",
                )
                selected_library_folders = (
                    current_tree_selection
                    if component_tree_selection is None
                    else component_tree_selection
                )
                st.session_state.library_folder_tree_selection = list(
                    selected_library_folders
                )
                # Compatibilidad con la prueba histórica 2.9:
                # key="library_folder_tree_selection" era también el estado
                # interno del componente y podía transformarse en None.

            include_library_subfolders = st.checkbox(
                "Incluir subcarpetas", value=True,
                key="library_include_subfolders",
            )
            filter_col, clear_col = st.columns(2)
            apply_library_filters = filter_col.form_submit_button(
                "Aplicar filtros", type="primary", use_container_width=True
            )
            clear_col.form_submit_button(
                "Limpiar filtros", use_container_width=True,
                on_click=_clear_library_filters,
            )

        selected_categories = (
            allowed_library_categories
            if selected_category_label == "Todas las categorías"
            else [selected_category_label]
        )
        if (
            st.session_state.get("_library_results_catalog_revision")
            != library_catalog_revision
        ):
            st.session_state.library_filtered_documents = None
            st.session_state._library_results_catalog_revision = (
                library_catalog_revision
            )
        if apply_library_filters:
            st.session_state.library_filtered_documents = (
                app.catalog.browse_documents_multi(
                    query=library_query,
                    folders=selected_library_folders,
                    include_subfolders=include_library_subfolders,
                    limit=2000,
                    categories=selected_categories,
                )
            )

        category_documents = st.session_state.get("library_filtered_documents")
        if category_documents is None:
            category_documents = app.catalog.recent_documents(
                limit=200,
                categories=selected_categories,
            )
            st.markdown("### Últimos documentos incorporados o actualizados")
        selected_category_total = sum(
            int(category_counts.get(category, 0) or 0)
            for category in selected_categories
        )
        st.caption(
            f"Documentos encontrados: {len(category_documents):,} · "
            f"Total en categorías documentales: {selected_category_total:,}"
        )
        if category_documents:
            _render_file_table(category_documents)
            if len(category_documents) == 2000:
                st.caption("Se muestran los primeros 2.000 resultados. Refina el filtro.")
        else:
            st.info("No hay documentos que coincidan con los filtros.")

        st.caption(
            "El progreso de indexación, OCR y otras tareas se muestra "
            "únicamente en Actividad."
        )
        # Compatibilidad histórica: library_live_busy y
        # key_suffix="library_sync_current" ya no ejecutan refrescos aquí.




    else:
        st.caption(
            "Verifica catálogo, texto, fragmentos, vectores, "
            "Knowledge Engine y disponibilidad para el Context Builder."
        )

        sync_token = app.autosync.state().get("last_sync")
        if st.session_state.get("_inspector_folder_cache_token") != sync_token:
            st.session_state._inspector_folder_counts_cache = app.catalog.folder_counts()
            st.session_state._inspector_folder_cache_token = sync_token
        folder_counts = st.session_state.get("_inspector_folder_counts_cache", {})
        folder_paths = sorted(folder_counts, key=lambda value: str(value).lower())
        common_root = None
        if folder_paths:
            try:
                common_root = Path(os.path.commonpath(folder_paths))
            except (ValueError, OSError):
                common_root = None

        relative_folders: list[tuple[str, Path]] = []
        for folder_path in folder_paths:
            path = Path(folder_path)
            if common_root is not None:
                try:
                    relative = path.relative_to(common_root)
                except ValueError:
                    relative = path
            else:
                relative = path
            relative_folders.append((folder_path, relative))

        if "inspector_matches" not in st.session_state:
            st.session_state.inspector_matches = []

        inspector_relative_by_path = dict(relative_folders)
        inspector_folder_labels = {
            path: " › ".join(inspector_relative_by_path[path].parts)
            + f" ({folder_counts[path]:,})"
            for path in folder_paths
        }

        def _set_inspector_folder_selection(selected: bool) -> None:
            st.session_state.inspector_folder_multiselect = (
                list(folder_paths) if selected else []
            )
            if not selected:
                st.session_state.inspector_matches = []

        with st.form("inspector_filters_form"):
            st.markdown("#### Carpetas")
            # Compatibilidad de prueba historica; el arbol ahora se representa
            # en un unico multiselect jerarquico y no con cientos de widgets:
            # with st.expander(f"📁 {top_name} ({top_total:,})")
            # selected_folders: list[str] = []
            # inspector_folder_multi_
            selected_folders = st.multiselect(
                "Seleccionar una o varias carpetas",
                options=folder_paths,
                format_func=lambda path: inspector_folder_labels[path],
                key="inspector_folder_multiselect",
                placeholder="Jurisprudencia › Tribunal › Año...",
            )

            include_subfolders = st.checkbox(
                "Incluir subcarpetas", value=True,
                key="inspector_include_subfolders",
            )
            term = st.text_input(
                "Nombre del archivo",
                placeholder="Ej.: Alberdi.pdf",
                key="inspector_search_term",
            )
            col1, col2, col3 = st.columns(3)
            col1.form_submit_button(
                "Seleccionar todas",
                use_container_width=True,
                on_click=_set_inspector_folder_selection,
                args=(True,),
                # inspector_select_all_folders
            )
            col2.form_submit_button(
                "Limpiar selección",
                use_container_width=True,
                on_click=_set_inspector_folder_selection,
                args=(False,),
            )
            apply_filters = col3.form_submit_button(
                "Aplicar filtros", type="primary", use_container_width=True
            )
        if apply_filters:
            st.session_state.inspector_matches = app.catalog.browse_documents_multi(
                query=term, folders=selected_folders,
                include_subfolders=include_subfolders, limit=None,
            ) if term.strip() or selected_folders else []

        matches = st.session_state.inspector_matches
        if apply_filters and not matches:
            st.warning("No se encontraron documentos con esos filtros.")

        if matches:
            st.caption(f"Documentos encontrados: {len(matches):,}")
            options = {
                f"{item['name']} — {item['category']} — {item['path']}": item['path']
                for item in matches
            }
            selected_label = st.selectbox(
                "Documento encontrado", list(options), key="inspector_selected_document"
            )
            selected_document_path = options[selected_label]
            _render_file_link(
                selected_document_path,
                Path(selected_document_path).name,
            )
            _render_document_delete_control(
                selected_document_path,
                Path(selected_document_path).name,
            )
            if st.button("Verificar documento", type="primary"):
                try:
                    st.session_state.document_inspection = app.document_inspector.inspect(
                        options[selected_label]
                    )
                except Exception as error:
                    st.error(str(error))

        inspection = st.session_state.get(
            "document_inspection"
        )

        if inspection:
            if inspection.overall_status == "Correcto":
                st.success(
                    f"Estado general: {inspection.overall_status}"
                )
            elif inspection.searchable:
                st.warning(
                    f"Estado general: {inspection.overall_status}"
                )
            else:
                st.error(
                    f"Estado general: {inspection.overall_status}"
                )

            col1, col2, col3 = st.columns(3)
            col1.metric(
                "Texto",
                f"{inspection.text_chars:,} caracteres",
            )
            col2.metric(
                "Fragmentos",
                inspection.fragment_count,
            )
            col3.metric(
                "Vectores",
                (
                    inspection.vector_count
                    if inspection.vector_count >= 0
                    else "No verificado"
                ),
            )

            for row in inspection.status_rows():
                icon = "✅" if row["correcto"] else "⚠️"
                st.markdown(
                    f"{icon} **{row['componente']}** — "
                    f"{row['detalle']}"
                )

            with st.expander("Datos del documento"):
                _render_file_link(
                    inspection.path,
                    inspection.name,
                )
                st.write(
                    {
                        "Nombre": inspection.name,
                        "Ruta": inspection.path,
                        "Categoría": inspection.category,
                        "Extensión": inspection.extension,
                        "Tamaño": inspection.size,
                        "Páginas": inspection.total_pages,
                        "Páginas OCR": inspection.ocr_pages,
                        "Método de extracción": (
                            inspection.extraction_method
                        ),
                        "Última actualización": (
                            format_argentina_datetime(
                                inspection.updated_at
                            )
                        ),
                        "Hash": inspection.content_hash,
                        "Duplicado de": (
                            inspection.duplicate_of or None
                        ),
                    }
                )

            if inspection.extraction_error:
                st.error(
                    "Error de extracción: "
                    + inspection.extraction_error
                )

            if inspection.knowledge:
                st.markdown("### Conocimiento detectado")

                concepts = inspection.knowledge.get(
                    "concepts",
                    [],
                )
                citations = inspection.knowledge.get(
                    "citations",
                    [],
                )

                if concepts:
                    st.write(
                        "**Conceptos:** "
                        + ", ".join(concepts)
                    )

                if citations:
                    with st.expander(
                        f"Citas detectadas ({len(citations)})"
                    ):
                        for citation in citations:
                            st.write(f"- {citation}")

                st.write(
                    {
                        "Tribunal": inspection.knowledge.get(
                            "court", ""
                        ),
                        "Jurisdicción": inspection.knowledge.get(
                            "jurisdiction", ""
                        ),
                        "Fecha": inspection.knowledge.get(
                            "decision_date", ""
                        ),
                        "Tipo": inspection.knowledge.get(
                            "document_type", ""
                        ),
                        "Materia": inspection.knowledge.get(
                            "matter", ""
                        ),
                    }
                )

elif page == "Acerca de LexIA":
    st.title("Acerca de LexIA")
    st.caption(
        "Identificación y autodiagnóstico de la plataforma instalada."
    )

    info = app.platform_info.status()

    st.subheader(info["product"])
    st.code(
        f"Versión: {info['version']}\n"
        f"Build: {info['build']}\n"
        f"Canal: {info['channel']}",
        language=None,
    )

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### Componentes")
        for name, component in info["components"].items():
            icon = "✅" if component["available"] else "❌"
            version = component.get("version", "")
            suffix = f" — {version}" if version else ""
            st.markdown(
                f"{icon} **{name}**{suffix}"
            )

    with col2:
        st.markdown("#### Configuración activa")
        st.markdown(
            f"- Inicio: **{info['settings']['startup_mode']}**"
        )
        st.markdown(
            f"- Consultas máximas: "
            f"**{info['settings']['max_queries']}**"
        )
        st.markdown(
            f"- Fuentes máximas operativas: "
            f"**{info['settings']['max_sources']}**"
        )
        st.markdown(
            f"- Qdrant: **{info['settings']['qdrant_mode']}**"
        )

    if info["healthy"]:
        st.success(
            "Los componentes esenciales de Platform 2.1 "
            "están disponibles."
        )
    else:
        st.error(
            "Faltan componentes esenciales. Ejecutá "
            "platform_self_check.py desde PowerShell."
        )

    if st.button(
        "Actualizar diagnóstico",
        use_container_width=True,
    ):
        st.rerun()

elif page == "OCR pendientes":
    st.title("OCR pendientes")
    st.caption(
        "Los PDF escaneados quedan pendientes y no bloquean "
        "la indexación de los demás documentos."
    )

    def _render_live_ocr_queue():
        queue_state = app.ocr_queue.state()
        queue_stats = app.ocr_queue.stats()

        col1, col2, col3 = st.columns(3)
        col1.metric(
            "Pendientes",
            queue_stats["pending"],
        )
        col2.metric(
            "Procesando",
            queue_stats["processing"],
        )
        col3.metric(
            "Con error",
            queue_stats["error"],
        )

        if queue_state.get("error"):
            if str(queue_state["error"]).startswith("OCR completado"):
                st.warning(queue_state["error"])
            else:
                st.error(queue_state["error"])

        if queue_state["running"]:
            total = max(
                1,
                int(queue_state["total"]),
            )
            done = int(
                queue_state["processed"]
            )
            stage_label = (
                "OCR" if queue_state.get("stage") == "ocr" else "Indexando"
            )
            st.progress(
                min(
                    100,
                    int(done / total * 100),
                ),
                text=(
                    f"{stage_label} {done} de {total} — "
                    f"{queue_state['current_file']}"
                ),
            )
            _render_file_link(
                queue_state["current_file"],
                Path(queue_state["current_file"]).name,
                key_suffix="ocr_current_file",
            )
            st.info(
                "Podés seguir usando otras secciones de LexIA "
                "mientras el OCR continúa."
            )
            st.code(queue_state["current_file"], language=None)
            if st.button(
                "Detener OCR",
                use_container_width=True,
                disabled=bool(queue_state.get("stopping")),
                key="ocr_stop_running",
            ):
                app.ocr_queue.request_stop()
                st.warning(
                    "El OCR se detendra al finalizar la pagina actual."
                )

        rows = app.ocr_queue.list_pending()

        if not rows:
            st.success(
                "No hay documentos pendientes de OCR."
            )
            return

        controls = st.columns(3)

        if controls[0].button(
            "Seleccionar todos",
            use_container_width=True,
            key="ocr_select_all",
        ):
            app.ocr_queue.select_all(True)
            st.rerun()

        if controls[1].button(
            "Deseleccionar todos",
            use_container_width=True,
            key="ocr_deselect_all",
        ):
            app.ocr_queue.select_all(False)
            st.rerun()

        if controls[2].button(
            "Iniciar OCR seleccionado",
            type="primary",
            use_container_width=True,
            disabled=(queue_state["running"] or queue_stats["processing"] > 0),
            key="ocr_start_selected",
        ):
            if app.ocr_queue.start_selected():
                st.success(
                    "OCR iniciado en segundo plano."
                )
                st.rerun()
            else:
                st.warning(
                    "Seleccioná al menos un documento."
                )

        st.markdown("### Documentos")

        for item_index, item in enumerate(rows):
            selected = st.checkbox(
                (
                    f"{item['document_name']} — "
                    f"{item['total_pages'] or '?'} páginas"
                ),
                value=bool(item["selected"]),
                key=f"ocr_{item['document_path']}",
            )

            if selected != bool(item["selected"]):
                app.ocr_queue.set_selected(
                    item["document_path"],
                    selected,
                )

            _render_file_link(
                item["document_path"],
                item["document_name"],
                key_suffix=f"ocr_pending_{item_index}",
            )
            st.code(item["document_path"], language=None)

            if item["status"] == "processing":
                st.caption(
                    f"Procesando página "
                    f"{item['progress_page']} de "
                    f"{item['total_pages'] or '?'}"
                )
            elif item["status"] == "error":
                st.error(
                    f"{item['document_name']}: "
                    f"{item['error']}"
                )

    ocr_fragment = getattr(
        st,
        "fragment",
        getattr(
            st,
            "experimental_fragment",
            None,
        ),
    )

    ocr_live_state = app.ocr_queue.state()
    if ocr_fragment is not None and ocr_live_state.get("running"):
        live_ocr_queue = ocr_fragment(
            run_every="2s"
        )(_render_live_ocr_queue)
        live_ocr_queue()
    else:
        _render_live_ocr_queue()
        st.caption(
            "Actualizá Streamlit para disponer de "
            "refresco automático de la cola OCR."
        )


elif page == "Configuración":
    st.title("Configuración")

    st.subheader("Modo de sincronización")
    sync_config = app.autosync.configuration()
    mode_labels = {
        "Manual": "manual",
        "Automático": "automatic",
        "Programado": "scheduled",
    }
    current_label = next(
        label for label, value in mode_labels.items()
        if value == sync_config.get("mode", "automatic")
    )
    selected_mode_label = st.radio(
        "Modo de sincronización",
        list(mode_labels),
        index=list(mode_labels).index(current_label),
        key="reconciliation_sync_mode",
    )
    schedule_text = str(sync_config.get("schedule_time", "03:00"))
    hour, minute = [int(value) for value in schedule_text.split(":")]
    selected_schedule = st.time_input(
        "Hora de reconciliación",
        value=clock_time(hour=hour, minute=minute),
        disabled=mode_labels[selected_mode_label] != "scheduled",
        key="reconciliation_schedule_time",
    )
    if st.button("Guardar modo de sincronización", type="primary"):
        app.autosync.set_configuration(
            mode_labels[selected_mode_label],
            selected_schedule.strftime("%H:%M"),
        )
        st.success("Configuración de sincronización guardada.")
        st.rerun()

    st.caption(
        "Manual: sólo actualiza al pulsar el botón. Automático: vigila la "
        "biblioteca. Programado: reconcilia una vez por día."
    )
    st.divider()

    st.success(
        "Modo Context Builder activo. "
        "No requiere API ni LM Studio."
    )

    st.write(
        "Los mensajes se guardan en "
        "`exports/context_packages`."
    )

    st.write(
        "La copia `.txt` es un respaldo. "
        "Para usar ChatGPT, copiá el mensaje y pegalo en el chat."
    )

    if st.button("Crear copia de seguridad"):
        st.success(
            f"Copia creada: {app.backups.create()}"
        )

    if st.button("Diagnóstico"):
        st.json(app.health.run())

    st.divider()
    st.subheader("Documentos rechazados")
    rejected_service = RejectedDocumentService()

    st.caption(
        "Esta carpeta está fuera de la biblioteca y sólo "
        "se revisa cuando pulsás el botón siguiente."
    )

    if st.button(
        "Analizar documentos rechazados",
        use_container_width=True,
    ):
        rejected_stats = rejected_service.stats()
        st.metric("Total rechazados", rejected_stats["total"])
        st.code(rejected_stats["root_path"], language=None)
        for category, count in rejected_stats["categories"].items():
            st.write(f"**{category}:** {count}")
