# AGENTS.md

This repository is the Textcast Agent Skill. Keep this file to rules that apply to almost every change.

## Who owns what

- [SKILL.md](SKILL.md) owns what an agent does when it runs the Skill: the workflow, hard rules, commands and paths.
- [references/ir-schema.md](references/ir-schema.md) owns the `ir.json` / `enrich.json` data contract.
- [README.md](README.md) owns what users read: install, features, requirements.
- The reading window is a separate project, [textcast-chat-axi](https://github.com/veardk/textcast-chat-axi). Its CLI help owns how to use the window; SKILL.md only says when to open it.
- When behaviour changes, update the owner in the same change.

## Conventions

- Python ≥ 3.10, standard library only. Node ≥ 22 for the channel fetch scripts, with no npm dependencies.
- Output paths are relative to the folder the Skill runs in (`./textcast/output/`), never the skill folder. Scripts create it.
- Never commit `output/` or personal cookies and credentials.
- Before committing, run a real ingest → publish on a short source and open the page.
- A release bumps `version` in `.claude-plugin/plugin.json`, then tags `v<version>` and creates a GitHub Release. Plugin installs only update when that version changes.
- Commit and PR titles follow Conventional Commits (`feat:`, `fix:`, `docs:`, `chore:`); PRs are squash-merged under their title.
