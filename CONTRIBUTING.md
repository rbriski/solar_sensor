# Reproduce and maintain the project

Start at [README](README.md), then follow the build guides in order. A clone contains everything needed to inspect wiring and print models. It does not contain Wi-Fi passwords, ingest tokens, receiver history or the original deployment's network configuration.

## Starting with an AI agent

Give your agent this repository and a prompt such as:

> Read AGENTS.md and the build overview. Help me reproduce the documented XIAO ESP32-C6 sensor. Compare my actual parts and dimensions with the BOM before adapting the wiring or CAD. Work through USB probe verification, receiver setup, wireless delivery, solar power, perfboard and assembly. Keep private credentials local. Explain each physical wiring step and its meter check before asking me to apply power. My mounting site may need a different mount.

Share component model numbers, measured dimensions and clear photos when a part differs. Do not ask an agent to infer battery polarity from connector fit or treat a generic perfboard size as a mounting-hole measurement. Use the full schematic and both board views together.

The repo uses [Beads](.agents/skills/beads/SKILL.md) for durable work tracking. An agent should run `bd prime` and use `bd` rather than adding Markdown task lists. A new clone may need a local Beads database initialized with the installed CLI. Database synchronization is separate from ordinary Git branches; do not import passive JSONL exports as the normal sync workflow.

## Source map

| Change | Edit/check |
| --- | --- |
| Electrical design | [Full schematic](docs/perfboard/full-schematic.svg), [wiring guide](docs/wiring.md), firmware pin assumptions |
| Perfboard routes | [render_layout.py](docs/perfboard/render_layout.py), then regenerate SVG/JSON and run its validator |
| Firmware | `firmware/probe_test/`, `firmware/roof_sensor/`; keep the local `secrets.h` ignored |
| Receiver/data validation | `monitor/collector.py`, its tests and config example |
| Dashboard | `monitor/static/index.html`, `monitor/transport_status.js` and JS tests |
| Transport diagnosis/recovery | `monitor/transport_watchdog.py` and failure/recovery tests |
| Receiver installation | `monitor/install.py`, service templates and installer tests |
| Enclosure geometry | `hardware/enclosure/build_enclosure.py`; current STEP/STL files are in `models/` |
| Print profile/project | `prepare_bambu.py`, `package_project.py`, `validate_project.py`, `bambu/` |
| Optional mount | `hardware/mount-example/build_mount.py`; separate from enclosure geometry |

## Software and documentation checks

From the repository root:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r monitor/requirements.txt
.venv/bin/python -m unittest discover -s monitor -v
node --test monitor/test_transport_status.cjs
python3 docs/perfboard/validate_layout.py
python3 scripts/check_docs.py
git diff --check
```

Node 22 and Python 3.12 are used by CI. Receiver code needs Python 3.10+; CAD has its own environment below. Tests cover durable deduplication, authenticated HTTP ingestion, optional-broker failure, installation without overwriting credentials, public-route diagnosis and bounded recovery. They do not contact the installed sensor or change Tailscale.

After installing the [documented Arduino dependencies](docs/firmware.md), run:

```bash
bash scripts/check_firmware.sh
```

This compiles the probe test, ordinary wireless build and a battery/failure-test variant in a temporary directory using dummy credentials. It never uploads. GitHub Actions runs the software, documentation, layout and firmware checks on pushes and pull requests.

## CAD and print project

Ready-to-print files are committed, so installing CAD tools is optional. To regenerate them, use a separate Python 3.12 environment:

```bash
python3 -m venv .venv-cad
.venv-cad/bin/python -m pip install -r hardware/enclosure/requirements.txt
.venv-cad/bin/python hardware/enclosure/build_enclosure.py
.venv-cad/bin/python hardware/mount-example/build_mount.py
```

The enclosure generator checks valid solids, watertight meshes, modeled interference, gasket dimensions and fastener insertion. For changes to an already fitted component, compare new and old STEP solids before replacing the print download. Preserve the originals outside the working tree while reviewing geometry. CAD cannot prove screw grip, weather sealing or structural capacity in a physical print.

To rebuild the four-plate project with **Bambu Studio 2.8.2.61**, use its installed `resources/profiles/BBL` directory (on some installations `share/BambuStudio/profiles/BBL`). Replace `/path/to/BBL` below and put the native CLI on PATH:

```bash
.venv-cad/bin/python hardware/enclosure/prepare_bambu.py --profiles /path/to/BBL --output build/bambu
bambu-studio --load-settings "$PWD/build/bambu/machine.json;$PWD/build/bambu/process.json" --load-filaments "$PWD/build/bambu/filament.json" --load-assemble-list "$PWD/build/bambu/plates.json" --arrange 0 --orient 0 --slice 0 --export-3mf solar-enclosure-X2D.3mf --outputdir "$PWD/build/bambu"
.venv-cad/bin/python hardware/enclosure/render_enclosure.py --manifest build/bambu/plates.json
.venv-cad/bin/python hardware/enclosure/package_project.py --staging build/bambu
bambu-studio --slice 0 --export-3mf reopened.3mf --outputdir "$PWD/build/bambu/roundtrip" "$PWD/hardware/enclosure/bambu/solar-enclosure-X2D.3mf"
.venv-cad/bin/python hardware/enclosure/validate_project.py --roundtrip build/bambu/roundtrip/reopened.3mf
```

`--slicer-output` on the preparation script can map the staging directory into a container. Generated manifests contain paths for that run; regenerate them for your machine. The profile provenance points to [Bambu's versioned profiles](https://github.com/bambulab/BambuStudio/tree/v02.08.02.61/resources/profiles/BBL). Stock machine G-code is retained, including reserved tool identifiers that produce CLI diagnostics; the checks verify successful slicing, no plate warnings and the saved temperature limits. An offscreen thumbnail failure can be handled by the supplied CAD-preview packaging step, provided actual slicing succeeded.

After a geometry change, update the STEP/STL exports, diagrams, 3MF and validation together. Do not leave a corrected standalone STL beside a full project that still embeds the old part. Verify all mesh copies in the 3MF and reopen/reslice the saved file before calling it ready to print.

## Publishing changes

Review staged files for private headers, JSON config, database files, logs and machine-specific paths. Keep third-party OneWire notices and profile provenance. No project-wide license has been selected; do not invent one during cleanup. Commit/push when the user authorizes it, report the checks performed, and distinguish computed fit from physical testing.
