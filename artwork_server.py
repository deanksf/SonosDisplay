#!/usr/bin/env python3

import http.server
import socketserver
import threading
import os
import json
from datetime import datetime
import signal
import sys

# Configuration
PORT = 8000
DIRECTORY = "/home/deankondo/sonos-display"
MAX_CONNECTIONS = 10  # Reduced from 20 to prevent resource exhaustion
MAX_THREADS = 8  # Limit concurrent threads to prevent Raspberry Pi overload
REQUEST_TIMEOUT = 30  # Timeout for requests in seconds

class FixedSonosHandler(http.server.SimpleHTTPRequestHandler):
    """HTTP handler with proper header ordering and download support"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)
    
    def log_message(self, format, *args):
        """Minimal logging with thread info"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        thread_id = threading.current_thread().name
        print(f"[{timestamp}] [{thread_id}] {format % args}")
    
    def do_GET(self):
        """Handle GET requests with proper HTTP protocol"""
        # Essential files only - proper header order in each method
        if self.path == '/metadata.json':
            self.serve_metadata()
        elif self.path == '/Adafruit/artwork_bar.bmp':
            self.serve_file('Adafruit/artwork_bar.bmp', 'image/bmp')
        elif self.path == '/Adafruit/artwork.bmp':
            self.serve_file('Adafruit/artwork.bmp', 'image/bmp')
        elif self.path == '/' or self.path == '/status':
            self.serve_status()
        else:
            self.send_error(404, "File not found")
    
    def do_HEAD(self):
        """Handle HEAD requests for artwork change detection"""
        if self.path == '/metadata.json':
            self.serve_metadata_head()
        elif self.path == '/Adafruit/artwork_bar.bmp':
            self.serve_file_head('Adafruit/artwork_bar.bmp', 'image/bmp')
        elif self.path == '/Adafruit/artwork.bmp':
            self.serve_file_head('Adafruit/artwork.bmp', 'image/bmp')
        else:
            self.send_error(404, "File not found")
    
    def serve_metadata(self):
        """Serve metadata.json with proper headers"""
        try:
            metadata_path = os.path.join(DIRECTORY, 'Adafruit/current_metadata.json')
            
            if os.path.exists(metadata_path):
                with open(metadata_path, 'r') as f:
                    data = f.read()
                
                mod_time = os.path.getmtime(metadata_path)
                last_modified = datetime.fromtimestamp(mod_time).strftime('%a, %d %b %Y %H:%M:%S GMT')
                
                # Proper HTTP header order: response, headers, end_headers, content
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(data.encode())))
                self.send_header('Last-Modified', last_modified)
                self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('Connection', 'close')
                self.end_headers()
                self.wfile.write(data.encode())
            else:
                # Return default metadata
                default_metadata = {
                    "title": "No music playing",
                    "artist": "",
                    "album": "",
                    "last_updated": 0
                }
                
                json_data = json.dumps(default_metadata)
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(json_data.encode())))
                self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('Connection', 'close')
                self.end_headers()
                self.wfile.write(json_data.encode())
                
        except Exception as e:
            print(f"Error serving metadata: {e}")
            self.send_error(500, "Internal server error")
    
    def serve_file(self, filepath, content_type):
        """Serve files with proper download headers and chunked transfer"""
        try:
            full_path = os.path.join(DIRECTORY, filepath)
            
            if not os.path.exists(full_path):
                self.send_error(404, f"File not found: {filepath}")
                return
            
            file_size = os.path.getsize(full_path)
            mod_time = os.path.getmtime(full_path)
            last_modified = datetime.fromtimestamp(mod_time).strftime('%a, %d %b %Y %H:%M:%S GMT')
            
            # Check for incomplete files
            if file_size < 1000:
                print(f"Warning: {filepath} is small ({file_size} bytes), may be incomplete")
            
            with open(full_path, 'rb') as f:
                # Proper HTTP header order
                self.send_response(200)
                self.send_header('Content-Type', content_type)
                self.send_header('Content-Length', str(file_size))
                self.send_header('Last-Modified', last_modified)
                # Proper download headers to fix Chrome "insecure download" issue
                self.send_header('Content-Disposition', f'inline; filename="{os.path.basename(filepath)}"')
                self.send_header('Accept-Ranges', 'bytes')
                self.send_header('Cache-Control', 'public, max-age=5')  # Very short cache
                self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('Connection', 'close')
                self.end_headers()
                
                # Stream file efficiently with timeout protection
                bytes_sent = 0
                chunk_size = 4096  # Reduced from 8KB to 4KB for better Raspberry Pi performance
                
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    try:
                        self.wfile.write(chunk)
                        bytes_sent += len(chunk)
                        # Flush periodically to prevent memory buildup
                        if bytes_sent % (chunk_size * 10) == 0:
                            self.wfile.flush()
                    except BrokenPipeError:
                        print(f"Client disconnected during {filepath} transfer")
                        break
                    except Exception as e:
                        print(f"Error during {filepath} transfer: {e}")
                        break
                
                print(f"✅ Served {filepath}: {bytes_sent}/{file_size} bytes (last_modified: {last_modified})")
                    
        except Exception as e:
            print(f"❌ Error serving {filepath}: {e}")
            self.send_error(500, "Internal server error")
    
    def serve_status(self):
        """Serve status page"""
        try:
            metadata_path = os.path.join(DIRECTORY, 'Adafruit/current_metadata.json')
            artwork_path = os.path.join(DIRECTORY, 'Adafruit/artwork_bar.bmp')
            
            active_threads = threading.active_count()
            
            status_info = {
                "metadata_exists": os.path.exists(metadata_path),
                "artwork_exists": os.path.exists(artwork_path),
                "artwork_size": os.path.getsize(artwork_path) if os.path.exists(artwork_path) else 0,
                "active_threads": active_threads
            }
            
            html = f"""
            <!DOCTYPE html>
            <html>
            <head><title>Fixed Sonos Display Server</title></head>
            <body>
                <h1>Fixed Sonos Display Server</h1>
                <p>Status: <strong>Running</strong></p>
                <p>Time: {datetime.now().isoformat()}</p>
                <h2>Files:</h2>
                <ul>
                    <li><a href="/metadata.json">metadata.json</a> - {'✅' if status_info['metadata_exists'] else '❌'}</li>
                    <li><a href="/Adafruit/artwork_bar.bmp">artwork_bar.bmp</a> - {'✅' if status_info['artwork_exists'] else '❌'} ({status_info['artwork_size']} bytes)</li>
                </ul>
                <p>Active threads: {active_threads}</p>
                <p><em>Fixed HTTP headers for proper downloads</em></p>
            </body>
            </html>
            """
            
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.send_header('Content-Length', str(len(html.encode())))
            self.send_header('Cache-Control', 'no-cache')
            self.send_header('Connection', 'close')
            self.end_headers()
            self.wfile.write(html.encode())
            
        except Exception as e:
            print(f"❌ Error serving status: {e}")
            self.send_error(500, "Internal server error")
    
    def serve_metadata_head(self):
        """Handle HEAD request for metadata"""
        try:
            metadata_path = os.path.join(DIRECTORY, 'Adafruit/current_metadata.json')
            
            if os.path.exists(metadata_path):
                file_size = os.path.getsize(metadata_path)
                mod_time = os.path.getmtime(metadata_path)
                last_modified = datetime.fromtimestamp(mod_time).strftime('%a, %d %b %Y %H:%M:%S GMT')
                
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(file_size))
                self.send_header('Last-Modified', last_modified)
                self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('Connection', 'close')
                self.end_headers()
            else:
                # Default metadata size
                default_size = len('{"title":"No music playing","artist":"","album":"","last_updated":0}')
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(default_size))
                self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('Connection', 'close')
                self.end_headers()
                
        except Exception as e:
            print(f"Error serving metadata HEAD: {e}")
            self.send_error(500, "Internal server error")
    
    def serve_file_head(self, filepath, content_type):
        """Handle HEAD request for files - crucial for artwork change detection"""
        try:
            full_path = os.path.join(DIRECTORY, filepath)
            
            if not os.path.exists(full_path):
                self.send_error(404, f"File not found: {filepath}")
                return
            
            file_size = os.path.getsize(full_path)
            mod_time = os.path.getmtime(full_path)
            last_modified = datetime.fromtimestamp(mod_time).strftime('%a, %d %b %Y %H:%M:%S GMT')
            
            print(f"🎨 HEAD {filepath}: size={file_size}, last_modified={last_modified}")
            
            # Send headers only (no body for HEAD)
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(file_size))
            self.send_header('Last-Modified', last_modified)  # CRITICAL: This was missing!
            self.send_header('Content-Disposition', f'inline; filename="{os.path.basename(filepath)}"')
            self.send_header('Accept-Ranges', 'bytes')
            self.send_header('Cache-Control', 'public, max-age=5')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Connection', 'close')
            self.end_headers()
            
        except Exception as e:
            print(f"❌ Error serving HEAD {filepath}: {e}")
            self.send_error(500, "Internal server error")

