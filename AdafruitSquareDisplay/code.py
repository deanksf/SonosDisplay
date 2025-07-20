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

# WiFi credentials - UPDATE THESE
WIFI_SSID = SonosCredentials.WIFI_SSID
WIFI_PASSWORD  = SonosCredentials.WIFI_PASSWORD

# Server URLs
IMAGE_URL = "http://sonos-display.local:8000/Adafruit/artwork.bmp"
METADATA_URL = "http://sonos-display.local:8000/metadata.json"

# Smart polling intervals
METADATA_POLL_INTERVAL = 2   # Very fast metadata-only polling for song detection
IDLE_POLL_INTERVAL = 15     # Very slow when no music detected

# Network settings
HTTP_TIMEOUT = 10
HTTP_DOWNLOAD_TIMEOUT = 30
MAX_RETRIES = 3
RETRY_DELAY = 3

print("Starting Sonos Qualia Display System...")
print("Using VERY SLOW FLICKER configuration with FULL COLOR support")

# TFT pins configuration from board
tft_pins = dict(board.TFT_PINS)

# TL040HDS20 needs NO initialization sequence
init_sequence_tl040hds20 = bytes()

# Initialize I2C and I/O expander
board.I2C().deinit()
i2c = busio.I2C(board.SCL, board.SDA, frequency=100_000)
tft_io_expander = dict(board.TFT_IO_EXPANDER)
#tft_io_expander['i2c_address'] = 0x38 # uncomment for rev B

# Send the empty init sequence to the I/O expander
dotclockframebuffer.ioexpander_send_init_sequence(i2c, init_sequence_tl040hds20, **tft_io_expander)

# ORIGINAL WORKING SETTINGS - Reduced frequency for stability
tft_timings = {
    "frequency": 6000000,       # Reduced from 8MHz to 6MHz for stability
    "width": 720,
    "height": 720,
    "hsync_pulse_width": 6,     # Original working values
    "hsync_front_porch": 60,    
    "hsync_back_porch": 54,     
    "vsync_pulse_width": 6,     
    "vsync_front_porch": 24,    
    "vsync_back_porch": 26,     
    "hsync_idle_low": True,     
    "vsync_idle_low": True,     
    "de_idle_high": False,      
    "pclk_active_high": True,   
    "pclk_idle_high": True,     
}

# Create the display with our very slow flicker configuration
print("Initializing display with VERY SLOW FLICKER (5MHz) settings...")
fb = dotclockframebuffer.DotClockFramebuffer(**tft_pins, **tft_timings)
display = FramebufferDisplay(fb, auto_refresh=False)  # Manual refresh only

# Clean up I2C
i2c.deinit()

# Connect to WiFi
print(f"Connecting to WiFi: {WIFI_SSID}...")
try:
    wifi.radio.connect(WIFI_SSID, WIFI_PASSWORD)
    print(f"✓ Connected to WiFi!")
    print(f"✓ IP Address: {wifi.radio.ipv4_address}")
except Exception as e:
    print(f"✗ WiFi connection failed: {e}")
    print("Please check your WiFi credentials and try again.")
    while True:
        time.sleep(1)

# Set up HTTP requests
pool = socketpool.SocketPool(wifi.radio)
requests = adafruit_requests.Session(pool)

def reset_socket_pool():
    """Reset socket pool to prevent exhaustion"""
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
force_image_refresh_interval = 60  # Force image refresh every 60 seconds
pending_display_data = None  # Stores downloaded image data awaiting display

