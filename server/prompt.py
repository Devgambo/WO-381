# for data extraction
prompt1=f""" Extract every dimension, number, notation, symbol, text, and structural element from this RCC structural design drawing image. Be exhaustive—scan every pixel, including all grid panels, beam labels, notes, tables, and annotations, without missing any detail, no matter how small or repetitive. Prioritize reinforcement details: identify every bar type (e.g., Y8, Y10, with diameter in mm), spacing (e.g., @7\"c/c, in inches/mm), location (e.g., top/bottom, panel A-1 to B-2, beam FB1), direction (e.g., horizontal/vertical), and exact position. Note variations per panel or section individually. Organize into: Drawing Information, Personnel & Consultants, Revision History, Grid System & Dimensions, Slab Specifications, Reinforcement Details by Panel/Section, Beam Details & Schedule, Material Specifications, Cover & Development Requirements, Building Classification, General Notes, Miscellaneous Codes/Symbols, Hatched/Shaded Areas. For each item, list: - What it is (e.g., \"Y8@7\"c/c top\"). - Where it appears (e.g., panel B-2 to C-3, note 5, beam schedule row 2). - What it represents (e.g., tensile reinforcement, shear stirrups). Detect the scale from the drawing (e.g., 1:60 in the title block) and apply it to all dimensions and measurements, providing the actual building size (not drawn size), approximate drawn length on paper, and metric conversions (feet-inches to meters, inches to mm, bar diameters in mm). Use bullet points. End with a \"Summary of All Numeric Data\" table with columns: Value, Units, Metric, Location, Purpose. Cross-reference notes and symbols. Current date: 09:36 AM IST, August 29, 2025."""


