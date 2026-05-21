import React, { useState, useRef, useMemo, useEffect, useCallback } from 'react';
import axios from 'axios';
import {
  UploadCloud, Activity, AlertTriangle, CheckCircle, Clock,
  Search, ArrowLeftRight, X, BookOpen, ShieldAlert, Zap,
  ChevronRight, RefreshCw, Star, Info, AlertCircle, CheckSquare
} from 'lucide-react';
import './index.css';

const API = 'http://localhost:8000';

// ─────────────────────────────────────────────────────────────────────────────
//  App
// ─────────────────────────────────────────────────────────────────────────────
function App() {
  const [appState, setAppState]       = useState('loading'); // loading | wizard | upload | results | compare | kb
  const [wizardAlarms, setWizardAlarms] = useState([]);
  const [file, setFile]               = useState(null);
  const [loading, setLoading]         = useState(false);
  const [progress, setProgress]       = useState(0);
  const [results, setResults]         = useState(null);
  const [newAlarms, setNewAlarms]     = useState([]);
  const [showNewAlarms, setShowNewAlarms] = useState(false);
  const [filters, setFilters]         = useState({ action: '', me: '', topology: '', alarm: '', severity: '' });
  const [selectedSiteA, setSelectedSiteA] = useState(null);
  const [compareMode, setCompareMode] = useState(false);
  const [kbStats, setKbStats]         = useState(null);
  const [activeTab, setActiveTab]     = useState('alarms'); // alarms | kb
  const [showAll, setShowAll]         = useState(false);
  const [detailModalAlarm, setDetailModalAlarm] = useState(null);
  const [kpiModalCategory, setKpiModalCategory] = useState(null);
  const [neHistoryModal, setNeHistoryModal] = useState(null);
  const [neHistoryData, setNeHistoryData] = useState(null);
  const fileInputRef = useRef(null);

  // ── Caricamento iniziale ────────────────────────────────────────────────────
  useEffect(() => {
    (async () => {
      try {
        const res = await axios.get(`${API}/api/first-launch`);
        const { wizard_completed, structural_alarms, kb_available } = res.data;
        if (!wizard_completed && kb_available && structural_alarms.length > 0) {
          setWizardAlarms(structural_alarms.map(a => ({ ...a, selected_action: a.suggested_action === 'TOLERABLE' ? 'TRASCURABILE' : 'MONITORA' })));
          setAppState('wizard');
        } else {
          setAppState('upload');
        }
      } catch {
        setAppState('upload'); // backend non pronto con KB → vai diretto all'upload
      }
    })();
  }, []);

  // ── Upload file ─────────────────────────────────────────────────────────────
  const processFile = async () => {
    if (!file) return;
    setLoading(true);
    setProgress(0);
    const iv = setInterval(() => setProgress(p => p >= 90 ? p : p + Math.floor(Math.random() * 12) + 4), 400);
    const fd = new FormData();
    fd.append('file', file);
    try {
      const res = await axios.post(`${API}/api/upload`, fd, { headers: { 'Content-Type': 'multipart/form-data' } });
      clearInterval(iv);
      setProgress(100);
      const data = res.data.data;
      setTimeout(() => {
        setResults(data);
        const na = data.new_alarms || [];
        setNewAlarms(na);
        if (na.length > 0) setShowNewAlarms(true);
        setLoading(false);
        setAppState('results');
        loadKbStats();
      }, 500);
    } catch (err) {
      clearInterval(iv);
      alert("Errore: " + (err.response?.data?.detail || err.message));
      setLoading(false);
      setProgress(0);
    }
  };

  const loadKbStats = async () => {
    try {
      const res = await axios.get(`${API}/api/kb/stats`);
      setKbStats(res.data);
    } catch {}
  };

  useEffect(() => { if (appState === 'kb') loadKbStats(); }, [appState]);

  // ── Wizard submit ───────────────────────────────────────────────────────────
  const submitWizard = async () => {
    const rules = wizardAlarms.map(a => ({
      alarm_code_name: a.alarm_code_name,
      operator_action: a.selected_action,
      note: '',
    }));
    try {
      await axios.post(`${API}/api/operator-kb/init`, { rules });
      setAppState('upload');
    } catch (e) {
      alert('Errore salvataggio preferenze: ' + e.message);
    }
  };

  // ── Feedback nuovi allarmi ──────────────────────────────────────────────────
  const handleNewAlarmAction = async (alarm, action, note = '') => {
    try {
      await axios.post(`${API}/api/operator-kb/update`, {
        alarm_code_name: alarm['Alarm Code Name'],
        operator_action: action,
        note,
        new_alarm_entry: { solution_applied: note, resolved: false },
      });
      setNewAlarms(prev => prev.filter(a => a['Alarm Code Name'] !== alarm['Alarm Code Name']));
      
      // Update the main table state to reflect the override
      setResults(prev => ({
        ...prev,
        alarms: prev.alarms.map(a => 
          a['Alarm Code Name'] === alarm['Alarm Code Name'] 
            ? { ...a, Action: action, Operator_Override: true }
            : a
        )
      }));
    } catch (e) {
      alert('Errore: ' + e.message);
    }
  };

  const handleRowAction = async (alarm, action) => {
    try {
      await axios.post(`${API}/api/operator-kb/update`, {
        alarm_code_name: alarm['Alarm Code Name'],
        operator_action: action,
        note: 'Forzato da tabella giornaliera',
      });
      setResults(prev => ({
        ...prev,
        alarms: prev.alarms.map(a => 
          a['Alarm Code Name'] === alarm['Alarm Code Name'] 
            ? { ...a, Action: action, Operator_Override: true }
            : a
        )
      }));
    } catch (e) {
      alert('Errore: ' + e.message);
    }
  };

  // ── Filtering ───────────────────────────────────────────────────────────────
  const filteredAlarms = useMemo(() => {
    if (!results) return [];
    return results.alarms.filter(a => {
      const matchAction   = !filters.action   || String(a.Action || '').toLowerCase().includes(filters.action.toLowerCase());
      const matchMe       = !filters.me       || String(a.ME || '').toLowerCase().includes(filters.me.toLowerCase());
      const matchTopology = !filters.topology || String(a.Topology_Role || '').toLowerCase().includes(filters.topology.toLowerCase());
      const matchAlarm    = !filters.alarm    || String(a['Alarm Code Name'] || '').toLowerCase().includes(filters.alarm.toLowerCase());
      const matchSeverity = !filters.severity || String(a['Alarm Severity'] || '').toLowerCase().includes(filters.severity.toLowerCase());
      return matchAction && matchMe && matchTopology && matchAlarm && matchSeverity;
    });
  }, [results, filters]);

  const displayAlarms = showAll ? filteredAlarms : filteredAlarms.slice(0, 200);

  // ── Site A/B pairing ────────────────────────────────────────────────────────
  const pairedSubnet = useMemo(() => {
    if (!selectedSiteA || !results) return null;
    const rec = results.alarms.find(a => a.ME === selectedSiteA && a.Topology_Role === 'Local (Site A)');
    return rec ? rec['ME IP'] : null;
  }, [selectedSiteA, results]);

  const siteAAlarms = useMemo(() => {
    if (!selectedSiteA || !results) return [];
    return results.alarms.filter(a => a.ME === selectedSiteA);
  }, [selectedSiteA, results]);

  const siteBAlarms = useMemo(() => {
    if (!pairedSubnet || !results) return [];
    // La logica di default trova i Remote (Site B) sulla stessa subnet
    // Il backend si è già occupato di assegnare "Remote (Site B)" in modo differenziato 
    // per NR9250 e ER2020E basandosi sugli IP della subnet.
    return results.alarms.filter(a => a.Topology_Role === 'Remote (Site B)' && isSameSubnet28(a['ME IP'], pairedSubnet));
  }, [pairedSubnet, results]);

  const siteBName = useMemo(() => siteBAlarms.length ? siteBAlarms[0].ME : null, [siteBAlarms]);

  const clearCompare = () => { setSelectedSiteA(null); setCompareMode(false); };

  const fetchNeHistory = async (meName) => {
    setNeHistoryModal(meName);
    setNeHistoryData(null);
    try {
      const res = await axios.get(`${API}/api/history/ne/${encodeURIComponent(meName)}`);
      setNeHistoryData(res.data);
    } catch (e) {
      alert("Errore fetch history: " + e.message);
      setNeHistoryModal(null);
    }
  };

  // ─────────────────────────────────────────────────────────────────────────────
  //  RENDER
  // ─────────────────────────────────────────────────────────────────────────────

  if (appState === 'loading') return (
    <div className="app-container" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '80vh' }}>
      <div style={{ textAlign: 'center' }}>
        <RefreshCw size={48} className="spin-icon" style={{ color: 'var(--accent-color)', marginBottom: '1rem' }} />
        <p style={{ color: 'var(--text-secondary)' }}>Caricamento sistema...</p>
      </div>
    </div>
  );

  if (appState === 'wizard') return (
    <WizardView alarms={wizardAlarms} setAlarms={setWizardAlarms} onSubmit={submitWizard} onSkip={() => setAppState('upload')} />
  );

  return (
    <div className="app-container">
      <header>
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', flexWrap: 'wrap' }}>
          <div>
            <h1>MW Alarm Manager</h1>
            <p>Intelligenza Agentica per l'Analisi dei Ponti Radio</p>
          </div>
          {results && (
            <div className="tab-bar">
              <button className={`tab-btn ${activeTab === 'alarms' ? 'active' : ''}`} onClick={() => setActiveTab('alarms')}>
                <Activity size={15} /> Dashboard
              </button>
              <button className={`tab-btn ${activeTab === 'kb' ? 'active' : ''}`} onClick={() => { setActiveTab('kb'); loadKbStats(); }}>
                <BookOpen size={15} /> Knowledge Base
              </button>
            </div>
          )}
        </div>
      </header>

      {/* ── Pannello Nuovi Allarmi ──────────────────────────────────────────── */}
      {showNewAlarms && newAlarms.length > 0 && (
        <NewAlarmsPanel
          alarms={newAlarms}
          onAction={handleNewAlarmAction}
          onClose={() => setShowNewAlarms(false)}
        />
      )}
      {results && newAlarms.length > 0 && !showNewAlarms && (
        <button className="new-alarms-badge" onClick={() => setShowNewAlarms(true)}>
          <AlertCircle size={16} /> {newAlarms.length} nuovi allarmi da classificare
        </button>
      )}

      {/* ── States ─────────────────────────────────────────────────────────── */}
      {!results ? (
        // UPLOAD VIEW
        <div className="glass-card upload-area"
             onDragOver={e => e.preventDefault()}
             onDrop={e => { e.preventDefault(); if (e.dataTransfer.files[0]) setFile(e.dataTransfer.files[0]); }}>
          <UploadCloud className="upload-icon" />
          <h2>Carica l'estrazione giornaliera degli allarmi</h2>
          <p style={{ color: 'var(--text-secondary)', marginTop: '0.5rem' }}>
            {file ? `📎 ${file.name}` : 'Trascina qui il file Excel (.xlsx) oppure clicca per sfogliare'}
          </p>
          <input type="file" ref={fileInputRef} onChange={e => { if (e.target.files[0]) setFile(e.target.files[0]); }}
                 style={{ display: 'none' }} accept=".xlsx,.xls" />
          <button className="upload-btn" onClick={() => fileInputRef.current.click()}>Seleziona File</button>
          {file && !loading && (
            <div style={{ marginTop: '1rem' }}>
              <button className="upload-btn" onClick={processFile} style={{ background: '#10b981' }}>
                <Zap size={16} style={{ marginRight: '0.4rem' }} /> Avvia Analisi
              </button>
            </div>
          )}
          {loading && (
            <div className="progress-container">
              <div className="progress-bar" style={{ width: `${progress}%` }} />
              <div className="progress-text">Analisi in corso... {progress}%</div>
            </div>
          )}
        </div>

      ) : compareMode && selectedSiteA ? (
        // COMPARE VIEW
        <div>
          <div className="compare-header">
            <h2 className="compare-title">
              <ArrowLeftRight size={22} style={{ color: 'var(--accent-color)' }} />
              Confronto Link Radio
            </h2>
            <button className="upload-btn" onClick={clearCompare} style={{ background: 'rgba(255,255,255,0.1)', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
              <X size={16} /> Chiudi Confronto
            </button>
          </div>
          <div className="compare-grid">
            <div className="glass-card compare-panel">
              <div className="compare-panel-header site-a">
                <span className="site-badge">SITO A — LOCALE</span>
                <strong>{selectedSiteA}</strong>
                <small>{pairedSubnet}</small>
              </div>
              <SiteAlarmTable alarms={siteAAlarms} />
            </div>
            <div className="glass-card compare-panel">
              <div className="compare-panel-header site-b">
                <span className="site-badge">SITO B — REMOTO</span>
                <strong>{siteBName || '—'}</strong>
                <small>{siteBAlarms[0]?.['ME IP'] || ''}</small>
              </div>
              {siteBAlarms.length > 0
                ? <SiteAlarmTable alarms={siteBAlarms} />
                : <p style={{ padding: '2rem', color: 'var(--text-secondary)', textAlign: 'center' }}>Nessun allarme trovato per il Sito B su questa subnet.</p>}
            </div>
          </div>
        </div>

      ) : activeTab === 'kb' ? (
        // KB VIEW
        <KBView stats={kbStats} onRefresh={loadKbStats} />

      ) : (
        // DASHBOARD VIEW
        <div>
          {/* KPI Row */}
          <div className="dashboard-grid">
            <div className="glass-card kpi-card">
              <Activity className="upload-icon" style={{ color: 'var(--text-secondary)' }} />
              <div className="kpi-value">{results.stats.total}</div>
              <div className="kpi-label">Totale Processati</div>
            </div>
            <div className="glass-card kpi-card clickable" onClick={() => setKpiModalCategory('ESCALATE')} style={{ borderTop: '4px solid var(--status-escalate)' }}>
              <AlertTriangle className="upload-icon" style={{ color: 'var(--status-escalate)' }} />
              <div className="kpi-value kpi-Escalate">{results.stats.categories.Escalate}</div>
              <div className="kpi-label">Escalate (Ticket)</div>
            </div>
            <div className="glass-card kpi-card clickable" onClick={() => setKpiModalCategory('MONITOR')} style={{ borderTop: '4px solid var(--status-monitor)' }}>
              <Activity className="upload-icon" style={{ color: 'var(--status-monitor)' }} />
              <div className="kpi-value kpi-Monitor">{results.stats.categories.Monitor}</div>
              <div className="kpi-label">Da Monitorare</div>
            </div>
            <div className="glass-card kpi-card clickable" onClick={() => setKpiModalCategory('TOLERABLE')} style={{ borderTop: '4px solid var(--status-tolerable)' }}>
              <CheckCircle className="upload-icon" style={{ color: 'var(--status-tolerable)' }} />
              <div className="kpi-value kpi-Tolerable">{results.stats.categories.Tolerable}</div>
              <div className="kpi-label">Trascurabili</div>
            </div>
            <div className="glass-card kpi-card clickable" onClick={() => setKpiModalCategory('CHRONIC')} style={{ borderTop: '4px solid #8b5cf6' }}>
              <Clock className="upload-icon" style={{ color: '#8b5cf6' }} />
              <div className="kpi-value" style={{ color: '#8b5cf6' }}>{results.stats.categories.Chronic_Feedback_Needed}</div>
              <div className="kpi-label">Cronici</div>
            </div>
            {results.stats.categories.New > 0 && (
              <div className="glass-card kpi-card" style={{ borderTop: '4px solid #f59e0b', cursor: 'pointer' }}
                   onClick={() => setShowNewAlarms(true)}>
                <AlertCircle className="upload-icon" style={{ color: '#f59e0b' }} />
                <div className="kpi-value" style={{ color: '#f59e0b' }}>{results.stats.categories.New}</div>
                <div className="kpi-label">Nuovi Allarmi ⚡</div>
              </div>
            )}
          </div>

          {/* Tabella */}
          <div className="glass-card data-table-container">
            <div className="table-header-row">
              <h3>Dettaglio Allarmi</h3>
              <span style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>{filteredAlarms.length} risultati</span>
            </div>
            <div className="filters-row">
              <FilterInput icon={<Search size={14}/>} placeholder="Azione..." value={filters.action} onChange={v => setFilters(f => ({ ...f, action: v }))} />
              <FilterInput icon={<Search size={14}/>} placeholder="Sito (ME)..." value={filters.me} onChange={v => setFilters(f => ({ ...f, me: v }))} />
              <FilterInput icon={<Search size={14}/>} placeholder="Topologia..." value={filters.topology} onChange={v => setFilters(f => ({ ...f, topology: v }))} />
              <FilterInput icon={<Search size={14}/>} placeholder="Allarme..." value={filters.alarm} onChange={v => setFilters(f => ({ ...f, alarm: v }))} />
              <FilterInput icon={<Search size={14}/>} placeholder="Severità..." value={filters.severity} onChange={v => setFilters(f => ({ ...f, severity: v }))} />
              {Object.values(filters).some(v => v) && (
                <button className="feedback-btn" onClick={() => setFilters({ action:'', me:'', topology:'', alarm:'', severity:'' })}>
                  <X size={14}/> Reset
                </button>
              )}
            </div>

            <table className="data-table">
              <thead>
                <tr>
                  <th>Azione Agente</th>
                  <th>Sito (ME)</th>
                  <th>Topologia / IP</th>
                  <th>Allarme</th>
                  <th>Severità</th>
                  <th>Data Insorgenza</th>
                  <th>Flag</th>
                  <th>Classifica</th>
                </tr>
              </thead>
              <tbody>
                {displayAlarms.map((alarm, idx) => (
                  <tr key={idx} style={{ opacity: alarm.Is_Chronic && !alarm.Is_New_Alarm ? 0.7 : 1 }}
                      className={alarm.Is_New_Alarm ? 'row-new-alarm' : ''}>
                    <td><span className={`badge badge-${alarm.Action}`}>{alarm.Action}</span></td>
                    <td>
                      {alarm.Topology_Role === 'Local (Site A)' ? (
                        <button className="site-link" title="Clicca per confrontare con il Sito B"
                          onClick={() => { setSelectedSiteA(alarm.ME); setCompareMode(true); }}>
                          {alarm.ME}
                          <ArrowLeftRight size={12} style={{ marginLeft: '0.4rem', opacity: 0.6 }} />
                        </button>
                      ) : <span>{alarm.ME}</span>}
                    </td>
                    <td>
                      <span className={`topo-badge ${alarm.Topology_Role === 'Local (Site A)' ? 'topo-local' : 'topo-remote'}`}>
                        {alarm.Topology_Role === 'Local (Site A)' ? 'A' : alarm.Topology_Role === 'Remote (Site B)' ? 'B' : '?'}
                      </span>
                      {' '}{alarm.Topology_Role}
                      <br /><small style={{ color: 'var(--text-secondary)' }}>{alarm['ME IP']}</small>
                      {alarm.Link_Type && <span style={{display:'block', fontSize:'0.75rem', opacity:0.8}}>{alarm.Link_Type}</span>}
                    </td>
                    <td>{alarm['Alarm Code Name']}</td>
                    <td>{alarm['Alarm Severity']}</td>
                    <td>{alarm['Occurrence Time']}</td>
                    <td>
                      <div style={{ display: 'flex', gap: '0.3rem', flexWrap: 'wrap' }}>
                        {alarm.Is_New_Alarm     && <span className="flag-badge flag-new">NUOVO</span>}
                        {alarm.Is_Structural    && <span className="flag-badge flag-structural">STRUCT</span>}
                        {alarm.Operator_Override && <span className="flag-badge flag-operator">OP</span>}
                        {alarm.Is_Chronic       && <span className="flag-badge flag-chronic">CRONICO</span>}
                      </div>
                    </td>
                    <td>
                      <div style={{ display: 'flex', gap: '0.3rem' }}>
                        <button className="row-action-btn ok" title="Trascurabile" onClick={() => handleRowAction(alarm, 'TRASCURABILE')}>
                          <CheckCircle size={14} />
                        </button>
                        <button className="row-action-btn mon" title="Monitora" onClick={() => handleRowAction(alarm, 'MONITORA')}>
                          <Activity size={14} />
                        </button>
                        <button className="row-action-btn esc" title="Scala Sempre" onClick={() => handleRowAction(alarm, 'SCALA')}>
                          <AlertTriangle size={14} />
                        </button>
                        <button className="row-action-btn" title="Dettaglio" onClick={() => setDetailModalAlarm(alarm)}>
                          <Info size={14} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!showAll && filteredAlarms.length > 200 && (
              <div style={{ textAlign: 'center', marginTop: '1rem' }}>
                <p style={{ color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>
                  Mostrando 200 di {filteredAlarms.length} risultati
                </p>
                <button className="feedback-btn" onClick={() => setShowAll(true)}>Mostra tutti i risultati</button>
              </div>
            )}
            {showAll && filteredAlarms.length > 200 && (
              <div style={{ textAlign: 'center', marginTop: '1rem' }}>
                <p style={{ color: 'var(--text-secondary)' }}>Tutti i {filteredAlarms.length} risultati mostrati.</p>
              </div>
            )}
          </div>

          <div style={{ marginTop: '2rem', textAlign: 'center' }}>
            <button className="upload-btn" onClick={() => { setResults(null); setNewAlarms([]); setShowNewAlarms(false); setFilters({ action:'', me:'', topology:'', alarm:'', severity:'' }); setAppState('upload'); }}>
              Analizza Nuovo File
            </button>
          </div>
        </div>
      )}

      {/* ── Modals ────────────────────────────────────────────────────────── */}
      {detailModalAlarm && (
        <DetailModal alarm={detailModalAlarm} onClose={() => setDetailModalAlarm(null)} />
      )}
      {kpiModalCategory && (
        <KpiModal 
          category={kpiModalCategory} 
          results={results} 
          onClose={() => setKpiModalCategory(null)} 
          onAction={handleRowAction}
        />
      )}
      {neHistoryModal && (
        <NeHistoryModal 
          meName={neHistoryModal}
          data={neHistoryData}
          onClose={() => { setNeHistoryModal(null); setNeHistoryData(null); }}
        />
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
//  Wizard Prima Apertura
// ─────────────────────────────────────────────────────────────────────────────
function WizardView({ alarms, setAlarms, onSubmit, onSkip }) {
  const [step, setStep]     = useState(0);   // 0=intro, 1=lista, 2=confirm
  const [saving, setSaving] = useState(false);

  const setAction = (idx, action) => {
    setAlarms(prev => prev.map((a, i) => i === idx ? { ...a, selected_action: action } : a));
  };

  const handleSubmit = async () => {
    setSaving(true);
    await onSubmit();
  };

  const actions = [
    { key: 'TRASCURABILE', label: 'Trascurabile', color: '#10b981', icon: '🟢', desc: 'Non aprire mai ticket' },
    { key: 'MONITORA',     label: 'Monitora',     color: '#f59e0b', icon: '🟡', desc: 'Tenere d\'occhio' },
    { key: 'SCALA',        label: 'Scala Sempre', color: '#ef4444', icon: '🔴', desc: 'Apri sempre ticket' },
  ];

  return (
    <div className="wizard-overlay">
      <div className="wizard-container">
        {step === 0 && (
          <div className="wizard-intro">
            <div className="wizard-icon-big"><BookOpen size={56} /></div>
            <h2>Benvenuto in MW Alarm Manager</h2>
            <p>
              Ho analizzato <strong>{alarms.length} tipologie di allarmi strutturali</strong> presenti 
              nello storico degli ultimi 20 giorni. Prima di iniziare, aiutami a capire 
              quali sono <strong>trascurabili</strong> e quali richiedono attenzione.
            </p>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginTop: '0.5rem' }}>
              Questa classificazione veloce (2-3 minuti) migliorerà significativamente 
              l'accuratezza del sistema. Potrai modificarla in qualsiasi momento dalla sezione Knowledge Base.
            </p>
            <div style={{ display: 'flex', gap: '1rem', justifyContent: 'center', marginTop: '2rem', flexWrap: 'wrap' }}>
              <button className="upload-btn" onClick={() => setStep(1)} style={{ background: 'var(--accent-color)' }}>
                Inizia Classificazione <ChevronRight size={18} />
              </button>
              <button className="upload-btn" onClick={onSkip} style={{ background: 'rgba(255,255,255,0.1)' }}>
                Salta per ora
              </button>
            </div>
          </div>
        )}

        {step === 1 && (
          <div className="wizard-list-view">
            <div className="wizard-list-header">
              <h2><ShieldAlert size={24} style={{ color: 'var(--accent-color)' }} /> Classificazione Allarmi Strutturali</h2>
              <p style={{ color: 'var(--text-secondary)' }}>
                Per ogni allarme, scegli l'azione predefinita. Il sistema ha suggerito un'azione in base allo storico.
              </p>
              <div className="action-legend">
                {actions.map(a => (
                  <span key={a.key} style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', fontSize: '0.8rem' }}>
                    {a.icon} {a.label} — {a.desc}
                  </span>
                ))}
              </div>
            </div>

            <div className="wizard-alarms-list">
              {alarms.map((alarm, idx) => (
                <div key={idx} className="wizard-alarm-row">
                  <div className="wizard-alarm-info">
                    <div className="wizard-alarm-name">{alarm.alarm_code_name}</div>
                    <div className="wizard-alarm-meta">
                      <span className={`sev-badge sev-${alarm.main_severity?.toLowerCase()}`}>{alarm.main_severity}</span>
                      <span style={{ color: 'var(--text-secondary)', fontSize: '0.8rem' }}>
                        {alarm.total_occurrences?.toLocaleString()} occorrenze · {alarm.affected_me_count} NE
                      </span>
                      <span style={{ color: 'var(--text-secondary)', fontSize: '0.8rem' }}>
                        Score: <strong style={{ color: 'var(--accent-color)' }}>{(alarm.filterability_score * 100).toFixed(0)}%</strong>
                      </span>
                    </div>
                  </div>
                  <div className="wizard-action-btns">
                    {actions.map(a => (
                      <button
                        key={a.key}
                        className={`wizard-action-btn ${alarm.selected_action === a.key ? 'selected' : ''}`}
                        style={alarm.selected_action === a.key ? { background: a.color, borderColor: a.color } : {}}
                        onClick={() => setAction(idx, a.key)}
                      >
                        {a.icon} {a.label}
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            </div>

            <div className="wizard-footer">
              <div style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
                <CheckSquare size={14} style={{ display: 'inline', marginRight: '0.3rem' }} />
                {alarms.filter(a => a.selected_action === 'TRASCURABILE').length} trascurabili · {' '}
                {alarms.filter(a => a.selected_action === 'MONITORA').length} da monitorare · {' '}
                {alarms.filter(a => a.selected_action === 'SCALA').length} da scalare
              </div>
              <button className="upload-btn" onClick={handleSubmit} disabled={saving} style={{ background: '#10b981' }}>
                {saving ? <RefreshCw size={16} className="spin-icon" /> : <CheckCircle size={16} />}
                {saving ? ' Salvataggio...' : ' Conferma e Vai alla Dashboard'}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
//  Pannello Nuovi Allarmi
// ─────────────────────────────────────────────────────────────────────────────
function NewAlarmsPanel({ alarms, onAction, onClose }) {
  const [notes, setNotes]   = useState({});
  const [done, setDone]     = useState(new Set());

  const handleAction = async (alarm, action) => {
    const note = notes[alarm['Alarm Code Name']] || '';
    await onAction(alarm, action, note);
    setDone(prev => new Set([...prev, alarm['Alarm Code Name']]));
  };

  const visible = alarms.filter(a => !done.has(a['Alarm Code Name']));

  return (
    <div className="new-alarms-overlay">
      <div className="new-alarms-panel">
        <div className="new-alarms-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.8rem' }}>
            <AlertCircle size={22} style={{ color: '#f59e0b' }} />
            <div>
              <h3 style={{ margin: 0 }}>⚡ Nuovi Allarmi Rilevati</h3>
              <p style={{ margin: 0, color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
                {visible.length} allarmi mai visti nello storico richiedono la tua classificazione
              </p>
            </div>
          </div>
          <button className="icon-btn" onClick={onClose}><X size={20} /></button>
        </div>

        <div className="new-alarms-body">
          {visible.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-secondary)' }}>
              <CheckCircle size={40} style={{ color: '#10b981', marginBottom: '0.5rem' }} />
              <p>Tutti i nuovi allarmi sono stati classificati!</p>
            </div>
          ) : visible.map((alarm, idx) => (
            <div key={idx} className="new-alarm-card">
              <div className="new-alarm-top">
                <div>
                  <div className="new-alarm-name">{alarm['Alarm Code Name']}</div>
                  <div className="new-alarm-meta">
                    <span className={`badge badge-${alarm.Action}`}>{alarm.Action}</span>
                    <span className={`sev-badge sev-${alarm['Alarm Severity']?.toLowerCase()}`}>{alarm['Alarm Severity']}</span>
                    <span style={{ color: 'var(--text-secondary)', fontSize: '0.82rem' }}>📡 {alarm.ME}</span>
                  </div>
                </div>
              </div>

              {alarm.Suggested_Solution && alarm.Suggested_Solution.length > 0 && (
                <div className="solution-box">
                  <div className="solution-title"><Star size={13} /> Azioni Suggerite:</div>
                  <ul className="solution-list">
                    {alarm.Suggested_Solution.map((s, i) => <li key={i}>{s}</li>)}
                  </ul>
                </div>
              )}

              <textarea
                className="note-input"
                placeholder="Note operative (opzionale)..."
                value={notes[alarm['Alarm Code Name']] || ''}
                onChange={e => setNotes(prev => ({ ...prev, [alarm['Alarm Code Name']]: e.target.value }))}
              />

              <div className="new-alarm-actions">
                <button className="action-btn action-escalate" onClick={() => handleAction(alarm, 'SCALA')}>
                  <AlertTriangle size={14} /> Apri Ticket
                </button>
                <button className="action-btn action-monitor" onClick={() => handleAction(alarm, 'MONITORA')}>
                  <Activity size={14} /> Monitora
                </button>
                <button className="action-btn action-ignore" onClick={() => handleAction(alarm, 'TRASCURABILE')}>
                  <CheckCircle size={14} /> Trascura Sempre
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
//  Knowledge Base View
// ─────────────────────────────────────────────────────────────────────────────
function KBView({ stats, onRefresh, onNeClick }) {
  if (!stats) return (
    <div className="glass-card" style={{ textAlign: 'center', padding: '3rem' }}>
      <RefreshCw size={32} className="spin-icon" style={{ color: 'var(--accent-color)', marginBottom: '1rem' }} />
      <p>Caricamento Knowledge Base...</p>
    </div>
  );

  if (!stats.available) return (
    <div className="glass-card" style={{ textAlign: 'center', padding: '3rem' }}>
      <Info size={40} style={{ color: '#f59e0b', marginBottom: '1rem' }} />
      <h3>Knowledge Base non ancora generata</h3>
      <p style={{ color: 'var(--text-secondary)' }}>
        Esegui <code style={{ background: 'rgba(255,255,255,0.1)', padding: '2px 6px', borderRadius: '4px' }}>python DATI/build_history_db.py</code> e poi{' '}
        <code style={{ background: 'rgba(255,255,255,0.1)', padding: '2px 6px', borderRadius: '4px' }}>python DATI/build_kb.py</code>
      </p>
    </div>
  );

  return (
    <div>
      {/* Metadati KB */}
      <div className="dashboard-grid">
        <div className="glass-card kpi-card">
          <BookOpen className="upload-icon" style={{ color: 'var(--accent-color)' }} />
          <div className="kpi-value">{stats.total_events?.toLocaleString()}</div>
          <div className="kpi-label">Eventi Storico</div>
        </div>
        <div className="glass-card kpi-card">
          <Activity className="upload-icon" style={{ color: '#10b981' }} />
          <div className="kpi-value" style={{ color: '#10b981' }}>{stats.unique_mes}</div>
          <div className="kpi-label">NE nel Database</div>
        </div>
        <div className="glass-card kpi-card">
          <CheckCircle className="upload-icon" style={{ color: '#8b5cf6' }} />
          <div className="kpi-value" style={{ color: '#8b5cf6' }}>{stats.structural_alarm_count}</div>
          <div className="kpi-label">Allarmi Strutturali</div>
        </div>
        <div className="glass-card kpi-card">
          <Star className="upload-icon" style={{ color: '#f59e0b' }} />
          <div className="kpi-value" style={{ color: '#f59e0b' }}>{stats.operator_rules_count}</div>
          <div className="kpi-label">Regole Operatore</div>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem', marginTop: '0' }}>
        {/* Top allarmi strutturali */}
        <div className="glass-card data-table-container">
          <div className="table-header-row">
            <h3>🔵 Allarmi Strutturali (Filtrabili)</h3>
            <span style={{ color: 'var(--text-secondary)', fontSize: '0.8rem' }}>Score ≥ {Math.round((stats.filterability_threshold || 0.85) * 100)}%</span>
          </div>
          <table className="data-table">
            <thead>
              <tr>
                <th>Allarme</th>
                <th>Score</th>
                <th>Occ.</th>
                <th>NE</th>
                <th>Operatore</th>
              </tr>
            </thead>
            <tbody>
              {(stats.top_structural_alarms || []).map((a, i) => (
                <tr key={i}>
                  <td style={{ fontSize: '0.78rem', maxWidth: '220px', wordBreak: 'break-word' }}>{a.name}</td>
                  <td>
                    <div className="score-bar-wrap">
                      <div className="score-bar" style={{ width: `${Math.round(a.score * 100)}%` }} />
                      <span>{Math.round(a.score * 100)}%</span>
                    </div>
                  </td>
                  <td style={{ fontSize: '0.8rem' }}>{a.occurrences?.toLocaleString()}</td>
                  <td style={{ fontSize: '0.8rem' }}>{a.affected_me}</td>
                  <td>
                    {a.operator_classified
                      ? <span className="flag-badge flag-operator">✓ OP</span>
                      : <span className="flag-badge" style={{ background: 'rgba(255,255,255,0.08)', color: '#888' }}>Auto</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Top NE a rischio */}
        <div className="glass-card data-table-container">
          <div className="table-header-row">
            <h3>🔴 NE ad Alto Rischio</h3>
            <span style={{ color: 'var(--text-secondary)', fontSize: '0.8rem' }}>Ultimi {stats.history_days} giorni</span>
          </div>
          <table className="data-table">
            <thead>
              <tr>
                <th>NE</th>
                <th>Risk</th>
                <th>Allarmi</th>
                <th>Cronici</th>
                <th>Azione</th>
              </tr>
            </thead>
            <tbody>
              {(stats.top_risk_ne || []).map((ne, i) => (
                <tr key={i}>
                  <td style={{ fontSize: '0.82rem' }}>{ne.name}</td>
                  <td>
                    <div className="score-bar-wrap">
                      <div className="score-bar risk-bar" style={{ width: `${Math.round(ne.risk_score * 100)}%` }} />
                      <span>{Math.round(ne.risk_score * 100)}%</span>
                    </div>
                  </td>
                  <td style={{ fontSize: '0.8rem' }}>{ne.total_alarms?.toLocaleString()}</td>
                  <td>
                    {ne.chronic_count > 0
                      ? <span className="flag-badge flag-chronic">{ne.chronic_count}</span>
                      : <span style={{ color: '#888', fontSize: '0.8rem' }}>—</span>}
                  </td>
                  <td>
                    <button className="row-action-btn" title="Storico NE" onClick={() => onNeClick(ne.name)}>
                      <Activity size={14} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div style={{ textAlign: 'center', marginTop: '1.5rem', color: 'var(--text-secondary)', fontSize: '0.82rem' }}>
        KB generata: {stats.generated_at ? new Date(stats.generated_at).toLocaleString('it-IT') : '—'} ·
        Periodo: {stats.date_from} → {stats.date_to}
        <button onClick={onRefresh} style={{ marginLeft: '1rem', background: 'none', border: 'none', color: 'var(--accent-color)', cursor: 'pointer', fontSize: '0.82rem' }}>
          <RefreshCw size={12} style={{ marginRight: '0.3rem' }} />Aggiorna
        </button>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
//  Helper Components
// ─────────────────────────────────────────────────────────────────────────────

function isSameSubnet28(ip1, ip2) {
  try {
    const toInt = ip => ip.split('.').reduce((acc, oct) => (acc << 8) + parseInt(oct), 0);
    const mask = 0xFFFFFFF0;
    return (toInt(ip1) & mask) === (toInt(ip2) & mask);
  } catch { return false; }
}

function FilterInput({ icon, placeholder, value, onChange }) {
  return (
    <div className="filter-input-wrapper">
      {icon}
      <input className="filter-input" placeholder={placeholder} value={value} onChange={e => onChange(e.target.value)} />
      {value && <button className="filter-clear" onClick={() => onChange('')}><X size={12}/></button>}
    </div>
  );
}

function SiteAlarmTable({ alarms }) {
  return (
    <div style={{ overflowX: 'auto' }}>
      <table className="data-table">
        <thead>
          <tr>
            <th>Azione</th>
            <th>Allarme</th>
            <th>Severità</th>
            <th>Data</th>
          </tr>
        </thead>
        <tbody>
          {alarms.slice(0, 50).map((alarm, idx) => (
            <tr key={idx}>
              <td><span className={`badge badge-${alarm.Action}`}>{alarm.Action}</span></td>
              <td>{alarm['Alarm Code Name']}</td>
              <td>{alarm['Alarm Severity']}</td>
              <td>{alarm['Occurrence Time']}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {alarms.length > 50 && (
        <p style={{ padding: '0.75rem', color: 'var(--text-secondary)', fontSize: '0.85rem', textAlign: 'center' }}>
          +{alarms.length - 50} altri allarmi...
        </p>
      )}
    </div>
  );
}

function DetailModal({ alarm, onClose }) {
  const raw = alarm.Raw_Data || {};
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h2><Info /> Dettagli Completi: {alarm['Alarm Code Name']}</h2>
          <button className="modal-close" onClick={onClose}><X /></button>
        </div>
        <div className="detail-grid">
          {Object.keys(raw).map(key => (
            <div key={key} className="detail-item">
              <strong>{key}</strong>
              <span>{raw[key]}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function KpiModal({ category, results, onClose, onAction }) {
  let alarms = [];
  if (category === 'CHRONIC') {
    alarms = results.alarms.filter(a => a.Is_Chronic);
  } else {
    alarms = results.alarms.filter(a => a.Action === category);
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" style={{ maxWidth: '1200px' }} onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Allarmi Filtrati: {category} ({alarms.length})</h2>
          <button className="modal-close" onClick={onClose}><X /></button>
        </div>
        <div style={{ overflowX: 'auto', maxHeight: '65vh' }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>Azione</th>
                <th>Sito</th>
                <th>Topologia</th>
                <th>Allarme</th>
                <th>Severità</th>
                <th>Data</th>
                <th>Azioni Operatore</th>
              </tr>
            </thead>
            <tbody>
              {alarms.map((alarm, idx) => (
                <tr key={idx}>
                  <td><span className={`badge badge-${alarm.Action}`}>{alarm.Action}</span></td>
                  <td>{alarm.ME}</td>
                  <td>{alarm.Topology_Role} <br/><small>{alarm['ME IP']}</small></td>
                  <td>{alarm['Alarm Code Name']}</td>
                  <td>{alarm['Alarm Severity']}</td>
                  <td>{alarm['Occurrence Time']}</td>
                  <td>
                    <div style={{ display: 'flex', gap: '0.3rem' }}>
                      <button className="row-action-btn ok" title="Trascurabile" onClick={() => onAction(alarm, 'TRASCURABILE')}><CheckCircle size={14} /></button>
                      <button className="row-action-btn mon" title="Monitora" onClick={() => onAction(alarm, 'MONITORA')}><Activity size={14} /></button>
                      <button className="row-action-btn esc" title="Scala Sempre" onClick={() => onAction(alarm, 'SCALA')}><AlertTriangle size={14} /></button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function NeHistoryModal({ meName, data, onClose }) {
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" style={{ maxWidth: '1100px' }} onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h2><Activity /> Dettaglio Sito (Storico): {meName}</h2>
          <button className="modal-close" onClick={onClose}><X /></button>
        </div>
        {!data ? (
          <div style={{ textAlign: 'center', padding: '2rem' }}>Caricamento storico in corso...</div>
        ) : (
          <div>
            <div className="glass-card" style={{ marginBottom: '1.5rem', background: 'rgba(59, 130, 246, 0.1)' }}>
              <h3 style={{ marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <CheckCircle size={18} /> Soluzioni Suggerite per il Link
              </h3>
              <ul style={{ paddingLeft: '1.5rem' }}>
                {(data.suggested_solutions || []).map((sol, i) => <li key={i}>{sol}</li>)}
              </ul>
            </div>
            
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem' }}>
              <div>
                <h4 style={{ marginBottom: '0.5rem', color: 'var(--accent-color)' }}>Sito Locale (A): {data.local_me}</h4>
                <div style={{ maxHeight: '400px', overflowY: 'auto' }}>
                  <table className="data-table">
                    <thead><tr><th>Allarme</th><th>Severità</th><th>Data</th></tr></thead>
                    <tbody>
                      {(data.local_alarms || []).map((a, i) => (
                        <tr key={i}><td>{a.Alarm_Code_Name}</td><td>{a.Alarm_Severity}</td><td>{a.Occurrence_Time}</td></tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
              <div>
                <h4 style={{ marginBottom: '0.5rem', color: 'var(--status-monitor)' }}>
                  Sito Remoto (B): {data.remote_me || 'Non trovato / P2MP'}
                </h4>
                <div style={{ maxHeight: '400px', overflowY: 'auto' }}>
                  {data.remote_alarms?.length > 0 ? (
                    <table className="data-table">
                      <thead><tr><th>Allarme</th><th>Severità</th><th>Data</th></tr></thead>
                      <tbody>
                        {data.remote_alarms.map((a, i) => (
                          <tr key={i}><td>{a.Alarm_Code_Name}</td><td>{a.Alarm_Severity}</td><td>{a.Occurrence_Time}</td></tr>
                        ))}
                      </tbody>
                    </table>
                  ) : (
                    <p style={{ color: 'var(--text-secondary)' }}>Nessun allarme remoto trovato nello storico.</p>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
