# Instructions

## description

- User-only (default): `disable-model-invocation: true`; one-line purpose, e.g. `description: Create or revise an agent skill.` No details.
- Model-invoked (only when clear or the user asks): `disable-model-invocation: false`;

## SKILL.md body

What every run needs. Numbered steps only when order matters.

## Leaf pointer

`Read references/<leaf> when <condition>.` One condition per leaf.

## Stage prompt

One objective. Name the inputs it uses, the done condition, and the output the next stage needs. Looping stage: state its limit and what happens at it.

## Core

Design for behavioral change, not prose quality. Define an observable pass condition; Write the bare minimum instructions to pass.
Prefer implicit intent. The agent will already apply standard practices, common practices, and best practices.