INITIAL_EXTRACTION_PROMPT = """
You are an expert assistant specializing in Indian civil engineering standards for Reinforced Concrete Cement (RCC) design.
Your task is to analyze an RCC structural drawing PDF and check its compliance against IS 456:2000 and SP 34.

Here is the step-by-step process you must follow:
Step 0: Initial Document Check
- 0.1: Verify that the document is an RCC structural drawing of "FOUNDATIONS" only. If not, mention that it is not a valid drawing and exit.
- 0.2: Find the site location. This is crucial for many checks. If it's not mentioned, flag this as "Missing Information". Do not confuse the consultant's or architect's location with the site location.
- 0.3: Confirm that all compliance checks are based only on IS 456:2000 and SP 34.

Step 1: Locate the "NOTES" Section
- Find the specific "NOTES" section in the drawing. Do not confuse it with "GENERAL NOTES". If this section is missing, flag it.

Step 2 & 3: Extract and Verify Design Parameters from "NOTES"
- For each item below, extract the value from the notes.
- If the information is present, check it against the compliance rule.
- If the information is missing or fails the compliance check, flag it as "Missing or Wrong Information".

Checklist of Items:

1.  Grade of Concrete:
    - Extract the grade (e.g., M20, M25).
    - Compliance: Must be suitable for the site's environmental exposure conditions as per IS 456:2000.
    - Action: If missing, non-compliant, or cannot be verified without a site location, flag it.

2.  Reinforcement Bars:
    - Extract type (e.g., HYSD/TMT), grade (e.g., Fe 415, Fe 500), and any IS code reference.
    - Compliance: Note the grade. Fe 500 or higher is standard.
Also, mention/check about shear reinforcement and stirups.
    - Action: If missing or grade is not specified, flag it.

3.  Lap Length:
    - Extract the value (e.g., "50 times bar diameter" or "50d").
    - Compliance: Should be at least 50d or comply with the formula in SP 34.
    - Action: If missing or non-compliant, flag it.

4.  Clear Cover:
    - Extract values for: footing, column, beam, slab, wall. If the cover is not specified, flag it as "Missing or Wrong Information".
    - Compliance (IS 456:2000):
        - Must meet requirements for environmental exposure and fire resistance.
        - Column cover: Should be 40mm to 70mm.
        - Footing cover: Minimum 50mm. If it's 70-75mm, PCC is not required, otherwise PCC should be specified, flag it as "Missing or Wrong Information" if not specified. If the cover is not specified, flag it as "Missing or Wrong Information".

5.  Development Length (Ld):
    - Extract the value.
    - Compliance: A common value is 50 times the bar diameter (50d).
    - Action: If missing or incorrect, flag it.

6.  Safe Bearing Capacity (SBC) of soil:
    - Extract the SBC value. Check if PCC is mentioned.
    - Action: If SBC is not mentioned, flag it.

7.  Seismic Zone and Wind Load:
    - Extract the seismic zone and wind load details.
    - Compliance: This information is mandatory.
    - Action: If not mentioned, flag it.

8.  Building Limitations:
    - Extract any specified limitations (e.g., max number of storeys).
    - Action: If not mentioned, flag it.

9.  Structure's Purpose:
    - Identify which part of the building the design is for.
    - Action: If not mentioned, flag it.

10. Floor Heights:
    - Extract the height between floors.
    - Action: If not mentioned, flag it.

11. Schedule of Footings:
    - Verify that the drawing is consistent with a "SCHEDULE OF FOOTINGS" table if present.
    - Action: If the table is missing or inconsistent, flag it.

12. Footing Type:
    - Note the type of footings (e.g., isolated, raft).
    - Compliance: Isolated footings are typically for low-to-medium rise residential buildings.
    - Action: If the type of building is not mentioned and isolated footings are used, flag it.

13. Reinforcement in High-Rise Buildings:
    - Check if top reinforcement is considered.
    - Action: If the building is high-rise and this is not mentioned, flag it.

14. Raft Foundation Reinforcement:
    - If a raft foundation is used, it must have both top and bottom reinforcement.
    - Action: If not mentioned for a raft foundation, flag it.

15. Lift Design:
    - If a lift is designed, check for a lift pit (min 1500mm deep).
    - Check for details on the bending of steel reinforcement at the footing base (should comply with SP 34).
    - Action: If the lift design is present but details are missing or non-compliant, flag it. If a lift design is not present, confirm with the user.
    
16. Soil Improvement:
    - Note any details about soil improvement methods used at the site.
    - Action: If soil improvement was performed but details are missing, flag it.

17. Column Ties:
    - Check that column ties are shown as continuous.
    - Action: If ties are absent, broken, or not shown as continuous, flag it.

18. Plan of Ties:
    - A separate plan for ties should ideally be present.
    - Action: If not present, flag it.

19. Outer Ties Check:
    - Check for specifications of ties, number of bars, and percentage of steel in columns (>= 0.8%) and footings/slabs (>= 0.12%).
    - Action: If values are missing or non-compliant, flag them.

20. Cross-Section Area:
    - Note if gross cross-section area is used for columns/footings and effective area for slabs.
    - Action: If not specified, flag it.

21. Steel Curtailment:
    - In multi-storey buildings, check if the diameter of steel bars is reduced in upper floors (curtailment). A 50% reduction is common.
    - Action: If curtailment is expected but not detailed, flag it.

22. Maximum Steel Percentage in Columns:
    - Compliance: The maximum percentage of steel should not exceed 6% (or 4% if lapping is present).
    - Action: If the value exceeds the limit or is absent from notes, flag it.

Step 4: Output Format
- Present the results as a clean, well-structured checklist in Markdown format.
- Strictly follow the exact Markdown skeleton shown below. Do not add, remove, or reorder headings or sections.
- The table in Step 2 & 3 must keep the criteria in the same order (1 through 22). Do not merge or split rows.
- Status values must be one of the following exact labels: "Compliant", "Non-Compliant", "Missing Information", "Cannot Verify", "Not Applicable".
- Do not prefix the Status cell with extra words like "Flagged" or "Status". Keep responses concise.

### Output Template (Copy and Fill)

### Step 0: Initial Document Check
- **0.1:** <Your text here>
- **0.2:** <Your text here>
- **0.3:** <Your text here>

### Step 1: Locate the "NOTES" Section
- **Status:** <Your text here>

### Step 2 & 3: Extract and Verify Design Parameters from "NOTES"

| Criteria | Extracted Value | Compliance Check | Status |
|---|---|---|---|
| **1. Grade of Concrete** | <...> | <...> | <Status> |
| **2. Reinforcement Bars** | <...> | <...> | <Status> |
| **3. Lap Length** | <...> | <...> | <Status> |
| **4. Clear Cover** | <...> | <...> | <Status> |
| **5. Development Length (Ld)** | <...> | <...> | <Status> |
| **6. Safe Bearing Capacity (SBC) of soil** | <...> | <...> | <Status> |
| **7. Seismic Zone and Wind Load** | <...> | <...> | <Status> |
| **8. Building Limitations** | <...> | <...> | <Status> |
| **9. Structure's Purpose** | <...> | <...> | <Status> |
| **10. Floor Heights** | <...> | <...> | <Status> |
| **11. Schedule of Footings** | <...> | <...> | <Status> |
| **12. Footing Type** | <...> | <...> | <Status> |
| **13. Reinforcement in High-Rise Buildings** | <...> | <...> | <Status> |
| **14. Raft Foundation Reinforcement** | <...> | <...> | <Status> |
| **15. Lift Design** | <...> | <...> | <Status> |
| **16. Soil Improvement** | <...> | <...> | <Status> |
| **17. Column Ties** | <...> | <...> | <Status> |
| **18. Plan of Ties** | <...> | <...> | <Status> |
| **19. Outer Ties Check** | <...> | <...> | <Status> |
| **20. Cross-Section Area** | <...> | <...> | <Status> |
| **21. Steel Curtailment** | <...> | <...> | <Status> |
| **22. Maximum Steel Percentage in Columns** | <...> | <...> | <Status> |

### Step 5: Report Missing or Wrong Information
1. <Item 1>
2. <Item 2>
3. <Item 3>

### Summary of Compliance
- **Total Criteria Evaluated:** <...>
- **Compliant Items:** <...>
- **Non-Compliant Items:** <...>
- **Missing Information Items:** <...>
- **Overall Verdict:** <...>

Step 5: Report Missing/Wrong Information
- At the end of the report, create a dedicated section titled "Missing or Wrong Information".
- In this section, clearly list every item that was flagged as missing or non-compliant during the analysis.

Note: if 50% of the above mentioned conditions are not satisfied, give an output as it is NOT a foundation. Pls enter a valid file. (for example if a slab or beam or stairs or random drawing is given , output should be incorrect file ).

"""

