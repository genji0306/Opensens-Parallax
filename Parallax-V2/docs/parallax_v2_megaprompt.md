# Parallax V2 – Claude Code Mega Prompt

You are Claude Code acting as the lead product architect, workflow designer, and full-stack engineer for Parallax V2.

Your task is to redesign and implement Parallax V2 as a robust, resumable, research workflow platform for paper development, literature intelligence, scientific review, drafting, and experiment planning.

---

## 1. PRODUCT GOAL

Build Parallax V2 as a serious “AI research lab” platform with two major surfaces:

### Paper Lab
- Literature search  
- Topic mapping  
- Debate / review / validation  
- Idea generation  
- Drafting  
- Experiment design / data planning  
- Revision and pass/fail scoring  

### Command Center
- Project creation  
- Project history  
- Restart/resume from any step  
- Project monitoring  
- Per-step advanced settings  
- Visibility into outputs, papers, maps, and intermediate artifacts  

---

## 2. CORE PROBLEM

Current system is too linear. V2 must be a **graph-based, checkpointed workflow engine**.

### Correct Protocol Structure

```
Search ---> Map
             | \
             |  \-> Debate ---> Validate
             |
             \----> Ideas -----> Draft -----> Experiment design/data -----> Revise -----> Pass (if high score)
                                           (if needed / possible)
```

---

## 3. KEY IMPROVEMENTS

### A. Model Selection
Support:
- Claude Haiku
- Claude Sonnet
- Claude Opus
- ChatGPT Codex (or equivalent)

Requirements:
- Per-step model selection
- Project-level defaults
- Model provenance tracking

---

### B. Deep Review System

Introduce **specialist review agents**:
- Electrochemistry
- EIS / CV / DPV / SWV
- Spectroscopy
- Materials science
- Statistics
- ML methodology
- Energy systems

Must detect:
- Missing controls
- Weak baselines
- Invalid interpretation
- Reproducibility risks

---

### C. Multimodal Capability

Current limitation: cannot process figures/graphs.

Required:
- Vision-capable API integration
- Extract captions, axes, legends
- Link figures to claims
- Fallback for text-only mode
- Future-ready architecture

---

## 4. COMMAND CENTER FIXES

### Critical Issues

- Fix new project bugs  
- Enable old project continuation  
- Add schema migration  

### Restart Capability

- Restart from ANY step  
- Preserve checkpoints  
- Warn dependency invalidation  

---

### Literature Search

Fix:
- Show paper list (not just count)

Include:
- Title, authors, year
- Abstract
- Relevance score
- Selection control

---

### Topic Mapping

Fix:
- Make nodes clickable  

Show:
- Cluster summary  
- Key papers  
- Contradictions  
- Novelty opportunities  

---

### Advanced Settings

Per-step config:
- Model selection  
- Token depth  
- Evidence size  
- Review strictness  
- Novelty threshold  
- Experiment requirement  

---

## 5. DRAFT STAGE (CRITICAL)

Draft must include:

### Experiment Design Agent
- Identify missing evidence  
- Suggest experiments  
- Define controls and calibration  
- Generate lab procedures  
- Accept real data input  
- Feed into revision  

---

## 6. ARCHITECTURE

### Workflow Engine
Each node:
- id
- type
- config
- inputs
- outputs
- status
- score
- timestamps
- model used

### Persistence
- Schema versioning  
- Migration support  
- Checkpoints  

### Artifacts
- Papers  
- Maps  
- Debate logs  
- Drafts  
- Experiments  
- Scores  

---

## 7. UX REQUIREMENTS

### Project Page
- Show graph state  
- Restart options  
- Outputs per node  
- Model visibility  

### Map View
- Interactive  
- Drill-down  
- Export to Ideas  

### Draft View
- Version history  
- Weakness tracking  
- Experiment linkage  

---

## 8. IMPLEMENTATION PLAN

### Step 1
- Refactor workflow into graph engine  

### Step 2
- Fix project creation + migration  

### Step 3
- Enable restart from any step  

### Step 4
- Add paper list UI  

### Step 5
- Interactive topic map  

### Step 6
- Advanced settings  

### Step 7
- Specialist review  

### Step 8
- Experiment integration  

### Step 9
- Multimodal layer  

---

## 9. ACCEPTANCE CRITERIA

System is valid ONLY IF:

- Old + new projects resume  
- Restart from any step  
- Graph-based workflow  
- Paper list visible  
- Topic map interactive  
- Advanced settings exist  
- Model selection works  
- Deep review works  
- Draft includes experiment design  
- Multimodal path exists  

---

## FINAL NOTE

Parallax V2 must behave like a **real scientific workflow system**, not a UI wrapper around LLM calls.
