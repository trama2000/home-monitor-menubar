#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# Home Monitor - Install Script for macOS
# Builds the .app bundle and sets up auto-start at login
# ═══════════════════════════════════════════════════════════════

set -e

echo "🏠 Home Monitor - Installer"
echo "═══════════════════════════════════════════════"
echo ""

# Check Python 3
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found. Install it with: brew install python3"
    exit 1
fi

echo "✅ Python 3 found: $(python3 --version)"

# Install dependencies
echo ""
echo "📦 Installing dependencies..."
pip3 install --user rumps requests py2app

# Check if config exists
CONFIG_FILE="$HOME/.home_monitor_config.json"
if [ ! -f "$CONFIG_FILE" ]; then
    echo ""
    echo "⚠️  No config file found. Creating template..."
    cp config_template.json "$CONFIG_FILE"
    echo "📝 Please edit $CONFIG_FILE with your credentials before running."
    echo "   nano $CONFIG_FILE"
    echo ""
    read -p "Press Enter after editing config, or Ctrl+C to exit..."
fi

# Build .app
echo ""
echo "🔨 Building Home Monitor.app..."
python3 setup.py py2app 2>&1 | tail -5

if [ -d "dist/Home Monitor.app" ]; then
    echo "✅ App built successfully!"
    
    # Copy to Applications
    echo ""
    echo "📂 Installing to /Applications..."
    rm -rf "/Applications/Home Monitor.app"
    cp -r "dist/Home Monitor.app" "/Applications/"
    echo "✅ Installed to /Applications/Home Monitor.app"
    
    # Create LaunchAgent for auto-start
    PLIST_DIR="$HOME/Library/LaunchAgents"
    PLIST_FILE="$PLIST_DIR/com.trama2000.homemonitor.plist"
    mkdir -p "$PLIST_DIR"
    
    cat > "$PLIST_FILE" << 'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.trama2000.homemonitor</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Applications/Home Monitor.app/Contents/MacOS/Home Monitor</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <false/>
    <key>ProcessType</key>
    <string>Interactive</string>
</dict>
</plist>
PLIST
    
    # Load the LaunchAgent
    launchctl unload "$PLIST_FILE" 2>/dev/null || true
    launchctl load "$PLIST_FILE"
    
    echo "✅ Auto-start configured (LaunchAgent)"
    echo ""
    echo "═══════════════════════════════════════════════"
    echo "🎉 Installation complete!"
    echo ""
    echo "  App location:  /Applications/Home Monitor.app"
    echo "  Config file:   ~/.home_monitor_config.json"
    echo "  Auto-start:    Enabled (login items)"
    echo ""
    echo "  To start now:  open '/Applications/Home Monitor.app'"
    echo "  To stop:       Click menu icon > Salir"
    echo "  To uninstall:  ./uninstall.sh"
    echo "═══════════════════════════════════════════════"
    
    # Launch it now
    echo ""
    read -p "🚀 Launch Home Monitor now? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        open "/Applications/Home Monitor.app"
        echo "✅ Home Monitor started! Check your menu bar."
    fi
else
    echo "❌ Build failed. Check errors above."
    exit 1
fi
