# Third-party notices

The root [MIT License](LICENSE) applies to this project's original code, documentation and CAD designs. It does not replace licenses or copyright notices attached to third-party material.

## OneWire

[`firmware/libraries/OneWire`](firmware/libraries/OneWire) is vendored from [Paul Stoffregen's OneWire repository](https://github.com/PaulStoffregen/OneWire/tree/800f26f3ee6eb446a72e013785cac3700e54cc13). Its source retains the upstream permission notices and attribution to Jim Studt, Dallas Semiconductor and other contributors. See [OneWire.cpp](firmware/libraries/OneWire/OneWire.cpp) and the [provenance record](firmware/libraries/OneWire/UPSTREAM.txt). Preserve these notices when redistributing the library.

## Bambu Studio profiles

The machine, process and filament JSON files in [`hardware/enclosure/bambu`](hardware/enclosure/bambu), and the upstream settings and machine G-code embedded in the enclosure and optional saddle 3MF projects, derive from [Bambu Studio v02.08.02.61 profiles](https://github.com/bambulab/BambuStudio/tree/v02.08.02.61/resources/profiles/BBL). Bambu Studio's [upstream license](https://github.com/bambulab/BambuStudio/blob/v02.08.02.61/LICENSE) is GNU AGPL version 3; an unchanged copy is included at [LICENSES/BambuStudio-AGPL-3.0.txt](LICENSES/BambuStudio-AGPL-3.0.txt). Those upstream portions are not relicensed under MIT.

Project-specific profile changes select the X2D, white PETG temperatures, speeds, walls, infill, brim and plate arrangement. The readable JSON files, [profile preparation script](hardware/enclosure/prepare_bambu.py) and [profile provenance](hardware/enclosure/bambu/profile-status.json) document those changes. The project's original CAD models and mesh geometry remain under MIT.

## Beads integration

The bundled Beads skill and generated integration hooks come from [Beads](https://github.com/gastownhall/beads). Its [upstream MIT license](https://github.com/gastownhall/beads/blob/main/LICENSE), copyright © 2025 Beads Contributors, is preserved at [LICENSES/Beads-MIT.txt](LICENSES/Beads-MIT.txt).

## Separately installed dependencies

Arduino/ESP32 libraries, Python packages and build tools installed by the setup instructions retain their respective licenses. The project license does not relicense those dependencies.
