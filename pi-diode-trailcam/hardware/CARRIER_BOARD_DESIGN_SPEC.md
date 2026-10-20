# Optional carrier-board design status

**Unreleased design study — do not fabricate the current outputs.** This document owns carrier development requirements; the modular build uses the [system BOM](../docs/HARDWARE_SPECS_AND_BOM.md) and [wiring schedule](../docs/WIRING_PINOUT.md).

The proposed carrier consolidates the Pico, always-on sensing supply, switched compute power, sensor interfaces, and heater control on a nominal 100 × 80 mm four-layer board. Those dimensions and functions are design intent, not qualification.

The [master decisions and roadmap](../../PROJECT_DECISIONS_AND_ROADMAP.md#decision-1-drop-the-custom-pcb--go-100-cots-modular-for-v1) record the decision to drop the custom carrier for V1 in favor of a 100% COTS modular build, along with the historical carrier-board layout defect analysis (mixed-voltage internal plane connections, different-net crossings, signals terminating on the wrong copper layer, incomplete schematic, and mismatched connector/radar assignments).

## Authoritative data model: CAD files over Markdown and images

To prevent the design drift and manufacturing defects identified in the assessment, **the project must use real CAD files (KiCad `.kicad_sch` and `.kicad_pcb`, and 3D `.step`) as the authoritative data model for all electronics design**, rather than relying on Markdown files (`.md`), standalone Python coordinate scripts, or concept illustrations.

1. **CAD as Single Source of Truth:**
   * The KiCad schematic defines the true electrical connectivity and component parameters.
   * The KiCad PCB defines exact physical placement, trace routing, copper clearances, layer stackup, and real-world millimeter dimensions.
   * 3D STEP models (`.step`) define mechanical clearances and component height envelopes inside the enclosure.

2. **Markdown and Visuals as Derivative Artifacts:**
   * **BOMs & Pinouts:** Markdown tables such as [ARCTIC_CARRIER_BOM.md](ARCTIC_CARRIER_BOM.md) and [WIRING_PINOUT.md](../docs/WIRING_PINOUT.md) must be exported or validated directly against the CAD schematic netlist, never manually edited or assumed to drive the circuit.
   * **2D Vector Layouts (SVG):** Exported directly from KiCad (`kicad-cli pcb export svg`) at 1:1 metric scale. These SVGs serve as the ground truth for assembly documentation and as semantic color-coded reference maps for technical documentation rendering.
   * **3D Mechanical & Documentation Renders:** Exported from KiCad as STEP (`kicad-cli pcb export step`) into FreeCAD/Blender. Orthographic and isometric mechanical renders provide exact perspective, connector orientation, and component scale verification for assembly manuals.

## Required development sequence

1. Freeze exact board/module variants, power requirements and connector pin assignments.
2. Complete a connected schematic in KiCad with correct parts, protection, switch drive and regulator requirements.
3. Derive the [component inventory](ARCTIC_CARRIER_BOM.md) from that schematic, verifying packages, limits and qualified substitutions.
4. Route the board in KiCad from the actual netlist with explicit voltage zones, clearances, current capacity and necessary layer transitions.
5. Run real KiCad ERC/DRC; review footprints, connector orientation, manufacturing outputs and assembly data independently.
6. Export 3D STEP models to verify enclosure clearance (dry-fit) against the battery, media converter, and cables in FreeCAD.
7. Bring up assembled prototypes with current limits, then verify load transients, leakage, sensor noise, temperature behavior and repeated cycles.

Generated Gerbers and assembly ZIPs are retained for engineering investigation only. Their filenames are not a release authorization. The camera/fiber prototype does not require this optional carrier to be finished first.
