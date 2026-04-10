# for data extraction
prompt1=f""" Extract every dimension, number, notation, symbol, text, and structural element from this RCC structural design drawing image. Be exhaustive—scan every pixel, including all grid panels, beam labels, notes, tables, and annotations, without missing any detail, no matter how small or repetitive. Prioritize reinforcement details: identify every bar type (e.g., Y8, Y10, with diameter in mm), spacing (e.g., @7\"c/c, in inches/mm), location (e.g., top/bottom, panel A-1 to B-2, beam FB1), direction (e.g., horizontal/vertical), and exact position. Note variations per panel or section individually. Organize into: Drawing Information, Personnel & Consultants, Revision History, Grid System & Dimensions, Slab Specifications, Reinforcement Details by Panel/Section, Beam Details & Schedule, Material Specifications, Cover & Development Requirements, Building Classification, General Notes, Miscellaneous Codes/Symbols, Hatched/Shaded Areas. For each item, list: - What it is (e.g., \"Y8@7\"c/c top\"). - Where it appears (e.g., panel B-2 to C-3, note 5, beam schedule row 2). - What it represents (e.g., tensile reinforcement, shear stirrups). Detect the scale from the drawing (e.g., 1:60 in the title block) and apply it to all dimensions and measurements, providing the actual building size (not drawn size), approximate drawn length on paper, and metric conversions (feet-inches to meters, inches to mm, bar diameters in mm). Use bullet points. End with a \"Summary of All Numeric Data\" table with columns: Value, Units, Metric, Location, Purpose. Cross-reference notes and symbols. Current date: 09:36 AM IST, August 29, 2025."""


INITIAL_EXTRACTION_PROMPT = """
You are an expert assistant specializing in Indian civil engineering standards for Reinforced Concrete Cement (RCC) design.
Your task is to analyze an RCC structural drawing PDF and check its compliance against IS 456:2000 and SP 34.

Here is the step-by-step process you must follow:
Step 0: Initial Document Check
- 0.1: Verify that the document is an RCC structural drawing of "FOUNDATIONS" only. If not, mention that it is not a valid drawing and exit.
- 0.2: Find the site location. This is crucial for many checks. If it's not mentioned, flag this as "Missing Information" (as "location"). Do not confuse the consultant's or architect's location with the site location.
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
- **column** — column layouts, column schedules, column reinforcement details, column cross 

Respond with ONLY a valid JSON object. No explanation, no markdown, no extra text:
{"type": "<foundation|slab|beam|unknown>"}

If the drawing does not clearly fit any of the three categories, respond with:
{"type": "unknown"}
"""

