import json
import base64
import io
import matplotlib.pyplot as plt
import re
from typing import Dict, Any, Optional

from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from app.core.dependencies import get_llm

DIAGRAM_PLANNER_PROMPT = """
I am working on an academic diagram task: given the 'Methodology' section of a paper, and the caption of the desired figure, automatically generate a detailed description of an illustrative diagram.
Methodology: {content}
Visual Intent / Caption: {intent}

Your description should be extremely detailed. Describe each element and their connections. Formally, include various details such as background style, layout, elements, etc.
Do not include figure titles. Provide ONLY the detailed description.
"""

DIAGRAM_STYLIST_PROMPT = """
You are a Lead Visual Designer for top-tier AI conferences (e.g., NeurIPS).
You are provided with a preliminary description of a diagram:
Detailed Description: {description}
Methodology Context: {content}

Refine and enrich this description based on professional aesthetic guidelines. Ensure it is publication-ready.
1. Preserve Semantic Content - do not alter the logic.
2. Enrich Details - specify exact colors, line styles, layout adjustments, typography.
Output ONLY the final polished Detailed Description.
"""

PLOT_PLANNER_PROMPT = """
I am working on an academic plotting task: given raw data and a visual intent, generate a detailed description of a statistical plot.
Raw Data: {content}
Visual Intent / Caption: {intent}

Explain the precise mapping of variables (x, y, hue) and enumerate the raw data points to be drawn. Specify aesthetic parameters like colors and markers. Output ONLY the description.
"""

PLOT_STYLIST_PROMPT = """
You are a Lead Visual Designer for top-tier academic conferences.
Preliminary plot description:
{description}

Refine and enrich this description to ensure publication-ready aesthetics. Specify visual attributes (colors, fonts, line styles). Do not alter semantic content or quantitative results.
Output ONLY the final polished Detailed Description.
"""

PLOT_VISUALIZER_PROMPT = """You are an expert statistical plot illustrator.
Use Python matplotlib to generate a statistical plot based on the following detailed description:
{description}

Output ONLY the executable python code wrapped in ```python ... ``` block. Do not include any explanations. The code MUST NOT call plt.show(), it should just prepare the figure.
"""

async def _execute_plot_code(code_text: str) -> Optional[str]:
    match = re.search(r"```python(.*?)```", code_text, re.DOTALL)
    code_clean = match.group(1).strip() if match else code_text.strip()

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.close("all")
    plt.rcdefaults()

    try:
        exec_globals = {}
        exec(code_clean, exec_globals)
        if plt.get_fignums():
            buf = io.BytesIO()
            plt.savefig(buf, format="jpeg", bbox_inches="tight", dpi=300)
            plt.close("all")
            buf.seek(0)
            img_bytes = buf.read()
            return base64.b64encode(img_bytes).decode("utf-8")
        return None
    except Exception as e:
        print(f"[PaperBanana] Plot visualization failed: {e}")
        return None

async def generate_paperbanana_illustration(
    content: str,
    intent: str,
    task_type: str = "diagram",
) -> Dict[str, Any]:
    """
    Executes the lightweight PaperBanana Agentic Pipeline (Planner -> Stylist -> Visualizer)
    """
    # Force gemini-2.5-pro for high quality generation
    llm = get_llm(model="gemini-2.5-pro")
    
    if task_type == "diagram":
        # 1. Planner Agent
        planner_chain = PromptTemplate.from_template(DIAGRAM_PLANNER_PROMPT) | llm | StrOutputParser()
        description = await planner_chain.ainvoke({"content": content, "intent": intent})
        
        # 2. Stylist Agent
        stylist_chain = PromptTemplate.from_template(DIAGRAM_STYLIST_PROMPT) | llm | StrOutputParser()
        polished_desc = await stylist_chain.ainvoke({"description": description, "content": content})
        
        # As we cannot directly hit Imagen here securely without specific API auth,
        # we will fallback to requesting the LLM to output Mermaid code based on the polished description for diagrams
        visualizer_chain = PromptTemplate.from_template(
            "Based on this polished description: {desc}\nProduce an advanced Mermaid.js flowchart or architecture diagram that faithfully represents it. Output ONLY the raw mermaid code wrapped in ```mermaid ... ```."
        ) | llm | StrOutputParser()
        
        viz_code = await visualizer_chain.ainvoke({"desc": polished_desc})
        match = re.search(r"```mermaid(.*?)```", viz_code, re.DOTALL)
        final_code = match.group(1).strip() if match else viz_code.strip()
        
        return {
            "task_type": "diagram",
            "planner_output": description,
            "stylist_output": polished_desc,
            "visualizer_output": final_code,
            "format": "mermaid"
        }

    else:
        # Task type: Plot
        # 1. Planner Agent
        planner_chain = PromptTemplate.from_template(PLOT_PLANNER_PROMPT) | llm | StrOutputParser()
        description = await planner_chain.ainvoke({"content": content, "intent": intent})
        
        # 2. Stylist Agent
        stylist_chain = PromptTemplate.from_template(PLOT_STYLIST_PROMPT) | llm | StrOutputParser()
        polished_desc = await stylist_chain.ainvoke({"description": description})
        
        # 3. Visualizer Agent (Code Gen)
        visualizer_chain = PromptTemplate.from_template(PLOT_VISUALIZER_PROMPT) | llm | StrOutputParser()
        plot_code = await visualizer_chain.ainvoke({"description": polished_desc})
        
        # 4. Executor
        base64_jpg = await _execute_plot_code(plot_code)
        
        return {
            "task_type": "plot",
            "planner_output": description,
            "stylist_output": polished_desc,
            "visualizer_output": base64_jpg,
            "code": plot_code,
            "format": "base64_jpg" if base64_jpg else "error"
        }
