#!/bin/bash

# SoilSense v4.0 Automatic Setup Script
# Optimized for Raspberry Pi (Raspbian/Debian)

echo "--- SOILSENSE AUTOMATIC SETUP STARTING ---"

# 1. Update System
echo "[1/4] Updating system packages..."
sudo apt-get update -y

# 2. Install Python Dependencies
echo "[2/4] Installing Python 3 and hardware libraries..."
sudo apt-get install -y python3 python3-pip python3-flask python3-serial python3-flask-cors

# 3. Install Node.js (if not present)
if ! command -v node &> /dev/null
then
    echo "[3/4] Node.js not found. Installing Node.js 20..."
    curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
    sudo apt-get install -y nodejs
else
    echo "[3/4] Node.js already installed."
fi

# 4. Install Project Dependencies
echo "[4/4] Installing project dependencies (npm)..."
npm install

echo "--- SETUP COMPLETE ---"
echo "To start the system, run: npm start"
echo "The UI will be available at http://<your-pi-ip>:3000"
