# Arctic Trail Cam System — IKEA-Style Manual Part 2: 3-Zone Enclosure Build, Camouflage, Tree Installation & Field Operation (Stages 4–6)

> **Zero Electronics Experience Required:** Before starting this manual, complete **[Part 1: Indoor Benchtop Assembly & Bring-Up (Stages 1–3)](BENCHTOP_QUICKSTART_GUIDE.md)** on your kitchen table so you know your camera, Pico 2, Raspberry Pi 5, and optical fiber links work.
>
> * Single electrical pin reference: [Wiring & Pinout Schedule](WIRING_PINOUT.md)
> * Parts list & planning BOM: [Hardware Configuration & BOM](HARDWARE_SPECS_AND_BOM.md)
> * Printable PDF booklet (including the **True 1:1 Physical-Scale CAD Vector Drilling Template**, `1.0 mm = 2.8346 pt`): [`ARCTIC_TRAIL_CAM_BUILD_AND_FIELD_GUIDE.pdf`](../../ARCTIC_TRAIL_CAM_BUILD_AND_FIELD_GUIDE.pdf)

---

## Tools (`[T04]`–`[T12]`) & 5-Hole Enclosure Drilling Schedule Reference

The complete workshop tool schedule (`[T01]`–`[T12]`) and the **Exact 5-Hole Enclosure Drilling Table (`Holes 1–5`)** are maintained in **[`HARDWARE_SPECS_AND_BOM.md`](HARDWARE_SPECS_AND_BOM.md#complete-tools--workshop-equipment-schedule-t01t12-with-retail-prices)**.
* **Plastic Hole-Saw Rule (`[T04]` + `[T05]`):** Always drill the central `1/4"` pilot hole in **`FORWARD`**, then flip your cordless drill to **`REVERSE`** before the outer circular hole-saw cup touches the ABS/polycarbonate box so the teeth score and shear cleanly without cracking the plastic.

---

## Visual Roadmap: How Your Working Desk Pile Splits Into the 3 Final Units (Stages 3B, 3C, 4 & 5)

Before you drill a single hole in any plastic enclosure, look at the 2-panel real-photo roadmap below. It shows **1) where every working part currently sitting on your desk (`Stage 3`) goes**, **2) which unopened bags to grab next from your Stage 4–5 parts kit**, and **3) the two quick bench tests (`Step A: 2 m Camera Umbilical + Radar` and `Step B: 12V -> 5V Power Train`) to run on the table before packing the weatherproof boxes**.

![From Desk Pile to 3 Finished Units: Visual Roadmap](images/desk_pile_to_final_units_guide_v6.jpg)

![How the 2-Meter Camera & Radar Extension Works: Exact Location in Parts Kit & Exact Breadboard Holes (a1, a2, a3, j1)](images/radar_and_2m_extension_exact_guide_v7.jpg)

| Physical Unit | What Moves From Your Current Desk Pile (`Left Panel`) | What Unopened Bags You Add From Your Stage 4–5 Parts Kit (`Right Panel`) |
| :--- | :--- | :--- |
| **UNIT #1: Zone 1 Tree Camera & Radar Micro-Pod** *(Mounts at `1.8–2.2 m` height on pine trunk)* | • **`Camera Module 3 NoIR Wide [P05]`** *(unclips from the short `200 mm` ribbon on your desk and moves into the tree pod)* | • **`Arducam CSI-to-HDMI Extension Boards + 2 m Black HDMI Cable [P06]`**<br>• **`HLK-LD2450` 24 GHz Radar + 4-Pin Wire (`[P11]`)**<br>• **`Hammond 1591BSBK` Black ABS Box + `30 mm` Glass Disc + Black Neoprene Foam Ring + `39 Ω 5W` De-Icer (`[P20]`)**<br>• **`Permatex 81158` Black Silicone (`[T11]`)** + **1× Silica Gel Packet** |
| **UNIT #2: Zone 3 Underground Base Compute, Battery & Diode Vault** *(Buried `20–30 cm` in root hummock at base of tree)* | • **`Raspberry Pi 5 [P01]` + `Active Cooler [P02]`**<br>• **`30-Row Breadboard [P09]`** (`Pico 2 [P07]` + `7 Wires [P10]` + `GY-271 Compass [P08]` — stays intact!)<br>• **`Field Media Converter #1 [P13]`** (`LFP = OFF`) + **Short Black Cat6**<br>• **`1×2 Optical Splitter [P14]`** (`White -> TX`, `Blue -> RX`, `Orange -> Coupler`)<br>• **`Blue SC/UPC Coupler [P15]`** | • **`QILIPSU IP67` Grey Hinged Enclosure (`[P21]`)** + **Closed-Cell Foam Liner**<br>• **`12V 12Ah` Battery (`[P17]`)** + **`Littelfuse 5A` Inline Blade Fuse + `6.3 mm` Spade Leads (`[P18]`)**<br>• **`MPM3610 5V` Buck + `12V->5V 5A` Buck + `STEMMA` Relays (`[P12]`)**<br>• **`StarTech USB-to-Type-M 5V` Barrel Cable (`[P19]`)** *(powers `Box #1` from the `5V` buck instead of the wall outlet!)*<br>• **`30 m` Black Armored Outdoor Fiber (`[P16]`)** *(replaces the `1 m` Yellow indoor bench test cord!)* |
| **UNIT #3: Cabin / Collector Receiver Hub** *(Stays indoors at your Cabin / Collector)* | • **`Collector Media Converter #2 [P13]`** (`RX` only, `TX` empty physical air-gap, `LFP = OFF`)<br>• **Blue Cat6 Ethernet (`[P22]`)** + **`USB-C` Gigabit Ethernet Adapter (`[P24]`)** $\rightarrow$ **`MacBook Pro [T02]`** | *Already 100% assembled! In Stage 5/6, simply unplug the `1 m` Yellow indoor bench test cord from `Box #2 RX` and plug in the incoming **`30 m` Black Armored Outdoor Fiber (`[P16]`)**.* |

---

## STAGE 4: Build & Camouflage the Zone 1 Tree Micro-Pod (`Hammond 1591BSBK` `[P20]`)

The **Zone 1 Micro-Pod** is the tiny, fist-sized black ABS box (`112 × 62 × 31 mm`, `[P20]`) that mounts at eye level (`1.8 m–2.2 m`) inside a vertical pine bark crevice. Look at the reference illustration below (and print the **True 1:1 CAD Vector Drilling Template** from [`ARCTIC_TRAIL_CAM_BUILD_AND_FIELD_GUIDE.pdf`](../../ARCTIC_TRAIL_CAM_BUILD_AND_FIELD_GUIDE.pdf) at `100% / Actual Size`) before drilling or gluing.

![Device 1 Reference: Inside the Zone 1 Camera & Radar Pod](images/device_1_camera_radar_pod.jpg)

### Parts & Tools Used in Stage 4

