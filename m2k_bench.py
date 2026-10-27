"""
m2k_bench.py
A small helper layer on top of libm2k for automated op-amp characterization.

Wraps the ADALM2000's power supplies, AWG (W1), and scope (1+, 2+) so the
test scripts read like a bench procedure instead of raw driver calls.

Channel mapping used by the test scripts:
    Supply V+  -> op-amp V+ (pin 8)
    Supply V-  -> op-amp V- (pin 4)
    W1         -> input divider -> op-amp IN+ (pin 3)
    Scope 1+   -> op-amp IN+ (pin 3)   (measured input)
    Scope 2+   -> op-amp OUT (pin 1)   (measured output)
    Scope 1-, 2-, GND -> circuit ground
"""

import math
import time

import numpy as np
import libm2k

# Sample rates the M2K hardware supports
AIN_RATES = [1e3, 1e4, 1e5, 1e6, 1e7, 1e8]
AOUT_RATES = [750, 7.5e3, 75e3, 750e3, 7.5e6, 75e6]

RANGE_LOW = libm2k.PLUS_MINUS_2_5V   # better resolution, clips near +/-2.5 V
RANGE_HIGH = libm2k.PLUS_MINUS_25V   # full swing, coarser resolution


class M2KBench:
    def __init__(self, uri=None, vpos=2.5, vneg=-2.5,
                 in_range=RANGE_LOW, out_range=RANGE_LOW):
        self.ctx = libm2k.m2kOpen(uri) if uri else libm2k.m2kOpen()
        if self.ctx is None:
            raise RuntimeError("No ADALM2000 found. Check USB cable and drivers.")

        # Calibrate once per session. Do this with nothing driving the inputs.
        self.ctx.calibrateADC()
        self.ctx.calibrateDAC()

        self.ain = self.ctx.getAnalogIn()
        self.aout = self.ctx.getAnalogOut()
        self.ps = self.ctx.getPowerSupply()

        self.ain.reset()
        self.aout.reset()
        self.ps.reset()

        self.ain.enableChannel(0, True)
        self.ain.enableChannel(1, True)
        self.ain.setRange(0, in_range)
        self.ain.setRange(1, out_range)
        # One kernel buffer so each capture is fresh data, not a stale buffer
        self.ain.setKernelBuffersCount(1)

        self.aout.enableChannel(0, True)
        self.aout.setCyclic(True)

        if vpos - vneg > 5.5:
            raise ValueError("TLV9062 max supply is 5.5 V total. Lower vpos/vneg.")
        self.vpos = vpos
        self.vneg = vneg

    # ---------------- power ----------------
    def power_on(self, settle=0.3):
        self.ps.enableChannel(0, True)
        self.ps.pushChannel(0, self.vpos)
        self.ps.enableChannel(1, True)
        self.ps.pushChannel(1, self.vneg)
        time.sleep(settle)

    def power_off(self):
        self.ps.pushChannel(0, 0.0)
        self.ps.pushChannel(1, 0.0)
        self.ps.enableChannel(0, False)
        self.ps.enableChannel(1, False)

    # ---------------- signal generator ----------------
    def set_dc(self, volts, settle=0.05):
        """Drive W1 with a constant voltage."""
        self.aout.setSampleRate(0, 750e3)
        self.aout.push(0, [float(volts)] * 1024)
        time.sleep(settle)

    def set_sine(self, freq, amplitude, offset=0.0, settle=0.05):
        """
        Drive W1 with a sine. Picks an AWG rate and buffer length that hold a
        whole number of cycles, so the waveform loops without a glitch.
        Returns the actual frequency produced.
        """
        # Highest AWG rate that keeps samples-per-period reasonable
        rate = AOUT_RATES[0]
        for r in AOUT_RATES:
            if r / freq <= 10000:
                rate = r
        spp = rate / freq                      # samples per period
        cycles = max(1, math.ceil(4000 / spp))  # buffer of at least ~4000 samples
        n = int(round(cycles * spp))
        f_actual = cycles * rate / n

        t = np.arange(n) / rate
        buf = offset + amplitude * np.sin(2 * np.pi * f_actual * t)

        self.aout.setSampleRate(0, rate)
        self.aout.push(0, buf.tolist())
        time.sleep(settle)
        return f_actual

    def stop_output(self):
        self.aout.stop()

    # ---------------- scope ----------------
    def capture(self, rate, n):
        """Capture n samples on both scope channels. Returns (ch1, ch2) in volts."""
        self.ain.setSampleRate(rate)
        self.ain.getSamples(n)          # throw away one buffer after any change
        data = self.ain.getSamples(n)
        return np.asarray(data[0]), np.asarray(data[1])

    def close(self):
        try:
            self.stop_output()
            self.power_off()
        finally:
            libm2k.contextClose(self.ctx)


# ---------------- analysis helpers ----------------
def pick_scope_rate(freq, min_spp=20):
    """Lowest scope rate giving at least min_spp samples per period."""
    for r in AIN_RATES:
        if r >= min_spp * freq:
            return r
    return AIN_RATES[-1]


def tone(x, rate, freq):
    """
    Amplitude (peak) and phase (rad) of the component of x at freq.
    Works like a software lock-in amplifier: multiply by a complex sinusoid
    at the known frequency and average over a whole number of cycles.
    Rejects noise and harmonics.
    """
    ncyc = int(len(x) * freq / rate)
    if ncyc < 1:
        raise ValueError("Capture is shorter than one cycle.")
    m = int(round(ncyc * rate / freq))
    x = x[:m] - np.mean(x[:m])
    t = np.arange(m) / rate
    z = 2 * np.mean(x * np.exp(-2j * np.pi * freq * t))
    return np.abs(z), np.angle(z)
