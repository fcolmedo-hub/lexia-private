from hashlib import sha256
from pathlib import Path


class FileHasher:
    def __init__(self, block_size: int = 1024 * 1024):
        self.block_size = block_size

    def calculate(self, file_path: str | Path) -> str:
        digest = sha256()

        with Path(file_path).open("rb") as stream:
            while block := stream.read(self.block_size):
                digest.update(block)

        return digest.hexdigest()
