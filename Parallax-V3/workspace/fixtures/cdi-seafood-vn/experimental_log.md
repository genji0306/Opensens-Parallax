# Experimental Log Seed — CDI for Seafood Factory Polishing (Vietnam)

No laboratory data collected yet. This is a green-field design run; the pipeline
should treat all quantitative targets as design specs to be bracketed from
literature and CDI theory, not as measured values.

## Assumed Operating Envelope (to be validated)

| Parameter                | Feed (post-pretreatment) | Target permeate       |
|--------------------------|--------------------------|-----------------------|
| TDS                      | ~1000 mg/L (500–1500)    | ≤100 mg/L             |
| Conductivity             | ~1.8 mS/cm               | ≤0.2 mS/cm            |
| Na⁺ / Cl⁻ dominant       | yes (brackish intrusion) | —                     |
| NH₄⁺                     | 10–40 mg/L               | <5 mg/L               |
| TOC                      | 3–8 mg/L                 | <2 mg/L               |
| Turbidity                | <1 NTU (post-UF)         | <0.5 NTU              |
| Temperature              | 28–34 °C                 | —                     |
| pH                       | 6.8–7.8                  | 6.5–8.5               |
| Throughput design points | 10 / 50 / 200 m³/day     | same recovery         |

## Open Questions for the Pipeline

1. Which electrode system gives the best Wh per gram of salt removed at
   1000 → 100 mg/L in a tropical 30 °C, biofouling-heavy matrix?
2. Is single-stage MCDI sufficient, or is a two-stage CDI → MCDI polishing
   train justified by energy and recovery math?
3. What pretreatment kills the organic fouling problem cheaply given local
   supply chains (Vietnamese UF skid vendors, activated carbon sources)?
4. How should brine / concentrate be handled — reuse in salt-brine workflows
   (ice, curing) or discharge to QCVN limits?
5. What is the expected electrode lifetime under this duty cycle, and what
   CIP chemistry (citric, NaOH, NaClO at what doses) is safe for the electrode
   binder and spacer materials?
