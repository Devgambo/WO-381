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
{previous_analysis}
{user_input}
"""