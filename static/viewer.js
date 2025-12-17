/**
 * VoxelMask Export Viewer — Navigation Logic
 * ===========================================
 * 
 * Presentation-only JavaScript for navigating exported images.
 * 
 * ═══════════════════════════════════════════════════════════════════════════
 * GOVERNANCE RULES — This script is a RENDERER, not a decision-maker.
 * ═══════════════════════════════════════════════════════════════════════════
 * 
 * MUST NOT:
 * - Reorder anything (trust display_index exactly)
 * - Infer anything about series structure
 * - Rename or modify any index data
 * - Assume files exist (handle missing gracefully)
 * - Mutate index data (read-only)
 * - Add selection/editing semantics (view-only)
 * - Use array.sort() anywhere
 * 
 * MUST:
 * - Trust viewer_index.json as authoritative
 * - Use display_index for position (not instance_number)
 * - Show both instance_number and display_index in UI
 * - Handle missing files with clear message
 * - Show filter state explicitly ("N series hidden")
 * 
 * ═══════════════════════════════════════════════════════════════════════════
 */

'use strict';

// ═══════════════════════════════════════════════════════════════════════════
// STATE
// ═══════════════════════════════════════════════════════════════════════════

const viewerState = {
    index: null,                    // Loaded from viewer_index.json
    selectedSeriesIdx: -1,          // Index into filtered series list
    selectedInstanceIdx: 0,         // Index into selected series instances
    showDocuments: false,           // Toggle for OT/SC visibility
    error: null,                    // Error message if load failed
};

// ═══════════════════════════════════════════════════════════════════════════
// INITIALIZATION
// ═══════════════════════════════════════════════════════════════════════════

document.addEventListener('DOMContentLoaded', init);

