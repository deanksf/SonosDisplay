from displayio import release_displays
release_displays()

import displayio
import busio
import board
import dotclockframebuffer
from framebufferio import FramebufferDisplay
import wifi
import socketpool
import adafruit_requests
import adafruit_imageload
import time
import gc
import json
from io import BytesIO

# Configuration
WIFI_SSID = ""
WIFI_PASSWORD = ""
IMAGE_URL = "http://sonos-display.local:8000/Adafruit/artwork_bar.bmp"
METADATA_URL = "http://sonos-display.local:8000/metadata.json"

# Network settings - simplified to match working 720x720 display
HTTP_TIMEOUT = 10
HTTP_DOWNLOAD_TIMEOUT = 30
MAX_RETRIES = 3
RETRY_DELAY = 3
METADATA_POLL_INTERVAL = 2   # Match working display exactly
FORCE_IMAGE_REFRESH_INTERVAL = 60

print("Starting Sonos Bar Display System...")
print("Using SIMPLIFIED networking approach (matching working 720x720 display)")

# TFT pins configurationT
tft_pins = dict(board.TFT_PINS)

# Official Adafruit HD458002C40 initialization sequence
init_sequence_st7701s = bytes((
    b'\xff\x05w\x01\x00\x00\x13'
    b'\xef\x01\x08'
    b'\xff\x05w\x01\x00\x00\x10'
    b'\xc0\x02w\x00'
    b'\xc1\x02\t\x08'
    b'\xc2\x02\x01\x02'
    b'\xc3\x01\x02'
    b'\xcc\x01\x10'
    b'\xb0\x10@\x14Y\x10\x12\x08\x03\t\x05\x1e\x05\x14\x10h3\x15'
    b'\xb1\x10@\x08S\t\x11\t\x02\x07\t\x1a\x04\x12\x12d))'
    b'\xff\x05w\x01\x00\x00\x11'
    b'\xb0\x01m'
    b'\xb1\x01\x1d'
    b'\xb2\x01\x87'
    b'\xb3\x01\x80'
    b'\xb5\x01I'
    b'\xb7\x01\x85'
    b'\xb8\x01 '
    b'\xc1\x01x'
    b'\xc2\x01x'
    b'\xd0\x01\x88'
    b'\xe0\x03\x00\x00\x02'
    b'\xe1\x0b\x02\x8c\x00\x00\x03\x8c\x00\x00\x0033'
    b'\xe2\r3333\xc9<\x00\x00\xca<\x00\x00\x00'
    b'\xe3\x04\x00\x0033'
    b'\xe4\x02DD'
    b'\xe5\x10\x05\xcd\x82\x82\x01\xc9\x82\x82\x07\xcf\x82\x82\x03\xcb\x82\x82'
    b'\xe6\x04\x00\x0033'
    b'\xe7\x02DD'
    b'\xe8\x10\x06\xce\x82\x82\x02\xca\x82\x82\x08\xd0\x82\x82\x04\xcc\x82\x82'
    b'\xeb\x07\x08\x01\xe4\xe4\x88\x00@'
    b'\xec\x03\x00\x00\x00'
    b'\xed\x10\xff\xf0\x07eO\xfc\xc2/\xf2,\xcf\xf4Vp\x0f\xff'
    b'\xef\x06\x10\r\x04\x08?\x1f'
    b'\xff\x05w\x01\x00\x00\x00'
    b'\x11\x80x'
    b'5\x01\x00'
    b':\x81fd'
    b')\x00'
))

# Initialize I2C and send init sequence
board.I2C().deinit()
i2c = busio.I2C(board.SCL, board.SDA, frequency=100_000)
tft_io_expander = dict(board.TFT_IO_EXPANDER)

print("Initializing ST7701S display...")
dotclockframebuffer.ioexpander_send_init_sequence(i2c, init_sequence_st7701s, **tft_io_expander)
time.sleep(0.2)

