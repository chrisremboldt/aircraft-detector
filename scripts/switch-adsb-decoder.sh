#!/bin/bash

# Aircraft Detector - ADS-B Decoder Switcher
# Easily switch between dump1090-mutability and dump1090-fa

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

show_usage() {
    echo "Usage: $0 [mutability|fa]"
    echo ""
    echo "Switch between ADS-B decoders:"
    echo "  mutability  - Use dump1090-mutability (package-managed, stable)"
    echo "  fa          - Use dump1090-fa (FlightAware, optimized)"
    echo ""
    echo "Examples:"
    echo "  $0 fa           # Switch to dump1090-fa"
    echo "  $0 mutability   # Switch to dump1090-mutability"
    echo ""
    echo "Current decoder can be checked with:"
    echo "  systemctl is-active dump1090-mutability"
    echo "  systemctl is-active dump1090-fa"
}

switch_to_mutability() {
    echo "🔄 Switching to dump1090-mutability..."
    
    # Stop dump1090-fa if running
    if systemctl is-active --quiet dump1090-fa; then
        echo "  Stopping dump1090-fa..."
        sudo systemctl stop dump1090-fa
        sudo systemctl disable dump1090-fa
    fi
    
    # Start dump1090-mutability
    echo "  Starting dump1090-mutability..."
    sudo systemctl enable dump1090-mutability
    sudo systemctl start dump1090-mutability
    
    # Wait a moment for service to start
    sleep 2
    
    # Check status
    if systemctl is-active --quiet dump1090-mutability; then
        echo "✅ Successfully switched to dump1090-mutability"
        echo ""
        echo "📋 Configuration:"
        echo "  JSON Data: /run/dump1090-mutability/aircraft.json"
        echo "  Web Interface: http://localhost:8080"
        echo "  Service: dump1090-mutability.service"
        echo ""
        echo "🚀 Start aircraft detector with:"
        echo "  python3 pi-aircraft-detector.py --web --web-port 8081 --enable-adsb --adsb-url http://localhost:8080/data/aircraft.json --camera-lat YOUR_LAT --camera-lon YOUR_LON"
    else
        echo "❌ Failed to start dump1090-mutability"
        sudo systemctl status dump1090-mutability --no-pager
        exit 1
    fi
}

switch_to_fa() {
    echo "🔄 Switching to dump1090-fa..."
    
    # Stop dump1090-mutability if running
    if systemctl is-active --quiet dump1090-mutability; then
        echo "  Stopping dump1090-mutability..."
        sudo systemctl stop dump1090-mutability
        sudo systemctl disable dump1090-mutability
    fi
    
    # Start dump1090-fa
    echo "  Starting dump1090-fa..."
    sudo systemctl enable dump1090-fa
    sudo systemctl start dump1090-fa
    
    # Wait a moment for service to start
    sleep 2
    
    # Check status
    if systemctl is-active --quiet dump1090-fa; then
        echo "✅ Successfully switched to dump1090-fa"
        echo ""
        echo "📋 Configuration:"
        echo "  JSON Data: /run/dump1090-fa/aircraft.json"
        echo "  Network Ports: 30001-30005"
        echo "  Service: dump1090-fa.service"
        echo ""
        echo "🚀 Start aircraft detector with:"
        echo "  python3 pi-aircraft-detector.py --web --web-port 8081 --enable-adsb --adsb-url http://localhost:8080/data/aircraft.json --camera-lat YOUR_LAT --camera-lon YOUR_LON"
    else
        echo "❌ Failed to start dump1090-fa"
        sudo systemctl status dump1090-fa --no-pager
        exit 1
    fi
}

show_current_status() {
    echo "📊 Current ADS-B Decoder Status:"
    echo ""
    
    if systemctl is-active --quiet dump1090-mutability; then
        echo "✅ dump1090-mutability: ACTIVE"
    else
        echo "⭕ dump1090-mutability: inactive"
    fi
    
    if systemctl is-active --quiet dump1090-fa; then
        echo "✅ dump1090-fa: ACTIVE"
    else
        echo "⭕ dump1090-fa: inactive"
    fi
    
    echo ""
    echo "Available decoders:"
    echo "  mutability - Use dump1090-mutability"
    echo "  fa         - Use dump1090-fa"
}

# Main script logic
case "${1:-}" in
    "mutability")
        switch_to_mutability
        ;;
    "fa")
        switch_to_fa
        ;;
    "status")
        show_current_status
        ;;
    "-h"|"--help"|"help")
        show_usage
        ;;
    "")
        show_current_status
        echo ""
        show_usage
        ;;
    *)
        echo "❌ Invalid option: $1"
        echo ""
        show_usage
        exit 1
        ;;
esac 