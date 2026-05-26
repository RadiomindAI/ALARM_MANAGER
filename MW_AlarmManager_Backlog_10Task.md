# MW Alarm Manager — Backlog Prioritizzato (10 Task)

> Backlog tecnico ordinato per impatto operativo, rischio e dipendenze.
> Ogni task include: descrizione, motivazione, file coinvolti, effort stimato, criteri di completamento (DoD).

---

## Metodo di Prioritizzazione

Le task sono ordinate secondo una combinazione di tre fattori:

- **Impatto** — quanto migliora stabilità, sicurezza o manutenibilità del sistema
- **Rischio** — quanto riduce vulnerabilità o probabilità di regressione
- **Dipendenza** — se sblocca task successive o può essere eseguita subito

La regola di base: prima si consolidano le fondamenta (config, sicurezza, test), poi si refactoring l'architettura, poi si aggiungono nuove capacità.

---

## Task 1 — Centralizzare configurazione e soglie tecniche

**Priorità: CRITICA — fare subito**

**Descrizione:** Creare `config/settings.py` (Pydantic Settings) e `config/thresholds.yml`.
Eliminare tutti i path hardcodati (`BACKEND_DIR`, `DATA_DIR`, `DATI_DIR`) e tutte le
costanti tecniche inline (`RSL < -63`, `XPI < 20`, `FILTERABILITY_THRESHOLD = 0.85`, ecc.)
che oggi sono sparsi in `main.py`, `core/classifier.py`, `core/ingestion.py`,
`core/pmingestion.py` e `WorkflowMWTroubleshootingZTE.py`.

**Motivazione:** Calibrare una soglia tecnica richiede oggi di cercare in 4-5 file diversi
e modificare codice sorgente. Con `thresholds.yml` basta editare un file YAML e riavviare.
Inoltre `settings.py` elimina i path relativi fragili e permette di configurare deploy
diversi (dev/staging/prod) senza toccare il codice.

**File coinvolti:**
- NUOVI: `backend/config/settings.py`, `backend/config/thresholds.yml`
- MODIFICATI: `main.py`, `core/classifier.py`, `core/ingestion.py`,
  `core/pmingestion.py`, `WorkflowMWTroubleshootingZTE.py`

**Effort:** 1-2 giorni

**DoD (Definition of Done):**
- [ ] Tutti i path assoluti derivano da `settings.base_dir`
- [ ] Tutte le soglie PM/FM sono in `thresholds.yml`
- [ ] L'app si avvia senza errori su path diversi
- [ ] `.env.example` documentato con tutte le variabili supportate

---

## Task 2 — Sicurezza e robustezza degli upload file

**Priorità: ALTA — fare subito**

**Descrizione:** Creare `utils/files.py` con `safe_save()` e `cleanup_upload()`.
Sostituire il salvataggio diretto con `file.filename` in `uploads/` con nome
randomizzato UUID, controllo dimensione (50 MB max), validazione MIME effettiva
(non solo estensione) e cleanup automatico del file temporaneo dopo l'elaborazione.

**Motivazione:** Attualmente un file con nome come `../../etc/passwd.xlsx` potrebbe
in linea teorica causare path traversal. Il nome originale viene usato per il path
senza sanificazione. Inoltre i file non vengono mai cancellati dalla cartella `uploads/`,
che cresce indefinitamente in produzione.

**File coinvolti:**
- NUOVO: `utils/files.py`
- MODIFICATO: `main.py` (endpoint `/api/upload` e `/api/upload-performance`)

**Effort:** 0.5 giorni

**DoD:**
- [ ] Nomi file sempre UUID + estensione
- [ ] Rifiuto file > 50 MB con HTTP 413
- [ ] File temporanei eliminati dopo elaborazione (anche in caso di errore)
- [ ] Test manuale con file malformato, file troppo grande, file con nome sospetto

---

## Task 3 — Suite test automatici sul dominio critico

**Priorità: ALTA**

**Descrizione:** Creare `tests/` con almeno 5 file di test che coprono le funzioni
più critiche del sistema. Usare `pytest` con `pytest-cov` per coverage.

**Test da scrivere:**

