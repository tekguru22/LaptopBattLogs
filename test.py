# gui_battery_logger.py
# A tiny Tkinter GUI to log laptop battery status to CSV.
# Works on Windows/macOS/Linux (psutil required).

import os
import csv
import psutil
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime

LOG_FILE = "battery_log.csv"

class BatteryLoggerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Battery Logger")
        self.root.geometry("680x420")
        self.root.minsize(640, 400)

        self.is_logging = False
        self.job_id = None

        # ===== Top controls =====
        top = ttk.Frame(root, padding=10)
        top.pack(fill="x")

        self.status_label = ttk.Label(top, text="Status: Idle", font=("Segoe UI", 11, "bold"))
        self.status_label.pack(side="left")

        ttk.Label(top, text="  Interval (sec):").pack(side="left", padx=(12, 4))
        self.interval_var = tk.IntVar(value=60)
        self.interval_spin = ttk.Spinbox(top, from_=5, to=3600, textvariable=self.interval_var, width=6)
        self.interval_spin.pack(side="left")

        self.start_btn = ttk.Button(top, text="Start", command=self.start_logging)
        self.start_btn.pack(side="left", padx=8)
        self.stop_btn = ttk.Button(top, text="Stop", command=self.stop_logging, state="disabled")
        self.stop_btn.pack(side="left")

        # ===== Battery summary panel =====
        panel = ttk.Frame(root, padding=(10, 0))
        panel.pack(fill="x", pady=6)

        self.percent_var = tk.StringVar(value="— %")
        self.state_var = tk.StringVar(value="—")
        self.time_left_var = tk.StringVar(value="—")

        # Progress
        self.progress = ttk.Progressbar(panel, orient="horizontal", mode="determinate", length=300)
        self.progress.grid(row=0, column=0, padx=(0, 10), pady=(6, 2), sticky="w")

        ttk.Label(panel, textvariable=self.percent_var, width=6).grid(row=0, column=1, sticky="w", pady=(6,2))
        ttk.Label(panel, text="State: ").grid(row=1, column=0, sticky="w")
        ttk.Label(panel, textvariable=self.state_var).grid(row=1, column=1, sticky="w")
        ttk.Label(panel, text="Time Left: ").grid(row=2, column=0, sticky="w")
        ttk.Label(panel, textvariable=self.time_left_var).grid(row=2, column=1, sticky="w")

        for i in range(2):
            panel.grid_columnconfigure(i, weight=0)

        # ===== Log view =====
        mid = ttk.Frame(root, padding=(10, 0))
        mid.pack(fill="both", expand=True)

        columns = ("time", "percent", "state", "secs_left")
        self.tree = ttk.Treeview(mid, columns=columns, show="headings", height=10)
        self.tree.heading("time", text="Timestamp")
        self.tree.heading("percent", text="Percent")
        self.tree.heading("state", text="State")
        self.tree.heading("secs_left", text="Seconds Left")
        self.tree.column("time", width=180, anchor="w")
        self.tree.column("percent", width=80, anchor="center")
        self.tree.column("state", width=120, anchor="center")
        self.tree.column("secs_left", width=120, anchor="center")
        self.tree.pack(side="left", fill="both", expand=True)

        vsb = ttk.Scrollbar(mid, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")

        # ===== Bottom bar =====
        bottom = ttk.Frame(root, padding=10)
        bottom.pack(fill="x")

        ttk.Button(bottom, text="Open Log…", command=self.open_log).pack(side="left")
        ttk.Button(bottom, text="Clear View", command=self.clear_view).pack(side="left", padx=8)
        ttk.Button(bottom, text="Exit", command=self.on_exit).pack(side="right")

        # Prepare CSV header if needed
        self.ensure_log_header()

        # Initial one-shot update
        self.update_battery_display()

    def ensure_log_header(self):
        if not os.path.exists(LOG_FILE):
            with open(LOG_FILE, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["timestamp", "percent", "state", "seconds_left"])

    def log_once(self):
        """Capture one sample, append to CSV, update UI, reschedule if logging."""
        sample = self.read_battery()
        if sample is None:
            messagebox.showerror("Battery", "Battery information not available on this system.")
            self.stop_logging()
            return

        # Update UI
        self.apply_sample_to_ui(sample)

        # Append to CSV
        with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([sample["timestamp"], sample["percent"], sample["state"], sample["seconds_left"]])

        # Insert into table (keep it light; don’t let it grow infinitely in RAM)
        self.tree.insert("", "end", values=(
            sample["timestamp"], f'{sample["percent"]}%', sample["state"], sample["seconds_left"]
        ))
        # Auto-scroll to latest
        self.tree.yview_moveto(1.0)

        # Re-arm timer if logging continues
        if self.is_logging:
            delay_ms = max(1000, self.interval_var.get() * 1000)
            self.job_id = self.root.after(delay_ms, self.log_once)

    def read_battery(self):
        """Read battery data via psutil. Return dict or None if unavailable."""
        batt = psutil.sensors_battery()
        if batt is None:
            return None
        percent = int(round(batt.percent))
        plugged = bool(batt.power_plugged)
        state = "Charging" if plugged else "Discharging"
        # psutil.secsleft: seconds left or psutil.POWER_TIME_UNLIMITED / UNKNOWN
        if batt.secsleft in (psutil.POWER_TIME_UNLIMITED, psutil.POWER_TIME_UNKNOWN, None):
            secs_left = "-"
        else:
            secs_left = int(batt.secsleft)

        return {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "percent": percent,
            "state": state,
            "seconds_left": secs_left
        }

    def apply_sample_to_ui(self, s):
        # Progress + labels
        self.progress["value"] = s["percent"]
        self.percent_var.set(f"{s['percent']} %")
        self.state_var.set(s["state"])
        self.time_left_var.set(self.format_secs(s["seconds_left"]))

        # Status label color-ish cue using emojis (portable)
        if s["state"] == "Charging":
            txt = f"Status: Charging ({s['percent']}%)"
        else:
            txt = f"Status: Discharging ({s['percent']}%)"
        self.status_label.config(text=txt)

    @staticmethod
    def format_secs(v):
        if v == "-" or v is None:
            return "—"
        mins, sec = divmod(int(v), 60)
        hrs, mins = divmod(mins, 60)
        return f"{hrs:02d}:{mins:02d}:{sec:02d}"

    def start_logging(self):
        if self.is_logging:
            return
        # Validate interval
        try:
            interval = int(self.interval_var.get())
            if interval < 1:
                raise ValueError
        except Exception:
            messagebox.showerror("Interval", "Please enter a valid interval (>= 1 second).")
            return

        self.is_logging = True
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.status_label.config(text="Status: Starting…")
        # Immediate first sample
        self.log_once()

    def stop_logging(self):
        self.is_logging = False
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        if self.job_id:
            self.root.after_cancel(self.job_id)
            self.job_id = None
        self.status_label.config(text="Status: Stopped")

    def update_battery_display(self):
        """Refresh the top summary once when idle."""
        sample = self.read_battery()
        if sample:
            self.apply_sample_to_ui(sample)

    def clear_view(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

    def open_log(self):
        # If file doesn’t exist yet, ensure header
        self.ensure_log_header()
        # Offer to open folder / pick file (some users prefer path)
        if os.path.exists(LOG_FILE):
            # Ask where to open a copy (optional)
            if messagebox.askyesno("Open Log", "Open log file with your default CSV viewer?"):
                try:
                    # Cross-platform best-effort
                    if os.name == "nt":
                        os.startfile(LOG_FILE)  # type: ignore[attr-defined]
                    elif sys.platform == "darwin":
                        os.system(f'open "{LOG_FILE}"')
                    else:
                        os.system(f'xdg-open "{LOG_FILE}"')
                except Exception as e:
                    messagebox.showerror("Open Log", f"Could not open file.\n{e}")
            else:
                filedialog.askopenfilename(initialfile=LOG_FILE)
        else:
            messagebox.showinfo("Open Log", "No log file found yet.")

    def on_exit(self):
        self.stop_logging()
        self.root.destroy()

if __name__ == "__main__":
    # Nice default ttk theme if available
    try:
        from tkinter import ttk
        style = ttk.Style()
        if "clam" in style.theme_names():
            style.theme_use("clam")
    except Exception:
        pass

    root = tk.Tk()
    app = BatteryLoggerApp(root)
    root.mainloop()