class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    """TCP Server with threading support and resource limits"""
    allow_reuse_address = True
    daemon_threads = True
    request_queue_size = MAX_CONNECTIONS
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.socket.setsockopt(socketserver.socket.SOL_SOCKET, socketserver.socket.SO_REUSEADDR, 1)
        # Set socket timeout to prevent hanging connections
        self.socket.settimeout(REQUEST_TIMEOUT)
    
    def verify_request(self, request, client_address):
        """Limit concurrent connections to prevent resource exhaustion"""
        active_threads = threading.active_count()
        if active_threads > MAX_THREADS:
            print(f"⚠️ Too many active threads ({active_threads}), rejecting connection from {client_address}")
            return False
        return True

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    print(f"\nShutting down server...")
    sys.exit(0)

def main():
    """Start the fixed HTTP server"""
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    os.chdir(DIRECTORY)
    
    print(f"🚀 Starting Fixed Sonos Display Server")
    print(f"📁 Directory: {DIRECTORY}")
    print(f"🌐 Port: {PORT}")
    print(f"🔧 Fixed: Proper HTTP headers for downloads")
    print(f"🛡️ Resource Limits: Max {MAX_THREADS} threads, {MAX_CONNECTIONS} connections")
    print(f"⏱️ Request timeout: {REQUEST_TIMEOUT}s, Chunk size: 4KB")
    print(f"📋 Endpoints:")
    print(f"   • http://localhost:{PORT}/metadata.json")
    print(f"   • http://localhost:{PORT}/Adafruit/artwork_bar.bmp")
    print(f"   • http://localhost:{PORT}/status")
    print("")
    
    try:
        with ThreadedTCPServer(("", PORT), FixedSonosHandler) as httpd:
            print(f"✅ Server started at http://localhost:{PORT}")
            print("🔄 Threading enabled, proper headers fixed")
            print("Press Ctrl+C to stop")
            httpd.serve_forever()
    except OSError as e:
        if e.errno == 98:
            print(f"❌ Port {PORT} already in use!")
            print("Stop existing server: sudo systemctl stop artwork_server.service")
        else:
            print(f"❌ Server error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 