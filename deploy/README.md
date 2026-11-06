# Linux Deployment Guide for HMS Machine Interface

This guide explains how to deploy and run the HMS Machine Interface on Linux (Ubuntu, Debian, RHEL, CentOS).

---

## 1. Prerequisites (Crucial!)

> [!IMPORTANT]
> **Use Python 3.10 or Python 3.11.**
> Django 3.2 uses the standard `cgi` module, which was removed in Python 3.13+.
> Ensure Python 3.11 is installed on your Linux machine:
> ```bash
> sudo apt update
> sudo apt install -y python3.11 python3.11-venv python3.11-dev git
> ```

---

## 2. Setup Virtual Environment & Install Dependencies

```bash
cd /path/to/HMS_Infterface

# Create virtual environment with Python 3.11
python3.11 -m venv venv

# Activate and install dependencies
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

---

## 3. Option A: Run via Scripts (Simple & Direct)

Make the scripts executable:
```bash
chmod +x start_all.sh stop_all.sh status.sh
```

- **Start Services**:
  ```bash
  ./start_all.sh
  ```
  *(Starts both Django Server on Port 1310 and the Automation Worker with crash-guard).*

- **Check Status & Queue**:
  ```bash
  ./status.sh
  ```

- **Stop Services**:
  ```bash
  ./stop_all.sh
  ```

---

## 4. Option B: Run via Systemd Services (Recommended for 24/7 Production)

Systemd automatically launches the services on system boot and restarts them immediately if they exit.

1. **Edit service files with your actual project directory**:
   In `deploy/hmsmi-server.service` and `deploy/hmsmi-worker.service`, replace `/path/to/HMS_Infterface` with your real path (e.g. `/home/ubuntu/HMS_Infterface`).

2. **Copy service files to systemd**:
   ```bash
   sudo cp deploy/hmsmi-server.service /etc/systemd/system/
   sudo cp deploy/hmsmi-worker.service /etc/systemd/system/
   sudo systemctl daemon-reload
   ```

3. **Enable & Start Services**:
   ```bash
   sudo systemctl enable --now hmsmi-server
   sudo systemctl enable --now hmsmi-worker
   ```

4. **Check Service Status**:
   ```bash
   sudo systemctl status hmsmi-server
   sudo systemctl status hmsmi-worker
   ```

5. **View Live Logs**:
   ```bash
   tail -f logs/server.log
   tail -f logs/automation.log
   ```

