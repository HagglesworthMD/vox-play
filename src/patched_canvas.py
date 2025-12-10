"""
Patched version of streamlit-drawable-canvas that works with newer Streamlit versions.
The original library uses st_image.image_to_url which was removed in newer versions.
This patch uses base64 encoding instead.
"""
import base64
import io
import os
from dataclasses import dataclass
from hashlib import md5

import numpy as np
import streamlit as st
import streamlit.components.v1 as components
from PIL import Image


# Point to the original library's frontend build
parent_dir = os.path.dirname(os.path.abspath(__file__))
# Look for the canvas in site-packages
import streamlit_drawable_canvas
canvas_dir = os.path.dirname(streamlit_drawable_canvas.__file__)
build_dir = os.path.join(canvas_dir, "frontend/build")
_component_func = components.declare_component("st_canvas", path=build_dir)


@dataclass
class CanvasResult:
    """Dataclass to store output of React Component"""
    image_data: np.array = None
    json_data: dict = None


def _data_url_to_image(data_url: str) -> Image:
    """Convert DataURL string to the image."""
    _, _data_url = data_url.split(";base64,")
    return Image.open(io.BytesIO(base64.b64decode(_data_url)))


def _resize_img(img: Image, new_height: int = 700, new_width: int = 700) -> Image:
    """Resize the image to the provided resolution."""
    h_ratio = new_height / img.height
    w_ratio = new_width / img.width
    img = img.resize((int(img.width * w_ratio), int(img.height * h_ratio)))
    return img


def _image_to_data_url(img: Image) -> str:
    """Convert PIL Image to base64 data URL - replacement for removed st_image.image_to_url"""
    # DEBUG: Print original mode
    print(f"[DEBUG patched_canvas] Input image mode = {img.mode}, size = {img.size}")
    
    # Ensure image is in RGB mode for proper display
    if img.mode == 'RGBA':
        # Create white background for transparency
        background = Image.new('RGB', img.size, (255, 255, 255))
        background.paste(img, mask=img.split()[3])  # 3 is the alpha channel
        img = background
        print(f"[DEBUG patched_canvas] Converted RGBA to RGB")
    elif img.mode in ('L', 'LA', 'I', 'F'):
        # Convert grayscale modes to RGB (common for ultrasound DICOM)
        print(f"[DEBUG patched_canvas] Converting grayscale {img.mode} to RGB...")
        img = img.convert('RGB')
        print(f"[DEBUG patched_canvas] After conversion: mode = {img.mode}")
    elif img.mode != 'RGB':
        print(f"[DEBUG patched_canvas] Converting {img.mode} to RGB...")
        img = img.convert('RGB')
        print(f"[DEBUG patched_canvas] After conversion: mode = {img.mode}")
    
    print(f"[DEBUG patched_canvas] Final image mode before encoding: {img.mode}")
    
    buffered = io.BytesIO()
    # PNG doesn't use quality param, use compress_level instead
    img.save(buffered, format="PNG", compress_level=6, optimize=False)
    img_str = base64.b64encode(buffered.getvalue()).decode()
    data_url = f"data:image/png;base64,{img_str}"
    print(f"[DEBUG patched_canvas] Generated data URL of length: {len(data_url)}")
    return data_url


def st_canvas(
    fill_color: str = "#eee",
    stroke_width: int = 20,
    stroke_color: str = "black",
    background_color: str = "",
    background_image: Image = None,
    update_streamlit: bool = True,
    height: int = 400,
    width: int = 600,
    drawing_mode: str = "freedraw",
    initial_drawing: dict = None,
    display_toolbar: bool = True,
    point_display_radius: int = 3,
    key=None,
) -> CanvasResult:
    """Create a drawing canvas in Streamlit app."""
    
    # Resize background_image to canvas dimensions by default
    background_image_url = None
    if background_image:
        print(f"[DEBUG patched_canvas] st_canvas: Received background image, mode={background_image.mode}, size={background_image.size}")
        background_image = _resize_img(background_image, height, width)
        print(f"[DEBUG patched_canvas] st_canvas: After resize, size={background_image.size}")
        # Use base64 data URL instead of deprecated st_image.image_to_url
        background_image_url = _image_to_data_url(background_image)
        background_color = ""
    else:
        print(f"[DEBUG patched_canvas] st_canvas: No background image provided")

    # Clean initial drawing, override its background color
    initial_drawing = (
        {"version": "4.4.0"} if initial_drawing is None else initial_drawing
    )
    initial_drawing["background"] = background_color

    # DEBUG: Confirm what we're passing to the component
    print(f"[DEBUG patched_canvas] Calling component with:")
    print(f"  - backgroundImageURL: {'SET (len=' + str(len(background_image_url)) + ')' if background_image_url else 'None'}")
    print(f"  - backgroundColor: '{background_color}'")
    print(f"  - canvasHeight: {height}, canvasWidth: {width}")

    component_value = _component_func(
        fillColor=fill_color,
        strokeWidth=stroke_width,
        strokeColor=stroke_color,
        backgroundColor=background_color,
        backgroundImageURL=background_image_url,
        realtimeUpdateStreamlit=update_streamlit and (drawing_mode != "polygon"),
        canvasHeight=height,
        canvasWidth=width,
        drawingMode=drawing_mode,
        initialDrawing=initial_drawing,
        displayToolbar=display_toolbar,
        displayRadius=point_display_radius,
        key=key,
        default=None,
    )
    if component_value is None:
        return CanvasResult()

    return CanvasResult(
        np.asarray(_data_url_to_image(component_value["data"])),
        component_value["raw"],
    )
