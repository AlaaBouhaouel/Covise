---
name: skill
description: Template for creating a new skill. Use this as a starting point.
user-invocable: false
---

# Skill Template

Replace this file with your skill's instructions.

Frontmatter options:
- `name` — slash command name (e.g. `/name`)
- `description` — when Claude should auto-invoke this skill
- `disable-model-invocation: true` — only runs when you type `/name`
- `allowed-tools` — tools allowed without permission prompts (e.g. `Read, Grep, Bash`)
- `context: fork` — runs in an isolated subagent
- `user-invocable: false` — hides from slash command menu (Claude reference only)

Arguments: use `$ARGUMENTS` or `$ARGUMENTS[0]` in the body.
