# Sincronizzazione casa / ufficio

Prima installazione: `git clone https://github.com/dragsber/ContaFlow.git`, poi `git switch codex/contaflow-sviluppo`.

Prima di lavorare: `git fetch origin` e `git pull --ff-only`.

Avvio: installare Python 3 con Tkinter e lanciare `python -m contaflow`.

Dopo modifiche verificate: `git add` solo file di codice/documentazione, `git commit -m "Descrizione"`, `git push`. Sull'altra postazione fare fetch e pull --ff-only. In caso di conflitto, fermarsi e riconciliare manualmente; non usare force push.

Il database resta sotto `%LOCALAPPDATA%\ContaFlow`; non sincronizzarlo tramite GitHub.
