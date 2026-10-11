#!/usr/bin/env python3
"""
NanoVNA LoRa & ISM Antenna Testing Tool
Automated RF resonance, S11 Return Loss, VSWR, and Impedance measurement
using a connected NanoVNA.
"""

import sys
import os
import time
import math
import argparse
import glob
from typing import List, Tuple, Optional, Dict

try:
    import serial
except ImportError:
    serial = None

# Standard LoRa and ISM Band Presets
BANDS = {
    "US915": {
        "name": "US 915 MHz LoRa / ISM (902 - 928 MHz)",
        "start": 902_000_000,
        "stop": 928_000_000,
        "center": 915_000_000,
        "points": 101,
    },
    "US915-WIDE": {
        "name": "US 915 MHz Wide View (890 - 940 MHz)",
        "start": 890_000_000,
        "stop": 940_000_000,
        "center": 915_000_000,
        "points": 101,
    },
    "EU868": {
        "name": "EU 868 MHz LoRa / ISM (863 - 870 MHz)",
        "start": 863_000_000,
        "stop": 870_000_000,
        "center": 868_000_000,
        "points": 101,
    },
    "AS923": {
        "name": "Asia 923 MHz LoRa (920 - 925 MHz)",
        "start": 920_000_000,
        "stop": 925_000_000,
        "center": 923_000_000,
        "points": 101,
    },
    "EU433": {
        "name": "433 MHz LoRa / ISM (433 - 435 MHz)",
        "start": 433_000_000,
        "stop": 435_000_000,
        "center": 433_920_000,
        "points": 101,
    },
}

def find_nanovna_port() -> Optional[str]:
    """Auto-detect connected NanoVNA serial port."""
    candidates = []
    if sys.platform.startswith("linux"):
        candidates.extend(glob.glob("/dev/ttyACM*"))
        candidates.extend(glob.glob("/dev/ttyUSB*"))
    elif sys.platform == "darwin":
        candidates.extend(glob.glob("/dev/cu.usbmodem*"))
        candidates.extend(glob.glob("/dev/cu.usbserial*"))
    elif sys.platform.startswith("win"):
        candidates.extend([f"COM{i}" for i in range(1, 32)])

    for port in candidates:
        if os.path.exists(port):
            return port
    return None