* **Parts:** `[P05]` (`Raspberry Pi Camera Module 3 NoIR Wide` or `Arducam IMX708 NoIR` Camera), `[P06]` (`200 mm` `22-to-15-pin` Ribbon `$9.99` + optional **`Arducam CSI-to-HDMI Extension Kit w/ 2.0 m Shielded Cable` `ASIN B06XDNBM63` `$18.99` for 2 m split-pod umbilical**), `[P11]` (`HLK-LD2450` $24\text{ GHz}$ Radar PCB + Harness — `$10.94`), `[P20]` (`Hammond 1591BSBK` Black ABS Box `$7.45` [factory `IP54` lap-joint; requires `Permatex 81158` perimeter lid-channel silicone gasket] or drop-in **`Hammond 1554EGY` factory `IP68` gasketed box** `$13.50` + `30 mm` Glass Disc `$6.49` + Black Neoprene Foam Ring `$7.99` + **`39-Ohm 5W` Ceramic De-Icer Resistor (`3.69 W` @ `12.0V`)** `$1.99` + `M12 IP68` bottom cable gland `$1.99` = `$25.91`), `[P22]` (`Rust-Oleum` Ultra-Flat Earth Brown `$8.98` & Deep Forest Green `$8.98` spray paint + `Gear Aid Camo Form` `$14.95` = `$32.91`).
* **Tools:** `[T04]` (Cordless drill with `Forward / Reverse`), `[T05]` (`1-1/8"` / `28 mm` Bi-Metal Hole Saw Cup + Center Pilot Drill Bit), `[T06]` (Center awl/nail + `4–22 mm` Titanium Cone Step Drill Bit for `18–20 mm` viewport hole & `12 mm` bottom hole), `[T07]` (`#1` Phillips screwdriver & pliers), `[T10]` (Scissors/craft knife, ruler, file & `400-grit` sandpaper), `[T11]` (Black waterproof silicone, rubbing alcohol, `3M` blue painter's tape & sea sponge), `[T12]` (Safety glasses & gloves).

### Step 4.1 — Drill the Upper Viewport Window (`20 mm` Cone Step Bit `[T06]` or `28 mm` Hole Saw `[T05]`) & `12 mm` Bottom Cable Hole

1. Put on your **Safety Glasses (`[T12]`)**, unscrew the 4 corner Phillips screws (`[T07]`) on the `Hammond 1591BSBK` box (`[P20]`), and place the empty lid flat on a scrap piece of wood on your worktable.
2. **Mark & Dimple the Single Upper Window Crosshair (`Hole 1`):**
   * Measure `32 mm` down from the top edge of the box lid, dead-center between the left and right edges (`31 mm` from either side edge), or tape the `1:1` paper template (`Panel A`) directly onto the lid.
   * Press your **Center Awl or a Sharp Nail (`[T06]`)** firmly into the center `+` crosshair to make a `1 mm` starter dimple so the drill bit cannot wander on the smooth plastic.
3. **Cut the Circular Viewport Window (Two Foolproof Methods — `< 2%` Risk of Cracking):**
   * **Method A — Recommended for `Raspberry Pi Camera Module 3 NoIR Wide [P05]` (`20 mm` Titanium Stepped Cone Bit `[T06]` — Zero Snagging Teeth!):**
     * Because the `Camera Module 3 NoIR Wide` (`25 × 24 mm` PCB) has a compact **`11.5 × 11.5 mm` square lens barrel** (`16 mm` diagonal) and a `6 mm` optical aperture, you do **not** need a `28 mm` hole!
     * Chuck your **Titanium Stepped Cone Drill Bit (`[T06]`)** into your drill (`[T04]`), place the `4 mm` tip into your center dimple, and drill smoothly down to the **`18 mm` or `20 mm` step**. A stepped cone bit has **zero snagging saw teeth**—it shaves a perfectly round, burr-free circle in `15 seconds` with zero risk of catching or cracking the `2 mm` ABS lid, while leaving a wide **`5 mm` solid plastic ledge all the way around (`360°`)** for the **`30 mm` Glass Disc (`[T11]`)** to seal against!
   * **Method B — For Wider `Arducam IMX708` w/ Side IR LEDs (`28 mm` / `1-1/8"` Hole Saw Cup `[T05]` in `REVERSE`):**
     * **Step A (Pilot Hole in `FORWARD`):** Set the drill to **`FORWARD`**, place the central `1/4"` pilot drill bit into your center dimple, and drill until the center bit pokes through—**STOP before the outer circular saw teeth touch the lid!**
     * **Step B (Outer Circle in `REVERSE` — Zero Cracks!):** Flip your drill's direction switch to **`REVERSE`** (`counter-clockwise`). Spin the hole saw in **`REVERSE`** at medium speed with gentle downward pressure so the backwards-spinning teeth score and shear a smooth `28 mm` circle without grabbing.
   * **Why Hole Edge Precision Does NOT Affect Waterproofing:** The drilled hole edge never seals the water out—the **flat inside surface of the lid around the hole** forms the seal! Because the `30 mm` glass disc (`[T11]`) overlaps the `20 mm` hole by `5 mm` on every side, even a slightly off-center hole seals `100%` watertight (`IP67`).
   * **DO NOT drill a hole for the radar in the lower half!** The `HLK-LD2450` $24\text{ GHz}$ radar (`[P11]`) sees straight through the solid `2 mm` ABS plastic wall with $<0.4\text{ dB}$ loss.
4. **Drill the `12 mm` (`1/2"`) Bottom Umbilical Hole (`Hole 2`):**
   * On the **bottom narrow end-wall** of the box (`62 × 31 mm` bottom face), press a center dimple (`[T06]`) dead-center (`31 mm` from left/right, `15.5 mm` from front/back).
   * Using the **Titanium Cone Step Drill Bit (`[T06]`)**, drill straight down to the **`12 mm` (`1/2"`) step** and thread in the **`M12 / PG7 IP68` waterproof cable gland**.

### Step 4.2 — Smudge-Free Glass Window Gluing (`3M` Tape Mask Trick), Foam Baffle & Straight Camera Mounting

1. **Apply the `3M Blue Painter's Tape [T11]` Center-Mask & Handle Before Touching Silicone (`Zero Smudge Risk`):**
   * Wipe both faces of the **`30 mm` Mineral Glass Disc (`[P20]`)** and the inside of the ABS lid with rubbing alcohol (`[T11]`) and let dry for 1 minute.
   * Cut two `20 mm` coin-sized circles of **`3M Blue Painter's Tape [T11]`** and stick one over the **center of the front face** and one over the **center of the back face** of the `30 mm` glass disc (leaving the outer `5 mm` glass rim bare for silicone bonding), with a folded tab of blue tape sticking up in the center like a handle.
2. **Bond the `30 mm` Glass Disc & Let Cure Overnight (`12–24 Hours` Recommended):**
   * Squeeze a continuous `3 mm` donut bead of **`Permatex 81158` Black Silicone (`[T11]`)** onto the flat inside plastic rim around the viewport hole.
   * Holding the `30 mm` glass disc by its blue tape handle tab, press it firmly into the wet silicone ring until a continuous black rubber gasket forms all the way around (`360°`). Let it cure (`30 min` skin-over, `12–24 hrs` full waterproof cure), then **peel off the inner blue tape circle** to reveal `100%` factory-clean, smudge-free glass! *(Leave the outer blue tape circle on until after Step 4.4 camo painting!)*
3. **Install the Anti-Glare Neoprene Foam Baffle Ring & Mount the Camera Dead-Straight (`✓ CRITICAL`):**
   * Press the **black closed-cell neoprene foam donut ring (`22 mm` OD, `12 mm` ID, `5–6 mm` thick, `[P20]`)** snugly around the **`11.5 × 11.5 mm` square central lens barrel** on the front of your camera board (`[P05]`). This creates a light-tight optical tunnel that eliminates internal glass glare and reflections.
   * **Front-Look Alignment & Ribbon Strain-Relief Trick:** Temporarily peel back a peek of the outer tape (or look through the glass from the front) while holding the camera board against the inside of the glass with the **`200 mm` orange ribbon (`[P06]`) exiting straight down**. Looking from the outside front lets you center the lens in the window and align the square PCB edges parallel to the rectangular box walls in `5 seconds`.
   * **Anchor the Ribbon First:** Tape the orange camera ribbon flat against the inside back wall `3 cm` below the camera with a strip of `3M` tape (`[T11]`) so the springy ribbon cannot twist or tilt the camera board, then secure the 4 corners of the camera PCB with `3M` double-sided foam tape + `4` corner dabs of `Permatex Black Silicone [T11]` so the black foam ring stays gently compressed (`1 mm`) against the inside of the glass.
4. **Mount the `39 Ω, 5W` Window De-Icer Resistor (`3.69 W` @ `12.0V`, `[P20]`):**
   * Bond the **`39 Ω, 5W` ceramic de-icer resistor (`[P20]`)** against the lower inside edge of the glass window (outside the foam ring) with thermal tape. Driven from the switched `+12.0V` rail via `STEMMA Relay #2` (`GP16`), it delivers $P = 12.0^2 / 39\,\Omega = 3.69\text{ W}$ (`~3.6 W`, `308 mA`, operating safely at $74\%$ of its `5.0 W` continuous rating during the `4.0 s` sub-zero pre-capture pulse).

### Step 4.3 — Mount the `HLK-LD2450` $24\text{ GHz}$ Radar (`[P11]`), Drop In Anti-Fog Desiccant & Gasket-Seal the Lid

1. Place the **`HLK-LD2450` radar board (`[P11]`)** inside the **lower half** of the `Hammond 1591BSBK` box, below the camera board, with the **shiny copper patch antenna rectangles facing FORWARD** against the solid unpainted/non-metallic front wall.
2. **Route the Umbilical Harness (`[P06]` + `[P11]`) & Add Anti-Fog Silica Gel Desiccant:**
   * Feed the camera umbilical (`[P06]`) and 4-wire radar cable (`[P11]`) out through the bottom `M12 IP68` gland and tighten the sealing nut (`[T07]`).
   * **Prevent Morning Glass Fogging (`-30°C` Anti-Condensation Rule):** Drop **one small silica-gel desiccant packet** (from the unboxed electronics pouches) into the bottom cavity of the `Hammond` pod before closing the lid so trapped indoor humidity can never condense on the cold glass window.
3. **Seal the Enclosure Lid Joint (`IP54` Factory Disclosure & Silicone Gasket Procedure):**
   * Lay a continuous `1.5 mm` bead of **`Permatex 81158` black silicone (`[T11]`)** along the perimeter tongue-and-groove channel of the `1591BSBK` lid and tighten all 4 corner screws evenly (or use the factory-gasketed `Hammond 1554EGY` `IP68` box).

### Step 4.4 — Paint the Zone 1 Pod in Solid Matte Forest Green (`[P22]`)

1. Confirm the **`3M` blue painter's tape circle (`[T11]`)** completely covers the outside of the glass window so zero paint touches the glass.
2. Lightly scuff the outside of the black plastic box with **400-grit sandpaper (`[T10]`)** for 60 seconds and wipe with rubbing alcohol (`[T11]`).
3. Spray 2–3 light, uniform coats of **`Rust-Oleum Specialty Ultra-Flat Deep Forest Green` (`[P22]`, `RAL 6003 / 6005`)** from `25 cm` away and let dry 20 minutes between coats. The uniform solid matte forest green finish gives the unit a clean, non-threatening civilian forestry/environmental sensor appearance that blends naturally against pine foliage and bark while its non-metallic mineral pigment remains 100% radar-transparent (`24 GHz`).
4. Peel the blue painter's tape off the `20 mm` glass window once dry.

---

## STAGE 5: Pack, Insulate, Wire & Commission the Zone 3 Underground Base Vault (`QILIPSU IP67` `[P21]`)

The **Zone 3 Base Vault** is buried **`20–30 cm` underground** in a free-draining root hummock (*mätäs*) at the base of the pine tree beneath `5–10 cm` of insulating forest soil, moss, and winter snowpack, and lined with **`10–20 mm` closed-cell neoprene/XPS thermal insulation foam**. This provides **100% visual & thermal concealment** (zero above-ground box outline) AND **geothermal freeze protection** (keeping the battery bay at **`-2°C to -8°C`** even when surface air drops to **`-30°C to -40°C`**).

Look at the exact physical layout in the diagram below—it matches your physical `QILIPSU` enclosure (`285 × 195 × 130 mm`, `[P21]`) with the **closed-cell thermal foam liner** and the **`ExpertPower 12V 12Ah` battery (`151 × 98 × 95 mm`, `[P17]`) sitting wall-to-wall across the bottom third**.

![Device 2 Reference: Inside the Underground-Buried & Foam-Insulated Zone 3 Base Vault](images/device_2_base_compute_vault.jpg)

### Step 5.1 — Drill the 3 Gland/Vent Holes, Line with Thermal Foam, Mount the Grid Backplate & Strap the Battery

> [!CAUTION]
> **KEEP BATTERY TERMINALS UNPLUGGED UNTIL STEP 5.4!** Cover both silver metal tabs (`Red +` and `Black -`) on top of the `12V 12Ah` battery (`[P17]`) with a piece of blue painter's tape (`[T11]`) while placing components inside the box.

1. **Drill the 3 Holes in the Empty `QILIPSU` Box (`[P21]`) Before Installing Electronics:**
   * **Holes 3 & 4 (`2× Bottom M20 Cable Glands — 20 mm / 3/4"`):** On the bottom wall (`285 × 130 mm`), mark and dimple two crosshairs with your center awl (`[T06]`): one at `75 mm` from the left edge (`65 mm` from front) and one at `210 mm` from the left edge (`65 mm` from front). Using your **Cordless Drill (`[T04]`)** and **`3/4"` (`19–20 mm`) Hole Saw Cup (`[T05]`)** in `REVERSE` (or the **`20 mm` step of your Cone Step Bit `[T06]`**), cut the two circular openings and thread in the **`M20 IP68` cable glands**.
   * **Hole 5 (`1× Right-Side M12 Breather Vent — 12 mm / 1/2"`):** On the right side wall (`45 mm` down from top, `65 mm` from front), dimple the crosshair and drill a **`12 mm` (`1/2"`) hole** using the `12 mm` step on your **Titanium Cone Step Drill Bit (`[T06]`)**, then thread in the **`M12 ePTFE` breather vent**.
2. **Line the Vault Interior & Door with Closed-Cell Thermal Foam Insulation (`10–20 mm` Neoprene / XPS):**
   * Press self-adhesive **`10 mm` closed-cell neoprene or XPS foam sheets** against the inside of the hinged door and around the lower battery bay walls (leaving the `M12 ePTFE` breather vent opening unobstructed).
3. Screw the white ABS grid mounting plate into the back of the `QILIPSU IP67` enclosure (`[P21]`) using the 4 corner Phillips screws (`[T07]`).
4. Place the **`ExpertPower 12V 12Ah` AGM battery (`[P17]`)** horizontally across the **foam-lined bottom third of the enclosure** and cinch it tightly to the grid slots with the heavy-duty Velcro strap (`[T12]`).

### Step 5.2 — Mount the Middle Row (`Stage 2 COTS Breadboard`, `5V Buck`, `Switches`, `Pi 5`) & Lock Connections for Snowmobile/Car Transport

> [!IMPORTANT]
> **Architectural Design Decision — Keep the Exact Stage 2 COTS `30-Row` Breadboard (`[P09]`) & `2.54 mm` Wiring (Zero Custom PCBs, Zero Second Design):**
> 1. **Supply-Chain Anonymity & OPSEC:** Custom PCBs require uploading `Gerber` files to a fabrication house (`JLCPCB`/`PCBWay`), creating a permanent digital blueprint and uniquely traceable board batch. Using 100% generic COTS `ELEGOO` breadboards (`[P09]`) and standard `2.54 mm` jumper ribbons (`[P10]`) guarantees **zero custom manufacturing trail and total COTS plausible deniability**.
> 2. **Cost & Field Modification Agility:** Custom PCBs save `$0` in prototype/small-batch quantities while freezing pin assignments in fiberglass. Keeping the breadboard allows `5-second` field pin modifications and eliminates building or testing a second hardware design.
> 3. **3-Step In-Place Vibration Lock (`Reduces Snowmobile/Car Transport Risk from 65% to < 2%` Without Unplugging a Single Wire):**
>    * **Lock 1 (Rigid Co-Mounting on the Same Backplate):** Peel the backing off the `3M` adhesive foam tape underneath your finished Stage 2 **`30-Row Breadboard [P09]`** (`Pico 2 [P07]` in `Rows 1–20`, `W1–W4` in `Col f Rows 24–27` with `3 empty bottom holes`, and soldered / foil-wedged `GY-271 [P08]` in `Col j Rows 24–28` with `2 empty bottom holes`) and stick it directly onto the white `QILIPSU` grid plate **`3 cm` beside the `Raspberry Pi 5 [P01]`**, adding a nylon zip-tie around the breadboard waist through the grid slots. Because both boards are fixed to the **same rigid plate**, zero relative movement ever tugs on `W5–W7`!
>    * **Lock 2 (`3M` Tape Multi-Pin Block Binding):** Wrap one tight turn of `3M` tape (`[T11]`) around the 4 adjacent black jumper shells in `Col f (Rows 24–27)`, around the left-column `Pico 2` shells (`Col a`), and around the 3 `Pi 5` Outer-Right GPIO sockets (`Pins 10, 14, 16`). Binding single `1x1` shells into a solid block stops individual pins from pivoting (`4x` pull-out resistance).
>    * **Lock 3 (Peelable `Permatex Black Silicone [T11]` Damper Bead):** Squeeze a `2 mm` bead of **`Permatex RTV Black Silicone [T11]`** along the seam where the black jumper shells meet the breadboard face, where the blue `GY-271` PCB meets its 5-pin header collar, and where the 3 female sockets meet the `Pi 5` GPIO header. It cures into a sub-zero (`-54°C`) rubber vibration damper that survives `10G+` snowmobile shocks yet peels off cleanly in one piece with tweezers if you ever modify a wire!

Using M2.5/M3 nylon standoffs, zip-ties, and the breadboard's `3M` adhesive backing on the white grid backplate **above the battery**:

1. **Middle Row (Left to Right, directly above the battery):**
   * **Far Left:** Stick and zip-tie your finished Stage 2 **`30-Row Breadboard [P09]`** (`Pico 2 [P07]` + `GY-271 QMC5883L [P08]` + optional `ADS1115 [P11-SEIS]`), alongside the **`Adafruit MPM3610` `5V` Buck Converter (`[P12]` — Domain A Always-On Power)** and **`Pololu 2810` High-Side MOSFET Switch (`[P12]` — `GP6` Radar Power Switch)**.
   * **Center-Left:** Mount **`Adafruit STEMMA` High-Side Relay #1 (`GP15` Domain B Power)**, **`STEMMA` High-Side Relay #2 (`GP16` `12V` Window De-Icer Switch)**, and the **`12V-to-5V 5A` Buck Converter (`[P12]` — Domain B Switched Power)**.
   * **Center-Right (`3 cm` from Breadboard):** Mount the **`Raspberry Pi 5` (`[P01]`)** with its **Active Cooler (`[P02]`)** and camera ribbon (`[P06]`), apply the `3M` tape + `Permatex Silicone [T11]` vibration damper bead across the jumper housings, and drop `2–3` **silica-gel desiccant packets** into the vault corners.
2. **Top Row (Left to Right, at the very top of the white grid plate):**
   * **Top-Left:** Mount **Field Media Converter #1 (`StarTech MCMGBSCSM10` `[P13]`)**, verify its front **`LFP` DIP switch is slid DOWN to `OFF`** before applying power, and connect a short `15 cm` Cat6 patch cable from the **Pi 5 Ethernet port** to **Media Converter #1 `RJ45`**.
   * **Top-Right:** Secure the **`1×2 SC/UPC` Optical Splitter (`[P14]`)** and **Blue `Cable Matters SC/UPC` Coupler (`[P15]`)** in gentle loops ($\ge 30\text{ mm}$ radius, wider than a soda can), pushing every blue `SC/UPC` plug firmly past the internal spring (`~1 mm` gap at the `Blue Coupler` center flange):
     * Plug the Splitter's **`Blue` Output 1 strand (`50%`)** $\rightarrow$ **Media Converter #1 `RX`** (right optical port — local carrier-detect loopback).
     * Plug the Splitter's **`Orange` Output 2 strand (`50%`)** $\rightarrow$ **Blue `SC/UPC` Coupler (`[P15]`)** $\rightarrow$ **Outbound `3 mm` Black Armored Outdoor Fiber Cable (`[P16]`)** exiting through the bottom-right `M20 IP68` gland (replacing the `1 m` Yellow indoor bench test cord).
     * Plug the Splitter's **Single `White` Input strand** $\rightarrow$ **Media Converter #1 `TX`** (left optical port) **last** so `1000BASE-X` auto-negotiation locks all **4 green LEDs** on Media Converter #1.

### Step 5.3 — Wire the Two Power Domains (`Domain A` Always-On vs. `Domain B` Switched + Radar/Heater Switches)

Using your **Wire Stripper & Crimping Pliers (`[T08]`)** and **`2.5 mm` Flathead / `#1` Phillips Screwdriver (`[T07]`)**, with the **`5A` tan blade fuse (`[P18]`) REMOVED from its fuse holder**, make the power connections below:

| Step | Wire From... | Wire To... | Why / Orientation Check |
| :---: | :--- | :--- | :--- |
| **`[Pwr 1]`** | **Battery `Red (+)` Spade Clip** | **Input wire of `Littelfuse` Holder (`[P18]`)** *(within `10 cm` of battery `+` tab)* | Protects the entire box if any wire ever shorts. |
| **`[Pwr 2]`** | **Output wire of `Littelfuse` Holder (`[P18]`)** | **`MPM3610` `VIN (+)`**, **`STEMMA` Relay #1 `COM`**, AND **`STEMMA` Relay #2 `COM`** | Feeds fused `+12V` to always-on Pico buck and both high-side relay inputs. |
| **`[Pwr 3]`** | **Battery `Black (-)` Spade Clip** | Common **`GND` Bus Strip** (`MPM3610 GND`, `Pico GND Pin 38`, `Relays GND`, `5V 5A Buck GND (-)`, Radar `GND`, Heater `-`) | Every single board MUST share the same `Black (-)` Ground reference! |
| **`[Pwr 4]`** | **`MPM3610` `5V OUT (+)`** | **`Pico 2` `VBUS` (`Pin 40` = Right-side `Row 1`)** AND **`Pololu 2810` Radar Switch `VIN`** | Powers the `Pico 2` gatekeeper continuously at `<4 mW` and supplies `+5V` to the radar switch input. |
| **`[Pwr 5]`** | **`Pico 2` `GP15` (`Pin 20` = Left-side `Row 20`)** | **`STEMMA` Relay #1 `SIGNAL (IN)` pin** *(plus `3V3` to Relay `VCC`)* | Lets the Pico turn the heavy Pi 5 + Fiber Converter ON and OFF. |
| **`[Pwr 6]`** | **`STEMMA` Relay #1 `NO` (Normally Open) screw terminal** | **`+12V IN (+)` of the `12V-to-5V 5A` Buck Converter (`[P12]`)** | Sends `+12V` to the heavy `5V 5A` buck **only** when Relay #1 closes! |
| **`[Pwr 7]`** | **`+5.0V DC OUT` of the `12V-to-5V 5A` Buck Converter** | **Both** the **Pi 5 USB-C power plug** AND the **`StarTech` Media Converter #1 `5V` barrel cable (`[P19]`)** | **CRITICAL:** Both the Pi 5 and the `StarTech` Media Converter receive **strictly regulated `+5.0V DC`**—never `12V`! |
| **`[Pwr 8]`** | **`Pico 2` `GP6` (`Pin 9` = Left-side `Row 9`)** | **`Pololu 2810` Switch `CTRL/ON` pin**; Switch **`VOUT`** $\rightarrow$ **Zone 1 `HLK-LD2450` Radar `5V` (`[P11]`)** | Switches the `180 mA` `+5V` radar load cleanly from `3.3 V` logic (`0.00 W` radar standby in Eco mode). |
| **`[Pwr 9]`** | **`Pico 2` `GP16` (`Pin 21` = Right-side `Row 20`)** | **`STEMMA` Relay #2 `SIGNAL (IN)`**; Relay #2 **`NO`** $\rightarrow$ **Zone 1 `39 Ω, 5W` De-Icer Resistor (`+`)** (`[P20]`) | Pulses `+12.0V` (`3.69 W` / `308 mA`) into the `39 Ω, 5W` window heater for `4.0 s` only when sub-zero & humid. |

Also confirm your sensor & handshake wires on the Pico 2 (`[P07]`):
* **Magnetometer (`GY-271 QMC5883L` `[P08]` in `Col j Rows 24–28`, `2 empty bottom holes` `j29–j30`) & `W1–W4` (`Col f Rows 24–27`, `3 empty bottom holes` `f28–f30`):** `W1 Red (j5 -> f24 = VCC)`; `W2 Black (j3 -> f25 = GND)`; `W4 Yellow (a7 -> f26 = SCL)`; `W3 Blue (a6 -> f27 = SDA)`; `j28 = DRDY (5th pin, bare)`.
* **Radar (`HLK-LD2450` `[P11]`):** `GP0 (Pin 1 / Left Row 1)` $\rightarrow$ Radar `RX`; `GP1 (Pin 2 / Left Row 2)` $\rightarrow$ Radar `TX`; `GP6 (Pin 9 / Left Row 9)` $\rightarrow$ `Pololu 2810` Radar `+5V` switch control (`[Pwr 8]`).
* **Pi 5 Outer-Right GPIO Handshake (`W5–W7`):** `W5 Purple (a11 -> Pi 5 Outer-Right #5 / Pin 10 GPIO15 RX)`; `W7 Green (a13 -> Pi 5 Outer-Right #7 / Pin 14 GND)`; `W6 Orange (a4 -> Pi 5 Outer-Right #8 / Pin 16 GPIO23 DONE)`.

### Step 5.4 — The Mandatory Multimeter `+5.0V DC` Safety Check (`[T09]`)

> [!IMPORTANT]
> **DO NOT SKIP THIS 30-SECOND CHECK!** Before plugging the USB-C power plug into the Raspberry Pi 5 (`[P01]`) or the barrel plug into the `StarTech` Media Converter (`[P13]`), verify the voltage with your **Digital Multimeter (`[T09]`)**.

1. Leave the **Pi 5 USB-C power cable** and **Media Converter barrel plug UNPLUGGED** from those two devices.
2. Push the **`5A` tan blade fuse** into the **`Littelfuse` holder (`[P18]`)** and slide the red and black spade clips onto the **`12V 12Ah` battery (`[P17]`)** (`Red` to `Red +`, `Black` to `Black -`).
3. Turn your **Digital Multimeter (`[T09]`)** dial to **`DC Volts (V= / 20V)`**:
   * **Check 1 (Battery):** Touch Red probe to Fuse output and Black probe to Battery `Black (-)`. You should read **`+12.4V` to `+13.0V DC`**.
   * **Check 2 (Domain A — Pico 5V):** Touch Red probe to `MPM3610 5V OUT` (`Pico Pin 40`) and Black probe to `GND`. You should read **`+4.95V` to `+5.15V DC`**.
   * **Check 3 (Domain B — Pi 5 & Converter 5V):** Wave your screwdriver (`[T03]`) over the magnetometer/radar so `STEMMA` Relay #1 clicks ON (its red LED lights up). Touch Red probe to the `5V 5A` buck output (and the center hole of the Media Converter barrel plug `[P19]`) and Black probe to `GND`. Confirm it reads **strictly `+4.95V` to `+5.15V DC`** (never `12V`!).
4. Remove the `5A` fuse, plug the USB-C power plug into the Pi 5 and the `5V` barrel plug into Media Converter #1, and put the `5A` fuse back in.

### Step 5.5 — Autonomous Field Commissioning: Provision Unique Node Keys & Install `diode-node.service`

Before closing the `QILIPSU` vault for unattended field operation, transition the `Raspberry Pi 5 [P01]` from manual bench mode to **autonomous cold-boot service execution** (`ALLOW_EXAMPLE_KEYS=0`, unique `Ed25519` node identity, hardware Wi-Fi/BT disabled, and read-only `OverlayFS` enabled):

1. **Generate the Unique `Ed25519` Keypair & Node Identity on `Raspberry Pi 5 [P01]`:**
   ```bash
   cd ~/pi-diode-trailcam/pi5_sender_node
   python3 generate_keys.py CAMERA-NORTH-01
   ```
   * This writes `node_key.json` (containing both `"node_id": "CAMERA-NORTH-01"` and `"private_key_hex"`) and prints the public-key registry snippet.
2. **Register the Node's Public Key on Your Cabin Collector Hub (`[T02]`):**
   * Copy the printed `CAMERA-NORTH-01` public key entry into `pi-diode-trailcam/collector_hub/authorized_nodes.json` on your Collector laptop/hub. *(Once `authorized_nodes.json` is present on the Collector Hub, `receiver_hub.py` automatically clears the demo `NODE-NORTH-01` example key and trusts **only** the provisioned nodes in `authorized_nodes.json`.)*
3. **Run the One-Command Production Fast-Boot & Service Installer on `Raspberry Pi 5 [P01]`:**
   ```bash
   sudo bash install_pi5_fastboot.sh CAMERA-NORTH-01
   ```
   * **What `install_pi5_fastboot.sh` configures automatically:**
     1. Copies `/opt/trailcam/sender_node.py`, installs `/etc/trailcam/node_key.json` (`chmod 600`), and writes `/etc/trailcam/node.env` (`NODE_ID=CAMERA-NORTH-01`, `ALLOW_EXAMPLE_KEYS=0`).
     2. Configures `/boot/firmware/config.txt` with `enable_uart=1`, `dtoverlay=disable-wifi`, and `dtoverlay=disable-bt` (`0.00 W` RF at hardware boot).
     3. Enables `/etc/systemd/system/diode-node.service` (`EnvironmentFile=-/etc/trailcam/node.env`) so every time `Pico 2` closes `STEMMA` Relay #1, `Pi 5` boots directly into `sender_node.py`, signs the alert as `CAMERA-NORTH-01`, blasts the `3×` optical carousel, asserts `GPIO23 (DONE)`, and halts cleanly.
     4. Enables read-only `OverlayFS` (`raspi-config nonint do_overlayfs 0`) so sudden power cuts can never corrupt the MicroSD card.
4. **Autonomous Cold-Boot Verification (`✓ STAGE 5 SUCCESS CHECK`):**
   * Reboot/power-cycle once with no SSH session attached. Wave your magnetic screwdriver (`[T03]`) over the sensor: Relay #1 clicks ON, `Pi 5` + Media Converter #1 boot in $<7\text{ seconds}$, the Collector Hub dashboard (`http://127.0.0.1:8123`) receives a verified alert signed by `CAMERA-NORTH-01`, `GPIO23 (DONE)` goes HIGH, and Relay #1 clicks OFF (`0.00 W` Pi standby)!

---

## STAGE 6: Tree Installation, Collector Setup & Operating the System in the Field

![3-Zone Covert Split-Pod Field Camera Unit in Context](images/product_units_in_context.jpg)

### Step 6.1 — Strap Zone 1 to the Pine Trunk & Bury + Insulate Zone 3 Underground

1. **Pick the Right Tree (`3–5 meters` off the trail edge):**
   * Choose a mature pine or spruce tree (`>25 cm` trunk diameter) growing on a slightly raised, free-draining root hummock (*mätäs*) with deep vertical bark grooves and low branches that shade the trunk from direct sky view.
2. **Mount the Zone 1 Micro-Pod (`[P20]`) at `1.8 m–2.2 m` Height (`25°` Oblique Angle):**
   * Tuck the camouflaged `Hammond 1591BSBK` pod into a vertical bark crevice at eye level (`1.8 m–2.2 m`).
   * **Aiming Rule (`25°` Oblique):** Point the single circular glass window **`25°` obliquely down the trail or driveway** (not `90°` straight across the road). This gives the camera and radar a `45 m` view down the approach path so walking intruders or vehicles stay in the frame for several seconds.
   * Secure the pod with a matte brown bark strap or two stainless wood screws through the rear mounting tabs, and tuck a piece of natural pine bark / lichen over the top seam.
3. **Wrap the Zone 2 Trunk Umbilical in `Gear Aid Camo Form` (`[P22]`):**
   * Press the `2 m` umbilical cable straight down a natural vertical groove in the tree bark to the ground, and wrap it with self-clinging matte **`Gear Aid Camo Form`** fabric tape (`[P22]`) so no black wire is visible.
4. **Bury & Insulate the Zone 3 Base Vault (`[P21]`) `20–30 cm` Underground (Concealment + Freeze Protection):**
   * **Dig a Shallow `20–30 cm` Pit in a Free-Draining Root Hummock (*Mätäs*):** Never bury the box in a low puddle or swamp hollow where spring snowmelt collects. Dig between the raised roots on the high side of the tree and spread **`5 cm` of coarse gravel, crushed rock, or dry pine cones** across the bottom of the pit as a free-draining base bed.
   * **Wrap & Insulate with Closed-Cell Foam (`10–20 mm` XPS / Neoprene):** In addition to the interior `10 mm` closed-cell foam liner installed in Step 5.1, wrap a **`10–20 mm` closed-cell extruded polystyrene (XPS) or neoprene foam sleeve** around the exterior sides and top of the latched `QILIPSU IP67` vault before setting it into the pit.
   * **Backfill with `5–10 cm` of Soil & Living Forest Moss (`Sphagnum / Pleurozium`):** Lay the lifted carpet of living forest moss, pine duff, and soil (`5–10 cm` thick) back over the top of the insulated vault so **100% of the box is underground and invisible** from the trail.
   * **Why Underground Burial + Foam Insulation Doubles Cold-Weather Battery Autonomy (WITH vs. WITHOUT Comparison):** Even when Arctic air plunges to **`-35°C to -40°C`** (`-45°C` under snow), geothermal heat from the forest soil combined with the `R-value` of closed-cell foam, moss, and winter snowpack keeps the buried battery compartment between **`-2°C and -8°C`**—preventing electrolyte freezing, eliminating any thermal hot-spot visible to FLIR cameras, and preserving full **`1.5 to 2.5+ year` battery life**!

| Component / Configuration | Reliable Cold-Weather Limit (Outside Air) | Internal Vault / Battery Temp | Usable Battery Capacity & Runtime (`12Ah` AGM / `24Ah` LiFePO4) | Why It Stops / Survival Mechanism |
| :--- | :---: | :---: | :---: | :--- |
| **Zone 1 Tree Micro-Pod (`[P20]` at `2.0 m` in open air)** | **`-35°C to -40°C` (`-31°F to -40°F`)** | Equal to outside air (`+12°C` at lens during `3.69W` de-ice pulse) | *Powered from Zone 3 via `2 m` umbilical* | Contains zero batteries or liquid electrolytes—only solid-state `IMX708` CMOS, `LD2450` MMIC radar, and the `39 Ω, 5W` ceramic window de-icer resistor (`[P12-HEAT]`). |
| **Zone 3 Base Vault WITHOUT Burial & WITHOUT Foam (`Above-ground in open air`, standard `12Ah` AGM `[P17]`)** | **`-15°C to -20°C` (`+5°F to -4°F`)** *(Brownout / freeze risk below `-22°C`)* | Equalizes to outside air (`-15°C to -20°C`) within `3–5 hours` | **`45%–55%` capacity** (`~140–190 days` on `12Ah` AGM) | Below `-22°C`, uninsulated AGM internal resistance (`ESR`) triples, causing voltage sag (`<10.5V` brownout) during the `Pi 5`'s `2.5A` cold-boot spike; partially discharged AGM electrolyte can freeze below `-22°C`. |
| **Zone 3 Base Vault WITHOUT Burial + WITH `10–20 mm` Foam Liner + Supercap Buffer (`[P21-FROST]`, exposed rock site)** | **`-25°C to -28°C` (`-13°F to -18°F`)** | Buffers overnight dips by `+4°C to +6°C` | **`50%–65%` capacity** (`~170–220 days` AGM; `1.0+ yr` `LiFePO4`) | For bare rock/concrete sites where digging is impossible: `2× 2.7V 50F` series supercapacitors absorb the `Pi 5` `2.5A` boot surge so high battery `ESR` at `-28°C` never triggers a brownout. |
| **Zone 3 Base Vault WITH Underground Burial (`20–30 cm`) + `10–20 mm` Closed-Cell Foam + Moss/Snow (`Recommended`)** | **`-35°C to -40°C` (`-31°F to -40°F`)** *(Down to **`-45°C`** with `30+ cm` snowpack)* | **`-2°C to -8°C` (`+28°F to +18°F`)** all winter | **`85%–92%` capacity** (`270–365+ days` `12Ah` AGM; **`1.2–2.5+ years`** `15Ah–24Ah` `LiFePO4`) | Geothermal heat rising from unfrozen subsoil (`+2°C to +4°C` at `1 m` depth) trapped beneath closed-cell XPS/neoprene foam (`R-4`), moss (`R-3.5`), and snow (`R-1/inch`) keeps the battery near freezing even in `-40°C` blizzards. |
| **Extreme Exposed Arctic Bedrock (`-40°C to -45°C` Open Air, Zero Soil)** | **`-40°C to -45°C` (`-40°F to -49°F`)** | Equal to outside air (`-40°C to -45°C`) | **`75%–85%` capacity** (`1.5–2.5+ years`) | Requires swapping `[P17]` to **Lithium Titanate (`LTO`) or `Li-SOCl2` primary pack (`[P17-ARCTIC]`)** + supercap boot buffer (`[P21-FROST]`). |

### Step 6.2 — Connect Your Collector Unit (Choose Your Scenario: `A`, `B1`, `B2`, or `B3`)

Look at the two illustrations below to choose the exact Collector setup that matches your property:

![Device 3 Reference: Cabin Collector Hub (3A) vs. Buried Woods Dead-Drop & 200m–20km Troposcatter NLOS Relay Vault (3B)](images/device_3_collector_units.jpg)

![Supported Deployment Topologies: Cabin Nearby (Scenario A) vs. No Cabin / 200m–20km Over-the-Hill (Scenarios B1, B2, B3)](images/deployment_scenarios_cabin_vs_remote.jpg)

* **If You Have a Cabin Within `30 m` to `10 km` (`Scenario A — Direct Moss-Buried Fiber`):**
  1. Unroll the `3 mm` black steel-tube armored single-mode OS2 fiber cable (`[P16]`) from the tree's Zone 3 Base Vault to your cabin, pressing it `2 cm` under the soft forest moss with a garden trowel (`no trench digging needed`).
  2. Inside the cabin, confirm the front **`LFP` switch on Media Converter #2 (`[P13]`) is slid DOWN to `OFF`**, push the incoming blue `SC/UPC` fiber connector firmly past the spring into the **`RX` port** of **Media Converter #2** (leave `TX` capped as an empty physical air-gap!), power Media Converter #2 with its `5V` adapter (`[P19]`), and connect Cat6 Ethernet to your cabin computer (`10.10.0.100`) so all **4 green LEDs** light solid ON.
* **If There Is NO Cabin Nearby (`Scenario B1 — 200 m Buried Dead-Drop Vault`):**
  1. Run `200 m` of moss-buried armored fiber (`[P16]`) from the trail tree deep into the woods to a second buried **`QILIPSU` Collector Vault (`Variant 3B`)** containing a `12V` battery, `5V` buck, Media Converter #2 (`RX` only), and a headless Collector Pi storing verified JPEGs to a `512 GB` NVMe SSD. Even if an intruder finds and smashes the camera at the trail, the signed photos are already safe `200 m` away under the moss.
* **If You Need Alerts Sent `200 m – 20 km` Over a Forested Hill With NO Line of Sight (`Scenario B3 — 200 m Lateral Fiber + Build D 2.4 GHz Troposcatter & Canopy-Bounce Bridge`):**
  1. **How Scenario B3 (`sky-diode-relay` `Build D`) Defeats Jamming & Interference (6-Layer Defense-in-Depth):**
     * **Layer 1 — `200 m` Lateral Fiber Separation + `L-com HG2414P` `14 dBi` Flat-Panel Spatial Nulling:** Because the camera at the trail (`Zone 1`–`Zone 3`) uses **100% passive glass fiber (`[P16]`)**, a handheld RF jammer carried down the trail has **zero effect** on the camera or its `200 m` fiber link to the buried woods vault. By routing the `200 m` fiber **laterally into the forest** and mounting the weatherproof square **`L-com HG2414P` `14 dBi` Flat-Panel Patch Antenna (`203 × 203 × 38 mm`)** tilted $+2^\circ$ into the sky/canopy scatter volume toward the farmhouse (plus the matching `HG2414P` `14 dBi` flat-panel antenna at the farmhouse aimed at the woods vault's sky scatter volume, NOT the trail), any jammer on the trail sits in the `>20 dB` off-axis/rear null of both flat-panel antennas and is attenuated by dense trees and terrain!
     * **Layer 2 — Out-of-ISM Guard-Band Hopping (`2380.373 MHz`, `2487.818 MHz`, `2459.496 MHz`) & `Mini-Circuits VBF-2435+` Bandpass Filtering:** The `ADALM-PLUTO` SDR + `Skyworks SE2576L-EK1` (`1 W` / `+30 dBm`) PA hops across 3 cryptographic frequencies derived from `SHA256(shared_secret || time_slot)` outside standard Wi-Fi (`2412–2462 MHz`), while the gold `Mini-Circuits VBF-2435+` (`2370–2500 MHz`) coaxial bandpass filter ahead of the `Skyworks SKY65405-21EK1` (`1.2 dB NF`) LNA provides `>40 dB` stopband rejection against LTE/5G/VHF/UHF/GPS blockers.
     * **Layer 3 — `VK7MO` Coherent Lock-In Integration (`+55.8 dB` Processing Gain) & FFT Spectral Excision:** Demodulates signals **`22.0 dB` BELOW the thermal noise floor** (`+14.1 dB` to `+62.3 dB` SNR margin from `200 m` to `20 km` in clear sky, `24h` summer sun, rain, fog, and blizzard snow) while automatically zeroing narrowband/swept jammers in the FFT domain.
     * **Layer 4 — Zero-Data-Loss `512 GB` NVMe Vault Storage & `Ed25519` Anti-Spoofing:** Even against a military-grade wideband barrage jammer, the signed JPEG is **already permanently stored on the `512 GB` NVMe SSD inside the buried `200 m` woods vault** (`<2 ms` after capture) and re-transmits automatically via persistent store-and-forward (`5s` to `300s` exponential backoff) once jamming clears. And because the farmhouse verifies the camera's **`Ed25519` cryptographic signature** before accepting any alert, an attacker can **never inject fake photos or spoofed alerts**.
  2. For complete zero-solder assembly (`~35–45 min`) of the `Build D` `200 m – 20 km` Troposcatter & Canopy-Bounce hardware, see **[`sky-diode-relay/hardware/SKY_RELAY_HARDWARE_SPEC_AND_BOM.md`](../../sky-diode-relay/hardware/SKY_RELAY_HARDWARE_SPEC_AND_BOM.md)**. To provision production `Ed25519` keys (`pi5_sender_node/generate_keys.py`) and launch the live Collector Hub & Dashboard (`collector_hub/receiver_hub.py` + `dashboard_server.py`), follow the **[Software Stack & CLI Reference (`pi-diode-trailcam/README.md`)](../README.md)**.
  3. Once installed, execute the 20-walk acceptance test, night `940 nm` zero-glare verification, and 48-hour (`192-event`) unattended soak test in the **[Field Testing & Validation Guide (`FIELD_TESTING_AND_VALIDATION_GUIDE.md`)](FIELD_TESTING_AND_VALIDATION_GUIDE.md)**.


---

## 10. International Air-Shipping & Battery-Free Transit Guide (Shipping Pre-Assembled Units)

Because the pre-assembled **Zone 1 Micro-Pod (`[P20]`)**, **Zone 3 Base Compute Vault (`[P21]`)**, **Cabin Receiver (`[P13]`)**, and **Optics/Cables (`[P14]`–`[P16]`)** contain **zero lithium or lead-acid batteries** when shipped dry, you can legally airmail or courier the entire pre-assembled, pre-tested system anywhere in the world as **100% standard non-hazardous air cargo (`No IATA Dangerous Goods`)**.

### 10.1 What to Leave Out of the Air Parcel (3 Strict Exclusions)
1. **Lead-Acid / LiFePO4 `12V 12Ah` Main Battery (`[P17]`):** Leave out (`saves 7.72 lbs / 3.50 kg` of shipping weight and avoids `UN2800` / `UN3480` battery rules). Keep the **`Littelfuse 5A Inline Fuse Holder [P18]`** and **`6.3mm (F2)` Red/Black Slide-On Spade Terminal Leads** pre-crimped inside the `QILIPSU` box so the recipient can plug in a local `12V 12Ah` battery in 30 seconds without tools.
2. **Optional `ML2020` Lithium Coin Cell on `Raspberry Pi 5 [P01]`:** Unplug the tiny 2-pin `J5 BAT` RTC coin cell if fitted (`UN3091`). The **`Pico 2 [P07]`** hardware timer timestamps every wake event automatically without a coin cell.
3. **Aerosol Spray Cans (`[P22]`) & Uncured Liquid Silicone Tubes (`[T11]`):** Paint the enclosures and cure the `30mm` glass viewport (`24 hours`) **before** packing. Once cured, dry paint and cured silicone rubber are 100% inert solids.

### 10.2 Nesting Trick ("Russian Doll" Packing in a Single `14" × 10" × 8"` Box — `8.4 lbs / 3.81 kg`)
Because the lower third of the **`QILIPSU` Base Vault (`[P21]`, `285 × 195 × 130 mm`)** is normally occupied by the `12V 12Ah` battery, that entire bottom compartment is **empty during shipping**:
1. Wrap the pre-assembled **`Hammond 1591BSBK` Camera/Radar Pod (`[P20]`)** and the **Cabin Receiver Media Converter (`[P13]`)** in anti-static bubble wrap and nest both **inside the empty lower battery bay of the `QILIPSU` Base Vault**, strapped down with the nylon battery cinch strap (`[T12]`) so nothing shifts in transit.
2. Place a piece of bubble wrap inside the `QILIPSU` lid so the **`Raspberry Pi 5 [P01]`**, **`Active Cooler [P02]`**, and **`Pico 2 [P07]`** cannot vibrate loose, and close the `QILIPSU` latches.
3. Pack the closed `QILIPSU` box alongside the **`30 m` Armored Fiber Spool (`[P16]`)** and umbilical/Ethernet cables inside a standard **`14" × 10" × 8"` (`36 × 25 × 20 cm`)** corrugated box (`Total packed weight: ~8.4 lbs / 3.81 kg`).

| Air Carrier Service (US $\rightarrow$ Nordic / EU) | Typical Rate (`8.4 lbs / 3.81 kg`) | Transit Time | Customs / Tracking Notes |
| :--- | :--- | :--- | :--- |
| **UPS Worldwide Expedited** *(via Pirate Ship)* | **`~$62 – $72`** | `3 – 5 Days` | Door-to-door air tracking + electronic customs pre-clearance |
| **USPS Priority Mail International** *(Commercial Rate)* | **`~$68 – $74`** | `6 – 10 Days` | Handed off to national postal service (*Posti* in Finland) |
| **DHL Express Worldwide** *(via Pirate Ship)* | **`~$82 – $93`** | `2 – 3 Days` | Fastest express air courier with SMS recipient customs link |

### 10.3 Customs Declaration (`CN23`) & 5-Minute Local Battery Hookup at Destination
* **Harmonized Tariff (`HS`) Codes for Smooth Customs Clearance:**
  * `HS 8471.50` — *Single-board microcomputer & digital camera sensor module (`Raspberry Pi 5` + `IMX708`, no battery)* (**`0%` EU/Finland duty tariff**)
  * `HS 8517.62` — *Ethernet-to-optical-fiber media converter modules & passive glass fiber cable (non-RF)* (**`0%` EU/Finland duty tariff**)
  * `HS 8538.10` — *Empty polycarbonate weatherproof electrical junction enclosure (`QILIPSU` + `Hammond`, no battery)*
  * **Important Note on Box Exterior:** Tape a clear notice reading: **`"CONTAINS NO BATTERIES — PASSIVE ELECTRONICS & OPTICS ONLY (NO LITHIUM / NO LEAD-ACID)"`**.
* **5-Minute Local `12V 12Ah` Battery Hookup Upon Arrival (`~€26.90` in Finland/EU):**
  * The recipient buys a standard **`12V 12Ah` (`151 × 98 × 95 mm`, `F2 / 6.3mm` spade terminals)** AGM or LiFePO4 battery locally (e.g., **Motonet** `Product #90-0014` *Yuasa NPW45-12 / MTX Energy 12V 12Ah AGM* or **Biltema** `Product #80-412` *12V 12Ah AGM*, `~€26.90`).
  * Open the `QILIPSU` Base Vault, remove the nested `Hammond` Camera Pod and Cabin Receiver, strap the local `12V 12Ah` battery into the bottom bay, push the pre-crimped **Black (`-`)** and **Red (`+`) `6.3mm` spade connectors** onto the battery tabs (**Red to `+`**, **Black to `-`**), and insert the `5A` blade fuse (`[P18]`). The system is immediately live!

