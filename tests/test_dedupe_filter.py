"""Tests for dedupe_filter module."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from backend.processor.shared.dedupe_filter import (
    BloomFilter,
    compute_content_fingerprint,
    compute_url_hash,
    is_duplicate,
    reset_bloom,
)


class TestBloomFilter:
    """Tests for BloomFilter."""

    def test_add_and_check(self) -> None:
        bf = BloomFilter(expected_items=1000, fp_rate=0.01)
        bf.add("hello")
        assert bf.might_contain("hello") is True

    def test_not_found(self) -> None:
        bf = BloomFilter(expected_items=1000, fp_rate=0.01)
        assert bf.might_contain("nonexistent") is False

    def test_multiple_items(self) -> None:
        bf = BloomFilter(expected_items=1000, fp_rate=0.01)
        items = [f"item_{i}" for i in range(100)]
        for item in items:
            bf.add(item)
        for item in items:
            assert bf.might_contain(item) is True

    def test_size_bytes(self) -> None:
        bf = BloomFilter(expected_items=1000, fp_rate=0.01)
        assert bf.size_bytes > 0

    def test_false_positive_rate(self) -> None:
        bf = BloomFilter(expected_items=1000, fp_rate=0.01)
        # Add 1000 items
        for i in range(1000):
            bf.add(f"existing_{i}")
        # Check 10000 non-existing items
        false_positives = sum(1 for i in range(10000) if bf.might_contain(f"check_{i}"))
        # FP rate should be roughly < 5% (generous margin for test stability)
        assert false_positives / 10000 < 0.05


class TestHashFunctions:
    """Tests for URL hash and content fingerprint."""

    def test_url_hash_deterministic(self) -> None:
        h1 = compute_url_hash("https://example.com/article/1")
        h2 = compute_url_hash("https://example.com/article/1")
        assert h1 == h2

    def test_url_hash_length(self) -> None:
        h = compute_url_hash("https://example.com/article/1")
        assert len(h) == 16

    def test_url_hash_different_urls(self) -> None:
        h1 = compute_url_hash("https://example.com/1")
        h2 = compute_url_hash("https://example.com/2")
        assert h1 != h2

    def test_content_fingerprint_deterministic(self) -> None:
        fp1 = compute_content_fingerprint("Title", "Body content here")
        fp2 = compute_content_fingerprint("Title", "Body content here")
        assert fp1 == fp2

    def test_content_fingerprint_length(self) -> None:
        fp = compute_content_fingerprint("Title", "Body")
        assert len(fp) == 16

    def test_content_fingerprint_body_truncation(self) -> None:
        long_body = "x" * 500
        fp1 = compute_content_fingerprint("T", long_body)
        fp2 = compute_content_fingerprint("T", long_body[:200] + "different")
        # Only first 200 chars of body matter
        assert fp1 == fp2


class TestIsDuplicate:
    """Tests for is_duplicate async function."""

    @pytest.fixture(autouse=True)
    def _reset(self) -> None:
        reset_bloom()

    @pytest.mark.asyncio
    async def test_new_item_not_duplicate(self) -> None:
        mock_redis = AsyncMock()
        mock_redis.sismember = AsyncMock(return_value=False)
        mock_pipeline = AsyncMock()
        mock_pipeline.sadd = MagicMock()
        mock_pipeline.expire = MagicMock()
        mock_pipeline.execute = AsyncMock(return_value=[])
        mock_redis.pipeline = MagicMock(return_value=mock_pipeline)

        with patch(
            "backend.processor.shared.dedupe_filter.get_redis",
            return_value=mock_redis,
        ):
            result = await is_duplicate("https://example.com/new", "Title", "Body")
            assert result is False

    @pytest.mark.asyncio
    async def test_url_duplicate_detected(self) -> None:
        mock_redis = AsyncMock()
        mock_redis.sismember = AsyncMock(return_value=True)
        mock_pipeline = AsyncMock()
        mock_pipeline.sadd = MagicMock()
        mock_pipeline.expire = MagicMock()
        mock_pipeline.execute = AsyncMock(return_value=[])
        mock_redis.pipeline = MagicMock(return_value=mock_pipeline)

        with patch(
            "backend.processor.shared.dedupe_filter.get_redis",
            return_value=mock_redis,
        ):
            url = "https://example.com/dup"
            # First call registers in bloom
            await is_duplicate(url, "T", "B")
            # Second call: bloom says maybe, redis confirms
            result = await is_duplicate(url, "T", "B")
            assert result is True

    @pytest.mark.asyncio
    async def test_redis_error_lets_item_through(self) -> None:
        with patch(
            "backend.processor.shared.dedupe_filter.get_redis",
            side_effect=RuntimeError("connection lost"),
        ):
            # Should not raise, should let item through
            result = await is_duplicate("https://example.com/err", "T", "B")
            assert result is False
