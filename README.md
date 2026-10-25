# HADES

Real-time consumer-drone detection and alerting pipeline: video source → detection → tracking → decision → alert outputs, with run logging and replay.

## Run

```bash
pip install -e ".[dev]"      # add ",train" for the ml/ tools
hades-run --config configs/default.yaml
hades-replay --config configs/default.yaml --clip data/demo/<clip>.mp4
```

Git LFS holds dataset images, demo clips and model weights. Downloads are skipped by default
(`GIT_LFS_SKIP_SMUDGE=1`); pull them only if you work on data, training or analysis (C, G, H).

## Where to look

| Path | Contents |
|---|---|
| `src/hades/` | everything that runs on the device; `contracts.py` is the single source of packet and interface types |
| `ml/` | dataset, training, analysis, export (not deployed) |
| `bench/` | benchmark and stability runs |
| `docs/spec.md` | packet specification (kept in step with `contracts.py`) |
| `docs/decisions.md` | decision log |
| `CONTRIBUTING.md` | development discipline |
