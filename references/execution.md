# References and scripts

The prompt is the default. Add a reference only for text a typical run skips; add a script only when the model must not do the step.

## Reference

Put text in `references/<name>.md` only when a typical run skips it and a condition can say when to read it. Keep text every run needs in `SKILL.md`, however long. One condition per reference; name that condition in the pointer.

## Script

Add a script only when the model must not do the step itself:

- determinism, including order that must be enforced or steps that must not be skipped;
- state that must persist across runs;
- an external action the model cannot perform.

The script belongs to this skill. The prompt says when to run it and what to do with the result. No generic stage engine or workflow template.

## Ordered steps

Write steps inline in the prompt. If order must be enforced, that is a determinism reason for a script.
