
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
        
        # 512*512*2 bytes = 0.5 MB << 300 MB
        self.assertTrue(should_render_pixels(ds))

    def test_should_render_pixels_large(self):
        """Test that a large dataset fails the guard."""
        ds = Dataset()
        ds.Rows = 1024
        ds.Columns = 1024
        ds.BitsAllocated = 16
        ds.SamplesPerPixel = 1
        
        # 1024*1024*2 = 2 MB per frame
        # Need > 300 MB -> > 150 frames
        ds.NumberOfFrames = 200 
        
        # 200 * 2 MB = 400 MB > 300 MB
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

if __name__ == '__main__':
    unittest.main()
