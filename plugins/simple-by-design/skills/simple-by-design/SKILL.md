---
name: simple-by-design
description: Design a solution through focused CLI-routed prompts.
disable-model-invocation: true
---

Set `S` to this skill's absolute directory. From the project:

```sh
python3 "$S/scripts/sbd.py" --request '<request, constraints, permissions>'
```

Bare invocation resumes. Do the prompt; submit via its command. Repeat until `DONE`. If blocked, obtain the answer and pause. At `DONE`, stop; await approval before implementing.
