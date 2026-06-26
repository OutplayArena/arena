"""Seed propagation for the SDK.

The backend now echoes the effective experiment config (including ``seed``) in
``creation_response``, ``public_state``, and ``get_results`` (see PR #37). The
SDK consumes that field on first contact so the seed the user actually ran
with is preserved even if the backend normalized it.

Users get:

* :attr:`BaseAgent.seed` &mdash; the resolved seed (``int | None``).
* :attr:`BaseAgent.rng` &mdash; a :class:`random.Random` seeded with that value.

Example::

    agent = ColonelBlottoAgent(...)
    await agent.run()

    # Same seed everywhere
    numpy.random.seed(agent.seed)
    torch.manual_seed(agent.seed)
    my_rng = random.Random(agent.seed)
"""
from __future__ import annotations

import random
from typing import Any


class SeedResolver:
    """Lazily resolves and stores the experiment seed.

    The user can pass a ``seed=`` to :class:`BaseAgent` to override whatever
    the backend echoes. If neither is available, :attr:`seed` is ``None`` and
    :attr:`rng` falls back to a non-seeded :class:`random.Random` instance.
    """

    def __init__(self, override: int | None = None):
        self._override = override
        self._resolved: int | None = None
        self._rng = random.Random()
        if override is not None:
            self._rng.seed(override)

    @property
    def seed(self) -> int | None:
        return self._override if self._override is not None else self._resolved

    @property
    def rng(self) -> random.Random:
        return self._rng

    def resolve_from_config(self, config: dict[str, Any] | None) -> int | None:
        """Pull the seed out of a backend config dict and seed the RNG.

        No-op if a user-supplied override is already set, but still returns
        what the backend had so callers can log it.
        """
        backend_seed: int | None = None
        if isinstance(config, dict):
            raw = config.get("seed")
            if isinstance(raw, int):
                backend_seed = raw
            elif raw is not None:
                try:
                    backend_seed = int(raw)
                except (TypeError, ValueError):
                    backend_seed = None

        if self._override is not None:
            self._rng.seed(self._override)
            return backend_seed

        self._resolved = backend_seed
        if backend_seed is not None:
            self._rng.seed(backend_seed)
        return backend_seed

    def __repr__(self) -> str:
        return f"SeedResolver(seed={self.seed!r}, override={self._override is not None})"
