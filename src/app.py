"""
VoxelMask - Streamlit GUI
Clean rewrite with 5 tabs including Interactive Redaction.
"""


# ==============================================================================
# VOXELMASK — STREAMLIT BOOTSTRAP (ANTI-GRAVITY SAFE)
# This block MUST be the first Streamlit interaction in the process.
# ==============================================================================

import streamlit as st

# ------------------------------------------------------------------------------
# HARD LOCK PAGE CONFIG
# ------------------------------------------------------------------------------
st.set_page_config(
    page_title="VoxelMask — Imaging De-Identification (Pilot Mode)",
    page_icon="🩺",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ------------------------------------------------------------------------------
# SIDEBAR & LAYOUT KILL SWITCH
# (Survives Streamlit >=1.30, reruns, hot reloads, imported modules)
# ------------------------------------------------------------------------------
st.markdown(
    """
    <style>
        /* --- Kill Streamlit Sidebar Completely --- */
        section[data-testid="stSidebar"] {
            display: none !important;
            visibility: hidden !important;
            width: 0 !important;
        }

        /* --- Kill the collapse / expand button --- */
        [data-testid="collapsedControl"] {
            display: none !important;
            visibility: hidden !important;
        }

        /* --- Remove any residual left padding --- */
        .stApp {
            margin-left: 0 !important;
        }

        /* --- Optional: tighten top spacing --- */
        header { visibility: hidden; height: 0; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ==============================================================================
# BUILD FINGERPRINT (logged on startup, no UI impact)
# ==============================================================================
import logging, subprocess
logging.info(
    "VoxelMask build %s",
    subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True).strip()
)

# ==============================================================================
# AFTER THIS POINT:
# - You may import other modules
# - You may define helper functions
# - You may build UI using columns/containers
# - NEVER use st. sidebar.*
# ==============================================================================
# ==============================================================================
# GUARD: PREVENT SIDEBAR USAGE (RUNTIME CHECK)
# ==============================================================================
import inspect

# Guard against accidental sidebar usage
# We verify the file source to ensure no sidebar calls slip in
src_content = open(__file__, "r", encoding="utf-8").read()
search_term = "st." + "sidebar"  # Split string to avoid self-match

if search_term in src_content:
    offenders = []
    for i, line in enumerate(open(__file__, "r", encoding="utf-8")):
        if search_term in line:
            # Ignore this guard block and the bootstrap warning
            if "NEVER use st. sidebar" in line: continue
            if "st." + "sidebar" in line: continue  # Ignore self
            
            offenders.append((i + 1, line.rstrip()))
            
    if offenders:
        raise RuntimeError(f"st." + f"sidebar usage detected in app.py: {offenders}")



import hashlib
import json
import os
import re
import sys
import shutil
import tempfile
import time
import zipfile
from datetime import date, datetime
from pathlib import Path
from typing import Optional, List, Dict

import cv2
import numpy as np
import pydicom
import uuid
import streamlit as st
from PIL import Image

# Use patched canvas that works with newer Streamlit versions
try:
    from patched_canvas import st_canvas
    CANVAS_AVAILABLE = True
except ImportError:
    try:
        from streamlit_drawable_canvas import st_canvas
        CANVAS_AVAILABLE = True
    except ImportError:
        CANVAS_AVAILABLE = False
        st_canvas = None

# Add src directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from run_on_dicom import process_dicom
from audit_manager import AuditLogger, embed_compliance_tags, AtomicScrubOperation
# Import from standalone audit.py module (not the audit/ package)
import importlib.util
_audit_spec = importlib.util.spec_from_file_location("audit_module", os.path.join(os.path.dirname(__file__), "audit.py"))
_audit_module = importlib.util.module_from_spec(_audit_spec)
_audit_spec.loader.exec_module(_audit_module)
generate_audit_receipt = _audit_module.generate_audit_receipt
from research_mode.anonymizer import DicomAnonymizer, AnonymizationConfig
from interactive_canvas import draw_canvas_with_image
from compliance_engine import DicomComplianceManager
from utils import should_render_pixels  # Memory guard
from nifti_handler import NiftiConverter, convert_dataset_to_nifti, generate_nifti_readme, generate_fallback_warning_file, check_dicom2nifti_available
from foi_engine import FOIEngine, process_foi_request, exclude_scanned_documents
from pdf_reporter import PDFReporter, create_report
from review_session import ReviewSession, ReviewRegion, RegionSource, RegionAction, preflight_scan_dataset
from decision_trace import DecisionTraceCollector, DecisionTraceWriter, record_region_decisions
from phase5a_ui_semantics import RegionSemantics  # Phase 5A: Presentation-only UX semantics
from selection_scope import SelectionScope, ObjectCategory, classify_object, should_include_object, get_category_label, generate_scope_audit_block, generate_scope_json  # Phase 6: Explicit selection semantics
from viewer_state import ViewerStudyState, build_viewer_state, ViewerOrderingMethod, SeriesOrderingMethod, get_instance_ordering_label, get_series_ordering_label  # Phase 6: Viewer UX
from export.viewer_index import generate_viewer_index  # Phase 6: HTML export viewer
from run_context import generate_run_id, build_run_paths, ensure_run_dirs  # Phase 8: Operational hardening
from preflight import run_preflight, raise_if_failed, PreflightError  # Phase 8: Startup gate
from evidence_capture import build_run_receipt, write_run_receipt, assert_phi_sterile  # Phase 8: Evidence capture
from session_state import reset_run_state, RUN_ID_KEY  # Phase 12: Centralized run state
from run_status import update_run_status  # Phase 8: Fail-safe completion

# Define base directory for dynamic path construction
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 12: RUN-SCOPED VIEWER CACHE
# 
# Ensures viewer file paths survive the entire review session.
# Uses content-hash filenames for deterministic file mapping.
# Files are written to runs/<run_id>/viewer_cache/ instead of /tmp/.
# ═══════════════════════════════════════════════════════════════════════════════

def _version_viewer_html(html_content: str, version_stamp: str) -> str:
    """
    Inject cache-busting version query strings into viewer.html asset references.
    
    Phase 12: Prevents browser caching issues when viewer assets are updated.
    Each run gets a unique version stamp so changes are picked up immediately.
    
    Args:
        html_content: Original viewer.html content
        version_stamp: Version string (e.g. Unix timestamp or run_id)
        
    Returns:
        HTML with versioned asset URLs: viewer.css?v=<stamp>
    """
    import re
    
    # Assets to version (CSS and JS files)
    versioned = html_content
    versioned = re.sub(r'href="viewer\.css"', f'href="viewer.css?v={version_stamp}"', versioned)
    versioned = re.sub(r'src="viewer\.js"', f'src="viewer.js?v={version_stamp}"', versioned)
    versioned = re.sub(r'src="viewer_index\.js"', f'src="viewer_index.js?v={version_stamp}"', versioned)
    
    return versioned

# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 12: LOCAL VIEWER SERVER
# 
# Serves the viewer over localhost HTTP to bypass Flatpak/portal sandbox issues.
# The file:// protocol fails on Steam Deck because xdg-open + Flatpak rewrites
# access through /run/user/1000/doc/<token>/... which can't load adjacent JS.
# 
# Solution: python3 -m http.server on 127.0.0.1 serves run_root, then xdg-open
# the HTTP URL. Server is reused across button clicks via session state.
# ═══════════════════════════════════════════════════════════════════════════════

import socket
import subprocess
import atexit

# Global registry of viewer servers (survives Streamlit reruns)
_VIEWER_SERVERS: dict = {}  # {run_id: {"port": int, "process": Popen}}

def _find_free_port() -> int:
    """Find an available port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]

def _is_server_running(run_id: str) -> bool:
    """Check if a viewer server for this run is still running."""
    if run_id not in _VIEWER_SERVERS:
        return False
    proc = _VIEWER_SERVERS[run_id].get("process")
    if proc is None:
        return False
    return proc.poll() is None  # None means still running

def _start_viewer_server(run_root: str, run_id: str) -> tuple[int, str]:
    """
    Start a local HTTP server for the viewer.
    
    Args:
        run_root: Path to the run directory to serve
        run_id: Run identifier for server tracking
        
    Returns:
        Tuple of (port, viewer_url)
    """
    # Reuse existing server if running
    if _is_server_running(run_id):
        port = _VIEWER_SERVERS[run_id]["port"]
        return port, f"http://127.0.0.1:{port}/viewer/viewer.html"
    
    # Find a free port
    port = _find_free_port()
    
    # Start HTTP server as subprocess
    # Using python3 -m http.server for maximum compatibility
    proc = subprocess.Popen(
        ['python3', '-m', 'http.server', str(port), '--bind', '127.0.0.1', '--directory', run_root],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True  # Detach from parent process group
    )
    
    # Register for cleanup
    _VIEWER_SERVERS[run_id] = {"port": port, "process": proc}
    
    # Give server a moment to start
    import time
    time.sleep(0.3)
    
    return port, f"http://127.0.0.1:{port}/viewer/viewer.html"

def _stop_viewer_server(run_id: str) -> None:
    """Stop a viewer server if running."""
    if run_id in _VIEWER_SERVERS:
        proc = _VIEWER_SERVERS[run_id].get("process")
        if proc and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()
        del _VIEWER_SERVERS[run_id]

def _cleanup_all_viewer_servers() -> None:
    """Cleanup all viewer servers on exit."""
    for run_id in list(_VIEWER_SERVERS.keys()):
        _stop_viewer_server(run_id)

# Register cleanup on interpreter exit
atexit.register(_cleanup_all_viewer_servers)

def _open_viewer_via_localhost(run_root: str, run_id: str) -> tuple[bool, str]:
    """
    Open the viewer via localhost HTTP server.
    
    Phase 12 UI Hardening:
    - Serves viewer over http://127.0.0.1:<PORT>
    - Bypasses Flatpak/portal sandbox issues with file:// protocol
    - Reuses existing server for same run_id
    
    Args:
        run_root: Path to the run root directory
        run_id: Run identifier
        
    Returns:
        Tuple of (success: bool, message: str)
    """
    import sys
    from pathlib import Path
    
    # Verify viewer exists
    viewer_path = Path(run_root) / "viewer" / "viewer.html"
    if not viewer_path.exists():
        return False, "Viewer was not generated for this run. Re-process your files with 'Include HTML export viewer' enabled."
    
    try:
        # Start or reuse server
        port, viewer_url = _start_viewer_server(run_root, run_id)
        
        # Open in browser via system opener
        if sys.platform == 'linux':
            subprocess.Popen(['xdg-open', viewer_url],
                           stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)
        elif sys.platform == 'darwin':
            subprocess.Popen(['open', viewer_url],
                           stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)
        elif sys.platform == 'win32':
            subprocess.Popen(['start', '', viewer_url],
                           shell=True,
                           stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)
        else:
            return False, f"Unsupported platform: {sys.platform}"
        
        return True, f"Viewer opened: {viewer_url}"
    
    except Exception as e:
        return False, f"Could not start viewer server. Try closing other browser tabs and clicking again. ({type(e).__name__})"

def _ensure_early_run_context() -> 'RunPaths':
    """
    Ensure run context exists early (at file upload time).
    
    Creates run_id and run_paths if not already present in session state.
    This is called before file scanning to ensure viewer_cache is available.
    
    Returns:
        RunPaths object for the current session
    """
    from pathlib import Path
    
    if st.session_state.get('run_paths') is None:
        # Generate new run ID
        run_id = generate_run_id()
        st.session_state.run_id = run_id
        
        # Build paths - use downloads directory as output root
        output_root = Path(os.path.join(BASE_DIR, "downloads"))
        run_paths = build_run_paths(output_root, run_id)
        
        # Create all directories including viewer_cache
        ensure_run_dirs(run_paths)
        
        st.session_state.run_paths = run_paths
        print(f"[Phase12] Early run context created: {run_paths.run_id}")
    
    return st.session_state.run_paths


def _get_viewer_cache_path(file_buffer, run_paths: 'RunPaths') -> str:
    """
    Get a deterministic, run-scoped path for caching a viewer input file.
    
    Uses content hash to generate stable filenames that can be reliably
    referenced throughout the review session.
    
    Args:
        file_buffer: File buffer with name and getbuffer() method
        run_paths: RunPaths for the current session
        
    Returns:
        Absolute path to the cached file in viewer_cache/
    """
    import hashlib
    
    # Get file content
    content = file_buffer.getbuffer()
    
    # Generate content hash for deterministic filename
    content_hash = hashlib.sha256(content).hexdigest()[:16]
    
    # Use original filename + hash for human-readable + unique naming
    # Sanitize filename to be filesystem-safe
    safe_name = "".join(c if c.isalnum() or c in '._-' else '_' for c in file_buffer.name)
    cached_filename = f"{content_hash}_{safe_name}"
    
    # Ensure .dcm extension
    if not cached_filename.lower().endswith('.dcm'):
        cached_filename += '.dcm'
    
    cache_path = run_paths.viewer_cache / cached_filename
    
    # Write file if not already cached
    # Write file if not already cached
    if not cache_path.exists():
        # Optimization: Write directly from memoryview/buffer to avoid RAM copy
        with cache_path.open("wb") as f:
            f.write(content)
    
    return str(cache_path)


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 12: CENTRALIZED RUN STATE RESET
# 
# Single function to clear all run-scoped state. Uses explicit allowlist to
# avoid nuking user preferences (gateway_profile, selection_scope, etc.)
# Call this on: new upload, "Start New Job", or any run boundary crossing.
# ═══════════════════════════════════════════════════════════════════════════════

# reset_run_state consolidated into src/session_state.py


def get_current_run_id() -> str:
    """
    Get the current run ID, or None if no run is active.
    
    Use this to verify run identity before accessing run-scoped state.
    """
    return st.session_state.get('run_id')


def assert_run_active(context: str = "operation") -> None:
    """
    Assert that a run is currently active. Raises if not.
    
    Use at the start of any code that requires run-scoped state.
    
    Args:
        context: Description of the operation requiring active run
        
    Raises:
        RuntimeError: If no run is active
    """
    if st.session_state.get('run_id') is None:
        raise RuntimeError(f"No active run for {context}. Call _ensure_early_run_context() first.")




def analyze_dicom_context(file_path):
    """
    Analyze a DICOM file to determine its type and risk level for processing.
    
    Args:
        file_path: Path to the DICOM file
        
    Returns:
        dict: Analysis results with keys: Type, Risk, Include
    """
    try:
        ds = pydicom.dcmread(file_path, stop_before_pixels=True, force=True)
        # Add fallback for missing TransferSyntaxUID
        if not hasattr(ds, 'file_meta') or not hasattr(ds.file_meta, 'TransferSyntaxUID'):
            ds.file_meta.TransferSyntaxUID = pydicom.uid.ImplicitVRLittleEndian
        
        modality = str(getattr(ds, 'Modality', '')).upper()
        sop_class_uid = str(getattr(ds, 'SOPClassUID', ''))
        series_description = str(getattr(ds, 'SeriesDescription', '')).upper()
        
        # Determine file type
        file_type = "Image"  # Default
        
        # Check for Structured Report
        if modality == 'SR' or 'STRUCTURED REPORT' in sop_class_uid:
            file_type = "SR"
        # Check for PDF
        elif 'ENCAPSULATED PDF' in sop_class_uid.upper():
            file_type = "PDF"
        # Check for Form/Worksheet (SC/OT)
        elif modality in ['SC', 'OT']:
            file_type = "Document"
        
        # Determine risk and inclusion
        # Documents are EXCLUDED by default - user can opt-in if needed
        if file_type == "Image":
            risk = "Low"
            include = True
        elif file_type == "Document":
            risk = "Medium"  # Documents may have PHI but we can mask them
            include = False  # EXCLUDE by default - forms usually not needed
        else:
            # SR, PDF - higher risk, exclude by default
            risk = "High"
            include = False  # Exclude by default - user can opt-in if needed
            
        return {
            'Type': file_type,
            'Risk': risk,
            'Include': include
        }
        
    except Exception as e:
        # If analysis fails, assume needs review
        return {
            'Type': 'Unknown',
            'Risk': 'High',
            'Include': True  # Include by default so user can see it
        }

# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 12: SESSION STATE INITIALIZATION
# ═══════════════════════════════════════════════════════════════════════════════

def init_session_state_defaults():
    """Ensure all required session state keys exist with safe defaults."""
    ss = st.session_state

    # Core run identity
    if RUN_ID_KEY not in ss:
        ss[RUN_ID_KEY] = None
    if 'run_paths' not in ss:
        ss['run_paths'] = None

    # Processing State
    if 'processing_complete' not in ss:
        ss['processing_complete'] = False
    if 'processed_file_path' not in ss:
        ss['processed_file_path'] = None
    if 'processed_file_data' not in ss:
        ss['processed_file_data'] = None
    
    # Audit & Hashes
    if 'audit_text' not in ss:
        ss['audit_text'] = None
    if 'scrub_uuid' not in ss:
        ss['scrub_uuid'] = None
    if 'input_file_hash' not in ss:
        ss['input_file_hash'] = None
    if 'output_file_hash' not in ss:
        ss['output_file_hash'] = None

    # Review Session
    if 'phi_review_session' not in ss:
        ss['phi_review_session'] = None

    # Selection Scope (User Preference - Preserved)
    if 'selection_scope' not in ss:
        ss['selection_scope'] = SelectionScope.create_default()

    # File Handling
    if 'uploaded_dicom_files' not in ss:
        ss['uploaded_dicom_files'] = []

# Initialize defaults immediately
init_session_state_defaults()

# Global initialization of mask variables to prevent NameError
mask_left = 0
mask_top = 0
mask_width = 0
mask_height = 0
frame_w = 0
frame_h = 0

def generate_repair_filename(original_filename: str, new_patient_id: str, series_description: str) -> str:
    """
    Generate descriptive filename for internal repair with series description.
    
    Args:
        original_filename: Original DICOM filename
        new_patient_id: New patient ID (sanitized)
        series_description: Series description from DICOM metadata
        
    Returns:
        Descriptive filename in format: [PatientID]_[SeriesDescription]_[OriginalName]_CORRECTED.dcm
    """
    # Sanitize patient ID (remove special chars, keep alphanumeric)
    sanitized_patient_id = re.sub(r'[^a-zA-Z0-9]', '', new_patient_id)
    
    # Sanitize series description
    # Remove special characters, replace spaces with underscores
    if series_description and series_description != "Scan":
        sanitized_series = re.sub(r'[^a-zA-Z0-9\s]', '', series_description)  # Keep spaces temporarily
        sanitized_series = re.sub(r'\s+', '_', sanitized_series.strip())  # Replace spaces with underscores
        sanitized_series = re.sub(r'_+', '_', sanitized_series)  # Replace multiple underscores with single
        sanitized_series = sanitized_series.strip('_')  # Remove leading/trailing underscores
    else:
        sanitized_series = "Scan"
    
    # Get original filename without extension
    original_base = original_filename.rsplit('.', 1)[0]
    
    # Construct hybrid filename
    descriptive_name = f"{sanitized_patient_id}_{sanitized_series}_{original_base}_CORRECTED.dcm"
    
    return descriptive_name

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════
PRESETS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "presets.json")
try:
    with open(PRESETS_PATH, "r") as f:
        MACHINE_PRESETS = json.load(f)
except Exception:
    MACHINE_PRESETS = {"Generic (Top Bar)": {"top": 0.0, "left": 0.0, "width": 1.0, "height": 0.15}}

# ═══════════════════════════════════════════════════════════════════════════════
# PAGE CONFIG
# ═══════════════════════════════════════════════════════════════════════════════
# Page config moved to top of file
# st.set_page_config(...) removed here to avoid 'set_page_config() can only be called once' error

