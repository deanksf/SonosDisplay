# SonosPlus Qualia WIDE Display System

A complete system that displays album artwork from Sonos speakers on an Adafruit Qualia S3 RGB666 display, automatically updating when music changes.

## We have two repositories for this feature
The album_artwork repo has some of the most current server code (get_metadata_soco.py, artwork_server.py, etc.).  Be sure the check between the two repositories for the most recent code.

## Hardware Requirements

- **Raspberry Pi** (any recent model with WiFi)
- **Adafruit Qualia S3 RGB666** display
- **Micro USB cable** for Qualia
- **MicroSD card** for Raspberry Pi
- **Power supplies** for both devices

## System Architecture

```
Sonos Speakers → Raspberry Pi → Qualia Display
     ↓              ↓              ↓
  Music Info → Metadata Service → Artwork Display
```

## Part 1: Raspberry Pi Setup

### 1.1 Initial Setup

1. **Flash Raspberry Pi OS** to SD card using Raspberry Pi Imager
2. **Boot Raspberry Pi** and complete initial setup:
   - Set hostname: `sonos-display`
   - Enable SSH
   - Connect to WiFi
   - Update system: `sudo apt update && sudo apt upgrade -y`

### 1.2 Install Dependencies

```bash
# Install system packages
sudo apt install -y python3-pip python3-venv python3-pil python3-pil.imagetk screen

# Create virtual environment
python3 -m venv /home/deankondo/sonos-venv
source /home/deankondo/sonos-venv/bin/activate

# Install Python packages
pip install soco requests pillow psutil
```

### 1.3 Create Project Structure

```bash
mkdir -p /home/deankondo/sonos-display/Adafruit
cd /home/deankondo/sonos-display
```

## Part 2: Raspberry Pi Files

### 2.1 Required Files

Copy these files to `/home/deankondo/sonos-display/`:

#### `get_metadata_soco.py`
Main script that monitors Sonos and downloads artwork.

#### `artwork_server.py`
Simple HTTP server to serve artwork.bmp on port 8000.

#### `get_metadata_soco.service`
Systemd service file for automatic startup.

#### `artwork_server.service`
Systemd service file for automatic startup.

#### Placeholder Images
Copy `MIL1.bmp` through `MIL6.bmp` to `/home/deankondo/sonos-display/Adafruit/`

### 2.2 Service Installation

```bash
# Copy service files to systemd
sudo cp /home/deankondo/sonos-display/get_metadata_soco.service /etc/systemd/system/
sudo cp /home/deankondo/sonos-display/artwork_server.service /etc/systemd/system/

# Reload systemd and enable services
sudo systemctl daemon-reload
sudo systemctl enable get_metadata_soco.service
sudo systemctl enable artwork_server.service
sudo systemctl start get_metadata_soco.service
sudo systemctl start artwork_server.service
```

### 2.3 Configuration

#### Sonos API Credentials
Edit `get_metadata_soco.py` and update:
```python
ACCESS_TOKEN = "YOUR_SONOS_ACCESS_TOKEN"
HOUSEHOLD_ID = "YOUR_SONOS_HOUSEHOLD_ID"
```

To get these credentials:
1. Go to https://integration.sonos.com/
2. Create a new integration
3. Get the access token and household ID

## Part 3: Qualia Setup

### 3.1 Initial Setup

1. **Download CircuitPython** for Qualia S3 RGB666 from Adafruit
2. **Flash CircuitPython** to Qualia
3. **Mount Qualia** as CIRCUITPY drive

### 3.2 Required Files

Copy these files to the CIRCUITPY drive:

#### `boot.py`
```python
import supervisor
supervisor.disable_autoreload()
```

#### `code.py`
Main display code that downloads and displays artwork.

#### `secrets.py`
```python
secrets = {
    'ssid': 'YOUR_WIFI_SSID',
    'password': 'YOUR_WIFI_PASSWORD',
}
```

### 3.3 Required Libraries

Copy these CircuitPython libraries to `/CIRCUITPY/lib/`:
- `adafruit_imageload/`
- `adafruit_requests/`
- `adafruit_esp32spi/`
- `adafruit_bus_device/`
- `adafruit_displayio_ssd1306/`
- `adafruit_display_text/`
- `adafruit_displayio_layout/`

Download from: https://circuitpython.org/libraries

## Part 4: File Transfer Commands

### 4.1 Copy Files to Raspberry Pi

```bash
# From your development machine
scp /path/to/your/project/get_metadata_soco.py deankondo@sonos-display.local:/home/deankondo/sonos-display/
scp /path/to/your/project/artwork_server.py deankondo@sonos-display.local:/home/deankondo/sonos-display/
scp /path/to/your/project/get_metadata_soco.service deankondo@sonos-display.local:/home/deankondo/sonos-display/
scp /path/to/your/project/artwork_server.service deankondo@sonos-display.local:/home/deankondo/sonos-display/
scp /path/to/your/project/Adafruit/MIL*.bmp deankondo@sonos-display.local:/home/deankondo/sonos-display/Adafruit/
```

