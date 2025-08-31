# smart_battery_logger.py
# Tkinter GUI that logs battery %, AC events, and estimates time to full/empty.
# Cross-platform via psutil.

import os
import sys
import csv
import time
import psutil
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
from collections import deque

LOG_FILE = "battery_log.csv"

# How many recent samples to keep for rate/ETA calculations (percent per second)
RATE_WINDOW = 8  # ~ last 8 samples
MIN_SECONDS_BETWEEN_SAMPLES = 5  # avoid jitter in rate calc

def human_hms(seconds):
    if seconds is None or seconds == "-" or seconds < 0:
        return "—"
    seconds = int(seconds)
    h, r = divmod(seconds, 3600)
    m, s = divmod(r, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"

class BatteryLoggerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Smart Battery Logger")
        self.root.geometry("760x480")
        self.root.minsize(700, 420)

        self.is_logging = False
        self.job_id = None
        self.prev_plugged = None

        # keep recent (timestamp, percent) to compute charge/discharge rate
        self.samples = deque(maxlen=RATE_WINDOW)

        # ====== Top bar ======
        top = ttk.Frame(root, padding=10)
        top.pack(fill="x")

        self.status_label = ttk.Label(top, text="Status: Idle", font=("Segoe UI", 11, "bold"))
        self.status_label.pack(side="left")

        ttk.Label(top, text="  Interval (sec):").pack(side="left", padx=(12, 4))
        self.interval_var = tk.IntVar(value=30)
        interval = ttk.Spinbox(top, from_=5, to=3600, textvariable=self.interval_var, width=6)
        interval.pack(side="left")

        self.start_btn = ttk.Button(top, text="Start", command=self.start_logging)
        self.start_btn.pack(side="left", padx=8)
        self.stop_btn = ttk.Button(top, text="Stop", command=self.stop_logging, state="disabled")
        self.stop_btn.pack(side="left")

        # ====== Gauges ======
        g = ttk.Frame(root, padding=(10, 0))
        g.pack(fill="x", pady=(4, 6))

        self.progress = ttk.Progressbar(g, orient="horizontal", mode="determinate", length=360)
        self.progress.grid(row=0, column=0, padx=(0, 10), pady=(2, 6), sticky="w")

        self.percent_var = tk.StringVar(value="— %")
        ttk.Label(g, textvariable=self.percent_var, width=8).grid(row=0, column=1, sticky="w")

        self.state_var = tk.StringVar(value="—")
        ttk.Label(g, text="State:").grid(row=1, column=0, sticky="w")
        ttk.Label(g, textvariable=self.state_var).grid(row=1, column=1, sticky="w")

        self.eta_var = tk.StringVar(value="—")
        ttk.Label(g, text="ETA (to full/empty):").grid(row=2, column=0, sticky="w")
        ttk.Label(g, textvariable=self.eta_var).grid(row=2, column=1, sticky="w")

        self.os_eta_var = tk.StringVar(value="—")
        ttk.Label(g, text="OS time remaining:").grid(row=3, column=0, sticky="w")
        ttk.Label(g, textvariable=self.os_eta_var).grid(row=3, column=1, sticky="w")

        # ====== Table ======
        mid = ttk.Frame(root, padding=(10, 0))
        mid.pack(fill="both", expand=True)

        cols = ("time", "percent", "state", "plugged", "os_secs_left", "eta_calc", "event")
        self.tree = ttk.Treeview(mid, columns=cols, show="headings")
        headings = {
            "time": "Timestamp",
            "percent": "Percent",
            "state": "State",
            "plugged": "AC",
            "os_secs_left": "OS Secs Left",
            "eta_calc": "ETA (calc sec)",
            "event": "Event"
        }
        widths = {"time": 170, "percent": 80, "state": 110, "plugged": 60,
                  "os_secs_left": 120, "eta_calc": 120, "event": 120}
        for k in cols:
            self.tree.heading(k, text=headings[k])
            self.tree.column(k, width=widths[k], anchor="center")
        self.tree.column("time", anchor="w")
        self.tree.pack(side="left", fill="both", expand=True)

        vsb = ttk.Scrollbar(mid, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")

        # ====== Bottom ======
        bottom = ttk.Frame(root, padding=10)
        bottom.pack(fill="x")
        ttk.Button(bottom, text="Open CSV", command=self.open_csv).pack(side="left")
        ttk.Button(bottom, text="Clear View", command=self.clear_view).pack(side="left", padx=8)
        ttk.Button(bottom, text="Exit", command=self.on_exit).pack(side="right")

        self.ensure_log_header()
        self.refresh_once()

    # ---------- File / UI helpers ----------
    def ensure_log_header(self):
        if not os.path.exists(LOG_FILE):
            with open(LOG_FILE, "w", newline="", encoding="utf-8") as f:
                csv.writer(f).writerow([
                    "timestamp", "percent", "state", "plugged",
                    "os_secs_left", "eta_calc_secs", "event"
                ])

    def append_csv(self, row):
        with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(row)

    def open_csv(self):
        try:
            if os.name == "nt":
                os.startfile(LOG_FILE)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                os.system(f'open "{LOG_FILE}"')
            else:
                os.system(f'xdg-open "{LOG_FILE}"')
        except Exception as e:
            messagebox.showerror("Open CSV", str(e))

    def clear_view(self):
        for i in self.tree.get_children():
            self.tree.delete(i)

    # ---------- Battery sampling & ETA ----------
    def read_sample(self):
        batt = psutil.sensors_battery()
        if not batt:
            return None

        now = time.time()
        percent = float(batt.percent)  # keep float for finer rate
        plugged = bool(batt.power_plugged)
        state = "Charging" if plugged else "Discharging"

        # OS estimate when discharging is often available; charging is usually unlimited/unknown
        if batt.secsleft in (psutil.POWER_TIME_UNKNOWN, psutil.POWER_TIME_UNLIMITED, None):
            os_secs = None
        else:
            os_secs = int(batt.secsleft)

        # Add to window for rate calculation
        add_sample = True
        if self.samples and (now - self.samples[-1][0]) < MIN_SECONDS_BETWEEN_SAMPLES:
            add_sample = False
        if add_sample:
            self.samples.append((now, percent))

        # Compute rate (percent per second) using oldest vs newest in window
        eta_calc_secs = None
        if len(self.samples) >= 2:
            t0, p0 = self.samples[0]
            t1, p1 = self.samples[-1]
            dt = max(1.0, t1 - t0)
            dp = p1 - p0  # +ve if charging, -ve if discharging
            rate = dp / dt  # percent per second

            if state == "Charging":
                if rate > 1e-6 and percent < 100.0:
                    eta_calc_secs = ((100.0 - percent) / rate)
                elif percent >= 100.0:
                    eta_calc_secs = 0
            else:
                if rate < -1e-6 and percent > 0.0:
                    eta_calc_secs = (percent / (-rate))
                elif percent <= 0.0:
                    eta_calc_secs = 0

        return {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "percent": percent,
            "plugged": plugged,
            "state": state,
            "os_secs_left": os_secs,
            "eta_calc_secs": int(eta_calc_secs) if eta_calc_secs is not None else None
        }

    def update_top(self, s):
        self.progress["value"] = s["percent"]
        self.percent_var.set(f"{int(round(s['percent']))} %")
        self.state_var.set(s["state"])
        self.os_eta_var.set(human_hms(s["os_secs_left"]))

        if s["state"] == "Charging":
            if s["eta_calc_secs"] is None:
                eta_text = "Estimating…"
            elif s["eta_calc_secs"] == 0:
                eta_text = "Full"
            else:
                eta_text = f"{human_hms(s['eta_calc_secs'])} to full"
        else:
            # Prefer OS estimate when on battery (usually more accurate)
            if s["os_secs_left"] is not None:
                eta_text = f"{human_hms(s['os_secs_left'])} to empty (OS)"
            elif s["eta_calc_secs"] is not None:
                eta_text = f"{human_hms(s['eta_calc_secs'])} to empty"
            else:
                eta_text = "Estimating…"

        self.eta_var.set(eta_text)
        self.status_label.config(text=f"Status: {s['state']} ({int(round(s['percent']))}%)")

    # ---------- Logging loop with AC plug events ----------
    def log_once(self):
        sample = self.read_sample()
        if sample is None:
            messagebox.showerror("Battery", "Battery information not available.")
            self.stop_logging()
            return

        # Detect plug-in/out event
        event = ""
        if self.prev_plugged is None:
            self.prev_plugged = sample["plugged"]
        elif self.prev_plugged != sample["plugged"]:
            event = "PLUGGED_IN" if sample["plugged"] else "UNPLUGGED"
            self.prev_plugged = sample["plugged"]

        # update UI
        self.update_top(sample)

        # table + CSV
        row = [
            sample["timestamp"],
            f"{sample['percent']:.1f}",
            sample["state"],
            "Yes" if sample["plugged"] else "No",
            sample["os_secs_left"] if sample["os_secs_left"] is not None else "-",
            sample["eta_calc_secs"] if sample["eta_calc_secs"] is not None else "-",
            event
        ]
        self.tree.insert("", "end", values=row)
        self.tree.yview_moveto(1.0)
        self.append_csv(row)

        # reschedule
        if self.is_logging:
            delay_ms = max(1000, int(self.interval_var.get()) * 1000)
            self.job_id = self.root.after(delay_ms, self.log_once)

    # ---------- Controls ----------
    def start_logging(self):
        if self.is_logging:
            return
        try:
            iv = int(self.interval_var.get())
            if iv < 1:
                raise ValueError
        except Exception:
            messagebox.showerror("Interval", "Please enter a valid interval (>=1 sec).")
            return

        self.is_logging = True
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.status_label.config(text="Status: Starting…")
        self.log_once()

    def stop_logging(self):
        self.is_logging = False
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        if self.job_id:
            self.root.after_cancel(self.job_id)
            self.job_id = None
        self.status_label.config(text="Status: Stopped")

    def refresh_once(self):
        s = self.read_sample()
        if s:
            self.update_top(s)

    def on_exit(self):
        self.stop_logging()
        self.root.destroy()


if __name__ == "__main__":
    # Optional: nicer ttk theme
    try:
        style = ttk.Style()
        if "clam" in style.theme_names():
            style.theme_use("clam")
    except Exception:
        pass

    root = tk.Tk()
    app = BatteryLoggerApp(root)
    root.mainloop()
