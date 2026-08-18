# 1. Mask conflicting router service permanently
sudo systemctl stop arduino-router
sudo systemctl mask arduino-router

# 2. Fix the system clock (prevents SSL CERTIFICATE_VERIFY_FAILED error)
# Replace with the current real-world date/time
sudo date -s "18 AUG 2026 10:20:00"

# 3. Reload systemd and start the background serial proxy
sudo systemctl daemon-reload
sudo systemctl restart fridge-bridge

# 4. View live traffic logs
journalctl -u fridge-bridge -f

# 5 changing files 
sudo nano /etc/systemd/system/fridge-bridge.service 
sudo systemctl daemon-reload
sudo systemctl restart fridge-bridge
Check the live logs to make sure your new code didn't introduce a syntax error:

bash
journalctl -u fridge-bridge -f
