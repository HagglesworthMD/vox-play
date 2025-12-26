# Dual Cursor Prototype (MVP)

## Goals

* Read raw input events from `/dev/input/event*`.
* Maintain **two independent cursor states** (Left + Right).
* Print cursor state updates (~20 Hz).
* No uinput, no X11, no overlay yet.

## Build & Run

```bash
cd dualmouse-deck
cargo build
RUST_LOG=info cargo run
```

### List candidate devices

```bash
cargo run -- --list-devices
```

### Run with explicit device sources

```bash
DUALMOUSE_SOURCES=/dev/input/event5,/dev/input/event6 RUST_LOG=debug cargo run
```

### Tune ABS motion scaling

```bash
DUALMOUSE_ABS_SCALE=0.02 RUST_LOG=debug cargo run
```

## Debugging Commands

```bash
libinput list-devices
sudo libinput debug-events --device /dev/input/eventX
sudo libinput debug-events --device /dev/input/eventY

evtest /dev/input/eventX
```

## Troubleshooting

* **No devices found:** check udev permissions or try `DUALMOUSE_SOURCES` with explicit event paths.
* **No motion on trackpads:** the device may report ABS events; use `RUST_LOG=debug` to confirm and adjust `DUALMOUSE_ABS_SCALE`.

## Notes

* If only one device shows up, mapping is handled in `src/evdev/decode.rs` via
  `SingleDeviceMapping`. You can extend it with real event patterns from the Deck.
* If no devices are detected, check udev permissions and Steam Input configuration.
