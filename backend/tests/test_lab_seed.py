import pytest
from app.seed.lab import LAB_GROUP_NAMES, LAB_PREFIX, LAB_USER_NAMES, seed_lab


@pytest.mark.asyncio
async def test_hard_requires_force():
    with pytest.raises(ValueError, match="--hard requires --force"):
        await seed_lab(force=False, hard=True, ensure_base=False)


def test_lab_identifiers_cover_seed_entities():
    assert "jsmith" in LAB_USER_NAMES
    assert "Service Desk" in LAB_GROUP_NAMES
    assert LAB_PREFIX == "[LAB]"
