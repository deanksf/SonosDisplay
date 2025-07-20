# save this as server.py on your laptop
import http.server
import socketserver
import os

PORT = 8000
DIRECTORY = os.path.expanduser("~/Desktop")  # Assuming the image is on your desktop

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

with socketserver.TCPServer(("", PORT), Handler) as httpd:
    print(f"Serving at http://localhost:{PORT}")
    print(f"Files are served from: {DIRECTORY}")
    httpd.serve_forever()