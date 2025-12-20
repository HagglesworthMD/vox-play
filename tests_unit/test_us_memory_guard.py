from types import SimpleNamespace

from src.utils import evaluate_us_mask_memory_guard


def _make_ds(rows, cols, frames, bits, samples):
    return SimpleNamespace(
        Rows=rows,
        Columns=cols,
        NumberOfFrames=frames,
        BitsAllocated=bits,
        SamplesPerPixel=samples,
    )


def test_guard_allows_small_us_series():
    ds = _make_ds(rows=512, cols=512, frames=1, bits=8, samples=1)

    should_skip, est_mb = evaluate_us_mask_memory_guard(ds, max_mb=10)

    assert should_skip is False
    assert est_mb < 10


def test_guard_blocks_large_us_series():
    ds = _make_ds(rows=4096, cols=4096, frames=10, bits=16, samples=3)

    should_skip, est_mb = evaluate_us_mask_memory_guard(ds, max_mb=600)

    assert should_skip is True
    assert est_mb > 600
