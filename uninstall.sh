#!/bin/bash
# Uninstall Home Monitor
echo "🏠 Uninstalling Home Monitor..."

# Stop the app
pkill -f "Home Monitor" 2>/dev/null || true

# Remove LaunchAgent
PLIST="$HOME/Library/LaunchAgents/com.trama2000.homemonitor.plist"
if [ -f "$PLIST" ]; then
    launchctl unload "$PLIST" 2>/dev/null || true
    rm "$PLIST"
    echo "✅ LaunchAgent removed"
fi

# Remove app
if [ -d "/Applications/Home Monitor.app" ]; then
    rm -rf "/Applications/Home Monitor.app"
    echo "✅ App removed from /Applications"
fi

echo ""
echo "✅ Home Monitor uninstalled."
echo "   Config file preserved: ~/.home_monitor_config.json"
echo "   To remove config: rm ~/.home_monitor_config.json"
