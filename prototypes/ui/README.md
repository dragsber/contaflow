# ContaFlow UI-1 — prototipo indipendente

**Questo non è ContaFlow in produzione.** Il prototipo usa solo un archivio sintetico creato in una \`TemporaryDirectory\`, poi letto con SQLite \`mode=ro\` e \`PRAGMA query_only=ON\`. Non apre \`%LOCALAPPDATA%\ContaFlow\`, non modifica l'applicazione o il suo database.

## Avvio su Windows 11 / Python 3.12

Dalla radice del repository (con Python 3.12 installato):

\`\`\`cmd
py -3.12 -m prototypes.ui.run --tema nativo
\`\`\`

Per confrontare i temi esterni, crea un **venv separato** solo per il prototipo:

\`\`\`cmd
py -3.12 -m venv prototypes\ui\.venv-ui1
prototypes\ui\.venv-ui1\Scripts\python.exe -m pip install -r prototypes\ui\requirements-prototype.txt
prototypes\ui\.venv-ui1\Scripts\python.exe -m prototypes.ui.run --tema ttkbootstrap
prototypes\ui\.venv-ui1\Scripts\python.exe -m prototypes.ui.run --tema sv-ttk
\`\`\`

La modalità nativa non richiede pacchetti esterni. Non installare le librerie nella Python di produzione: sono esclusivamente opzioni del prototipo.

## Confronto guidato

1. Apri Panoramica e individua saldo EUR e CHF: non vanno mai sommati; saldo calcolato, variazione netta e saldo riconciliato sono etichette distinte.
2. Entra in Movimenti e individua un movimento "In attesa" o "Proposto"; verifica dettagli, ricerca, filtri collassabili, "N di M" e "Azzera filtri".
3. Verifica leggibilità e interazioni a 900×620, 1120×760, massimizzata e, se possibile, scaling Windows 125% e 150%.
4. Prova ognuno dei tre temi sullo stesso layout. Le restanti tre aree sono segnaposto dichiarati; le azioni di importazione e modifica multipla non operano.

## Test

\`\`\`cmd
py -3.12 -m unittest prototypes.ui.test_presentation -v
py -3.12 -m unittest discover -s tests -v
\`\`\`

I sei test puri sono eseguibili senza display. Le prove del campione su SQLite e della GUI su Windows richiedono un ambiente con il repository completo. **La modalità di esecuzione non modifica alcun dato personale.**

## Licenze e versioni verificate su PyPI (2026-11-06)

| Pacchetto | Versione fissata per il prototipo | Licenza e Python | Fonte |
|---|---|---|---|
| ttkbootstrap | 2.2.7 | MIT AND (Apache-2.0 OR BSD-2-Clause), Python ≥3.10 | https://pypi.org/project/ttkbootstrap/2.2.7/ |
| sv-ttk | 2.6.1 | MIT, Python ≥3.9 (classifier 3.12) | https://pypi.org/project/sv-ttk/2.6.1/ |
| Pillow | 12.1.0 | licenza permissiva Pillow/HPND; classificatore Python 3.12 | https://pypi.org/project/pillow/12.1.0/ |

\`ttkbootstrap\` dichiara Pillow come dipendenza. Non è stato effettuato il collaudo delle dipendenze transitive o la verifica delle dimensioni e delle licenze del bundle Windows. **Nessuna di queste dipendenze è stata aggiunta all'EXE ContaFlow.**

## Perimetro

I moduli in \`prototypes/ui/\` non sono importati dal pacchetto principale e non sono inclusi nel comando di build Windows dell'app. Il prototipo richiama i servizi esistenti solo per creare e leggere il campione temporaneo. Non include funzionalità di scrittura, import reali, migrazioni dell'utente o riclassificazioni. La decisione su UI-2 resta all'utente.
