# NanoVNA LoRa & ISM Antenna Tester

An automated, lightweight command-line tool for testing, tuning, and verifying LoRa, Meshtastic, Helium, and ISM antennas using a connected **NanoVNA** (NanoVNA-H, NanoVNA-H4, NanoVNA V2, etc.).

---

## Features

- **Automated NanoVNA Detection**: Automatically discovers your NanoVNA on USB serial (`/dev/ttyACM*`, `/dev/ttyUSB*`, `COM*`).
- **Standard LoRa Band Presets**:
  - `US915`: **902 – 928 MHz** (Center: 915.0 MHz) — United States & Americas
  - `US915-WIDE`: **890 – 940 MHz** (Wide view around 915 MHz)
  - `EU868`: **863 – 870 MHz** (Center: 868.0 MHz) — Europe
  - `AS923`: **920 – 925 MHz** (Center: 923.0 MHz) — Asia & Australia
  - `EU433`: **433 – 435 MHz** (Center: 433.92 MHz) — 433 MHz ISM band
- **Full RF Analysis**:
  - **VSWR** (Voltage Standing Wave Ratio)
  - **S11 Return Loss** (in dB)
  - **Complex Impedance** ($Z = R + jX$ in $\Omega$, compared to ideal $50\ \Omega$)
  - **Radiated Power Percentage** (e.g. 95% transmitted vs. 5% reflected)
  - **Automatic Pass / Fail Verdict**
- **ASCII Graph & Terminal Curves**: Displays visual VSWR curves directly in the terminal with colored status indicators.
- **Graphical PNG Plot Generation**: Generates high-resolution dual-axis plots (VSWR and Return Loss) via `--plot`.
- **CSV Data Export**: Export frequency and reflection data for logging with `--csv antenna_data.csv`.
- **Live Tuning Mode (`--live`)**: Continuously sweeps and updates metrics every second so you can adjust and trim elements in real time.

---

## Installation

### 1. Clone the Repository
```bash
git clone https://github.com/sircharlesxx/nanovna-lora-test.git
cd nanovna-lora-test
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

---

## Usage

### Quick Test (Default US 915 MHz Band)
Connect your antenna to **Channel 0 (CH0 / TX)** of the NanoVNA and run:
```bash
python3 nanovna_lora_test.py
```

### Test European 868 MHz Band
```bash
python3 nanovna_lora_test.py --band EU868
```

### Test Asian 923 MHz Band
```bash
python3 nanovna_lora_test.py --band AS923
```

### Generate High-Resolution PNG Graph
```bash
python3 nanovna_lora_test.py --band US915 --plot antenna_915_sweep.png
```

### Live Antenna Tuning Mode
If you are adjusting an antenna (e.g. trimming a dipole or adjusting ground radials), use live mode to see real-time updates:
```bash
python3 nanovna_lora_test.py --band US915 --live
```

### Export Measurements to CSV
```bash
python3 nanovna_lora_test.py --band US915 --csv test_results.csv
```

---

## Interpreting Antenna Metrics

| VSWR | Return Loss (S11) | Radiated Power | Quality Rating | Practical Meaning |
| :--- | :--- | :--- | :--- | :--- |
| **< 1.5 : 1** | **< -14.0 dB** | **> 96%** | **EXCELLENT** | Ideal match. Maximum transmission range. |
| **< 2.0 : 1** | **< -9.5 dB** | **> 90%** | **GOOD** | Completely safe and effective for LoRa / radios. |
| **2.0 - 3.0 : 1** | **-9.5 to -6.0 dB** | **75% - 90%** | **MARGINAL** | Noticeable signal loss; consider retuning. |
| **> 3.0 : 1** | **> -6.0 dB** | **< 75%** | **POOR** | Significant power reflection; transmitter may overheat. |

---

## Hardware Connection Diagram

```text
               +--------------------------------+
               |           NanoVNA-H            |
               |                                |
  [Antenna] -> | [CH0 / TX]         [CH1 / RX]  | <- [50 Ohm Cap / Open]
               +--------------------------------+
                               |
                        [USB-C Cable]
                               |
                               v
                       [Computer / Laptop]
```

> **Note:** For antenna testing, always connect the antenna under test to **Channel 0 (CH0 / TX)**. Channel 1 (RX) should remain open or capped.

---

## License

MIT License. See [LICENSE](LICENSE) for details.
