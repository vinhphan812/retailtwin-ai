"""Case-insensitive HTTP header mapping.

``google-auth`` treats response headers as a case-insensitive mapping: the
compute-engine metadata transport reads ``response.headers["content-type"]``
and ``response.headers.get("Metadata-Flavor")``, while the ``requests``-backed
transport satisfies that with ``requests.structures.CaseInsensitiveDict``.

A plain ``dict`` of headers does **not** satisfy the contract: HTTP servers
answer with canonical casing (``Content-Type``), so a lowercase lookup raises
``KeyError`` and an Application Default Credentials refresh fails with
``Application Default Credentials are not available: KeyError``.

:class:`CaseInsensitiveHeaders` is the stdlib-only equivalent used by the
``urllib`` transport, so both ADC paths behave identically.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from typing import Any

__all__ = ["CaseInsensitiveHeaders"]


class CaseInsensitiveHeaders(Mapping[str, str]):
    """A read-only mapping of HTTP headers with case-insensitive lookups.

    Keys are matched case-insensitively; the original casing is preserved
    when iterating, mirroring ``requests.structures.CaseInsensitiveDict``.
    """

    __slots__ = ("_store",)

    def __init__(self, headers: Mapping[str, str] | None = None) -> None:
        # lowercase key -> (original key, value)
        store: dict[str, tuple[str, str]] = {}
        for key, value in (headers or {}).items():
            store[key.lower()] = (key, value)
        self._store = store

    def __getitem__(self, key: str) -> str:
        try:
            return self._store[key.lower()][1]
        except KeyError:
            raise KeyError(key) from None

    def __iter__(self) -> Iterator[str]:
        return (original for original, _ in self._store.values())

    def __len__(self) -> int:
        return len(self._store)

    def __contains__(self, key: object) -> bool:
        return isinstance(key, str) and key.lower() in self._store

    def get(self, key: str, default: Any = None) -> Any:
        entry = self._store.get(key.lower())
        return default if entry is None else entry[1]

    def __repr__(self) -> str:
        return f"{type(self).__name__}({dict(self)!r})"
