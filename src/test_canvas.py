"""Minimal test app for canvas background image"""
import streamlit as st
import numpy as np
from PIL import Image
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import patched canvas
from patched_canvas import st_canvas

st.title("Canvas Background Test")

# Create a colorful test image (NOT black)
test_array = np.zeros((300, 400, 3), dtype=np.uint8)
# Red gradient on left
test_array[:, :100, 0] = 255
# Green gradient in middle  
test_array[:, 100:200, 1] = 255
# Blue gradient on right
test_array[:, 200:300, 2] = 255
# White on far right
test_array[:, 300:, :] = 255

# Add some pattern
for i in range(0, 300, 20):
    test_array[i:i+10, :, :] = 128

test_img = Image.fromarray(test_array, mode='RGB')

st.write(f"Test image mode: {test_img.mode}, size: {test_img.size}")
st.image(test_img, caption="This is what the canvas background should show")

st.write("---")
st.write("Canvas with background image:")

canvas_result = st_canvas(
    fill_color="rgba(0, 255, 255, 0.3)",
    stroke_width=3,
    stroke_color="#FF0000",
    background_image=test_img,
    drawing_mode="rect",
    height=300,
    width=400,
    key="test_canvas",
    display_toolbar=True,
)

if canvas_result.json_data:
    st.write("Canvas data:", canvas_result.json_data)