# ──────────────────────────────────────────────────────────────
# SLAB EXTRACTION PROMPT
# ──────────────────────────────────────────────────────────────
SLAB_EXTRACTION_PROMPT = """
SLAB

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
    - Additional Check: Minimum grade for RCC slabs should not be less than M20.
    - Action: If missing, non-compliant, or cannot be verified without a site location, flag it.

2.  Grade of Steel / Reinforcement Bars:
    - Extract type (e.g., HYSD/TMT), grade (e.g., Fe 415, Fe 500), and any IS code reference.
    - Compliance: Fe 500 or higher is standard. Must conform to IS 1786.
    - Action: If missing or grade is not specified, flag it.

3.  Slab Type (One-way / Two-way):
    - Determine slab type based on aspect ratio (Ly/Lx). If Ly/Lx <= 2, it is a two-way slab (IS 456 Cl. 24.4).
    - Extract clear spans in both directions (center-to-center minus support width).
    - Additional Check: Confirm support condition (simply supported / continuous).
    - Action: If spans are not mentioned or slab type is ambiguous, flag it.

4.  Slab Thickness:
    - Extract overall thickness (D) and effective depth (d).
    - Compliance: Check against span-to-depth ratio limits (IS 456 Cl. 23.2).
    - Additional Check: Ensure minimum thickness ≥ 100 mm (practical slab design guideline).
    - Action: If thickness is missing or non-compliant, flag it.

5.  Clear Cover:
    - Extract cover values.
    - Compliance (IS 456 Cl. 26.4):
      - Slab cover: Minimum 20mm (mild exposure), 30mm (moderate), etc.
    - Additional Check: Cover should not exceed 75mm unnecessarily.
    - Action: If missing or non-compliant, flag it.

6.  Main Reinforcement (Bottom):
    - Extract bar diameter, spacing, and direction.
    - Compliance:
      - Minimum steel: 0.12% of bD for HYSD bars (IS 456 Cl. 26.5.2.1).
      - Maximum spacing: 3d or 300mm, whichever is smaller.
      - Minimum bar diameter: 8mm.
    - Additional Check: Check if spacing consistency is maintained across slab panel.
    - Action: If missing or non-compliant, flag it.

7.  Distribution Steel:
    - Extract bar diameter, spacing, and direction.
    - Compliance:
      - Minimum 0.12% of bD.
      - Maximum spacing: 5d or 450mm.
    - Additional Check: Must be perpendicular to main reinforcement.
    - Action: If missing or non-compliant, flag it.

8.  Top Reinforcement (at Supports):
    - Check if extra top bars or cranked bars are provided.
    - Compliance: Mandatory for continuous slabs.
    - Additional Check: Verify anchorage length into supports.
    - Action: If missing, flag it.

9.  Lap Length:
    - Extract value (e.g., 50d).
    - Compliance: ≥ 50d or as per SP 34.
    - Additional Check: Ensure laps are staggered and not all at same section.
    - Action: If missing or non-compliant, flag it.

10. Development Length (Ld):
    - Extract value.
    - Compliance: As per IS 456 Cl. 26.2 (not just assumed 50d).
    - Additional Check: Verify Ld based on stress and bond conditions if data available.
    - Action: If missing or incorrect, flag it.

11. Deflection Check:
    - Check span-to-depth ratio with modification factors.
    - Additional Check: Consider tension reinforcement percentage if available.
    - Action: If insufficient data, flag it.

12. Seismic Zone and Wind Load:
    - Extract details.
    - Compliance: Must reference IS 1893 (seismic) and IS 875 (wind).
    - Action: If not mentioned, flag it.

13. Loading Details:
    - Extract dead load, live load, floor finish, and factored load.
    - Compliance: Live load must match IS 875 Part 2.
    - Additional Check: Ensure load combinations are mentioned.
    - Action: If missing, flag it.

14. Slab Schedule:
    - Verify consistency between plan and schedule.
    - Additional Check: Check marking labels (S1, S2, etc.).
    - Action: If missing or inconsistent, flag it.

15. Opening / Cutout Details:
    - Check reinforcement around openings.
    - Compliance: Openings >150mm require trimming bars.
    - Additional Check: Verify stress redistribution detailing.
    - Action: If missing, flag it.

16. Construction Joint / Pour Sequence:
    - Check if joints are specified.
    - Additional Check: Verify joints are placed at low moment regions.
    - Action: If missing, flag it.

17. Bar Bending Schedule (BBS):
    - Check presence or reference.
    - Additional Check: Ensure bar marks match drawing.
    - Action: If missing, flag it.

18. Edge/Corner Reinforcement:
    - For two-way slabs, check torsion reinforcement.
    - Compliance: IS 456 Cl. D-1.8.
    - Additional Check: Verify % of main reinforcement provided.
    - Action: If missing, flag it.

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
- 0.1.1: Ensure drawing contains beam layout, beam sections, reinforcement details, or beam schedule. If only architectural layout → reject.
- 0.1.2: If mixed drawings exist (slab/column/foundation), extract only beam-related data.
- 0.2: Find the site location. This is crucial for exposure condition checks. If it's not mentioned, flag this as "Missing Information".
- 0.2.1: If location suggests aggressive environment (coastal/industrial), assume severe exposure conservatively.
- 0.3: Confirm that all compliance checks are based only on IS 456:2000 and SP 34.
- 0.4: Identify drawing scale, units (mm/m), and levels. If unclear → "Cannot Verify".
- 0.5: Identify beam support conditions (simply supported / continuous / cantilever).

Step 1: Locate the "NOTES" Section
- Find the specific "NOTES" section. Do not confuse with "GENERAL NOTES".
- If multiple exist, prioritize "STRUCTURAL NOTES".

Step 2 & 3: Extract and Verify Design Parameters from "NOTES"

General Rule:
- If multiple values → choose conservative.
- If conflicting → "Non-Compliant".
- If inferred but not explicit → "Cannot Verify".

Checklist of Items:

1.  Grade of Concrete:
    - Extract grade
    - Compliance:
        - Minimum M20
        - As per exposure (IS 456 Table 5)
    - Additional Check:
        - For heavily loaded beams → M25+
    - Action: If missing → flag

2.  Grade of Steel / Reinforcement Bars:
    - Extract type, grade, IS code
    - Compliance: Fe 500+ preferred
    - Additional Check:
        - Check ductility requirement (important in seismic zones)
    - Action: If missing → flag

3.  Beam Dimensions:
    - Extract b, D, span L
    - Compliance:
        - Minimum width ≥ 200mm
        - D/b ≤ 4 (practical)
    - Additional Check:
        - Check span consistency with layout
    - Action: If missing → flag

4.  Effective Depth:
    - Extract/calculate d
    - Compliance: Must align with cover + bar dia
    - Action: If not derivable → flag

5.  Clear Cover:
    - Extract values
    - Compliance:
        - 25mm (mild), 30mm (moderate)
    - Additional Check:
        - Cover should not be excessive (>75mm)
    - Action: If missing → flag

6.  Main Tension Reinforcement (Bottom):
    - Extract bars, dia, spacing
    - Compliance:
        - Min steel = 0.85bd/fy
        - Max steel = 4% of bD
        - Minimum 2 bars continuous
    - Additional Check:
        - Check anchorage into supports
    - Action: If missing → flag

7.  Compression Reinforcement (Top at Midspan):
    - Extract details
    - Compliance:
        - ≥ 2 bars (≥12mm)
    - Additional Check:
        - Required for doubly reinforced beams
    - Action: If missing → flag

8.  Top Reinforcement at Supports:
    - Check hogging reinforcement
    - Compliance: Mandatory for continuous beams
    - Additional Check:
        - Check proper anchorage length
    - Action: If missing → flag

9.  Shear Reinforcement (Stirrups):
    - Extract dia, spacing, type
    - Compliance:
        - Max spacing = 0.75d or 300mm
        - Min dia = 8mm
    - Additional Check:
        - Closer spacing near supports (within 2d)
        - Check shear capacity vs demand if data available
    - Action: If missing → flag
    
10. Lap Length:
    - Extract value
    - Compliance: ≥ 50d
    - Additional Check:
        - Avoid lap in high stress regions
        - Stagger laps
    - Action: If missing → flag

11. Development Length (Ld):
    - Extract value
    - Compliance: As per IS 456 Cl. 26.2
    - Additional Check:
        - Ld beyond support face
    - Action: If missing → flag

12. Deflection Check:
    - Check L/d limits
    - Additional Check:
        - Include modification factors
    - Action: If insufficient data → flag

13. Beam Schedule:
    - Verify consistency
    - Additional Check:
        - Check beam IDs (B1, B2, etc.)
    - Action: If missing → flag

14. Seismic Zone and Wind Load:
    - Extract values
    - Compliance: IS 1893 + IS 875
    - Action: If missing → flag

15. Seismic Detailing:
    - Check IS 13920 provisions
    - Additional Check:
        - Closely spaced stirrups at joints
        - Continuous bars
    - Action: If missing → flag

16. Side Face Reinforcement:
    - For D > 750mm
    - Compliance:
        - ≥ 0.1% web area
    - Action: If missing → flag


17. Torsion Reinforcement:
    - Check if torsion exists
    - Compliance: IS 456 Cl. 41
    - Additional Check:
        - Closed stirrups + longitudinal bars
    - Action: If missing → flag

18. Bar Curtailment:
    - Check extension rules
    - Compliance:
        - Extend ≥ Ld or d or 12ϕ
    - Additional Check:
        - At least 1/3 bars into support
    - Action: If missing → flag

19. Bearing at Supports:
    - Extract bearing length
    - Compliance:
        - ≥ 200mm (typical)
    - Additional Check:
        - Check load transfer adequacy
    - Action: If missing → flag

20. Shear Check (NEW):
    - Verify shear capacity vs demand
    - Compliance: IS 456 Cl. 40
    - Action: If not addressed → flag

21. Moment Capacity Check (NEW):
    - Check Mu vs capacity
    - Action: If not verifiable → flag

22. Crack Control (NEW):
    - Check spacing limits for crack control
    - Action: If ignored → flag

23. Anchorage & Hook Details (NEW):
    - Check bends/hooks (90°, 135°)
    - Compliance: SP 34
    - Action: If missing → flag

24. Load Path (NEW):
    - Verify load transfer (slab → beam → column)
    - Action: If unclear → flag
    
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

COLUMN_EXTRACTION_PROMPT = """
You are an expert assistant specializing in Indian civil engineering standards for RCC design (IS 456:2000, SP 34, IS 13920).

