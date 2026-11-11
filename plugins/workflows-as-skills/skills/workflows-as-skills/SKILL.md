---
name: workflows-as-skills
description: Design and publish an explicitly invoked agent skill whose workflow shape earns its cost. Decide and challenge delegation criteria, cognitive boundaries, verification loops, stop rules, approval gates and engine need; instruction prose belongs to semantic-instructions.
disable-model-invocation: true
---
# Workflows as skills

Set `S` to this skill's absolute directory; from the task project run `python3 "$S/scripts/skillflow.py" --root . --request '<verbatim request>'`, then follow each printed prompt and submit JSON through its printed command. Design and stage only in the printed staging directory; never edit engine state or publish manually.
