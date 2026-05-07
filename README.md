# Laptop Battery Data Logger

A GUI-based Python app for laptop battery monitoring and logging.

## Features

- Live battery percentage
- Charging/discharging state
- Plug-in and plug-out event detection
- Timestamped CSV logs
- CPU, RAM, and disk usage logging
- Real-time graph visualization
- Excel export
- Low battery alert

## Installation

```bash
pip install -r requirements.txt
```

## Run

```bash
python main.py
```

## Output Files

Logs are saved in:

```text
logs/battery_log.csv
logs/battery_events.csv
```

Excel reports are saved/exported into:

```text
exports/
```

## Notes

This application uses `psutil.sensors_battery()`. On desktop PCs without a battery, battery data may not be available.
