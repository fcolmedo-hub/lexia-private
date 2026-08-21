class QdrantStatusService:
    def __init__(self, vector_store):
        self.vector_store = vector_store

    def status(self) -> dict:
        try:
            return {"healthy": True, **self.vector_store.status()}
        except Exception as error:
            return {
                "healthy": False,
                "mode": "error",
                "url": "",
                "collection": "",
                "points": 0,
                "error": str(error),
            }
