# Workflow MW Troubleshooting (Architetture fino a 4+0 XPIC)

Questo workflow documenta il modulo di diagnostica massiva e bidirezionale (Local vs Remote) delle tratte radio ZTE. L'analisi aggrega automaticamente tutti i link (es. Modem 7 e 8, AIR 1 e 2) legati a due apparati di terminazione comunicanti.

## Requisiti

Assicurati di avere installato le dipendenze:
```bash
pip install pandas openpyxl matplotlib python-pptx
```

## Uso Standalone (CLI)

```bash
python WorkflowMWTroubleshootingZTE.py <percorso_file_excel>
```

**Esempio:**
```bash
python WorkflowMWTroubleshootingZTE.py "Performance Management-History Query-LIVORNO.xlsx"
```

> **Nota:** Lo script identifica automaticamente il sito locale e il remoto ordinando gli IP per valore numerico: il sito con IP più basso viene trattato come **Sito Locale**, quello con IP più alto come **Sito Remoto**. Non è necessario specificare il nome del sito.

## Come funziona lo script

1. **Topologia Dinamica:** Legge l'Excel e individua i due siti della tratta tramite ordinamento numerico degli indirizzi IP presenti nella colonna `ME IP`.
2. **Detection Architettura:** Se tra i modem del sito locale è presente un checkpoint con `"AIR:2"`, lo script riconosce automaticamente l'architettura **4+0 XPIC**; altrimenti assume una **2+0**.
3. **Calcolo Downshift (pre-processing):** Prima di generare grafici e statistiche, calcola la colonna `Sub-Max Mod Time(s)` per ogni modem — i secondi totali trascorsi a modulazione inferiore alla massima (downshift).
4. **Generazione Analisi Bipolare:**
   - **Lato Locale:** Produce grafici temporali per RSL, XPI, MSE e Downshift di Modulazione.
   - **Lato Remoto:** Estrapola gli stessi grafici per il sito ricevente.
5. **Analisi Algoritmica (Conclusioni Visive):**
   - Calcola statistiche per ogni modem: ES totali, Min RSL, Min MSE, Min XPI, Tot Downshift.
   - Genera una presentazione PPTX: `"Troubleshooting_<Local>_vs_<Remote>.pptx"`.
   - Sull'ultima diapositiva redige una proposta tecnica indicando su quale sito e modem intervenire, distinguendo tra problemi RSL (climatici/ambientali) e problemi di pura decodifica (Hardware/Interferenza).

## Logica Conclusioni Tecniche

| Condizione | Esito | Causa dedotta |
|---|---|---|
| ES > 0 e RSL < -65 dBm | FALLIMENTO COLLAUDO | Attenuazione climatica/ambientale |
| ES > 0 e RSL nominale | FALLIMENTO COLLAUDO | Problema Hardware / Interferenza |
| ES = 0 ma XPI < 25 dB o Downshift > 0 e RSL < -65 dBm | PREOCCUPAZIONE QUALITATIVA | Fisiologico da clima — nessun intervento HW |
| ES = 0 ma XPI < 25 dB o Downshift > 0 e RSL nominale | PREOCCUPAZIONE QUALITATIVA | Interferenza / cavo Mod-ODU difettoso |
| ES = 0 e nessuna anomalia | SUPERATO | Tratta stabile e conforme |

---

## Integrazione con Alarm Manager

Lo script è integrato come modulo nell'applicazione **MW Alarm Manager**. Il sistema mantiene uno storico persistente dei dati PM.

### Architettura

```
File PM ZTE (upload) → DATI/pm_history.parquet → GET /api/performance/{site}
                                                        ↓
                                             WorkflowMWTroubleshootingZTE.analyze_and_return()
                                                        ↓
                                             Grafici base64 + Stats + Conclusione → Frontend
```

### Flusso operativo

1. **Caricamento storico:** Dalla schermata principale dell'Alarm Manager, sezione "Performance MW", caricare il file Excel PM ZTE storico. I dati vengono salvati in `DATI/pm_history.parquet`.
2. **Aggiornamento giornaliero:** Caricare il nuovo file PM ogni giorno. Il sistema aggiunge i nuovi record senza duplicati (dedup su `ME + PM Checkpoint + Begin Time`).
3. **Analisi per sito:** Nella vista **Confronto Link Radio** (apertura dal click sul sito nella tabella allarmi), il tab **"📊 Performance MW"** carica automaticamente l'analisi per il sito selezionato interrogando il Parquet storico.

### Funzione `analyze_and_return()`

```python
from WorkflowMWTroubleshootingZTE import analyze_and_return

# df = DataFrame già letto da pm_history.parquet (filtrato per sito)
result = analyze_and_return(df, site_name_filter="CIGLITBV-PRZT-001")

# result contiene:
# {
#   "local_site": str, "remote_site": str, "arch": str,
#   "stats_local": [...], "stats_remote": [...],
#   "conclusion": [str, str, str, str],
#   "outcome": "SUPERATO" | "FALLIMENTO" | "PREOCCUPAZIONE",
#   "charts": {
#     "local":  { "rsl_trend": "<base64>", "xpi_trend": "...", ... },
#     "remote": { ... }
#   }
# }
```