Your task is to perform a **FULL DATA EXTRACTION + COMPLIANCE CHECK** of an RCC COLUMN structural drawing.

⚠️ IMPORTANT:
- Do NOT miss ANY detail.
- Scan EVERY part of the drawing: column layout, schedules, sections, notes, callouts, symbols, bar marks.
- Extract EVEN repetitive or small values.
- If multiple columns exist → treat EACH column separately.

──────────────────────────────────────────────

### Step 0: Initial Document Check

- 0.1: Confirm drawing contains COLUMN details:
  (layout / schedule / reinforcement / cross-section)
  If not → "Not a valid column drawing"

- 0.2: Extract SITE LOCATION (mandatory for exposure condition)
  If missing → flag "Missing Information"

- 0.3: Confirm checks ONLY based on IS 456:2000, SP 34, IS 13920

- 0.4: Identify:
  - Units (mm/m)
  - Scale
  - Drawing type (layout / schedule / section)

- 0.5: Identify for EACH column:
  - Short / Long column
  - Axial / Eccentric loading
  - Interior / Edge / Corner column

──────────────────────────────────────────────

### Step 1: Locate "NOTES"

- Extract ONLY STRUCTURAL NOTES (ignore general notes)
- If missing → flag

──────────────────────────────────────────────

### Step 2: FULL EXTRACTION (VERY IMPORTANT)

