# Industrial SSVEP Realtime Pipeline

Software-only SSVEP pipeline for validating the realtime stack before OpenBCI hardware arrives.

## What Runs Today

- Simulated multi-channel EEG source with SSVEP fundamental and harmonic components.
- Realtime ring buffer with configurable window and step size.
- Band-pass preprocessing.
- CCA decoding across configured target frequencies.
- Decision smoothing for stable command output.
- Acquisition interface designed so OpenBCI/BrainFlow can replace the simulator without changing the realtime pipeline.

## Layout

```text
acquisition/   EEG source interface, simulator, future OpenBCI adapter
processing/    ring buffer and signal preprocessing
decoder/       CCA decoder, placeholders for FBCCA/TRCA
realtime/      realtime orchestration and decision smoothing
ui/            reserved dashboard surface
config.py      central runtime defaults
main.py        command-line entrypoint
```

## Run

```bash
python main.py --target 10 --iterations 30
```

Expected output should stabilize on `CENTER`, because `config.py` maps target frequencies `[8, 10, 12]` to labels `["LEFT", "CENTER", "RIGHT"]`.

Try the other simulated targets:

```bash
python main.py --target 8 --iterations 30
python main.py --target 12 --iterations 30
```

## Run The Speller UI

```bash
python main.py --ui
```

The UI is a full simulated SSVEP typing surface:

- 30 flickering targets: `A-Z`, `SPACE`, `DEL`, `CLR`, and `SEND`.
- Each target owns a unique low-frequency comfort stimulus from 6.0 to 11.8 Hz.
- Click a target, or use arrow keys plus Enter, to simulate gaze during hardware-free testing.
- Press Space to start or pause the realtime loop.
- Decoded commands are committed into the text output area after a short dwell gate, which avoids runaway repeated letters while testing.
- Low-confidence decisions are blocked by score and top-two margin checks before the dwell gate can advance.
- The UI uses low-contrast comfort flicker and single-shot selection: hold to type once, then re-select the same target if you want to repeat it.
- On wide screens, the stimulus grid stays centered with a maximum width so targets remain scan-friendly instead of becoming oversized.
- The side panel reports typing progress, confidence status, CPM, online accuracy, and an estimated ITR.
- When paused, stimuli stop flickering and switch to a static state so the runtime status is visually unambiguous.

## Hardware Swap Point

Implement `OpenBCIReader` in `acquisition/openbci_reader.py` with the same `EEGSource` contract:

- `start()`
- `read_chunk(samples) -> EEGChunk`
- `stop()`

The realtime pipeline only depends on that interface.