1. `test_alarm_rules.py` — classificazione allarmi: CRITICAL → ESCALATE, override operatore,
   allarme cronico, allarme nuovo, allarme strutturale TOLERABLE
2. `test_pm_rules.py` — `compute_downshift_column`, `analyze_site_stats`,
   `build_conclusions` sui 5 scenari della matrice diagnostica
3. `test_topology.py` — `autodetect_sites` con IP contigui, `autodetect_sites`
   con un solo sito, pairing via subnet fallback
4. `test_parquet_repo.py` — append con dedup, append su file non esistente,
   `filter_by_site`, `get_status`
5. `test_api_alarms.py` — upload file valido, upload file senza colonne, upload vuoto
   (TestClient FastAPI)

**Motivazione:** le funzioni di classificazione e diagnostica PM sono il cuore del
valore del tool. Oggi una modifica a `build_conclusions` o `classify_single_alarm`
non ha nessuna protezione da regressione. Con la suite, ogni PR è verificabile.

**File coinvolti:**
- NUOVI: `tests/__init__.py`, `tests/test_alarm_rules.py`, `tests/test_pm_rules.py`,
  `tests/test_topology.py`, `tests/test_parquet_repo.py`, `tests/test_api_alarms.py`
- PREREQUISITO: Task 1 (le funzioni di dominio devono accettare thresholds come parametro)

**Effort:** 2-3 giorni

**DoD:**
- [ ] `pytest` passa senza errori
- [ ] Coverage ≥ 80% su `domain/` e `core/classifier.py`
- [ ] I test girano senza connessione di rete e senza file reali
- [ ] CI-ready: un singolo `pytest tests/` basta per verificare tutto

---

## Task 4 — Consolidare `loadjson`/`savejson` e `ParquetRepository`

**Priorità: MEDIA-ALTA**

**Descrizione:** Creare `repositories/json_repo.py` e `repositories/parquet_repo.py`
come da refactoring file-per-file. Sostituire le implementazioni duplicate
(presenti in `main.py` e implicitamente in vari moduli `core/`).

**Motivazione:** `loadjson`/`savejson` con FileLock sono implementati almeno due volte.
La logica Parquet (dedup, append, lock) è duplicata tra `ingestion.py` e `pmingestion.py`
con piccole differenze che nel tempo divergono. Un repository unico garantisce
comportamento coerente e un solo punto di fix quando ci sono problemi di lock.

**File coinvolti:**
- NUOVI: `repositories/json_repo.py`, `repositories/parquet_repo.py`
- MODIFICATI: `main.py`, `core/ingestion.py`, `core/pmingestion.py`, `core/classifier.py`

**Effort:** 1 giorno

**DoD:**
- [ ] Zero implementazioni duplicate di `loadjson`/`savejson`
- [ ] `ParquetRepository` usato sia per allarmi FM che per PM
- [ ] Tutti i test di Task 3 ancora verdi dopo la migrazione

---

## Task 5 — Spezzare `main.py` in router FastAPI separati

**Priorità: MEDIA**

**Descrizione:** Creare i router `api/alarms.py`, `api/performance.py`, `api/kb.py`,
`api/predictive.py`, `api/session.py`, `api/audit.py`. Spostare gli endpoint
nei router corrispondenti. Il `main.py` finale deve essere ≤ 60 righe.

**Motivazione:** `main.py` attualmente è il file più difficile da leggere, modificare
e fare review. Con i router, ogni area funzionale ha il suo file e ogni sviluppatore
può lavorare su un'area senza conflitti di merge con le altre.

**File coinvolti:**
- NUOVI: `api/__init__.py`, `api/alarms.py`, `api/performance.py`, `api/kb.py`,
  `api/predictive.py`, `api/session.py`, `api/audit.py`
- MODIFICATO: `main.py` (drasticamente ridotto)
- PREREQUISITO: Task 1 (settings), Task 4 (repositories)

**Effort:** 1-2 giorni

**DoD:**
- [ ] `main.py` ≤ 60 righe
- [ ] Tutti gli endpoint esistenti rispondono identicamente (nessuna breaking change)
- [ ] Test API di Task 3 ancora verdi
- [ ] Swagger `/docs` mostra tutti gli endpoint organizzati per tag

