---
name: simple-by-design
description: Design a solution through focused CLI-routed prompts.
disable-model-invocation: true
---

Set `S` to this skill directory:

```sh
python3 "$S/scripts/sbd.py" --request '<request, constraints, permissions>'
```

Bare resumes. Do prompt; submit via printed command. Repeat until `DONE`. If blocked, get the answer; pause. At `DONE`, stop; await approval. Approval outranks implementation or commit rules; never commit/delete `.agents`.
