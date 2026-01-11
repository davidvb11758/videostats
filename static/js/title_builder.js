// Global state
let availableFonts = [];

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    loadFonts();
    setupEventListeners();
});

// Load available fonts from API
async function loadFonts() {
    try {
        const response = await fetch('/api/title-builder/fonts');
        const data = await response.json();
        availableFonts = data.fonts || [];
        
        // Populate all font selects
        const fontSelects = document.querySelectorAll('.font-select');
        fontSelects.forEach(select => {
            // Clear existing options
            select.innerHTML = '';
            
            availableFonts.forEach(font => {
                const option = document.createElement('option');
                option.value = font;
                option.textContent = font;
                select.appendChild(option);
            });
            
            // Set default to Arial
            select.value = 'Arial';
        });
    } catch (error) {
        showMessage('Failed to load fonts: ' + error.message, 'error');
    }
}

// Setup event listeners
function setupEventListeners() {
    // Preview button
    document.getElementById('preview-btn').addEventListener('click', previewImage);
    
    // Generate video button
    document.getElementById('generate-btn').addEventListener('click', generateVideo);
    
    // Export button
    document.getElementById('export-btn').addEventListener('click', exportSettings);
    
    // Import button
    document.getElementById('import-btn').addEventListener('click', () => {
        document.getElementById('import-file').click();
    });
    
    // Import file input
    document.getElementById('import-file').addEventListener('change', importSettings);
    
    // Close preview button
    document.getElementById('close-preview').addEventListener('click', () => {
        document.getElementById('preview-section').style.display = 'none';
    });
}

// Collect current settings from form
function collectSettings() {
    const bgColor = hexToRgb(document.getElementById('bg-color').value);
    
    const lines = [];
    const lineControls = document.querySelectorAll('.line-controls');
    
    lineControls.forEach((lineControl, index) => {
        const text = lineControl.querySelector('.text-input').value.trim();
        const fontStyle = lineControl.querySelector('.font-select').value;
        const fontSize = parseInt(lineControl.querySelector('.font-size').value) || 30;
        const fontBold = lineControl.querySelector('.bold-checkbox').checked;
        const fontItalic = lineControl.querySelector('.italic-checkbox').checked;
        const color = hexToRgb(lineControl.querySelector('.color-picker').value);
        
        lines.push({
            text: text,
            color: color,
            font_style: fontStyle,
            font_size: fontSize,
            font_bold: fontBold,
            font_italic: fontItalic
        });
    });
    
    return {
        background_color: bgColor,
        lines: lines
    };
}

// Convert hex color to RGB object
function hexToRgb(hex) {
    const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
    return result ? {
        r: parseInt(result[1], 16),
        g: parseInt(result[2], 16),
        b: parseInt(result[3], 16)
    } : { r: 255, g: 255, b: 255 };
}

// Convert RGB object to hex
function rgbToHex(rgb) {
    return '#' + [rgb.r, rgb.g, rgb.b].map(x => {
        const hex = x.toString(16);
        return hex.length === 1 ? '0' + hex : hex;
    }).join('');
}

// Preview image
async function previewImage() {
    const settings = collectSettings();
    
    // Validate: at least one line with text
    if (!settings.lines.some(line => line.text.trim())) {
        showMessage('Please enter at least one line of text.', 'error');
        return;
    }
    
    try {
        const response = await fetch('/api/title-builder/preview', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(settings)
        });
        
        const data = await response.json();
        
        if (data.success) {
            const previewImg = document.getElementById('preview-image');
            previewImg.src = data.image;
            document.getElementById('preview-section').style.display = 'block';
            showMessage('Preview generated successfully!', 'success');
        } else {
            showMessage('Error: ' + (data.error || 'Failed to generate preview'), 'error');
        }
    } catch (error) {
        showMessage('Failed to generate preview: ' + error.message, 'error');
    }
}

// Generate title video
async function generateVideo() {
    const settings = collectSettings();
    
    // Validate: at least one line with text
    if (!settings.lines.some(line => line.text.trim())) {
        showMessage('Please enter at least one line of text.', 'error');
        return;
    }
    
    const generateBtn = document.getElementById('generate-btn');
    const originalText = generateBtn.textContent;
    
    try {
        generateBtn.disabled = true;
        generateBtn.textContent = 'Generating...';
        
        const response = await fetch('/api/title-builder/generate-video', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(settings)
        });
        
        const data = await response.json();
        
        if (data.success) {
            showMessage('Title video generated successfully! Saved as video_clips/title.mp4', 'success');
        } else {
            showMessage('Error: ' + (data.error || 'Failed to generate title video'), 'error');
        }
    } catch (error) {
        showMessage('Failed to generate title video: ' + error.message, 'error');
    } finally {
        generateBtn.disabled = false;
        generateBtn.textContent = originalText;
    }
}

// Export settings to JSON
async function exportSettings() {
    const settings = collectSettings();
    
    try {
        const response = await fetch('/api/title-builder/export', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(settings)
        });
        
        if (response.ok) {
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'settings.json';
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
            showMessage('Settings exported successfully!', 'success');
        } else {
            const data = await response.json();
            showMessage('Error: ' + (data.error || 'Failed to export settings'), 'error');
        }
    } catch (error) {
        showMessage('Failed to export settings: ' + error.message, 'error');
    }
}

// Import settings from JSON
async function importSettings(event) {
    const file = event.target.files[0];
    if (!file) return;
    
    const formData = new FormData();
    formData.append('file', file);
    
    try {
        const response = await fetch('/api/title-builder/import', {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        
        if (data.success) {
            const settings = data.settings;
            
            // Set background color
            const bgColor = settings.background_color;
            document.getElementById('bg-color').value = rgbToHex(bgColor);
            
            // Set line settings
            const lineControls = document.querySelectorAll('.line-controls');
            settings.lines.forEach((lineData, index) => {
                if (index < lineControls.length) {
                    const lineControl = lineControls[index];
                    lineControl.querySelector('.text-input').value = lineData.text || '';
                    lineControl.querySelector('.font-select').value = lineData.font_style || 'Arial';
                    lineControl.querySelector('.font-size').value = lineData.font_size || 30;
                    lineControl.querySelector('.bold-checkbox').checked = lineData.font_bold || false;
                    lineControl.querySelector('.italic-checkbox').checked = lineData.font_italic || false;
                    lineControl.querySelector('.color-picker').value = rgbToHex(lineData.color || { r: 255, g: 255, b: 255 });
                }
            });
            
            // Reset file input
            event.target.value = '';
            
            showMessage('Settings imported successfully!', 'success');
        } else {
            showMessage('Error: ' + (data.error || 'Failed to import settings'), 'error');
        }
    } catch (error) {
        showMessage('Failed to import settings: ' + error.message, 'error');
    }
}

// Show message
function showMessage(text, type) {
    const messageEl = document.getElementById('message');
    messageEl.textContent = text;
    messageEl.className = 'message ' + type;
    messageEl.style.display = 'block';
    
    // Auto-hide after 5 seconds
    setTimeout(() => {
        messageEl.style.display = 'none';
    }, 5000);
}
