# ContaFlow · Alpha 0.2 — build intermedia

Ultimo commit precedente all'incremento corrente: 46a797e5dde97379d9eb5143cddfb5bc0ac6ea48.
L'incremento corrente è identificato dal commit che contiene questo file.
Branch codex/contaflow-sviluppo. Fase attiva A completata, prossimo incremento B.

## Funzioni e verifiche

- Registro operativo nella GUI con filtri combinabili per conto, testo, date ISO, categoria,
  fornitore e stato. Pulsante Da classificare, ordinamento su ogni colonna, dettaglio originale,
  legenda testuale e colori, scroll su entrambi gli assi, importi italiani tramite Decimal.
- Eliminato il limite precedente di 100 movimenti dal percorso FinanceService.
- Sprint A verificato con 3 test automatici su Windows, inclusi widget Tk reali e 150 movimenti.
- Baseline 46a797e preservata. In sessione precedente 25 test passati su Windows,
  collaudo manuale Alpha 0.1 dichiarato dall'utente.
- EXE Alpha 0.2 non prodotto. Collaudo manuale della nuova GUI pendente.
- Git CLI indisponibile per scaricamento (errore DNS). Sorgenti letti e commit pubblicati
  mediante connessione GitHub, con controllo HEAD e aggiornamento fast-forward.

## Roadmap

Percentuali stimate di copertura del prodotto, distinte dai risultati dei test.
I nomi seguono la roadmap del master prompt Alpha 0.2.

| Fase | Architettura | Operativa GUI | Collaudata |
|---|---:|---:|---|
| 01 App Windows | 85% | 80% | Registro A automatico Windows |
| 02 Import bancario | 65% | 60% | Baseline Alpha 0.1 |
| 03 Conti e saldi iniziali | 40% | 20% | Baseline parziale |
| 04 Contabilità e trasferimenti | 10% | 0% | Pendente |
| 05 Esportazioni | 0% | 0% | Pendente |
| 06 Fornitori e categorie | 60% | 60% | Baseline Alpha 0.1 |
| 07 Ricorrenze | 0% | 0% | Pendente |
| 08 Budget | 10% | 0% | Pendente |
| 09 Dashboard | 40% | 40% | Baseline Alpha 0.1 |
| 10 AI locale | 0% | 0% | Non valutata |
| 11 Google Sheets | 5% | 0% | Pendente |
| 12 Distribuzione | 30% | 10% | Portable 0.1 manuale utente |

## Lavori aperti

B audit, modifica e classificazione multipla. C completamento anagrafiche.
D anteprima obbligatoria e annullamento lotti. E trasferimenti/rimborsi. F budget.
Prima di introdurre colonne nuove, rendere sicura la migrazione con backup automatico
verificato, transazioni e diagnostica di errore. Nessuna migrazione nello sprint A.
BPER/PDF/XLSX predisposti come ambiti futuri, parser non collaudati.

Gli importi SQLite REAL esistenti restano compatibili. Nuovi calcoli usano Decimal.
Una futura migrazione verso importi esatti richiederà strategia e test dedicati,
senza conversione massiva in questa versione.
