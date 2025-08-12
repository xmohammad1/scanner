#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e
echo "Installing Python3 and pip..."
sudo apt update
sudo apt install -y python3 python3-pip unzip curl git
# Clone the scanner repository
echo "Cloning scanner repository..."
git clone https://github.com/xmohammad1/scanner

# Change directory to the cloned repository
cd scanner || exit

# Download the Xray-core release
cd /root/scanner
apt-get update
apt-get install -y curl unzip

arch=$(uname -m)
case "$arch" in
  x86_64|amd64)   asset="Xray-linux-64.zip" ;;
  aarch64|arm64)  asset="Xray-linux-arm64-v8a.zip" ;;
  armv7l)         asset="Xray-linux-arm32-v7a.zip" ;;
  *) echo "Unsupported arch: $arch"; exit 1 ;;
esac

curl -L -o xray.zip "https://github.com/XTLS/Xray-core/releases/download/v25.5.16/$asset"
unzip -oj xray.zip xray geoip.dat geosite.dat -d .
./xray -version

rm xray.zip

# Install Python requirements
if [ -f requirements.txt ]; then
    echo "Installing Python requirements..."
    apt install -y python3 python3-pip
    pip install --upgrade pip
    pip install -r requirements.txt
else
    echo "requirements.txt not found. Skipping pip install."
fi
echo "download complete."
