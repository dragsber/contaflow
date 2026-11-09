# Playbook ContaFlow

I playbook sono procedure riusabili per attività ricorrenti. Restano bozze finché non vengono approvati; non contengono i vincoli permanenti del progetto, che si richiamano da [`AGENTS.md`](../AGENTS.md).

## Procedura

1. **Intervista:** raccogliere dall'utente obiettivo, input, scelte e casi dubbi.
2. **File riusabili:** identificare file, modelli e riferimenti autorizzati da riutilizzare.
3. **Definizione di finito:** concordare controlli osservabili e condizioni di completamento.
4. **Correzione del playbook:** dopo errori o cambi di istruzioni aggiornare la procedura, non limitarsi a correggere la singola chat.

**Ogni errore si corregge nel playbook** corrispondente, così non si ripete nelle sessioni successive.

## Collegamento a Codex

La documentazione ufficiale descrive le skills di progetto in `.agents/skills/<nome>/SKILL.md` ([skills per repository](https://developers.openai.com/blog/skills-agents-sdk)); `AGENTS.md` è caricato dalle directory del repository ([guida Codex](https://developers.openai.com/cookbook/examples/gpt-5/codex_prompting_guide)). `playbooks/` è l'archivio canonico, non una cartella skills rilevata automaticamente. Quando un playbook è approvato, renderlo scopribile aggiungendo in `.agents/skills/<nome>/SKILL.md` un breve wrapper con `name` e `description` che rimandi al relativo `playbooks/<nome>/SKILL.md`. Le bozze non si collegano.
