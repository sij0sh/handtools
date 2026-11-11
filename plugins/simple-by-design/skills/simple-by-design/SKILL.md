---
name: simple-by-design
description: Design a solution through focused CLI-routed prompts.
disable-model-invocation: true
---

Set `S` to this skill directory:

```sh
python3 "$S/scripts/sbd.py" --request '<request, constraints, permissions>'
```

Omit arguments to resume. Follow each prompt and submit using its printed command. Repeat until `DONE`. If blocked, obtain the missing answer and pause. At `DONE`, stop for approval;
