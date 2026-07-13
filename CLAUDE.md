# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

Aqua Scope (Trạm Quan Trắc & Đếm Hạt/Rác Thải Vĩ Mô Trong Dòng Chảy) is a hardware design project that turns the camera of a mini-microscope (XIAO ESP32-S3 Sense) into a fully automated station that images a **flowing open water stream from above** to **detect, count, and size** plastic/macro debris particles (design range 1mm–5mm; **current test scope is <2mm** — see the pump note below), using **backlit silhouette imaging + a hybrid on-device vision pipeline (classical CV for count/size + a small classifier for per-particle type)**.

**Honest scope:** the baseline counts and sizes particles by silhouette, and adds an **appearance-based** on-device classifier for per-particle type (e.g. plastic vs bubble vs organic vs fiber — class list not yet fixed). It does **not** chemically distinguish "plastic vs non-plastic"; the classifier reasons from shape/appearance only, not chemistry. Fluorescent (Nile Red) plastic-specific detection is noted as a **future extension only** (a possible extra feature for the classifier), not part of the baseline. Do not reintroduce claims that UV makes plastics glow — that was an earlier, physically wrong idea (most PE/PP/PET/PS do not autofluoresce; organic matter does).

**Application context (use case):** quality control of **intake water for a food-processing plant** — the station checks source water for macro debris **before** it enters the production line. This context implies: samples are **stable** (clean-ish supply water, not highly variable wastewater) → a fixed threshold on an even backlit field is adequate; samples are taken **periodically/per-batch** (not continuous 24/7 monitoring) → the Stop-Flow cycle fits naturally; and there is a hard **traceability requirement** → every measurement must be logged with a sample ID / timestamp / count / size distribution for later audit (this is a real functional requirement, not just "count and done"). Positioning stays a **demo/lab rig** illustrating the QC workflow — it is not a certified food-safety instrument.

This is **not a software codebase in its current state** — there is no buildable/lintable/testable code checked in yet. The repository currently contains:
- `README.md` — primary architecture doc (Vietnamese), describes the current "Backlit Silhouette" baseline (short imaging tube + white backlight from below + classical CV)
- `info.txt` — detailed Vietnamese technical report of the mechanical structure and operating cycle
- `technical_specs.md` — dimensional data extracted from the reference STL geometry (bounding boxes, hole diameters/positions, etc.)
- `implementation_plan.md` — a plan for building a full OpenSCAD parametric model of the system (file list, constants table, phased task breakdown)
- `base/` — reference STL files from the Matchboxscope project (repurposed as the removable top cap / camera mount)
- `perestaltic pump/` — reference STL files from the Planktoscope Mini peristaltic pump. **Reference only — this peristaltic design is REJECTED** (28BYJ-48 is far too slow: ~vài mL/min). The baseline pump is now an **active RS365 12V diaphragm pump** (see the Flow note below).
- `pone.0244103.pdf` — reference paper on closed-microfluidic flow-cell imaging that the design deliberately diverges from

**The `openscad/` model EXISTS (built 2026-07-07):** `constants.scad` (all constants + assembly asserts + vertical layout), `components/*.scad` (11 parts; latest version wins — e.g. `top_cap_002` supersedes `_001`, plugging the 3 legacy Ø8 holes while re-drilling the two overlapping M3 passages), `aqua_scope_assembly_001.scad` (flags `explode`/`show_pump`/`show_electronics`/`show_window`/`cam_variant`), and `print/*.scad → *.stl` (7 printable parts, manifold-checked). An optional **ESP32-CAM variant** (`top_cap_esp32cam_001` + `esp32cam_001` mock, `cam_variant=1`) swaps in for the XIAO base via the same 4×M3 30×30 flange interface, reusing the printed Matchboxscope **lid** STL as the clamp cover; baseline XIAO stays untouched. Key architecture decisions from the build (documented in `plan.md` §2 & §8): **bottom-loading assembly** (one-piece housing → tray/window/retainer/diffuser/LED-shelf all insert from below; barbs pass through 2 vertical wall slots ±X with light-blocking plugs), acrylic window Ø42 with **snap-fit retainer** (an M2.5 screw ring is geometrically impossible at tray OD44), and a **"LED xuôi"** light box (upward-facing keychain LED module + ~8mm mixing chamber + stacked diffusers — the bounce/baffle idea is superseded). `plan.md` is the build contract; consult it before modifying the model.