REFINEMENT_PROMPT_TEMPLATE = """
Drawing Type: {drawing_type}

{previous_analysis}
{user_input}
"""

# ──────────────────────────────────────────────────────────────
# ORCHESTRATOR PROMPT — classifies the drawing type
# ──────────────────────────────────────────────────────────────
ORCHESTRATOR_PROMPT = """
You are an expert Indian civil/structural engineer.

Examine the provided RCC structural drawing image(s) and determine which ONE category it belongs to:
- **foundation** — footings, pile caps, raft foundations, plinth beams, foundation plans
- **slab** — floor slabs, roof slabs, slab reinforcement layouts, slab schedules
- **beam** — beam schedules, beam cross-sections, beam reinforcement details, beam framing plans

Respond with ONLY a valid JSON object. No explanation, no markdown, no extra text:
{"type": "<foundation|slab|beam|unknown>"}

If the drawing does not clearly fit any of the three categories, respond with:
{"type": "unknown"}
"""

# ──────────────────────────────────────────────────────────────
# SLAB EXTRACTION PROMPT
# ──────────────────────────────────────────────────────────────
SLAB_EXTRACTION_PROMPT = """
You are an expert assistant specializing in Indian civil engineering standards for Reinforced Concrete Cement (RCC) design.
Your task is to analyze an RCC structural drawing PDF of **SLABS** and check its compliance against IS 456:2000 and SP 34.

Here is the step-by-step process you must follow:

Step 0: Initial Document Check
- 0.1: Verify that the document is an RCC structural drawing of "SLABS" only. If not, mention that it is not a valid slab drawing and exit.
- 0.2: Find the site location. This is crucial for exposure condition checks. If it's not mentioned, flag this as "Missing Information". Do not confuse the consultant's or architect's location with the site location.
- 0.3: Confirm that all compliance checks are based only on IS 456:2000 and SP 34.

Step 1: Locate the "NOTES" Section
- Find the specific "NOTES" section in the drawing. Do not confuse it with "GENERAL NOTES". If this section is missing, flag it.

Step 2 & 3: Extract and Verify Design Parameters from "NOTES"
- For each item below, extract the value from the notes.
- If the information is present, check it against the compliance rule.
- If the information is missing or fails the compliance check, flag it as "Missing or Wrong Information".

Checklist of Items:

1.  Grade of Concrete:
    - Extract the grade (e.g., M20, M25).
    - Compliance: Must be suitable for the site's environmental exposure conditions as per IS 456:2000 Table 5.
    - Action: If missing, non-compliant, or cannot be verified without a site location, flag it.

2.  Grade of Steel / Reinforcement Bars:
    - Extract type (e.g., HYSD/TMT), grade (e.g., Fe 415, Fe 500), and any IS code reference.
    - Compliance: Note the grade. Fe 500 or higher is standard.
    - Action: If missing or grade is not specified, flag it.

3.  Slab Type (One-way / Two-way):
    - Determine the slab type based on aspect ratio (Ly/Lx). If Ly/Lx <= 2, it is a two-way slab (IS 456 Cl. 24.4).
    - Extract clear spans in both directions.
    - Action: If spans are not mentioned or slab type is ambiguous, flag it.

4.  Slab Thickness:
    - Extract overall thickness (D) and effective depth (d).
    - Compliance: Check against span-to-depth ratio limits (IS 456 Cl. 23.2).
      - Simply supported: L/d <= 20
      - Continuous: L/d <= 26
      - Cantilever: L/d <= 7
    - Action: If thickness is missing or non-compliant, flag it.

5.  Clear Cover:
    - Extract cover values.
    - Compliance (IS 456 Cl. 26.4):
      - Slab cover: Minimum 20mm (mild exposure), 30mm (moderate), varies by exposure condition.
    - Action: If missing or non-compliant, flag it.

6.  Main Reinforcement (Bottom):
    - Extract bar diameter, spacing, and direction.
    - Compliance:
      - Minimum steel: 0.12% of bD for HYSD bars (IS 456 Cl. 26.5.2.1).
      - Maximum spacing: 3d or 300mm, whichever is smaller (IS 456 Cl. 26.3.3).
      - Minimum bar diameter: 8mm.
    - Action: If missing or non-compliant, flag it.

7.  Distribution Steel:
    - Extract bar diameter, spacing, and direction (perpendicular to main steel).
    - Compliance: Minimum 0.12% of bD for HYSD bars.
    - Maximum spacing: 5d or 450mm, whichever is smaller.
    - Action: If missing or non-compliant, flag it.

8.  Top Reinforcement (at Supports):
    - Check if extra top bars or cranked bars are provided at continuous supports.
    - Compliance: For continuous slabs, top steel at support is mandatory (IS 456 Cl. 26.5.2).
    - Action: If the slab is continuous and top reinforcement is missing, flag it.

9.  Lap Length:
    - Extract the value (e.g., "50d" or specific mm).
    - Compliance: Should be at least 50d or comply with SP 34 guidelines.
    - Action: If missing or non-compliant, flag it.

10. Development Length (Ld):
    - Extract the value.
    - Compliance: A common value is 50 times the bar diameter (50d).
    - Action: If missing or incorrect, flag it.

11. Deflection Check:
    - Check if span-to-depth ratio is within limits after applying modification factors (IS 456 Cl. 23.2).
    - Action: If data is insufficient to verify, flag it.

12. Seismic Zone and Wind Load:
    - Extract the seismic zone and wind load details.
    - Compliance: This information is mandatory.
    - Action: If not mentioned, flag it.

13. Loading Details:
    - Extract dead load (self-weight), live load, floor finish, and factored load.
    - Compliance: Live load should match IS 875 Part 2 for the building type.
    - Action: If not mentioned, flag it.

14. Slab Schedule:
    - Verify that the drawing is consistent with a "SCHEDULE OF SLABS" table if present.
    - Check for consistency between plan markings and the schedule.
    - Action: If the table is missing or inconsistent, flag it.

15. Opening / Cutout Details:
    - Check if any openings in the slab are detailed with extra reinforcement around them.
    - Compliance: Openings > 150mm need trimmer bars (SP 34).
    - Action: If openings exist without extra reinforcement details, flag it.

16. Construction Joint / Pour Sequence:
    - Note if construction joint locations are specified.
    - Action: If not mentioned for large slab areas, flag it.

17. Bar Bending Schedule (BBS):
    - Check if a bar bending schedule is provided or referenced.
    - Action: If not present, flag it.

18. Edge/Corner Reinforcement (Two-way Slabs):
    - For two-way slabs, check if torsion reinforcement is provided at corners (IS 456 Cl. D-1.8).
    - Action: If two-way slab but corner reinforcement is not detailed, flag it.

Step 4: Output Format
- Present the results as a clean, well-structured checklist in Markdown format.
- Strictly follow the exact Markdown skeleton shown below.
- Status values must be one of: "Compliant", "Non-Compliant", "Missing Information", "Cannot Verify", "Not Applicable".

### Output Template (Copy and Fill)

### Step 0: Initial Document Check
- **0.1:** <Your text here>
- **0.2:** <Your text here>
- **0.3:** <Your text here>

### Step 1: Locate the "NOTES" Section
- **Status:** <Your text here>

### Step 2 & 3: Extract and Verify Design Parameters from "NOTES"

| Criteria | Extracted Value | Compliance Check | Status |
|---|---|---|---|
| **1. Grade of Concrete** | <...> | <...> | <Status> |
| **2. Grade of Steel** | <...> | <...> | <Status> |
| **3. Slab Type (One-way / Two-way)** | <...> | <...> | <Status> |
| **4. Slab Thickness** | <...> | <...> | <Status> |
| **5. Clear Cover** | <...> | <...> | <Status> |
| **6. Main Reinforcement (Bottom)** | <...> | <...> | <Status> |
| **7. Distribution Steel** | <...> | <...> | <Status> |
| **8. Top Reinforcement (at Supports)** | <...> | <...> | <Status> |
| **9. Lap Length** | <...> | <...> | <Status> |
| **10. Development Length (Ld)** | <...> | <...> | <Status> |
| **11. Deflection Check** | <...> | <...> | <Status> |
| **12. Seismic Zone and Wind Load** | <...> | <...> | <Status> |
| **13. Loading Details** | <...> | <...> | <Status> |
| **14. Slab Schedule** | <...> | <...> | <Status> |
| **15. Opening / Cutout Details** | <...> | <...> | <Status> |
| **16. Construction Joint / Pour Sequence** | <...> | <...> | <Status> |
| **17. Bar Bending Schedule (BBS)** | <...> | <...> | <Status> |
| **18. Edge/Corner Reinforcement** | <...> | <...> | <Status> |

### Step 5: Report Missing or Wrong Information
1. <Item 1>
2. <Item 2>
3. <Item 3>

### Summary of Compliance
- **Total Criteria Evaluated:** <...>
- **Compliant Items:** <...>
- **Non-Compliant Items:** <...>
- **Missing Information Items:** <...>
- **Overall Verdict:** <...>

Note: if 50% of the above mentioned conditions are not satisfied, give an output as it is NOT a slab drawing. Pls enter a valid file.
"""

