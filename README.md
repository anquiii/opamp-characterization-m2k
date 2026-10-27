# Op-amp characterization with the ADALM2000

Python scripts that use the ADALM2000 (M2K) and the libm2k library to characterize a TLV9062 op-amp automatically. The scripts power the circuit, sweep the input, capture the input and output, and report results against expected values.

## What it measures

| Script | Test | Results |
|---|---|---|
| `dc_sweep.py` | DC transfer sweep | Closed-loop gain, input offset, nonlinearity, output swing to each rail |
| `freq_sweep.py` | Small-signal frequency sweep | Bode plot, -3 dB bandwidth, gain-bandwidth product |

`m2k_bench.py` is a helper layer over libm2k. It handles calibration, the power supplies, the waveform generator, and scope capture. It also includes a lock-in style `tone()` function that pulls the amplitude and phase at the test frequency out of noisy data.

## Hardware

- ADALM2000
- TLV9062 dual op-amp on a breakout board
- Resistors: 10k and 1k (gain setting), 9.1k and 1k (input divider)
- Two 0.1 uF bypass capacitors

## Circuit

Non-inverting amplifier, gain = 1 + 10k/1k = 11.

| TLV9062 pin | Connection |
|---|---|
| 8 (V+) | M2K V+ (+2.5 V) |
| 4 (V-) | M2K V- (-2.5 V) |
| 3 (IN+ A) | Divider midpoint (W1 -> 9.1k -> pin 3 -> 1k -> GND), and scope 1+ |
| 2 (IN- A) | 10k to pin 1, 1k to GND |
| 1 (OUT A) | Scope 2+ |
| 5, 6, 7 (amp B) | Pin 7 to pin 6, pin 5 to GND |

Scope 1-, 2-, and M2K GND go to circuit ground. Each supply pin has a 0.1 uF capacitor to ground.

## Setup

```
pip install -r requirements.txt
python dc_sweep.py
python freq_sweep.py
```

Each script saves a CSV and a PNG plot to `results/`.

## Results

To be added after bench measurements.
