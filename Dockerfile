FROM python:3.10-slim
LABEL maintainer="VoxelMask Engineering Team"
LABEL version="1.0.0"
LABEL description="VoxelMask - Intelligent DICOM De-Identification Workstation"

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies for OpenCV/Paddle
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    ffmpeg \
    libsm6 \
    libxext6 \
    libgl1 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Create PaddleX directory to prevent permission issues with model downloads
RUN mkdir -p /root/.paddlex/

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src /app/src
COPY tools /app/tools

# Create data directory
RUN mkdir -p /app/data

# Expose Streamlit port
EXPOSE 8501

# Health check
HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health || exit 1

# Run VoxelMask
ENTRYPOINT ["streamlit", "run", "src/app.py", "--server.port=8501", "--server.address=0.0.0.0", "--theme.primaryColor=#00d4ff"]
