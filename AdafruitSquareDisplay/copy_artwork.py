import os
import time
import shutil
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class ArtworkHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if event.src_path.endswith('artwork.bmp'):
            print(f"\n=== New artwork detected ===")
            print(f"Source: {event.src_path}")
            print(f"File size: {os.path.getsize(event.src_path)} bytes")
            print(f"Last modified: {time.ctime(os.path.getmtime(event.src_path))}")
            
            # Wait a moment to ensure file is completely written
            time.sleep(0.5)
            try:
                # Copy to the Qualia device
                dest = '/media/deankondo/CIRCUITPY/artwork.bmp'
                print(f"\nAttempting to copy to: {dest}")
                
                # Check if destination exists and is writable
                if os.path.exists('/media/deankondo/CIRCUITPY'):
                    print("✓ Qualia mount point exists")
                    # Ensure the destination is writable
                    print("Remounting as read-write...")
                    os.system('sudo mount -o remount,rw /media/deankondo/CIRCUITPY')
                    time.sleep(1)  # Give it a moment to remount
                    
                    # Check if we can write to the destination
                    if os.access('/media/deankondo/CIRCUITPY', os.W_OK):
                        print("✓ Destination is writable")
                        print("Copying file...")
                        shutil.copy2(event.src_path, dest)
                        print(f"✓ Successfully copied to {dest}")
                        print(f"New file size: {os.path.getsize(dest)} bytes")
                        print(f"New file modified: {time.ctime(os.path.getmtime(dest))}")
                    else:
                        print("✗ Destination is not writable")
                else:
                    print("✗ Qualia mount point does not exist")
            except Exception as e:
                print(f"✗ Error copying file: {e}")
                print(f"Error type: {type(e)}")
                print(f"Error details: {str(e)}")

if __name__ == "__main__":
    path = '/home/deankondo/sonos-display/Adafruit'
    event_handler = ArtworkHandler()
    observer = Observer()
    observer.schedule(event_handler, path, recursive=False)
    observer.start()
    print(f"\n=== Starting artwork monitor ===")
    print(f"Watching {path} for artwork changes...")
    print(f"Current permissions on watch directory: {oct(os.stat(path).st_mode)[-3:]}")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join() 