# ═══════════════════════════════════════════════════════════════════════════════
# CUSTOM CSS - ChatGPT 2025 Dark Mode Theme
# ═══════════════════════════════════════════════════════════════════════════════
st.markdown("""
<style>
    /* ═══════════════════════════════════════════════════════════════════════════
       CHATGPT 2025 DARK MODE THEME
       Background: #0d1117 | Sidebar: #161b22 | Text: #e6edf3 | Borders: #30363d
    ═══════════════════════════════════════════════════════════════════════════ */

    /* Import fonts - Inter Variable for body, General Sans for headings */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@100..900&display=swap');
    @import url('https://api.fontshare.com/v2/css?f[]=general-sans@200,300,400,500,600,700&display=swap');

    /* Root variables */
    :root {
        --bg-primary: #0d1117;
        --bg-secondary: #161b22;
        --bg-tertiary: #21262d;
        --text-primary: #e6edf3;
        --text-secondary: #8b949e;
        --text-muted: #6e7681;
        --border-default: #30363d;
        --border-muted: #21262d;
        --accent-blue: #3391ff;
        --accent-green: #238636;
        --accent-hover: #1f6feb;
        --shadow-default: 0 1px 3px rgba(0,0,0,0.6);
        --shadow-elevated: 0 4px 12px rgba(0,0,0,0.5);
        --radius-card: 12px;
        --radius-button: 8px;
        --font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        --font-heading: 'General Sans', 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }

    /* Global font and background - disable ligatures to prevent corruption */
    html, body, [data-testid="stAppViewContainer"], .main {
        font-family: var(--font-family) !important;
        font-size: 14px;
        background-color: var(--bg-primary) !important;
        color: var(--text-primary) !important;
        font-feature-settings: "liga" 0, "clig" 0, "calt" 0 !important;
        -webkit-font-feature-settings: "liga" 0, "clig" 0, "calt" 0 !important;
        -moz-font-feature-settings: "liga" 0, "clig" 0, "calt" 0 !important;
        text-rendering: optimizeLegibility;
    }

    /* Main container */
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
        background-color: var(--bg-primary);
    }

    /* Stacked container / root */
    [data-testid="stAppViewContainer"] > section > div {
        background-color: var(--bg-primary);
    }

    /* Header area */
    header[data-testid="stHeader"] {
        background-color: var(--bg-primary) !important;
        border-bottom: 1px solid var(--border-default);
    }

    /* ═══════════════════════════════════════════════════════════════════════════
       SIDEBAR
    ═══════════════════════════════════════════════════════════════════════════ */
    /* ═══════════════════════════════════════════════════════════════════════════
       SIDEBAR - PERMANENTLY HIDDEN
    ═══════════════════════════════════════════════════════════════════════════ */
    [data-testid="stSidebar"] {
        display: none !important;
        visibility: hidden !important;
    }

    [data-testid="collapsedControl"] {
        display: none !important;
        visibility: hidden !important;
    }
    
    /* Ensure no residual spacing from sidebar */
    .stApp > header {
        background-color: transparent !important;
    }

    .stApp {
        margin-top: 30px;
    }

    /* ═══════════════════════════════════════════════════════════════════════════
       TYPOGRAPHY
    ═══════════════════════════════════════════════════════════════════════════ */
    h1, h2, h3, h4, h5, h6 {
        color: var(--text-primary) !important;
        font-family: var(--font-heading) !important;
        font-weight: 600;
    }

    h1 {
        font-size: 24px !important;
        border-bottom: 1px solid var(--border-default);
        padding-bottom: 0.75rem;
    }

    h2, h3 {
        font-size: 16px !important;
    }

    /* Bold text uses heading font */
    strong, b {
        font-family: var(--font-heading) !important;
        font-weight: 600;
    }

    p, span, div, label {
        color: var(--text-primary);
        font-family: var(--font-family) !important;
        font-feature-settings: "liga" 0, "clig" 0, "calt" 0 !important;
    }

    /* Force all text elements to use safe rendering */
    * {
        font-feature-settings: "liga" 0, "clig" 0, "calt" 0 !important;
        -webkit-font-feature-settings: "liga" 0, "clig" 0, "calt" 0 !important;
    }

    /* Markdown text */
    [data-testid="stMarkdownContainer"] {
        color: var(--text-primary) !important;
    }

    [data-testid="stMarkdownContainer"] p,
    [data-testid="stMarkdownContainer"] li,
    [data-testid="stMarkdownContainer"] span {
        color: var(--text-primary) !important;
    }

    /* Caption / muted text */
    .stCaption, [data-testid="stCaptionContainer"] {
        color: var(--text-secondary) !important;
    }

    /* ═══════════════════════════════════════════════════════════════════════════
       BUTTONS
    ═══════════════════════════════════════════════════════════════════════════ */
    .stButton > button {
        background-color: var(--bg-tertiary) !important;
        color: var(--text-primary) !important;
        border: 1px solid var(--border-default) !important;
        border-radius: var(--radius-button) !important;
        padding: 0.5rem 1.5rem;
        font-weight: 500;
        font-size: 14px;
        font-family: var(--font-family) !important;
        box-shadow: var(--shadow-default);
        transition: all 0.15s ease;
    }

    .stButton > button:hover {
        background-color: var(--border-default) !important;
        border-color: var(--text-secondary) !important;
        box-shadow: var(--shadow-elevated);
    }

    .stButton > button:focus {
        box-shadow: 0 0 0 2px var(--accent-blue) !important;
        outline: none;
    }

    /* Primary button */
    .stButton > button[kind="primary"],
    .stButton > button[data-testid="baseButton-primary"] {
        background-color: var(--accent-blue) !important;
        border-color: var(--accent-blue) !important;
        color: #ffffff !important;
    }

    .stButton > button[kind="primary"]:hover,
    .stButton > button[data-testid="baseButton-primary"]:hover {
        background-color: var(--accent-hover) !important;
        border-color: var(--accent-hover) !important;
    }

    /* Download button */
    .stDownloadButton > button {
        background-color: var(--accent-green) !important;
        color: #ffffff !important;
        border: 1px solid var(--accent-green) !important;
        border-radius: var(--radius-button) !important;
        font-family: var(--font-family) !important;
        box-shadow: var(--shadow-default);
    }

    .stDownloadButton > button:hover {
        background-color: #2ea043 !important;
        border-color: #2ea043 !important;
    }

    /* ═══════════════════════════════════════════════════════════════════════════
       TABS
    ═══════════════════════════════════════════════════════════════════════════ */
    .stTabs [data-baseweb="tab-list"] {
        background-color: transparent;
        gap: 4px;
        border-bottom: 1px solid var(--border-default);
    }

    .stTabs [data-baseweb="tab"] {
        background-color: transparent !important;
        color: var(--text-secondary) !important;
        border-radius: var(--radius-button) var(--radius-button) 0 0 !important;
        padding: 10px 20px;
        font-weight: 500;
        font-size: 14px;
        font-family: var(--font-family) !important;
        border: 1px solid transparent;
        border-bottom: none;
        transition: all 0.15s ease;
    }

    .stTabs [data-baseweb="tab"]:hover {
        background-color: var(--bg-tertiary) !important;
        color: var(--text-primary) !important;
    }

    .stTabs [data-baseweb="tab"][aria-selected="true"] {
        background-color: var(--bg-tertiary) !important;
        color: var(--text-primary) !important;
        border-color: var(--border-default) !important;
        border-bottom: 1px solid var(--bg-primary) !important;
        margin-bottom: -1px;
    }

    .stTabs [data-baseweb="tab-highlight"] {
        background-color: var(--accent-blue) !important;
    }

    .stTabs [data-baseweb="tab-panel"] {
        background-color: var(--bg-primary);
        padding-top: 1rem;
    }

    /* ═══════════════════════════════════════════════════════════════════════════
       INPUTS & FORM ELEMENTS
    ═══════════════════════════════════════════════════════════════════════════ */
    /* Text inputs */
    .stTextInput > div > div > input,
    .stTextArea > div > div > textarea {
        background-color: var(--bg-tertiary) !important;
        color: var(--text-primary) !important;
        border: 1px solid var(--border-default) !important;
        border-radius: var(--radius-button) !important;
        font-size: 14px;
        font-family: var(--font-family) !important;
        padding: 0.5rem 0.75rem;
    }

    .stTextInput > div > div > input:focus,
    .stTextArea > div > div > textarea:focus {
        border-color: var(--accent-blue) !important;
        box-shadow: 0 0 0 1px var(--accent-blue) !important;
    }

    .stTextInput > div > div > input::placeholder,
    .stTextArea > div > div > textarea::placeholder {
        color: var(--text-muted) !important;
    }

    /* Labels */
    .stTextInput label,
    .stTextArea label,
    .stSelectbox label,
    .stMultiSelect label,
    .stSlider label,
    .stDateInput label,
    .stTimeInput label,
    .stCheckbox label,
    .stRadio label {
        color: var(--text-primary) !important;
        font-family: var(--font-family) !important;
        font-size: 14px;
    }

    /* Select boxes */
    .stSelectbox > div > div,
    [data-baseweb="select"] > div {
        background-color: var(--bg-tertiary) !important;
        border: 1px solid var(--border-default) !important;
        border-radius: var(--radius-button) !important;
    }

    [data-baseweb="select"] > div > div {
        color: var(--text-primary) !important;
    }

    /* Dropdown menu */
    [data-baseweb="popover"] > div,
    [data-baseweb="menu"] {
        background-color: var(--bg-secondary) !important;
        border: 1px solid var(--border-default) !important;
        border-radius: var(--radius-button) !important;
        box-shadow: var(--shadow-elevated);
    }

    [data-baseweb="menu"] li {
        color: var(--text-primary) !important;
        background-color: transparent !important;
    }

    [data-baseweb="menu"] li:hover {
        background-color: var(--bg-tertiary) !important;
    }

    /* Selectbox dropdown list - comprehensive fix for white background */
    [data-baseweb="popover"],
    [data-baseweb="popover"] [data-baseweb="menu"],
    [data-baseweb="select"] [data-baseweb="popover"],
    [data-baseweb="list"],
    ul[role="listbox"],
    div[role="listbox"] {
        background-color: var(--bg-secondary) !important;
        border: 1px solid var(--border-default) !important;
    }

    /* Individual options in dropdown */
    [data-baseweb="menu"] [role="option"],
    ul[role="listbox"] li,
    div[role="listbox"] [role="option"],
    [data-baseweb="list"] li,
    [data-baseweb="menu-item"] {
        background-color: var(--bg-secondary) !important;
        color: var(--text-primary) !important;
    }

    [data-baseweb="menu"] [role="option"]:hover,
    ul[role="listbox"] li:hover,
    div[role="listbox"] [role="option"]:hover,
    [data-baseweb="list"] li:hover,
    [data-baseweb="menu-item"]:hover {
        background-color: var(--bg-tertiary) !important;
    }

    /* Selected option highlight */
    [data-baseweb="menu"] [aria-selected="true"],
    ul[role="listbox"] [aria-selected="true"],
    [data-baseweb="list"] [aria-selected="true"] {
        background-color: var(--bg-tertiary) !important;
        color: var(--accent-blue) !important;
    }

    /* Ensure the popover body has dark background */
    [data-baseweb="popover"] > div > div,
    [data-baseweb="popover"] > div > div > div {
        background-color: var(--bg-secondary) !important;
    }

    /* Sliders - larger thumb for easier clicking */
    .stSlider > div > div > div > div {
        background-color: var(--border-default) !important;
        height: 6px !important;
        border-radius: 3px !important;
    }

    .stSlider > div > div > div > div > div {
        background-color: var(--accent-blue) !important;
        border-radius: 3px !important;
    }

    .stSlider [data-baseweb="slider"] [role="slider"] {
        background-color: var(--text-primary) !important;
        border: 3px solid var(--accent-blue) !important;
        width: 20px !important;
        height: 20px !important;
        border-radius: 50% !important;
        box-shadow: 0 2px 6px rgba(0,0,0,0.4) !important;
        cursor: grab !important;
    }
    
    .stSlider [data-baseweb="slider"] [role="slider"]:hover {
        transform: scale(1.15) !important;
        box-shadow: 0 3px 10px rgba(51, 145, 255, 0.5) !important;
    }
    
    .stSlider [data-baseweb="slider"] [role="slider"]:active {
        cursor: grabbing !important;
        transform: scale(1.1) !important;
    }

    /* Date/Time inputs */
    .stDateInput > div > div > input,
    .stTimeInput > div > div > input {
        background-color: var(--bg-tertiary) !important;
        color: var(--text-primary) !important;
        border: 1px solid var(--border-default) !important;
        border-radius: var(--radius-button) !important;
    }

    /* Checkbox */
    .stCheckbox > label > span {
        color: var(--text-primary) !important;
    }

    .stCheckbox [data-testid="stCheckbox"] > label > div:first-child {
        background-color: var(--bg-tertiary);
        border-color: var(--border-default);
    }

    /* Radio buttons */
    .stRadio > div {
        background-color: transparent !important;
    }

    .stRadio > div > label > div:first-child {
        background-color: var(--bg-tertiary) !important;
        border-color: var(--border-default) !important;
    }

    /* Hide 'Press Enter to apply' hint on text inputs */
    .stTextInput [data-baseweb="input-container"] + div,
    .stTextArea [data-baseweb="textarea-container"] + div,
    .stTextInput > div > div:last-child:not([data-baseweb]),
    div[data-testid="InputInstructions"],
    .stTextInput small,
    .stTextArea small {
        display: none !important;
        visibility: hidden !important;
    }

    /* Also hide form helper text */
    .stTextInput [data-testid="stHelperText"],
    .stTextArea [data-testid="stHelperText"] {
        /* Keep help text visible, only hide enter-to-apply */
    }

    /* ═══════════════════════════════════════════════════════════════════════════
       FILE UPLOADER
    ═══════════════════════════════════════════════════════════════════════════ */
    [data-testid="stFileUploader"] {
        background-color: var(--bg-tertiary);
        border: 2px dashed var(--border-default);
        border-radius: var(--radius-card);
        padding: 1rem;
    }

    [data-testid="stFileUploader"]:hover {
        border-color: var(--accent-blue);
    }

    [data-testid="stFileUploader"] section {
        background-color: transparent !important;
    }

    [data-testid="stFileUploader"] section > button {
        background-color: var(--bg-secondary) !important;
        color: var(--text-primary) !important;
        border: 1px solid var(--border-default) !important;
    }

    [data-testid="stFileUploaderDropzone"] {
        background-color: transparent !important;
    }

    /* ═══════════════════════════════════════════════════════════════════════════
       GLOBAL FIX - Hide all broken Material Icon text
    ═══════════════════════════════════════════════════════════════════════════ */
    
    /* Hide ALL broken Material Symbols that render as text like "keyboard_double_arrow_right" */
    [data-testid="stIconMaterial"],
    .material-symbols-rounded,
    span[class*="material"] {
        font-size: 0 !important;
        visibility: hidden !important;
    }
    
    /* Sidebar collapse button - hide broken icon, show SVG chevron */
    [data-testid="stSidebarCollapseButton"] button,
    [data-testid="collapsedControl"] button {
        font-size: 0 !important;
        position: relative;
        min-width: 24px;
        min-height: 24px;
    }
    
    [data-testid="stSidebarCollapseButton"] button::after {
        content: "";
        position: absolute;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        width: 16px;
        height: 16px;
        background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%238b949e' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpolyline points='11 17 6 12 11 7'/%3E%3Cpolyline points='18 17 13 12 18 7'/%3E%3C/svg%3E");
        background-size: contain;
        background-repeat: no-repeat;
    }
    
    [data-testid="collapsedControl"] button::after {
        content: "";
        position: absolute;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        width: 16px;
        height: 16px;
        background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%238b949e' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpolyline points='13 17 18 12 13 7'/%3E%3Cpolyline points='6 17 11 12 6 7'/%3E%3C/svg%3E");
        background-size: contain;
        background-repeat: no-repeat;
    }
    
    /* ═══════════════════════════════════════════════════════════════════════════
       EXPANDERS - Fix Material Icon rendering issue
    ═══════════════════════════════════════════════════════════════════════════ */
    
    /* Hide broken Material Symbols text that shows as "keyboard_arrow_right" */
    [data-testid="stExpander"] summary span[data-testid="stMarkdownContainer"],
    [data-testid="stExpander"] summary > span:first-child {
        font-family: var(--font-family) !important;
    }
    
    /* Hide the broken icon span and replace with CSS chevron */
    [data-testid="stExpander"] summary svg,
    [data-testid="stExpander"] summary [data-testid="stIconMaterial"] {
        display: none !important;
    }
    
    /* Create custom chevron indicator */
    [data-testid="stExpander"] summary::before {
        content: ">";
        display: inline-block;
        margin-right: 8px;
        font-size: 12px;
        font-weight: bold;
        transition: transform 0.2s ease;
        color: var(--text-secondary);
    }
    
    [data-testid="stExpander"] details[open] summary::before {
        transform: rotate(90deg);
    }
    
    .streamlit-expanderHeader {
        background-color: var(--bg-tertiary) !important;
        color: var(--text-primary) !important;
        border: 1px solid var(--border-default) !important;
        border-radius: var(--radius-button) !important;
        font-family: var(--font-family) !important;
    }

    .streamlit-expanderHeader:hover {
        background-color: var(--border-default) !important;
    }

    [data-testid="stExpander"] {
        background-color: var(--bg-secondary);
        border: 1px solid var(--border-default);
        border-radius: var(--radius-card);
        box-shadow: var(--shadow-default);
    }

    [data-testid="stExpander"] details {
        border: none !important;
    }

    [data-testid="stExpander"] summary {
        color: var(--text-primary) !important;
        font-family: var(--font-family) !important;
        list-style: none !important;
    }
    
    /* Remove default marker */
    [data-testid="stExpander"] summary::-webkit-details-marker {
        display: none;
    }
    
    [data-testid="stExpander"] summary::marker {
        display: none;
        content: "";
    }

    [data-testid="stExpander"] > details > div {
        background-color: var(--bg-secondary) !important;
        border-top: 1px solid var(--border-default);
    }

    /* ═══════════════════════════════════════════════════════════════════════════
       ALERTS & INFO BOXES
    ═══════════════════════════════════════════════════════════════════════════ */
    .stAlert, [data-testid="stAlert"] {
        background-color: var(--bg-tertiary) !important;
        border: 1px solid var(--border-default) !important;
        border-radius: var(--radius-card) !important;
        color: var(--text-primary) !important;
    }

    /* Info */
    .stAlert[data-baseweb="notification"][kind="info"],
    [data-testid="stAlert"]:has([data-testid="stAlertContentInfo"]) {
        background-color: rgba(51, 145, 255, 0.1) !important;
        border-color: var(--accent-blue) !important;
    }

    /* Success */
    .stAlert[data-baseweb="notification"][kind="positive"],
    [data-testid="stAlert"]:has([data-testid="stAlertContentSuccess"]) {
        background-color: rgba(35, 134, 54, 0.15) !important;
        border-color: var(--accent-green) !important;
    }

    /* Warning */
    .stAlert[data-baseweb="notification"][kind="warning"],
    [data-testid="stAlert"]:has([data-testid="stAlertContentWarning"]) {
        background-color: rgba(210, 153, 34, 0.15) !important;
        border-color: #d29922 !important;
    }

    /* Error */
    .stAlert[data-baseweb="notification"][kind="negative"],
    [data-testid="stAlert"]:has([data-testid="stAlertContentError"]) {
        background-color: rgba(248, 81, 73, 0.15) !important;
        border-color: #f85149 !important;
    }

    /* ═══════════════════════════════════════════════════════════════════════════
       PROGRESS BAR
    ═══════════════════════════════════════════════════════════════════════════ */
    .stProgress > div > div > div {
        background-color: var(--border-default) !important;
        border-radius: 4px;
    }

    .stProgress > div > div > div > div {
        background-color: var(--accent-blue) !important;
        border-radius: 4px;
    }

    /* ═══════════════════════════════════════════════════════════════════════════
       DIVIDERS
    ═══════════════════════════════════════════════════════════════════════════ */
    hr, [data-testid="stDivider"] {
        border-color: var(--border-default) !important;
    }

    /* ═══════════════════════════════════════════════════════════════════════════
       IMAGES
    ═══════════════════════════════════════════════════════════════════════════ */
    [data-testid="stImage"] {
        border-radius: var(--radius-card);
        overflow: hidden;
        box-shadow: var(--shadow-default);
        border: 1px solid var(--border-default);
    }

    /* ═══════════════════════════════════════════════════════════════════════════
       SPINNER
    ═══════════════════════════════════════════════════════════════════════════ */
    .stSpinner > div {
        border-color: var(--accent-blue) transparent transparent transparent !important;
    }

    /* ═══════════════════════════════════════════════════════════════════════════
       SCROLLBARS
    ═══════════════════════════════════════════════════════════════════════════ */
    ::-webkit-scrollbar {
        width: 8px;
        height: 8px;
    }

    ::-webkit-scrollbar-track {
        background: var(--bg-primary);
    }

    ::-webkit-scrollbar-thumb {
        background-color: var(--border-default);
        border-radius: 4px;
        border: 2px solid var(--bg-primary);
    }

    ::-webkit-scrollbar-thumb:hover {
        background-color: var(--text-muted);
    }

    /* Firefox scrollbar */
    * {
        scrollbar-width: thin;
        scrollbar-color: var(--border-default) var(--bg-primary);
    }

    /* ═══════════════════════════════════════════════════════════════════════════
       TEXT SELECTION
    ═══════════════════════════════════════════════════════════════════════════ */
    ::selection {
        background-color: var(--accent-blue);
        color: #ffffff;
    }

    ::-moz-selection {
        background-color: var(--accent-blue);
        color: #ffffff;
    }

    /* ═══════════════════════════════════════════════════════════════════════════
       TOOLTIPS
    ═══════════════════════════════════════════════════════════════════════════ */
    [data-baseweb="tooltip"] {
        background-color: var(--bg-secondary) !important;
        color: var(--text-primary) !important;
        border: 1px solid var(--border-default) !important;
        border-radius: var(--radius-button) !important;
        box-shadow: var(--shadow-elevated);
    }

    /* ═══════════════════════════════════════════════════════════════════════════
       COLUMNS
    ═══════════════════════════════════════════════════════════════════════════ */
    [data-testid="column"] {
        background-color: transparent;
    }

    /* ═══════════════════════════════════════════════════════════════════════════
       METRIC CARDS
    ═══════════════════════════════════════════════════════════════════════════ */
    [data-testid="stMetric"] {
        background-color: var(--bg-tertiary);
        border: 1px solid var(--border-default);
        border-radius: var(--radius-card);
        padding: 1rem;
        box-shadow: var(--shadow-default);
    }

    [data-testid="stMetricLabel"] {
        color: var(--text-secondary) !important;
    }

    [data-testid="stMetricValue"] {
        color: var(--text-primary) !important;
    }

    /* ═══════════════════════════════════════════════════════════════════════════
       DATAFRAMES & TABLES
    ═══════════════════════════════════════════════════════════════════════════ */
    .stDataFrame, [data-testid="stDataFrame"] {
        background-color: var(--bg-secondary);
        border: 1px solid var(--border-default);
        border-radius: var(--radius-card);
    }

    /* ═══════════════════════════════════════════════════════════════════════════
       FOOTER / BOTTOM ELEMENTS
    ═══════════════════════════════════════════════════════════════════════════ */
    footer {
        background-color: var(--bg-primary) !important;
        color: var(--text-muted) !important;
    }

    /* Hide "Made with Streamlit" */
    footer:after {
        visibility: hidden;
    }

    /* ═══════════════════════════════════════════════════════════════════════════
       ADDITIONAL POLISH
    ═══════════════════════════════════════════════════════════════════════════ */
    /* Ensure all icons inherit proper color */
    svg {
        fill: currentColor;
    }

    /* Links */
    a {
        color: var(--accent-blue) !important;
    }

    a:hover {
        color: var(--accent-hover) !important;
        text-decoration: underline;
    }

    /* Code blocks */
    code, pre {
        background-color: var(--bg-tertiary) !important;
        color: var(--text-primary) !important;
        border: 1px solid var(--border-default);
        border-radius: 4px;
        font-family: 'SF Mono', 'Fira Code', 'Consolas', monospace;
    }

    /* Blockquotes */
    blockquote {
        border-left: 3px solid var(--accent-blue);
        padding-left: 1rem;
        color: var(--text-secondary);
    }

    /* ═══════════════════════════════════════════════════════════════════════════
       VOXELMASK LOADING ANIMATION
    ═══════════════════════════════════════════════════════════════════════════ */
    
    @keyframes voxel-pulse {
        0%, 100% { transform: scale(1); opacity: 1; }
        50% { transform: scale(1.1); opacity: 0.8; }
    }
    
    @keyframes voxel-rotate {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }
    
    @keyframes voxel-glow {
        0%, 100% { box-shadow: 0 0 10px rgba(51, 145, 255, 0.5); }
        50% { box-shadow: 0 0 25px rgba(51, 145, 255, 0.9), 0 0 40px rgba(51, 145, 255, 0.4); }
    }
    
    .voxelmask-loader {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 40px;
        background: linear-gradient(135deg, rgba(51, 145, 255, 0.08) 0%, rgba(35, 134, 54, 0.05) 100%);
        border: 1px solid rgba(51, 145, 255, 0.2);
        border-radius: 16px;
        margin: 20px 0;
    }
    
    .voxel-cube-container {
        position: relative;
        width: 60px;
        height: 60px;
        margin-bottom: 20px;
    }
    
    .voxel-cube {
        width: 100%;
        height: 100%;
        background: linear-gradient(135deg, #3391ff 0%, #238636 100%);
        border-radius: 12px;
        animation: voxel-pulse 2s ease-in-out infinite, voxel-glow 2s ease-in-out infinite;
    }
    
    .voxel-cube::before {
        content: "V";
        position: absolute;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        font-size: 28px;
        font-weight: 700;
        color: #ffffff;
        font-family: 'General Sans', sans-serif;
        text-shadow: 0 2px 4px rgba(0,0,0,0.3);
    }
    
    .voxel-ring {
        position: absolute;
        top: -10px;
        left: -10px;
        width: 80px;
        height: 80px;
        border: 3px solid transparent;
        border-top-color: #3391ff;
        border-radius: 50%;
        animation: voxel-rotate 1.5s linear infinite;
    }
    
    .voxel-progress-text {
        font-size: 16px;
        font-weight: 600;
        color: #e6edf3;
        margin-top: 12px;
    }
    
    .voxel-progress-subtext {
        font-size: 13px;
        color: #8b949e;
        margin-top: 4px;
    }
</style>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════
def is_valid_dicom(filepath: str) -> bool:
    """Check if a file is a valid DICOM with pixel data."""
    try:
        ds = pydicom.dcmread(filepath, stop_before_pixels=True, force=True)
        # Add fallback for missing TransferSyntaxUID
        if not hasattr(ds, 'file_meta') or not hasattr(ds.file_meta, 'TransferSyntaxUID'):
            ds.file_meta.TransferSyntaxUID = pydicom.uid.ImplicitVRLittleEndian
        return hasattr(ds, 'PixelData') or 'PixelData' in ds
    except Exception:
        return False

def get_original_name(dcm_path: str) -> str:
    """Extract patient name from DICOM file."""
    try:
        ds = pydicom.dcmread(dcm_path, stop_before_pixels=True, force=True)
        # Add fallback for missing TransferSyntaxUID
        if not hasattr(ds, 'file_meta') or not hasattr(ds.file_meta, 'TransferSyntaxUID'):
            ds.file_meta.TransferSyntaxUID = pydicom.uid.ImplicitVRLittleEndian
        return str(ds.PatientName) if hasattr(ds, 'PatientName') else "UNKNOWN"
    except Exception:
        return "UNKNOWN"

def get_original_metadata(dcm_path: str) -> dict:
    """Extract key patient/study metadata from DICOM file."""
    try:
        ds = pydicom.dcmread(dcm_path, stop_before_pixels=True, force=True)
        # Add fallback for missing TransferSyntaxUID
        if not hasattr(ds, 'file_meta') or not hasattr(ds.file_meta, 'TransferSyntaxUID'):
            ds.file_meta.TransferSyntaxUID = pydicom.uid.ImplicitVRLittleEndian
        
        # Format DOB if present
        dob = ""
        if hasattr(ds, 'PatientBirthDate') and ds.PatientBirthDate:
            try:
                dob_str = str(ds.PatientBirthDate)
                if len(dob_str) == 8:
                    dob = f"{dob_str[6:8]}/{dob_str[4:6]}/{dob_str[0:4]}"
                else:
                    dob = dob_str
            except:
                dob = str(ds.PatientBirthDate)
        
        # Format Study Date if present
        study_date = ""
        if hasattr(ds, 'StudyDate') and ds.StudyDate:
            try:
                sd_str = str(ds.StudyDate)
                if len(sd_str) == 8:
                    study_date = f"{sd_str[6:8]}/{sd_str[4:6]}/{sd_str[0:4]}"
                else:
                    study_date = sd_str
            except:
                study_date = str(ds.StudyDate)
        
        # Format Study Time if present
        study_time = ""
        if hasattr(ds, 'StudyTime') and ds.StudyTime:
            try:
                st_str = str(ds.StudyTime).split('.')[0]
                if len(st_str) >= 4:
                    study_time = f"{st_str[0:2]}:{st_str[2:4]}"
                    if len(st_str) >= 6:
                        study_time += f":{st_str[4:6]}"
            except Exception as e:
                study_time = str(ds.StudyTime)
        
        return {
            "patient_name": str(ds.PatientName) if hasattr(ds, 'PatientName') else "",
            "patient_id": str(ds.PatientID) if hasattr(ds, 'PatientID') else "",
            "dob": dob,
            "sex": str(ds.PatientSex) if hasattr(ds, 'PatientSex') else "",
            "accession": str(ds.AccessionNumber) if hasattr(ds, 'AccessionNumber') else "",
            "study_date": study_date,
            "study_time": study_time,
            "study_desc": str(ds.StudyDescription) if hasattr(ds, 'StudyDescription') else "",
            "modality": str(ds.Modality) if hasattr(ds, 'Modality') else "",
            "institution": str(ds.InstitutionName) if hasattr(ds, 'InstitutionName') else "",
            "operators_name": str(ds.OperatorsName) if hasattr(ds, 'OperatorsName') else "",
            "performing_physician_name": str(ds.PerformingPhysicianName) if hasattr(ds, 'PerformingPhysicianName') else "",
            # Sonography-specific fields
            "series_description": str(ds.SeriesDescription) if hasattr(ds, 'SeriesDescription') else "",
            "protocol_name": str(ds.ProtocolName) if hasattr(ds, 'ProtocolName') else "",
            "body_part_examined": str(ds.BodyPartExamined) if hasattr(ds, 'BodyPartExamined') else "",
            "scanning_sequence": str(ds.ScanningSequence) if hasattr(ds, 'ScanningSequence') else "",
            "sequence_variant": str(ds.SequenceVariant) if hasattr(ds, 'SequenceVariant') else "",
            "acquisition_date": str(ds.AcquisitionDate) if hasattr(ds, 'AcquisitionDate') else "",
            "acquisition_time": str(ds.AcquisitionTime) if hasattr(ds, 'AcquisitionTime') else "",
            "frame_time": str(ds.FrameTime) if hasattr(ds, 'FrameTime') else "",
            "probe_type": str(ds.ProbeType) if hasattr(ds, 'ProbeType') else ""
        }
    except Exception:
        return {"patient_name": "UNKNOWN"}

def apply_dicom_window_level(arr: np.ndarray, ds) -> np.ndarray:
    """Apply DICOM window/level transformation for proper display.
    
    CRITICAL: For CT images, must apply RescaleIntercept/RescaleSlope first
    to convert raw pixel values to Hounsfield Units before windowing.
    """
    try:
        # Convert to float for calculations
        arr = arr.astype(np.float64)
        
        # ═══════════════════════════════════════════════════════════════════════════
        # CRITICAL: Apply Rescale Slope/Intercept for CT Hounsfield Units
        # Without this, signed CT data appears as white screen
        # Formula: HU = pixel_value * RescaleSlope + RescaleIntercept
        # ═══════════════════════════════════════════════════════════════════════════
        rescale_slope = float(getattr(ds, 'RescaleSlope', 1.0))
        rescale_intercept = float(getattr(ds, 'RescaleIntercept', 0.0))
        
        if rescale_slope != 1.0 or rescale_intercept != 0.0:
            arr = arr * rescale_slope + rescale_intercept
        
        # Check if Window Center and Window Width are present
        if hasattr(ds, 'WindowCenter') and hasattr(ds, 'WindowWidth'):
            # Handle multiple window/level values
            if isinstance(ds.WindowCenter, (list, tuple)):
                window_center = float(ds.WindowCenter[0])
                window_width = float(ds.WindowWidth[0]) if isinstance(ds.WindowWidth, (list, tuple)) else float(ds.WindowWidth)
            else:
                window_center = float(ds.WindowCenter)
                window_width = float(ds.WindowWidth)
            
            # Apply window/level
            min_val = window_center - window_width / 2
            max_val = window_center + window_width / 2
            
            # Clip and normalize to 0-255
            arr = np.clip(arr, min_val, max_val)
            arr = ((arr - min_val) / (max_val - min_val) * 255).astype(np.uint8)
        else:
            # No window/level, use auto-contrast based on percentiles
            p2, p98 = np.percentile(arr, (2, 98))
            if p98 > p2:
                arr = np.clip(arr, p2, p98)
                arr = ((arr - p2) / (p98 - p2) * 255).astype(np.uint8)
            else:
                # Fallback to simple normalization
                if arr.max() > arr.min():
                    arr = ((arr - arr.min()) / (arr.max() - arr.min()) * 255).astype(np.uint8)
                else:
                    arr = np.zeros_like(arr, dtype=np.uint8)
    except Exception:
        # Fallback to simple normalization
        arr = arr.astype(np.float64)
        if arr.max() > arr.min():
            arr = ((arr - arr.min()) / (arr.max() - arr.min()) * 255).astype(np.uint8)
        else:
            arr = np.zeros_like(arr, dtype=np.uint8)
    
    return arr

# ═══════════════════════════════════════════════════════════════════════════════
# HYBRID PREVIEW LOGIC - EFFICIENCY & SAFETY PROTOCOL
# ═══════════════════════════════════════════════════════════════════════════════

# Modalitites that are safe and large - skip preview to save resources
PREVIEW_SKIP_MODALITIES = {
    'CT',    # Computed Tomography - large, pixel-clean
    'MR',    # Magnetic Resonance Imaging - large, pixel-clean
    'CR',    # Computed Radiography - large, pixel-clean
    'DX',    # Digital Radiography - large, pixel-clean
    'XA',    # X-Ray Angiography - large, pixel-clean
    'RF',    # Radiofluoroscopy - large, pixel-clean
    'MG',    # Mammography - large, pixel-clean
    'PT',    # Positron Emission Tomography - large, pixel-clean
    'NM',    # Nuclear Medicine - large, pixel-clean
}

# Modalitites that require visual confirmation of pixel safety
PREVIEW_REQUIRED_MODALITIES = {
    'US',    # Ultrasound - high risk of burned-in PHI
    'SC',    # Secondary Capture - screenshots, annotations
    'OT',    # Other - text-heavy modalities
    'SR',    # Structured Report - text-based
    'KO',    # Key Object Selection - annotations
}

def should_show_preview(dcm_path: str) -> bool:
    """
    Determine if DICOM preview should be shown based on modality.
    
    Returns True for modalities requiring visual confirmation (US, SC, OT).
    Returns False for large, pixel-clean modalities (CT, MR, etc.) to save resources.
    """
    try:
        ds = pydicom.dcmread(dcm_path, force=True, stop_before_pixels=True)
        # Add fallback for missing TransferSyntaxUID
        if not hasattr(ds, 'file_meta') or not hasattr(ds.file_meta, 'TransferSyntaxUID'):
            ds.file_meta.TransferSyntaxUID = pydicom.uid.ImplicitVRLittleEndian
        modality = str(getattr(ds, 'Modality', '')).upper()
        
        # Always show preview for modalities requiring visual confirmation
        if modality in PREVIEW_REQUIRED_MODALITIES:
            return True
            
        # Skip preview for large, pixel-clean modalities
        if modality in PREVIEW_SKIP_MODALITIES:
            return False
            
        # Default: show preview for unknown modalities (safety first)
        return True
        
    except Exception:
        # If we can't read the file, err on the side of safety and show preview
        return True

def display_preview_hybrid(dcm_path: str, caption: str):
    """
    Hybrid preview display - shows preview only for modalities requiring visual confirmation.
    Skips preview for large, pixel-clean modalities to optimize performance.
    """
    if should_show_preview(dcm_path):
        display_preview(dcm_path, caption)
    else:
        try:
            ds = pydicom.dcmread(dcm_path, force=True, stop_before_pixels=True)
            # Add fallback for missing TransferSyntaxUID
            if not hasattr(ds, 'file_meta') or not hasattr(ds.file_meta, 'TransferSyntaxUID'):
                ds.file_meta.TransferSyntaxUID = pydicom.uid.ImplicitVRLittleEndian
            modality = str(getattr(ds, 'Modality', '')).upper()
            st.info(f"📋 Preview skipped for {modality} modality (pixel-clean, large dataset) - processing optimized for speed")
        except Exception:
            st.info("📋 Preview skipped for efficiency (unable to determine modality)")

def display_preview_with_mask_hybrid(dcm_path: str, mask_coords: tuple, caption: str):
    """
    Hybrid preview with mask display - shows preview only for modalities requiring visual confirmation.
    """
    if should_show_preview(dcm_path):
        display_preview_with_mask(dcm_path, mask_coords, caption)
    else:
        try:
            ds = pydicom.dcmread(dcm_path, force=True, stop_before_pixels=True)
            # Add fallback for missing TransferSyntaxUID
            if not hasattr(ds, 'file_meta') or not hasattr(ds.file_meta, 'TransferSyntaxUID'):
                ds.file_meta.TransferSyntaxUID = pydicom.uid.ImplicitVRLittleEndian
            modality = str(getattr(ds, 'Modality', '')).upper()
            st.info(f"📋 Preview with mask skipped for {modality} modality (pixel-clean, large dataset) - processing optimized for speed")
        except Exception:
            st.info("📋 Preview with mask skipped for efficiency (unable to determine modality)")

def display_preview(dcm_path: str, caption: str):
    """Display middle frame preview from DICOM."""
    try:
        ds = pydicom.dcmread(dcm_path, force=True)
        # Add fallback for missing TransferSyntaxUID
        if not hasattr(ds, 'file_meta') or not hasattr(ds.file_meta, 'TransferSyntaxUID'):
            ds.file_meta.TransferSyntaxUID = pydicom.uid.ImplicitVRLittleEndian
        
        # Check if this DICOM file has pixel data (images) or is metadata-only
        if not hasattr(ds, 'PixelData') or ds.PixelData is None:
            # Phase 12: Neutral placeholder for non-image objects
            modality = str(getattr(ds, 'Modality', 'UNK')).upper()
            st.info(f"📄 Non-image object ({modality}). Preview is not available.")
            st.caption("This item will remain in the evidence bundle and export outputs according to policy.")
            return
            
        # ═══════════════════════════════════════════════════════════════════════
        # MEMORY PROTECTION: Pixel Guard
        # ═══════════════════════════════════════════════════════════════════════
        if not should_render_pixels(ds):
            modality = str(getattr(ds, 'Modality', 'UNK')).upper()
            st.warning(f"⚠️ {modality} image too large for browser preview (>150MB raw).")
            st.caption("Metadata will be processed normally. Pixel data is preserved in export.")
            return

        arr = ds.pixel_array
        if arr.ndim == 4:
            frame = arr[len(arr)//2]
        elif arr.ndim == 3 and arr.shape[2] not in (3, 4):
            frame = arr[len(arr)//2]
        else:
            frame = arr
        
        # Apply proper DICOM window/level
        frame = apply_dicom_window_level(frame, ds)
        
        # Convert to 3-channel for display
        if frame.ndim == 2:
            frame = np.stack([frame]*3, axis=-1)
        
        st.image(frame, caption=caption, use_container_width=True)
    except Exception as e:
        st.warning(f"Preview unavailable: {e}")

def display_preview_with_mask(dcm_path: str, mask_coords: tuple, caption: str):
    """Display preview with red rectangle showing mask area."""
    try:
        ds = pydicom.dcmread(dcm_path, force=True)
        # Add fallback for missing TransferSyntaxUID
        if not hasattr(ds, 'file_meta') or not hasattr(ds.file_meta, 'TransferSyntaxUID'):
            ds.file_meta.TransferSyntaxUID = pydicom.uid.ImplicitVRLittleEndian
        
        # Check if this DICOM file has pixel data (images) or is metadata-only
        if not hasattr(ds, 'PixelData') or ds.PixelData is None:
            # Phase 12: Neutral placeholder for non-image objects
            modality = str(getattr(ds, 'Modality', 'UNK')).upper()
            st.info(f"📄 Non-image object ({modality}). Preview is not available.")
            st.caption("This item will remain in the evidence bundle and export outputs according to policy.")
            return
        
        # ═══════════════════════════════════════════════════════════════════════
        # MEMORY PROTECTION: Pixel Guard
        # ═══════════════════════════════════════════════════════════════════════
        if not should_render_pixels(ds):
            modality = str(getattr(ds, 'Modality', 'UNK')).upper()
            st.warning(f"⚠️ {modality} image too large for browser preview (>150MB raw).")
            st.caption("Metadata will be processed normally. Pixel data is preserved in export.")
            return
        
        arr = ds.pixel_array
        if arr.ndim == 4:
            frame = arr[0].copy()
        elif arr.ndim == 3 and arr.shape[2] not in (3, 4):
            frame = arr[0].copy()
        else:
            frame = arr.copy()
        
        # Apply proper DICOM window/level
        frame = apply_dicom_window_level(frame, ds)
        
        # Convert to 3-channel for display
        if frame.ndim == 2:
            frame = np.stack([frame]*3, axis=-1)
        
        x, y, w, h = mask_coords
        cv2.rectangle(frame, (x, y), (x+w, y+h), (255, 0, 0), 3)
        st.image(frame, caption=caption, use_container_width=True)
    except Exception as e:
        st.warning(f"Preview unavailable: {e}")

def dicom_to_pil(dcm_path: str) -> tuple:
    """Convert DICOM to PIL Image, return (pil_image, original_width, original_height)."""
    ds = pydicom.dcmread(dcm_path, force=True)
    # Add fallback for missing TransferSyntaxUID
    if not hasattr(ds, 'file_meta') or not hasattr(ds.file_meta, 'TransferSyntaxUID'):
        ds.file_meta.TransferSyntaxUID = pydicom.uid.ImplicitVRLittleEndian
    
    # Check if this DICOM file has pixel data (images) or is metadata-only
    if not hasattr(ds, 'PixelData') or ds.PixelData is None:
        raise ValueError("DICOM file contains no pixel data - cannot convert to image")
    
    # ═══════════════════════════════════════════════════════════════════════
    # MEMORY PROTECTION: Pixel Guard
    # ═══════════════════════════════════════════════════════════════════════
    if not should_render_pixels(ds):
        raise MemoryError(f"DICOM too large for pixel rendering (>150MB estimated raw)")
    
    try:
        ds.decompress()
    except Exception:
        pass
    arr = ds.pixel_array
    
    # Get single frame
    if arr.ndim == 4:
        frame = arr[0]
    elif arr.ndim == 3:
        if arr.shape[2] in (3, 4):
            frame = arr
        else:
            frame = arr[0]
    else:
        frame = arr
    
    # Get photometric interpretation for color handling
    photometric = str(getattr(ds, 'PhotometricInterpretation', '')).upper()
    
    # Handle YBR color spaces (common in JPEG compressed DICOMs)
    # These often display with purple/weird colors if not converted
    if 'YBR' in photometric and frame.ndim == 3 and frame.shape[2] == 3:
        try:
            from PIL import Image as PILImage
            # Convert YCbCr to RGB
            temp_img = PILImage.fromarray(frame, mode='YCbCr')
            temp_img = temp_img.convert('RGB')
            frame = np.array(temp_img)
        except Exception:
            pass  # Fall back to standard handling
    
    # Apply proper DICOM window/level (only for grayscale)
    if frame.ndim == 2:
        frame = apply_dicom_window_level(frame, ds)
    
    # Ensure uint8 type
    if frame.dtype != np.uint8:
        if frame.max() > 255:
            frame = ((frame - frame.min()) / (frame.max() - frame.min()) * 255).astype(np.uint8)
        else:
            frame = frame.astype(np.uint8)
    
    # Convert to 3-channel RGB for display
    if frame.ndim == 2:
        frame = np.stack([frame]*3, axis=-1)
    elif frame.ndim == 3 and frame.shape[2] == 4:
        # RGBA to RGB
        frame = frame[:, :, :3]
    
    orig_h, orig_w = frame.shape[:2]
    pil_img = Image.fromarray(frame, mode='RGB')
    return pil_img, orig_w, orig_h


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 6: HTML EXPORT VIEWER HELPERS
# Presentation-only rendering for export ZIP viewer.
# ═══════════════════════════════════════════════════════════════════════════════

def render_dicom_bytes_to_png(data: bytes) -> Optional[bytes]:
    """
    Render DICOM bytes to PNG for HTML viewer preview (presentation only).
    
    GOVERNANCE: This is export-time presentation rendering, not processing.
    DICOM bytes are already final. No metadata changes. No pixel mutation.
    PNG is explicitly a derived artefact for view-only purposes.
    """
    import tempfile
    
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".dcm", delete=False) as tmp:
            tmp.write(data)
            tmp_path = tmp.name
        
        pil_img, _, _ = dicom_to_pil(tmp_path)
        
        with io.BytesIO() as buf:
            pil_img.save(buf, format="PNG")
            return buf.getvalue()
    
    except Exception:
        return None
    
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


def _build_viewer_ordered_entries(processed_files: List[Dict], file_info_cache: Dict, root_folder: str) -> List[Dict]:
    """
    Build ordered_entries for viewer_index.json from processed files.
    
    GOVERNANCE:
    - Read-only assembly from existing state
    - No mutation of processed_files
    - No reordering (preserves export order exactly)
    - No touching anonymisation/masking/audit logic
    
    Args:
        processed_files: List of processed file dicts from export
        file_info_cache: Metadata cache from preflight scan
        root_folder: Export root folder name
    
    Returns:
        List of entry dicts suitable for generate_viewer_index()
    """
    ordered_entries = []
    
    for pf in processed_files:
        src_name = pf.get("original_name")  # original upload filename
        info = (file_info_cache or {}).get(src_name, {})  # may be empty
        
        # Build relative path within export
        # GOVERNANCE: Path must be strictly relative for relocatable viewer.
        # Strip any leading system path components, drive letters, or separators.
        folder_path = pf.get("folder_path", "")
        # Remove drive letter if present (manual check for cross-platform safety)
        if len(folder_path) > 1 and folder_path[1] == ":":
            folder_path = folder_path[2:]
        
        folder_path = folder_path.strip(os.sep + "/")
        
        filename = pf.get("filename", "unknown.dcm")
        dicom_rel = f"{folder_path}/{filename}" if folder_path else filename
        
        ordered_entries.append({
            # Viewer index wants paths relative to root_folder
            "relative_path": dicom_rel,
            "file_path": dicom_rel,  # tolerant duplicate key
            
            # Required viewer grouping / navigation metadata
            "modality": info.get("modality") or pf.get("modality") or "UNK",
            "series_number": info.get("series_number") or pf.get("series_number"),
            "series_description": info.get("series_desc") or info.get("series_description") or "Unknown",
            "series_instance_uid": info.get("series_instance_uid") or "UNKNOWN",
            
            "sop_instance_uid": info.get("sop_instance_uid") or "UNKNOWN",
            "instance_number": info.get("instance_number"),  # allow None
        })
    
    return ordered_entries


# ═══════════════════════════════════════════════════════════════════════════════
# HEADER
# ═══════════════════════════════════════════════════════════════════════════════
st.title("VoxelMask — Imaging De-Identification (Pilot Mode)")
st.markdown("**Evaluation build. Copy-out processing only. Not for clinical use.**")

# BUILD STAMP - temporary debug helper (remove after verification)
def _build_stamp():
    import subprocess, os, datetime
    try:
        sha = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True).strip()
    except Exception:
        sha = "no-git"
    return f"build={sha} pid={os.getpid()} cwd={os.getcwd()} ts={datetime.datetime.now().isoformat(timespec='seconds')}"
st.caption(_build_stamp())

# Initialize variables (previously in sidebar)
enable_manual_mask = True
repair_context = None
research_context = None
new_patient_name = ""

# ═══════════════════════════════════════════════════════════════════════════════
# ENSURE DIRECTORIES
# ═══════════════════════════════════════════════════════════════════════════════
os.makedirs(os.path.join(BASE_DIR, "studies", "input"), exist_ok=True)
os.makedirs(os.path.join(BASE_DIR, "studies", "output"), exist_ok=True)
os.makedirs("studies", exist_ok=True)

# ═══════════════════════════════════════════════════════════════════════════════
# SUCCESS VIEW - Show download buttons when processing is complete (HIGH PRIORITY)
# ═══════════════════════════════════════════════════════════════════════════════
if st.session_state.get('processing_complete') and st.session_state.get('output_zip_buffer'):
    st.success(f"✅ Processing complete! {len(st.session_state.processed_files)} files processed successfully")
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # PROCESSING DIAGNOSTICS PANEL
    # ═══════════════════════════════════════════════════════════════════════════════
    if st.session_state.get('processing_stats'):
        stats = st.session_state.processing_stats
        
        # Format values for display
        duration = stats.get('duration_seconds', 0)
        if duration < 60:
            duration_str = f"{duration:.1f}s"
        else:
            mins = int(duration // 60)
            secs = duration % 60
            duration_str = f"{mins}m {secs:.1f}s"
        
        input_mb = stats.get('input_bytes', 0) / (1024 * 1024)
        output_mb = stats.get('output_bytes', 0) / (1024 * 1024)
        files_per_sec = stats.get('files_per_second', 0)
        mb_per_sec = stats.get('mb_per_second', 0)
        
        # Get profile display name (Phase 6 governance-safe)
        profile_names = {
            "internal_repair": "🔧 Internal Repair",
            "us_research_safe_harbor": "🇺🇸 Safe Harbor",
            "au_strict_oaic": "🇦🇺 AU Strict",
            "foi_legal": "⚖️ FOI/Legal",
            "foi_patient": "📋 FOI/Patient"
        }
        profile_display = profile_names.get(stats.get('profile', ''), stats.get('profile', 'Unknown'))
        
        # Use native Streamlit components for reliability
        st.markdown("### 📊 Processing Diagnostics")
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("⏱️ Duration", duration_str)
        with col2:
            st.metric("📁 Files", stats.get('file_count', 0))
        with col3:
            st.metric("⚡ Speed", f"{files_per_sec:.1f}/sec")
        with col4:
            st.metric("💾 Throughput", f"{mb_per_sec:.1f} MB/s")
        
        st.caption(f"📥 Input: {input_mb:.2f} MB  |  🏷️ Profile: {profile_display}  |  🕐 {stats.get('timestamp', '')[:19].replace('T', ' ')}")
    
    num_files = len(st.session_state.processed_files)
    zip_data = st.session_state.output_zip_buffer
    
    # Create downloads directory
    downloads_dir = os.path.join(os.path.dirname(__file__), "..", "downloads")
    os.makedirs(downloads_dir, exist_ok=True)
    
    # Phase 8: Get run paths for deterministic output locations
    run_paths = st.session_state.get("run_paths")
    
    if num_files > 1:
        # Multiple files - use meaningful folder name for ZIP filename
        output_name = st.session_state.get('output_folder_name', f"VoxelMask_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        zip_filename = f"{output_name}.zip"
        zip_path = os.path.join(downloads_dir, zip_filename)
        
        # Write ZIP to disk
        with open(zip_path, 'wb') as f:
            f.write(zip_data)
        
        st.info(f"📁 **File saved to:** `downloads/{zip_filename}`")
        
        # Show the download button with explicit bytes
        st.download_button(
            label=f"📦 Download ZIP ({num_files} files)",
            data=bytes(zip_data),  # Explicit bytes conversion
            file_name=zip_filename,
            mime="application/zip",
            key=f"zip_dl_{hash(zip_filename)}",
            type="primary",
            use_container_width=True
        )
        
        st.markdown(f"""
        <div style="background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 12px; margin-top: 10px;">
            <div style="color: #8b949e; font-size: 12px;">💡 <strong>If the download has a weird filename:</strong></div>
            <div style="color: #c9d1d9; font-size: 13px; margin-top: 4px;">
                The file <code style="background: #21262d; padding: 2px 6px; border-radius: 4px;">{zip_filename}</code> 
                has also been saved to <code style="background: #21262d; padding: 2px 6px; border-radius: 4px;">downloads/</code> folder
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Show folder structure info for AI training
        if st.session_state.get('folder_structure_info'):
            info = st.session_state.folder_structure_info
            st.markdown(f"""
            <div style="background: linear-gradient(135deg, rgba(51, 145, 255, 0.1) 0%, rgba(35, 134, 54, 0.08) 100%); 
                        border: 1px solid rgba(51, 145, 255, 0.25); 
                        border-radius: 12px; 
                        padding: 16px 20px; 
                        margin: 12px 0;">
                <div style="font-weight: 600; color: #e6edf3; font-size: 14px; margin-bottom: 8px;">
                    📂 AI Training Ready - Organized by Study/Series
                </div>
                <div style="color: #8b949e; font-size: 13px;">
                    <strong style="color: #3391ff;">{info['files']}</strong> files • 
                    <strong style="color: #238636;">{info['studies']}</strong> studies • 
                    <strong style="color: #d29922;">{info['series']}</strong> series
                </div>
                <div style="color: #6e7681; font-size: 12px; margin-top: 8px;">
                    Sorted by InstanceNumber for radiologist-style scroll-through
                </div>
            </div>
            """, unsafe_allow_html=True)
    else:
        # Single file - STILL use ZIP format with viewer for consistency
        output_name = st.session_state.get('output_folder_name', f"VoxelMask_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        zip_filename = f"{output_name}.zip"
        zip_path = os.path.join(downloads_dir, zip_filename)
        
        # Write ZIP to disk (already created with viewer in processing step)
        with open(zip_path, 'wb') as f:
            f.write(zip_data)
        
        st.info(f"📁 **File saved to:** `downloads/{zip_filename}`")
        
        # Show the download button with explicit bytes
        st.download_button(
            label=f"📦 Download ZIP (1 file + Viewer)",
            data=bytes(zip_data),  # Explicit bytes conversion
            file_name=zip_filename,
            mime="application/zip",
            key=f"zip_dl_single_{hash(zip_filename)}",
            type="primary",
            use_container_width=True
        )
        
        st.markdown(f"""
        <div style="background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 12px; margin-top: 10px;">
            <div style="color: #8b949e; font-size: 12px;">💡 <strong>ZIP includes DICOM Viewer</strong></div>
            <div style="color: #c9d1d9; font-size: 13px; margin-top: 4px;">
                Open <code style="background: #21262d; padding: 2px 6px; border-radius: 4px;">DICOM_Viewer.html</code> 
                to view your processed file
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # PHASE 12: CANONICAL VIEWER (Localhost HTTP Server)
    # 
    # UI Hardening Requirements:
    # 1. Only one "Open Viewer" action (no duplicate buttons)
    # 2. Serves viewer via http://127.0.0.1 to bypass Flatpak sandbox
    # 3. Never uses file:// protocol (fails with document portal)
    # 4. Shows canonical path for FOI/support reference
    # ═══════════════════════════════════════════════════════════════════════════════
    run_viewer_path = st.session_state.get('run_scoped_viewer_path')
    if run_viewer_path and os.path.exists(run_viewer_path) and run_paths:
        # Display viewer panel with localhost HTTP server button
        st.markdown("""
        <div style="background: linear-gradient(135deg, rgba(35, 134, 54, 0.15) 0%, rgba(51, 145, 255, 0.1) 100%); 
                    border: 1px solid rgba(35, 134, 54, 0.4); 
                    border-radius: 12px; 
                    padding: 16px 20px; 
                    margin: 12px 0;">
            <div style="font-weight: 600; color: #e6edf3; font-size: 14px; margin-bottom: 8px;">
                🖼️ Export Viewer
            </div>
            <div style="color: #8b949e; font-size: 13px; margin-bottom: 4px;">
                Opens in your default browser via localhost server.
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Localhost HTTP server button - Phase 12 hardened
        if st.button("🔍 Open Viewer", key="open_viewer_localhost", type="secondary", use_container_width=True):
            success, message = _open_viewer_via_localhost(str(run_paths.root), run_paths.run_id)
            if success:
                st.success(f"✅ {message}")
            else:
                st.error(f"❌ {message}")
        
        # Show canonical path for audit/support reference
        st.caption(f"📁 Viewer path: `{run_viewer_path}`")
    
    # Always offer audit log download
    audit_filename = f"VoxelMask_AuditLog_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    
    # Phase 8: Route to run directory when available, fallback to downloads/
    if run_paths:
        audit_path = str(run_paths.logs_dir / audit_filename)
    else:
        audit_path = os.path.join(downloads_dir, audit_filename)
    
    with open(audit_path, 'w', encoding='utf-8') as f:
        f.write(st.session_state.combined_audit_logs)
    
    st.download_button(
        label="📋 Download Audit Log",
        data=st.session_state.combined_audit_logs,
        file_name=audit_filename,
        mime="text/plain",
        key=f"audit_dl_{hash(audit_filename)}"
    )
    
    # Start New Job button
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("🔄 Start New Job", use_container_width=True, type="secondary", key="start_new_job"):
            # Phase 12: Centralized run state reset
            reset_run_state(st.session_state, reason="Start New Job button clicked")
            st.rerun()
    
    # CRITICAL: Stop execution here to prevent re-running processing logic
    st.stop()

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN UI - Upload and Processing Logic (Default State)
# ═══════════════════════════════════════════════════════════════════════════════
else:
    # ═══════════════════════════════════════════════════════════════════════════════
    # GATEWAY STEP 1: PROFILE SELECTOR (Primary Decision Point)
    # This determines EVERYTHING: what UI shows, what engine runs, what PDF generates
    # ═══════════════════════════════════════════════════════════════════════════════
    
    # Initialize profile in session state if not present
    if 'gateway_profile' not in st.session_state:
        st.session_state.gateway_profile = "internal_repair"
    
    st.markdown("### Processing Configuration")
    st.caption("Defines which metadata fields are modified and which image regions may be masked.")
    
    pacs_operation_mode = st.selectbox(
        "**De-Identification Profile**",
        options=[
            "internal_repair",
            "us_research_safe_harbor", 
            "au_strict_oaic",
            "foi_legal",
            "foi_patient"
        ],
        format_func=lambda x: {
            "internal_repair": "🔧 Internal Repair - Metadata correction (evaluation only)",
            "us_research_safe_harbor": "🇺🇸 US Research (Safe Harbor) - De-identification for research",
            "au_strict_oaic": "🇦🇺 AU Strict (OAIC APP11) - Hash IDs, shift dates",
            "foi_legal": "⚖️ FOI/Legal - Staff redacted, patient data preserved",
            "foi_patient": "📋 FOI/Patient - Patient record release"
        }.get(x, x),
        index=list(["internal_repair", "us_research_safe_harbor", "au_strict_oaic", "foi_legal", "foi_patient"]).index(st.session_state.gateway_profile),
        help="Profiles reflect policy intent, not regulatory certification. Output is intended for research, audit, or evaluation workflows. Not validated for diagnostic or clinical decision-making.",
        key="gateway_profile_selector"
    )
    
    # Update session state
    st.session_state.gateway_profile = pacs_operation_mode
    
    # DERIVE legacy 'mode' from profile for backward compatibility
    if pacs_operation_mode == "internal_repair":
        mode = "Internal Repair"
    else:
        mode = "Research De-ID"
    
    # Store for session state compatibility
    st.session_state.processing_mode = mode
    
    # Show profile summary (Phase 6 governance-safe language)
    profile_summaries = {
        "internal_repair": ("✅", "success", "**Internal Repair**: Metadata correction. Dates/UIDs preserved. For evaluation."),
        "us_research_safe_harbor": ("🛡️", "info", "**Safe Harbor**: De-identification based on configured rules. For research workflows."),
        "au_strict_oaic": ("🔒", "warning", "**AU Strict**: Hashes PatientID, shifts dates. Based on OAIC APP11 policy intent."),
        "foi_legal": ("⚖️", "info", "**FOI/Legal**: Preserves patient data, redacts staff names. For disclosure workflows."),
        "foi_patient": ("📋", "info", "**FOI/Patient**: Patient record release. For review and evaluation purposes.")
    }
    
    icon, style, text = profile_summaries.get(pacs_operation_mode, ("ℹ️", "info", "Select a profile"))
    if style == "success":
        st.success(text)
    elif style == "warning":
        st.warning(text)
    else:
        st.info(text)
    
    st.divider()
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # PHASE 6: EXPLICIT SELECTION SCOPE
    # Replaces implicit document handling with explicit operator toggles.
    # Default is conservative: images included, documents excluded.
    # ═══════════════════════════════════════════════════════════════════════════════
    
    st.markdown("### 📋 Selection Scope")
    st.caption("Define which object types are included in the output package.")
    
    # Get current selection scope from session state
    selection_scope = st.session_state.selection_scope
    
    scope_col1, scope_col2 = st.columns(2)
    
    with scope_col1:
        include_images = st.checkbox(
            "☑ **Include Imaging Series**",
            value=selection_scope.include_images,
            help="Include standard imaging modalities (US, CT, MR, XR, etc.) in the output package.",
            key="scope_include_images"
        )
        if include_images != selection_scope.include_images:
            selection_scope.set_include_images(include_images)
    
    with scope_col2:
        include_documents = st.checkbox(
            "☐ **Include Associated Documents**",
            value=selection_scope.include_documents,
            help="Non-image objects (worksheets, reports, SC, OT) are only included when explicitly selected. This affects output content and audit records.",
            key="scope_include_documents"
        )
        if include_documents != selection_scope.include_documents:
            selection_scope.set_include_documents(include_documents)
    
    # Show explicit status message based on document selection
    if not selection_scope.include_documents:
        st.markdown("""
        <div style="background: rgba(139, 148, 158, 0.1); border: 1px solid rgba(139, 148, 158, 0.3); 
                    border-radius: 8px; padding: 10px 14px; margin: 8px 0; font-size: 13px;">
            <span style="color: #8b949e;">ℹ️ <strong>Associated Documents: Excluded by selection</strong></span>
            <br><span style="color: #6e7681; font-size: 12px;">
            Worksheets, reports, SC/OT objects, and PDFs will not appear in output package, viewer, or audit evidence bundle.
            </span>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div style="background: rgba(51, 145, 255, 0.1); border: 1px solid rgba(51, 145, 255, 0.3); 
                    border-radius: 8px; padding: 10px 14px; margin: 8px 0; font-size: 13px;">
            <span style="color: #3391ff;">📋 <strong>Associated Documents: Included</strong></span>
            <br><span style="color: #6e7681; font-size: 12px;">
            Worksheets, reports, SC/OT objects, and PDFs will be included and labelled as "Associated Objects" in the output.
            </span>
        </div>
        """, unsafe_allow_html=True)
    
    st.divider()

    # ═══════════════════════════════════════════════════════════════════════════════
    # UNIFIED SMART INGEST - Single drop zone that handles everything
    # ═══════════════════════════════════════════════════════════════════════════════
    
    # Large file disclaimer
    st.markdown("""
    <div style="background: linear-gradient(135deg, rgba(51, 145, 255, 0.1) 0%, rgba(51, 145, 255, 0.05) 100%); 
                border: 1px solid rgba(51, 145, 255, 0.3); 
                border-radius: 12px; 
                padding: 16px 20px; 
                margin-bottom: 20px;">
        <div style="display: flex; align-items: center; gap: 12px;">
            <div style="font-size: 24px;">💾</div>
            <div>
                <div style="font-weight: 600; color: #e6edf3; font-size: 14px;">Large File Support Enabled</div>
                <div style="color: #8b949e; font-size: 13px;">Upload limit: <strong style="color: #3391ff;">10 GB</strong> • Large studies may take a while to load</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("### Input Studies")
st.caption("DICOM studies are processed in copy-out mode. Source data is not modified.")

uploaded_files = st.file_uploader(
    "**Select DICOM Files**", 
    type=None, 
    accept_multiple_files=True,
    key="unified_upload"
)

# Show loading animation when files are being uploaded
if uploaded_files and len(uploaded_files) > 0:
    total_size_bytes = sum(f.size for f in uploaded_files)
    total_size_mb = total_size_bytes / (1024 * 1024)
    total_size_gb = total_size_bytes / (1024 * 1024 * 1024)
    
    # Show size warning for large uploads
    if total_size_gb > 1:
        st.markdown(f"""
        <div style="background: linear-gradient(135deg, rgba(210, 153, 34, 0.15) 0%, rgba(210, 153, 34, 0.05) 100%); 
                    border: 1px solid rgba(210, 153, 34, 0.4); 
                    border-radius: 12px; 
                    padding: 16px 20px; 
                    margin: 10px 0;">
            <div style="display: flex; align-items: center; gap: 12px;">
                <div style="font-size: 24px;">⏳</div>
                <div>
                    <div style="font-weight: 600; color: #e6edf3; font-size: 14px;">Large Dataset Detected</div>
                    <div style="color: #8b949e; font-size: 13px;">Total size: <strong style="color: #d29922;">{total_size_gb:.2f} GB</strong> • Processing may take several minutes</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    elif total_size_mb > 100:
        st.info(f"📊 Upload size: **{total_size_mb:.1f} MB** ({len(uploaded_files)} files)")

# Smart file detection and extraction
dicom_files = []
if uploaded_files:
    for uploaded_file in uploaded_files:
        if uploaded_file.name.lower().endswith('.zip'):
            # Extract ZIP and find DICOM files
            try:
                with tempfile.TemporaryDirectory() as temp_dir:
                    zip_path = os.path.join(temp_dir, "upload.zip")
                    with open(zip_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())
                    
                    with zipfile.ZipFile(zip_path, 'r') as zf:
                        zf.extractall(temp_dir)
                    
                    # Find all DICOM files (skip HTML, CSS, JS, text files)
                    skip_extensions = ('.html', '.htm', '.css', '.js', '.txt', '.md', '.json', '.xml', '.pdf', '.doc', '.docx')
                    for root, dirs, files in os.walk(temp_dir):
                        for file in files:
                            if not file.startswith('.') and not file.startswith('__') and not file.lower().endswith(skip_extensions):
                                file_path = os.path.join(root, file)
                                try:
                                    with open(file_path, 'rb') as f:
                                        header = f.read(132)
                                        if len(header) >= 132 and header[128:132] == b'DICM':
                                            with open(file_path, 'rb') as df:
                                                file_bytes = df.read()
                                            
                                            class FileBuffer:
                                                def __init__(self, name, data):
                                                    self.name = name
                                                    self._data = data
                                                def getbuffer(self):
                                                    return self._data
                                            
                                            dicom_files.append(FileBuffer(file, file_bytes))
                                except:
                                    pass
            except Exception as e:
                st.error(f"Error extracting ZIP: {e}")
        else:
            # Regular file - filter out non-DICOM files (HTML, CSS, JS, text, etc.)
            skip_extensions = ('.html', '.htm', '.css', '.js', '.txt', '.md', '.json', '.xml', '.pdf', '.doc', '.docx')
            if not uploaded_file.name.lower().endswith(skip_extensions):
                dicom_files.append(uploaded_file)

# Store uploaded files in session state to persist across form interactions
# Detect new upload and reset run state if files changed
if 'uploaded_dicom_files' in st.session_state:
    old_names = set(fb.name for fb in st.session_state.uploaded_dicom_files)
    new_names = set(fb.name for fb in dicom_files)
    if old_names != new_names and dicom_files:
        # Phase 12: New files uploaded - full run state reset
        reset_run_state(st.session_state, reason="New files uploaded (different from previous)")
        
st.session_state.uploaded_dicom_files = dicom_files

# Analyze DICOM files and create manifest for selection
if st.session_state.get('uploaded_dicom_files'):
    dicom_files = st.session_state.uploaded_dicom_files
    import pandas as pd
    
    # Initialize session state for manifest selections (persists across reruns)
    # Use unique FileID (index-based) since filenames can be duplicated
    if 'manifest_selections' not in st.session_state:
        st.session_state.manifest_selections = {}  # {file_id: True/False}
    
    # Cache analysis results to prevent re-analyzing on every page interaction
    current_file_hash = "_".join(sorted([fb.name for fb in dicom_files]))
    needs_reanalysis = (
        'manifest_data_cache' not in st.session_state or 
        st.session_state.get('manifest_file_hash') != current_file_hash
    )
    
    if needs_reanalysis:
        # Analyze all DICOM files to determine type and risk
        manifest_data = []
        for file_idx, file_buffer in enumerate(dicom_files):
            # Create unique file ID (index + name to handle duplicates)
            file_id = f"{file_idx}_{file_buffer.name}"
            
            try:
                # Read DICOM metadata without pixel data for analysis
                with tempfile.NamedTemporaryFile(delete=False, suffix='.dcm') as tmp:
                    tmp.write(file_buffer.getbuffer())
                    temp_path = tmp.name
                
                analysis = analyze_dicom_context(temp_path)
                analysis['Filename'] = file_buffer.name
                analysis['FileID'] = file_id  # Unique identifier
                analysis['FileIndex'] = file_idx  # For mapping back to dicom_files
                
                # Auto-exclude DICOMDIR files
                if file_buffer.name.upper() == 'DICOMDIR':
                    analysis['Include'] = False
                    analysis['Type'] = 'DICOMDIR'
                    analysis['Risk'] = 'Skip'
                
                # Use stored selection if available, otherwise use analysis default
                if file_id in st.session_state.manifest_selections:
                    analysis['Include'] = st.session_state.manifest_selections[file_id]
                else:
                    # First time seeing this file - store the initial selection
                    # Auto-exclude DICOMDIR
                    if file_buffer.name.upper() == 'DICOMDIR':
                        st.session_state.manifest_selections[file_id] = False
                    else:
                        st.session_state.manifest_selections[file_id] = analysis['Include']
                
                manifest_data.append(analysis)
                
                # Clean up temp file
                os.unlink(temp_path)
            except Exception as e:
                # If analysis fails, mark as high risk
                manifest_data.append({
                    'Filename': file_buffer.name,
                    'FileID': file_id,
                    'FileIndex': file_idx,
                    'Type': 'Unknown',
                    'Risk': 'High',
                    'Include': st.session_state.manifest_selections.get(file_id, False)
                })
        
        # Cache the analysis results
        st.session_state.manifest_data_cache = manifest_data
        st.session_state.manifest_file_hash = current_file_hash
    else:
        # Use cached analysis but update Include values from current selections
        manifest_data = []
        for item in st.session_state.manifest_data_cache:
            item_copy = item.copy()
            file_id = item_copy['FileID']
            if file_id in st.session_state.manifest_selections:
                item_copy['Include'] = st.session_state.manifest_selections[file_id]
            manifest_data.append(item_copy)
    
    # Create manifest DataFrame
    manifest_df = pd.DataFrame(manifest_data)
    
    st.markdown("### 📋 File Analysis Complete")
    
    # Interactive manifest editor FIRST (so user can toggle checkboxes)
    st.markdown("**Select files to process:**")
    st.caption("⚠️ DICOMDIR files are automatically excluded. Toggle checkboxes to include/exclude files.")
    
    # Show only user-facing columns (hide FileID and FileIndex)
    display_df = manifest_df[['Type', 'Risk', 'Include', 'Filename']].copy()
    
    edited_manifest = st.data_editor(
        display_df,
        column_config={
            "Include": st.column_config.CheckboxColumn(
                "✓ Include",
                help="Check to include this file in processing",
                default=False,
            ),
            "Type": st.column_config.TextColumn(
                "Type",
                help="File type detected",
            ),
            "Risk": st.column_config.TextColumn(
                "Risk",
                help="Processing risk level",
            ),
            "Filename": st.column_config.TextColumn(
                "Filename",
                help="Original filename",
            ),
        },
        disabled=["Type", "Risk", "Filename"],
        hide_index=True,
        key="manifest_editor",
        use_container_width=True
    )
    
    # IMPORTANT: Save user's selections back to session state using FileID
    for idx in range(len(edited_manifest)):
        file_id = manifest_df.iloc[idx]['FileID']
        st.session_state.manifest_selections[file_id] = edited_manifest.iloc[idx]['Include']
    
    # Show LIVE summary based on edited_manifest (AFTER user edits)
    total_files = len(edited_manifest)
    included_files = len(edited_manifest[edited_manifest['Include'] == True])
    excluded_files = len(edited_manifest[edited_manifest['Include'] == False])
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Files", total_files)
    with col2:
        st.metric("Selected", included_files, help="Files checked for processing")
    with col3:
        st.metric("Excluded", excluded_files, help="Files unchecked or auto-excluded")
    
    # Get selected file indices for processing (use indices to avoid filename collision)
    selected_indices = []
    for idx in range(len(edited_manifest)):
        if edited_manifest.iloc[idx]['Include']:
            selected_indices.append(manifest_df.iloc[idx]['FileIndex'])
    
    selected_file_buffers = [dicom_files[i] for i in selected_indices]
    
    # Also create a DataFrame view for display purposes
    selected_files = edited_manifest[edited_manifest['Include'] == True]
    
    # Fast Prescan: Group files by modality without loading pixel data
    # ONLY true US modality goes to bucket_us - SC/OT (worksheets) go to bucket_safe
    bucket_us = []
    bucket_safe = []
    bucket_skip = []
    bucket_docs = []  # NEW: Documents that need individual masking (SC, OT, worksheets)
    
    if selected_file_buffers:
        with st.spinner("🔍 Analyzing file modalities..."):
            for file_buffer in selected_file_buffers:
                try:
                    # ═══════════════════════════════════════════════════════════════
                    # MEMORY FIX: Persist immediately to disk
                    # Avoid holding multiple copies in RAM (BytesIO + pydicom read)
                    # ═══════════════════════════════════════════════════════════════
                    run_paths = _ensure_early_run_context()
                    
                    # Persist to run-scoped storage (deduplicated by content hash)
                    # effectively "upload straight to disk"
                    local_path = _get_viewer_cache_path(file_buffer, run_paths)
                    
                    # Read minimal dataset header from DISK (no pixel data)
                    ds = pydicom.dcmread(local_path, stop_before_pixels=True)
                    modality = str(getattr(ds, 'Modality', '')).upper()
                    series_desc = str(getattr(ds, 'SeriesDescription', '')).upper()
                    sop_class_uid = str(getattr(ds, 'SOPClassUID', ''))
                    
                    # ═══════════════════════════════════════════════════════════════
                    # PHASE 6 FIX: SOP Class–Based Classification (Single Source of Truth)
                    # 
                    # CRITICAL: This is the ONLY place where bucket assignment happens.
                    # We use classify_object() which checks SOP Class UID first, then
                    # falls back to modality/keywords. This prevents documents from
                    # leaking into image buckets via modality string manipulation.
                    #
                    # Buckets:
                    # - bucket_us: Pure ultrasound images (shared mask)
                    # - bucket_docs: Documents, SC, OT, SR, PDFs (gated by include_documents)
                    # - bucket_safe: CT, MR, etc (no pixel masking needed)
                    # ═══════════════════════════════════════════════════════════════
                    
                    category = classify_object(
                        modality=modality,
                        sop_class_uid=sop_class_uid,
                        series_description=series_desc,
                        image_type=''
                    )
                    
                    if category == ObjectCategory.IMAGE:
                        # IMAGE category: Check modality for US vs safe bucket
                        if modality == 'US':
                            bucket_us.append(file_buffer)
                        else:
                            bucket_safe.append(file_buffer)
                    elif category in (
                        ObjectCategory.DOCUMENT,
                        ObjectCategory.STRUCTURED_REPORT,
                        ObjectCategory.ENCAPSULATED_PDF,
                    ):
                        # Document category: All gated by include_documents toggle
                        bucket_docs.append(file_buffer)
                    else:
                        # Unknown category (shouldn't happen) → conservative, goes to docs
                        bucket_docs.append(file_buffer)
                    
                    # Store the local path in the file buffer object for later use if needed?
                    # Streamlit's UploadedFile object doesn't easily allow arbitrary attributes.
                    # But since we use _get_viewer_cache_path(file_buffer) which is deterministic (hash-based),
                    # we can just call it again later to get the same path.

                    
                except Exception as e:
                    st.warning(f"Could not analyze {file_buffer.name}: {e}")
                    # Default to docs bucket if analysis fails (need user to review)
                    bucket_docs.append(file_buffer)
    
    # SR files are automatically excluded via the manifest table selection
    # Users can manually include them by checking the box in the file list
    exclude_sr = True
    
    manual_box = None
    
    # Initialize per-file masks storage
    if 'per_file_masks' not in st.session_state:
        st.session_state.per_file_masks = {}  # {filename: (x, y, w, h)}
    
    if 'us_shared_mask' not in st.session_state:
        st.session_state.us_shared_mask = None  # Shared mask for all US files
    
    # ═══════════════════════════════════════════════════════════════════════════
    # PHASE 6: Preview respects selection scope
    # 
    # CRITICAL: Preview must show exactly what will be exported.
    # If include_documents=False, documents do NOT appear in viewer.
    # This prevents "worksheet in preview but not in export" confusion.
    # ═══════════════════════════════════════════════════════════════════════════
    selection_scope = st.session_state.selection_scope
    
    preview_files = []
    
    if selection_scope.include_images:
        preview_files.extend(bucket_us.copy() if bucket_us else [])
    
    if selection_scope.include_documents:
        preview_files.extend(bucket_docs.copy() if bucket_docs else [])
    
    # Pre-analyze all preview files for display
    # ═══════════════════════════════════════════════════════════════════════════════
    # PHASE 12: Run-scoped viewer cache
    # Files are written to viewer_cache/ instead of /tmp/ to survive the session.
    # ═══════════════════════════════════════════════════════════════════════════════
    run_paths = _ensure_early_run_context()
    
    file_info_cache = {}
    for f in preview_files:
        # Use run-scoped viewer cache instead of ephemeral /tmp
        temp_path = _get_viewer_cache_path(f, run_paths)
        try:
            ds = pydicom.dcmread(temp_path, force=True)
            modality = str(getattr(ds, 'Modality', 'UNK')).upper()
            series_desc = str(getattr(ds, 'SeriesDescription', '')).upper()
            image_type = str(getattr(ds, 'ImageType', [])).upper()
            
            # Get image dimensions for aspect ratio check
            rows = int(getattr(ds, 'Rows', 0))
            cols = int(getattr(ds, 'Columns', 0))
            aspect_ratio = cols / rows if rows > 0 else 1
            num_frames = int(getattr(ds, 'NumberOfFrames', 1))
            
            # DOCUMENT DETECTION - Focus on CLEAR indicators only
            # Real US images should NEVER be classified as documents!
            # Only classify as document if we have STRONG evidence:
            
            # 1. Modality is a clear document type (not US)
            is_doc_modality = modality in ['SC', 'OT', 'SR', 'DOC', 'PR']
            
            # 2. Series description clearly indicates a document/form
            doc_keywords = ['WORKSHEET', 'REPORT', 'SUMMARY', 'FORM', 'PAGE', 
                           'CHART', 'GRAPH', 'DOCUMENT', 'SCREEN', 'TEXT', 'TABLE',
                           'OBSTETRIC', 'GENERAL REPORT', 'AUTHORISED']
            desc_indicates_doc = any(kw in series_desc for kw in doc_keywords)
            
            # 3. ImageType indicates derived/secondary content
            image_type_indicates_doc = any(kw in image_type for kw in 
                ['SCREEN', 'REPORT', 'FOR PRESENTATION', 'DERIVED', 'SECONDARY'])
            
            # 4. Very extreme aspect ratio (like a landscape document) - threshold now 1.5
            is_very_extreme_aspect = aspect_ratio > 1.5 or aspect_ratio < 0.65
            
            # 5. NEW: Scanned document detection - check BitsStored
            # Scanned documents are typically 1-bit (black/white) or 8-bit grayscale
            # Real US images are typically 8-12 bits with actual ultrasound data
            bits_stored = int(getattr(ds, 'BitsStored', 8))
            bits_allocated = int(getattr(ds, 'BitsAllocated', 16))
            photometric = str(getattr(ds, 'PhotometricInterpretation', '')).upper()
            
            # Scanned document indicators:
            # - 1-bit: definitely a scanned document (black and white)
            # - MONOCHROME1/2 with extreme aspect: likely a form/report
            is_scanned_doc = bits_stored == 1
            is_likely_form = (is_very_extreme_aspect and 
                             rows > 1000 and cols > 800 and  # Large image
                             photometric in ['MONOCHROME1', 'MONOCHROME2'])
            
            # DECISION LOGIC:
            # - If modality is SC/OT/SR/DOC → always a document
            # - If modality is US but has document keywords → document
            # - If looks like a scanned form (1-bit or extreme aspect) → document
            # - If modality is US but normal content → US image
            
            if is_doc_modality:
                is_document = True
                is_pure_us = False
            elif is_scanned_doc or is_likely_form:
                # Scanned document regardless of modality
                is_document = True
                is_pure_us = False
            elif modality == 'US':
                # For US modality, only classify as doc if DESCRIPTION says so
                is_document = desc_indicates_doc or image_type_indicates_doc
                is_pure_us = not is_document
            else:
                # Other modalities
                is_document = desc_indicates_doc or image_type_indicates_doc
                is_pure_us = False
            
            if is_document:
                file_type = "📋 Document"
            elif is_pure_us:
                file_type = "🔊 US Image"
            else:
                file_type = f"📄 {modality}"
            
            file_info_cache[f.name] = {
                'modality': modality,
                'series_desc': getattr(ds, 'SeriesDescription', '') or f'{modality} - {cols}×{rows}px',
                'file_type': file_type,
                'is_worksheet': is_document,  # Keep old name for compatibility
                'is_pure_us': is_pure_us,
                'dimensions': f'{cols}×{rows}',
                'aspect_ratio': aspect_ratio,
                'temp_path': temp_path,
                'doc_score': doc_score,
                # Phase 6: Additional fields for viewer series grouping
                'sop_instance_uid': str(getattr(ds, 'SOPInstanceUID', 'UNKNOWN')),
                'series_instance_uid': str(getattr(ds, 'SeriesInstanceUID', 'UNKNOWN')),
                'instance_number': int(getattr(ds, 'InstanceNumber', 0)) if hasattr(ds, 'InstanceNumber') and ds.InstanceNumber is not None else None,
                'series_number': int(getattr(ds, 'SeriesNumber', 0)) if hasattr(ds, 'SeriesNumber') and ds.SeriesNumber is not None else None,
                'acquisition_time': str(getattr(ds, 'AcquisitionTime', '')) or str(getattr(ds, 'ContentTime', '')) or None,
            }
        except Exception as e:
            file_info_cache[f.name] = {
                'modality': 'UNK',
                'series_desc': 'Unknown',
                'file_type': '❓ Unknown',
                'is_worksheet': False,
                'is_pure_us': False,
                'temp_path': temp_path,
                'worksheet_score': 0,
                # Phase 6: Fallback fields for viewer
                'sop_instance_uid': 'UNKNOWN',
                'series_instance_uid': 'UNKNOWN',
                'instance_number': None,
                'series_number': None,
                'acquisition_time': None,
            }
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # SPRINT 2: BURNED-IN PHI REVIEW SCAFFOLD (Read-Only)
    # ═══════════════════════════════════════════════════════════════════════════════
    if preview_files and (bucket_us or bucket_docs):
        # Initialize or update review session
        if st.session_state.get("phi_review_session") is None:
            # Create new session with first available file's SOP UID
            try:
                first_file = preview_files[0]
                info = file_info_cache.get(first_file.name, {})
                temp_path = info.get('temp_path', '')
                if temp_path and os.path.exists(temp_path):
                    ds = pydicom.dcmread(temp_path, force=True, stop_before_pixels=True)
                    sop_uid = str(getattr(ds, 'SOPInstanceUID', 'unknown'))
                else:
                    sop_uid = 'unknown'
                st.session_state["phi_review_session"] = ReviewSession.create(sop_instance_uid=sop_uid)
            except Exception:
                st.session_state["phi_review_session"] = ReviewSession.create(sop_instance_uid='unknown')
            
            # ═══════════════════════════════════════════════════════════════════
            # PREFLIGHT SCAN: Detect Secondary Capture and Encapsulated PDF
            # This is a passive, read-only scan that does NOT affect processing.
            # Findings are stored for potential future review UI.
            # Freeze-safe: informational only; no gating; no export changes.
            # Phase 2 Hardening: Register deterministic filename → UID mapping
            # ═══════════════════════════════════════════════════════════════════
            try:
                for f in preview_files:
                    finfo = file_info_cache.get(f.name, {})
                    ftemp_path = finfo.get('temp_path', '')
                    if ftemp_path and os.path.exists(ftemp_path):
                        try:
                            scan_ds = pydicom.dcmread(ftemp_path, force=True, stop_before_pixels=True)
                            
                            # Register deterministic file → UID mapping
                            sop_uid = str(getattr(scan_ds, 'SOPInstanceUID', ''))
                            sop_class = str(getattr(scan_ds, 'SOPClassUID', ''))
                            if sop_uid and sop_class:
                                st.session_state.get("phi_review_session").register_file_uid(
                                    filename=f.name,
                                    sop_instance_uid=sop_uid,
                                    sop_class_uid=sop_class
                                )
                            
                            # Preflight scan for findings
                            finding = preflight_scan_dataset(scan_ds)
                            if finding is not None:
                                st.session_state.get("phi_review_session").add_finding(finding)
                        except Exception:
                            pass  # Skip files that can't be read - non-fatal
            except Exception:
                pass  # Preflight scan failure is non-fatal - do not block session
        
        review_session = st.session_state.get("phi_review_session")
        
        # Guard: Only show review panel if review session is initialized
        if review_session is None:
            st.info("📋 Review session initializing... Please wait for file analysis to complete.")
        else:
            # Review panel - collapsed by default
            with st.expander("🔍 **Burned-In PHI Review** (Preview)", expanded=False):
                st.caption("Sprint 2: Human-in-the-loop review for burned-in text regions")
                
                # Status badge
                if review_session.review_accepted:
                    st.success("✅ Review accepted - ready for export")
                elif review_session.review_started:
                    st.warning("⏳ Review in progress")
                else:
                    st.info("📋 Review not started - regions shown below are auto-detected defaults")
                
                # Summary metrics - AUTHORITATIVE: Derived only from ReviewSession state
                # This is governance-critical: UI must match audit trail
                summary = review_session.get_summary()
                total_regions = summary['total_regions']
                
                col1, col2, col3 = st.columns(3)
                
                # If no regions exist, detection hasn't run yet - show 'Pending' not '0'
                # This prevents misleading UI (showing "0" when actual count is unknown)
                if total_regions == 0 and not review_session.review_accepted:
                    with col1:
                        st.metric("Detected Regions", "—", help="Detection runs during processing")
                    with col2:
                        st.metric("Manual Regions", summary['manual_regions'])
                    with col3:
                        st.metric("Will Mask", "—", help="Determined after detection")
                else:
                    # Regions exist or review is complete - show authoritative counts
                    with col1:
                        st.metric("Detected Regions", summary['ocr_regions'])
                    with col2:
                        st.metric("Manual Regions", summary['manual_regions'])
                    with col3:
                        st.metric("Will Mask", summary['will_mask'])
            
                # ═══════════════════════════════════════════════════════════════════
                # PREFLIGHT FINDINGS INDICATOR (Read-Only, Informational)
                # Shows detected Secondary Capture and Encapsulated PDF instances
                # Freeze-safe: informational only; no gating; no export changes.
                # ═══════════════════════════════════════════════════════════════════
                if review_session.has_findings():
                    findings_summary = review_session.get_findings_summary()
                    sc_count = findings_summary.get('secondary_capture', 0)
                    pdf_count = findings_summary.get('encapsulated_pdf', 0)
                    
                    # Build warning message with finding counts
                    finding_items = []
                    if sc_count > 0:
                        finding_items.append(f"**{sc_count}** Secondary Capture image{'s' if sc_count > 1 else ''}")
                    if pdf_count > 0:
                        finding_items.append(f"**{pdf_count}** Encapsulated PDF{'s' if pdf_count > 1 else ''}")
                    
                    findings_text = " and ".join(finding_items)
                    
                    st.markdown("---")
                    st.warning(
                        f"⚠️ **Non-Standard Objects Detected**\n\n"
                        f"This study contains {findings_text}.\n\n"
                        f"These objects are often overlooked during export. "
                        f"Review carefully before proceeding."
                    )
                    st.caption(
                        "ℹ️ *Secondary Capture images may contain scanned documents or screenshots. "
                        "Encapsulated PDFs are documents embedded in DICOM format. "
                        "Both may contain visible PHI. "
                        "This warning is informational only and does not change masking or export.*"
                    )
                    
                    # ═══════════════════════════════════════════════════════════════
                    # PDF EXCLUSION CONTROLS (Phase 2: User-Driven, Logged)
                    # Allows operator to exclude Encapsulated PDFs from export
                    # ═══════════════════════════════════════════════════════════════
                    pdf_findings = review_session.get_pdf_findings()
                    if pdf_findings and not review_session.is_sealed():
                        st.markdown("---")
                        st.markdown("**📄 Encapsulated PDF Management:**")
                        st.caption("Exclude PDFs from export. This action is logged for audit purposes.")
                        
                        for idx, pdf in enumerate(pdf_findings):
                            # Create unique key for checkbox
                            checkbox_key = f"exclude_pdf_{pdf.sop_instance_uid[:20]}_{idx}"
                            
                            # Display checkbox with current state
                            exclude_label = f"Exclude PDF (SOP: ...{pdf.sop_instance_uid[-12:]})"
                            current_excluded = pdf.excluded
                            
                            new_excluded = st.checkbox(
                                exclude_label,
                                value=current_excluded,
                                key=checkbox_key,
                                help=f"Series: {pdf.series_instance_uid[:20]}... | Modality: {pdf.modality or 'Unknown'}"
                            )
                            
                            # Handle state change with audit logging
                            if new_excluded != current_excluded:
                                review_session.set_pdf_excluded(pdf.sop_instance_uid, new_excluded)
                                
                                # Audit log the decision
                                try:
                                    from audit_manager import AuditLogger
                                    audit_logger = AuditLogger()
                                    audit_logger.log_scrub_event(
                                        operator_id=st.session_state.get('operator_id', 'OPERATOR'),
                                        original_filename=f"PDF_{pdf.sop_instance_uid}",
                                        scrub_uuid=audit_logger.generate_scrub_uuid(),
                                        reason_code="EXCLUDE_ENCAPSULATED_PDF" if new_excluded else "INCLUDE_ENCAPSULATED_PDF",
                                        output_filename=None,
                                        modality=pdf.modality or "DOC",
                                        success=True
                                    )
                                except Exception:
                                    pass  # Audit logging failure is non-fatal
                                
                                st.rerun()
                        
                        # Show exclusion summary
                        excluded_count = len(review_session.get_excluded_pdf_uids())
                        if excluded_count > 0:
                            st.info(f"📋 **{excluded_count}** PDF{'s' if excluded_count > 1 else ''} marked for exclusion from export.")
                    
                    elif pdf_findings and review_session.is_sealed():
                        # Show read-only status after seal
                        excluded_count = len(review_session.get_excluded_pdf_uids())
                        if excluded_count > 0:
                            st.markdown("---")
                            st.success(f"✅ **{excluded_count}** Encapsulated PDF{'s' if excluded_count > 1 else ''} excluded from export (locked).")
                
                # ═══════════════════════════════════════════════════════════════════
                # BULK ACTIONS (PR 4)
                # ═══════════════════════════════════════════════════════════════════
                if not review_session.is_sealed():
                    st.markdown("**Bulk Actions:**")
                    bulk_col1, bulk_col2, bulk_col3 = st.columns(3)
                    
                    with bulk_col1:
                        if st.button("🔴 Mask All Detected", key="bulk_mask_all", use_container_width=True):
                            review_session.mask_all_detected()
                            if not review_session.review_started:
                                review_session.start_review()
                            st.rerun()
                    
                    with bulk_col2:
                        if st.button("🟢 Keep All", key="bulk_unmask_all", use_container_width=True):
                            review_session.unmask_all()
                            if not review_session.review_started:
                                review_session.start_review()
                            st.rerun()
                    
                    with bulk_col3:
                        if st.button("🔄 Reset to Defaults", key="bulk_reset", use_container_width=True):
                            review_session.reset_to_defaults()
                            st.rerun()
                    
                    st.markdown("---")
                
                # ═══════════════════════════════════════════════════════════════════
                # REGION LIST WITH TOGGLE BUTTONS (PR 4)
                # ═══════════════════════════════════════════════════════════════════
                # ═══════════════════════════════════════════════════════════════════
                # PHASE 5A: REVIEW UX SEMANTICS (PRESENTATION-ONLY)
                # Status: Approved | Risk: Low | Behavioral Change: None
                #
                # Visual elements below are derived from Phase 4 data:
                # - Detection Strength Badges: [ OCR: HIGH/MEDIUM/LOW/? ]
                # - Spatial Zone Labels: Zone: HEADER/BODY/FOOTER
                # - Uncertainty Tooltips: ℹ️ for LOW strength or OCR failure
                #
                # INVARIANT: If these visuals are disabled, system behavior is identical.
                # Phase 5A introduces no new decision logic and does not alter review outcomes.
                # ═══════════════════════════════════════════════════════════════════
                regions = review_session.get_active_regions()
                if regions:
                    st.markdown("**Region List:**")
                    
                    for idx, region in enumerate(regions):
                        source_icon = "🔍 OCR" if region.source == RegionSource.OCR else "✏️ Manual"
                        current_action = region.get_effective_action()
                        action_icon = "🔴 MASK" if current_action == RegionAction.MASK else "🟢 KEEP"
                        
                        # Phase 5A: Generate presentation elements (no state mutation)
                        semantics = RegionSemantics.from_region_attributes(
                            detection_strength=region.detection_strength,
                            region_zone=region.region_zone,
                            source=region.source,
                        )
                        
                        # Create row with info and toggle button
                        row_col1, row_col2, row_col3, row_col4 = st.columns([1, 2, 3, 2])
                        
                        with row_col1:
                            st.markdown(f"**#{idx + 1}**")
                        
                        with row_col2:
                            st.markdown(source_icon)
                        
                        with row_col3:
                            st.markdown(f"`({region.x}, {region.y}) {region.w}×{region.h}`")
                        
                        with row_col4:
                            if review_session.is_sealed():
                                # Show static badge if sealed
                                st.markdown(action_icon)
                            else:
                                # Toggle button
                                toggle_label = "🟢 Keep" if current_action == RegionAction.MASK else "🔴 Mask"
                                if st.button(toggle_label, key=f"toggle_{region.region_id}", use_container_width=True):
                                    review_session.toggle_region(region.region_id)
                                    if not review_session.review_started:
                                        review_session.start_review()
                                    st.rerun()
                        
                        # ═══════════════════════════════════════════════════════════════
                        # PHASE 5A: Detection Strength Badge + Zone Label + Uncertainty
                        # Presentation-only: No buttons, no toggles, no action language
                        # ═══════════════════════════════════════════════════════════════
                        if region.source == RegionSource.OCR:
                            # Combine all Phase 5A elements into a single metadata row
                            phase5a_html = f"""
                            <div style="margin-left: 12px; margin-top: 2px; font-size: 0.85em; color: #8b949e;">
                                {semantics.strength_badge_html}
                                {semantics.zone_label_html}
                                {semantics.uncertainty_html}
                            </div>
                            """
                            st.markdown(phase5a_html, unsafe_allow_html=True)
                        
                        # Delete button for manual regions (on separate row to avoid crowding)
                        if region.can_delete() and not review_session.is_sealed():
                            if st.button(f"🗑️ Delete Region #{idx + 1}", key=f"delete_{region.region_id}"):
                                review_session.delete_region(region.region_id)
                                st.rerun()
                        
                        # Visual separator between regions
                        st.markdown("<div style='border-bottom: 1px solid #30363d; margin: 4px 0;'></div>", unsafe_allow_html=True)
                else:
                    st.markdown("*No regions detected yet. Regions will appear after OCR detection runs.*")
                
                # ═══════════════════════════════════════════════════════════════════
                # ADD MANUAL REGION (PR 4)
                # ═══════════════════════════════════════════════════════════════════
                if not review_session.is_sealed():
                    st.markdown("---")
                    st.markdown("**Add Manual Region:**")
                    st.caption("Draw a rectangle by specifying coordinates (pixels)")
                    
                    manual_col1, manual_col2, manual_col3, manual_col4 = st.columns(4)
                    with manual_col1:
                        manual_x = st.number_input("X", min_value=0, max_value=2000, value=0, key="manual_x")
                    with manual_col2:
                        manual_y = st.number_input("Y", min_value=0, max_value=2000, value=0, key="manual_y")
                    with manual_col3:
                        manual_w = st.number_input("Width", min_value=1, max_value=2000, value=100, key="manual_w")
                    with manual_col4:
                        manual_h = st.number_input("Height", min_value=1, max_value=2000, value=50, key="manual_h")
                    
                    if st.button("➕ Add Manual Region", key="add_manual_region"):
                        review_session.add_manual_region(
                            x=int(manual_x), 
                            y=int(manual_y), 
                            w=int(manual_w), 
                            h=int(manual_h)
                        )
                        if not review_session.review_started:
                            review_session.start_review()
                        st.rerun()
                    
                    # Clear all manual regions
                    if summary['manual_regions'] > 0:
                        if st.button("🗑️ Clear All Manual Regions", key="clear_manual"):
                            review_session.clear_manual_regions()
                            st.rerun()
                
                # ═══════════════════════════════════════════════════════════════════
                # ACCEPT & CONTINUE (PR 5 - Accept Gating)
                # ═══════════════════════════════════════════════════════════════════
                st.markdown("---")
                if review_session.is_sealed():
                    st.success("✅ Review accepted. Regions locked — ready for export.")
                else:
                    # Show modification status
                    modified_count = len([r for r in regions if r.is_modified()])
                    if modified_count > 0:
                        st.info(f"📝 {modified_count} region(s) modified from defaults")
                    
                    # Accept button - only shows when review has started
                    if review_session.can_accept():
                        st.markdown("---")
                        st.markdown("**Ready to proceed?**")
                        st.caption("⚠️ Once accepted, region decisions are locked and cannot be changed. Original pixel data is NOT retained.")
                        
                        if st.button("✅ Accept & Continue", key="accept_review", type="primary", use_container_width=True):
                            review_session.accept()
                            st.success("✅ Review accepted! You may now proceed to export.")
                            st.rerun()
                    else:
                        # Review not started yet - prompt user to interact
                        st.caption("💡 *Toggle regions above or add manual regions to begin review.*")
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # PHASE 6: SERIES BROWSER + STACK NAVIGATION
    # Presentation-only. Does NOT affect processing, audit, or export.
    # Ordering source: Gate 1 manifests when available, otherwise DICOM keys.
    # ═══════════════════════════════════════════════════════════════════════════════
    if preview_files and file_info_cache:
        # Build viewer state if needed
        if 'viewer_state' not in st.session_state or st.session_state.get('viewer_needs_rebuild', True):
            st.session_state.viewer_state = build_viewer_state(
                preview_files=preview_files,
                file_info_cache=file_info_cache,
                # Gate 1 manifests could be loaded here if available in session
                ordered_series_manifest=None,
                baseline_order_manifest=None,
            )
            st.session_state.viewer_needs_rebuild = False
        
        viewer_state: ViewerStudyState = st.session_state.viewer_state
        
        if viewer_state and viewer_state.series_list:
            st.markdown("### 📂 Series Browser")
            st.caption("Navigate through series and images. Ordering is preserved from source.")
            
            # Summary row
            summary = viewer_state.get_summary()
            if summary['hidden_series'] > 0:
                st.caption(f"Showing {summary['filtered_series']} of {summary['total_series']} series ({summary['hidden_series']} non-image series hidden)")
            
            # Filter toggle
            show_docs = st.checkbox(
                "Show non-image objects (OT/SC)",
                value=viewer_state.show_non_image_objects,
                key="viewer_show_non_image",
                help="Include Secondary Capture, OT, and other non-image modalities in the series list"
            )
            if show_docs != viewer_state.show_non_image_objects:
                viewer_state.show_non_image_objects = show_docs
                viewer_state.selected_series_idx = 0
                viewer_state.selected_instance_idx = 0
                st.rerun()
            
            # Two-column layout: series list | viewport
            col_browser, col_viewport = st.columns([1, 3])
            
            filtered_series = viewer_state.filtered_series_list
            
            with col_browser:
                st.markdown("**Series:**")
                for idx, series in enumerate(filtered_series):
                    is_selected = (idx == viewer_state.selected_series_idx)
                    
                    # Use container for visual selection
                    if is_selected:
                        st.markdown(f"▶ **{series.display_label}**")
                    else:
                        if st.button(series.display_label, key=f"series_btn_{idx}", use_container_width=True):
                            viewer_state.select_series(idx)
                            st.rerun()
                
                # Ordering provenance (audit-friendly transparency)
                if viewer_state.selected_series:
                    order_icon, order_desc = get_instance_ordering_label(viewer_state.selected_series.ordering_method)
                    st.caption(f"{order_icon} *{order_desc}*")
            
            with col_viewport:
                series = viewer_state.selected_series
                instance = viewer_state.selected_instance
                
                if series and instance:
                    # Stack position display
                    current = viewer_state.selected_instance_idx + 1
                    total = series.count
                    
                    st.markdown(f"**{series.series_description}** — Image {current} of {total}")
                    
                    # Navigation controls
                    nav_col1, nav_col2, nav_col3 = st.columns([1, 8, 1])
                    
                    with nav_col1:
                        if st.button("◀", key="viewer_prev_img", disabled=(current <= 1), use_container_width=True, help="Previous image"):
                            viewer_state.prev_instance()
                            st.rerun()
                    
                    with nav_col2:
                        new_pos = st.slider(
                            "Navigate",
                            min_value=1,
                            max_value=total,
                            value=current,
                            label_visibility="collapsed",
                            key="viewer_stack_slider"
                        )
                        if new_pos != current:
                            viewer_state.goto_instance(new_pos - 1)
                            st.rerun()
                    
                    with nav_col3:
                        if st.button("▶", key="viewer_next_img", disabled=(current >= total), use_container_width=True, help="Next image"):
                            viewer_state.next_instance()
                            st.rerun()
                    
                    # ═══════════════════════════════════════════════════════════════
                    # PHASE 12: OT/SC Non-Image Placeholder Handling
                    # Non-image modalities get neutral placeholder, not error banners.
                    # Image modalities that fail to decode ARE errors (real fault).
                    # ═══════════════════════════════════════════════════════════════
                    
                    if instance.is_image_modality:
                        # Image modality - attempt pixel rendering
                        try:
                            pil_img, w, h = dicom_to_pil(instance.temp_path)
                            st.image(pil_img, use_container_width=True)
                        except Exception as e:
                            # Real error - image modality should have displayable pixels
                            st.error(f"Cannot display image: {e}")
                    else:
                        # Non-image modality (OT, SC, SR, DOC, etc.) - neutral placeholder
                        st.markdown("""
                        <div style="background: rgba(139, 148, 158, 0.08); 
                                    border: 1px solid rgba(139, 148, 158, 0.25); 
                                    border-radius: 12px; 
                                    padding: 40px 30px; 
                                    text-align: center;
                                    margin: 20px 0;">
                            <div style="font-size: 48px; margin-bottom: 16px;">📄</div>
                            <div style="font-size: 16px; font-weight: 500; color: #e6edf3; margin-bottom: 8px;">
                                Non-image object ({0}). Preview is not available.
                            </div>
                            <div style="font-size: 13px; color: #8b949e;">
                                This item will remain in the evidence bundle and export outputs according to policy.
                            </div>
                        </div>
                        """.format(instance.modality), unsafe_allow_html=True)
                    
                    # Metadata footer (shown for all object types)
                    st.caption(f"Modality: {instance.modality} | SOP: {instance.sop_instance_uid[:16]}… | Instance#: {instance.instance_number or '—'} | Position: {instance.stack_position}/{total}")
                else:
                    st.info("Select a series to view images.")
            
            st.markdown("---")
    
    if preview_files:
        st.markdown("### 🎨 Draw Redaction Mask")
        
        # Use US images for mask drawing - documents are handled automatically
        us_images = bucket_us.copy() if bucket_us else []
        documents = bucket_docs.copy() if bucket_docs else []
        
        # Show info about documents if any
        if documents:
            st.info(f"📋 **{len(documents)} document/worksheet files** detected - redaction mask from US image will be applied automatically.")
        
        # ==== US IMAGES - Show FIRST image only for shared mask ====
        # Filter to ONLY actual pure US images (exclude documents that may be in bucket_us)
        pure_us_images = [f for f in us_images if file_info_cache.get(f.name, {}).get('is_pure_us', False)]
        
        # If no pure US found but we have us_images, fall back to first non-document
        if not pure_us_images and us_images:
            # Filter out known documents
            pure_us_images = [f for f in us_images if not file_info_cache.get(f.name, {}).get('is_worksheet', False)]
        
        if pure_us_images:
            st.markdown("#### 🔊 Ultrasound Mask")
            st.caption(f"This mask will apply to ALL {len(pure_us_images)} ultrasound images")
            
            # Show mask status
            if st.session_state.us_shared_mask:
                mx, my, mw, mh = st.session_state.us_shared_mask
                st.success(f"✅ Shared mask set: ({mx},{my}) {mw}×{mh}px → applies to {len(pure_us_images)} images")
            
            # Show FIRST pure US image only
            first_us = pure_us_images[0]
            info = file_info_cache.get(first_us.name, {})
            temp_path = info.get('temp_path', '')
            
            try:
                pil_img, orig_w, orig_h = dicom_to_pil(temp_path)
                
                # Calculate display size (max 700px wide to fit in UI)
                max_display_width = 700
                scale = min(1.0, max_display_width / orig_w)
                display_w = int(orig_w * scale)
                display_h = int(orig_h * scale)
                
                st.markdown("**🎯 Click and drag to draw mask region:**")
                st.caption("Draw a rectangle over the area you want to black out (e.g., patient info header)")
                
                # Prepare existing mask for initial rectangle
                existing_mask = st.session_state.us_shared_mask
                initial_drawing = None
                if existing_mask:
                    mx, my, mw, mh = existing_mask
                    # Scale to display coordinates
                    initial_drawing = {
                        "version": "4.4.0",
                        "objects": [{
                            "type": "rect",
                            "left": mx * scale,
                            "top": my * scale,
                            "width": mw * scale,
                            "height": mh * scale,
                            "fill": "rgba(0, 0, 0, 0.5)",
                            "stroke": "#ff0000",
                            "strokeWidth": 2
                        }]
                    }
                
                # Use drawable canvas for click-and-drag rectangle
                # st_canvas is already imported from patched_canvas at top of file
                
                # Resize image for display
                display_img = pil_img.resize((display_w, display_h))
                
                # Convert image to base64 for HTML canvas background
                import io
                import base64
                buffered = io.BytesIO()
                display_img.save(buffered, format="PNG")
                img_b64 = base64.b64encode(buffered.getvalue()).decode()
                
                # Get existing mask if any
                existing = st.session_state.us_shared_mask
                init_x = int(existing[0] * scale) if existing else 0
                init_y = int(existing[1] * scale) if existing else 0
                init_w = int(existing[2] * scale) if existing else 0
                init_h = int(existing[3] * scale) if existing else 0
                
                # Custom HTML5 Canvas with JavaScript for rectangle drawing
                html_canvas = f"""
                <div id="canvas-container" style="position:relative; display:inline-block;">
                    <canvas id="maskCanvas" width="{display_w}" height="{display_h}" 
                            style="border:2px solid #444; border-radius:4px; cursor:crosshair;"></canvas>
                </div>
                <div id="coords" style="margin-top:8px; color:#ccc; font-family:monospace;">
                    Draw a rectangle on the image above
                </div>
                <input type="hidden" id="maskData" value="">
                
                <script>
                    const canvas = document.getElementById('maskCanvas');
                    const ctx = canvas.getContext('2d');
                    const coordsDiv = document.getElementById('coords');
                    const maskInput = document.getElementById('maskData');
                    
                    // Load background image
                    const img = new Image();
                    img.onload = function() {{
                        ctx.drawImage(img, 0, 0, {display_w}, {display_h});
                        // Draw existing mask if any
                        if ({init_w} > 0 && {init_h} > 0) {{
                            ctx.fillStyle = 'rgba(0, 0, 0, 0.6)';
                            ctx.strokeStyle = '#ff0000';
                            ctx.lineWidth = 2;
                            ctx.fillRect({init_x}, {init_y}, {init_w}, {init_h});
                            ctx.strokeRect({init_x}, {init_y}, {init_w}, {init_h});
                            coordsDiv.innerHTML = '📐 Current mask: X=' + {init_x} + ', Y=' + {init_y} + 
                                                  ', W=' + {init_w} + ', H=' + {init_h};
                        }}
                    }};
                    img.src = 'data:image/png;base64,{img_b64}';
                    
                    let isDrawing = false;
                    let startX, startY, currentRect = null;
                    
                    canvas.onmousedown = function(e) {{
                        const rect = canvas.getBoundingClientRect();
                        startX = e.clientX - rect.left;
                        startY = e.clientY - rect.top;
                        isDrawing = true;
                    }};
                    
                    canvas.onmousemove = function(e) {{
                        if (!isDrawing) return;
                        const rect = canvas.getBoundingClientRect();
                        const x = e.clientX - rect.left;
                        const y = e.clientY - rect.top;
                        
                        // Redraw image
                        ctx.drawImage(img, 0, 0, {display_w}, {display_h});
                        
                        // Draw rectangle
                        const w = x - startX;
                        const h = y - startY;
                        ctx.fillStyle = 'rgba(0, 0, 0, 0.6)';
                        ctx.strokeStyle = '#ff0000';
                        ctx.lineWidth = 2;
                        ctx.fillRect(startX, startY, w, h);
                        ctx.strokeRect(startX, startY, w, h);
                        
                        currentRect = {{x: Math.min(startX, x), y: Math.min(startY, y), 
                                        w: Math.abs(w), h: Math.abs(h)}};
                    }};
                    
                    canvas.onmouseup = function(e) {{
                        if (!isDrawing) return;
                        isDrawing = false;
                        
                        if (currentRect && currentRect.w > 5 && currentRect.h > 5) {{
                            // Scale back to original image coordinates
                            const scale = {scale};
                            const origX = Math.round(currentRect.x / scale);
                            const origY = Math.round(currentRect.y / scale);
                            const origW = Math.round(currentRect.w / scale);
                            const origH = Math.round(currentRect.h / scale);
                            
                            coordsDiv.innerHTML = '📐 <b>Mask region:</b> X=' + origX + ', Y=' + origY + 
                                                  ', Width=' + origW + 'px, Height=' + origH + 'px' +
                                                  '<br><span style="color:#4CAF50;">✓ Use the inputs below to apply</span>';
                            
                            // Store in hidden input for potential form submission
                            maskInput.value = origX + ',' + origY + ',' + origW + ',' + origH;
                            
                            // Try to update Streamlit session state via URL params
                            // (This is a workaround - Streamlit can read this)
                            window.parent.postMessage({{
                                type: 'streamlit:setComponentValue',
                                data: {{x: origX, y: origY, w: origW, h: origH}}
                            }}, '*');
                        }}
                    }};
                    
                    canvas.onmouseleave = function() {{ isDrawing = false; }};
                </script>
                """
                
                import streamlit.components.v1 as components
                components.html(html_canvas, height=display_h + 60)
                
                # Manual input fallback (user can copy values from canvas display)
                st.markdown("**Fine-tune coordinates manually** *(or enter values shown above):*")
                existing_mask = st.session_state.us_shared_mask or (0, 0, orig_w, 80)
                
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    us_mx = st.number_input("X", 0, orig_w, existing_mask[0], key="us_mx_manual")
                with col2:
                    us_my = st.number_input("Y", 0, orig_h, existing_mask[1], key="us_my_manual")
                with col3:
                    us_mw = st.number_input("Width", 10, orig_w, existing_mask[2], key="us_mw_manual")
                with col4:
                    us_mh = st.number_input("Height", 10, orig_h, existing_mask[3], key="us_mh_manual")
                
                if st.button(f"✅ Apply Mask to ALL {len(pure_us_images)} US Images", type="primary", use_container_width=True):
                    st.session_state.us_shared_mask = (us_mx, us_my, us_mw, us_mh)
                    st.session_state.batch_mask = (us_mx, us_my, us_mw, us_mh)
                    st.toast(f"✅ Mask applied to all {len(pure_us_images)} US images")
                    st.rerun()
                    
            except Exception as e:
                st.error(f"Could not load US preview: {e}")
        
        # Set manual_box for processing
        manual_box = st.session_state.us_shared_mask
        
        # Cleanup temp files
        for f in preview_files:
            info = file_info_cache.get(f.name, {})
            try:
                os.unlink(info.get('temp_path', ''))
            except:
                pass
                
    elif bucket_safe:
        # No US files, just safe files
        st.info(f"📋 Detected {len(bucket_safe)} safe modality files (CT/MR/etc.). Standard Tag Anonymization will be applied - no pixel masking needed.")
        manual_box = None
    else:
        # No processable files
        st.warning("No processable files found in selection.")
        manual_box = None
    
    # Determine final file list - ONLY use files that are checked in the manifest
    # This ensures unchecked files are never processed
    all_files = []
    selected_filenames = set(selected_files['Filename'].values)  # Files checked in the data editor
    
    # ═══════════════════════════════════════════════════════════════════════════
    # PHASE 6: Apply Selection Scope Filtering
    # Documents are ONLY included when explicitly selected via include_documents toggle
    # ═══════════════════════════════════════════════════════════════════════════
    selection_scope = st.session_state.selection_scope
    
    # Track counts for Phase 6 UI integrity (no "Documents 0" lie)
    included_image_count = 0
    excluded_document_count = 0
    included_document_count = 0
    
    # Process imaging files (bucket_us, bucket_safe)
    if selection_scope.include_images:
        for fb in bucket_us + bucket_safe:
            if fb.name in selected_filenames:
                all_files.append(fb)
                included_image_count += 1
    
    # Process document files (bucket_docs) - ONLY if include_documents is explicitly True
    if selection_scope.include_documents:
        for fb in bucket_docs:
            if fb.name in selected_filenames:
                all_files.append(fb)
                included_document_count += 1
    else:
        # Count how many documents were excluded by selection scope
        for fb in bucket_docs:
            if fb.name in selected_filenames:
                excluded_document_count += 1
    
    if not exclude_sr:
        for fb in bucket_skip:
            if fb.name in selected_filenames:
                # SR files are documents, respect the toggle
                if selection_scope.include_documents:
                    all_files.append(fb)
                    included_document_count += 1
                else:
                    excluded_document_count += 1
    
    # ═══════════════════════════════════════════════════════════════════════════
    # PHASE 6: UI Integrity - Show accurate exclusion message
    # No "Documents 0" lie - show "Excluded by selection" when documents are not included
    # ═══════════════════════════════════════════════════════════════════════════
    if excluded_document_count > 0:
        st.markdown(f"""
        <div style="background: rgba(139, 148, 158, 0.1); border: 1px solid rgba(139, 148, 158, 0.3); 
                    border-radius: 8px; padding: 10px 14px; margin: 8px 0; font-size: 13px;">
            <span style="color: #8b949e;">📋 <strong>{excluded_document_count} Associated Document{'s' if excluded_document_count > 1 else ''}: Excluded by selection</strong></span>
            <br><span style="color: #6e7681; font-size: 12px;">
            Enable "Include Associated Documents" to include worksheets/reports in output.
            </span>
        </div>
        """, unsafe_allow_html=True)
    elif included_document_count > 0:
        st.markdown(f"""
        <div style="background: rgba(51, 145, 255, 0.1); border: 1px solid rgba(51, 145, 255, 0.3); 
                    border-radius: 8px; padding: 10px 14px; margin: 8px 0; font-size: 13px;">
            <span style="color: #3391ff;">📋 <strong>{included_document_count} Associated Object{'s' if included_document_count > 1 else ''}</strong> included in output</span>
        </div>
        """, unsafe_allow_html=True)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # PDF EXCLUSION: Filter out user-excluded Encapsulated PDFs from export
    # Phase 2: User-driven exclusion - does NOT affect masking or anonymisation
    # Phase 2 Hardening: Uses deterministic filename → UID mapping (no re-reading)
    #
    # GOVERNANCE GUARDRAIL (Phase 6):
    # Export ordering uses Gate 1 manifests (source_order_manifest / export_order_manifest).
    # Do NOT reference st.session_state.viewer_state for export ordering or file lists.
    # viewer_state is presentation-only and may differ from export order.
    # ═══════════════════════════════════════════════════════════════════════════
    review_session = st.session_state.get('phi_review_session')
    if review_session and review_session.has_file_uid_mapping():
        # Get filenames to exclude using the stored deterministic mapping
        excluded_filenames = set(review_session.get_excluded_filenames())
        
        if excluded_filenames:
            # Filter out excluded files by filename (reliable, no re-reading)
            filtered_files = [fb for fb in all_files if fb.name not in excluded_filenames]
            excluded_count = len(all_files) - len(filtered_files)
            all_files = filtered_files
            
            if excluded_count > 0:
                st.info(f"📋 **{excluded_count}** Encapsulated PDF{'s' if excluded_count > 1 else ''} excluded from export (user selection).")
    
    if len(all_files) == 0:
        st.warning("⚠️ No files selected for processing. Please check the boxes above to select files.")
    else:
        st.success(f"✅ **{len(all_files)} files selected** for processing")
        
        # Show processing button only if files are selected
        if len(all_files) > 0:
            st.markdown("---")
            
            # ═══════════════════════════════════════════════════════════════════
            # GATEWAY STEP 3: CONDITIONAL MIDDLE SECTION
            # Show different UI based on selected profile
            # ═══════════════════════════════════════════════════════════════════
            
            # Dynamic header based on profile
            if pacs_operation_mode == "internal_repair":
                st.markdown("### 📝 Patient Details")
                st.caption("Enter the CORRECT patient information to replace the existing data")
            elif pacs_operation_mode.startswith("foi_"):
                st.markdown("### 📋 FOI Request Details")
                st.caption("Enter cover letter details for the release package")
            else:
                st.markdown("### 🔬 Research Configuration")
                st.caption("Configure de-identification settings for research output")
            
            # Use a form to batch all inputs - prevents rerun on every character
            with st.form(key="patient_details_form", clear_on_submit=False):
                # ═══════════════════════════════════════════════════════════════
                # GATEWAY CONDITIONAL UI - Profile-specific inputs
                # ═══════════════════════════════════════════════════════════════
                
                # Initialize defaults for all profiles (prevents UnboundLocalError)
                new_patient_name = ""
                patient_sex = ""
                patient_dob = None
                study_date = date.today()
                study_time = None
                study_type = ""
                location = ""
                gestational_age = ""
                sonographer_name = ""
                referring_physician = ""
                reason_for_correction = ""
                correction_notes = ""
                operator_name = ""
                auto_timestamp = True
                research_context = None
                repair_context = None
                compliance_profile = "safe_harbor"
                research_trial_id = "TRIAL-001"
                research_site_id = "SITE-01"
                research_subject_id = "SUB-001"
                research_time_point = "Baseline"
                research_deid_date = date.today()
                regenerate_uids = False
                uid_only_mode = False  # Phase 12: Initialize here so it's always defined
                exclude_scanned_docs = False
                output_as_nifti = False
                include_html_viewer = False  # Phase 6: HTML export viewer
                foi_case_ref = ""
                foi_requesting_party = ""
                foi_facility_name = "Medical Imaging Department"
                foi_signatory = ""
                foi_recipient = ""  # For "Dear X" greeting in patient letter
                
                # ═══════════════════════════════════════════════════════════════
                # PROFILE A: INTERNAL REPAIR (internal_repair)
                # Show: Patient Name, Sex, DOB, Study Details
                # ═══════════════════════════════════════════════════════════════
                if pacs_operation_mode == "internal_repair":
                    # UID-Only Mode Toggle - Prominent at top
                    uid_only_mode = st.checkbox(
                        "🔁 **UID Regeneration Only** (Keep all patient data, fix PACS duplicates)",
                        value=False,
                        help="Enable this to regenerate SOP Instance UIDs without modifying any patient information. Use when re-importing studies that have duplicate UID errors."
                    )
                    
                    if uid_only_mode:
                        st.info("ℹ️ **UID-Only Mode**: Patient name, DOB, and all other data will be **preserved**. Only SOP/Series/Study Instance UIDs will be regenerated to prevent PACS conflicts.")
                        # Auto-enable UID regeneration
                        regenerate_uids = True
                        # Skip patient name requirement
                        new_patient_name = "PRESERVED"
                        patient_sex = ""
                        patient_dob = None
                    else:
                        # Normal Internal Repair mode - Patient Demographics
                        col1, col2 = st.columns([2, 1])
                        with col1:
                            new_patient_name = st.text_input(
                                "**Patient Name**",
                                placeholder="e.g., CAREY NICOLE AMY",
                                help="Format: SURNAME FIRSTNAME MIDDLENAME - this will replace the original")
                        with col2:
                            patient_sex = st.selectbox("**Sex**", options=["", "F", "M", "O"], index=0)
                        
                        # Secondary row
                        col1, col2 = st.columns([1, 1])
                        with col1:
                            patient_dob = st.date_input("**Date of Birth**", value=None, min_value=date(1900, 1, 1))
                        with col2:
                            regenerate_uids = st.checkbox("🔄 Regenerate UIDs", value=False, help="Fix duplicate UID errors")
                    
                    # Expandable sections for additional details
                    col1, col2 = st.columns(2)
                    with col1:
                        with st.expander("📅 Study Details", expanded=False):
                            study_date = st.date_input("**Study Date**", value=date.today())
                            study_time = st.time_input("**Study Time**", value=None)
                            study_type = st.selectbox(
                                "**Study Type**",
                                options=["", "OB", "GYN", "ABD", "VASC", "MSK", "CARDIAC", "RENAL", "THYROID", "BREAST", "OTHER"],
                                index=0
                            )
                            location = st.text_input(
                                "**Location/Department**",
                                placeholder="e.g., Womens & Childrens Hosp. Rm18"
                            )
                            if study_type == "OB":
                                gestational_age = st.text_input("**Gestational Age**", placeholder="e.g., 25 w 2 d")
                    
                    with col2:
                        with st.expander("👥 Personnel", expanded=False):
                            sonographer_name = st.text_input("**Sonographer/Operator**", placeholder="e.g., LS")
                            referring_physician = st.text_input("**Referring Physician**", placeholder="e.g., Dr. Smith")
                        
                        with st.expander("📋 Correction Notes (Audit)", expanded=False):
                            reason_for_correction = st.selectbox(
                                "**Reason for Correction**",
                                options=["", "Typo/Spelling Error", "Wrong Patient Selected", "Merged Record", "Name Change (Legal)", "Data Entry Error", "Other"]
                            )
                            correction_notes = st.text_area("**Notes**", placeholder="e.g., Patient name corrected from SMITH JOHN to SMITH, JANE")
                            operator_name = st.text_input("**Corrected By (Operator)**", placeholder="e.g., J. Smith")
                            auto_timestamp = st.checkbox("Auto-add timestamp to notes", value=True)
                    
                    research_context = None
                
                # ═══════════════════════════════════════════════════════════════
                # PROFILE D: FOI (foi_legal, foi_patient)
                # Show: Cover Letter Details, Exclude Scanned checkbox
                # HIDE: Patient Name/Sex/DOB inputs entirely
                # ═══════════════════════════════════════════════════════════════
                elif pacs_operation_mode.startswith("foi_"):
                    st.info("ℹ️ **FOI Mode**: Patient data will be PRESERVED. Staff names will be REDACTED.")
                    
                    # FOI Cover Letter Details
                    col1, col2 = st.columns(2)
                    with col1:
                        foi_case_ref = st.text_input("**Case/Request Reference**", placeholder="FOI-2024-001", help="Custom reference number for the letter (e.g., foi9)")
                        foi_requesting_party = st.text_input("**Requesting Party**", placeholder="Law Firm / Patient Name")
                        foi_recipient = st.text_input("**Letter Recipient**", placeholder="e.g., lawyer, patient name", help="This appears as 'Dear [Recipient]' in the cover letter")
                    with col2:
                        foi_facility_name = st.text_input("**Facility Name**", value="Medical Imaging Department")
                        foi_signatory = st.text_input("**Signatory Name**", placeholder="Health Records Officer")
                    
                    # FOI-specific options
                    col1, col2 = st.columns(2)
                    with col1:
                        exclude_scanned_docs = st.checkbox(
                            "🚫 Exclude Scanned Documents (SC/OT)",
                            value=False,
                            help="Exclude worksheets and secondary captures"
                        )
                    with col2:
                        regenerate_uids = st.checkbox(
                            "🔄 Regenerate UIDs",
                            value=False,
                            help="⚠️ Warning: May break chain of custody for legal proceedings"
                        )
                    
                    if regenerate_uids:
                        st.warning("⚠️ Regenerating UIDs may break chain of custody for legal proceedings. Consider keeping original UIDs.")
                    
                    # Set patient name to preserve for FOI
                    new_patient_name = "PRESERVED"  # Placeholder - actual name kept from original
                    repair_context = None
                    research_context = None
                
                # ═══════════════════════════════════════════════════════════════
                # PROFILE B/C: RESEARCH (us_research_safe_harbor, au_strict_oaic)
                # Show: Trial/Subject IDs, Compliance toggles
                # HIDE: Patient Name/Sex/DOB inputs entirely
                # ═══════════════════════════════════════════════════════════════
                else:
                    # Research mode (Safe Harbor or AU Strict)
                    if pacs_operation_mode == "us_research_safe_harbor":
                        st.info("🛡️ **HIPAA Safe Harbor**: All 18 identifiers will be removed or generalized.")
                    else:
                        st.warning("🔒 **AU Strict (OAIC)**: PatientID will be hashed, dates shifted, institution removed.")
                    
                    # Compliance Profile Selection
                    compliance_profile = st.radio(
                        "**Compliance Standard**",
                        options=["safe_harbor", "limited_data_set"],
                        format_func=lambda x: "🛡️ HIPAA Safe Harbor (Strict)" if x == "safe_harbor" else "📅 Limited Data Set (Dates Retained)",
                        index=0,
                        help="Safe Harbor required for public release. LDS allowed for internal research."
                    )
                    
                    col1, col2 = st.columns([1, 1])
                    with col1:
                        research_trial_id = st.text_input("**Trial/Protocol ID**", value="TRIAL-001", placeholder="e.g., LUNG-01")
                        research_site_id = st.text_input("**Site ID**", value="SITE-01", placeholder="e.g., ADL-01")
                    with col2:
                        research_subject_id = st.text_input("**Subject ID**", value="SUB-001", placeholder="e.g., SUB-101")
                        research_time_point = st.selectbox(
                            "**Timepoint/Visit**",
                            options=["Baseline", "Week 1", "Week 2", "Week 4", "Week 8", "Week 12", "Month 3", "Month 6", "Follow-up"],
                            index=0
                        )
                    
                    research_deid_date = st.date_input("**De-identification Date**", value=date.today())
                    
                    # Research toggles
                    col1, col2 = st.columns(2)
                    with col1:
                        exclude_scanned_docs = st.checkbox(
                            "🚫 Exclude Scanned Documents",
                            value=True,  # Default ON for research
                            help="Exclude SC/OT modalities (worksheets)"
                        )
                    with col2:
                        regenerate_uids = st.checkbox("🔄 Regenerate UIDs", value=False, help="Generate new UIDs for each file")
                    
                    research_context = {
                        "trial_id": research_trial_id.strip() or "TRIAL-001",
                        "site_id": research_site_id.strip() or "SITE-01",
                        "subject_id": research_subject_id.strip() or "SUB-001",
                        "time_point": research_time_point,
                        "deid_date": str(research_deid_date)
                    }
                    new_patient_name = research_context["subject_id"]
                    repair_context = None
                    
                
                # ═══════════════════════════════════════════════════════════════
                # RESEARCH FORMAT - NIfTI Export Option (For Research profiles only)
                # ═══════════════════════════════════════════════════════════════
                if pacs_operation_mode in ["us_research_safe_harbor", "au_strict_oaic"]:
                    st.markdown("---")
                    st.markdown("**🔬 Research Format**")
                    
                    output_as_nifti = st.checkbox(
                        "📦 Output as NIfTI (.nii.gz) for AI/ML",
                        value=False,
                        help="Convert anonymized DICOMs to NIfTI format for PyTorch, TensorFlow, MONAI, etc."
                    )
                    
                    if output_as_nifti:
                        st.info("""
                        ℹ️ **AI Readiness**: Converts DICOMs to NIfTI volumes for Machine Learning.
                        
                        🧠 **Smart Conversion**:
                        - **3D Volumes**: Automatic for CT, MRI, PET
                        - **2D Fallback**: Ultrasound/single slices saved individually
                        
                        ⚠️ **Warning**: This **strips most metadata**.
                        ❌ DICOM Viewer will NOT be included (incompatible format).
                        """)
                
                # ═══════════════════════════════════════════════════════════════
                # HTML EXPORT VIEWER (Phase 6 - Presentation only)
                # ═══════════════════════════════════════════════════════════════
                st.markdown("---")
                st.markdown("**🔍 Export Viewer**")
                
                include_html_viewer = st.checkbox(
                    "📄 Include HTML export viewer (view-only navigation)",
                    value=False,
                    help="Adds a view-only HTML viewer and presentation index to the ZIP. Does not modify DICOM."
                )
                
                if include_html_viewer:
                    st.info("""
                    ℹ️ **View-Only Navigation**: Adds a browser-based viewer for convenient image browsing.
                    
                    📋 **Includes**:
                    - Series browser with modality grouping
                    - Stack navigation (prev/next)
                    - PNG previews for web display
                    
                    ⚠️ **Note**: This viewer is for convenience only. It does not represent DICOM structure.
                    """)
                
                # ═══════════════════════════════════════════════════════════════════
                # PHASE 12: RESOLVED SETTINGS SUMMARY
                # Show final resolved settings before Run to prevent "what did I set?" confusion
                # ═══════════════════════════════════════════════════════════════════
                st.markdown("---")
                st.markdown("**📋 Resolved Settings (Before Run)**")
                
                # Derive pixel masking status from bucket contents and review session
                review_session_exists = st.session_state.get('phi_review_session') is not None
                has_maskable_regions = review_session_exists and st.session_state.phi_review_session.get_summary().get('will_mask', 0) > 0
                pixel_mask_status = "ON" if has_maskable_regions else "OFF (no regions defined)"
                
                # Derive patient tags status from profile
                if pacs_operation_mode in ["foi_patient", "foi_legal", "foi_legal_chain"]:
                    patient_tags_status = "PRESERVED (FOI chain of custody)"
                elif pacs_operation_mode == "internal_repair":
                    if uid_only_mode:
                        patient_tags_status = "PRESERVED (UID-only mode)"
                    else:
                        patient_tags_status = "CORRECTED (new values applied)"
                else:  # Research profiles
                    patient_tags_status = "ANONYMISED (research de-identification)"
                
                # UID status (already captured)
                uid_regen_status = "ON" if regenerate_uids else "OFF"
                
                # Display summary in compact format
                summary_html = f"""
                <div style="background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 12px 16px; margin: 8px 0;">
                    <table style="width: 100%; font-size: 13px; color: #c9d1d9;">
                        <tr>
                            <td style="padding: 4px 0;">🎭 <b>Pixel masking:</b></td>
                            <td style="padding: 4px 0; color: {'#238636' if has_maskable_regions else '#8b949e'};">{pixel_mask_status}</td>
                        </tr>
                        <tr>
                            <td style="padding: 4px 0;">📋 <b>Patient tags in DICOM:</b></td>
                            <td style="padding: 4px 0; color: {'#d29922' if 'PRESERVED' in patient_tags_status or 'CORRECTED' in patient_tags_status else '#238636'};">{patient_tags_status}</td>
                        </tr>
                        <tr>
                            <td style="padding: 4px 0;">🔄 <b>UID regeneration:</b></td>
                            <td style="padding: 4px 0; color: {'#238636' if regenerate_uids else '#8b949e'};">{uid_regen_status}</td>
                        </tr>
                    </table>
                </div>
                """
                st.markdown(summary_html, unsafe_allow_html=True)
                
                # Form submit button
                st.markdown("---")
                process_btn = st.form_submit_button(
                    "🚀 Process Selected Files", 
                    use_container_width=True, 
                    type="primary"
                )
            
            # Validation happens AFTER form submission
            can_process = True
            
            # Only require patient name for Internal Repair (unless UID-only mode)
            if pacs_operation_mode == "internal_repair" and not uid_only_mode and not new_patient_name.strip():
                if process_btn:
                    st.warning("⚠️ Please enter a patient name before processing")
                can_process = False
            
            # ═══════════════════════════════════════════════════════════════════
            # EXPORT GATING (PR 5): Require review acceptance for burned-in PHI
            # ═══════════════════════════════════════════════════════════════════
            review_session = st.session_state.get('phi_review_session')
            requires_phi_review = (bucket_us or bucket_docs) and review_session is not None
            
            if requires_phi_review and not review_session.review_accepted:
                if process_btn:
                    st.error("🚫 **Review not accepted.** Please complete the burned-in PHI review and click 'Accept & Continue' before proceeding.")
                can_process = False
            elif requires_phi_review and review_session.review_accepted:
                # Show confirmation that review is complete
                if process_btn:
                    summary = review_session.get_summary()
                    st.success(f"✅ Review accepted: {summary['will_mask']} region(s) to mask, {summary['will_unmask']} override(s) to keep")
            
            if process_btn and can_process:
                # Note: Accession numbers are generated per-file automatically
                st.info("🔄 Accession numbers will be generated per-file based on original values")
                
                # Initialize into Session State
                if 'audit_logger' not in st.session_state:
                    st.session_state.audit_logger = AuditLogger()
                elif st.session_state.audit_logger is None:
                    st.session_state.audit_logger = AuditLogger()
                
                # Build context dictionary based on profile
                if pacs_operation_mode == "internal_repair":
                    # Internal Repair
                    repair_context = {
                        "patient_name": new_patient_name.strip(),
                        "patient_sex": patient_sex,
                        "patient_dob": str(patient_dob) if patient_dob else "",
                        "study_date": str(study_date) if study_date else "",
                        "study_time": str(study_time) if study_time else "",
                        "study_type": study_type,
                        "location": location.strip() if location else "",
                        "gestational_age": gestational_age.strip() if study_type == "OB" and gestational_age else "",
                        "sonographer": sonographer_name.strip() if sonographer_name else "",
                        "referring_physician": referring_physician.strip() if referring_physician else "",
                        "reason_for_correction": reason_for_correction,
                        "correction_notes": correction_notes.strip() if correction_notes else "",
                        "operator_name": operator_name.strip() if operator_name else "",
                        "auto_timestamp": auto_timestamp,
                        "uid_only_mode": uid_only_mode  # If True, preserve patient data but regenerate UIDs
                    }
                    research_context = None
                elif pacs_operation_mode.startswith("foi_"):
                    # FOI mode - no context needed, data preserved from original
                    repair_context = None
                    research_context = None
                else:
                    # Research modes (Safe Harbor, AU Strict)
                    repair_context = None
                    research_context = {
                        "trial_id": research_trial_id.strip() if research_trial_id else "TRIAL-001",
                        "site_id": research_site_id.strip() if research_site_id else "SITE-01",
                        "subject_id": research_subject_id.strip() if research_subject_id else "SUB-001",
                        "time_point": research_time_point,
                        "deid_date": str(research_deid_date)
                    }
                
                # Process all selected files
                # Show VoxelMask loading animation
                loader_placeholder = st.empty()
                loader_placeholder.markdown(f"""
                <div class="voxelmask-loader">
                    <div class="voxel-cube-container">
                        <div class="voxel-cube"></div>
                        <div class="voxel-ring"></div>
                    </div>
                    <div class="voxel-progress-text">Processing {len(all_files)} files...</div>
                    <div class="voxel-progress-subtext">Preparing de-identification engine</div>
                </div>
                """, unsafe_allow_html=True)
                
                processed_files = []
                combined_audit_logs = []
                
                # ═══════════════════════════════════════════════════════════════
                # PHASE 6: Add Selection Scope to Audit Log (NON-NEGOTIABLE)
                # Every run MUST record selection_scope for FOI defensibility
                # ═══════════════════════════════════════════════════════════════
                selection_scope = st.session_state.selection_scope
                scope_audit_block = generate_scope_audit_block(selection_scope)
                combined_audit_logs.append(scope_audit_block)
                
                # ═══════════════════════════════════════════════════════════════
                # PHASE 8: Create Run Context (Operational Hardening 4.2)
                # Single run ID for this entire processing session
                # ═══════════════════════════════════════════════════════════════
                run_id = generate_run_id()
                st.session_state.run_id = run_id
                
                # Determine output root (use downloads directory for now)
                output_root = Path(os.path.dirname(__file__)).parent / "downloads"
                run_paths = build_run_paths(output_root, run_id)
                ensure_run_dirs(run_paths)
                st.session_state.run_paths = run_paths
                
                # Log run context creation (debug, non-PHI)
                print(f"[Phase8] Run context created: {run_id}")
                print(f"[Phase8] Run directory: {run_paths.root}")
                
                # ═══════════════════════════════════════════════════════════════
                # PHASE 8: Write run_status.json stub (4.2.4)
                # Establishes run identity; prepares for fail-safe behaviour
                # ═══════════════════════════════════════════════════════════════
                import json
                from datetime import timezone
                status_path = run_paths.root / "run_status.json"
                status_payload = {
                    "run_id": run_id,
                    "started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "status": "in_progress",
                }
                status_path.write_text(json.dumps(status_payload, indent=2) + "\n", encoding="utf-8")
                print(f"[Phase8] Run status written: {status_path}")
                
                # ═══════════════════════════════════════════════════════════════
                # PHASE 8: Run Preflight Checks (4.1)
                # Fail early on unsafe conditions; update run_status on failure
                # ═══════════════════════════════════════════════════════════════
                try:
                    mode = st.session_state.get("processing_mode") or pacs_operation_mode
                    preflight_result = run_preflight(
                        downloads_dir=Path(os.path.dirname(__file__)).parent / "downloads",
                        run_root=run_paths.root,
                        processing_mode=mode,
                        min_free_bytes=250 * 1024 * 1024,  # 250MB conservative
                        required_modules=("pydicom",),
                    )
                    raise_if_failed(preflight_result)
                    print(f"[Phase8] Preflight: PASS")
                    
                except PreflightError as preflight_err:
                    # Update run_status.json to preflight_failed
                    try:
                        existing_status = json.loads(status_path.read_text(encoding="utf-8"))
                    except Exception:
                        existing_status = {"run_id": run_id, "status": "unknown"}
                    existing_status["status"] = "preflight_failed"
                    status_path.write_text(json.dumps(existing_status, indent=2) + "\n", encoding="utf-8")
                    
                    # Write preflight error log
                    err_path = run_paths.logs_dir / "preflight_error.txt"
                    err_path.write_text(str(preflight_err).strip() + "\n", encoding="utf-8")
                    
                    st.error("🚫 Preflight checks failed. See preflight_error.txt in the run logs folder.")
                    print(f"[Phase8] Preflight: FAILED - {preflight_err}")
                    st.stop()
                
                # ═══════════════════════════════════════════════════════════════
                # PHASE 8: Evidence/Config Capture (4.4)
                # PHI-sterile run receipt; non-fatal warning on failure
                # ═══════════════════════════════════════════════════════════════
                try:
                    receipt = build_run_receipt(
                        run_id=run_id,
                        run_root=run_paths.root,
                        processing_mode=st.session_state.get("processing_mode") or pacs_operation_mode,
                        gateway_profile=st.session_state.get("gateway_profile") or pacs_operation_mode,
                        selection_scope=st.session_state.get("selection_scope"),
                        build_info=_build_stamp(),
                        git_sha="unknown",  # Could extract from _build_stamp if needed
                        preflight_result=preflight_result,
                    )
                    assert_phi_sterile(receipt)
                    receipt_path = write_run_receipt(run_paths.receipts_dir, receipt)
                    print(f"[Phase8] Run receipt written: {receipt_path}")
                except Exception as receipt_err:
                    # Non-fatal: receipt failure must not alter processing semantics
                    warn_path = run_paths.logs_dir / "receipt_warning.txt"
                    warn_path.write_text(f"Receipt capture warning: {receipt_err.__class__.__name__}: {receipt_err}\n", encoding="utf-8")
                    print(f"[Phase8] Receipt warning: {receipt_err}")
                
                # ═══════════════════════════════════════════════════════════════
                # DIAGNOSTIC TRACKING - Start timer and byte counter
                # ═══════════════════════════════════════════════════════════════
                import time
                processing_start_time = time.time()
                # Calculate total input bytes - handle both UploadedFile (.size) and BytesIO (len(getbuffer()))
                total_input_bytes = sum(
                    getattr(f, 'size', len(f.getbuffer()) if hasattr(f, 'getbuffer') else 0)
                    for f in all_files
                )
                total_output_bytes = 0
                
                # Progress bar for multi-file processing
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                for i, file_buffer in enumerate(all_files):
                    # ═══════════════════════════════════════════════════════════════
                    # STEP 1: SAFE DEFAULT INITIALIZATION (The "Waterfall" Pattern)
                    # All variables defined here BEFORE any conditional logic
                    # This prevents UnboundLocalError crashes
                    # ═══════════════════════════════════════════════════════════════
                    
                    # Processing state defaults
                    success = False
                    apply_mask = False
                    compliance_log_entry = f"Compliance: {pacs_operation_mode}"  # Safe default
                    compliance_info = {'log': []}  # Safe default for compliance engine output
                    audit_log = ""  # Will be populated later
                    
                    # File path defaults (will be overwritten)
                    input_path = None
                    output_path = None
                    
                    # Metadata defaults - read from file or use safe fallbacks
                    original_name = "UNKNOWN"
                    verification_ds = None
                    
                    # --- UNIVERSAL LOGGER SETUP (Fixes NameError for CT/MR/XR) ---
                    # Ensure local variable 'audit_logger' exists for this specific file iteration
                    if 'audit_logger' in st.session_state and st.session_state.audit_logger:
                        audit_logger = st.session_state.audit_logger
                    else:
                        audit_logger = AuditLogger()
                        st.session_state.audit_logger = audit_logger
                    # ═══════════════════════════════════════════════════════════════
                    
                    try:
                        # Update progress with percentage
                        progress = (i) / len(all_files)
                        percent = int(progress * 100)
                        progress_bar.progress(progress)
                        status_text.markdown(f"**{percent}%** — Processing file {i+1}/{len(all_files)}: `{file_buffer.name}`")
                        
                        # Update loader text dynamically
                        loader_placeholder.markdown(f"""
                        <div class="voxelmask-loader">
                            <div class="voxel-cube-container">
                                <div class="voxel-cube"></div>
                                <div class="voxel-ring"></div>
                            </div>
                            <div class="voxel-progress-text">{percent}% Complete</div>
                            <div class="voxel-progress-subtext">Processing file {i+1} of {len(all_files)}</div>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        # Create temp input file
                        input_tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".dcm")
                        input_tmp.write(file_buffer.getbuffer())
                        input_path = input_tmp.name
                        input_tmp.close()
                        
                        # ═══════════════════════════════════════════════════════════════
                        # EXTRACT ORIGINAL METADATA (Before any processing!)
                        # For FOI mode, we need the ORIGINAL StudyDate and AccessionNumber
                        # ═══════════════════════════════════════════════════════════════
                        original_ds = pydicom.dcmread(input_path, stop_before_pixels=True, force=True)
                        
                        # Extract StudyDate (0008,0020) - format nicely if possible
                        orig_study_date = "Unknown"
                        if hasattr(original_ds, 'StudyDate') and original_ds.StudyDate:
                            try:
                                sd_str = str(original_ds.StudyDate)
                                if len(sd_str) == 8 and sd_str.isdigit():
                                    orig_study_date = f"{sd_str[0:4]}-{sd_str[4:6]}-{sd_str[6:8]}"  # YYYY-MM-DD
                                else:
                                    orig_study_date = sd_str
                            except Exception:
                                orig_study_date = str(original_ds.StudyDate)
                        
                        # Extract AccessionNumber (0008,0050)
                        orig_accession = "Unknown"
                        if hasattr(original_ds, 'AccessionNumber') and original_ds.AccessionNumber:
                            orig_accession = str(original_ds.AccessionNumber).strip()
                            if not orig_accession:
                                orig_accession = "Unknown"
                        
                        # Extract Modality for reference
                        orig_modality = str(getattr(original_ds, 'Modality', 'Unknown')).upper()
                        
                        # Create temp output file
                        output_tmp = tempfile.NamedTemporaryFile(delete=False, suffix="_anonymized.dcm")
                        output_path = output_tmp.name
                        output_tmp.close()
                        
                        # Get original name for this file
                        original_name = get_original_name(input_path)
                        
                        # Determine if masking should be applied (only for US files)
                        apply_mask = file_buffer in bucket_us and manual_box is not None
                        
                        # Process the file
                        # CRITICAL: FOI mode must PRESERVE patient data - only redact staff names
                        # So we bypass general anonymization and copy the original file
                        success = False
                        is_foi_mode = pacs_operation_mode in ["foi_legal", "foi_patient"]
                        
                        if is_foi_mode:
                            # FOI MODE: Copy original file as-is - FOI engine handles staff redaction
                            # Patient data (name, ID, DOB, accession) MUST be preserved for legal compliance
                            import shutil
                            shutil.copy2(input_path, output_path)
                            success = True
                        elif mode == "Research De-ID":
                            config = AnonymizationConfig(compliance_profile=compliance_profile)
                            anonymizer = DicomAnonymizer(config)
                            result = anonymizer.anonymize_file(input_path, output_path)
                            success = result.success
                        elif repair_context and repair_context.get('uid_only_mode', False):
                            # ═══════════════════════════════════════════════════════════════════
                            # UID-ONLY MODE: Metadata-only path (Phase 3 Pixel Invariant)
                            # ═══════════════════════════════════════════════════════════════════
                            # CRITICAL: This path ensures:
                            #   - NO pixel decode
                            #   - NO AI detection
                            #   - NO overlay generation
                            #   - NO black boxes
                            #   - PixelData bytes are IDENTICAL to input
                            #
                            # Only UIDs (SOP/Series/Study Instance UIDs) are regenerated.
                            # Patient data (name, ID, DOB, dates, accession) is PRESERVED.
                            # ═══════════════════════════════════════════════════════════════════
                            import pydicom
                            from run_on_dicom import process_dataset
                            from pixel_invariant import PixelAction, validate_uid_only_output, sha256_bytes
                            
                            # Read original dataset
                            ds = pydicom.dcmread(input_path)
                            
                            # Capture baseline pixel hash for invariant check
                            baseline_hash = None
                            if hasattr(ds, 'PixelData') and ds.PixelData:
                                baseline_hash = sha256_bytes(ds.PixelData)
                            
                            # Keep a reference to original PixelData (defensive copy not needed
                            # since process_dataset won't modify it in uid_only_mode)
                            original_pixel_data = ds.PixelData if hasattr(ds, 'PixelData') else None
                            
                            # Process metadata only (no pixel processing)
                            audit_dict = {}
                            process_dataset(
                                ds,
                                old_name_text=original_name,
                                new_name_text="PRESERVED",  # Marker - actual patient name preserved
                                clinical_context=repair_context,
                                audit_dict=audit_dict,
                            )
                            
                            # PHASE 3 INVARIANT CHECK: Verify PixelData unchanged
                            if baseline_hash is not None and hasattr(ds, 'PixelData') and ds.PixelData:
                                current_hash = sha256_bytes(ds.PixelData)
                                if current_hash != baseline_hash:
                                    raise RuntimeError(
                                        f"FATAL: UID-only mode pixel invariant violated! "
                                        f"PixelData hash changed from {baseline_hash[:16]}... to {current_hash[:16]}... "
                                        f"This should never happen. Aborting export."
                                    )
                            
                            # Save with original Transfer Syntax preserved
                            ds.save_as(output_path, write_like_original=True)
                            success = True
                            
                            # Log the UID-only processing
                            print(f"[UID-ONLY] Metadata-only processing complete for {os.path.basename(input_path)}")
                            print(f"[UID-ONLY] pixel_action={audit_dict.get('pixel_action', 'N/A')}, "
                                  f"pixel_invariant={audit_dict.get('pixel_invariant', 'N/A')}")
                        else:
                            # Full pixel pipeline - ONLY when masking is actually requested
                            success = process_dicom(
                                input_path=input_path,
                                output_path=output_path,
                                old_name_text=original_name,
                                new_name_text=new_patient_name.strip(),
                                manual_box=manual_box if apply_mask else None,
                                research_context=research_context,
                                clinical_context=repair_context
                            )
                        
                        if success:
                            # VERIFICATION STEP: Read the file we just wrote to disk
                            # This guarantees the log matches the output file 100%
                            # Force a sync to ensure the file is fully written
                            import os
                            if hasattr(os, 'sync'):
                                os.sync()
                            
                            # Read back the saved file to get the final dataset
                            verification_ds = pydicom.dcmread(output_path)
                            
                            # ═══════════════════════════════════════════════════════════════
                            # ROUTING: FOI vs COMPLIANCE ENGINE
                            # ═══════════════════════════════════════════════════════════════
                            if pacs_operation_mode.startswith("foi_"):
                                # FOI MODE: Use FOI Engine (preserves patient data, redacts staff)
                                foi_mode = "legal" if pacs_operation_mode == "foi_legal" else "patient"
                                verification_ds, foi_result = process_foi_request(
                                    dataset=verification_ds,
                                    mode=foi_mode,
                                    exclude_scanned=exclude_scanned_docs,
                                    redact_referring=False  # Keep referring physician for legal
                                )
                                
                                # Build compliance_info from FOI result
                                compliance_info = {
                                    'log': [f"FOI Mode: {foi_mode}"] + [f"{r['tag']}: {r['action']}" for r in foi_result.redactions],
                                    'foi_result': foi_result,
                                    'foi_mode': foi_mode
                                }
                                
                                if foi_result.excluded_files:
                                    compliance_log_entry = f"Compliance: FOI ({foi_mode}) | EXCLUDED (Scanned Doc)"
                                else:
                                    compliance_log_entry = f"Compliance: FOI ({foi_mode}) | {len(foi_result.redactions)} redactions"
                            else:
                                # STANDARD: Use Compliance Engine
                                compliance_manager = DicomComplianceManager()
                                verification_ds, compliance_info = compliance_manager.process_dataset(
                                    dataset=verification_ds,
                                    profile_mode=pacs_operation_mode,
                                    fix_uids=regenerate_uids
                                )
                                
                                # Log compliance processing info (only for non-FOI modes)
                                compliance_log_entry = f"Compliance: {pacs_operation_mode}"
                                if regenerate_uids:
                                    compliance_log_entry += " | UIDs Regenerated"
                                if compliance_info.get('date_shift_days'):
                                    compliance_log_entry += f" | Date Shift: {compliance_info['date_shift_days']} days"
                            # ═══════════════════════════════════════════════════════════════
                            
                            # Save the processed dataset back to disk
                            verification_ds.save_as(output_path)
                            
                            # Read processed file for download (now includes compliance changes)
                            with open(output_path, "rb") as f:
                                processed_data = f.read()
                            
                            # Generate filename for this file
                            if mode == "Internal Repair":
                                file_filename = generate_repair_filename(
                                    file_buffer.name,
                                    new_patient_name.strip(),
                                    get_original_metadata(input_path).get('series_description', 'Scan')
                                )
                            elif is_foi_mode:
                                # FOI MODE: Preserve original filename (legal chain of custody requirement)
                                # Patient data is NOT anonymized in FOI mode
                                file_filename = file_buffer.name
                            else:
                                file_filename = f"ANONYMIZED_{file_buffer.name}"
                            
                            # === FOLDER STRUCTURE FOR AI TRAINING ===
                            # Extract Study and Series info for proper hierarchy
                            # Format: StudyDescription_Modality/SeriesNumber_SeriesDescription/filename.dcm
                            try:
                                study_desc = str(getattr(verification_ds, 'StudyDescription', '')).strip() or 'UnknownStudy'
                                series_desc = str(getattr(verification_ds, 'SeriesDescription', '')).strip() or 'UnknownSeries'
                                modality = str(getattr(verification_ds, 'Modality', '')).upper() or 'UNK'
                                series_num = str(getattr(verification_ds, 'SeriesNumber', '0')).zfill(3)
                                instance_num = str(getattr(verification_ds, 'InstanceNumber', '0')).zfill(4)
                                
                                # Sanitize folder names (remove special chars)
                                import re
                                study_folder = re.sub(r'[^\w\s-]', '', study_desc)[:50].strip() or 'Study'
                                study_folder = f"{study_folder}_{modality}"
                                series_folder = re.sub(r'[^\w\s-]', '', series_desc)[:40].strip() or 'Series'
                                series_folder = f"S{series_num}_{series_folder}"
                                
                                # Create hierarchical path
                                folder_path = f"{study_folder}/{series_folder}"
                                
                                # Add instance number to filename for proper sorting
                                base_name = file_filename.rsplit('.', 1)[0] if '.' in file_filename else file_filename
                                file_filename = f"IMG_{instance_num}_{base_name}.dcm"
                                
                            except Exception as e:
                                # Fallback to flat structure if metadata extraction fails
                                folder_path = "Processed"
                            
                            # ═══════════════════════════════════════════════════════════════
                            # CALCULATE SHA-256 HASHES FOR FORENSIC INTEGRITY (FOI Legal)
                            # ═══════════════════════════════════════════════════════════════
                            original_file_hash = hashlib.sha256(file_buffer.getbuffer()).hexdigest()
                            processed_file_hash = hashlib.sha256(processed_data).hexdigest()
                            
                            # Store processed file data with folder path
                            processed_files.append({
                                'filename': file_filename,
                                'folder_path': folder_path,
                                'full_path': f"{folder_path}/{file_filename}",
                                'data': processed_data,
                                'original_name': file_buffer.name,
                                'modality': modality if 'modality' in dir() else orig_modality,
                                'series_number': series_num if 'series_num' in dir() else '000',
                                # Original metadata for FOI PDF reports
                                'study_date': orig_study_date,
                                'accession': orig_accession,
                                # SHA-256 hashes for Forensic Integrity Certificate (FOI Legal)
                                'original_hash': original_file_hash,
                                'processed_hash': processed_file_hash
                            })
                            
                            # Generate audit log with verified dataset
                            scrub_uuid = audit_logger.generate_scrub_uuid()
                            
                            # Format Study Date if present (handle both original and shifted dates)
                            actual_study_date = ""
                            if hasattr(verification_ds, 'StudyDate') and verification_ds.StudyDate:
                                try:
                                    sd_str = str(verification_ds.StudyDate)
                                    if len(sd_str) == 8 and sd_str.isdigit():
                                        actual_study_date = f"{sd_str[6:8]}/{sd_str[4:6]}/{sd_str[0:4]}"
                                    else:
                                        actual_study_date = sd_str
                                except Exception:
                                    actual_study_date = str(verification_ds.StudyDate)
                            
                            new_meta = {
                                'patient_name': str(verification_ds.PatientName) if hasattr(verification_ds, 'PatientName') else 'ANONYMIZED',
                                'patient_id': str(verification_ds.PatientID) if hasattr(verification_ds, 'PatientID') else 'ANONYMIZED',
                                # FOI mode and Internal Repair preserve accession for chain of custody/workflow
                                'accession': (str(verification_ds.AccessionNumber) if hasattr(verification_ds, 'AccessionNumber') and verification_ds.AccessionNumber else orig_accession) if (is_foi_mode or pacs_operation_mode == "internal_repair") else 'REMOVED',
                                'study_date': actual_study_date or 'DATE_MISSING'
                            }
                            audit_log = generate_audit_receipt(
                                original_meta=get_original_metadata(input_path),
                                new_meta=new_meta,
                                uuid_str=scrub_uuid,
                                operator_id="WEBAPP_USER",
                                mode=mode.split()[0],
                                filename=file_buffer.name,
                                mask_applied=apply_mask,
                                original_file_hash=original_file_hash,  # Use pre-calculated hash
                                anonymized_file_hash=processed_file_hash,  # Use pre-calculated hash
                                safety_notification=None,
                                compliance_profile=pacs_operation_mode,  # Use PACS operation mode
                                pixel_action_reason=(f"Batch mask applied | {compliance_log_entry}" if apply_mask else compliance_log_entry),
                                dataset=verification_ds,
                                is_foi_mode=is_foi_mode,
                                foi_redactions=compliance_info.get('foi_result', {}).redactions if is_foi_mode and compliance_info.get('foi_result') else None
                            )
                        
                        # Append compliance processing log to audit
                        if 'compliance_info' in dir() and compliance_info.get('log'):
                            audit_log += f"\n\n--- Compliance Engine Log ---\n" + "\n".join(compliance_info['log'])
                        
                        combined_audit_logs.append(audit_log)
                        
                        # Clean up temp files
                        try:
                            os.unlink(input_path)
                            os.unlink(output_path)
                        except:
                            pass
                            
                    except Exception as e:
                        st.error(f"Error processing {file_buffer.name}: {e}")
                
                # Complete progress
                progress_bar.progress(1.0)
                status_text.markdown("**100%** — Processing complete! ✅")
                
                # Clear the loader and show completion
                loader_placeholder.markdown(f"""
                <div class="voxelmask-loader" style="background: linear-gradient(135deg, rgba(35, 134, 54, 0.15) 0%, rgba(51, 145, 255, 0.05) 100%); border-color: rgba(35, 134, 54, 0.4);">
                    <div class="voxel-cube-container">
                        <div class="voxel-cube" style="background: linear-gradient(135deg, #238636 0%, #3391ff 100%);"></div>
                    </div>
                    <div class="voxel-progress-text" style="color: #238636;">✅ Complete!</div>
                    <div class="voxel-progress-subtext">All {len(all_files)} files processed successfully</div>
                </div>
                """, unsafe_allow_html=True)
                
                # Store results in session state
                if processed_files:
                    st.session_state.processed_files = processed_files
                    st.session_state.combined_audit_logs = "\n\n".join(combined_audit_logs)
                    st.session_state.processing_complete = True
                    
                    # ═══════════════════════════════════════════════════════════════
                    # PHASE 8: Mark run completed (4.5)
                    # ═══════════════════════════════════════════════════════════════
                    try:
                        if run_paths:
                            update_run_status(
                                run_paths.root,
                                status="completed",
                                timestamp_field="completed_at",
                            )
                            print(f"[Phase8] Run status: completed")
                    except Exception:
                        pass  # Non-fatal
                    
                    # ═══════════════════════════════════════════════════════════════
                    # DIAGNOSTIC STATS - Calculate processing metrics
                    # ═══════════════════════════════════════════════════════════════
                    processing_end_time = time.time()
                    processing_duration = processing_end_time - processing_start_time
                    
                    # Calculate output bytes from processed files
                    for pf in processed_files:
                        if 'output_bytes' in pf:
                            total_output_bytes += pf.get('output_bytes', 0)
                    
                    st.session_state.processing_stats = {
                        'duration_seconds': processing_duration,
                        'file_count': len(processed_files),
                        'input_bytes': total_input_bytes,
                        'output_bytes': total_output_bytes,
                        'files_per_second': len(processed_files) / processing_duration if processing_duration > 0 else 0,
                        'mb_per_second': (total_input_bytes / (1024 * 1024)) / processing_duration if processing_duration > 0 else 0,
                        'profile': pacs_operation_mode,
                        'timestamp': datetime.now().isoformat()
                    }
                    
                    # Create ZIP file for bulk download WITH FOLDER STRUCTURE
                    import io
                    import re
                    zip_buffer = io.BytesIO()
                    
                    # ═══════════════════════════════════════════════════════════════
                    # SMART NAMING: Use meaningful identifiers for easy identification
                    # Priority: StudyID > AccessionNumber > PatientName > Fallback
                    # ═══════════════════════════════════════════════════════════════
                    root_folder_raw = None
                    
                    # Try to get metadata from first processed file for naming
                    first_file_meta = processed_files[0] if processed_files else {}
                    
                    if pacs_operation_mode and pacs_operation_mode.startswith('foi_'):
                        # FOI MODE: Use AccessionNumber or StudyDate for legal traceability
                        accession = first_file_meta.get('accession', '')
                        study_date = first_file_meta.get('study_date', '')
                        
                        if accession and accession not in ['Unknown', 'N/A', '']:
                            root_folder_raw = f"FOI_{accession}"
                        elif study_date and study_date not in ['Unknown', 'N/A', '']:
                            root_folder_raw = f"FOI_{study_date.replace('-', '')}"
                        else:
                            root_folder_raw = f"FOI_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                    
                    elif repair_context:
                        # REPAIR MODE: Use patient name (this is an internal repair)
                        patient_name = repair_context.get('patient_name', '')
                        uid_only = repair_context.get('uid_only_mode', False)
                        
                        if uid_only:
                            # In UID-only mode, get original patient name from first file
                            original_name = first_file_meta.get('patient_name', '')
                            root_folder_raw = f"UID_Regen_{original_name}" if original_name else f"UID_Regen_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                        elif patient_name and patient_name != "PRESERVED":
                            root_folder_raw = patient_name
                        else:
                            root_folder_raw = f"Repair_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                    
                    elif research_context:
                        # RESEARCH MODE: Use subject_id + trial_id (de-identified)
                        subject_id = research_context.get('subject_id', 'SUB')
                        trial_id = research_context.get('trial_id', 'TRIAL')
                        root_folder_raw = f"{subject_id}_{trial_id}"
                    
                    else:
                        # FALLBACK: Try to extract from first file's modality + study date
                        modality = first_file_meta.get('modality', 'DICOM')
                        study_date = first_file_meta.get('study_date', '')
                        
                        if study_date and study_date not in ['Unknown', 'N/A', '']:
                            root_folder_raw = f"{modality}_{study_date.replace('-', '')}"
                        else:
                            root_folder_raw = f"{modality}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                    
                    # Sanitize folder name (remove invalid chars, replace spaces with underscores)
                    root_folder = re.sub(r'[<>:"/\\|?*]', '', root_folder_raw)
                    root_folder = root_folder.replace(' ', '_').replace('^', '_').strip('_')
                    if not root_folder:
                        root_folder = f"VoxelMask_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                    
                    # Store root_folder for download filename
                    st.session_state.output_folder_name = root_folder
                    
                    # Collect unique folders for summary
                    unique_studies = set()
                    unique_series = set()
                    
                    # ═══════════════════════════════════════════════════════════════
                    # NIFTI CONVERSION PIPELINE
                    # ═══════════════════════════════════════════════════════════════
                    nifti_conversion_attempted = False
                    nifti_conversion_success = False
                    nifti_result = None
                    
                    if output_as_nifti:
                        nifti_conversion_attempted = True
                        status_text.markdown("**Converting to NIfTI format...**")
                        
                        # Create temp directories for DICOM staging and NIfTI output
                        temp_dicom_dir = tempfile.mkdtemp(prefix="voxelmask_dicom_")
                        temp_nifti_dir = tempfile.mkdtemp(prefix="voxelmask_nifti_")
                        
                        try:
                            # Stage all processed DICOMs to temp folder (maintaining structure)
                            for file_info in processed_files:
                                folder_path = file_info.get('folder_path', 'Processed')
                                full_folder = os.path.join(temp_dicom_dir, folder_path)
                                os.makedirs(full_folder, exist_ok=True)
                                
                                dcm_path = os.path.join(full_folder, file_info['filename'])
                                with open(dcm_path, 'wb') as f:
                                    f.write(file_info['data'])
                                
                                # Track for summary
                                if '/' in folder_path:
                                    study, series = folder_path.split('/', 1)
                                    unique_studies.add(study)
                                    unique_series.add(folder_path)
                                else:
                                    unique_studies.add(folder_path)
                            
                            # Attempt NIfTI conversion
                            nifti_result = convert_dataset_to_nifti(
                                dicom_input_folder=temp_dicom_dir,
                                nifti_output_folder=temp_nifti_dir,
                                compression=True,
                                reorient=True
                            )
                            
                            nifti_conversion_success = nifti_result.success
                            
                            if nifti_conversion_success:
                                # Show mode (3D volumetric or 2D fallback)
                                mode_label = "3D volumetric" if nifti_result.mode == "3D" else "2D slice-by-slice"
                                status_text.markdown(f"**NIfTI conversion successful!** {len(nifti_result.converted_files)} files ({mode_label})")
                                
                                # ZIP the NIfTI files
                                with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                                    for nifti_path in nifti_result.converted_files:
                                        nifti_filename = os.path.basename(nifti_path)
                                        zip_path = f"{root_folder}/{nifti_filename}"
                                        with open(nifti_path, 'rb') as f:
                                            zip_file.writestr(zip_path, f.read())
                                    
                                    # Add NIfTI-specific README
                                    nifti_readme = generate_nifti_readme(
                                        conversion_result=nifti_result,
                                        original_mode=mode,
                                        compliance_profile=pacs_operation_mode
                                    )
                                    zip_file.writestr(f"{root_folder}/README_NIfTI.txt", nifti_readme)
                                    
                                    # Add audit log (with NIfTI conversion details and quality audit)
                                    nifti_audit_note = f"\n\n--- NIfTI Conversion ---\nFormat: NIfTI (.nii.gz)\nConversion Mode: {nifti_result.mode}\nFiles Created: {len(nifti_result.converted_files)}\nDICOM Viewer: NOT INCLUDED (incompatible with NIfTI)\n"
                                    
                                    # Add quality audit if available
                                    if nifti_result.quality_audit:
                                        retention, status = nifti_result.quality_audit.calculate_retention()
                                        nifti_audit_note += f"\n--- Quality Audit ---\n"
                                        nifti_audit_note += f"Input DICOMs: {nifti_result.quality_audit.input_dicom_count}\n"
                                        nifti_audit_note += f"Input Frames: {nifti_result.quality_audit.input_frame_count}\n"
                                        nifti_audit_note += f"Output Slices: {nifti_result.quality_audit.output_slice_count}\n"
                                        nifti_audit_note += f"Quality Check: {status}\n"
                                    
                                    if nifti_result.warnings:
                                        nifti_audit_note += "\nConversion Log:\n" + "\n".join(f"  - {w}" for w in nifti_result.warnings) + "\n"
                                    full_audit = st.session_state.combined_audit_logs + nifti_audit_note
                                    zip_file.writestr(f"{root_folder}/VoxelMask_AuditLog.txt", full_audit)
                                    
                                    # NOTE: DICOM Viewer is NOT included for NIfTI output
                            else:
                                # NIfTI conversion failed - fall back to DICOM
                                status_text.markdown("**⚠️ NIfTI conversion failed - falling back to DICOM output**")
                                st.warning(f"NIfTI conversion failed: {nifti_result.error_message}. Outputting as DICOM instead.")
                                
                        except Exception as nifti_error:
                            nifti_conversion_success = False
                            st.warning(f"NIfTI conversion error: {nifti_error}. Falling back to DICOM output.")
                        
                        finally:
                            # Clean up temp directories
                            try:
                                shutil.rmtree(temp_dicom_dir, ignore_errors=True)
                                shutil.rmtree(temp_nifti_dir, ignore_errors=True)
                            except:
                                pass
                    
                    # ═══════════════════════════════════════════════════════════════
                    # STANDARD DICOM ZIP (if NIfTI not requested or failed)
                    # ═══════════════════════════════════════════════════════════════
                    if not output_as_nifti or not nifti_conversion_success:
                        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                            for file_info in processed_files:
                                # Use full_path if available, otherwise fallback to filename
                                original_path = file_info.get('full_path', file_info['filename'])
                                # Wrap in root folder
                                zip_path = f"{root_folder}/{original_path}"
                                zip_file.writestr(zip_path, file_info['data'])
                                
                                # ═══════════════════════════════════════════════════════════════
                                # PHASE 6: PNG PREVIEW FOR HTML VIEWER (Presentation only)
                                # ═══════════════════════════════════════════════════════════════
                                if include_html_viewer:
                                    try:
                                        # Only render PNG for image modalities
                                        modality = file_info.get('modality', '')
                                        if modality.upper() in ['US', 'CT', 'MR', 'DX', 'CR', 'MG', 'XA', 'RF', 'NM', 'PT']:
                                            png_bytes = render_dicom_bytes_to_png(file_info['data'])
                                            if png_bytes:
                                                # Write PNG adjacent to DICOM (same path, .png extension)
                                                png_zip_path = zip_path.rsplit('.', 1)[0] + '.png'
                                                zip_file.writestr(png_zip_path, png_bytes)
                                    except Exception:
                                        # Silent skip - viewer.js will show "Image unavailable" if missing
                                        pass
                                
                                # Track folder structure for summary
                                folder_path = file_info.get('folder_path', 'Processed')
                                if '/' in folder_path:
                                    study, series = folder_path.split('/', 1)
                                    unique_studies.add(study)
                                    unique_series.add(folder_path)
                                else:
                                    unique_studies.add(folder_path)
                            
                            # Add combined audit log inside root folder
                            audit_content = st.session_state.combined_audit_logs
                            
                            # Add fallback warning if NIfTI was attempted but failed
                            if nifti_conversion_attempted and not nifti_conversion_success and nifti_result:
                                fallback_warning = generate_fallback_warning_file(
                                    error_message=nifti_result.error_message or "Unknown error",
                                    warnings=nifti_result.warnings
                                )
                                zip_file.writestr(f"{root_folder}/NIFTI_CONVERSION_FAILED.txt", fallback_warning)
                                audit_content += f"\n\n--- NIfTI Conversion Failed ---\n{nifti_result.error_message}\nOutput: DICOM (fallback)\n"
                            
                            # ═══════════════════════════════════════════════════════════════
                            # PDF REPORT GENERATION (Replaces Text Audit Log)
                            # ═══════════════════════════════════════════════════════════════
                            try:
                                # Determine report type based on operation mode
                                if pacs_operation_mode == "internal_repair":
                                    report_type = "INTERNAL_REPAIR"
                                    pdf_filename = "VoxelMask_DataRepairLog.pdf"
                                elif pacs_operation_mode == "us_research_safe_harbor":
                                    report_type = "RESEARCH"
                                    pdf_filename = "VoxelMask_SafeHarborCertificate.pdf"
                                elif pacs_operation_mode == "au_strict_oaic":
                                    report_type = "STRICT"
                                    pdf_filename = "VoxelMask_OAIC_PrivacyAudit.pdf"
                                elif pacs_operation_mode == "foi_legal":
                                    report_type = "FOI_LEGAL"
                                    pdf_filename = "VoxelMask_ForensicCertificate.pdf"
                                elif pacs_operation_mode == "foi_patient":
                                    report_type = "FOI_PATIENT"
                                    pdf_filename = "VoxelMask_PatientRelease.pdf"
                                else:
                                    report_type = "INTERNAL_REPAIR"
                                    pdf_filename = "VoxelMask_Report.pdf"
                                
                                # Build PDF data dictionary from session state
                                pdf_data = {
                                    'patient_name': root_folder_raw,
                                    'file_count': len(processed_files),
                                    'timestamp': datetime.now().isoformat(),
                                    'uuid': st.session_state.audit_logger.generate_scrub_uuid() if hasattr(st.session_state, 'audit_logger') else 'N/A',
                                    'operator': 'WEBAPP_USER',
                                    'mask_applied': any(f.get('mask_applied') for f in processed_files) if processed_files else False,
                                    'uids_regenerated': regenerate_uids,
                                    'original_hash': processed_files[0].get('original_hash', 'N/A')[:32] if processed_files else 'N/A',
                                    'processed_hash': processed_files[0].get('processed_hash', 'N/A')[:32] if processed_files else 'N/A',
                                }
                                
                                # ═══════════════════════════════════════════════════════════════
                                # REVIEWER ACTION SUMMARY (PR 5 - counts only, no PHI)
                                # ═══════════════════════════════════════════════════════════════
                                phi_review = st.session_state.get('phi_review_session')
                                if phi_review is not None and phi_review.review_accepted:
                                    review_summary = phi_review.get_summary()
                                    pdf_data['reviewer_summary'] = {
                                        'reviewed': True,
                                        'ocr_regions': review_summary['ocr_regions'],
                                        'manual_regions': review_summary['manual_regions'],
                                        'will_mask': review_summary['will_mask'],
                                        'will_unmask': review_summary['will_unmask'],
                                        'total_regions': review_summary['total_regions']
                                    }
                                
                                # Add mode-specific data
                                if report_type == "RESEARCH":
                                    pdf_data.update({
                                        'subject_id': research_context.get('subject_id', 'SUB-001') if research_context else 'SUB-001',
                                        'trial_id': research_context.get('trial_id', 'TRIAL-001') if research_context else 'TRIAL-001',
                                        'site_id': research_context.get('site_id', 'SITE-01') if research_context else 'SITE-01',
                                        'time_point': research_context.get('time_point', 'Baseline') if research_context else 'Baseline',
                                        'pixel_masked': pdf_data['mask_applied']
                                    })
                                elif report_type == "STRICT":
                                    pdf_data.update({
                                        'hashed_patient_id': 'SHA256_' + hashlib.sha256(root_folder_raw.encode()).hexdigest()[:24],
                                        'date_shift_days': compliance_info.get('date_shift_days', '-14 to -100') if compliance_info else '-14 to -100'
                                    })
                                elif report_type.startswith("FOI"):
                                    # Map FOI UI inputs to PDF template fields
                                    # reference_number -> used for "Reference: X" line
                                    # recipient -> used for "Dear X" greeting
                                    # patient_name -> used for letter header (already in base pdf_data)
                                    pdf_data.update({
                                        'case_reference': foi_case_ref or f"FOI-{datetime.now().strftime('%Y%m%d')}",
                                        'reference_number': foi_case_ref or f"FOI-{datetime.now().strftime('%Y%m%d')}",  # Maps to "Reference:" line
                                        'recipient': foi_recipient or (foi_requesting_party if foi_requesting_party else root_folder_raw),  # Maps to "Dear X"
                                        'requesting_party': foi_requesting_party or 'N/A',
                                        'facility_name': foi_facility_name or 'Medical Imaging Department',
                                        'signatory_name': foi_signatory or 'Health Records Officer',
                                        'signatory_title': 'Health Information Services',
                                        'request_date': datetime.now().strftime('%Y-%m-%d'),
                                        'files': [{'name': f['filename'], 'original_hash': f.get('original_hash', 'N/A'), 'processed_hash': f.get('processed_hash', 'N/A')} for f in processed_files[:10]],
                                        'redactions': compliance_info.get('foi_result', {}).redactions if compliance_info and hasattr(compliance_info.get('foi_result', {}), 'redactions') else []
                                    })
                                    if report_type == "FOI_PATIENT":
                                        # Get metadata from foi_result (extracted in foi_engine.py)
                                        # or fall back to processed_files if available
                                        foi_result = compliance_info.get('foi_result') if compliance_info else None
                                        pdf_data.update({
                                            'study_date': (
                                                foi_result.study_date if foi_result and hasattr(foi_result, 'study_date') and foi_result.study_date != "Unknown"
                                                else processed_files[0].get('study_date', 'Unknown') if processed_files 
                                                else 'Unknown'
                                            ),
                                            'modality': (
                                                foi_result.modality if foi_result and hasattr(foi_result, 'modality') and foi_result.modality != "Unknown"
                                                else processed_files[0].get('modality', 'Unknown') if processed_files 
                                                else 'Unknown'
                                            ),
                                            'accession': (
                                                foi_result.accession if foi_result and hasattr(foi_result, 'accession') and foi_result.accession != "Unknown"
                                                else processed_files[0].get('accession', 'Unknown') if processed_files 
                                                else 'Unknown'
                                            ),
                                            'included_items': [
                                                f"{len(processed_files)} DICOM image file(s)",
                                                "DICOM Viewer application (HTML)",
                                                "This cover letter"
                                            ]
                                        })
                                
                                # Generate PDF
                                pdf_bytes = create_report(report_type, pdf_data)
                                zip_file.writestr(f"{root_folder}/{pdf_filename}", pdf_bytes)
                                
                            except Exception as pdf_error:
                                # Fallback to text if PDF fails
                                st.warning(f"PDF generation failed ({pdf_error}), using text log instead.")
                                zip_file.writestr(f"{root_folder}/VoxelMask_AuditLog.txt", audit_content)
                            
                            # Also include text log as backup (for machine parsing)
                            zip_file.writestr(f"{root_folder}/VoxelMask_AuditLog.txt", audit_content)
                            
                            # Add a README with structure info inside root folder
                            readme_content = f"""VoxelMask Processing Summary
=============================
Patient/Subject: {root_folder_raw}
Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Files Processed: {len(processed_files)}
Unique Studies: {len(unique_studies)}
Unique Series: {len(unique_series)}

Folder Structure:
-----------------
This archive is organized for easy PACS upload:

  {root_folder}/
    └── StudyDescription_Modality/
          └── S###_SeriesDescription/
                └── IMG_####_filename.dcm

Simply drag the "{root_folder}" folder to your PACS import.

Studies in this archive:
{chr(10).join('  • ' + s for s in sorted(unique_studies))}
"""
                            zip_file.writestr(f"{root_folder}/README.txt", readme_content)
                            
                            # Add DICOM Viewer for easy verification inside root folder
                            # (Only for DICOM output, not NIfTI)
                            viewer_path = os.path.join(os.path.dirname(__file__), 'assets', 'dicom_viewer.html')
                            if os.path.exists(viewer_path):
                                with open(viewer_path, 'r', encoding='utf-8') as f:
                                    viewer_content = f.read()
                                zip_file.writestr(f"{root_folder}/DICOM_Viewer.html", viewer_content)
                            
                            # ═══════════════════════════════════════════════════════════════
                            # PHASE 6: HTML EXPORT VIEWER (Presentation only)
                            # Write viewer assets and index. Index MUST be written LAST.
                            # ═══════════════════════════════════════════════════════════════
                            if include_html_viewer:
                                try:
                                    # Copy viewer assets from static/
                                    static_dir = os.path.join(os.path.dirname(__file__), '..', 'static')
                                    
                                    # PHASE 12: Pre-flight verification of viewer assets
                                    # Fail early with clear error instead of mysterious browser "file not found"
                                    required_assets = ('viewer.html', 'viewer.css', 'viewer.js')
                                    missing_assets = [n for n in required_assets if not os.path.exists(os.path.join(static_dir, n))]
                                    if missing_assets:
                                        raise RuntimeError(f"Export viewer assets missing from static/: {', '.join(missing_assets)}")
                                    
                                    for asset_name in required_assets:
                                        asset_path = os.path.join(static_dir, asset_name)
                                        with open(asset_path, 'rb') as f:
                                            zip_file.writestr(f"{root_folder}/viewer/{asset_name}", f.read())
                                    
                                    # Add friendly redirect at root level
                                    redirect_html = b"<!doctype html><meta http-equiv='refresh' content='0; url=viewer/viewer.html'><title>VoxelMask Export Viewer</title>"
                                    zip_file.writestr(f"{root_folder}/VIEWER.html", redirect_html)
                                    
                                    # ═══════════════════════════════════════════════════════════════
                                    # GOVERNANCE: Write viewer_index.json LAST
                                    # This ensures all other artefacts are committed before index.
                                    # ═══════════════════════════════════════════════════════════════
                                    ordered_entries = _build_viewer_ordered_entries(
                                        processed_files=processed_files,
                                        file_info_cache=file_info_cache,
                                        root_folder=root_folder
                                    )
                                    
                                    viewer_index = generate_viewer_index(
                                        ordered_entries=ordered_entries,
                                        ordering_source="export_order_manifest",
                                        output_path=None  # No filesystem write - we write to ZIP
                                    )
                                    
                                    # Convert to JSON and write to ZIP
                                    import json as json_module
                                    index_dict = viewer_index.to_dict()
                                    index_json = json_module.dumps(index_dict, indent=2)
                                    
                                    # Write standard JSON (for machine readability)
                                    zip_file.writestr(f"{root_folder}/viewer/viewer_index.json", index_json.encode('utf-8'))
                                    
                                    # Write JS Global (for file:// protocol support)
                                    index_js = viewer_index.to_js()
                                    zip_file.writestr(f"{root_folder}/viewer/viewer_index.js", index_js.encode('utf-8'))
                                    
                                    # ═══════════════════════════════════════════════════════════════
                                    # PHASE 12 FIX: WRITE VIEWER TO RUN-SCOPED DIRECTORY
                                    # This ensures viewer paths survive Steam Deck's xdg-document-portal
                                    # sandboxing, which creates ephemeral /run/user/1000/doc/... paths
                                    # that disappear after extraction.
                                    # ═══════════════════════════════════════════════════════════════
                                    if run_paths:
                                        # Phase 12: Use canonical viewer_dir from RunPaths
                                        run_viewer_dir = run_paths.viewer_dir
                                        run_viewer_dir.mkdir(parents=True, exist_ok=True)  # Defensive
                                        
                                        # Copy viewer assets with versioning
                                        # Phase 12: Use run_id as version stamp for cache-busting
                                        version_stamp = run_paths.run_id
                                        
                                        for asset_name in required_assets:
                                            asset_path = os.path.join(static_dir, asset_name)
                                            dst_path = run_viewer_dir / asset_name
                                            
                                            if asset_name == 'viewer.html':
                                                # Version the HTML file to bust browser cache
                                                with open(asset_path, 'r', encoding='utf-8') as f:
                                                    html_content = f.read()
                                                versioned_html = _version_viewer_html(html_content, version_stamp)
                                                dst_path.write_text(versioned_html, encoding='utf-8')
                                            else:
                                                # Copy other assets as-is
                                                shutil.copy2(asset_path, dst_path)
                                        
                                        # Write viewer_index.json
                                        (run_viewer_dir / "viewer_index.json").write_text(index_json, encoding='utf-8')
                                        
                                        # Write viewer_index.js
                                        (run_viewer_dir / "viewer_index.js").write_text(index_js, encoding='utf-8')
                                        
                                        # Copy processed DICOM files and PNGs for viewer
                                        for file_info in processed_files:
                                            folder_path = file_info.get('folder_path', 'Processed')
                                            dcm_dst = run_viewer_dir.parent / folder_path / file_info['filename']
                                            dcm_dst.parent.mkdir(parents=True, exist_ok=True)
                                            dcm_dst.write_bytes(file_info['data'])
                                            
                                            # Render PNG if image modality
                                            modality = file_info.get('modality', '')
                                            if modality.upper() in ['US', 'CT', 'MR', 'DX', 'CR', 'MG', 'XA', 'RF', 'NM', 'PT']:
                                                try:
                                                    png_bytes = render_dicom_bytes_to_png(file_info['data'])
                                                    if png_bytes:
                                                        png_dst = dcm_dst.with_suffix('.png')
                                                        png_dst.write_bytes(png_bytes)
                                                except Exception:
                                                    pass  # Silent skip
                                        
                                        # Store run-scoped viewer path in session state
                                        run_viewer_html = run_viewer_dir / "viewer.html"
                                        assert run_viewer_html.exists(), f"Viewer HTML not found: {run_viewer_html}"
                                        st.session_state.run_scoped_viewer_path = str(run_viewer_html)
                                        print(f"[Phase12] Run-scoped viewer written: {run_viewer_html}")
                                    
                                except Exception as viewer_error:
                                    # Viewer is optional - don't fail export if viewer generation fails
                                    st.warning(f"HTML viewer generation failed: {viewer_error}. DICOM export completed successfully.")
                    
                    # Store folder structure info for display
                    st.session_state.folder_structure_info = {
                        'studies': len(unique_studies),
                        'series': len(unique_series),
                        'files': len(processed_files)
                    }
                    
                    # ═══════════════════════════════════════════════════════════════
                    # DECISION TRACE COMMIT (PR 5 - Atomic Export Integration)
                    # Record reviewer region decisions to SQLite ONLY after successful export
                    # ═══════════════════════════════════════════════════════════════
                    review_session = st.session_state.get('phi_review_session')
                    if review_session is not None and review_session.review_accepted:
                        try:
                            # Create collector and record all region decisions
                            collector = DecisionTraceCollector()
                            active_regions = review_session.get_active_regions()
                            sop_uid = review_session.sop_instance_uid
                            
                            # Record each region decision to the collector
                            decisions_recorded = record_region_decisions(
                                collector=collector,
                                regions=active_regions,
                                sop_instance_uid=sop_uid
                            )
                            
                            # Commit to SQLite atomically
                            db_path = os.path.join(BASE_DIR, 'scrub_history.db')
                            writer = DecisionTraceWriter(db_path)
                            
                            # Generate scrub UUID from audit logger if available
                            scrub_uuid = (
                                st.session_state.audit_logger.generate_scrub_uuid() 
                                if hasattr(st.session_state, 'audit_logger') and st.session_state.audit_logger
                                else str(uuid.uuid4())
                            )
                            
                            writer.commit(scrub_uuid, collector)
                            
                            # Log success to combined audit
                            summary = review_session.get_summary()
                            decision_summary = (
                                f"\n\n--- Reviewer Region Decision Trace (Sprint 2) ---\n"
                                f"Session ID: {review_session.session_id}\n"
                                f"SOP Instance UID: {sop_uid[:32]}...\n"
                                f"Total Regions: {summary['total_regions']}\n"
                                f"OCR Detected: {summary['ocr_regions']}\n"
                                f"Manual: {summary['manual_regions']}\n"
                                f"Will Mask: {summary['will_mask']}\n"
                                f"Overrides (Keep): {summary['will_unmask']}\n"
                                f"Decision Records Committed: {decisions_recorded}\n"
                                f"Scrub UUID: {scrub_uuid}\n"
                            )
                            st.session_state.combined_audit_logs += decision_summary
                            
                        except Exception as e:
                            # Log warning but don't fail export
                            st.warning(f"Decision trace recording failed: {e}")
                    
                    st.session_state.output_zip_buffer = zip_buffer.getvalue()
                    
                    # Rerun to show download UI
                    st.rerun()
                else:
                    # ═══════════════════════════════════════════════════════════════
                    # PHASE 8: Mark run failed (4.5)
                    # ═══════════════════════════════════════════════════════════════
                    try:
                        if run_paths:
                            update_run_status(
                                run_paths.root,
                                status="failed",
                                timestamp_field="failed_at",
                                failure_reason="no_files_processed",
                            )
                            print(f"[Phase8] Run status: failed (no_files_processed)")
                    except Exception:
                        pass  # Non-fatal
                    st.error("No files were processed successfully")
            
        else:
            st.info("📁 Upload DICOM files to begin processing")
            st.caption("Supports: Single files, multiple files, or ZIP archives")
# ═══════════════════════════════════════════════════════════════════════════════
# FOOTER
# ═══════════════════════════════════════════════════════════════════════════════
st.divider()
st.markdown(
    "<div style='text-align: center; color: #64748B; font-size: 0.85rem; line-height: 1.6;'>"
    "VoxelMask does not guarantee removal of all personal or identifying information.<br>"
    "Users are responsible for validating outputs for their intended use."
    "</div>",
    unsafe_allow_html=True
)
