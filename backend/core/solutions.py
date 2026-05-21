"""
solutions.py
=============
Knowledge Base delle soluzioni suggerite per tipo di allarme.
Usata dal classifier per proporre azioni correttive all'operatore.
"""

# ── Dizionario soluzioni per tipo di allarme ──────────────────────────────────
# Chiave: stringa (o sottostringa) del nome allarme (case-insensitive match)
# Valore: lista di azioni suggerite (ordinate per priorità)

SOLUTIONS_KB = {
    # ── LINK RADIO / MODEM ─────────────────────────────────────────────────────
    "transmission unit link break": [
        "Verificare il livello RX sul NE remoto (Site B) via NMS",
        "Controllare eventuali ostruzioni fisiche sul percorso radio",
        "Verificare i parametri ATPC e ACM sul link",
        "Aprire ticket per intervento on-site se il link non si ripristina entro 30 min",
    ],
    "modem part unlock": [
        "Riavviare il modulo modem via NMS (soft reset)",
        "Verificare frequenza e polarizzazione configurata vs reale",
        "Controllare il livello RX: se <-80dBm, probabile causa interferenza",
        "Se persiste dopo reset, pianificare intervento on-site ODU",
    ],
    "uas alarm of radio": [
        "Controllare il livello RSL (Received Signal Level) sul link",
        "Verificare condizioni meteo (pioggia/nebbia intensi per frequenze >10GHz)",
        "Confrontare con il link speculare (Site A vs Site B)",
        "Se UAS >10 sec consecutivi, aprire ticket di degrado link",
    ],
    "mw_ber_exc": [
        "Verificare RSL e CINR sul link radio",
        "Controllare interferenze sulla frequenza",
        "Verificare parametri ACM: potrebbe essere necessario abbassare la modulazione",
        "Aprire ticket per analisi frequenza con gestore",
    ],
    "mw_ber_sd": [
        "Monitorare per 1 ora: se persiste aprire ticket",
        "Verificare RSL e confrontare con valori nominali",
        "Controllare allineamento antenna (potenziale micro-disallineamento)",
    ],
    "xpic function becomes invalid": [
        "Verificare stato delle due polarizzazioni H/V sul link XPIC",
        "Controllare che entrambi gli ODU siano allineati",
        "Verificare configurazione XPIC su entrambi i NE del link",
        "Reset XPIC via NMS se configurazione corretta",
    ],
    "xpi value is below threshold": [
        "Monitorare il valore XPI: soglia normale >25dB",
        "Verificare interferenza co-canale sulla frequenza",
        "Controllare allineamento antenna fine",
    ],
    "rdi alarm": [
        "Verificare lo stato del Site A (il problema è a monte)",
        "Controllare la continuità del segnale dal lato trasmittente",
        "Se Site A è OK, verificare il percorso di trasmissione intermedio",
    ],
    "fade margin value is below threshold": [
        "Controllare RSL attuale vs RSL nominale di progetto",
        "Verificare condizioni atmosferiche",
        "Se RSL degradato stabilmente, pianificare allineamento antenna",
    ],

    # ── ODU / RF ────────────────────────────────────────────────────────────────
    "odu alarm - rf unit tx rf pll unlocked": [
        "Eseguire hard reset dell'ODU via NMS",
        "Verificare alimentazione ODU (cavo IF/alimentazione DC)",
        "Se persiste dopo reset, pianificare sostituzione ODU",
    ],
    "odu alarm - rx rf input signal is too low": [
        "Verificare RSL sul link: probabilmente il Site B ha problemi TX",
        "Controllare stato ODU del NE remoto",
        "Verificare assenza ostruzioni fisiche o variazioni del percorso",
    ],
    "odu alarm - rf unit is mute": [
        "Verificare se il muting è stato imposto manualmente via NMS",
        "Controllare potenza TX configurata",
        "Se involontario, eseguire reset ODU",
    ],
    "odu alarm - rf unit power supply abnormal": [
        "Verificare tensione alimentazione DC sull'IDU",
        "Controllare cavo IF per corti circuiti o rotture",
        "Misurare tensione al connettore ODU (nominale: 24-48V DC)",
    ],
    "odu alarm - rf unit is rebooting": [
        "Monitorare: se riavvio ripetuto indica problema HW",
        "Verificare alimentazione stabile",
        "Pianificare sostituzione se riavvii > 3 in 1 ora",
    ],
    "odu alarm - rf unit communication is interrupted": [
        "Verificare cavo IF tra IDU e ODU",
        "Controllare connettori (umidità, ossidazione)",
        "Eseguire test di continuità del cavo IF",
    ],

    # ── CLOCK / SINCRONIZZAZIONE ────────────────────────────────────────────────
    "clock pll can not lock": [
        "Verificare la sorgente di clock configurata (PTP/BITS/interno)",
        "Controllare la catena di sincronizzazione a monte",
        "Verificare qualità del segnale PTP (packet loss, delay)",
        "Se nessuna sorgente disponibile, configurare holdover/free-run temporaneo",
    ],
    "ptp reference clock source unavailable": [
        "Verificare raggiungibilità del server PTP (ping dall'NE)",
        "Controllare la configurazione PTP (IP server, dominio)",
        "Verificare QoS sul percorso IP per i pacchetti PTP",
    ],
    "ptp clock link abnormal": [
        "Verificare l'interfaccia PTP: link UP/DOWN",
        "Controllare i parametri PTP: delay, offset, jitter",
        "Verificare che il grandmaster PTP sia operativo",
    ],
    "time synchronization is out of lock": [
        "Controllare tutte le sorgenti di sync disponibili",
        "Verificare il BMCA (Best Master Clock Algorithm) nella rete",
        "Monitorare per 30 min: se persiste aprire ticket sincronizzazione",
    ],
    "clock quality deteriorated": [
        "Verificare qualità del link di trasporto PTP",
        "Controllare se ci sono oscillazioni di ritardo nella rete IP",
        "Valutare sorgente di backup (BITS/GPS) se disponibile",
    ],
    "clock reference source lost": [
        "Verificare disponibilità sorgente primaria",
        "Attivare sorgente di backup se configurata",
        "Aprire ticket verso il fornitore della sorgente clock",
    ],

    # ── RETE / ETHERNET / IP ────────────────────────────────────────────────────
    "layer 2 protocols of an interface are in down status.": [
        "Verificare lo stato fisico della porta Ethernet",
        "Controllare la configurazione VLAN e STP",
        "Verificare che il dispositivo connesso sia operativo",
    ],
    "the physical port is down.": [
        "Verificare cavo/fibra sulla porta segnalata",
        "Controllare lo stato admin della porta (non in shutdown?)",
        "Verificare negoziazione velocità/duplex",
    ],
    "ipv4 protocol state of the interface is down.": [
        "Verificare la configurazione IP dell'interfaccia",
        "Controllare routing verso la destinazione",
        "Verificare che il layer 2 sia UP prima",
    ],
    "the ospf neighbor is down.": [
        "Verificare raggiungibilità IP del neighbor OSPF",
        "Controllare parametri OSPF (hello interval, area ID, auth)",
        "Verificare stato dell'interfaccia di collegamento",
    ],
    "the port is not receiving ethernet packets": [
        "Verificare il device connesso alla porta",
        "Controllare statistiche di traffico sulla porta",
        "Verificare eventuali storm-control o port-security attivi",
    ],
    "the link between the server and the ne is broken": [
        "Verificare raggiungibilità NMS → NE (ping)",
        "Controllare interfaccia di gestione sul NE",
        "Verificare firewall/ACL sul percorso di gestione",
        "Controllare se il NE è in manutenzione programmata",
    ],

    # ── ALIMENTAZIONE ───────────────────────────────────────────────────────────
    "the main power supply abnormal": [
        "Verificare alimentazione AC/DC al sito",
        "Controllare stato UPS se presente",
        "Aprire ticket urgente se il sito è senza alimentazione",
    ],
    "input voltage is out of the configured range": [
        "Misurare tensione di ingresso al rack",
        "Verificare stabilità della rete elettrica del sito",
        "Controllare configurazione soglie di tensione sull'NE",
    ],

    # ── TEMPERATURA ─────────────────────────────────────────────────────────────
    "the temperature exceeds the threshold.": [
        "Verificare il sistema di raffreddamento del sito",
        "Controllare se i filtri dell'aria sono ostruiti",
        "Verificare la temperatura ambiente del locale",
        "Se >70°C, pianificare intervento urgente per evitare spegnimento termico",
    ],

    # ── OTTICO ─────────────────────────────────────────────────────────────────
    "signals on an optical port are lost.": [
        "Verificare la fibra connessa alla porta ottica",
        "Pulire i connettori ottici (particelle di polvere)",
        "Misurare la potenza ottica ricevuta con power meter",
        "Verificare lo stato dell'apparato trasmittente remoto",
    ],
    "input optical power (dbm) exceeds the threshold": [
        "Verificare potenza TX del trasmettitore remoto",
        "Inserire attenuatore se il livello è eccessivo",
        "Controllare la configurazione delle soglie ottiche sull'NE",
    ],

    # ── CSF / E1 ────────────────────────────────────────────────────────────────
    "csf": [
        "Client Signal Fail: verificare il segnale client (E1/Ethernet) a monte",
        "Controllare stato dell'apparato che alimenta il segnale",
        "Verificare la continuità del servizio end-to-end",
    ],
    "e1-ais": [
        "Alarm Indication Signal: segnale AIS ricevuto da monte",
        "Verificare la catena E1 dal punto di origine",
        "Controllare se il problema è sul Site A o sul percorso a monte",
    ],

    # ── DEFAULT (fallback) ─────────────────────────────────────────────────────
    "_default": [
        "Verificare i log di sistema sull'NE tramite NMS",
        "Confrontare con la configurazione nominale dell'apparato",
        "Consultare la documentazione tecnica del vendor per questo codice allarme",
        "Aprire ticket di analisi se l'allarme non si risolve entro 1 ora",
    ],
}


def get_solution(alarm_name: str) -> list[str]:
    """
    Restituisce le soluzioni suggerite per un allarme.
    Cerca prima una corrispondenza esatta (case-insensitive),
    poi una corrispondenza parziale (sottostringa),
    poi restituisce il default.
    """
    alarm_lower = alarm_name.lower().strip()

    # 1. Match esatto
    if alarm_lower in SOLUTIONS_KB:
        return SOLUTIONS_KB[alarm_lower]

    # 2. Match parziale (la chiave è sottostringa del nome allarme)
    for key, solutions in SOLUTIONS_KB.items():
        if key == '_default':
            continue
        if key in alarm_lower or alarm_lower in key:
            return solutions

    # 3. Fallback
    return SOLUTIONS_KB['_default']
