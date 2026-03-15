"""Tests for license key generation and hashing utilities."""

from __future__ import annotations

from license_server.key_gen import (
    PRODUCT_KEY_CONFIG,
    _compute_check_segment,
    generate_key,
    hash_key,
    mask_key,
    validate_key_checksum,
    validate_key_format,
)

_CMDF_SALT = PRODUCT_KEY_CONFIG["anchormd"][1]


class TestGenerateKey:
    def test_format_valid(self) -> None:
        key = generate_key()
        assert validate_key_format(key)

    def test_checksum_valid(self) -> None:
        key = generate_key()
        assert validate_key_checksum(key)

    def test_starts_with_prefix(self) -> None:
        key = generate_key()
        assert key.startswith("ANMD-")

    def test_four_segments(self) -> None:
        key = generate_key()
        assert len(key.split("-")) == 4

    def test_each_segment_four_chars(self) -> None:
        key = generate_key()
        for part in key.split("-"):
            assert len(part) == 4

    def test_uniqueness(self) -> None:
        keys = {generate_key() for _ in range(50)}
        assert len(keys) == 50

    def test_uppercase(self) -> None:
        key = generate_key()
        assert key == key.upper()


class TestMultiProduct:
    def test_agent_lint_prefix(self) -> None:
        key = generate_key("agent-lint")
        assert key.startswith("ALNT-")
        assert validate_key_format(key, "agent-lint")
        assert validate_key_checksum(key, "agent-lint")

    def test_ai_spend_prefix(self) -> None:
        key = generate_key("ai-spend")
        assert key.startswith("ASPD-")
        assert validate_key_format(key, "ai-spend")
        assert validate_key_checksum(key, "ai-spend")

    def test_promptctl_prefix(self) -> None:
        key = generate_key("promptctl")
        assert key.startswith("PCTL-")
        assert validate_key_format(key, "promptctl")
        assert validate_key_checksum(key, "promptctl")

    def test_unknown_product_raises(self) -> None:
        import pytest

        with pytest.raises(ValueError, match="Unknown product"):
            generate_key("nonexistent")

    def test_cross_product_checksum_fails(self) -> None:
        """A key for one product must not validate against another."""
        key = generate_key("agent-lint")
        assert not validate_key_checksum(key, "anchormd")
        assert not validate_key_format(key, "anchormd")

    def test_cross_product_format_fails(self) -> None:
        key = generate_key("ai-spend")
        assert not validate_key_format(key, "promptctl")


class TestHashKey:
    def test_deterministic(self) -> None:
        h1 = hash_key("ANMD-ABCD-EFGH-32E3")
        h2 = hash_key("ANMD-ABCD-EFGH-32E3")
        assert h1 == h2

    def test_hex_string(self) -> None:
        h = hash_key("ANMD-ABCD-EFGH-32E3")
        int(h, 16)  # raises ValueError if not hex

    def test_64_chars(self) -> None:
        h = hash_key("ANMD-ABCD-EFGH-32E3")
        assert len(h) == 64

    def test_different_keys_different_hashes(self) -> None:
        h1 = hash_key("ANMD-ABCD-EFGH-32E3")
        h2 = hash_key("ANMD-WXYZ-QRST-1234")
        assert h1 != h2

    def test_strips_whitespace(self) -> None:
        h1 = hash_key("ANMD-ABCD-EFGH-32E3")
        h2 = hash_key("  ANMD-ABCD-EFGH-32E3  ")
        assert h1 == h2


class TestMaskKey:
    def test_masks_middle_segments(self) -> None:
        assert mask_key("ANMD-ABCD-EFGH-32E3") == "ANMD-****-****-32E3"

    def test_preserves_last_segment(self) -> None:
        masked = mask_key("ANMD-XXXX-YYYY-ZZZZ")
        assert masked.endswith("ZZZZ")

    def test_invalid_format_gives_full_mask(self) -> None:
        masked = mask_key("garbage")
        assert masked == "****-****-****-****"

    def test_strips_whitespace(self) -> None:
        masked = mask_key("  ANMD-ABCD-EFGH-32E3  ")
        assert masked == "ANMD-****-****-32E3"

    def test_masks_other_products(self) -> None:
        assert mask_key("ALNT-ABCD-EFGH-54EF") == "ALNT-****-****-54EF"
        assert mask_key("ASPD-ABCD-EFGH-54EF") == "ASPD-****-****-54EF"
        assert mask_key("PCTL-ABCD-EFGH-54EF") == "PCTL-****-****-54EF"


class TestValidateKeyFormat:
    def test_valid(self) -> None:
        assert validate_key_format("ANMD-ABCD-EFGH-32E3") is True

    def test_wrong_prefix(self) -> None:
        assert validate_key_format("XXXX-ABCD-EFGH-54EF") is False

    def test_lowercase(self) -> None:
        assert validate_key_format("ANMD-abcd-efgh-54ef") is False

    def test_too_short(self) -> None:
        assert validate_key_format("ANMD-AB-CD") is False

    def test_empty(self) -> None:
        assert validate_key_format("") is False

    def test_unknown_product_returns_false(self) -> None:
        assert validate_key_format("ANMD-ABCD-EFGH-32E3", "nonexistent") is False


class TestCheckSegment:
    def test_deterministic(self) -> None:
        s1 = _compute_check_segment("ABCD-EFGH", _CMDF_SALT)
        s2 = _compute_check_segment("ABCD-EFGH", _CMDF_SALT)
        assert s1 == s2

    def test_four_chars(self) -> None:
        seg = _compute_check_segment("ABCD-EFGH", _CMDF_SALT)
        assert len(seg) == 4

    def test_uppercase(self) -> None:
        seg = _compute_check_segment("ABCD-EFGH", _CMDF_SALT)
        assert seg == seg.upper()

    def test_different_bodies(self) -> None:
        s1 = _compute_check_segment("ABCD-EFGH", _CMDF_SALT)
        s2 = _compute_check_segment("WXYZ-QRST", _CMDF_SALT)
        assert s1 != s2

    def test_different_salts(self) -> None:
        s1 = _compute_check_segment("ABCD-EFGH", "salt-a")
        s2 = _compute_check_segment("ABCD-EFGH", "salt-b")
        assert s1 != s2

    def test_matches_cli_implementation(self) -> None:
        """Verify server key_gen matches CLI licensing.py for anchormd."""
        from anchormd.licensing import _compute_check_segment as cli_compute

        body = "ABCD-EFGH"
        assert _compute_check_segment(body, _CMDF_SALT) == cli_compute(body)
