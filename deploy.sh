#!/bin/bash
# Deploy script for VoxelMask v1.0

set -e

TARGET_DIR=~/Projects/voxelmask

echo "🔧 Creating target directories..."
mkdir -p "$TARGET_DIR/src"
mkdir -p "$TARGET_DIR/tools"
mkdir -p "$TARGET_DIR/studies/input"
mkdir -p "$TARGET_DIR/studies/output"
mkdir -p "$TARGET_DIR/.streamlit"
mkdir -p "$TARGET_DIR/data"

echo "📦 Copying files to $TARGET_DIR..."
cp -r ./* "$TARGET_DIR/" 2>/dev/null || true
cp -r ./.streamlit "$TARGET_DIR/" 2>/dev/null || true

echo "🔄 Restarting Docker container..."
cd "$TARGET_DIR"
sudo docker compose restart voxelmask-engine

echo "🚀 VoxelMask v1.0 Deployed and Restarted!"
