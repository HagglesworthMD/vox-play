"""
Unit tests for src/patched_canvas.py

Tests the patched streamlit-drawable-canvas that uses base64 encoding
instead of the removed st_image.image_to_url.
"""
import base64
import io

import numpy as np
import pytest
from PIL import Image


@pytest.fixture
def rgb_img():
    return Image.new("RGB", (10, 10), color=(10, 20, 30))


@pytest.fixture
def rgba_img():
    # semi-transparent pixel to ensure RGBA path is used
    img = Image.new("RGBA", (10, 10), color=(10, 20, 30, 128))
    return img


@pytest.fixture
def l_img():
    return Image.new("L", (10, 10), color=128)


@pytest.fixture
def la_img():
    return Image.new("LA", (10, 10), color=(128, 200))


@pytest.fixture
def p_img():
    # Palette mode hits "other modes -> RGB"
    img = Image.new("P", (10, 10))
    return img


def _decode_data_url(data_url: str) -> bytes:
    assert data_url.startswith("data:image/")
    header, b64 = data_url.split(",", 1)
    return base64.b64decode(b64)


# ============================================================================
# Tests for _data_url_to_image
# ============================================================================

def test_data_url_to_image_decodes_png_roundtrip(rgb_img):
    from src.patched_canvas import _image_to_data_url, _data_url_to_image

    url = _image_to_data_url(rgb_img)
    out = _data_url_to_image(url)

    assert isinstance(out, Image.Image)
    assert out.size == (10, 10)
    assert out.mode in ("RGB", "RGBA")  # encoder may choose


# ============================================================================
# Tests for _resize_img
# ============================================================================

def test_resize_img_changes_dimensions(rgb_img):
    from src.patched_canvas import _resize_img

    out = _resize_img(rgb_img, new_height=7, new_width=5)
    assert isinstance(out, Image.Image)
    assert out.size == (5, 7)


def test_resize_img_maintains_image_validity(rgb_img):
    from src.patched_canvas import _resize_img

    out = _resize_img(rgb_img, new_height=20, new_width=30)
    assert out.mode in ("RGB", "RGBA", "L", "P")
    # Should be able to get pixels without error
    assert out.getpixel((0, 0)) is not None


# ============================================================================
# Tests for _image_to_data_url
# ============================================================================

def test_image_to_data_url_rgb_stays_valid(rgb_img):
    from src.patched_canvas import _image_to_data_url

    url = _image_to_data_url(rgb_img)
    raw = _decode_data_url(url)

    im2 = Image.open(io.BytesIO(raw))
    assert im2.size == (10, 10)


def test_image_to_data_url_converts_rgba_to_rgb_with_white_bg(rgba_img):
    """
    Covers RGBA -> RGB composite on white background branch (lines 54-58).
    """
    from src.patched_canvas import _image_to_data_url

    url = _image_to_data_url(rgba_img)
    raw = _decode_data_url(url)
    im2 = Image.open(io.BytesIO(raw))

    # Should no longer be RGBA after conversion branch
    assert im2.mode in ("RGB", "P")  # depending on encoder; typically RGB
    assert im2.size == (10, 10)


def test_image_to_data_url_converts_grayscale_L_to_rgb(l_img):
    """
    Covers grayscale L mode conversion (lines 60-64).
    """
    from src.patched_canvas import _image_to_data_url

    url = _image_to_data_url(l_img)
    raw = _decode_data_url(url)
    im2 = Image.open(io.BytesIO(raw))

    assert im2.size == (10, 10)
    assert im2.mode in ("RGB", "P", "RGBA")


def test_image_to_data_url_converts_grayscale_LA_to_rgb(la_img):
    """
    Covers grayscale LA mode conversion (lines 60-64).
    """
    from src.patched_canvas import _image_to_data_url

    url = _image_to_data_url(la_img)
    raw = _decode_data_url(url)
    im2 = Image.open(io.BytesIO(raw))

    assert im2.size == (10, 10)
    assert im2.mode in ("RGB", "P", "RGBA")


def test_image_to_data_url_converts_other_modes_to_rgb(p_img):
    """
    Hits the 'other modes -> RGB' branch (lines 65-68, e.g., palette mode).
    """
    from src.patched_canvas import _image_to_data_url

    url = _image_to_data_url(p_img)
    raw = _decode_data_url(url)
    im2 = Image.open(io.BytesIO(raw))

    assert im2.size == (10, 10)
    assert im2.mode in ("RGB", "P", "RGBA")


