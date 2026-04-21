# CDI Water Treatment Process Design — Vietnamese Seafood Processing Factory

## Research Question

Design and specify a Capacitive Deionization (CDI) based water treatment process
to reduce total dissolved solids (TDS) from ~1000 mg/L to ≤100 mg/L for process
and discharge water at a seafood processing facility in Vietnam.

## Context & Constraints

- **Location:** Vietnam (Mekong Delta / central coastal processing cluster —
  tropical climate, 25–35 °C ambient, high humidity, frequent brownouts).
- **Source water:** Blend of municipal supply, shallow groundwater, and
  brackish intrusion (dry-season Cl⁻ spikes). Seasonal TDS swings 500–1500 mg/L.
- **Target:** Permeate ≤100 mg/L TDS, suitable for cleaning-in-place (CIP),
  ice-making, product rinse, or discharge to QCVN 11-MT:2015/BTNMT Column A.
- **Feed matrix caveats:** Seafood process streams carry residual NaCl,
  NH₄⁺/NO₃⁻ from protein breakdown, fats/oils (FOG), fine solids, and microbial
  load. Raw seafood wastewater is usually far >1000 mg/L — this brief targets
  the post-DAF / post-MBR polishing stream that enters CDI at ~1000 mg/L.
- **Plant scale:** Design points at 10, 50, and 200 m³/day.
- **Economics:** CAPEX + OPEX (kWh/m³, electrode life, cleaning chemistry) must
  beat a comparable RO polishing train at Vietnamese electricity tariffs
  (~0.09 USD/kWh industrial) with VN tropical fouling realities.

## What the Pipeline Must Produce

1. **Feasibility map** — CDI vs MCDI vs HCDI vs RO for this TDS window and
   matrix; recovery, specific energy (Wh/L-removed), salt-adsorption capacity
   expectations.
2. **Pretreatment train** — ultrafiltration / activated carbon / antiscalant
   selection tuned to seafood-derived FOG, proteins, and biofouling risk.
3. **CDI stack sizing** — electrode material choice (activated carbon cloth,
   carbon aerogel, MXene-composite), cell geometry, flow rate, charge/discharge
   cycle time to hit ≤100 mg/L at target throughput.
4. **Control strategy** — constant-current vs constant-voltage operation,
   energy recovery, regeneration frequency, CIP protocol.
5. **Monitoring** — inline conductivity, ORP, turbidity, TOC; alarm logic for
   electrode degradation and biofouling breakthrough.
6. **Risk register** — fouling, electrode oxidation, brine disposal, power
   reliability, operator skill gap in rural Vietnam.
7. **Deliverable** — PFD, mass balance, energy balance, and a
   build-vs-buy recommendation (local fabrication vs imported skid).

## Known Tensions to Surface

- CDI's sweet spot is 500–3000 mg/L — this sits inside it, but organic fouling
  from seafood streams is the dominant failure mode, not ionic breakthrough.
- ≤100 mg/L from 1000 mg/L is ~90% TDS removal in one pass — feasible with
  MCDI (membrane CDI) but marginal for conventional CDI without staging.
- Tropical biofouling + intermittent grid = uptime and control design matter
  more than nominal electrode capacity.

## Deliverable Format

Structured exploration: hypothesis → supporting evidence → design sketch →
quantitative sizing → residual risks. Cite mechanisms and numeric anchors; call
out where assumptions need empirical validation.
