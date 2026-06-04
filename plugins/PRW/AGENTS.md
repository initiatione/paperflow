# Paper Research Wiki Agent Shell

This plugin exposes one user-facing paper wiki assistant: `paper-research-wiki`.
It also ships the supporting language gate `paper-wiki-language` for formal page prose.

Users should be able to ask for coarse actions such as directly depositing EPI papers, checking the wiki library, updating the wiki library, or relinking paper knowledge. Do not ask users to choose internal workflow names.

For every task:

1. Read `skills/paper-research-wiki/SKILL.md`.
2. Route the request to extract, check, or update.
3. Resolve the target vault contract before formal writes.
4. Treat EPI `_epi/` artifacts as evidence inputs, not formal wiki pages.
5. Before drafting, rewriting, or materially repairing formal pages, read `skills/paper-wiki-language/SKILL.md` and apply it throughout writing.
