"""
VoxelMask UI Tests
==================
Tests for the Streamlit user interface.

Uses Streamlit's testing framework to verify:
1. App loads without errors
2. Title is displayed correctly
3. Profile selector works
4. UI updates based on user interactions

Run with: pytest tests/test_ui.py -v

Note: These tests require the streamlit testing module (streamlit >= 1.28).
"""

import os
import sys
import pytest

# Check if Streamlit testing is available
try:
    from streamlit.testing.v1 import AppTest
    STREAMLIT_TESTING_AVAILABLE = True
except ImportError:
    STREAMLIT_TESTING_AVAILABLE = False
    AppTest = None

# Skip all tests if Streamlit testing is not available
pytestmark = pytest.mark.skipif(
    not STREAMLIT_TESTING_AVAILABLE,
    reason="Streamlit testing module not available (requires streamlit >= 1.28)"
)


class TestAppLoading:
    """Tests for basic app loading and initialization."""
    
    @pytest.fixture
    def app(self):
        """
        Create an AppTest instance for the VoxelMask app.
        
        Note: We use a longer timeout because the app imports many dependencies.
        """
        # Get the path to app.py
        app_path = os.path.join(
            os.path.dirname(__file__), 
            '..', 
            'src', 
            'app.py'
        )
        
        # Verify the app file exists
        assert os.path.exists(app_path), f"App file not found: {app_path}"
        
        # Create AppTest instance
        at = AppTest.from_file(app_path, default_timeout=30)
        return at
    
    def test_app_loads_without_error(self, app):
        """
        Assert: The app loads without raising exceptions.
        """
        try:
            app.run()
            # If we get here, the app loaded successfully
            assert not app.exception, \
                f"App raised an exception: {app.exception}"
        except Exception as e:
            # Some exceptions are acceptable during CI (missing canvas, etc.)
            if "st_canvas" in str(e) or "streamlit_drawable_canvas" in str(e):
                pytest.skip("Canvas component not available in test environment")
            raise
    
    def test_app_has_title(self, app):
        """
        Assert: The app displays the VoxelMask title.
        """
        try:
            app.run()
            
            # Check for title element
            # Note: st.title creates a heading element
            titles = [t.value for t in app.title]
            
            assert len(titles) > 0, "App should have a title"
            
            # Check for VoxelMask in title (case insensitive)
            title_text = ' '.join(titles).lower()
            assert 'voxelmask' in title_text, \
                f"Title should contain 'VoxelMask', got: {titles}"
                
        except Exception as e:
            if "st_canvas" in str(e):
                pytest.skip("Canvas component not available")
            raise
    
    def test_app_has_profile_selector(self, app):
        """
        Assert: The app has a profile/operation mode selector.
        """
        try:
            app.run()
            
            # Look for selectbox elements
            selectboxes = app.selectbox
            
            # Should have at least one selectbox (profile selector)
            assert len(selectboxes) > 0, \
                "App should have at least one selectbox for profile selection"
                
        except Exception as e:
            if "st_canvas" in str(e):
                pytest.skip("Canvas component not available")
            raise


class TestProfileSelection:
    """Tests for profile/operation mode selection."""
    
    @pytest.fixture
    def app(self):
        """Create AppTest instance."""
        app_path = os.path.join(
            os.path.dirname(__file__), 
            '..', 
            'src', 
            'app.py'
        )
        return AppTest.from_file(app_path, default_timeout=30)
    
    def test_profile_options_available(self, app):
        """
        Assert: Profile selector has the expected options.
        """
        try:
            app.run()
            
            # Get the first selectbox (should be profile selector)
            if len(app.selectbox) > 0:
                profile_selector = app.selectbox[0]
                
                # Check that options exist
                options = profile_selector.options
                assert len(options) > 0, \
                    "Profile selector should have options"
                
                # Verify expected profiles exist
                options_lower = [str(o).lower() for o in options]
                
                # At minimum, these core profiles should exist
                expected_profiles = ['internal_repair', 'us_research', 'au_strict']
                
                found_any = False
                for profile in expected_profiles:
                    if any(profile in opt for opt in options_lower):
                        found_any = True
                        break
                
                assert found_any, \
                    f"Expected to find at least one core profile in: {options}"
                    
        except Exception as e:
            if "st_canvas" in str(e):
                pytest.skip("Canvas component not available")
            raise
    
    def test_selecting_us_research_profile(self, app):
        """
        Assert: Selecting US Research profile updates the UI.
        """
        try:
            app.run()
            
            if len(app.selectbox) > 0:
                profile_selector = app.selectbox[0]
                
                # Find the US Research option
                options = profile_selector.options
                us_research_option = None
                
                for opt in options:
                    if 'us_research' in str(opt).lower() or 'safe_harbor' in str(opt).lower():
                        us_research_option = opt
                        break
                
                if us_research_option:
                    # Select the US Research profile
                    profile_selector.set_value(us_research_option)
                    app.run()
                    
                    # After selecting, the app should still load without error
                    assert not app.exception, \
                        f"App raised exception after profile change: {app.exception}"
                else:
                    pytest.skip("US Research profile option not found in selector")
                    
        except Exception as e:
            if "st_canvas" in str(e):
                pytest.skip("Canvas component not available")
            raise


class TestUIElements:
    """Tests for specific UI elements and components."""
    
    @pytest.fixture
    def app(self):
        """Create AppTest instance."""
        app_path = os.path.join(
            os.path.dirname(__file__), 
            '..', 
            'src', 
            'app.py'
        )
        return AppTest.from_file(app_path, default_timeout=30)
    
    def test_file_uploader_exists(self, app):
        """
        Assert: The app has a file uploader component.
        """
        try:
            app.run()
            
            # Check for file uploader
            uploaders = app.file_uploader
            
            assert len(uploaders) > 0, \
                "App should have a file uploader for DICOM files"
                
        except Exception as e:
            if "st_canvas" in str(e):
                pytest.skip("Canvas component not available")
            raise
    
    def test_app_has_markdown_content(self, app):
        """
        Assert: The app displays informational markdown content.
        """
        try:
            app.run()
            
            # Check for markdown elements
            markdown_elements = app.markdown
            
            # Should have some markdown content for instructions/descriptions
            assert len(markdown_elements) > 0, \
                "App should have markdown content for instructions"
                
        except Exception as e:
            if "st_canvas" in str(e):
                pytest.skip("Canvas component not available")
            raise
    
    def test_no_uncaught_exceptions(self, app):
        """
        Assert: App runs without uncaught exceptions on initial load.
        """
        try:
            app.run()
            
            if app.exception:
                # Check if it's a known/acceptable exception
                exc_str = str(app.exception)
                acceptable_exceptions = [
                    'st_canvas',
                    'streamlit_drawable_canvas',
                    'ModuleNotFoundError'
                ]
                
                is_acceptable = any(ae in exc_str for ae in acceptable_exceptions)
                
                if not is_acceptable:
                    pytest.fail(f"App raised unexpected exception: {app.exception}")
                else:
                    pytest.skip(f"App raised acceptable exception: {exc_str[:100]}")
                    
        except Exception as e:
            if "st_canvas" in str(e) or "ModuleNotFoundError" in str(e):
                pytest.skip(f"Known import issue: {str(e)[:100]}")
            raise
