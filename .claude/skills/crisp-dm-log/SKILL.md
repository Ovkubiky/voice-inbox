---
name: crisp-dm-log
description: Append a decision/finding to report/crisp_dm_log.md under the correct CRISP-DM phase. Use after any design decision, dataset change, eval result, abandoned approach, or scope cut.
---

# CRISP-DM log entry

Append to `report/crisp_dm_log.md` under the matching `## <Phase>` heading
(Business Understanding · Data Understanding · Data Preparation · Modeling · Evaluation · Deployment):

```
- **<short title>**: <what was decided/found>. *Why:* <reason>. *Evidence:* <metric, file, or command>.
```

Rules:
- One to three lines per entry, facts only, with numbers where they exist.
- Abandoned approaches and scope cuts **are** entries (they show iteration in the report).
- Never include content from `data/private/`.
- Don't rewrite old entries. If something changed, add a new entry that references the old one.
