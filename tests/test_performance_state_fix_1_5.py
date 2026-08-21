from pathlib import Path
def test_performance_and_state_fix():
 ui=(Path(__file__).parents[1]/"app"/"ui.py").read_text(encoding="utf-8")
 cat=(Path(__file__).parents[1]/"storage"/"catalog.py").read_text(encoding="utf-8")
 assert "def browse_documents_multi" in cat
 assert "app.catalog.browse_documents_multi" in ui
 assert "_inspector_folder_counts_cache" in ui
 assert "_open_local_path(_validate_openable_file(path))" in ui
 assert 'st.query_params.get("lexia_open_file")' not in ui
