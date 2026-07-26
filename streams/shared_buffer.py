"""Cross-process latest-frame buffers for Stream Manager consumers."""

from __future__ import annotations

import mmap
from pathlib import Path
import struct
import threading
import time


_MAGIC = b"AIV2"
_HEADER = struct.Struct("<4sQQQ")
_DEFAULT_CAPACITY = 2 * 1024 * 1024


def buffer_path(directory: str | Path, slot_number: int) -> Path:
    return Path(directory) / f".stream_frame_slot_{int(slot_number)}.buf"


class SharedFrameWriter:
    """Single-writer, multi-reader memory-mapped JPEG buffer."""

    def __init__(
        self,
        directory: str | Path,
        slot_number: int,
        capacity: int = _DEFAULT_CAPACITY,
    ):
        self.path = buffer_path(directory, slot_number)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.capacity = max(int(capacity), 64 * 1024)
        self._lock = threading.Lock()
        self._sequence = 0
        total_size = _HEADER.size + self.capacity
        try:
            self._file = self.path.open("x+b")
            self._file.truncate(total_size)
        except FileExistsError:
            self._file = self.path.open("r+b")
            if self.path.stat().st_size != total_size:
                self._file.truncate(total_size)
        self._mapping = mmap.mmap(self._file.fileno(), 0, access=mmap.ACCESS_WRITE)
        self._write_header(0, 0, 0)

    def publish(self, data: bytes) -> int:
        if len(data) > self.capacity:
            raise ValueError(
                f"encoded frame is {len(data)} bytes; buffer capacity is {self.capacity}"
            )
        with self._lock:
            writing_sequence = self._sequence + 1
            if writing_sequence % 2 == 0:
                writing_sequence += 1
            self._write_header(writing_sequence, 0, 0)
            self._mapping[_HEADER.size : _HEADER.size + len(data)] = data
            self._sequence = writing_sequence + 1
            self._write_header(self._sequence, len(data), time.time_ns())
            return self._sequence

    def close(self, remove: bool = False) -> None:
        with self._lock:
            mapping = getattr(self, "_mapping", None)
            self._mapping = None
            if mapping is not None:
                mapping.close()
            file_handle = getattr(self, "_file", None)
            self._file = None
            if file_handle is not None:
                file_handle.close()
        if remove:
            try:
                self.path.unlink()
            except OSError:
                pass

    def _write_header(self, sequence: int, length: int, timestamp_ns: int) -> None:
        self._mapping[: _HEADER.size] = _HEADER.pack(
            _MAGIC, sequence, length, timestamp_ns
        )


class SharedFrameReader:
    """Read coherent snapshots without locking or owning the producer."""

    def __init__(self, directory: str | Path, slot_number: int):
        self.path = buffer_path(directory, slot_number)
        self._file = None
        self._mapping = None
        self._identity = None

    def read(self, after_sequence: int | None = None) -> tuple[int, bytes] | None:
        if self._mapping is not None and not self._is_current_file():
            self.close()
        if not self._ensure_open():
            return None
        for _ in range(3):
            try:
                first = _HEADER.unpack(self._mapping[: _HEADER.size])
                magic, sequence, length, _timestamp_ns = first
                if (
                    magic != _MAGIC
                    or sequence == 0
                    or sequence % 2
                    or length == 0
                    or length > len(self._mapping) - _HEADER.size
                ):
                    return None
                if after_sequence is not None and sequence == after_sequence:
                    return None
                data = bytes(self._mapping[_HEADER.size : _HEADER.size + length])
                second = _HEADER.unpack(self._mapping[: _HEADER.size])
                if first == second and data.startswith(b"\xff\xd8") and data.endswith(b"\xff\xd9"):
                    return sequence, data
            except (BufferError, OSError, ValueError):
                self.close()
                return None
        return None

    def close(self) -> None:
        mapping = self._mapping
        self._mapping = None
        if mapping is not None:
            mapping.close()
        file_handle = self._file
        self._file = None
        self._identity = None
        if file_handle is not None:
            file_handle.close()

    def _ensure_open(self) -> bool:
        if self._mapping is not None:
            return True
        try:
            self._file = self.path.open("rb")
            self._mapping = mmap.mmap(self._file.fileno(), 0, access=mmap.ACCESS_READ)
            stat = self.path.stat()
            self._identity = (stat.st_dev, stat.st_ino)
            return True
        except (FileNotFoundError, OSError, ValueError):
            self.close()
            return False

    def _is_current_file(self) -> bool:
        try:
            stat = self.path.stat()
            return self._identity == (stat.st_dev, stat.st_ino)
        except OSError:
            return False
