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

def tprint(message):
    """Print with timestamp for debugging"""
    current_time = time.monotonic()
    print(f"[{current_time:8.1f}s] {message}")

# Configuration
WIFI_SSID = ""
WIFI_PASSWORD = ""
IMAGE_URL = "http://192.168.86.60:8000/Adafruit/artwork_bar.bmp"
METADATA_URL = "http://192.168.86.60:8000/metadata.json"

# Network settings - enhanced for bar display hardware constraints
HTTP_TIMEOUT = 15             # Bar display needs longer timeouts
HTTP_DOWNLOAD_TIMEOUT = 180   # CircuitPython 9 needs much more time for large images
MAX_RETRIES = 3
RETRY_DELAY = 3
METADATA_POLL_INTERVAL = 2    # Match working display exactly
FORCE_IMAGE_REFRESH_INTERVAL = 300  # 5 minutes instead of 1 minute

tprint("Starting Sonos Bar Display System...")
tprint("Using SIMPLIFIED networking approach (matching working 720x720 display)")

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

tprint("Initializing ST7701S display...")
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
tprint("✓ Display initialized")

# Quick display test
test_bitmap = displayio.Bitmap(tft_timings['width'], tft_timings['height'], 1)
test_palette = displayio.Palette(1)
test_palette[0] = 0x00FF00  # Green
test_grid = displayio.TileGrid(test_bitmap, pixel_shader=test_palette)
test_group = displayio.Group()
test_group.append(test_grid)
display.root_group = test_group
display.refresh()
tprint("✓ Display test complete")
time.sleep(2)

# Add power-saving measures to reduce current spikes and flickering
tprint("Applying power-saving measures for display stability...")

# Add stabilization delay after display initialization
time.sleep(1.0)  # Allow power supply to stabilize

# Reduce display refresh frequency to minimize power spikes
display.auto_refresh = False  # Ensure manual refresh only
tprint("✓ Power-saving measures applied")

# Clean up I2C

# Connect to WiFi
tprint(f"Connecting to WiFi: {WIFI_SSID}...")
try:
    wifi.radio.connect(WIFI_SSID, WIFI_PASSWORD)
    tprint(f"✓ Connected: {wifi.radio.ipv4_address}")
    
    # Network diagnostics
    try:
        signal_strength = wifi.radio.ap_info.rssi
        tprint(f"📶 WiFi signal: {signal_strength} dBm")
    except:
        tprint("📶 WiFi signal: Could not read signal strength")
    
    try:
        gateway = wifi.radio.ipv4_gateway
        tprint(f"🌐 Gateway: {gateway}")
    except:
        tprint("🌐 Gateway: Could not read gateway")
    
    tprint(f"🔗 Image URL: {IMAGE_URL}")
    tprint(f"🔗 Metadata URL: {METADATA_URL}")
    
    # Quick connectivity test to diagnose networking issues
    tprint("🧪 Testing server connectivity...")
    test_start = time.monotonic()
    try:
        import socket
        test_socket = pool.socket(pool.AF_INET, pool.SOCK_STREAM)
        test_socket.settimeout(10)
        test_socket.connect(("192.168.86.60", 8000))
        test_time = time.monotonic() - test_start
        tprint(f"🧪 TCP connection to IP: {test_time:.1f}s ✅")
        test_socket.close()
    except Exception as test_error:
        test_time = time.monotonic() - test_start
        tprint(f"🧪 TCP connection failed after {test_time:.1f}s: {test_error}")
    
    # Test DNS resolution (the previous problem)
    tprint("🧪 Testing DNS resolution...")
    dns_start = time.monotonic()
    try:
        import adafruit_requests
        dns_response = requests.get("http://192.168.86.60:8000/metadata.json", timeout=5)
        dns_time = time.monotonic() - dns_start
        tprint(f"🧪 DNS resolution test: {dns_time:.1f}s")
        dns_response.close()
    except Exception as dns_error:
        dns_time = time.monotonic() - dns_start
        tprint(f"🧪 DNS resolution failed after {dns_time:.1f}s: {dns_error} ❌")
    
except Exception as e:
    tprint(f"✗ WiFi failed: {e}")
    while True:
        time.sleep(1)

# Initialize HTTP session
pool = socketpool.SocketPool(wifi.radio)
requests = adafruit_requests.Session(pool)

