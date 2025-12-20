import gc

import numpy as np

from src.sequential_masking import process_instances_sequentially


def test_process_instances_sequentially_handles_failures_and_cleanup(monkeypatch):
    arrays = [np.array([1, 2]), np.array([4])]
    processed = []
    gc_calls = []

    monkeypatch.setattr(gc, "collect", lambda: gc_calls.append(True))

    def _process(arr):
        processed.append(int(arr.sum()))
        if arr.sum() == 4:
            raise RuntimeError("boom")

    failures = process_instances_sequentially(arrays, _process)

    assert processed == [3, 4]
    assert failures == 1
    assert len(gc_calls) == len(arrays)

