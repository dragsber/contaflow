# Stato sviluppo ContaFlow

- Ultimo commit: 08d90664a0a4b4742549bab773d3c34fc50fc07c.
- Fase attiva: sprint architetturale, incrementi 1 e 2.
- Architettura: FinanceService collegato alla GUI; models Account/Movement; adapters non configurati per Sheets, Enable Banking e AI locale.
- Schema v2: fornitori, alias univoci, regole, categorie estese, vista movimenti compatibile, trasferimenti, rimborsi, budget, importazioni, saldi iniziali.
- Incremento 1 collaudo: migrazione sintetica DB legacy superata, conserva i movimenti e può essere ripetuta. Suite completa non eseguita.
- Incremento 2: FinanceService gestisce ora elenchi/creazione/archiviazione categorie e anagrafiche/alias fornitori. Compilazione sintattica del servizio superata.
- GUI operativa: conti, movimenti filtrati e importazione CSV Revolut. Sezioni fornitori/categorie e altre GUI integrate ancora da realizzare.
- Collaudi mancanti: test funzionali dei metodi FinanceService, test applicazione end-to-end e GUI Windows.
- Prossimo incremento: classificatore confermato → alias → regola → proposta → attesa, con riuso delle associazioni.
- Avanzamento stimato fasi 01-12: 01 75%, 02 55%, 03 30%, 04 10%, 05 0%, 06 10%, 07 0%, 08 0%, 09 10%, 10 0%, 11 0%, 12 0%.