---

## Task 6 — Creare `services/` e svuotare la logica applicativa dagli endpoint

**Priorità: MEDIA**

**Descrizione:** Creare `services/alarm_service.py`, `services/pm_service.py`,
`services/kb_service.py`. Spostare la logica di orchestrazione
(upload → parse → classify → persist → return) dagli endpoint ai service.
Gli endpoint diventano chiamate a una sola funzione del service.

**Motivazione:** Oggi se vuoi capire cosa fa `/api/upload` devi leggere ~80 righe
di endpoint inline. Con un service, l'endpoint è 5 righe e la logica è testabile
separatamente da FastAPI.

**File coinvolti:**
- NUOVI: `services/alarm_service.py`, `services/pm_service.py`, `services/kb_service.py`
- MODIFICATI: `api/alarms.py`, `api/performance.py`, `api/kb.py`
- PREREQUISITI: Task 4, Task 5

**Effort:** 2 giorni

**DoD:**
- [ ] Ogni endpoint ha ≤ 10 righe di corpo
- [ ] I service sono istanziabili e testabili senza FastAPI TestClient
- [ ] Nessuna logica di business negli endpoint

---

## Task 7 — Rimuovere `importlib.reload` dall'endpoint performance

**Priorità: MEDIA**

**Descrizione:** L'endpoint `GET /api/performance/{site_name}` fa attualmente
`importlib.reload(WorkflowMWTroubleshootingZTE)` ad ogni chiamata per forzare il
ricaricamento del modulo. Questo è un workaround rischioso (non thread-safe,
lento, causa reload globale del modulo Python).

**Soluzione:** creare `services/troubleshooting_service.py` che importa
`WorkflowMWTroubleshootingZTE` una volta all'avvio e espone `analyze_and_return`
come metodo di istanza. Il modulo non deve mai essere ricaricato a runtime.

**File coinvolti:**
- NUOVO: `services/troubleshooting_service.py`
- MODIFICATO: `api/performance.py`

**Effort:** 0.5 giorni

**DoD:**
- [ ] Zero `importlib.reload` nel codebase
- [ ] L'analisi di performance ritorna risultati corretti su chiamate multiple
- [ ] Nessuna race condition in caso di chiamate concorrenti

---

## Task 8 — Migliorare error handling e feedback nel frontend

**Priorità: MEDIA**

**Descrizione:** Sostituire tutti gli `alert()` del frontend con un sistema di toast/notifiche
inline. Aggiungere stati di errore espliciti per: upload fallito, analisi PM non disponibile,
KB non generata, sessione scaduta. Migliorare i messaggi d'errore che arrivano dal backend
(oggi spesso generici come "Errore interno").

**Motivazione:** in un contesto operativo di rete, l'operatore lavora sotto pressione.
Un `alert()` blocca l'interfaccia e spezza il flusso. Un toast in basso a destra informa
senza interrompere. I messaggi d'errore devono essere azionabili: non "Errore 500"
ma "File PM non trovato — carica prima un file dalla sezione Performance".

**File coinvolti:**
- FRONTEND: `frontend.jsx` (rimozione `alert`, aggiunta toast component)
- BACKEND: endpoint con messaggi di errore più descrittivi

**Effort:** 1-2 giorni

**DoD:**
- [ ] Zero `alert()` nel codebase frontend
- [ ] Ogni errore API ha un messaggio leggibile e un'azione suggerita
- [ ] Errori di upload mostrano quale file ha fallito e perché
- [ ] Toast scompaiono automaticamente dopo 5 secondi (con possibilità di chiusura manuale)

---

## Task 9 — Logging strutturato e metriche operative

**Priorità: MEDIA-BASSA**

**Descrizione:** Sostituire il `logging.basicConfig` con una configurazione strutturata
(JSON log o almeno log con campi fissi: `timestamp`, `level`, `module`, `event`, `duration_ms`).
Aggiungere timing automatico sugli endpoint più lenti (upload, analisi PM, rebuild KB).
Considerare l'aggiunta di un endpoint `/api/metrics` con contatori base.