def show_status_message(message):
    """Display a working checkerboard status pattern"""
    # Use the checkerboard pattern we know works
    bitmap = displayio.Bitmap(720, 720, 2)
    palette = displayio.Palette(2)
    palette[0] = 0x000000  # Black
    palette[1] = 0xFFFFFF  # White
    
    # Create checkerboard pattern with 60x60 pixel squares
    for y in range(720):
        for x in range(720):
            square_x = x // 60
            square_y = y // 60
            if (square_x + square_y) % 2 == 0:
                bitmap[x, y] = 0
            else:
                bitmap[x, y] = 1
    
    tile_grid = displayio.TileGrid(bitmap, pixel_shader=palette)
    group = displayio.Group()
    group.append(tile_grid)
    display.root_group = group
    display.refresh()  # Manual refresh
    print(f"Status displayed: {message}")

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
    force_refresh = time_since_image_update > force_image_refresh_interval
    
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
        
        # Download and display image
        print("🖼️ Downloading image...")
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
        bitmap, palette_or_converter, metadata_snapshot = pending_display_data
        
        print(f"🖼️ Displaying: {bitmap.width}x{bitmap.height} image")
        
        # Create display elements
        tile_grid = displayio.TileGrid(bitmap, pixel_shader=palette_or_converter)
        group = displayio.Group()
        group.append(tile_grid)
        
        # Update display
        display.root_group = group
        display.refresh()
        
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
    
    # Direct image download with retry logic
    response = http_request_with_retry(IMAGE_URL, method="GET", timeout=HTTP_DOWNLOAD_TIMEOUT)
    
    if response and response.status_code == 200:
        try:
            # Read image data
            image_data = response.content
            print(f"✅ Downloaded image: {len(image_data)} bytes")
            
            # Validate response content before processing
            if len(image_data) < 1000:  # Less than 1KB probably indicates error
                print(f"✗ Downloaded content too small: {len(image_data)} bytes")
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
                print(f"✗ Invalid bitmap loaded: {bitmap}")
                return False
            
            print(f"✓ Loaded: {bitmap.width}x{bitmap.height} image")
            
            # Store as pending data (with metadata snapshot) in case display fails
            metadata_snapshot = dict(current_metadata)  # Create snapshot
            pending_display_data = (bitmap, palette_or_converter, metadata_snapshot)
            
            # Update download tracking immediately to prevent re-downloads
            last_metadata = current_metadata.copy()
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
            print(f"❌ Image processing error: {e}")
            
            # Fallback pattern on error
            try:
                bitmap = displayio.Bitmap(720, 720, 2)
                palette = displayio.Palette(2)
                palette[0] = 0x202020  # Dark gray
                palette[1] = 0x404040  # Slightly lighter gray
                
                # Create subtle checkerboard pattern
                for y in range(720):
                    for x in range(720):
                        square_x = x // 60
                        square_y = y // 60
                        if (square_x + square_y) % 2 == 0:
                            bitmap[x, y] = 0
                        else:
                            bitmap[x, y] = 1
                
                tile_grid = displayio.TileGrid(bitmap, pixel_shader=palette)
                group = displayio.Group()
                group.append(tile_grid)
                display.root_group = group
                display.refresh()
                
                print(f"✓ Fallback pattern displayed")
                return True
                
            except Exception as e2:
                print(f"✗ Fallback error: {e2}")
                return False
        finally:
            # Always clean up response
            try:
                response.close()
            except:
                pass
    else:
        if response:
            print(f"❌ HTTP error: {response.status_code}")
            try:
                response.close()
            except:
                pass
        else:
            print("❌ No response received")
        return False

# Show initial status
print("✓ Display initialized with VERY SLOW FLICKER configuration")
print("✓ Settings: 5MHz frequency + Inverted sync + Manual refresh + FULL COLOR")
print("✓ WiFi connected")
print(f"✓ Image URL: {IMAGE_URL}")
print(f"✓ Metadata URL: {METADATA_URL}")
print("✓ Smart polling: 2s metadata checks, images only on song changes")
print("✓ Display: Robust retry system prevents re-downloads")
print("")
print("FEATURES: Smart polling + 90% fewer downloads + Instant song detection + Display Fix")
print("")

show_status_message("SMART POLLING - Waiting for metadata...")

# Main loop - smart polling: metadata every 2 seconds, images only when needed
print("Starting smart Sonos monitoring...")
print("📋 Metadata polling: 2 seconds")
print("🖼️ Image downloads: Only on song changes or every 60 seconds")

while True:
    try:
        success = smart_update_cycle()
        
        if not success:
            print("Update failed, retrying...")
        
        # Show pending status if applicable
        pending_status = " (PENDING DISPLAY)" if pending_display_data else ""
        print(f"🔄 Next check in {METADATA_POLL_INTERVAL}s{pending_status}")
        
        # Fast metadata polling for immediate song change detection
        time.sleep(METADATA_POLL_INTERVAL)
        
    except KeyboardInterrupt:
        print("Stopping smart monitoring...")
        break
    except Exception as e:
        print(f"Unexpected error: {e}")
        print("Continuing in 1 second...")
        time.sleep(1)