async function init() {
    try {
        await loadIndex();
        setupEventListeners();
        renderSeriesList();

        // Auto-select first series if available
        const filteredSeries = getFilteredSeries();
        if (filteredSeries.length > 0) {
            selectSeries(0);
        }

        updateFooter();
    } catch (error) {
        showError('Failed to load viewer index: ' + error.message);
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// DATA LOADING
// ═══════════════════════════════════════════════════════════════════════════

async function loadIndex() {
    const response = await fetch('viewer_index.json');

    if (!response.ok) {
        throw new Error(`Could not load viewer_index.json (${response.status})`);
    }

    viewerState.index = await response.json();

    // Validate required fields (do NOT modify data)
    if (!viewerState.index.series) {
        throw new Error('Invalid index: missing series array');
    }

    console.log(
        `Loaded viewer index: ${viewerState.index.series.length} series, ` +
        `${viewerState.index.total_instances} instances, ` +
        `source=${viewerState.index.ordering_source}`
    );
}

// ═══════════════════════════════════════════════════════════════════════════
// FILTERING (Presentation-only)
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Get series filtered by current visibility settings.
 * 
 * GOVERNANCE: This does NOT reorder. Series appear in index order.
 * Filter only includes/excludes based on is_image_modality flag.
 */
function getFilteredSeries() {
    if (!viewerState.index || !viewerState.index.series) {
        return [];
    }

    if (viewerState.showDocuments) {
        // Show all series (no filtering)
        return viewerState.index.series;
    }

    // Filter to image modalities only
    return viewerState.index.series.filter(s => s.is_image_modality);
}

/**
 * Count hidden (document) series.
 */
function getHiddenSeriesCount() {
    if (!viewerState.index || !viewerState.index.series) {
        return 0;
    }

    if (viewerState.showDocuments) {
        return 0;
    }

    return viewerState.index.series.filter(s => !s.is_image_modality).length;
}

// ═══════════════════════════════════════════════════════════════════════════
// RENDERING — Series List
// ═══════════════════════════════════════════════════════════════════════════

function renderSeriesList() {
    const container = document.getElementById('series-list');
    const countDisplay = document.getElementById('series-count-display');
    const hiddenNote = document.getElementById('hidden-series-note');

    if (!container) return;

    container.innerHTML = '';

    const filteredSeries = getFilteredSeries();
    const hiddenCount = getHiddenSeriesCount();
    const totalCount = viewerState.index ? viewerState.index.series.length : 0;

    // Update count display
    if (countDisplay) {
        if (hiddenCount > 0) {
            countDisplay.textContent = `${filteredSeries.length} of ${totalCount} series`;
        } else {
            countDisplay.textContent = `${totalCount} series`;
        }
    }

    // Update hidden note
    if (hiddenNote) {
        if (hiddenCount > 0) {
            hiddenNote.textContent = `📄 ${hiddenCount} document series hidden (OT/SC)`;
            hiddenNote.style.display = 'block';
        } else {
            hiddenNote.textContent = '';
            hiddenNote.style.display = 'none';
        }
    }

    // Render series rows
    if (filteredSeries.length === 0) {
        container.innerHTML = `
            <div class="series-row placeholder">
                <span class="series-desc">No series available</span>
            </div>
        `;
        return;
    }

    filteredSeries.forEach((series, idx) => {
        const row = createSeriesRow(series, idx);
        container.appendChild(row);
    });
}

function createSeriesRow(series, idx) {
    const row = document.createElement('div');
    row.className = 'series-row';

    // Add document class for visual distinction
    if (!series.is_image_modality) {
        row.classList.add('document');
    }

    // Add selected class if this is the selected series
    if (idx === viewerState.selectedSeriesIdx) {
        row.classList.add('selected');
    }

    const icon = getModalityIcon(series.modality);
    const desc = truncate(series.series_description || 'Unknown', 25);
    const seriesNum = series.series_number != null ? `S${String(series.series_number).padStart(3, '0')}` : '';

    row.innerHTML = `
        <div class="series-main">
            <span class="series-icon">${icon}</span>
            <span class="series-desc">${desc}</span>
        </div>
        <div class="series-meta">
            ${seriesNum} • ${series.modality} • <span class="series-count">(${series.instance_count})</span>
        </div>
    `;

    row.addEventListener('click', () => selectSeries(idx));

    return row;
}

// ═══════════════════════════════════════════════════════════════════════════
// RENDERING — Image Viewport
// ═══════════════════════════════════════════════════════════════════════════

function renderImage() {
    const filteredSeries = getFilteredSeries();
    const series = filteredSeries[viewerState.selectedSeriesIdx];

    if (!series || !series.instances || series.instances.length === 0) {
        showImagePlaceholder('No images in selected series');
        return;
    }

    const instance = series.instances[viewerState.selectedInstanceIdx];

    if (!instance) {
        showImagePlaceholder('Image not found');
        return;
    }

    // Update header
    const seriesDesc = document.getElementById('viewport-series-desc');
    const position = document.getElementById('viewport-position');

    if (seriesDesc) {
        seriesDesc.textContent = series.series_description || 'Unknown Series';
    }

    if (position) {
        const current = viewerState.selectedInstanceIdx + 1;
        const total = series.instance_count;
        position.textContent = `Image ${current} of ${total}`;
    }

    // Update navigation controls
    updateNavigationControls(series);

    // Update metadata footer
    updateMetadataFooter(instance, series);

    // Load image
    loadImage(instance);
}

function showImagePlaceholder(message) {
    const container = document.getElementById('image-display');
    if (!container) return;

    container.innerHTML = `
        <div class="image-placeholder">
            <div class="placeholder-icon">🖼️</div>
            <div class="placeholder-text">${escapeHtml(message)}</div>
        </div>
    `;

    // Disable controls
    const slider = document.getElementById('nav-slider');
    const prevBtn = document.getElementById('btn-prev');
    const nextBtn = document.getElementById('btn-next');

    if (slider) { slider.disabled = true; slider.value = 1; slider.max = 1; }
    if (prevBtn) { prevBtn.disabled = true; }
    if (nextBtn) { nextBtn.disabled = true; }
}

function loadImage(instance) {
    const container = document.getElementById('image-display');
    if (!container) return;

    // Derive image path (expect .png alongside .dcm)
    // GOVERNANCE: We do NOT check if file exists — just try to load
    const imagePath = instance.file_path.replace(/\.dcm$/i, '.png');

    const img = document.createElement('img');
    img.alt = `Instance ${instance.display_index}`;

    img.onload = () => {
        container.innerHTML = '';
        container.appendChild(img);
    };

    img.onerror = () => {
        // Try JPEG as fallback
        const jpegPath = instance.file_path.replace(/\.dcm$/i, '.jpg');
        const imgJpeg = document.createElement('img');
        imgJpeg.alt = img.alt;

        imgJpeg.onload = () => {
            container.innerHTML = '';
            container.appendChild(imgJpeg);
        };

        imgJpeg.onerror = () => {
            showImageUnavailable(instance);
        };

        imgJpeg.src = jpegPath;
    };

    img.src = imagePath;
}

function showImageUnavailable(instance) {
    const container = document.getElementById('image-display');
    if (!container) return;

    container.innerHTML = `
        <div class="image-placeholder error-message">
            <div class="error-icon">⚠️</div>
            <div class="error-text">
                Image unavailable<br>
                <small>File not found in export: ${escapeHtml(instance.file_path)}</small>
            </div>
        </div>
    `;
}

function updateNavigationControls(series) {
    const slider = document.getElementById('nav-slider');
    const prevBtn = document.getElementById('btn-prev');
    const nextBtn = document.getElementById('btn-next');

    const current = viewerState.selectedInstanceIdx;
    const total = series.instance_count;

    if (slider) {
        slider.min = 1;
        slider.max = total;
        slider.value = current + 1;
        slider.disabled = total <= 1;
    }

    if (prevBtn) {
        prevBtn.disabled = current <= 0;
    }

    if (nextBtn) {
        nextBtn.disabled = current >= total - 1;
    }
}

function updateMetadataFooter(instance, series) {
    const footer = document.getElementById('viewport-metadata');
    if (!footer) return;

    const instanceNum = instance.instance_number != null
        ? `Instance #${instance.instance_number}`
        : 'Instance # —';

    const displayPos = `Display position: ${instance.display_index}/${series.instance_count}`;

    footer.textContent = `${instanceNum} | ${displayPos}`;
}

// ═══════════════════════════════════════════════════════════════════════════
// NAVIGATION
// ═══════════════════════════════════════════════════════════════════════════

function selectSeries(idx) {
    const filteredSeries = getFilteredSeries();

    if (idx < 0 || idx >= filteredSeries.length) {
        return;
    }

    viewerState.selectedSeriesIdx = idx;
    viewerState.selectedInstanceIdx = 0; // Reset to first image

    renderSeriesList(); // Update selection highlighting
    renderImage();
}

function prevInstance() {
    if (viewerState.selectedInstanceIdx > 0) {
        viewerState.selectedInstanceIdx--;
        renderImage();
    }
}

function nextInstance() {
    const filteredSeries = getFilteredSeries();
    const series = filteredSeries[viewerState.selectedSeriesIdx];

    if (series && viewerState.selectedInstanceIdx < series.instance_count - 1) {
        viewerState.selectedInstanceIdx++;
        renderImage();
    }
}

function gotoInstance(idx) {
    const filteredSeries = getFilteredSeries();
    const series = filteredSeries[viewerState.selectedSeriesIdx];

    if (series && idx >= 0 && idx < series.instance_count) {
        viewerState.selectedInstanceIdx = idx;
        renderImage();
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// EVENT LISTENERS
// ═══════════════════════════════════════════════════════════════════════════

function setupEventListeners() {
    // Document filter toggle
    const toggle = document.getElementById('show-documents-toggle');
    if (toggle) {
        toggle.checked = viewerState.showDocuments;
        toggle.addEventListener('change', (e) => {
            viewerState.showDocuments = e.target.checked;
            viewerState.selectedSeriesIdx = 0;
            viewerState.selectedInstanceIdx = 0;
            renderSeriesList();

            const filteredSeries = getFilteredSeries();
            if (filteredSeries.length > 0) {
                selectSeries(0);
            } else {
                showImagePlaceholder('No series available');
            }
        });
    }

    // Navigation buttons
    const prevBtn = document.getElementById('btn-prev');
    const nextBtn = document.getElementById('btn-next');

    if (prevBtn) {
        prevBtn.addEventListener('click', prevInstance);
    }

    if (nextBtn) {
        nextBtn.addEventListener('click', nextInstance);
    }

    // Navigation slider
    const slider = document.getElementById('nav-slider');
    if (slider) {
        slider.addEventListener('input', (e) => {
            const newIdx = parseInt(e.target.value, 10) - 1;
            gotoInstance(newIdx);
        });
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// FOOTER
// ═══════════════════════════════════════════════════════════════════════════

function updateFooter() {
    const footer = document.getElementById('footer-generated');
    if (!footer || !viewerState.index) return;

    const generated = viewerState.index.generated_at
        ? `Generated: ${viewerState.index.generated_at}`
        : '';

    const source = viewerState.index.ordering_source
        ? `Ordering source: ${viewerState.index.ordering_source}`
        : '';

    footer.textContent = [generated, source].filter(Boolean).join(' | ');
}

// ═══════════════════════════════════════════════════════════════════════════
// ERROR HANDLING
// ═══════════════════════════════════════════════════════════════════════════

function showError(message) {
    viewerState.error = message;
    console.error('Viewer error:', message);

    const container = document.getElementById('series-list');
    if (container) {
        container.innerHTML = `
            <div class="error-message">
                <div class="error-icon">⚠️</div>
                <div class="error-text">${escapeHtml(message)}</div>
            </div>
        `;
    }

    showImagePlaceholder('Unable to load viewer');
}

// ═══════════════════════════════════════════════════════════════════════════
// UTILITIES
// ═══════════════════════════════════════════════════════════════════════════

function getModalityIcon(modality) {
    const icons = {
        'US': '🔊',
        'CT': '🩻',
        'MR': '🧲',
        'DX': '📷',
        'CR': '📷',
        'MG': '📷',
        'SC': '📋',
        'OT': '📄',
        'SR': '📝',
        'DOC': '📄',
    };
    return icons[modality] || '🖼️';
}

function truncate(str, maxLen) {
    if (!str) return '';
    return str.length > maxLen ? str.slice(0, maxLen - 3) + '...' : str;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