def reset_socket_pool():
    """Enhanced socket pool reset for bar display"""
    global pool, requests
    tprint("🔧 Resetting socket pool...")
    
    try:
        requests._session.close()
        pool.close()
    except:
        pass
    
    # Bar display specific: More thorough cleanup
    gc.collect()
    time.sleep(2)
    
    # Check WiFi connection health
    if not wifi.radio.connected:
        tprint("⚠️ WiFi disconnected during socket reset - reconnecting...")
        try:
            wifi.radio.connect(WIFI_SSID, WIFI_PASSWORD)
            tprint(f"✅ WiFi reconnected: {wifi.radio.ipv4_address}")
        except Exception as e:
            tprint(f"❌ WiFi reconnection failed: {e}")
    
    pool = socketpool.SocketPool(wifi.radio)
    requests = adafruit_requests.Session(pool)
    tprint("✅ Socket pool reset complete")

def reset_wifi_connection():
    """Reset WiFi connection for severe network issues"""
    tprint("🔧 Resetting WiFi...")
    try:
        wifi.radio.enabled = False
        time.sleep(3)
        wifi.radio.enabled = True
        time.sleep(2)
        wifi.radio.connect(WIFI_SSID, WIFI_PASSWORD)
        tprint(f"✅ WiFi reconnected: {wifi.radio.ipv4_address}")
        reset_socket_pool()
        return True
    except Exception as e:
        tprint(f"❌ WiFi reset failed: {e}")
        return False

def http_request_with_retry(url, method="GET", timeout=HTTP_TIMEOUT, max_retries=MAX_RETRIES):
    """Enhanced HTTP request for bar display - minimal but targeted networking fixes"""
    for attempt in range(max_retries):
        response = None
        try:
            start_time = time.monotonic()
            tprint(f"🔍 Starting {method} request to {url}")
            
            # Bar display specific: Force GC before each request
            gc_start = time.monotonic()
            gc.collect()
            gc_time = time.monotonic() - gc_start
            tprint(f"🔍 GC completed in {gc_time:.1f}s")
            
            request_start = time.monotonic()
            if method == "HEAD":
                response = requests.head(url, timeout=timeout)
            else:
                response = requests.get(url, timeout=timeout)
            request_time = time.monotonic() - request_start
            tprint(f"🔍 HTTP request completed in {request_time:.1f}s")
            
            elapsed = time.monotonic() - start_time
            tprint(f"🔍 Total request time: {elapsed:.1f}s")
            
            # Check for slow responses (may indicate socket issues)
            if elapsed > 15:
                tprint(f"⚠️ Slow response ({elapsed:.1f}s) - resetting socket pool")
                response.close()
                reset_socket_pool()
                continue
            
            return response
            
        except Exception as e:
            # Always clean up response on error
            if response:
                try:
                    response.close()
                except:
                    pass
            
            elapsed = time.monotonic() - start_time if 'start_time' in locals() else 0
            error_str = str(e).lower()
            
            tprint(f"❌ HTTP {method} failed (attempt {attempt + 1}/{max_retries}): {e}")
            
            # Bar display specific: Reset socket pool on timeout errors
            if "etimedout" in error_str or "socket" in error_str or "repeated" in error_str:
                tprint("🔧 Networking error detected - resetting socket pool")
                reset_socket_pool()
                time.sleep(1)  # Brief pause after reset
            
            # Progressive retry delay with extra time for socket issues
            if attempt < max_retries - 1:
                retry_delay = RETRY_DELAY * (attempt + 1)
                if "socket" in error_str or "repeated" in error_str or "etimedout" in error_str:
                    retry_delay += 2
                tprint(f"⏳ Retrying in {retry_delay}s...")
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
            tprint(f"✅ Metadata: {current_metadata['title']} - {current_metadata['artist']}")
            return True
        except Exception as e:
            tprint(f"❌ Metadata parse error: {e}")
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
    tprint(f"Status: {message}")



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
    
    # Debug output
    if song_changed:
        tprint(f"🎵 Song changed detected: '{current_metadata['title']}' vs '{last_metadata['title']}'")
    if force_refresh:
        tprint(f"⏰ Force refresh triggered: {time_since_image_update:.1f}s since last update (limit: {FORCE_IMAGE_REFRESH_INTERVAL}s)")
    if first_run:
        tprint(f"🆕 First run detected: last_image_update = {last_image_update}")
    
    needs_update = song_changed or force_refresh or first_run
    if not needs_update:
        tprint(f"✓ No update needed: song_same={not song_changed}, time_ok={not force_refresh}, not_first_run={not first_run}")
    
    return needs_update, song_changed