### 4.2 Copy Files to Qualia

```bash
# From your development machine
scp /path/to/your/project/Adafruit/code.py deankondo@sonos-display.local:/home/deankondo/sonos-display/
scp /path/to/your/project/Adafruit/boot.py deankondo@sonos-display.local:/home/deankondo/sonos-display/

# Then from Raspberry Pi to Qualia
ssh deankondo@sonos-display.local "sudo mount -o remount,rw /media/deankondo/CIRCUITPY && cp /home/deankondo/sonos-display/code.py /media/deankondo/CIRCUITPY/code.py"
ssh deankondo@sonos-display.local "sudo mount -o remount,rw /media/deankondo/CIRCUITPY && cp /home/deankondo/sonos-display/boot.py /media/deankondo/CIRCUITPY/boot.py"
```

## Part 5: Testing and Verification

### 5.1 Test Raspberry Pi Services

```bash
# Check service status
sudo systemctl status get_metadata_soco.service artwork_server.service

# Test artwork server
curl -I http://localhost:8000/Adafruit/artwork.bmp

# Check logs
sudo journalctl -u get_metadata_soco.service -f
sudo journalctl -u artwork_server.service -f
```

### 5.2 Test Qualia

1. **Power cycle Qualia**
2. **Check serial output** for initialization
3. **Verify WiFi connection**
4. **Test artwork download and display**

### 5.3 Monitor Qualia Logs

```bash
# Connect to Qualia serial console
ssh deankondo@sonos-display.local
sudo screen /dev/ttyACM0 115200

# Exit screen: Ctrl+A, then K
```

## Part 6: Troubleshooting

### 6.1 Common Issues

#### Services Not Starting
```bash
# Check logs
sudo journalctl -u get_metadata_soco.service -n 10
sudo journalctl -u artwork_server.service -n 10

# Restart services
sudo systemctl restart get_metadata_soco.service
sudo systemctl restart artwork_server.service
```

#### Port 8000 in Use
```bash
# Find process using port
sudo lsof -i :8000

# Kill process
sudo kill <PID>
```

#### Qualia Not Connecting
- Check WiFi credentials in `secrets.py`
- Verify network connectivity
- Check serial output for errors

#### Display Issues
- Check timing parameters in `code.py`
- Try different frequency settings
- Verify display initialization

### 6.2 Performance Optimization

The system is optimized for:
- **Display frequency**: 6MHz (reduced from 8MHz for stability)
- **Update interval**: 10 seconds between checks
- **Image format**: 720x720 BMP with 8-bit color

### 6.3 Useful Commands

```bash
# Check disk space
df -h

# Check network connectivity
ping sonos-display.local

# Monitor real-time logs
sudo journalctl -f

# Check service status
sudo systemctl status get_metadata_soco.service artwork_server.service

# Restart all services
sudo systemctl restart get_metadata_soco.service artwork_server.service
```

## Part 7: File Structure

### Raspberry Pi Structure
```
/home/deankondo/sonos-display/
├── get_metadata_soco.py
├── artwork_server.py
├── get_metadata_soco.service
├── artwork_server.service
└── Adafruit/
    ├── artwork.bmp
    ├── MIL1.bmp
    ├── MIL2.bmp
    ├── MIL3.bmp
    ├── MIL4.bmp
    ├── MIL5.bmp
    └── MIL6.bmp
```

### Qualia Structure
```
/CIRCUITPY/
├── boot.py
├── code.py
├── secrets.py
└── lib/
    ├── adafruit_imageload/
    ├── adafruit_requests/
    ├── adafruit_esp32spi/
    ├── adafruit_bus_device/
    ├── adafruit_displayio_ssd1306/
    ├── adafruit_display_text/
    └── adafruit_displayio_layout/
```

## Part 8: Maintenance

### 8.1 Automatic Startup
Both services are configured to:
- Start automatically on boot
- Restart automatically if they crash
- Run continuously in the background

### 8.2 Updates
To update the system:
1. Copy new files to Raspberry Pi
2. Restart services: `sudo systemctl restart get_metadata_soco.service artwork_server.service`
3. Copy new files to Qualia
4. Power cycle Qualia

### 8.3 Monitoring
Monitor system health with:
```bash
# Check service status
sudo systemctl status get_metadata_soco.service artwork_server.service

# Check disk space
df -h

# Check network
ping sonos-display.local

# View logs
sudo journalctl -u get_metadata_soco.service -f
```

## Performance Metrics

Typical performance:
- **HEAD request**: ~0.5 seconds
- **Download**: ~0.1-0.3 seconds
- **Image processing**: ~0.1-0.2 seconds
- **Display update**: ~0.5 seconds
- **Total update time**: ~5-6 seconds

## Support

For issues:
1. Check service logs: `sudo journalctl -u <service> -n 10`
2. Check Qualia serial output
3. Verify network connectivity
4. Check file permissions and paths

The system is designed to be fully automated and self-healing, with automatic restarts and fallback mechanisms for reliability. 