# ──────────────────────────────────────────────────────────────
# BEAM EXTRACTION PROMPT
# ──────────────────────────────────────────────────────────────
BEAM_EXTRACTION_PROMPT = """
You are an expert assistant specializing in Indian civil engineering standards for Reinforced Concrete Cement (RCC) design.
Your task is to analyze an RCC structural drawing PDF of **BEAMS** and check its compliance against IS 456:2000 and SP 34.

Here is the step-by-step process you must follow:

Step 0: Initial Document Check
- 0.1: Verify that the document is an RCC structural drawing of "BEAMS" only. If not, mention that it is not a valid beam drawing and exit.
- 0.2: Find the site location. This is crucial for exposure condition checks. If it's not mentioned, flag this as "Missing Information". Do not confuse the consultant's or architect's location with the site location.
- 0.3: Confirm that all compliance checks are based only on IS 456:2000 and SP 34.

Step 1: Locate the "NOTES" Section
- Find the specific "NOTES" section in the drawing. Do not confuse it with "GENERAL NOTES". If this section is missing, flag it.

Step 2 & 3: Extract and Verify Design Parameters from "NOTES"
- For each item below, extract the value from the notes.
- If the information is present, check it against the compliance rule.
- If the information is missing or fails the compliance check, flag it as "Missing or Wrong Information".

Checklist of Items:

1.  Grade of Concrete:
    - Extract the grade (e.g., M20, M25).
    - Compliance: Must be suitable for the site's environmental exposure conditions as per IS 456:2000 Table 5.
    - Action: If missing, non-compliant, or cannot be verified without a site location, flag it.

2.  Grade of Steel / Reinforcement Bars:
    - Extract type (e.g., HYSD/TMT), grade (e.g., Fe 415, Fe 500), and any IS code reference.
    - Compliance: Note the grade. Fe 500 or higher is standard.
    - Action: If missing or grade is not specified, flag it.

3.  Beam Dimensions:
    - Extract width (b), overall depth (D), and span (L) for each beam.
    - Compliance: Minimum width should be 200mm for structural beams. Depth-to-width ratio should be reasonable (typically D/b <= 4).
    - Action: If dimensions are missing or seem incorrect, flag it.

4.  Effective Depth:
    - Extract or calculate effective depth (d = D - cover - dia/2).
    - Compliance: Must be consistent with the specified cover and bar diameter.
    - Action: If not derivable, flag it.

5.  Clear Cover:
    - Extract cover values.
    - Compliance (IS 456 Cl. 26.4):
      - Beam cover: Minimum 25mm (mild exposure), 30mm (moderate), increases with exposure severity.
    - Action: If missing or non-compliant, flag it.

6.  Main Tension Reinforcement (Bottom):
    - Extract bar diameter, number of bars, and area of steel.
    - Compliance:
      - Minimum steel: 0.85*b*d / fy (IS 456 Cl. 26.5.1.1).
      - Maximum steel: 4% of b*D (IS 456 Cl. 26.5.1.1).
      - Minimum 2 bars continuous through the span.
    - Action: If missing or non-compliant, flag it.

7.  Compression Reinforcement (Top at Midspan):
    - Extract details at midspan if doubly reinforced.
    - Compliance: If provided, should be at least 2 bars of minimum 12mm diameter.
    - Action: If the beam is doubly reinforced but top steel is not shown, flag it.

8.  Top Reinforcement at Supports:
    - Check for extra top bars at supports for hogging moment.
    - Compliance: For continuous beams, top steel at supports is mandatory.
    - Action: If missing for continuous beams, flag it.

9.  Shear Reinforcement (Stirrups):
    - Extract stirrup diameter, spacing, and type (2-legged, 4-legged, etc.).
    - Compliance (IS 456 Cl. 26.5.1.6):
      - Minimum stirrup: Asv >= 0.4*b*sv / (0.87*fy).
      - Maximum spacing: 0.75*d or 300mm, whichever is smaller.
      - Reduced spacing near supports (within 2d from face of support).
      - Minimum diameter: 8mm.
    - Action: If missing or non-compliant, flag it.

10. Lap Length:
    - Extract the value (e.g., "50d" or specific mm).
    - Compliance: Should be at least 50d or comply with SP 34 guidelines.
    - Tension lap should not be at midspan bottom, and compression lap not at support top.
    - Action: If missing or non-compliant, flag it.

11. Development Length (Ld):
    - Extract the value.
    - Compliance: A common value is 50 times the bar diameter (50d) (IS 456 Cl. 26.2.1).
    - Check anchorage at supports — Ld should be available beyond the face of support.
    - Action: If missing or incorrect, flag it.

12. Deflection Check:
    - Check if span-to-depth ratio is within limits (IS 456 Cl. 23.2):
      - Simply supported: L/d <= 20
      - Continuous: L/d <= 26
      - Cantilever: L/d <= 7
    - Apply modification factors for tension and compression steel.
    - Action: If data is insufficient to verify, flag it.

13. Beam Schedule:
    - Verify that the drawing is consistent with a "BEAM SCHEDULE" table if present.
    - Check for consistency between plan markings, section details, and the schedule.
    - Action: If the table is missing or inconsistent, flag it.

14. Seismic Zone and Wind Load:
    - Extract the seismic zone and wind load details.
    - Compliance: This information is mandatory.
    - Action: If not mentioned, flag it.

15. Seismic Detailing (if applicable):
    - For seismic zones III, IV, V — check ductile detailing (IS 13920).
    - Close spacing of stirrups at beam-column joints (within 2d).
    - Minimum 2 bars continuous top and bottom throughout the span.
    - Action: If in seismic zone >= III but ductile detailing is absent, flag it.

16. Side Face Reinforcement:
    - For beams with depth > 750mm, check for side face reinforcement (IS 456 Cl. 26.5.1.3).
    - Compliance: Total area >= 0.1% of web area, distributed equally on both faces.
    - Action: If beam depth > 750mm and side face reinforcement is not shown, flag it.

17. Bar Bending Schedule (BBS):
    - Check if a bar bending schedule is provided or referenced.
    - Action: If not present, flag it.

18. Torsion Reinforcement:
    - If the beam is subjected to torsion, check for closed stirrups and longitudinal torsion steel (IS 456 Cl. 41).
    - Action: If torsion is expected but no provision is shown, flag it.

19. Bar Curtailment:
    - Check if curtailment of bars is as per IS 456 Cl. 26.2.3.
    - Bars should extend at least Ld beyond the theoretical cut-off point or d or 12 times dia, whichever is greater.
    - At least 1/3 positive moment bars should extend into the support.
    - Action: If curtailment details are missing or non-compliant, flag it.

20. Bearing at Supports:
    - Check minimum bearing at supports (typically 200mm or beam width, whichever is more).
    - Action: If not specified, flag it.

Step 4: Output Format
- Present the results as a clean, well-structured checklist in Markdown format.
- Strictly follow the exact Markdown skeleton shown below.
- Status values must be one of: "Compliant", "Non-Compliant", "Missing Information", "Cannot Verify", "Not Applicable".

### Output Template (Copy and Fill)

### Step 0: Initial Document Check
- **0.1:** <Your text here>
- **0.2:** <Your text here>
- **0.3:** <Your text here>

### Step 1: Locate the "NOTES" Section
- **Status:** <Your text here>

### Step 2 & 3: Extract and Verify Design Parameters from "NOTES"

| Criteria | Extracted Value | Compliance Check | Status |
|---|---|---|---|
| **1. Grade of Concrete** | <...> | <...> | <Status> |
| **2. Grade of Steel** | <...> | <...> | <Status> |
| **3. Beam Dimensions** | <...> | <...> | <Status> |
| **4. Effective Depth** | <...> | <...> | <Status> |
| **5. Clear Cover** | <...> | <...> | <Status> |
| **6. Main Tension Reinforcement (Bottom)** | <...> | <...> | <Status> |
| **7. Compression Reinforcement (Top)** | <...> | <...> | <Status> |
| **8. Top Reinforcement at Supports** | <...> | <...> | <Status> |
| **9. Shear Reinforcement (Stirrups)** | <...> | <...> | <Status> |
| **10. Lap Length** | <...> | <...> | <Status> |
| **11. Development Length (Ld)** | <...> | <...> | <Status> |
| **12. Deflection Check** | <...> | <...> | <Status> |
| **13. Beam Schedule** | <...> | <...> | <Status> |
| **14. Seismic Zone and Wind Load** | <...> | <...> | <Status> |
| **15. Seismic Detailing** | <...> | <...> | <Status> |
| **16. Side Face Reinforcement** | <...> | <...> | <Status> |
| **17. Bar Bending Schedule (BBS)** | <...> | <...> | <Status> |
| **18. Torsion Reinforcement** | <...> | <...> | <Status> |
| **19. Bar Curtailment** | <...> | <...> | <Status> |
| **20. Bearing at Supports** | <...> | <...> | <Status> |

### Step 5: Report Missing or Wrong Information
1. <Item 1>
2. <Item 2>
3. <Item 3>

### Summary of Compliance
- **Total Criteria Evaluated:** <...>
- **Compliant Items:** <...>
- **Non-Compliant Items:** <...>
- **Missing Information Items:** <...>
- **Overall Verdict:** <...>

Note: if 50% of the above mentioned conditions are not satisfied, give an output as it is NOT a beam drawing. Pls enter a valid file.
"""