def smart_update_cycle():
    """Smart polling: check metadata first, handle pending displays, then download if needed"""
    global last_metadata, last_image_update, pending_display_data
    
    try:
        cycle_start = time.monotonic()
        
        # Always check metadata first (lightweight operation)
        tprint("📋 Checking metadata...")
        metadata_start = time.monotonic()
        metadata_success = fetch_metadata()
        metadata_time = time.monotonic() - metadata_start
        tprint(f"📋 Metadata check completed in {metadata_time:.1f}s")
        
        if not metadata_success:
            tprint("❌ Metadata fetch failed")
            return False
        
        # First priority: try to display any pending downloaded data
        if pending_display_data:
            tprint("🔄 Attempting to display previously downloaded image...")
            pending_start = time.monotonic()
            if display_pending_image():
                pending_time = time.monotonic() - pending_start
                tprint(f"✅ Successfully displayed pending image in {pending_time:.1f}s")
                return True
            else:
                pending_time = time.monotonic() - pending_start
                tprint(f"❌ Pending display failed in {pending_time:.1f}s - will try downloading fresh")
                pending_display_data = None  # Clear failed pending data
        
        # Second priority: check if we need to download new image
        tprint("🔄 Checking if image update needed...")
        check_start = time.monotonic()
        needs_image, song_changed = check_if_image_needed()
        check_time = time.monotonic() - check_start
        tprint(f"🔄 Image check completed in {check_time:.1f}s")
        
        if song_changed:
            tprint(f"🎵 Song changed: {current_metadata['title']} - {current_metadata['artist']}")
        
        if not needs_image:
            tprint("✓ Metadata only - no image update needed")
            total_cycle_time = time.monotonic() - cycle_start
            tprint(f"✓ Cycle completed in {total_cycle_time:.1f}s")
            return True
        
        # Download and display server-rendered composite image
        tprint("🔄 Starting image download and display...")
        download_start = time.monotonic()
        result = download_and_display_image()
        download_total_time = time.monotonic() - download_start
        tprint(f"🔄 Download and display completed in {download_total_time:.1f}s")
        
        total_cycle_time = time.monotonic() - cycle_start
        tprint(f"✓ Full cycle completed in {total_cycle_time:.1f}s")
        return result
        
    except Exception as e:
        tprint(f"❌ Smart update error: {e}")
        return False

def display_pending_image():
    """Display previously downloaded image data"""
    global pending_display_data, last_metadata, last_image_update
    
    if not pending_display_data:
        return False

    try:
        bitmap, palette, metadata_snapshot = pending_display_data
        
        tprint(f"🖼️ Displaying: {bitmap.width}x{bitmap.height} composite")
        
        # Create display elements
        tprint("🔄 Creating TileGrid...")
        tilegrid_start = time.monotonic()
        tile_grid = displayio.TileGrid(bitmap, pixel_shader=palette)
        tprint(f"🔄 TileGrid created in {time.monotonic() - tilegrid_start:.1f}s")
        
        tprint("🔄 Creating Group...")
        group_start = time.monotonic()
        group = displayio.Group()
        group.append(tile_grid)
        tprint(f"🔄 Group created in {time.monotonic() - group_start:.1f}s")
        
        # Update display with power-saving measures
        tprint("🔄 Setting root group...")
        root_start = time.monotonic()
        display.root_group = group
        tprint(f"🔄 Root group set in {time.monotonic() - root_start:.1f}s")
        
        # Add small delay before refresh to reduce power spike
        tprint("🔄 Pre-refresh delay...")
        time.sleep(0.1)
        
        tprint("🔄 Refreshing display...")
        refresh_start = time.monotonic()
        display.refresh()
        refresh_time = time.monotonic() - refresh_start
        tprint(f"🔄 Display refreshed in {refresh_time:.1f}s")
        
        tprint("🔄 Post-refresh stabilization...")
        time.sleep(0.1)  # Allow power to stabilize after refresh
        
        # Update tracking after successful display
        tprint("🔄 Updating tracking variables...")
        tracking_start = time.monotonic()
        last_metadata.update(metadata_snapshot)
        last_image_update = time.monotonic()
        pending_display_data = None  # Clear pending data
        tprint(f"🔄 Tracking updated in {time.monotonic() - tracking_start:.1f}s")
        
        tprint(f"✅ Displayed: {metadata_snapshot['title']} by {metadata_snapshot['artist']}")
        return True
        
    except Exception as e:
        tprint(f"❌ Pending display error: {e}")
        return False