For EACH column (C1, C2, etc.), extract:

#### 2.1 Geometry
- Column ID
- Location (grid reference)
- Shape (rectangular / circular)
- Dimensions (b × D)
- Height / storey level
- Effective length (Le)

#### 2.2 Material Properties
- Concrete grade (M20, M25...)
- Steel grade (Fe 415, Fe 500...)

#### 2.3 Longitudinal Reinforcement
- Number of bars
- Bar diameter (e.g., 12mm, 16mm)
- Total steel area
- % reinforcement
- Bar arrangement (corner, face, circular)

#### 2.4 Lateral Reinforcement (Ties / Stirrups)
- Tie diameter
- Spacing (zone-wise if varying)
- Confinement zones (near joints)
- Special seismic ties (if any)

#### 2.5 Reinforcement Detailing
- Lap length (location + value)
- Development length (Ld)
- Anchorage details
- Hook angles (90°, 135°)

#### 2.6 Column-Footing Connection
- Dowel bars
- Anchorage into footing
- Starter bars

#### 2.7 Loads
- Axial load (Pu)
- Moment (Mu) if given
- Load combinations

#### 2.8 Slenderness & Stability
- Slenderness ratio (Le/D)
- Buckling consideration

#### 2.9 Spacing & Clearances
- Clear cover
- Clear spacing between bars

#### 2.10 Seismic Detailing
- Confinement reinforcement
- Tie spacing reduction near joints
- IS 13920 compliance

#### 2.11 Fire / Durability
- Cover requirements
- Exposure condition

#### 2.12 Column Schedule
- Cross-check schedule vs drawing

──────────────────────────────────────────────

### Step 3: COMPLIANCE CHECK (IS 456 + SP 34)

| Criteria | Extracted Value | Compliance Check | Status |
|---|---|---|---|

1. Grade of Concrete → ≥ M20  
2. Grade of Steel → Fe 500 preferred  
3. Column Dimensions → ≥ 200 mm  
4. Effective Length → required  
5. Slenderness Ratio → ≤ 12 (short column)  
6. Clear Cover → ≥ 40 mm  
7. Longitudinal Reinforcement → 0.8%–6%  
8. Minimum Bars → 4 (rectangular), 6 (circular)  
9. Bar Diameter → ≥ 12 mm  
10. Lateral Ties → spacing limits satisfied  
11. Tie Configuration → closed ties + hooks  
12. Development Length → IS 456 compliant  
13. Lap Length → ≥ 50d  
14. Bar Spacing → ≥ max(25mm, dia)  
15. Column-Footing Connection → proper anchorage  
16. Load Data → available / missing  
17. Seismic Detailing → IS 13920  
18. Minimum Eccentricity → ≥ L/500 + D/30  
19. Buckling Check → if slender  
20. Column Schedule → consistent  

──────────────────────────────────────────────

### Step 4: CROSS-CHECK LOGIC (IMPORTANT)

Perform internal consistency checks:

- % steel = (Ast / Ag) → must be 0.8%–6%
- Tie spacing ≤ min(least dim, 16ϕ, 300mm)
- Cover + bar dia + spacing ≤ column size
- Lap locations staggered
- Schedule matches section

Flag inconsistencies.

──────────────────────────────────────────────

### Step 5: Output Format

### Step 0: Initial Document Check
- **0.1:** ...
- **0.2:** ...
- **0.3:** ...

### Step 1: NOTES
- **Status:** ...

### Step 2: Extracted Column Data

(List EACH column separately like:)
- Column C1:
  - Dimensions:
  - Reinforcement:
  - Ties:
  - Cover:
  - Loads:

### Step 3: Compliance Table

| Criteria | Extracted Value | Compliance Check | Status |

### Step 4: Missing / Wrong Information
1. ...
2. ...
3. ...

### Step 5: Summary
- Total Criteria Evaluated:
- Compliant:
- Non-Compliant:
- Missing:
- Overall Verdict:

⚠️ RULE:
If more than 50% data missing → NOT a valid column drawing
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
    "column": COLUMN_EXTRACTION_PROMPT,
}