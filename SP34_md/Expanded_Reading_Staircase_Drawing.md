# RCC Design and Drawing Interpretation --- Staircase

## Step 1: Locate the "NOTES" section

(Sometimes labeled as *STAIRCASE DETAILS*, *RCC NOTES*, or *GENERAL
SPECIFICATIONS*).\
If missing, request the architect or structural consultant to provide
this data.

------------------------------------------------------------------------

## Step 2: Identify the Type of Staircase

Before reading reinforcement or geometry, determine the structural type:

-   **Dog-legged Staircase** --- Two flights in opposite directions with
    a common landing.\
-   **Open-well Staircase** --- Two flights separated by an open space
    or well.\
-   **Quarter-turn / Half-turn Staircase** --- Flights change direction
    by 90° or 180°.\
-   **Spiral Staircase** --- Circular plan with central support.\
-   **Cantilever Staircase** --- Steps projecting from a wall or central
    spine beam.

Understanding the type helps identify load paths and reinforcement
layout.

------------------------------------------------------------------------

## Step 3: Preliminary Design Data and Verification

### Material Data

-   **Grade of Concrete:** M20 or M25 (IS 456:2000, Cl. 5.3.1).\
-   **Reinforcement Steel:** Fe415/Fe500 (IS 1786:2008).

### Load Data

-   **Self-weight:** Depends on waist slab thickness (typically 150--200
    mm).\
-   **Floor finish load:** 1.0 kN/m² (typical).\
-   **Live load:** 3--5 kN/m² for residential/institutional use. (IS 875
    Part 2).\
-   **Handrail load:** Consider additional 0.3 kN/m along railing edge.

### Stair Geometry

-   **Rise (R):** 150--175 mm\
-   **Tread (T):** 250--300 mm\
-   **Waist thickness (t):** 150--200 mm\
-   **Flight angle (θ):** θ = tan⁻¹(R/T)

Ensure that:

    No. of Risers × Rise + Landing Thickness = Floor-to-Floor Height

------------------------------------------------------------------------

## Step 4: Structural Classification

-   **Waist Slab Type:** Reinforced slab spanning between supports (most
    common).\
-   **Beam Supported:** Slab supported on edge beams or walls.\
-   **Cantilever Type:** One edge fixed into a wall or beam.\
-   **Slabless Type:** Stringer beam carries steps individually.

Identify supports (wall, beam, column) and check in drawing whether
reinforcement extends into these supports adequately.

------------------------------------------------------------------------

## Step 5: Load Calculation for Design Verification

### 1. **Self-weight of Waist Slab**

    w₁ = t × γ × cosθ

Where: - *t* = thickness of waist slab (m)\
- *γ* = density of RCC (25 kN/m³)\
- *θ* = angle of staircase to horizontal

### 2. **Weight of Steps**

    w₂ = (Rise × Tread × γ) / (Tread projection)

Approx. 1.0 to 1.2 kN/m² additional.

### 3. **Live Load (w₃):**

As per IS 875 Part 2 --- 3 kN/m² (residential), 5 kN/m² (public).

### 4. **Total Load:**

    w_total = (w₁ + w₂ + w₃)

Factored load = 1.5 × (DL + LL)

------------------------------------------------------------------------

## Step 6: Bending Moment and Shear Check

For a simply supported waist slab:

    M = wL² / 8
    V = wL / 2

Where *L* = inclined length of stair flight.

Check design moment and shear against permissible limits:\
- IS 456:2000, Cl. 40 (Shear)\
- Cl. 22.3 (Flexural strength)

Ensure reinforcement layout matches moment direction --- main bars along
the slope.

------------------------------------------------------------------------

## Step 7: Reinforcement Detailing and Verification

### Main Reinforcement (Tension Steel)

-   Placed parallel to the slope, extending into landings.\
-   Minimum area: 0.12% of cross-section (IS 456:2000, Cl. 26.5.2.1).\
-   Anchorage length ≥ Development Length (Ld).

### Distribution Reinforcement

-   Placed perpendicular to the main bars.\
-   Spacing ≤ 200 mm c/c.

### Lap Length and Anchorage

-   Lap ≥ 50 × bar dia (IS SP 34).\
-   Bars must be properly bent or hooked into beams or landings.

### Clear Cover

-   Minimum 25 mm for moderate exposure (IS 456:2000, Table 16).

### Continuity Over Landing

-   Reinforcement must continue through landings if monolithic.\
-   If landing is supported on a beam, anchorage should extend into the
    beam.

------------------------------------------------------------------------

## Step 8: Deflection and Crack Control

-   **Span-to-depth ratio:** ≤ IS 456 Table 2 limits (typically 20 for
    simply supported).\
-   **Crack width:** ≤ 0.3 mm (IS 456 Cl. 35.3.2).\
-   Proper bar spacing and adequate cover ensure serviceability.

------------------------------------------------------------------------

## Step 9: Centering and Formwork

-   Proper slope, alignment, and rise must be maintained.\
-   Formwork should be watertight and well-braced.\
-   Shuttering below landing should be designed for concentrated load
    transfer.\
-   Check for bulging or sagging before pouring concrete.

------------------------------------------------------------------------

## Step 10: Construction and Curing

-   Maintain geometry of treads and risers accurately.\
-   Reinforcement must not shift during concreting.\
-   Minimum curing period:
    -   7 days (OPC)\
    -   10 days (blended cement).\
        (IS 456:2000, Cl. 13.5.1)

------------------------------------------------------------------------

## Step 11: Finishing and Safety

-   Provide a 1:60 outward slope on treads for drainage.\
-   Non-slip finish for safety.\
-   Railing embedment should not disturb main reinforcement.\
-   Verify smoothness and line alignment along stair flight.

------------------------------------------------------------------------

## Step 12: Detailing Verification Checklist

  **Criteria**           **Requirement / Reference**    **Remarks**
  ---------------------- ------------------------------ -------------
  Concrete Grade         M20 (Min) per IS 456:2000      
  Steel Grade            Fe415 / Fe500 (IS 1786:2008)   
  Clear Cover            25 mm                          
  Main Bar Dia           10--12 mm typical              
  Distribution Bar Dia   8--10 mm                       
  Bar Spacing            ≤ 200 mm c/c                   
  Waist Thickness        150--200 mm                    
  Rise & Tread           150--175 mm / 250--300 mm      
  Live Load              3--5 kN/m²                     
  Anchorage              Ld ≥ 50Φ                       
  Lap Length             ≥ 50Φ (SP 34)                  
  Deflection Limit       Span/250                       
  Crack Width            ≤ 0.3 mm                       

------------------------------------------------------------------------

## Step 13: Common Errors to Check in Drawings

-   Missing development length at supports.\
-   Improper bar bending at landing junction.\
-   Steps not aligned to waist slab slope.\
-   Reinforcement discontinuity between flight and landing.\
-   Insufficient cover at riser--tread junction.\
-   Lack of railing anchorage detail.

------------------------------------------------------------------------

## Step 14: Missing or Wrong Information

List any missing data from drawing or site information under:

**"Missing or Wrong Information according to compliance check."**\
(Example: Concrete grade not mentioned, unclear support type, or missing
reinforcement continuity.)

------------------------------------------------------------------------

**References:**\
- IS 456:2000 --- Plain and Reinforced Concrete --- Code of Practice\
- IS 875 (Part 2):1987 --- Imposed Loads on Buildings\
- IS SP 34: Handbook on Concrete Reinforcement Detailing\
- SP 16: Design Aids for Reinforced Concrete
