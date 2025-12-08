"""Test the new HTML canvas implementation"""
import streamlit as st
import numpy as np
from PIL import Image
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import new HTML canvas
from html_canvas import st_canvas

st.title("HTML Canvas Test")

# Create a colorful test image
test_array = np.zeros((300, 400, 3), dtype=np.uint8)
test_array[:, :100, 0] = 255  # Red
test_array[:, 100:200, 1] = 255  # Green
test_array[:, 200:300, 2] = 255  # Blue
test_array[:, 300:, :] = 255  # White

# Add pattern
for i in range(0, 300, 20):
    test_array[i:i+10, :, :] = 128

test_img = Image.fromarray(test_array, mode='RGB')

st.write(f"Test image mode: {test_img.mode}, size: {test_img.size}")
st.image(test_img, caption="Reference (what canvas background should show)")

st.write("---")
st.write("**Canvas with background image:**")
st.caption("Click and drag to draw a rectangle")

canvas_result = st_canvas(
    background_image=test_img,
    stroke_color="#00FFFF",
    stroke_width=3,
    fill_color="rgba(0, 255, 255, 0.3)",
    height=300,
    width=400,
    drawing_mode="rect",
    key="test_canvas",
)

if canvas_result.json_data and canvas_result.json_data.get("objects"):
    st.success(f"Rectangles drawn: {canvas_result.json_data['objects']}")
