"""
Unit tests for src/run_on_dicom.py

Goals:
- Test process_dataset() metadata-only and pixel-present paths
- Test detect_text_box_from_array() with mocked OCR results
- Test process_dicom() error handling paths
"""

from __future__ import annotations

import inspect
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional, Tuple

import numpy as np
import pytest

# Ensure src is on the path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import run_on_dicom


# ----------------------------
# Helpers
# ----------------------------

def _call_with_supported_kwargs(func, *args, **kwargs):
    sig = inspect.signature(func)
    supported = {k: v for k, v in kwargs.items() if k in sig.parameters}
    return func(*args, **supported)


def _make_fake_dataset(**fields):
    """Prefer real pydicom Dataset if available; otherwise a simple stub."""
    try:
        from pydicom.dataset import Dataset  # type: ignore
        ds = Dataset()
        for k, v in fields.items():
            setattr(ds, k, v)
        return ds
    except Exception:
        class Stub: ...
        ds = Stub()
        for k, v in fields.items():
            setattr(ds, k, v)
        return ds


def _find_corrector_method(corrector: Any) -> Callable:
    """
    detect_text_box_from_array() will call *something* on corrector.
    We try common method names used in ClinicalCorrector implementations.
    """
    candidates = [
        "detect_static_text",
        "detect_text_box_from_array",  # sometimes delegated
        "ocr_frame",
        "run_ocr",
        "infer_text_boxes",
        "detect_text",
    ]
    for name in candidates:
        m = getattr(corrector, name, None)
        if callable(m):
            return m

    # fallback: any callable attribute containing 'ocr' or 'detect'
    for name in dir(corrector):
        if ("ocr" in name.lower() or "detect" in name.lower()) and callable(getattr(corrector, name, None)):
            return getattr(corrector, name)

    raise AssertionError(
        "Could not find a usable OCR/detect method on the stub corrector. "
        "Update _find_corrector_method() to match the method called inside "
        "run_on_dicom.detect_text_box_from_array()."
    )


@dataclass
class StubCorrector:
    """
    A deterministic corrector stub that returns a configured box per call.
    If `boxes` is a list, each call returns the next box (or None).
    """
    boxes: list[Optional[Tuple[int, int, int, int]]]

    def __post_init__(self):
        self.calls = 0

    # Common name used in your project
    def detect_static_text(self, frame: np.ndarray, debug_frame: np.ndarray = None) -> Optional[Tuple[int, int, int, int]]:
        i = self.calls
        self.calls += 1
        if i < len(self.boxes):
            return self.boxes[i]
        return self.boxes[-1] if self.boxes else None
    
    # Stub for _preprocess_for_ocr (called inside detect_text_box_from_array)
    def _preprocess_for_ocr(self, frame: np.ndarray) -> np.ndarray:
        return frame
    
    # Stub for _boxes_overlap (called inside detect_text_box_from_array)
    def _boxes_overlap(self, box1, box2, tolerance=20) -> bool:
        x1, y1, w1, h1 = box1
        x2, y2, w2, h2 = box2
        # Simple overlap check with tolerance
        return (abs(x1 - x2) < tolerance and 
                abs(y1 - y2) < tolerance and
                abs(w1 - w2) < tolerance and
                abs(h1 - h2) < tolerance)


@dataclass
class StubOCR:
    """Stub OCR engine that returns configured detection results."""
    det_boxes: list
    
    def predict(self, frame: np.ndarray) -> list:
        if not self.det_boxes:
            return []
        return [{"det_boxes": self.det_boxes}]


# ----------------------------
# process_dataset tests
# ----------------------------

