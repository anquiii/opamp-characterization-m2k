"""
freq_sweep.py
Small-signal frequency response (Bode plot) of a TLV9062 non-inverting
amplifier (G = 11). Same circuit as dc_sweep.py.

Measures: low-frequency gain, -3 dB bandwidth, and estimated
gain-bandwidth product (GBW = G x f_3dB).

Gain and phase are computed as OUT relative to the measured IN+, so any
error in the AWG amplitude cancels out.
"""

import csv
import os

import numpy as np
import matplotlib.pyplot as plt

from m2k_bench import M2KBench, RANGE_LOW, pick_scope_rate, tone

# ---------------- test settings ----------------
VPOS, VNEG = 2.5, -2.5
GAIN_NOMINAL = 11.0
GBW_DATASHEET = 10e6                # check the TLV9062 datasheet for typ value
AWG_AMPLITUDE = 0.2                 # 0.2 V peak at W1 -> ~20 mV at IN+ -> ~0.22 V out
FREQS = np.logspace(np.log10(100), np.log10(2e6), 40)
OUT_DIR = "results"

os.makedirs(OUT_DIR, exist_ok=True)

bench = M2KBench(vpos=VPOS, vneg=VNEG, in_range=RANGE_LOW, out_range=RANGE_LOW)

rows = []
try:
    bench.power_on()
    for f in FREQS:
        f_act = bench.set_sine(f, AWG_AMPLITUDE)
        rate = pick_scope_rate(f_act)
        n = max(4000, int(np.ceil(20 * rate / f_act)))   # >= 20 cycles
        vin, vout = bench.capture(rate, n)

        a_in, p_in = tone(vin, rate, f_act)
        a_out, p_out = tone(vout, rate, f_act)

        gain_db = 20 * np.log10(a_out / a_in)
        phase = np.degrees(np.angle(np.exp(1j * (p_out - p_in))))  # wrap to +/-180
        rows.append((f_act, a_in, a_out, gain_db, phase))
        print(f"{f_act:10.1f} Hz   gain = {gain_db:6.2f} dB   phase = {phase:7.1f} deg")
finally:
    bench.close()

data = np.array(rows)
freq, gain_db, phase = data[:, 0], data[:, 3], data[:, 4]

# ---------------- analysis ----------------
g0_db = np.mean(gain_db[:3])
g0 = 10 ** (g0_db / 20)
below = np.where(gain_db < g0_db - 3)[0]

if len(below):
    i = below[0]
    # interpolate the -3 dB crossing on a log-frequency axis
    x0, x1 = np.log10(freq[i - 1]), np.log10(freq[i])
    y0, y1 = gain_db[i - 1], gain_db[i]
    f3db = 10 ** (x0 + (g0_db - 3 - y0) * (x1 - x0) / (y1 - y0))
    gbw = g0 * f3db
else:
    f3db = gbw = None

print("\n----- AC results -----")
print(f"Low-frequency gain: {g0:.3f} V/V ({g0_db:.2f} dB)")
if f3db:
    print(f"-3 dB bandwidth:    {f3db/1e3:.1f} kHz")
    print(f"Estimated GBW:      {gbw/1e6:.2f} MHz  (datasheet ~{GBW_DATASHEET/1e6:.0f} MHz)")
else:
    print("No -3 dB point found. Extend FREQS higher or raise the gain.")

# ---------------- save ----------------
with open(os.path.join(OUT_DIR, "freq_sweep.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["freq_Hz", "vin_pk_V", "vout_pk_V", "gain_dB", "phase_deg"])
    w.writerows(rows)

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(7, 7), sharex=True)
ax1.semilogx(freq, gain_db, "o-", ms=3)
ax1.axhline(g0_db - 3, ls="--", c="gray", lw=0.8)
if f3db:
    ax1.axvline(f3db, ls="--", c="gray", lw=0.8)
    ax1.set_title(f"TLV9062 Bode plot, G = 11, f-3dB = {f3db/1e3:.0f} kHz")
ax1.set_ylabel("Gain (dB)")
ax1.grid(alpha=0.3, which="both")

ax2.semilogx(freq, phase, "o-", ms=3)
ax2.set_xlabel("Frequency (Hz)")
ax2.set_ylabel("Phase (deg)")
ax2.grid(alpha=0.3, which="both")

fig.tight_layout()
fig.savefig(os.path.join(OUT_DIR, "freq_sweep.png"), dpi=150)
plt.show()
