"""
dc_sweep.py
DC transfer characteristic of a TLV9062 non-inverting amplifier (G = 11).

Measures: closed-loop gain, input-referred offset, linearity error,
and output swing limits (how close the output gets to each rail).

Circuit (op-amp A):
    W1 --9.1k--+--> IN+ (pin 3)          10:1 divider gives finer input steps
               |
              1k
               |
              GND
    OUT (pin 1) --10k-- IN- (pin 2) --1k-- GND     gain = 1 + 10k/1k = 11
"""

import csv
import os

import numpy as np
import matplotlib.pyplot as plt

from m2k_bench import M2KBench, RANGE_LOW, RANGE_HIGH

# ---------------- test settings ----------------
VPOS, VNEG = 2.5, -2.5
GAIN_NOMINAL = 1 + 10e3 / 1e3
GAIN_TOL = 0.02                     # +/-2%, set by 1% resistors
AWG_STEPS = np.linspace(-3.0, 3.0, 61)   # ~ +/-0.3 V at IN+ after divider
SCOPE_RATE = 1e5
SCOPE_N = 10000                     # 100 ms per point, averages out 60 Hz
LINEAR_MARGIN = 0.4                 # stay this far from rails for the gain fit
OUT_DIR = "results"

os.makedirs(OUT_DIR, exist_ok=True)

# Output channel on the high range so it does not clip when the op-amp
# swings to the rails. Input channel stays on the low range for resolution.
bench = M2KBench(vpos=VPOS, vneg=VNEG, in_range=RANGE_LOW, out_range=RANGE_HIGH)

vin, vout = [], []
try:
    bench.power_on()
    for v in AWG_STEPS:
        bench.set_dc(v)
        a, b = bench.capture(SCOPE_RATE, SCOPE_N)
        vin.append(a.mean())
        vout.append(b.mean())
        print(f"W1 = {v:+.3f} V   IN+ = {vin[-1]*1e3:+8.2f} mV   OUT = {vout[-1]:+.4f} V")
finally:
    bench.close()

vin = np.array(vin)
vout = np.array(vout)

# ---------------- analysis ----------------
linear = (vout > VNEG + LINEAR_MARGIN) & (vout < VPOS - LINEAR_MARGIN)
gain, intercept = np.polyfit(vin[linear], vout[linear], 1)
vos_in = intercept / gain           # Vout = G * (Vin + Vos)
residual = vout - (gain * vin + intercept)
max_nonlin = np.max(np.abs(residual[linear]))
vout_max, vout_min = vout.max(), vout.min()

gain_ok = abs(gain - GAIN_NOMINAL) / GAIN_NOMINAL <= GAIN_TOL

print("\n----- DC results -----")
print(f"Gain:              {gain:.4f} V/V   (nominal {GAIN_NOMINAL:.1f})  {'PASS' if gain_ok else 'FAIL'}")
print(f"Input offset:      {vos_in*1e3:+.3f} mV  (includes M2K measurement error)")
print(f"Max nonlinearity:  {max_nonlin*1e3:.2f} mV in linear region")
print(f"Output high:       {vout_max:.3f} V  ({(VPOS - vout_max)*1e3:.0f} mV below V+)")
print(f"Output low:        {vout_min:.3f} V  ({(vout_min - VNEG)*1e3:.0f} mV above V-)")

# ---------------- save ----------------
with open(os.path.join(OUT_DIR, "dc_sweep.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["awg_V", "vin_V", "vout_V", "residual_V", "in_fit"])
    for row in zip(AWG_STEPS, vin, vout, residual, linear):
        w.writerow(row)

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(7, 7), sharex=True)
ax1.plot(vin * 1e3, vout, "o", ms=3, label="measured")
ax1.plot(vin * 1e3, gain * vin + intercept, "-", lw=1, label=f"fit, G = {gain:.3f}")
ax1.axhline(VPOS, ls="--", c="gray", lw=0.8)
ax1.axhline(VNEG, ls="--", c="gray", lw=0.8)
ax1.set_ylabel("Vout (V)")
ax1.set_title("TLV9062 DC transfer, G = 11")
ax1.legend()
ax1.grid(alpha=0.3)

ax2.plot(vin[linear] * 1e3, residual[linear] * 1e3, "o", ms=3)
ax2.set_xlabel("Vin (mV)")
ax2.set_ylabel("Fit residual (mV)")
ax2.grid(alpha=0.3)

fig.tight_layout()
fig.savefig(os.path.join(OUT_DIR, "dc_sweep.png"), dpi=150)
plt.show()