def download_and_display_image():
    """Download image - SIMPLIFIED to match working 720x720 approach"""
    global last_metadata, last_image_update, pending_display_data
    
    # Direct image download with retry logic - exactly like working version
    response = http_request_with_retry(IMAGE_URL, method="GET", timeout=HTTP_DOWNLOAD_TIMEOUT)
    
    if response and response.status_code == 200:
        try:
            # Read image data with detailed timing
            tprint(f"🔍 Response status: {response.status_code}")
            tprint("🔍 Reading response.content...")
            content_start = time.monotonic()
            
            try:
                image_data = response.content
                content_time = time.monotonic() - content_start
                tprint(f"🔍 Content read completed in {content_time:.1f}s")
                tprint(f"✅ Downloaded image: {len(image_data)} bytes")
            except Exception as content_error:
                content_time = time.monotonic() - content_start
                tprint(f"❌ Content read failed after {content_time:.1f}s: {content_error}")
                raise
            
            # Simple validation like working version
            if len(image_data) < 1000:
                tprint(f"✗ Downloaded content too small: {len(image_data)} bytes")
                return False
            
            # SIMPLIFIED: Exact same approach as working 720x720 version
            tprint("🔄 Loading image...")
            image_file = BytesIO(image_data)
            
            # Use identical parameters to working version
            bitmap, palette = adafruit_imageload.load(image_file, 
                                                     bitmap=displayio.Bitmap, 
                                                     palette=displayio.Palette)
            image_file.close()
            
            # Validate the loaded image
            if not bitmap or bitmap.width == 0 or bitmap.height == 0:
                tprint(f"✗ Invalid bitmap loaded: {bitmap}")
                return False
            
            tprint(f"✓ Loaded: {bitmap.width}x{bitmap.height} image")
            
            # Store as pending data (with metadata snapshot) - like working version
            metadata_snapshot = dict(current_metadata)
            pending_display_data = (bitmap, palette, metadata_snapshot)
            
            # Update download tracking immediately
            last_metadata = current_metadata.copy()
            last_image_update = time.monotonic()
            
            # Attempt immediate display
            if display_pending_image():
                tprint("✅ Immediate display successful")
                return True
            else:
                tprint("⚠️ Immediate display failed - image stored as pending")
                return False
            
        except Exception as e:
            tprint(f"❌ Image processing error: {e}")
            return False
        finally:
            # Always clean up response
            try:
                response.close()
            except:
                pass
    else:
        if response:
            tprint(f"❌ HTTP error: {response.status_code}")
            try:
                response.close()
            except:
                pass
        else:
            tprint("❌ No response received")
        return False

# Initialize
tprint("✓ Sonos Bar Display ready")
tprint("Features: HD458002C40 display + server-rendered composites")
tprint("Smart polling: 2s metadata checks + hostname resolution")
tprint("Network: SIMPLIFIED approach copied from working 720x720 display")
tprint("Power: Optimized refresh timing to reduce flicker")
tprint("Simple: Basic socket management + minimal retry logic")
tprint("Optimized: Server creates perfect 320×960 images ready for display")
show_status_message("Power-Optimized Display Ready")

# Main loop - smart polling: metadata every 2 seconds, images only when needed
while True:
    try:
        loop_start = time.monotonic()
        tprint("🔄 Starting main loop iteration...")
        
        gc_start = time.monotonic()
        gc.collect()
        tprint(f"🔄 Main loop GC completed in {time.monotonic() - gc_start:.1f}s")
        
        cycle_start = time.monotonic()
        success = smart_update_cycle()
        cycle_time = time.monotonic() - cycle_start
        tprint(f"🔄 Smart update cycle completed in {cycle_time:.1f}s")
        
        if not success:
            tprint("Update failed, retrying...")
        
        # Show pending status if applicable
        pending_status = " (PENDING DISPLAY)" if pending_display_data else ""
        total_loop_time = time.monotonic() - loop_start
        tprint(f"🔄 Total loop time: {total_loop_time:.1f}s")
        tprint(f"🔄 Next check in {METADATA_POLL_INTERVAL}s{pending_status}")
        
        # Fast metadata polling for immediate song change detection
        sleep_start = time.monotonic()
        time.sleep(METADATA_POLL_INTERVAL)
        tprint(f"🔄 Sleep completed in {time.monotonic() - sleep_start:.1f}s")
        
    except KeyboardInterrupt:
        tprint("Stopping smart monitoring...")
        break
    except Exception as e:
        tprint(f"Unexpected error: {e}")
        tprint("Continuing in 1 second...")
        time.sleep(1)
