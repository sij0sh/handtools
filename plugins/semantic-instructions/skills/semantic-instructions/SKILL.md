---
name: semantic-instructions
description: Create, edit, review, or simplify instructions for AI agents, including prompts, SKILL.md, AGENTS.md, agent definitions, workflow stages, and evaluation instructions. Use when authoring or improving agent-facing instructions, not generic prose or code.
disable-model-invocation: true
---

Set `S` to this skill's absolute directory. From the task project run `python3 "$S/scripts/semantic_flow.py" --request '<request>'`; follow each printed prompt and submit JSON through its printed command. Bare invocation resumes. The engine routes Frame → Compose → Challenge; read [details](references/details.md) when prompted. Do not write before challenge passes.