# Official Adafruit HD458002C40 timing parameters
tft_timings = {
    "frequency": 16000000,
    "width": 320,
    "height": 960,
    "overscan_left": 80,
    "hsync_pulse_width": 10,
    "hsync_front_porch": 30,
    "hsync_back_porch": 50,
    "hsync_idle_low": False,
    "vsync_pulse_width": 2,
    "vsync_front_porch": 15,
    "vsync_back_porch": 17,
    "vsync_idle_low": False,
    "pclk_active_high": False,
    "pclk_idle_high": False,
    "de_idle_high": False,
}

# Create display
fb = dotclockframebuffer.DotClockFramebuffer(**tft_pins, **tft_timings)
display = FramebufferDisplay(fb, auto_refresh=False)
print("✓ Display initialized")

# Quick display test
test_bitmap = displayio.Bitmap(tft_timings['width'], tft_timings['height'], 1)
test_palette = displayio.Palette(1)
test_palette[0] = 0x00FF00  # Green
test_grid = displayio.TileGrid(test_bitmap, pixel_shader=test_palette)
test_group = displayio.Group()
test_group.append(test_grid)
display.root_group = test_group
display.refresh()
print("✓ Display test complete")
time.sleep(2)

# Add power-saving measures to reduce current spikes and flickering
print("Applying power-saving measures for display stability...")

# Add stabilization delay after display initialization
time.sleep(1.0)  # Allow power supply to stabilize

# Reduce display refresh frequency to minimize power spikes
display.auto_refresh = False  # Ensure manual refresh only
print("✓ Power-saving measures applied")

# Clean up I2C

# Connect to WiFi
print(f"Connecting to WiFi: {WIFI_SSID}...")
try:
    wifi.radio.connect(WIFI_SSID, WIFI_PASSWORD)
    print(f"✓ Connected: {wifi.radio.ipv4_address}")
except Exception as e:
    print(f"✗ WiFi failed: {e}")
    while True:
        time.sleep(1)

# Initialize HTTP session
pool = socketpool.SocketPool(wifi.radio)
requests = adafruit_requests.Session(pool)

def reset_socket_pool():
    """Simple socket pool reset - copied from working 720x720 display"""
    global pool, requests
    print("🔧 Resetting socket pool...")
    
    try:
        requests._session.close()
        pool.close()
    except:
        pass
    
    gc.collect()
    time.sleep(2)
    
    pool = socketpool.SocketPool(wifi.radio)
    requests = adafruit_requests.Session(pool)

def reset_wifi_connection():
    """Reset WiFi connection for severe network issues"""
    print("🔧 Resetting WiFi...")
    try:
        wifi.radio.enabled = False
        time.sleep(3)
        wifi.radio.enabled = True
        time.sleep(2)
        wifi.radio.connect(WIFI_SSID, WIFI_PASSWORD)
        print(f"✅ WiFi reconnected: {wifi.radio.ipv4_address}")
        reset_socket_pool()
        return True
    except Exception as e:
        print(f"❌ WiFi reset failed: {e}")
        return False

def http_request_with_retry(url, method="GET", timeout=HTTP_TIMEOUT, max_retries=MAX_RETRIES):
    """Simple HTTP request with retry logic - copied from working 720x720 display"""
    for attempt in range(max_retries):
        try:
            start_time = time.monotonic()
            
            if method == "HEAD":
                response = requests.head(url, timeout=timeout)
            else:
                response = requests.get(url, timeout=timeout)
            
            elapsed = time.monotonic() - start_time
            
            # Check for slow responses (may indicate socket issues)
            if elapsed > 15:
                print(f"⚠️ Slow response ({elapsed:.1f}s) - resetting socket pool")
                response.close()
                reset_socket_pool()
                continue
            
            return response
            
        except Exception as e:
            elapsed = time.monotonic() - start_time if 'start_time' in locals() else 0
            error_str = str(e).lower()
            
            print(f"❌ HTTP {method} failed (attempt {attempt + 1}/{max_retries}): {e}")
            
            # Progressive retry delay with extra time for socket issues
            if attempt < max_retries - 1:
                retry_delay = RETRY_DELAY * (attempt + 1)
                if "socket" in error_str or "repeated" in error_str:
                    retry_delay += 2
                print(f"⏳ Retrying in {retry_delay}s...")
                time.sleep(retry_delay)
    
    return None

