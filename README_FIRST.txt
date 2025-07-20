SonosArtworkCompleteProject is the most current code

This is stored on GitHub
- Repo SonosArtwork
- Branch 'main'
- config.py files have been excluded


You may want to get the most recent files from the devices to be sure you have the most current versions
- get_metadata_soco.py monitors Sonos, gets the artwork and hosts them on a localhost URL
- get_metadata_soco.py run in the directory sonos-display on the Raspberry Pi
- Adafruit*/code.py runs on the respective Qualia display devices

To see output of a Qualia device use Mu Editor on Mac
- Open Mu Editor
- Connect Qualia
- Click 'Serial'

To connect to Raspberry Pi:
ssh deankondo@sonos-display.local

PW same as mac

To see if web server is running:
sudo systemctl status sonos-web

To see if sonos monitor is running:
sudo systemctl status sonos-display

Restart get_metadata_soco on Raspberry Pi
ssh deankondo@sonos-display.local "sudo systemctl restart get_metadata_soco.service"

To see if the copy service (Raspberry Pi to Adafruit) is running:
sudo systemctl status sonos-usb

To see Adafruit display code running, connect to Mac via USB-C cable, open Mu Editor and click 'Serial'

View Live Logs (Real-time)
ssh deankondo@sonos-display.local "sudo journalctl -u get_metadata_soco.service -f"

View Recent Logs (Last 50 entries)
ssh deankondo@sonos-display.local "sudo journalctl -u get_metadata_soco.service -n 50"

View Both Services Status
ssh deankondo@sonos-display.local "sudo systemctl status get_metadata_soco.service artwork_server.service"

View Artwork Server Logs
ssh deankondo@sonos-display.local "sudo journalctl -u artwork_server.service -f"

Monitor resources on the raspberry pi
ssh deankondo@sonos-display.local 'sonos-display/monitor_pi_load.sh 600' | tee local_pi_monitor.log


Write log files to disk on mac:
cat /dev/tty.usbmodem* > qualia_log.txt