## OpenSCAD modeling skills

`.claude/skills/` has three project-local skills (from [iancanderson/openscad-agent](https://github.com/iancanderson/openscad-agent)) for the iterate-and-print workflow:
- `/openscad` — create a new versioned `.scad` file (`<name>_001.scad`, `_002`, ...) via `.claude/skills/openscad/scripts/version-scad.sh <name>` to get the next version number, then render+compare against the previous version.
- `/preview-scad` — render any `.scad` to PNG via `.claude/skills/preview-scad/scripts/render-scad.sh <file.scad>` for visual inspection (read the resulting PNG to check the design).
- `/export-stl` — convert a finalized `.scad` to `.stl` via `.claude/skills/export-stl/scripts/export-stl.sh <file.scad>`, with non-manifold/self-intersection/degenerate-face checks.

OpenSCAD itself is installed at `C:\Program Files\OpenSCAD\openscad.exe` on this machine but is **not on PATH** — both scripts were patched (relative to the upstream repo, which only checks the macOS app bundle path or PATH) to also fall back to that Windows install location. If OpenSCAD gets reinstalled/moved, check that fallback path in `render-scad.sh` and `export-stl.sh` still resolves.

## Working in this repo

- All primary documentation (`README.md`, `info.txt`, `implementation_plan.md`) is written in Vietnamese. Match that language when editing these docs unless told otherwise.
- `technical_specs.md` values (bounding boxes, hole positions/diameters, PCDs) are derived directly from the STL files in `base/` and `perestaltic pump/` — treat it as the source of truth for those parts' dimensions when authoring OpenSCAD geometry, over eyeballing the STLs.
- `implementation_plan.md` §"Bảng hằng số baseline" is the intended contents of the not-yet-created `constants.scad`. When creating OpenSCAD files, pull constants from there rather than re-deriving them.
- **Empirically-fixed parameter:** the OV2640 factory lens focuses sharply at **3–5cm** working distance (measured on the actual hardware). The imaging tube is sized around a ~40mm camera-to-water distance. Do not revert to the old 10–15cm distance.

## Core design constraints ("3 KHÔNG" / 3 NOs)

Non-negotiable constraints — check new proposals against them:
1. **No lens modification** — keep the factory lens. Testing showed the factory OV2640 lens already focuses sharply at 3–5cm, so no rotation/replacement is needed; just place the sample at that distance.
2. **No sealed microfluidic chips** — 1–5mm debris would clog/leak micron-scale channels (as in `pone.0244103.pdf`). Uses an open "Macro-Flow Stage" tray with a **fixed water level via an overflow weir** (and optionally a **fixed flat glass window** resting on ledges to flatten the surface). Do **not** use a "freely floating glass slide" — glass is denser than water and sinks; that was an earlier wrong idea.
3. **No manual intervention** — pump, lighting, imaging, counting, and flushing are automated. (Realistic exception: periodic cleaning against biofouling; the baseline is positioned as a demo/lab rig, not a multi-week unattended field deployment.)

## Physical/optical architecture

Short, monolithic cylindrical **"Imaging Tube"** (~40–50mm tall — NOT the old 10–15cm tube or the even older Z-axis cantilever pillar; both are superseded):
- **Top cap (removable)**: **the already-printed Matchboxscope base itself, reused directly as the cap** (not a new round cap hosting the geometry). It seats the XIAO ESP32-S3 Sense with the camera facing straight down and is screwed onto the tube through the base's existing holes (removable, not glued, for servicing).
- **Tube body**: hollow opaque **straight** cylinder — its outer diameter equals the printed base's footprint (~50×52mm) so the base covers/seals the mouth. Decision: keep it a **straight tube, NOT widened into a "cup"** (real testing showed a straight tube images no worse than a wide one — silhouette quality comes from matte-black interior + manual exposure, not tube width). It fixes the ~40mm camera-to-water distance and blocks ambient light; interior matte black to kill stray reflections. Because the mouth is only ~50mm, the tray/window/backlight shrink to fit the bore (~46mm ID → imaged water area ~40mm, still fills the frame).
- **Bottom stage**: open flow tray with a **transparent bottom**, water level fixed by an overflow weir. A **white diffused LED backlight sits BELOW the transparent tray bottom and shines upward** (backlit silhouette).

**Lighting is backlit silhouette, NOT UV fluorescence and NOT oblique darkfield.** A diffused white LED underneath the transparent tray backlights the water; particles appear as dark silhouettes on a bright, even field. Critical practical rules (learned from real testing):
- The light must be **diffused** (frosted sheet / tracing paper) into an even grey field — no hotspot; the camera must never see the bare LED.
- **Manual exposure is mandatory**: in the firmware, turn **OFF AEC (auto exposure), AEC DSP, and AGC (auto gain)**, then set **Gain=0 and a low Exposure value**. If AEC/AGC stay on, the sensor overrides manual values and the field blows out to pure white regardless of physical brightness. (Serial: `t<exposure>`, `g<gain>`.)
- The bright field should **fill the frame** — avoid a small lit disc in a large black surround (wastes pixels and fools auto-exposure).
- Stream/preview can be low-res for smoothness, but **capture analysis frames at high resolution (SXGA/UXGA)** or small particles vanish.

Flow: **an active RS365 12V diaphragm pump drives the whole cycle — NOT gravity, and NOT the rejected 28BYJ-48 peristaltic.** The pump (self-priming) sits at the outlet and pulls the series loop **source → tray → pump → waste**; running it fills/flows, stopping it lets the overflow weir hold the level for settling. Sample enters the tray through a wide tube (ID ≥ 6mm) and a **coarse pre-screen with >5mm openings** (blocks only big debris, not the particles being measured). **Decision (deliberate trade-off): particles DO pass through the pump** at the outlet side — this reverses the earlier "particles never through the pump" rule. It is acceptable **only because the current test scope is <2mm** (smaller than the diaphragm's ~2–4mm check-valve seats, which are the real choke point — not the tube). **If the range ever returns to 5mm this must be revisited.** Flushing is done by **running the pump hard** to sweep particles out via the outlet (an optional bottom drain valve remains only for full draining/cleaning, not required by the cycle). The pump station is physically decoupled from the optical stack to isolate vibration. Electrical: RS365 12V switched by a **logic-level MOSFET (IRLZ44N)** from an ESP32 GPIO, with a **flyback diode (1N4007)** and a **470–1000µF bulk cap** on the 12V rail; powered from a **12V/2A adapter**, ESP32 on its own 5V (USB or a 12V→5V buck), **common ground**. A prior tray model (`khay_dong_chay_001.scad`) still contains a 0.8mm retention mesh at the weir that must be **removed** to match this decision.

## Operating cycle (Stop-Flow)

Pump ON (RS365 pulls source→tray→pump→waste, fills to weir) → Pump OFF 1–2s (weir holds level, surface settles) → white backlight on, capture high-res image → run the **hybrid** pipeline on-device (classical CV: threshold → connected components → centroid + area → count + size distribution; then crop each blob → small classifier → per-particle type) → backlight off, **run pump hard to flush particles out via the outlet**, refill → repeat. See the mermaid sequence diagram in `README.md` for the authoritative current version.

## Image processing / inference

**Hybrid on-device pipeline — classical CV for count/size, a small classifier for type. NOT end-to-end object detection.** (1) Classical CV: grayscale → threshold (dark blobs on the bright backlit field) → connected-components labeling → per-blob centroid + area → particle count and size distribution. (2) Crop each blob → a **small on-device classifier** (TinyML, using the ESP32-S3's vector/AI instructions) → per-particle type label (class list not yet fixed; e.g. plastic / bubble / organic / fiber). Runs on the XIAO ESP32-S3 (PSRAM 8MB, 240MHz); the CV stage may be downscaled to VGA (~14px/mm at ~40mm working distance) to fit RAM, while the classifier only sees small crops. **Do not replace the CV stage with FOMO/end-to-end detection**: FOMO's 96×96 input cannot resolve <2mm particles (~5px at a 40mm FOV, ~143ms/~7fps) and it returns only centroids (no size), losing the size-distribution deliverable. Nile-Red fluorescence is a possible future add-on feeding extra color features to the classifier for plastic-vs-non-plastic discrimination, not the baseline.
