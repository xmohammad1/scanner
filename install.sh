#!/usr/bin/env bash
set -e

# Determine available package manager
if command -v apt >/dev/null 2>&1; then
    PM=apt
elif command -v apt-get >/dev/null 2>&1; then
    PM=apt-get
elif command -v dnf >/dev/null 2>&1; then
    PM=dnf
elif command -v yum >/dev/null 2>&1; then
    PM=yum
elif command -v pacman >/dev/null 2>&1; then
    PM=pacman
elif command -v zypper >/dev/null 2>&1; then
    PM=zypper
else
    echo "Supported package manager not found. Install Python3 and pip manually." >&2
    exit 1
fi

# Install Python and pip using the detected package manager
case "$PM" in
    apt|apt-get)
        sudo $PM update
        sudo $PM install -y python3 python3-pip
        ;;
    dnf|yum)
        sudo $PM install -y python3 python3-pip
        ;;
    pacman)
        sudo $PM -Sy --noconfirm python python-pip
        ;;
    zypper)
        sudo $PM refresh
        sudo $PM install -y python3 python3-pip
        ;;
    *)
        echo "Unsupported package manager: $PM" >&2
        exit 1
        ;;
        
esac

# Install Python dependencies
pip3 install --user -r requirements.txt

echo "Installation complete."
