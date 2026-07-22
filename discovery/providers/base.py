"""Provider contract and shared value types."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from urllib.parse import quote


@dataclass
class StreamCredentials:
    username: str = ""
    password: str = ""

    def userinfo(self) -> str:
        """URL-encoded ``user:pass@`` prefix, or "" when no username is set."""
        if not self.username:
            return ""
        user = quote(self.username, safe="")
        if self.password:
            return f"{user}:{quote(self.password, safe='')}@"
        return f"{user}@"


@dataclass
class StreamChannel:
    channel: int
    stream_url: str  # full URL, credentials embedded, for storage/streaming
    name: str
    description: str | None = None


@dataclass
class EnumerationResult:
    provider: str
    channels: list[StreamChannel] = field(default_factory=list)
    requires_auth: bool = False
    error: str | None = None


class StreamProvider(ABC):
    """Turns a discovered service into connectable channels."""

    name: str = "base"

    @abstractmethod
    def supports(self, vendor: str | None, protocol: str) -> bool:
        """Whether this provider can enumerate the given device/service."""

    @abstractmethod
    def enumerate(
        self,
        host: str,
        port: int,
        protocol: str,
        credentials: StreamCredentials | None,
        channel_count: int,
    ) -> EnumerationResult:
        """Produce the channels for this device/service."""