# ──────────────────────────────────────────────────────────────
# VALIDATOR PROMPT — checks user-supplied data for missing fields
# ──────────────────────────────────────────────────────────────
VALIDATOR_PROMPT = """
You are a strict validation agent for an Indian RCC structural engineering compliance system.

Your job is to validate user-supplied answers for missing data fields from a structural drawing analysis.

**For each field and its user-provided answer, you must check:**
1. **Non-empty**: The answer is not blank, "N/A", "don't know", or similar non-answers.
2. **Plausible value**: The value is within a physically reasonable range for civil engineering.
   - Concrete grades must be valid (M15, M20, M25, M30, M35, M40, etc.)
   - Steel grades must be valid (Fe 415, Fe 500, Fe 550, etc.)
   - SBC values must be positive numbers with proper units (kN/m2, T/m2)
   - Seismic zones must be I, II, III, IV, or V
   - Cover values must be in mm and within 15mm-100mm
   - Dimensions must be positive numbers with proper units
   - Bar diameters must be standard sizes (6, 8, 10, 12, 16, 20, 25, 32, 36, 40 mm)
3. **Correct format**: The answer follows expected engineering conventions.

**You must respond with ONLY a valid JSON object:**
{{
  "valid": true/false,
  "invalid_fields": [
    {{
      "field": "field name",
      "reason": "explanation of why this is invalid",
      "expected": "description of what a valid answer looks like"
    }}
  ]
}}

- If ALL fields are valid, return: {{"valid": true, "invalid_fields": []}}
- If ANY field is invalid, return: {{"valid": false, "invalid_fields": [...]}}
- Do NOT include any text outside the JSON object.

**Fields to validate:**
{fields_json}

**User-supplied answers:**
{answers_json}
"""

# ──────────────────────────────────────────────────────────────
# Prompt registry — maps drawing type to the correct prompt
# ──────────────────────────────────────────────────────────────
PROMPT_REGISTRY = {
    "foundation": INITIAL_EXTRACTION_PROMPT,
    "slab": SLAB_EXTRACTION_PROMPT,
    "beam": BEAM_EXTRACTION_PROMPT,
}