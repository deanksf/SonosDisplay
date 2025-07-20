#!/bin/bash

echo "🔄 Sonos Display Service Restart Script"
echo "======================================="

# Stop any existing services
echo "1. Stopping existing services..."
sudo systemctl stop artwork_server.service 2>/dev/null || echo "   artwork_server.service not running"
sudo systemctl stop get_metadata_soco.service 2>/dev/null || echo "   get_metadata_soco.service not running"

# Kill any lingering Python processes
echo "2. Cleaning up lingering processes..."
pkill -f "artwork_server.py" 2>/dev/null || echo "   No artwork_server.py processes found"
pkill -f "get_metadata_soco.py" 2>/dev/null || echo "   No get_metadata_soco.py processes found"

# Wait for cleanup
sleep 3

# Check system resources
echo "3. Checking system resources..."
free -h
echo "CPU usage: $(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1)%"

# Start services with staggered timing to reduce load
echo "4. Starting optimized services..."

# Start metadata service first (does the heavy processing)
echo "   Starting get_metadata_soco.service..."
sudo systemctl start get_metadata_soco.service
sleep 5  # Give it time to initialize

# Check if metadata service started successfully
if sudo systemctl is-active --quiet get_metadata_soco.service; then
    echo "   ✅ get_metadata_soco.service started successfully"
else
    echo "   ❌ get_metadata_soco.service failed to start"
    sudo systemctl status get_metadata_soco.service
fi

# Start artwork server (lightweight HTTP server)
echo "   Starting artwork_server.service..."
sudo systemctl start artwork_server.service
sleep 2

# Check if artwork server started successfully
if sudo systemctl is-active --quiet artwork_server.service; then
    echo "   ✅ artwork_server.service started successfully"
else
    echo "   ❌ artwork_server.service failed to start"
    sudo systemctl status artwork_server.service
fi

# Show final status
echo ""
echo "5. Final service status:"
echo "   get_metadata_soco.service: $(sudo systemctl is-active get_metadata_soco.service)"
echo "   artwork_server.service: $(sudo systemctl is-active artwork_server.service)"

# Test HTTP endpoints
echo ""
echo "6. Testing HTTP endpoints..."
if curl -s --max-time 5 http://localhost:8000/metadata.json > /dev/null; then
    echo "   ✅ http://localhost:8000/metadata.json - OK"
else
    echo "   ❌ http://localhost:8000/metadata.json - Failed"
fi

if curl -s --max-time 5 -I http://localhost:8000/Adafruit/artwork_bar.bmp | grep -q "200 OK"; then
    echo "   ✅ http://localhost:8000/Adafruit/artwork_bar.bmp - OK"
else
    echo "   ❌ http://localhost:8000/Adafruit/artwork_bar.bmp - Failed"
fi

echo ""
echo "🎯 Restart complete! Services are optimized for reduced system load:"
echo "   • Metadata polling: Every 10 seconds (was 5 seconds)"
echo "   • System resource monitoring enabled"
echo "   • Spotify API calls disabled to reduce load"
echo "   • Staggered service startup"
echo ""
echo "Monitor with: sudo journalctl -fu get_metadata_soco.service"
echo "Check status: systemctl status artwork_server.service get_metadata_soco.service" 