
import unittest
import pydicom
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.uid import ImplicitVRLittleEndian
from src.utils import should_render_pixels

class TestMemoryGuard(unittest.TestCase):
    def test_should_render_pixels_small(self):
        """Test that a small dataset passes the guard."""
        ds = Dataset()
        ds.Rows = 512
        ds.Columns = 512
        ds.NumberOfFrames = 1
        ds.BitsAllocated = 16
        ds.SamplesPerPixel = 1
        
        # 512*512*2 bytes = 0.5 MB << 150 MB
        self.assertTrue(should_render_pixels(ds))

    def test_should_render_pixels_large(self):
        """Test that a large dataset fails the guard."""
        ds = Dataset()
        ds.Rows = 1024
        ds.Columns = 1024
        ds.BitsAllocated = 16
        ds.SamplesPerPixel = 1
        
        # 1024*1024*2 = 2 MB per frame
        # Need > 150 MB -> > 75 frames
        ds.NumberOfFrames = 100 
        
        # 100 * 2 MB = 200 MB > 150 MB
        self.assertFalse(should_render_pixels(ds))

    def test_should_render_pixels_custom_limit(self):
        """Test that custom limits work."""
        ds = Dataset()
        ds.Rows = 100
        ds.Columns = 100
        ds.BitsAllocated = 8
        ds.SamplesPerPixel = 1
        ds.NumberOfFrames = 1
        
        # 10kb
        
        self.assertFalse(should_render_pixels(ds, max_raw_pixel_bytes=5000))
        self.assertTrue(should_render_pixels(ds, max_raw_pixel_bytes=20000))


class TestFileSizePreFlight(unittest.TestCase):
    """Tests for file-size pre-flight guard (Phase 13)."""
    
    def test_check_file_size_limit_small_file(self):
        """Test that small files pass the pre-flight check."""
        import tempfile
        import os
        from src.utils import check_file_size_limit
        
        # Create a small temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.dcm') as f:
            f.write(b'x' * 1000)  # 1 KB
            temp_path = f.name
        
        try:
            is_safe, size = check_file_size_limit(temp_path, max_bytes=50_000_000)
            self.assertTrue(is_safe)
            self.assertEqual(size, 1000)
        finally:
            os.unlink(temp_path)
    
    def test_check_file_size_limit_large_file(self):
        """Test that large files fail the pre-flight check."""
        import tempfile
        import os
        from src.utils import check_file_size_limit
        
        # Create a file larger than limit
        with tempfile.NamedTemporaryFile(delete=False, suffix='.dcm') as f:
            f.write(b'x' * 100_000)  # 100 KB
            temp_path = f.name
        
        try:
            is_safe, size = check_file_size_limit(temp_path, max_bytes=50_000)  # 50 KB limit
            self.assertFalse(is_safe)
            self.assertEqual(size, 100_000)
        finally:
            os.unlink(temp_path)
    
    def test_require_file_size_limit_raises(self):
        """Test that require_file_size_limit raises MemoryError for large files."""
        import tempfile
        import os
        from src.utils import require_file_size_limit
        
        # Create a file larger than limit
        with tempfile.NamedTemporaryFile(delete=False, suffix='.dcm') as f:
            f.write(b'x' * 100_000)  # 100 KB
            temp_path = f.name
        
        try:
            with self.assertRaises(MemoryError) as context:
                require_file_size_limit(temp_path, max_bytes=50_000, context="test")
            
            self.assertIn("too large", str(context.exception))
            self.assertIn("test", str(context.exception))
        finally:
            os.unlink(temp_path)


if __name__ == '__main__':
    unittest.main()