def test_process_dataset_calls_anonymize_metadata_and_returns_metadata_only_when_no_pixeldata(monkeypatch):
    ds = _make_fake_dataset(PatientName="OLD^NAME")  # no PixelData attribute

    called = {"n": 0, "args": None}

    def spy_anonymize(d, new_name, research_context, clinical_context):
        called["n"] += 1
        called["args"] = (d, new_name, research_context, clinical_context)

    monkeypatch.setattr(run_on_dicom, "anonymize_metadata", spy_anonymize)

    out = run_on_dicom.process_dataset(
        ds,
        old_name_text="OLD",
        new_name_text="NEW",
        research_context={"mode": "research"},
        clinical_context={"mode": "clinical"},
    )

    assert out is ds
    assert called["n"] == 1
    assert called["args"][0] is ds
    assert called["args"][1] == "NEW"


def test_process_dataset_returns_early_when_pixeldata_present(monkeypatch):
    ds = _make_fake_dataset(PatientName="OLD^NAME", PixelData=b"\x00\x01")

    called = {"n": 0}

    def spy_anonymize(*args, **kwargs):
        called["n"] += 1

    monkeypatch.setattr(run_on_dicom, "anonymize_metadata", spy_anonymize)

    out = run_on_dicom.process_dataset(
        ds,
        old_name_text="OLD",
        new_name_text="NEW",
        research_context=None,
        clinical_context=None,
    )

    assert out is ds
    assert called["n"] == 1


def test_process_dataset_returns_ds_when_pixeldata_is_none(monkeypatch):
    """Covers line 317-318: PixelData exists but is None."""
    ds = _make_fake_dataset(PatientName="OLD^NAME", PixelData=None)

    def spy_anonymize(*args, **kwargs):
        pass

    monkeypatch.setattr(run_on_dicom, "anonymize_metadata", spy_anonymize)

    out = run_on_dicom.process_dataset(
        ds,
        old_name_text="OLD",
        new_name_text="NEW",
    )

    assert out is ds


# ----------------------------
# detect_text_box_from_array tests
# ----------------------------

def test_detect_text_box_returns_tuple_for_empty_input():
    """Empty array should return DetectionResult with None static_box."""
    corrector = StubCorrector(boxes=[])
    corrector.ocr = StubOCR(det_boxes=[])
    arr = np.zeros((1, 64, 64, 3), dtype=np.uint8)  # 4D array as expected
    
    result = run_on_dicom.detect_text_box_from_array(corrector, arr)
    
    # Phase 4: Function now returns DetectionResult
    from run_on_dicom import DetectionResult
    assert isinstance(result, DetectionResult)
    assert result.static_box is None
    assert isinstance(result.all_detected_boxes, list)


def test_detect_text_box_returns_box_when_consistent_across_frames():
    """When OCR returns same box across frames, should be detected as static."""
    # Create box coordinates (note: OCR returns scaled coordinates)
    box_points = [[20, 24], [120, 24], [120, 84], [20, 84]]  # x2 scale
    
    corrector = StubCorrector(boxes=[])
    corrector.ocr = StubOCR(det_boxes=[box_points])
    
    # 6 frames, 4D array
    arr = np.zeros((6, 64, 64, 3), dtype=np.uint8)
    
    result = run_on_dicom.detect_text_box_from_array(corrector, arr)
    
    # Should have detected boxes
    assert len(result.all_detected_boxes) > 0


def test_detect_text_box_handles_single_frame():
    """Single frame should work without errors."""
    corrector = StubCorrector(boxes=[])
    corrector.ocr = StubOCR(det_boxes=[])
    
    arr = np.zeros((1, 64, 64, 3), dtype=np.uint8)
    
    result = run_on_dicom.detect_text_box_from_array(corrector, arr)
    
    # Should return DetectionResult even with single frame
    from run_on_dicom import DetectionResult
    assert isinstance(result, DetectionResult)
    assert result.static_box is None or isinstance(result.static_box, tuple)


def test_detect_text_box_handles_grayscale_frames():
    """Grayscale frames should be converted to BGR."""
    corrector = StubCorrector(boxes=[])
    corrector.ocr = StubOCR(det_boxes=[])
    
    # 2D frames (grayscale)
    arr = np.zeros((3, 64, 64), dtype=np.uint8)
    # Add channel dimension
    arr = arr[:, :, :, np.newaxis]
    
    result = run_on_dicom.detect_text_box_from_array(corrector, arr)
    
    assert isinstance(result.all_detected_boxes, list)


