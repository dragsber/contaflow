# Codex development protocol
Fetch origin at session start, inspect status and branch, and synchronize only with fast-forward. Never force-push, reset hard, or overwrite user files. Keep financial exports, databases, credentials, tokens, logs and backups out of Git. Use synthetic tests. After verified changes, commit and push to `codex/contaflow-sviluppo`; never merge to main without explicit instruction.

Before work listed in `playbooks/INDEX.md`, read and follow its `SKILL.md` only when its state is `approvato`. If it is `bozza` or `da creare`, do not apply it and report that status.
