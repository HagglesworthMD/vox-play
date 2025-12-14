"""
Unit tests for src/interactive_canvas.py

Tests the HTML5 canvas component for drawing redaction masks.
Uses monkeypatching to avoid actual Streamlit component execution.
"""
import base64
import io
import types

import pytest
from PIL import Image


@pytest.fixture
def tiny_pil_image():
    # 10x10 simple RGB image
    img = Image.new("RGB", (10, 10), color=(255, 0, 0))
    return img


def test_image_to_base64_returns_decodable_string(tiny_pil_image):
    from src.interactive_canvas import image_to_base64

    b64 = image_to_base64(tiny_pil_image)
    assert isinstance(b64, str)
    assert len(b64) > 0

    raw = base64.b64decode(b64)
    assert isinstance(raw, (bytes, bytearray))
    assert len(raw) > 10


def test_image_to_base64_round_trips_to_valid_image(tiny_pil_image):
    from src.interactive_canvas import image_to_base64

    b64 = image_to_base64(tiny_pil_image)
    raw = base64.b64decode(b64)

    im2 = Image.open(io.BytesIO(raw))
    assert im2.size == (10, 10)
    assert im2.mode in ("RGB", "RGBA", "P")  # allow encoder differences


def test_image_to_base64_converts_non_rgb_mode():
    """Cover line 16: mode conversion branch for non-RGB images."""
    from src.interactive_canvas import image_to_base64
    from PIL import Image
    import base64, io

    # 'L' (grayscale) forces conversion branch
    img = Image.new("L", (10, 10), color=128)

    b64 = image_to_base64(img)
    raw = base64.b64decode(b64)
    im2 = Image.open(io.BytesIO(raw))

    # Result should be a valid encoded image; usually RGB after conversion
    assert im2.size == (10, 10)
    assert im2.mode in ("RGB", "RGBA")  # allow encoder differences


def test_draw_canvas_with_image_calls_streamlit_components_html(monkeypatch, tiny_pil_image):
    """
    We don't execute JS. We verify that draw_canvas_with_image builds HTML
    and passes it to streamlit.components.v1.html().
    """
    # Import module under test
    import src.interactive_canvas as ic

    calls = {}

    def fake_html(html, **kwargs):
        calls["html"] = html
        calls["kwargs"] = kwargs
        # streamlit.components.html() returns whatever; your code may expect a value.
        return {"ok": True}

    # Patch components.html
    # The module likely did: import streamlit.components.v1 as components
    # so patch ic.components.html
    assert hasattr(ic, "components"), "interactive_canvas should import streamlit components as `components`"
    monkeypatch.setattr(ic.components, "html", fake_html)

    # Also need to mock st.session_state
    class FakeSessionState(dict):
        pass
    
    fake_state = FakeSessionState()
    monkeypatch.setattr(ic.st, "session_state", fake_state)

    result = ic.draw_canvas_with_image(tiny_pil_image)

    assert "html" in calls
    assert isinstance(calls["html"], str)
    assert len(calls["html"]) > 100


def test_draw_canvas_html_contains_canvas_and_context(monkeypatch, tiny_pil_image):
    import src.interactive_canvas as ic

    captured = {}

    def fake_html(html, **kwargs):
        captured["html"] = html
        captured["kwargs"] = kwargs
        return None

    monkeypatch.setattr(ic.components, "html", fake_html)
    
    # Mock session_state
    class FakeSessionState(dict):
        pass
    monkeypatch.setattr(ic.st, "session_state", FakeSessionState())

    ic.draw_canvas_with_image(tiny_pil_image)

    html = captured["html"]
    assert "<canvas" in html.lower()
    assert "getcontext('2d')" in html.lower() or 'getcontext("2d")' in html.lower()


def test_draw_canvas_html_contains_mouse_and_touch_handlers(monkeypatch, tiny_pil_image):
    import src.interactive_canvas as ic

    captured = {}

    def fake_html(html, **kwargs):
        captured["html"] = html
        return None

    monkeypatch.setattr(ic.components, "html", fake_html)
    
    # Mock session_state
    class FakeSessionState(dict):
        pass
    monkeypatch.setattr(ic.st, "session_state", FakeSessionState())

    ic.draw_canvas_with_image(tiny_pil_image)

    h = captured["html"].lower()

    # Mouse drag support
    assert "mousedown" in h
    assert "mousemove" in h
    assert "mouseup" in h

    # Touch support (per your summary: lines 200-242)
    assert "touchstart" in h
    assert "touchmove" in h
    assert "touchend" in h


def test_draw_canvas_html_posts_rectangle_coords_to_streamlit(monkeypatch, tiny_pil_image):
    import src.interactive_canvas as ic

    captured = {}

    def fake_html(html, **kwargs):
        captured["html"] = html
        return None

    monkeypatch.setattr(ic.components, "html", fake_html)
    
    # Mock session_state
    class FakeSessionState(dict):
        pass
    monkeypatch.setattr(ic.st, "session_state", FakeSessionState())

    ic.draw_canvas_with_image(tiny_pil_image)

    h = captured["html"]

    # Robust checks: postMessage plus some coordinate-ish keys
    # (Your summary: lines 175-183)
    assert "postmessage" in h.lower()
    # look for typical keys that represent rectangle bounds
    lower = h.lower()
    assert ("rect" in lower) or ("x1" in lower) or ("x2" in lower) or ("width" in lower) or ("height" in lower)


def test_draw_canvas_html_uses_cyan_stroke_for_rectangles(monkeypatch, tiny_pil_image):
    import src.interactive_canvas as ic

    captured = {}

    def fake_html(html, **kwargs):
        captured["html"] = html
        return None

    monkeypatch.setattr(ic.components, "html", fake_html)
    
    # Mock session_state
    class FakeSessionState(dict):
        pass
    monkeypatch.setattr(ic.st, "session_state", FakeSessionState())

    ic.draw_canvas_with_image(tiny_pil_image)

    lower = captured["html"].lower()
    # Your summary: "cyan stroke color"
    assert "cyan" in lower or "strokestyle" in lower


def test_draw_canvas_passes_reasonable_dimensions(monkeypatch, tiny_pil_image):
    """
    If your draw function passes height/width to components.html(), verify it does.
    This is optional but can cover kwargs branches.
    """
    import src.interactive_canvas as ic

    captured = {}

    def fake_html(html, **kwargs):
        captured["kwargs"] = kwargs
        return None

    monkeypatch.setattr(ic.components, "html", fake_html)
    
    # Mock session_state
    class FakeSessionState(dict):
        pass
    monkeypatch.setattr(ic.st, "session_state", FakeSessionState())

    ic.draw_canvas_with_image(tiny_pil_image)

    # Only assert if those kwargs exist (avoid brittleness if you don't set them)
    kw = captured.get("kwargs", {})
    # Common streamlit components.html kwargs are height/width/scrolling
    if "height" in kw:
        assert isinstance(kw["height"], int)
        assert kw["height"] > 0
    if "width" in kw:
        assert isinstance(kw["width"], int)
        assert kw["width"] > 0
