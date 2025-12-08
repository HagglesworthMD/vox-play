"""
Test script to verify NIfTI dependencies are installed correctly.
"""
import sys

def test_imports():
    """Test all NIfTI-related imports."""
    print("Testing NIfTI dependencies...")
    
    # Test dicom2nifti
    try:
        import dicom2nifti
        print(f"  [OK] dicom2nifti: {dicom2nifti.__version__ if hasattr(dicom2nifti, '__version__') else 'installed'}")
    except ImportError as e:
        print(f"  [FAIL] dicom2nifti: {e}")
        return False
    
    # Test nibabel
    try:
        import nibabel
        print(f"  [OK] nibabel: {nibabel.__version__}")
    except ImportError as e:
        print(f"  [FAIL] nibabel: {e}")
        return False
    
    # Test scipy
    try:
        import scipy
        print(f"  [OK] scipy: {scipy.__version__}")
    except ImportError as e:
        print(f"  [FAIL] scipy: {e}")
        return False
    
    # Test our custom handler
    try:
        sys.path.insert(0, 'src')
        from nifti_handler import convert_dataset_to_nifti, check_dicom2nifti_available
        available = check_dicom2nifti_available()
        print(f"  [OK] nifti_handler: dicom2nifti available = {available}")
    except ImportError as e:
        print(f"  [FAIL] nifti_handler: {e}")
        return False
    
    print("\nSUCCESS: All NIfTI dependencies installed correctly!")
    return True

if __name__ == "__main__":
    success = test_imports()
    sys.exit(0 if success else 1)
