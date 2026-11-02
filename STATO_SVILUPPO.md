# Stato sviluppo ContaFlow

- Ultimo incremento verificato: migrazione schema v2, commit migration 308645f0aff61708c4dbed38954c6617eb45777c.
- Fase attiva: sprint architetturale, incremento 1 completato; incremento 2 da iniziare.
- Architettura: FinanceService è collegato alla GUI; models per Account e Movement; adattatori senza connessioni per Google Sheets, Enable Banking e AI locale.
- Schema v2: fornitori, alias univoci normalizzati, regole, categorie estese, movimenti tramite vista compatibile su transactions, trasferimenti, rimborsi, budget, importazioni, saldi iniziali e schema_version.
- Verifiche: migrazione sintetica da DB legacy superata, conserva la transazione esistente, vista movimenti leggibile e migrazione ripetibile. Suite completa e GUI Windows non eseguite.
- Operativo dalla GUI: conti, filtro movimenti e import CSV Revolut con riconciliazione e conteggi.
- Non ancora operativo dalla GUI: fornitori, categorie, trasferimenti, rimborsi, budget, impostazioni e dashboard integrata.
- Problemi aperti: servizi FinanceService ancora limitati a conti/movimenti/import; nessun saldo iniziale confermato.
- Prossimo incremento: estendere FinanceService per conti, fornitori, categorie, movimenti e importazioni, mantenendo la GUI senza SQL.
- Avanzamento stimato fasi 01-12: 01 75%, 02 55%, 03 30%, 04 10%, 05 0%, 06 0%, 07 0%, 08 0%, 09 10%, 10 0%, 11 0%, 12 0%.
