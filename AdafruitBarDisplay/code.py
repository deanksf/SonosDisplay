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
from io import BytesIO
from config import SonosCredentials

def tprint(message):
    """Print with timestamp for debugging and log to file"""
    current_time = time.monotonic()
    log_message = f"[{current_time:8.1f}s] {message}"
    print(log_message)

    # Also write to log file on CIRCUITPY drive
    try:
        with open("/log.txt", "a") as f:
            f.write(log_message + "\n")
            f.flush()
    except:
        pass  # Don't let logging errors crash the main program

# WiFi credentials
WIFI_SSID = SonosCredentials.WIFI_SSID
WIFI_PASSWORD = SonosCredentials.WIFI_PASSWORD

# Server URLs - Bar display specific
# IMAGE_URL = "http://192.168.86.60:8000/Adafruit/artwork_bar.bmp"
# METADATA_URL = "http://192.168.86.60:8000/metadata.json"

IMAGE_URL = "http://sonos-display.local:8000/Adafruit/artwork_bar.bmp"
METADATA_URL = "http://sonos-display.local:8000/metadata.json"

# Smart polling intervals
METADATA_POLL_INTERVAL = 2   # Fast metadata polling for song detection
FORCE_IMAGE_REFRESH_INTERVAL = 300  # 5 minutes

# Network settings
HTTP_TIMEOUT = 15
HTTP_DOWNLOAD_TIMEOUT = 180
MAX_RETRIES = 3
RETRY_DELAY = 3

tprint("Starting Sonos Bar Display System...")
tprint("Using bar display configuration (320x960)")

# TFT pins configuration from board
tft_pins = dict(board.TFT_PINS)

# Official Adafruit HD458002C40 initialization sequence for bar display
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

# Initialize I2C and I/O expander
board.I2C().deinit()
i2c = busio.I2C(board.SCL, board.SDA, frequency=100_000)
tft_io_expander = dict(board.TFT_IO_EXPANDER)

# Send the init sequence to the I/O expander
dotclockframebuffer.ioexpander_send_init_sequence(i2c, init_sequence_st7701s, **tft_io_expander)