def test_detect_text_box_handles_ocr_exception(capsys):
    """OCR exception should be caught and logged, with explicit uncertainty."""
    corrector = StubCorrector(boxes=[])
    
    # Create OCR that raises exception
    class FailingOCR:
        def predict(self, frame):
            raise RuntimeError("OCR failed")
    
    corrector.ocr = FailingOCR()
    
    arr = np.zeros((2, 64, 64, 3), dtype=np.uint8)
    
    result = run_on_dicom.detect_text_box_from_array(corrector, arr)
    
    captured = capsys.readouterr()
    assert "OCR error" in captured.out
    # Phase 4: OCR failure should result in explicit uncertainty
    assert result.ocr_failure is True
    assert result.detection_strength is None


def test_detect_text_box_accepts_debug_frame_argument():
    """debug_frame parameter should be accepted."""
    corrector = StubCorrector(boxes=[])
    corrector.ocr = StubOCR(det_boxes=[])

    arr = np.zeros((3, 32, 32, 3), dtype=np.uint8)
    debug = np.zeros((32, 32, 3), dtype=np.uint8)

    # Should not raise
    result = run_on_dicom.detect_text_box_from_array(corrector, arr, debug_frame=debug)
    from run_on_dicom import DetectionResult
    assert isinstance(result, DetectionResult)


def test_detect_text_box_handles_list_format_ocr_result():
    """OCR can return list format instead of dict format."""
    corrector = StubCorrector(boxes=[])
    
    # List format: [[box_points, (text, confidence)], ...]
    box_points = [[20, 24], [120, 24], [120, 84], [20, 84]]
    
    class ListFormatOCR:
        def predict(self, frame):
            return [[[box_points, ("TEXT", 0.95)]]]
    
    corrector.ocr = ListFormatOCR()
    
    arr = np.zeros((2, 64, 64, 3), dtype=np.uint8)
    
    result = run_on_dicom.detect_text_box_from_array(corrector, arr)
    
    # Should handle list format without error
    assert isinstance(result.all_detected_boxes, list)


# ----------------------------
# process_dicom negative-path test
# ----------------------------

def test_process_dicom_raises_runtimeerror_when_dcmread_fails(monkeypatch, capsys, tmp_path):
    def boom(*args, **kwargs):
        raise Exception("nope")

    monkeypatch.setattr(run_on_dicom.pydicom, "dcmread", boom)

    in_path = tmp_path / "in.dcm"
    out_path = tmp_path / "out.dcm"
    in_path.write_bytes(b"")  # file existence not strictly required, but harmless

    with pytest.raises(RuntimeError) as excinfo:
        run_on_dicom.process_dicom(
            str(in_path),
            str(out_path),
            old_name_text="OLD",
            new_name_text="NEW",
        )

    # Verify print happened and error message is wrapped consistently
    captured = capsys.readouterr()
    assert "Loading DICOM file" in captured.out
    assert "Failed to read DICOM file" in str(excinfo.value)


def test_process_dicom_prints_loading_message(monkeypatch, capsys, tmp_path):
    """Verify process_dicom prints loading message (line 459)."""
    def boom(*args, **kwargs):
        raise Exception("fail early")

    monkeypatch.setattr(run_on_dicom.pydicom, "dcmread", boom)

    in_path = tmp_path / "test.dcm"
    out_path = tmp_path / "out.dcm"
    in_path.write_bytes(b"DICM")

    with pytest.raises(RuntimeError):
        run_on_dicom.process_dicom(
            str(in_path),
            str(out_path),
            old_name_text="OLD",
            new_name_text="NEW",
        )

    captured = capsys.readouterr()
    assert "Loading DICOM file" in captured.out
    assert str(in_path) in captured.out