def test_image_to_data_url_returns_valid_data_url_format(rgb_img):
    """
    Ensures the returned string is a valid data URL with correct prefix.
    """
    from src.patched_canvas import _image_to_data_url

    url = _image_to_data_url(rgb_img)
    
    assert url.startswith("data:image/png;base64,")
    # Should be decodable
    b64_part = url.split(",", 1)[1]
    decoded = base64.b64decode(b64_part)
    assert len(decoded) > 0


# ============================================================================
# Tests for CanvasResult dataclass
# ============================================================================

def test_canvas_result_dataclass_defaults():
    from src.patched_canvas import CanvasResult

    result = CanvasResult()
    assert result.image_data is None
    assert result.json_data is None


def test_canvas_result_dataclass_with_values():
    from src.patched_canvas import CanvasResult

    arr = np.zeros((10, 10, 3), dtype=np.uint8)
    json_data = {"objects": []}
    
    result = CanvasResult(image_data=arr, json_data=json_data)
    
    assert result.image_data is arr
    assert result.json_data == {"objects": []}


# ============================================================================
# Tests for st_canvas
# ============================================================================

def test_st_canvas_returns_empty_result_when_component_returns_none(monkeypatch, rgb_img):
    """
    When the component returns None (no drawing yet), st_canvas returns empty CanvasResult.
    """
    import src.patched_canvas as pc

    def fake_component_func(*args, **kwargs):
        return None

    monkeypatch.setattr(pc, "_component_func", fake_component_func)

    res = pc.st_canvas(
        fill_color="rgba(255, 0, 0, 0.3)",
        stroke_width=2,
        stroke_color="#00ffff",
        background_color="#ffffff",
        height=100,
        width=200,
        drawing_mode="rect",
        key="test_none",
    )

    assert isinstance(res, pc.CanvasResult)
    assert res.image_data is None
    assert res.json_data is None


def test_st_canvas_wraps_component_result(monkeypatch, rgb_img):
    """
    st_canvas should call _component_func and return CanvasResult(image_data, json_data).
    We mock the component payload to match what the real component returns.
    """
    import src.patched_canvas as pc

    # Create an image data URL to simulate what the component would return
    # The real component returns {"data": data_url, "raw": json_data}
    image_url = pc._image_to_data_url(rgb_img)
    
    payload = {
        "data": image_url,  # Component returns 'data' key
        "raw": {"objects": [{"type": "rect", "left": 1, "top": 2, "width": 3, "height": 4}]},
    }

    def fake_component_func(*args, **kwargs):
        return payload

    monkeypatch.setattr(pc, "_component_func", fake_component_func)

    res = pc.st_canvas(
        fill_color="rgba(255, 0, 0, 0.3)",
        stroke_width=2,
        stroke_color="#00ffff",
        background_color="#ffffff",
        height=100,
        width=200,
        drawing_mode="rect",
        key="test_result",
    )

    assert isinstance(res, pc.CanvasResult)
    # image_data is converted to numpy array by _data_url_to_image + np.asarray
    assert isinstance(res.image_data, np.ndarray)
    assert res.image_data.shape[:2] == (10, 10)  # Height x Width
    
    # json_data is the 'raw' from component
    assert isinstance(res.json_data, dict)
    assert "objects" in res.json_data


def test_st_canvas_resizes_background_image(monkeypatch, rgb_img):
    """
    When background_image is provided, it should be resized to canvas dimensions.
    """
    import src.patched_canvas as pc

    captured_kwargs = {}

    def fake_component_func(*args, **kwargs):
        captured_kwargs.update(kwargs)
        return None

    monkeypatch.setattr(pc, "_component_func", fake_component_func)

    pc.st_canvas(
        background_image=rgb_img,
        height=50,
        width=75,
        key="test_bg",
    )

    # backgroundImageURL should be set when background_image is provided
    assert "backgroundImageURL" in captured_kwargs
    assert captured_kwargs["backgroundImageURL"] is not None
    assert captured_kwargs["backgroundImageURL"].startswith("data:image/png;base64,")
    
    # backgroundColor should be cleared when background_image is provided
    assert captured_kwargs["backgroundColor"] == ""


def test_st_canvas_passes_drawing_mode_to_component(monkeypatch, rgb_img):
    """
    Drawing mode should be passed through to the component.
    """
    import src.patched_canvas as pc

    captured_kwargs = {}

    def fake_component_func(*args, **kwargs):
        captured_kwargs.update(kwargs)
        return None

    monkeypatch.setattr(pc, "_component_func", fake_component_func)

    pc.st_canvas(
        drawing_mode="polygon",
        height=100,
        width=100,
        key="test_mode",
    )

    assert captured_kwargs["drawingMode"] == "polygon"
    # For polygon mode, realtime update should be disabled
    assert captured_kwargs["realtimeUpdateStreamlit"] is False
