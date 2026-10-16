# Validation plan

This document owns acceptance procedures. The [master decisions and roadmap](../../PROJECT_DECISIONS_AND_ROADMAP.md) owns the 1–2 week delivery timeline and architecture gates; a passing simulation is not a substitute for these measurements. Record exact hardware, software revision, settings, ambient conditions, and raw logs for every run. Agree required thresholds before testing.

## Stage 1 — bench and actual software path

Use a current-limited supply and corrected [wiring](WIRING_PINOUT.md). Confirm the selected sensors, power outputs, camera images, model execution, UART telemetry, and DONE cutoff individually. Exercise the actual sender and receiver with rejected signatures, blank/reused nonces, restarts, lost/corrupted chunks, repeated identical images, model failure, and disk failure.

Deliver more than 100 sequential alerts plus bursts. Count every submitted, accepted, rejected, stored, and displayed event. Open the saved JPEGs and compare them with actual captured scenes. Dashboard appearance alone is insufficient.

## Stage 2 — short physical fiber pilot

Use the exact proposed converters and splitter. Log negotiation and successful delivery over repeated power cycles; disconnect and reconnect the optical path. Record transmitted and recovered event counts and time to first complete verified image. Check the topology has no connected reverse path. A copper test exercises application transport only.

## Stage 3 — mission coverage and power

Test a controlled approach with independently counted person/vehicle events at the intended direction, speed, distance, and lighting. Add intended wildlife classes separately; do not infer them from car/person results. Include no-target periods, foliage motion, precipitation, and site vibration.

| Measure | Required record |
|---|---|
| Detection | Ground-truth events, triggers, misses, and false wakes/day |
| Useful images | Images in which the intended target is actually visible at required detail |
| Latency | Trigger-to-power, power-to-capture, capture-to-store; p50 and p95 |
| Energy | Battery-side standby watts and integrated Wh/event, including failed wakes and IR/heater use |
| Delivery | Sent, reconstructed, corrupted, duplicate, and missing events |
| Recovery | Sensor faults, hung Pi, link loss, restart, low battery, and full storage |

Compute endurance from measured daily energy and usable battery capacity at the intended temperature. Include collector-computer power separately. Repeated wake cycles alone do not prove months of autonomy.

## Stage 4 — environmental pilot

Start with component operating limits and a defined enclosure thermal strategy. Cold-soak before boot tests; exercise condensation, frost on the viewport, battery sag, and wet cable entries. Measure window temperature and image clarity to test de-icing. A die-temperature reading is not a window measurement.

Run an attended pilot before unattended operation. Keep an independent event counter and maintenance log so silent failures and missed events remain visible. Report results by weather and temperature, rather than a single success percentage.

## Separate track — `200 m – 20 km` Troposcatter & Optical Sky-Relay (`sky-diode-relay`)

For the ordered **`Build D` (`200 m – 20 km` All-Weather `2.4 GHz` Troposcatter, Hydrometeor & Canopy-Bounce Relay)**, complete the `35–45 minute` zero-solder coaxial assembly in [`SKY_RELAY_HARDWARE_SPEC_AND_BOM.md`](../../sky-diode-relay/hardware/SKY_RELAY_HARDWARE_SPEC_AND_BOM.md) and execute the 3-stage validation protocol in [`FIELD_TESTING_AND_CLIENT_READINESS.md`](../../sky-diode-relay/docs/FIELD_TESTING_AND_CLIENT_READINESS.md):

1. **Stage 1 (Indoor Coaxial & Over-the-Air Bench Verification):** Verify `+5.00V` output on both `TDK-Lambda LS50-5` supplies, attach `HG2414P` antennas (or `50 Ω` load) before powering the `SE2576L-EK1` `1W` PA, run `python3 -B sky-diode-relay/tests/test_sky_relay_simulation.py` (`23/23` tests passing), and verify indoor `DD\x01` + `DD\x02` JPEG reconstruction in `receiver_hub.py`.
2. **Stage 2 (`200 m – 2 km` Forest Canopy / Building Bounce):** Aim the `L-com HG2414P` `14 dBi` flat-panel antennas (`30° × 30°` beamwidth, `+2°` upward tilt) along the reciprocal compass bearing and verify `10/10` signed JPEG deliveries and automatic `2D` Costas CFO tracking.
3. **Stage 3 (`10 km – 20 km` Over-the-Hill Troposcatter & All-Weather Acceptance):** Validate `100%` frame reconstruction across clear night, daytime sun, and rain/snow conditions (`+14.1 dB` to `+29.8 dB` post-correlation SNR) and confirm 6-layer out-of-ISM guard-band (`2380 / 2488 / 2459 MHz`) anti-jamming immunity.
