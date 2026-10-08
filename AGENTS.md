# Agent instructions

Read [README.md](README.md) for the build order and [CONTRIBUTING.md](CONTRIBUTING.md) for sources and validation commands. The current hardware is **XIAO ESP32-C6**, DFR0559, DS18B20 and a 30 × 70 mm perfboard. Do not substitute another XIAO pinout.

## Working rules

- Use the [Beads skill](.agents/skills/beads/SKILL.md) and run `bd prime` for workflow context. Use `bd` for all durable task tracking, and `bd remember` for project memory; do not create Markdown task lists or MEMORY.md.
- Issue state lives in `.beads/dolt/`. `bd dolt push/pull` synchronizes `refs/dolt/data`, separately from code branches. JSONL exports are passive snapshots, not the normal sync source. See the [Beads sync concepts](https://github.com/gastownhall/beads/blob/main/docs/SYNC_CONCEPTS.md).
- Preserve fitted component positions unless a requested change requires moving them. Keep CAD, STL/STEP, embedded 3MF meshes and diagrams consistent. Check physical dimensions rather than guessing from nominal product sizes.
- Top perfboard wires are insulated point-to-point; bottom bare links and shared rails have intentional intermediate connections. Numbers label the short side, letters the long side. Keep USB at the top in both views; the solder side is mirrored horizontally.
- Keep receiver architecture independent of downstream Pi/pool control. Acknowledgement follows durable storage; duplicates cannot refresh receipt time.
- Never commit `secrets.h`, receiver credentials, databases, private state or deployment logs. Test using temporary directories and dummy credentials. Do not upload firmware, restart live services or alter Tailscale as a side effect of a documentation check.
- Battery sensing has a documented unpowered-GPIO limitation. Do not imply firmware can isolate the physical divider or that voltage gives calibrated charge percentage.
- Use non-interactive file commands (`cp -f`, `mv -f`, `rm -f`, `rm -rf` as appropriate); use `ssh/scp -o BatchMode=yes` and package-manager non-interactive flags.

## Finish work

Run appropriate tests and `git diff --check`, record real follow-up work in Beads, and close completed issues. Report changes, validation and remaining limits. Default Git policy is conservative: commit, push and remote Dolt sync require user authority. An explicit user request to commit/push authorizes those actions; do not ask again. Code push does not require publishing private Beads records. If a required command fails, report its exact error.
