# Laptop Battery Data Logger

A GUI-based Python application for monitoring and recording laptop battery usage in real time.

This project shows live battery status, records timestamped logs, detects charger plug-in / plug-out events, monitors CPU/RAM/Disk usage, draws real-time graphs, and exports logs to Excel.

## Features

- Live battery percentage display
- Charging / discharging status
- Charger plug-in and plug-out event logging
- Timestamped CSV battery logs
- CPU usage logging
- RAM usage logging
- Disk usage logging
- Real-time graph visualization
- Low battery alert
- Excel report export
- Logs folder and exports folder included
- Simple Tkinter GUI

## Project Structure

```text
battery-data-logger/
│
├── main.py
├── requirements.txt
├── README.md
├── LICENSE
├── .gitignore
│
├── src/
│   └── battery_logger_gui.py
│
├── logs/
│   └── .gitkeep
│
├── exports/
│   └── .gitkeep
│
├── assets/
│   └── .gitkeep
│
└── screenshots/
    └── .gitkeep
```

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/your-username/battery-data-logger.git
cd battery-data-logger
```

### 2. Create a virtual environment

#### Windows

```bash
python -m venv .venv
.venv\Scripts\activate
```

#### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

## Run the App

```bash
python main.py
```

## Output Files

The app automatically creates these files:

```text
logs/battery_log.csv
logs/battery_events.csv
```

Excel exports are saved in:

```text
exports/
```

## Logged Data Columns

```text
timestamp
battery_percent
battery_state
plugged
seconds_left
time_left
cpu_percent
ram_percent
disk_percent
os_name
```

## Event Log Columns

```text
timestamp
event
battery_percent
```

Example events:

```text
Charger Plugged In
Charger Plugged Out
Low Battery Alert: 20%
```

## Build EXE for Windows Optional

Install PyInstaller:

```bash
pip install pyinstaller
```

Create executable:

```bash
pyinstaller --onefile --windowed main.py
```

The EXE file will be available inside the `dist/` folder.

## Notes

- Battery information depends on your operating system and laptop hardware.
- Some desktop computers may not return battery data.
- On Linux, battery permissions and desktop environment can affect available data.

## License

This project is licensed under the MIT License.
