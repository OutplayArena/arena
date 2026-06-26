"""Tests for :mod:`outplayarena_sdk.seed`."""
from __future__ import annotations

import random

from outplayarena_sdk.seed import SeedResolver


class TestSeedResolver:
    def test_no_seed_no_override(self):
        r = SeedResolver()
        assert r.seed is None
        # rng is still usable, just not deterministic.
        assert isinstance(r.rng, random.Random)
        assert r.rng.random() >= 0  # doesn't raise

    def test_override_takes_precedence(self):
        r = SeedResolver(override=42)
        assert r.seed == 42
        # Two consecutive draws match what random.Random(42) would do.
        rng = random.Random(42)
        assert r.rng.random() == rng.random()

    def test_resolve_from_config(self):
        r = SeedResolver()
        assert r.resolve_from_config({"seed": 7, "rounds": 5}) == 7
        assert r.seed == 7
        rng = random.Random(7)
        assert r.rng.random() == rng.random()

    def test_resolve_from_config_overridden(self):
        """When an override is set, resolve_from_config seeds the rng from the override."""
        r = SeedResolver(override=99)
        r.resolve_from_config({"seed": 7})
        assert r.seed == 99
        rng = random.Random(99)
        assert r.rng.random() == rng.random()

    def test_resolve_from_config_missing_seed(self):
        r = SeedResolver()
        result = r.resolve_from_config({"rounds": 5})
        assert result is None
        assert r.seed is None

    def test_resolve_from_config_none_dict(self):
        r = SeedResolver()
        result = r.resolve_from_config(None)
        assert result is None
        assert r.seed is None

    def test_resolve_from_config_invalid_seed_type(self):
        r = SeedResolver()
        result = r.resolve_from_config({"seed": "not-a-number"})
        assert result is None
        assert r.seed is None

    def test_resolve_repeated_overwrites(self):
        """Re-resolving should update the rng, not stack effects."""
        r = SeedResolver()
        r.resolve_from_config({"seed": 1})
        r.rng.random()  # discard first draw
        r.resolve_from_config({"seed": 2})
        actual = r.rng.random()
        # Re-reseeding makes draws deterministic from the new seed.
        rng = random.Random(2)
        assert actual == rng.random()