# Variables for tracking updates and smart polling
current_metadata = {"album": "", "title": "", "artist": ""}
last_metadata = {"album": "", "title": "", "artist": ""}
last_image_update = 0
pending_display_data = None  # Stores downloaded image data awaiting display

def fetch_metadata():
    """Fetch current song metadata"""
    global current_metadata
    
    response = http_request_with_retry(METADATA_URL, method="GET", timeout=HTTP_TIMEOUT)
    
    if response:
        try:
            data = response.json()
            current_metadata = {
                "album": data.get("album", ""),
                "title": data.get("title", ""), 
                "artist": data.get("artist", "")
            }
            print(f"✅ Metadata: {current_metadata['title']} - {current_metadata['artist']}")
            return True
        except Exception as e:
            print(f"❌ Metadata parse error: {e}")
            return False
        finally:
            # Always close response to prevent socket leaks
            try:
                response.close()
            except:
                pass
    return False

def show_status_message(message):
    """Display status checkerboard pattern"""
    bitmap = displayio.Bitmap(tft_timings['width'], tft_timings['height'], 2)
    palette = displayio.Palette(2)
    palette[0] = 0x000000  # Black
    palette[1] = 0xFFFFFF  # White
    
    square_size = max(20, tft_timings['width'] // 20)
    
    for y in range(tft_timings['height']):
        for x in range(tft_timings['width']):
            square_x = x // square_size
            square_y = y // square_size
            if (square_x + square_y) % 2 == 0:
                bitmap[x, y] = 0
            else:
                bitmap[x, y] = 1
    
    tile_grid = displayio.TileGrid(bitmap, pixel_shader=palette)
    group = displayio.Group()
    group.append(tile_grid)
    display.root_group = group
    
    # Power-saving refresh
    time.sleep(0.1)
    display.refresh()
    time.sleep(0.1)
    print(f"Status: {message}")



def check_if_image_needed():
    """Determine if we need to download a new image based on metadata changes"""
    global last_metadata, last_image_update
    
    # Check if song has changed
    song_changed = (
        current_metadata["title"] != last_metadata["title"] or
        current_metadata["artist"] != last_metadata["artist"] or
        current_metadata["album"] != last_metadata["album"]
    )
    
    # Check if it's been too long since last image update
    current_time = time.monotonic()
    time_since_image_update = current_time - last_image_update
    force_refresh = time_since_image_update > FORCE_IMAGE_REFRESH_INTERVAL
    
    # First run (no previous image)
    first_run = last_image_update == 0
    
    return song_changed or force_refresh or first_run, song_changed

def smart_update_cycle():
    """Smart polling: check metadata first, handle pending displays, then download if needed"""
    global last_metadata, last_image_update, pending_display_data
    
    try:
        # Always check metadata first (lightweight operation)
        print("📋 Checking metadata...")
        metadata_success = fetch_metadata()
        
        if not metadata_success:
            print("❌ Metadata fetch failed")
            return False
        
        # First priority: try to display any pending downloaded data
        if pending_display_data:
            print("🔄 Attempting to display previously downloaded image...")
            if display_pending_image():
                print("✅ Successfully displayed pending image")
                return True
            else:
                print("❌ Pending display failed - will try downloading fresh")
                pending_display_data = None  # Clear failed pending data
        
        # Second priority: check if we need to download new image
        needs_image, song_changed = check_if_image_needed()
        
        if song_changed:
            print(f"🎵 Song changed: {current_metadata['title']} - {current_metadata['artist']}")
        
        if not needs_image:
            print("✓ Metadata only - no image update needed")
            return True
        
        # Download and display server-rendered composite image
        return download_and_display_image()
        
    except Exception as e:
        print(f"❌ Smart update error: {e}")
        return False

def display_pending_image():
    """Display previously downloaded image data"""
    global pending_display_data, last_metadata, last_image_update
    
    if not pending_display_data:
        return False
    
    try:
        bitmap, palette, metadata_snapshot = pending_display_data
        
        print(f"🖼️ Displaying: {bitmap.width}x{bitmap.height} composite")
        
        # Create display elements
        tile_grid = displayio.TileGrid(bitmap, pixel_shader=palette)
        group = displayio.Group()
        group.append(tile_grid)
        
        # Update display with power-saving measures
        display.root_group = group
        
        # Add small delay before refresh to reduce power spike
        time.sleep(0.1)
        display.refresh()
        time.sleep(0.1)  # Allow power to stabilize after refresh
        
        # Update tracking after successful display
        last_metadata.update(metadata_snapshot)
        last_image_update = time.monotonic()
        pending_display_data = None  # Clear pending data
        
        print(f"✅ Displayed: {metadata_snapshot['title']} by {metadata_snapshot['artist']}")
        return True
        
    except Exception as e:
        print(f"❌ Pending display error: {e}")
        return False

def download_and_display_image():
    """Download image and attempt immediate display, with pending fallback"""
    global last_metadata, last_image_update, pending_display_data
    
    response = None
    
    try:
        # Download the ready-to-display composite image from server
        print("📥 Downloading composite image...")
        print("⏳ Expect ~5-15s with CircuitPython 10 networking improvements...")
        start_time = time.monotonic()
        response = http_request_with_retry(IMAGE_URL, method="GET", timeout=HTTP_DOWNLOAD_TIMEOUT)
        if not response:
            return False
        download_time = time.monotonic() - start_time
        print(f"✓ Download completed in {download_time:.1f}s")
        
        # Process and load image
        gc.collect()
        try:
            image_file = BytesIO(response.content)
            bitmap, palette = adafruit_imageload.load(image_file, 
                                                    bitmap=displayio.Bitmap, 
                                                    palette=displayio.Palette)
            image_file.close()
        finally:
            # Always close response to prevent socket leaks
            try:
                response.close()
            except:
                pass
        
        print(f"✓ Loaded: {bitmap.width}x{bitmap.height} composite")
        
        # Store as pending data (with metadata snapshot) in case display fails
        metadata_snapshot = dict(current_metadata)  # Create snapshot
        pending_display_data = (bitmap, palette, metadata_snapshot)
        
        # Update download tracking immediately to prevent re-downloads
        last_metadata.update(current_metadata)
        last_image_update = time.monotonic()
        print("✓ Download tracking updated - preventing unnecessary re-downloads")
        
        # Attempt immediate display
        if display_pending_image():
            print("✅ Immediate display successful")
            return True
        else:
            print("⚠️ Immediate display failed - image stored as pending for retry")
            return False  # Will retry pending display on next cycle
        
    except Exception as e:
        print(f"❌ Download/processing error: {e}")
        return False
    
    finally:
        # Clean up response if still open
        if response:
            try:
                response.close()
            except:
                pass
        gc.collect()

# Initialize
print("✓ Sonos Bar Display ready")
print("Features: HD458002C40 display + server-rendered composites")
print("Smart polling: 2s metadata checks + hostname resolution")
print("Network: CircuitPython 9.2.8 enhanced with aggressive socket management")
print("Power: Optimized refresh timing to reduce flicker")
print("Recovery: Preventive socket resets + progressive retry delays")
print("Optimized: Server creates perfect 320×960 images ready for display")
show_status_message("Power-Optimized Display Ready")

# Main loop with smart polling
consecutive_failures = 0
while True:
    try:
        gc.collect()
        success = smart_update_cycle()
        
        if not success:
            print("Update failed, retrying...")
        
        # Show pending status if applicable
        pending_status = " (PENDING DISPLAY)" if pending_display_data else ""
        print(f"🔄 Next check in {METADATA_POLL_INTERVAL}s{pending_status}")
        
        # Fast metadata polling for immediate song change detection
        time.sleep(METADATA_POLL_INTERVAL)
        
    except KeyboardInterrupt:
        print("Stopping...")
        break
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        time.sleep(2)
