# RCC Design and Drawing Interpretation --- Beam

## Step 1: Locate the "NOTES" section

(Sometimes labeled as *BEAM DETAILS*, *RCC NOTES*, or *STRUCTURAL
GENERAL NOTES*).\
If absent, request the consultant or architect for these details before
proceeding.

------------------------------------------------------------------------

## Step 2: Identify Beam Type and Layout

-   **Main (Primary) Beam:** Carries load from slabs and secondary
    beams.\
-   **Secondary Beam:** Transfers load to primary beam.\
-   **Lintel Beam:** Above openings (doors/windows).\
-   **Plinth Beam:** At plinth level to tie columns.\
-   **Cantilever Beam:** Projecting member fixed at one end.

Examine the plan, elevation, and section drawings to identify support
locations, beam spans, and load transfer patterns.

------------------------------------------------------------------------

## Step 3: Preliminary Design Data and Material Verification

-   **Grade of Concrete:** M20 or higher (IS 456:2000, Cl. 5.3.1).\
-   **Reinforcement Steel:** Fe415 or Fe500 (IS 1786:2008).\
-   **Load Transfer:** From slab → beam → column → footing.\
-   **Self-weight of Beam:** ( 25 × b × D ) kN/m (for unit width).

------------------------------------------------------------------------

## Step 4: Structural Classification

  Type                    Description
  ----------------------- --------------------------------------------
  Simply Supported Beam   Supported at both ends only
  Continuous Beam         Extends over more than two supports
  Cantilever Beam         Fixed at one end, free at other
  T-Beam                  Formed monolithically with slab
  L-Beam                  Edge beam supporting slab on one side only

Identify from drawing whether the beam acts as a **rectangular** or
**T-beam** section.\
If T-beam, verify flange thickness = slab thickness and effective flange
width as per IS 456:2000, Cl. 23.1.2.

------------------------------------------------------------------------

## Step 5: Load Estimation

### Dead Load (DL)

-   Self-weight of beam = 25 × b × D (kN/m).\
-   Include wall load (if wall rests on beam):\
    ( w = t × h × γ )\
    where t = wall thickness, h = height, γ = 20 kN/m³.

### Live Load (LL)

Transferred from slab or superimposed loads (as per IS 875 Part 2).

### Factored Load

    w_u = 1.5 × (DL + LL)

------------------------------------------------------------------------

## Step 6: Bending Moment and Shear Check

### Simply Supported Beam

    M = wL² / 8
    V = wL / 2

### Continuous Beam (approx.)

    M_mid = wL² / 12
    M_support = wL² / 10

Check design moments and shear forces per IS 456:2000, Cl. 40.\
Shear strength of concrete = τ_c (from IS 456 Table 19).

------------------------------------------------------------------------

## Step 7: Flexural Reinforcement Detailing

-   **Main (Tension) Bars:** Placed at the bottom in simply supported
    beams.\
-   **Top (Compression) Bars:** Placed at supports in continuous beams.\
-   **Curtailment:** Cut off bars at points where bending moment
    reduces, ensuring anchorage ≥ Ld beyond cutoff.\
-   **Minimum Steel Area:**\
    ( A\_{st,min} = 0.85bd / f_y ) for Fe415 (IS 456 Cl. 26.5.1.1).\
-   **Maximum Steel:** ≤ 4% of gross area.\
-   **Spacing:** ≤ 3d or 300 mm (whichever smaller).\
-   **Bar Diameter:** 12--25 mm typical for main reinforcement.

------------------------------------------------------------------------

## Step 8: Shear Reinforcement (Stirrups)

-   **Purpose:** To resist diagonal tension and hold longitudinal bars.\
-   **Minimum Shear Reinforcement:**\
    ( A\_{sv} / (b s) = 0.4 / f_y ) (IS 456 Cl. 26.5.1.6).\
-   **Spacing:** ≤ 0.75d or 300 mm (whichever smaller).\
-   **Stirrup Type:** 2-legged or 4-legged closed ties (8 mm typical).

------------------------------------------------------------------------

## Step 9: Anchorage and Development Length (Ld)

-   **Ld = (Φ × σ_s) / (4 × τ_bd)**\
    where Φ = bar dia, τ_bd = design bond stress (Table 26, IS 456).\
-   Extend bottom bars into supports by ≥ Ld.\
-   Hooks and bends must follow IS SP 34 detailing.

------------------------------------------------------------------------

## Step 10: Deflection and Crack Control

-   **Span-to-depth ratio:** 20 (simply supported), 26 (continuous).\
-   **Deflection limit:** ≤ span/250.\
-   **Crack width:** ≤ 0.3 mm (IS 456 Cl. 35.3.2).\
-   Ensure sufficient cover and bar spacing to control cracks.

------------------------------------------------------------------------

## Step 11: Clear Cover and Spacing

-   **Clear cover:**
    -   25 mm for slabs\
    -   30 mm for beams (IS 456 Table 16).\
-   **Minimum spacing between bars:** ≥ bar dia or 25 mm.

------------------------------------------------------------------------

## Step 12: Centering, Shuttering, and Construction Notes

-   Ensure shuttering is properly leveled, tight, and oiled before
    concreting.\
-   Check beam--column joint alignment before placing reinforcement.\
-   Provide proper spacers and chairs for maintaining cover.\
-   Curing: Minimum 7 days (OPC), 10 days (blended cement).

------------------------------------------------------------------------

## Step 13: Common Drawing or Site Errors

-   Missing negative reinforcement over supports.\
-   Insufficient anchorage into columns.\
-   Wrong bar placement (top vs bottom).\
-   Incorrect stirrup spacing near supports.\
-   Incomplete or inconsistent section labeling.

------------------------------------------------------------------------

## Step 14: Detailing Verification Checklist

  **Criteria**               **Requirement / Reference**   **Remarks**
  -------------------------- ----------------------------- -------------
  Concrete Grade             M20 (min)                     
  Steel Grade                Fe415 / Fe500                 
  Clear Cover                30 mm                         
  Main Bar Dia               12--25 mm                     
  Stirrup Dia                8 mm (min)                    
  Spacing                    ≤ 3d or 300 mm                
  Shear Reinforcement        As per IS 456 Cl. 26.5.1.6    
  Ld                         As per IS 456 Cl. 26.2.1      
  Max Deflection             Span/250                      
  Crack Width                ≤ 0.3 mm                      
  Top/Bottom Bar Anchorage   Proper per SP 34              

------------------------------------------------------------------------

## Step 15: Missing or Wrong Information

List missing data under:

**"Missing or Wrong Information according to compliance check."**\
Examples: Concrete grade not specified, bar spacing missing, support
conditions unclear.

------------------------------------------------------------------------

**References:**\
- IS 456:2000 --- Plain and Reinforced Concrete --- Code of Practice\
- IS 875 (Part 2):1987 --- Imposed Loads\
- IS SP 34: Handbook on Reinforcement Detailing\
- SP 16: Design Aids for Reinforced Concrete