class NanoVNA:
    def __init__(self, port: str):
        self.port = port
        self.fd = -1
        self._connect()

    def _connect(self):
        # Open non-blocking to prevent carrier hangs on Linux CDC ACM
        self.fd = os.open(self.port, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
        # Flush any leftover input
        self._flush()

    def _flush(self):
        while True:
            try:
                b = os.read(self.fd, 8192)
                if not b: break
                time.sleep(0.01)
            except BlockingIOError:
                break

    def query(self, cmd: str, wait_sec: float = 0.4) -> str:
        self._flush()
        os.write(self.fd, (cmd + "\r\n").encode("latin1"))
        time.sleep(wait_sec)
        res = b""
        start_t = time.time()
        while time.time() - start_t < (wait_sec + 1.5):
            try:
                chunk = os.read(self.fd, 4096)
                if chunk:
                    res += chunk
                    time.sleep(0.02)
                else:
                    break
            except BlockingIOError:
                if res and (time.time() - start_t > wait_sec):
                    break
                time.sleep(0.02)
        return res.decode("latin1", errors="replace")

    def sweep(self, start_hz: int, stop_hz: int, points: int = 101) -> Tuple[List[int], List[Tuple[float, float]]]:
        """Configure sweep and retrieve S11 data points."""
        self.query(f"sweep {start_hz} {stop_hz} {points}", wait_sec=0.2)
        time.sleep(0.1)

        f_raw = self.query("frequencies", wait_sec=0.3)
        d_raw = self.query("data 0", wait_sec=0.5)

        freqs = [int(l.strip()) for l in f_raw.split("\n") if l.strip().isdigit()]
        pts = []
        for l in d_raw.split("\n"):
            parts = l.strip().split()
            if len(parts) == 2:
                try:
                    pts.append((float(parts[0]), float(parts[1])))
                except ValueError:
                    pass

        return freqs, pts

    def close(self):
        if self.fd >= 0:
            os.close(self.fd)
            self.fd = -1

def calculate_rf_metrics(freqs: List[int], pts: List[Tuple[float, float]]) -> List[Dict]:
    """Calculate Return Loss, VSWR, Impedance, and Radiated Power %."""
    results = []
    for f, (re, im) in zip(freqs, pts):
        gamma = math.sqrt(re * re + im * im)
        s11_db = 20.0 * math.log10(max(gamma, 1e-6))
        
        if gamma < 0.999:
            vswr = (1.0 + gamma) / max(1.0 - gamma, 1e-6)
        else:
            vswr = 99.0

        # Percentage of power transmitted (radiated) vs reflected
        p_refl_pct = (gamma ** 2) * 100.0
        p_rad_pct = max(0.0, 100.0 - p_refl_pct)

        # Complex Impedance Z = 50 * (1 + Gamma) / (1 - Gamma)
        denom = (1.0 - re) ** 2 + (im ** 2)
        if denom > 1e-6:
            z_r = 50.0 * (1.0 - re ** 2 - im ** 2) / denom
            z_x = 50.0 * (2.0 * im) / denom
        else:
            z_r, z_x = 0.0, 0.0

        results.append({
            "freq": f,
            "s11_db": s11_db,
            "vswr": vswr,
            "z_r": z_r,
            "z_x": z_x,
            "gamma": gamma,
            "rad_pct": p_rad_pct,
        })
    return results

def get_vswr_rating(vswr: float) -> Tuple[str, str]:
    """Returns (status_label, ansi_color_code)."""
    if vswr <= 1.5:
        return "EXCELLENT", "\033[92m" # Green
    elif vswr <= 2.0:
        return "GOOD", "\033[96m"      # Cyan
    elif vswr <= 3.0:
        return "MARGINAL", "\033[93m"  # Yellow
    else:
        return "POOR", "\033[91m"      # Red

def render_ascii_graph(results: List[Dict], width: int = 50):
    """Render an ASCII VSWR plot in the terminal."""
    if not results: return
    vswrs = [r["vswr"] for r in results]
    min_v = max(1.0, min(vswrs))
    max_v = min(5.0, max(vswrs))
    if max_v <= min_v: max_v = min_v + 1.0

    print("\n  VSWR Curve (Lower is Better):")
    print("  " + "-" * (width + 10))
    # Sample down to width points
    step = len(results) / width
    for i in range(width):
        idx = min(int(i * step), len(results) - 1)
        v = results[idx]["vswr"]
        f_mhz = results[idx]["freq"] / 1e6
        norm = int(((v - min_v) / (max_v - min_v)) * 20)
        norm = max(1, min(20, norm))
        bar = "#" * norm
        color = "\033[92m" if v <= 1.5 else ("\033[93m" if v <= 2.0 else "\033[91m")
        if i % 5 == 0 or i == width - 1:
            print(f"  {f_mhz:6.1f} MHz | {color}{bar:<20}\033[0m {v:.2f}:1")
    print("  " + "-" * (width + 10))

def plot_graph(results: List[Dict], target_freq: int, filename: str):
    """Plot Return Loss and VSWR to a PNG image file using matplotlib."""
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("[!] matplotlib not installed. Install with `pip install matplotlib` to generate PNG plots.")
        return

    freqs_mhz = [r["freq"] / 1e6 for r in results]
    vswrs = [r["vswr"] for r in results]
    s11s = [r["s11_db"] for r in results]

    fig, ax1 = plt.subplots(figsize=(10, 6))

    color = "tab:blue"
    ax1.set_xlabel("Frequency (MHz)", fontsize=12)
    ax1.set_ylabel("VSWR (:1)", color=color, fontsize=12)
    line1 = ax1.plot(freqs_mhz, vswrs, color=color, linewidth=2, label="VSWR")
    ax1.axhline(1.5, color="green", linestyle="--", alpha=0.6, label="VSWR 1.5:1 (Ideal)")
    ax1.axhline(2.0, color="orange", linestyle="--", alpha=0.6, label="VSWR 2.0:1 (Max Good)")
    ax1.tick_params(axis="y", labelcolor=color)
    ax1.set_ylim(1.0, min(max(vswrs) + 0.5, 6.0))

    ax2 = ax1.twinx()
    color = "tab:red"
    ax2.set_ylabel("Return Loss S11 (dB)", color=color, fontsize=12)
    line2 = ax2.plot(freqs_mhz, s11s, color=color, linewidth=2, linestyle="-.", label="S11 (dB)")
    ax2.tick_params(axis="y", labelcolor=color)

    # Highlight target frequency
    target_mhz = target_freq / 1e6
    ax1.axvline(target_mhz, color="black", linestyle=":", linewidth=1.5, label=f"Center ({target_mhz:.1f} MHz)")

    plt.title(f"NanoVNA LoRa Antenna Sweep ({min(freqs_mhz):.1f} - {max(freqs_mhz):.1f} MHz)", fontsize=14, fontweight="bold")
    fig.tight_layout()
    plt.grid(True, alpha=0.3)
    plt.savefig(filename, dpi=150)
    print(f"\n[+] Saved measurement graph to: {filename}")

def run_test(args):
    port = args.port or find_nanovna_port()
    if not port:
        print("[!] No NanoVNA detected. Please check USB connection.")
        sys.exit(1)

    # Resolve band parameters
    if args.band in BANDS:
        cfg = BANDS[args.band]
        start_hz = cfg["start"]
        stop_hz = cfg["stop"]
        center_hz = cfg["center"]
        points = cfg["points"]
        band_name = cfg["name"]
    else:
        start_hz = args.start
        stop_hz = args.stop
        center_hz = (start_hz + stop_hz) // 2
        points = args.points
        band_name = f"Custom ({start_hz/1e6:.1f} - {stop_hz/1e6:.1f} MHz)"

    vna = NanoVNA(port)

    try:
        freqs, pts = vna.sweep(start_hz, stop_hz, points)
        if not freqs or not pts or len(freqs) != len(pts):
            print("[!] Failed to acquire sweep data from NanoVNA. Please re-run.")
            return

        results = calculate_rf_metrics(freqs, pts)
        
        # Closest point to target center
        p_center = min(results, key=lambda x: abs(x["freq"] - center_hz))
        # Best match in the entire band
        p_best = min(results, key=lambda x: x["vswr"])

        center_rating, center_color = get_vswr_rating(p_center["vswr"])
        best_rating, best_color = get_vswr_rating(p_best["vswr"])

        RESET = "\033[0m"
        BOLD = "\033[1m"

        print(f"\n{BOLD}======================================================================{RESET}")
        print(f"{BOLD}  NanoVNA LoRa / ISM Antenna Verification Report{RESET}")
        print(f"  Target Band: {BOLD}{band_name}{RESET}")
        print(f"  Serial Port: {port}")
        print(f"{BOLD}======================================================================{RESET}\n")

        print(f"  {BOLD}TARGET FREQUENCY ({center_hz / 1e6:.3f} MHz):{RESET}")
        print(f"    VSWR:              {center_color}{BOLD}{p_center['vswr']:.2f} : 1{RESET} [{center_color}{center_rating}{RESET}]")
        print(f"    Return Loss (S11): {p_center['s11_db']:.2f} dB")
        sign = "+" if p_center["z_x"] >= 0 else "-"
        print(f"    Impedance (Z):     {p_center['z_r']:.1f} {sign} {abs(p_center['z_x']):.1f}j ohms (Ideal: 50.0 ohms)")
        print(f"    Radiated Power:    {p_center['rad_pct']:.1f}% transmitted ({100.0 - p_center['rad_pct']:.1f}% reflected)")

        print(f"\n  {BOLD}BEST RESONANCE IN BAND:{RESET}")
        print(f"    Frequency:         {BOLD}{p_best['freq'] / 1e6:.3f} MHz{RESET}")
        print(f"    Minimum VSWR:      {best_color}{BOLD}{p_best['vswr']:.2f} : 1{RESET} [{best_color}{best_rating}{RESET}]")
        print(f"    Return Loss:       {p_best['s11_db']:.2f} dB")

        print(f"\n{BOLD}----------------------------------------------------------------------{RESET}")
        print(f"  {BOLD}Frequency (MHz)   Return Loss      VSWR         Power Transmitted{RESET}")
        print(f"{BOLD}----------------------------------------------------------------------{RESET}")
        step = max(1, len(results) // 10)
        for r in results[::step]:
            _, col = get_vswr_rating(r["vswr"])
            print(f"   {r['freq']/1e6:8.2f} MHz      {r['s11_db']:7.2f} dB     {col}{r['vswr']:5.2f}:1{RESET}            {r['rad_pct']:5.1f}%")
        print(f"{BOLD}----------------------------------------------------------------------{RESET}")

        render_ascii_graph(results)

        if args.plot:
            plot_filename = args.plot if isinstance(args.plot, str) and args.plot != "True" else "antenna_sweep.png"
            plot_graph(results, center_hz, plot_filename)

        if args.csv:
            with open(args.csv, "w") as f:
                f.write("Frequency_Hz,ReturnLoss_dB,VSWR,Real_Z,Imag_Z,Radiated_Percent\n")
                for r in results:
                    f.write(f"{r['freq']},{r['s11_db']:.3f},{r['vswr']:.3f},{r['z_r']:.2f},{r['z_x']:.2f},{r['rad_pct']:.1f}\n")
            print(f"[+] Exported CSV data to: {args.csv}")

        # Final verdict output
        if p_center['vswr'] <= 2.0:
            print(f"\n{center_color}{BOLD}VERDICT: [PASSED] Antenna is properly tuned and safe for LoRa transmission!{RESET}\n")
        else:
            print(f"\n{center_color}{BOLD}VERDICT: [NEEDS TUNING] High VSWR at target frequency. Check cable/ground plane.{RESET}\n")

    finally:
        vna.close()

def main():
    parser = argparse.ArgumentParser(description="NanoVNA LoRa Antenna Tester & Analyzer")
    parser.add_argument("--band", choices=list(BANDS.keys()), default="US915", help="Preset LoRa/ISM band (default: US915)")
    parser.add_argument("--port", help="Serial port of NanoVNA (auto-detected if omitted)")
    parser.add_argument("--start", type=int, default=900_000_000, help="Custom start frequency in Hz")
    parser.add_argument("--stop", type=int, default=930_000_000, help="Custom stop frequency in Hz")
    parser.add_argument("--points", type=int, default=101, help="Number of sweep points (default: 101)")
    parser.add_argument("--plot", nargs="?", const="antenna_sweep.png", help="Generate PNG plot of VSWR & Return Loss (e.g. --plot [filename.png])")
    parser.add_argument("--csv", help="Save measurement data to CSV file")
    parser.add_argument("--live", action="store_true", help="Continuously monitor and update VSWR for real-time antenna trimming")
    args = parser.parse_args()

    if args.live:
        print("[*] Entering live tuning mode. Press Ctrl+C to stop.")
        try:
            while True:
                run_test(args)
                time.sleep(1.0)
        except KeyboardInterrupt:
            print("\n[*] Exited live monitoring.")
    else:
        run_test(args)

if __name__ == "__main__":
    main()
