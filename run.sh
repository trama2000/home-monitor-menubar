#!/bin/bash
# Quick run - no build needed, just Python
# Use this for testing before building the .app

CONFIG="$HOME/.home_monitor_config.json"
if [ ! -f "$CONFIG" ]; then
    echo "⚠️  Config not found. Creating from template..."
    cp config_template.json "$CONFIG"
    echo "📝 Edit $CONFIG with your credentials first."
    echo "   nano $CONFIG"
    exit 1
fi

pip3 install --user rumps requests 2>/dev/null
python3 home_monitor.py