**Motivazione:** in produzione, quando qualcosa va storto alle 2:00 di notte e il rebuild
KB fallisce silenziosamente, serve un log strutturato che permetta di capire cosa è successo.
Il logging attuale è sufficiente per debug locale, non per monitoring remoto.

**File coinvolti:**
- NUOVO: `utils/logging_config.py`
- MODIFICATI: `main.py`, `core/ingestion.py`, `core/pmingestion.py`, service layer

**Effort:** 1 giorno

**DoD:**
- [ ] Log in formato JSON (o struttura equivalente parsabile da ELK/Loki)
- [ ] Ogni endpoint logga: metodo, path, status_code, duration_ms
- [ ] Rebuild KB logga: durata totale, record elaborati, errori
- [ ] Nessun `print()` nel codebase di produzione (solo in script standalone CLI)

---

## Task 10 — Documentazione operativa e README di produzione

**Priorità: BASSA — ma utile prima del deploy su altri ambienti**

**Descrizione:** Creare documentazione operativa in `docs/`:
- `docs/DEPLOY.md` — come deployare su Render, Docker, macchina locale Windows
- `docs/OPERATIONS.md` — come aggiornare i file PM, quando fare rebuild KB, come
  interpretare i badge di stato, cosa fare quando il wizard riappare
- `docs/THRESHOLDS.md` — spiegazione di ogni soglia in `thresholds.yml`,
  come calibrarla, casi d'uso tipici
- Aggiornare `README.md` principale con architettura aggiornata e quickstart

**Motivazione:** oggi l'unica documentazione è il codice stesso e qualche commento.
Se un nuovo operatore o un tecnico di rete deve usare il tool, non ha un punto di
partenza. La documentazione operativa riduce le domande ripetitive e permette al tool
di essere usato in autonomia.

**File coinvolti:**
- NUOVI: `docs/DEPLOY.md`, `docs/OPERATIONS.md`, `docs/THRESHOLDS.md`
- MODIFICATO: `README.md`

**Effort:** 1-2 giorni

**DoD:**
- [ ] Un tecnico che non ha visto il codice riesce a deployare il sistema seguendo `DEPLOY.md`
- [ ] Un operatore di rete capisce come usare il tool leggendo `OPERATIONS.md`
- [ ] Tutte le soglie in `thresholds.yml` hanno una spiegazione tecnica in `THRESHOLDS.md`
- [ ] README aggiornato con screenshot e link alle docs

---

## Riepilogo e Timeline

| # | Task | Priorità | Effort | Prerequisiti |
|---|------|----------|--------|--------------|
| 1 | Config centralizzata + soglie YAML | 🔴 Critica | 1-2 gg | — |
| 2 | Sicurezza upload (UUID, size limit, cleanup) | 🔴 Alta | 0.5 gg | — |
| 3 | Suite test automatici dominio critico | 🔴 Alta | 2-3 gg | Task 1 |
| 4 | Repository JSON e Parquet unificati | 🟠 Media-Alta | 1 gg | — |
| 5 | Split `main.py` in router FastAPI | 🟠 Media | 1-2 gg | Task 1, 4 |
| 6 | Services layer (logica fuori dagli endpoint) | 🟠 Media | 2 gg | Task 4, 5 |
| 7 | Rimuovere `importlib.reload` da performance | 🟠 Media | 0.5 gg | Task 5 |
| 8 | Error handling e toast frontend | 🟡 Media | 1-2 gg | — |
| 9 | Logging strutturato e metriche | 🟡 Media-Bassa | 1 gg | Task 5 |
| 10 | Documentazione operativa | 🟢 Bassa | 1-2 gg | — |

**Effort totale stimato: 11-18 giorni lavorativi** distribuibili in 5-6 sprint da 3 giorni.

**Ordine consigliato se hai poco tempo:** Task 1 → Task 2 → Task 3.
Queste tre task da sole portano il progetto da "funziona" a "è sicuro e testato",
senza toccare l'architettura. Tutto il resto è miglioramento progressivo.

---

*Fine documento backlog*
