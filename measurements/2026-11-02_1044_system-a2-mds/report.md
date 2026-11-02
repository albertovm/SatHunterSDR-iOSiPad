# Lab measurement 2026-11-02 10:44:28

Generator: vsg60, 436.600000 MHz, attenuation 33.6 dB. Chain: VSG60A, 30 dB attenuator, 1.5 m cable (3.6 dB), Spacewalker LNA 434 MHz v1.4 (bias tee), RTL-SDR Blog V3, Xiaomi Mi 10. Levels at the LNA input (attenuator nominal 30 dB).

Phone: {'source': 'rtl', 'source_status': 'tuner r820t, 1.024 MS/s, gain 12.5 dB, bias tee ON', 'rate': 1024000.0, 'gain': 12.5, 'ppm': 0.0, 'bias_tee': True, 'decimation': 8, 'bins': 4096}

Noise floor: -75.7 dBFS per 31 Hz bin

Frequency: offset +150.8 Hz (+0.35 ppm) at 44.5 dB SNR

## Gain sweep and system noise figure

AWGN 80 kHz wide at -165, -158 dBm/Hz at the receiver input (file peak-to-average 9.94 dB), measured in the middle 60 kHz. NF = PSD + 174 - rise, rise = AWGN / receiver noise in the channel. CW at -110 dBm for C/N0.

| Gain dB | NF dB | NF spread dB | Noise off dBFS/bin | CW C/N0 dB-Hz | CW peak dBFS |
|---|---|---|---|---|---|
| 12.5 | 2.21 | 0.15 | -69.0 | 62.0 | -31.0 |

Chosen gain for the level sweep: 12.5 dB (lowest gain within 0.3 dB of the best NF).

## Level sweep

| Level dBm | Passes | Peak dBFS | SNR dB | SNR spread dB | C/N0 dB-Hz | Offset Hz |
|---|---|---|---|---|---|---|
| -110.0 | 2 | -31.1 | 44.5 | 0.0 | 62.5 | +149.9 |
| -120.0 | 2 | -41.1 | 34.6 | 0.0 | 52.5 | +149.2 |
| -125.0 | 2 | -46.1 | 29.6 | 0.0 | 47.5 | +149.3 |
| -130.0 | 2 | -51.0 | 24.7 | 0.0 | 42.6 | +149.1 |
| -135.0 | 2 | -56.1 | 19.6 | 0.1 | 37.5 | +150.4 |
| -138.0 | 2 | -59.0 | 16.6 | 0.3 | 34.6 | +149.6 |
| -141.0 | 2 | -62.1 | 13.6 | 0.2 | 31.6 | +148.5 |
| -144.0 | 2 | -64.9 | 10.8 | 0.1 | 28.7 | +150.1 |
| -147.0 | 2 | -67.5 | 8.2 | 0.1 | 26.1 | +147.5 |
| -150.0 | 2 | -69.9 | 5.7 | 0.4 | 23.7 | +148.6 |
| -153.0 | 2 | -72.4 | 3.3 | 1.4 | 21.3 | +148.6 |

Sensitivity (SNR 3 dB in a 31 Hz bin): not reached in the sweep

Levels are at the receiver input (generator level minus --atten); the VSG60's absolute level is ±2 dB.

| CW level dBm | Decoded | OK | WPM |
|---|---|---|---|
| -130.0 | `AVV DE HG0LAB TEST VVV DE HG0LAB TEST VVV` | yes | 15.4 |
| -135.0 | `EVV DE HG0LAB TEST VVV DE HG0LAB TEST VVV` | yes | 15.1 |
| -138.0 | `AVV DE HG0LAB TEST VVV DE HG0LAB TEST VVV` | yes | 15.3 |
| -141.0 | `TVV DE HG0LAB TEST VVV DE HG0LAB TEST VVV` | yes | 15.2 |
| -144.0 | `TVV DE HG0LAB TEST VVV DE HG~LAB TEST V4V` | no | 15.1 |
| -147.0 | `A4~ 6 HM ~LABEAEHNE EII5V DE HZ~LA~ REST V~IA` | no | 16.4 |
| -150.0 | `` | no | 0.0 |
