"""Test script to check DICOM to PIL conversion"""
import sys
sys.path.insert(0, 'src')

import os
import numpy as np
import pydicom
from PIL import Image

# Find any US DICOM files in the project
test_files = []
for root, dirs, files in os.walk('.'):
    for f in files:
        if f.endswith('.dcm'):
            filepath = os.path.join(root, f)
            try:
                ds = pydicom.dcmread(filepath, stop_before_pixels=True, force=True)
                if hasattr(ds, 'Modality') and ds.Modality == 'US':
                    test_files.append(filepath)
            except:
                pass

if not test_files:
    print("No US DICOM files found. Looking for any DICOM...")
    for root, dirs, files in os.walk('.'):
        for f in files:
            if f.endswith('.dcm'):
                test_files.append(os.path.join(root, f))
                break
        if test_files:
            break

if test_files:
    print(f"Testing with: {test_files[0]}")
    
    # Load and process
    ds = pydicom.dcmread(test_files[0], force=True)
    if not hasattr(ds, 'file_meta') or not hasattr(ds.file_meta, 'TransferSyntaxUID'):
        ds.file_meta.TransferSyntaxUID = pydicom.uid.ImplicitVRLittleEndian
    
    try:
        ds.decompress()
    except:
        pass
    
    arr = ds.pixel_array
    print(f"Pixel array shape: {arr.shape}, dtype: {arr.dtype}")
    print(f"Pixel array min: {arr.min()}, max: {arr.max()}")
    
    # Get single frame
    if arr.ndim == 4:
        frame = arr[0]
    elif arr.ndim == 3 and arr.shape[2] not in (3, 4):
        frame = arr[0]
    else:
        frame = arr
    
    print(f"Frame shape: {frame.shape}, dtype: {frame.dtype}")
    print(f"Frame min: {frame.min()}, max: {frame.max()}")
    
    # Normalize to uint8
    if frame.max() > frame.min():
        frame_norm = ((frame - frame.min()) / (frame.max() - frame.min()) * 255).astype(np.uint8)
    else:
        frame_norm = np.zeros_like(frame, dtype=np.uint8)
    
    print(f"Normalized min: {frame_norm.min()}, max: {frame_norm.max()}")
    
    # Convert to RGB
    if frame_norm.ndim == 2:
        frame_rgb = np.stack([frame_norm]*3, axis=-1)
    else:
        frame_rgb = frame_norm
    
    print(f"RGB shape: {frame_rgb.shape}")
    
    # Create PIL image
    pil_img = Image.fromarray(frame_rgb, mode='RGB')
    print(f"PIL Image mode: {pil_img.mode}, size: {pil_img.size}")
    
    # Save to test
    pil_img.save("test_dicom_output.png")
    print(f"Saved test image to test_dicom_output.png")
    print("SUCCESS! Check the image file to see if it looks correct.")
else:
    print("No DICOM files found in project")
