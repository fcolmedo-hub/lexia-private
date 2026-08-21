from dataclasses import dataclass
from time import perf_counter


@dataclass(slots=True)
class SearchTiming:
    total_ms: float = 0.0
    cache_hit: bool = False


class SearchProfiler:
    def __enter__(self):
        self.started = perf_counter()
        self.timing = SearchTiming()
        return self.timing

    def __exit__(self, exc_type, exc, tb):
        self.timing.total_ms = round(
            (perf_counter() - self.started) * 1000,
            2,
        )