# Bar display timings - reduced frequency for stability
tft_timings = {
    "frequency": 12000000,      # Reduced from 16MHz for stability
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

# Create the display
tprint("Initializing bar display (320x960)...")
fb = dotclockframebuffer.DotClockFramebuffer(**tft_pins, **tft_timings)
display = FramebufferDisplay(fb, auto_refresh=False)  # Manual refresh only

# Clean up I2C
i2c.deinit()

# Connect to WiFi
tprint(f"Connecting to WiFi: {WIFI_SSID}...")
try:
    wifi.radio.connect(WIFI_SSID, WIFI_PASSWORD)
    tprint(f"✓ Connected to WiFi!")
    tprint(f"✓ IP Address: {wifi.radio.ipv4_address}")
except Exception as e:
    tprint(f"✗ WiFi connection failed: {e}")
    tprint("Please check your WiFi credentials and try again.")
    while True:
        time.sleep(1)

# Set up HTTP requests
pool = socketpool.SocketPool(wifi.radio)
requests = adafruit_requests.Session(pool)

def reset_socket_pool():
    """Reset socket pool to prevent exhaustion"""
    global pool, requests
    tprint("🔧 Resetting socket pool...")

    try:
        requests._session.close()
        pool.close()
    except:
        pass

    gc.collect()
    time.sleep(2)

    pool = socketpool.SocketPool(wifi.radio)
    requests = adafruit_requests.Session(pool)

def http_request_with_retry(url, method="GET", timeout=HTTP_TIMEOUT, max_retries=MAX_RETRIES):
    """HTTP request with retry logic and socket management"""
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
                tprint(f"⚠️ Slow response ({elapsed:.1f}s) - resetting socket pool")
                response.close()
                reset_socket_pool()
                continue

            return response

        except Exception as e:
            elapsed = time.monotonic() - start_time if 'start_time' in locals() else 0
            error_str = str(e).lower()

            tprint(f"❌ HTTP {method} failed (attempt {attempt + 1}/{max_retries}): {e}")

            # Progressive retry delay with extra time for socket issues
            if attempt < max_retries - 1:
                retry_delay = RETRY_DELAY * (attempt + 1)
                if "socket" in error_str or "repeated" in error_str:
                    retry_delay += 2
                tprint(f"⏳ Retrying in {retry_delay}s...")
                time.sleep(retry_delay)

    return None

# Variables for tracking updates and smart polling
current_metadata = {"album": "", "title": "", "artist": ""}
last_displayed_metadata = {"album": "", "title": "", "artist": ""}  # Only updated on successful display
pending_metadata = {"album": "", "title": "", "artist": ""}  # Metadata we want to display
last_image_update = 0
pending_display_data = None  # Stores downloaded image data awaiting display
last_artwork_headers = {'last_modified': '', 'content_length': '0'}  # Track artwork changes

def show_status_message(message):
    """Display a working checkerboard status pattern for bar display"""
    bitmap = displayio.Bitmap(320, 960, 2)
    palette = displayio.Palette(2)
    palette[0] = 0x000000  # Black
    palette[1] = 0xFFFFFF  # White
    
    # Create checkerboard pattern with appropriate squares for bar display
    square_size = 40
    for y in range(960):
        for x in range(320):
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
    display.refresh()  # Manual refresh
    tprint(f"Status displayed: {message}")

def fetch_metadata():
    """Fetch current song metadata"""
    global current_metadata
    
    response = http_request_with_retry(METADATA_URL, method="GET", timeout=HTTP_TIMEOUT)

    if response:
        # DEBUG: Print metadata response headers
        # tprint(f"📋 DEBUG: Metadata response status: {response.status_code}")
        # tprint(f"📋 DEBUG: Metadata response headers:")
        # for header_name, header_value in response.headers.items():
        #     tprint(f"📋 DEBUG:   {header_name}: {header_value}")
        
        try:
            data = response.json()
            # Safety: Ensure we never have None values that could break comparisons
            current_metadata = {
                "album": data.get("album", "") or "",
                "title": data.get("title", "") or "",
                "artist": data.get("artist", "") or ""
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

def check_if_image_needed():
    """Determine if we need to download a new image based on metadata AND artwork changes"""
    global pending_metadata, last_image_update

    # DEBUG: Show current state
    tprint(f"🔍 Current metadata: title='{current_metadata['title']}' artist='{current_metadata['artist']}' album='{current_metadata['album']}'")
    tprint(f"🔍 Last displayed: title='{last_displayed_metadata['title']}' artist='{last_displayed_metadata['artist']}' album='{last_displayed_metadata['album']}'")

    # Check if we have new metadata that hasn't been displayed yet
    title_changed = current_metadata["title"] != last_displayed_metadata["title"]
    artist_changed = current_metadata["artist"] != last_displayed_metadata["artist"]
    album_changed = current_metadata["album"] != last_displayed_metadata["album"]
    
    song_changed = title_changed or artist_changed or album_changed
    
    # DEBUG: Show comparison results
    if title_changed:
        tprint(f"🔍 Title changed: '{last_displayed_metadata['title']}' → '{current_metadata['title']}'")
    if artist_changed:
        tprint(f"🔍 Artist changed: '{last_displayed_metadata['artist']}' → '{current_metadata['artist']}'")
    if album_changed:
        tprint(f"🔍 Album changed: '{last_displayed_metadata['album']}' → '{current_metadata['album']}'")

    # Check if it's been too long since last image update
    current_time = time.monotonic()
    time_since_image_update = current_time - last_image_update
    force_refresh = time_since_image_update > FORCE_IMAGE_REFRESH_INTERVAL

    # First run (no previous image)
    first_run = last_image_update == 0

    # DEBUG: Show timing info
    tprint(f"🔍 Time since last image: {time_since_image_update:.1f}s (force refresh at {FORCE_IMAGE_REFRESH_INTERVAL}s)")
    
    # NEW: Always check if artwork changed (independent of metadata)
    tprint(f"🎨 Checking if artwork changed...")
    artwork_changed = check_artwork_changed()
    
    # Decision logic:
    # 1. Force refresh or first run → always update
    # 2. Metadata changed → update  
    # 3. Artwork changed (even with same metadata) → update
    needs_update = force_refresh or first_run or song_changed or artwork_changed
    
    tprint(f"🔍 Decision factors: song_changed={song_changed}, artwork_changed={artwork_changed}, force_refresh={force_refresh}, first_run={first_run}")
    tprint(f"🔍 Final decision: needs_update={needs_update}")

    # If we need to update, set the pending metadata
    if needs_update:
        pending_metadata = current_metadata.copy()
        tprint(f"🔍 Image update needed - setting pending metadata")
    else:
        tprint(f"🔍 No image update needed")

    return needs_update, song_changed

def download_and_display_image():
    """Download image and attempt immediate display"""
    global last_displayed_metadata, last_image_update

    # Direct image download with retry logic
    response = http_request_with_retry(IMAGE_URL, method="GET", timeout=HTTP_DOWNLOAD_TIMEOUT)

    if response and response.status_code == 200:
        try:
            # Read image data
            image_data = response.content
            tprint(f"✅ Downloaded image: {len(image_data)} bytes")

            # Validate response content before processing
            if len(image_data) < 1000:  # Less than 1KB probably indicates error
                tprint(f"✗ Downloaded content too small: {len(image_data)} bytes")
                return False
            
            # Create BytesIO object from downloaded data
            image_file = BytesIO(image_data)
            
            # Load the image using adafruit_imageload from memory
            bitmap, palette_or_converter = adafruit_imageload.load(image_file, 
                                                                 bitmap=displayio.Bitmap, 
                                                                 palette=displayio.Palette)
            image_file.close()
            
            # Validate the loaded image
            if not bitmap or bitmap.width == 0 or bitmap.height == 0:
                tprint(f"✗ Invalid bitmap loaded: {bitmap}")
                return False
            
            tprint(f"✓ Loaded: {bitmap.width}x{bitmap.height} image")
            
            # Create display elements
            tile_grid = displayio.TileGrid(bitmap, pixel_shader=palette_or_converter)
            group = displayio.Group()
            group.append(tile_grid)

            # Update display
            display.root_group = group
            display.refresh()

            # Update tracking ONLY after successful display
            last_displayed_metadata = pending_metadata.copy()
            last_image_update = time.monotonic()

            tprint(f"✅ Displayed: {pending_metadata['title']} by {pending_metadata['artist']}")
            return True

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

def smart_update_cycle():
    """Smart polling: check metadata first, then download if needed"""
    global last_displayed_metadata, last_image_update

    try:
        # Always check metadata first (lightweight operation)
        tprint("📋 Checking metadata...")
        metadata_success = fetch_metadata()

        if not metadata_success:
            tprint("❌ Metadata fetch failed")
            return False

        # Check if we need to download new image
        tprint("🔍 Checking if image update is needed...")
        needs_image, song_changed = check_if_image_needed()

        if song_changed:
            tprint(f"🎵 Song changed detected!")

        if not needs_image:
            tprint("✓ Metadata only - no image update needed")
            return True

        # Download and display image
        tprint("🖼️ Image update required - starting download...")
        image_success = download_and_display_image()
        
        if not image_success:
            tprint(f"⚠️ Image download failed - will retry on next cycle")
        else:
            tprint(f"✅ Image update completed successfully")
            
        return image_success
        
    except Exception as e:
        tprint(f"❌ Smart update error: {e}")
        return False

def check_artwork_changed():
    """Check if artwork has actually changed on server using HTTP headers"""
    global last_artwork_headers
    
    try:
        # Use HEAD request to get headers without downloading the image
        tprint(f"🎨 Making HEAD request to {IMAGE_URL}...")
        response = http_request_with_retry(IMAGE_URL, method="HEAD", timeout=HTTP_TIMEOUT)
        
        if response:
            # DEBUG: Print ALL response headers
            #tprint(f"🎨 DEBUG: Response status: {response.status_code}")
            #tprint(f"🎨 DEBUG: All response headers:")
            #for header_name, header_value in response.headers.items():
            #    tprint(f"🎨 DEBUG:   {header_name}: {header_value}")
            
            # Get Last-Modified header (headers are lowercase in adafruit_requests)
            last_modified = response.headers.get('last-modified', '')
            content_length = response.headers.get('content-length', '0')
            
            tprint(f"🎨 Server headers: Last-Modified='{last_modified}', Content-Length='{content_length}'")
            tprint(f"🎨 Stored headers: Last-Modified='{last_artwork_headers['last_modified']}', Content-Length='{last_artwork_headers['content_length']}'")
            
            # Check if artwork has actually changed
            artwork_changed = (
                last_modified != last_artwork_headers['last_modified'] or
                content_length != last_artwork_headers['content_length']
            )
            
            if artwork_changed:
                tprint(f"🎨 Artwork changed detected:")
                tprint(f"   Last-Modified: '{last_artwork_headers['last_modified']}' → '{last_modified}'")
                tprint(f"   Content-Length: '{last_artwork_headers['content_length']}' → '{content_length}'")
                
                # Update tracking
                last_artwork_headers['last_modified'] = last_modified
                last_artwork_headers['content_length'] = content_length
            else:
                tprint(f"🎨 Artwork unchanged (headers match)")
            
            response.close()
            return artwork_changed
            
        else:
            tprint(f"❌ No response from artwork check")
            return False  # Fixed: Don't assume change on network failure
            
    except Exception as e:
        tprint(f"❌ Artwork check failed: {e}")
        # Fixed: If we can't check, don't assume it changed (prevents false downloads)
        return False
        
    return False  # Default to no change if check fails

# Show initial status
tprint("✓ Bar display initialized (320x960)")
tprint("✓ WiFi connected")
tprint(f"✓ Image URL: {IMAGE_URL}")
tprint(f"✓ Metadata URL: {METADATA_URL}")
tprint("✓ Smart polling: 2s metadata checks, images only on song changes")

show_status_message("SMART POLLING - Waiting for metadata...")

# Main loop - smart polling: metadata every 2 seconds, images only when needed
tprint("Starting smart Sonos monitoring...")
tprint("📋 Metadata polling: 2 seconds")
tprint("🖼️ Image downloads: Only on song changes or every 5 minutes")

while True:
    try:
        success = smart_update_cycle()
        
        if not success:
            tprint("Update failed, retrying...")
        
        tprint(f"🔄 Next check in {METADATA_POLL_INTERVAL}s")

        # Fast metadata polling for immediate song change detection
        time.sleep(METADATA_POLL_INTERVAL)
        
    except KeyboardInterrupt:
        tprint("Stopping smart monitoring...")
        break
    except Exception as e:
        tprint(f"Unexpected error: {e}")
        tprint("Continuing in 1 second...")
        time.sleep(1)