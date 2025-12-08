"""
Click-and-drag canvas implementation using HTML5 canvas with Streamlit.
Shows background image and allows drawing rectangles directly on it.
"""
import streamlit as st
import streamlit.components.v1 as components
import base64
import io
from PIL import Image
import numpy as np


def image_to_base64(img: Image.Image) -> str:
    """Convert PIL image to base64 string"""
    if img.mode != 'RGB':
        img = img.convert('RGB')
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode()


def draw_canvas_with_image(
    image: Image.Image,
    canvas_key: str = "draw_canvas",
    stroke_color: str = "#00FFFF",
    stroke_width: int = 3,
    fill_color: str = "rgba(0, 255, 255, 0.2)",
) -> dict:
    """
    Display image with click-and-drag rectangle drawing.
    Returns the rectangle coordinates when drawn.
    """
    
    # Get image dimensions
    img_width, img_height = image.size
    
    # Convert image to base64
    img_base64 = image_to_base64(image)
    
    # State key for storing drawn rectangle
    state_key = f"_rect_{canvas_key}"
    if state_key not in st.session_state:
        st.session_state[state_key] = None
    
    # HTML/JavaScript for interactive canvas
    html_content = f'''
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{ background: transparent; }}
            #container {{
                position: relative;
                width: {img_width}px;
                height: {img_height}px;
                border: 2px solid {stroke_color};
                border-radius: 8px;
                overflow: hidden;
                cursor: crosshair;
            }}
            #bgImage {{
                position: absolute;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
            }}
            #drawCanvas {{
                position: absolute;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
            }}
            #info {{
                margin-top: 8px;
                color: #58a6ff;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
                font-size: 14px;
                font-weight: 500;
            }}
        </style>
    </head>
    <body>
        <div id="container">
            <img id="bgImage" src="data:image/png;base64,{img_base64}" />
            <canvas id="drawCanvas" width="{img_width}" height="{img_height}"></canvas>
        </div>
        <div id="info">👆 Click and drag to draw mask rectangle</div>
        
        <script>
            const canvas = document.getElementById('drawCanvas');
            const ctx = canvas.getContext('2d');
            const info = document.getElementById('info');
            
            let isDrawing = false;
            let startX, startY;
            let currentRect = null;
            let savedRect = null;
            
            function drawRect(x, y, w, h, isSaved) {{
                ctx.clearRect(0, 0, canvas.width, canvas.height);
                
                // Draw saved rectangle if exists
                if (savedRect && !isSaved) {{
                    ctx.strokeStyle = '#FF6B6B';
                    ctx.lineWidth = 2;
                    ctx.fillStyle = 'rgba(255, 107, 107, 0.1)';
                    ctx.beginPath();
                    ctx.rect(savedRect.x, savedRect.y, savedRect.w, savedRect.h);
                    ctx.fill();
                    ctx.stroke();
                }}
                
                // Draw current rectangle
                ctx.strokeStyle = '{stroke_color}';
                ctx.lineWidth = {stroke_width};
                ctx.fillStyle = '{fill_color}';
                ctx.beginPath();
                ctx.rect(x, y, w, h);
                ctx.fill();
                ctx.stroke();
                
                // Draw corner handles
                const handleSize = 8;
                ctx.fillStyle = '{stroke_color}';
                ctx.fillRect(x - handleSize/2, y - handleSize/2, handleSize, handleSize);
                ctx.fillRect(x + w - handleSize/2, y - handleSize/2, handleSize, handleSize);
                ctx.fillRect(x - handleSize/2, y + h - handleSize/2, handleSize, handleSize);
                ctx.fillRect(x + w - handleSize/2, y + h - handleSize/2, handleSize, handleSize);
            }}
            
            canvas.addEventListener('mousedown', (e) => {{
                const rect = canvas.getBoundingClientRect();
                const scaleX = canvas.width / rect.width;
                const scaleY = canvas.height / rect.height;
                startX = (e.clientX - rect.left) * scaleX;
                startY = (e.clientY - rect.top) * scaleY;
                isDrawing = true;
                currentRect = null;
            }});
            
            canvas.addEventListener('mousemove', (e) => {{
                if (!isDrawing) return;
                
                const rect = canvas.getBoundingClientRect();
                const scaleX = canvas.width / rect.width;
                const scaleY = canvas.height / rect.height;
                const currentX = (e.clientX - rect.left) * scaleX;
                const currentY = (e.clientY - rect.top) * scaleY;
                
                // Calculate rectangle (handle negative dimensions)
                let x = Math.min(startX, currentX);
                let y = Math.min(startY, currentY);
                let w = Math.abs(currentX - startX);
                let h = Math.abs(currentY - startY);
                
                currentRect = {{ x, y, w, h }};
                drawRect(x, y, w, h, false);
                info.textContent = '📐 Drawing: ' + Math.round(w) + ' × ' + Math.round(h) + ' px';
            }});
            
            canvas.addEventListener('mouseup', (e) => {{
                if (!isDrawing) return;
                isDrawing = false;
                
                if (currentRect && currentRect.w > 10 && currentRect.h > 10) {{
                    savedRect = currentRect;
                    drawRect(currentRect.x, currentRect.y, currentRect.w, currentRect.h, true);
                    info.innerHTML = '✅ <b>Mask saved:</b> (' + Math.round(currentRect.x) + ', ' + Math.round(currentRect.y) + ') ' + 
                                     Math.round(currentRect.w) + ' × ' + Math.round(currentRect.h) + ' px';
                    
                    // Send to Streamlit via postMessage
                    window.parent.postMessage({{
                        type: 'streamlit:setComponentValue',
                        data: {{
                            x: Math.round(currentRect.x),
                            y: Math.round(currentRect.y),
                            w: Math.round(currentRect.w),
                            h: Math.round(currentRect.h)
                        }}
                    }}, '*');
                }} else {{
                    info.textContent = '⚠️ Rectangle too small. Click and drag to draw a larger area.';
                }}
            }});
            
            canvas.addEventListener('mouseleave', () => {{
                if (isDrawing) {{
                    isDrawing = false;
                    if (savedRect) {{
                        drawRect(savedRect.x, savedRect.y, savedRect.w, savedRect.h, true);
                    }} else {{
                        ctx.clearRect(0, 0, canvas.width, canvas.height);
                    }}
                }}
            }});
            
            // Touch support for mobile/tablet
            canvas.addEventListener('touchstart', (e) => {{
                e.preventDefault();
                const touch = e.touches[0];
                const rect = canvas.getBoundingClientRect();
                const scaleX = canvas.width / rect.width;
                const scaleY = canvas.height / rect.height;
                startX = (touch.clientX - rect.left) * scaleX;
                startY = (touch.clientY - rect.top) * scaleY;
                isDrawing = true;
            }});
            
            canvas.addEventListener('touchmove', (e) => {{
                e.preventDefault();
                if (!isDrawing) return;
                const touch = e.touches[0];
                const rect = canvas.getBoundingClientRect();
                const scaleX = canvas.width / rect.width;
                const scaleY = canvas.height / rect.height;
                const currentX = (touch.clientX - rect.left) * scaleX;
                const currentY = (touch.clientY - rect.top) * scaleY;
                
                let x = Math.min(startX, currentX);
                let y = Math.min(startY, currentY);
                let w = Math.abs(currentX - startX);
                let h = Math.abs(currentY - startY);
                
                currentRect = {{ x, y, w, h }};
                drawRect(x, y, w, h, false);
            }});
            
            canvas.addEventListener('touchend', (e) => {{
                e.preventDefault();
                if (!isDrawing) return;
                isDrawing = false;
                
                if (currentRect && currentRect.w > 10 && currentRect.h > 10) {{
                    savedRect = currentRect;
                    drawRect(currentRect.x, currentRect.y, currentRect.w, currentRect.h, true);
                    info.innerHTML = '✅ <b>Mask saved:</b> (' + Math.round(currentRect.x) + ', ' + Math.round(currentRect.y) + ') ' + 
                                     Math.round(currentRect.w) + ' × ' + Math.round(currentRect.h) + ' px';
                }}
            }});
        </script>
    </body>
    </html>
    '''
    
    # Render the component
    components.html(html_content, height=img_height + 50, scrolling=False)
    
    return st.session_state[state_key]
