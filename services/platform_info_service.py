\
import importlib.util

from config.settings import SETTINGS
from platform_version import (
    BUILD,
    CHANNEL,
    PRODUCT_NAME,
    VERSION,
)


class PlatformInfoService:
    ESSENTIAL_COMPONENTS = {
        "Performance Core": (
            "services.performance_profiler",
            "2.0",
        ),
        "Prompt Protocol": (
            "prompt.compiler",
            "2.0",
        ),
        "Prompt Launcher": (
            "prompt.launcher",
            "1.0",
        ),
        "Knowledge Engine": (
            "services.knowledge_engine",
            "3.x",
        ),
        "Index Engine": (
            "core.pipeline",
            "3.x",
        ),
        "Activity Center": (
            "services.activity_center_service",
            "1.x",
        ),
        "PDF Header Validation": (
            "core.document_extractor",
            "1.0",
        ),
    }

    def status(self):
        components = {}

        for name, (
            module,
            version,
        ) in self.ESSENTIAL_COMPONENTS.items():
            available = (
                importlib.util.find_spec(module)
                is not None
            )
            components[name] = {
                "available": available,
                "version": version,
            }

        healthy = all(
            component["available"]
            for component in components.values()
        )

        return {
            "product": PRODUCT_NAME,
            "version": VERSION,
            "build": BUILD,
            "channel": CHANNEL,
            "healthy": healthy,
            "components": components,
            "settings": {
                "startup_mode": getattr(
                    SETTINGS,
                    "autosync_startup_mode",
                    "unknown",
                ),
                "max_queries": getattr(
                    SETTINGS,
                    "interpreted_max_queries",
                    "unknown",
                ),
                "max_sources": getattr(
                    SETTINGS,
                    "context_builder_runtime_max_sources",
                    "unknown",
                ),
                "qdrant_mode": (
                    "local_embedded"
                    if getattr(
                        SETTINGS,
                        "vector_path",
                        None,
                    )
                    else "unknown"
                ),
            },
        }
