import { useState, useRef, useMemo, useEffect } from 'react';
import axios from 'axios';
import {
  UploadCloud, Activity, AlertTriangle, CheckCircle, Clock,
  Search, ArrowLeftRight, X, BookOpen, ShieldAlert, Zap,
  ChevronRight, RefreshCw, Star, Info, AlertCircle, CheckSquare,
  BarChart2, TrendingUp, Database, Award, CloudRain,
  ZoomIn, ZoomOut, Maximize2, Minimize2, ArrowUpDown
} from 'lucide-react';
import './index.css';

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// ─────────────────────────────────────────────────────────────────────────────
//  App
// ─────────────────────────────────────────────────────────────────────────────
function App() {
  const [appState, setAppState]       = useState('loading'); // loading | wizard | upload | results | compare | kb
  const [wizardAlarms, setWizardAlarms] = useState([]);
  const [files, setFiles]               = useState([]);
  const [loading, setLoading]         = useState(false);
  const [progress, setProgress]       = useState(0);
  const [results, setResults]         = useState(null);
  const [newAlarms, setNewAlarms]     = useState([]);
  const [showNewAlarms, setShowNewAlarms] = useState(false);
  const [filters, setFilters]         = useState({ action: '', me: '', topology: '', alarm: '', severity: '', macroarea: '' });
  const [sortOrder, setSortOrder]     = useState('');
  const [selectedSiteA, setSelectedSiteA] = useState(null);
  const [compareMode, setCompareMode] = useState(false);
  const [kbStats, setKbStats]         = useState(null);
  const [activeTab, setActiveTab]     = useState('alarms'); // alarms | kb | predictive
  const [predictiveData, setPredictiveData] = useState(null);
  const [predictiveLoading, setPredictiveLoading] = useState(false);
  const [predictiveError, setPredictiveError] = useState(null);
  const [showAll, setShowAll]         = useState(false);
  const [detailModalAlarm, setDetailModalAlarm] = useState(null);
  const [kpiModalCategory, setKpiModalCategory] = useState(null);
  const [neHistoryModal, setNeHistoryModal] = useState(null);
  const [neHistoryData, setNeHistoryData] = useState(null);
  const [toasts, setToasts] = useState([]);
  const showToast = (message, type = 'info') => {
    const id = Date.now() + Math.random();
    setToasts(prev => [...prev, { id, message, type }]);
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id));
    }, 5000);
  };
  const fileInputRef = useRef(null);

  // ── Performance MW state ────────────────────────────────────────────────────
  const [pmStatus, setPmStatus]         = useState(null);  // status DB PM
  const [alarmsStatus, setAlarmsStatus] = useState(null);  // status DB Alarms (FM)
  const [pmFiles, setPmFiles]             = useState([]);   // file PM selezionati per upload
  const [pmUploading, setPmUploading]   = useState(false);
  const [pmProgress, setPmProgress]     = useState(0);      // barra di progresso per upload PM
  const [compareTab, setCompareTab]     = useState('alarms'); // 'alarms' | 'performance'
  const [perfData, setPerfData]         = useState(null);   // risposta /api/performance/{site}
  const [perfLoading, setPerfLoading]   = useState(false);
  const [perfError, setPerfError]       = useState(null);
  const [selectedPerfDateFrom, setSelectedPerfDateFrom] = useState(''); // data inizio per analisi performance
  const [selectedPerfDateTo, setSelectedPerfDateTo]     = useState(''); // data fine per analisi performance
  const pmFileInputRef = useRef(null);

  // ── Caricamento iniziale ────────────────────────────────────────────────────
  useEffect(() => {
    (async () => {
      // Carica status PM e Alarmi in parallelo
      loadPmStatus();
      loadAlarmsStatus();
      try {
        const res = await axios.get(`${API}/api/first-launch`);
        const { wizard_completed, structural_alarms, kb_available } = res.data;
        if (!wizard_completed && kb_available && structural_alarms.length > 0) {
          setWizardAlarms(structural_alarms.map(a => ({ ...a, selected_action: a.suggested_action === 'TOLERABLE' ? 'TRASCURABILE' : 'MONITORA' })));
          setAppState('wizard');
        } else {
          try {
            const sessionRes = await axios.get(`${API}/api/last-session`);
            if (sessionRes.data.available) {
              const data = sessionRes.data.data;
              setResults(data);
              const na = data.new_alarms || [];
              setNewAlarms(na);
              if (na.length > 0) setShowNewAlarms(true);
              setAppState('results');
              loadKbStats();
            } else {
              setAppState('upload');
            }
          } catch (e) {
            setAppState('upload');
          }
        }
      } catch {
        setAppState('upload'); // backend non pronto con KB → vai diretto all'upload
      }
    })();
  }, []);

  // ── Upload file ─────────────────────────────────────────────────────────────
  const processFile = async () => {
    if (files.length === 0) return;
    setLoading(true);
    setProgress(0);
    const iv = setInterval(() => setProgress(p => p >= 90 ? p : p + Math.floor(Math.random() * 12) + 4), 400);
    const fd = new FormData();
    files.forEach(f => {
      fd.append('files', f);
    });
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
        loadAlarmsStatus();
      }, 500);
    } catch (err) {
      clearInterval(iv);
      showToast("Errore: " + (err.response?.data?.detail || err.message), 'error');
      setLoading(false);
      setProgress(0);
    }
  };

  const loadKbStats = async () => {
    try {
      const res = await axios.get(`${API}/api/kb/stats`);
      setKbStats(res.data);
    } catch (e) { console.error("Error loading stats", e); }
  };

  const loadPredictiveReport = async () => {
    setPredictiveLoading(true);
    setPredictiveError(null);
    try {
      const res = await axios.get(`${API}/api/predictive/report`);
      setPredictiveData(res.data);
    } catch (e) {
      setPredictiveError(e.response?.data?.detail || e.message);
    } finally {
      setPredictiveLoading(false);
    }
  };

  // ── Performance MW helpers ──────────────────────────────────────────────────
  const loadPmStatus = async () => {
    try {
      const res = await axios.get(`${API}/api/performance/status`);
      setPmStatus(res.data);
    } catch (e) { console.error("Error loading PM status", e); }
  };

  const loadAlarmsStatus = async () => {
    try {
      const res = await axios.get(`${API}/api/alarms/status`);
      setAlarmsStatus(res.data);
    } catch (e) { console.error("Error loading Alarms status", e); }
  };

  const uploadPmFile = async () => {
    if (pmFiles.length === 0) return;
    setPmUploading(true);
    setPmProgress(0);
    const iv = setInterval(() => setPmProgress(p => p >= 90 ? p : p + Math.floor(Math.random() * 8) + 2), 400);
    const fd = new FormData();
    pmFiles.forEach(f => {
      fd.append('files', f);
    });
    try {
      await axios.post(`${API}/api/upload/performance`, fd, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      clearInterval(iv);
      setPmProgress(100);
      setTimeout(async () => {
        setPmFiles([]);
        setPmProgress(0);
        setPmUploading(false);
        await loadPmStatus();
      }, 500);
    } catch (err) {
      clearInterval(iv);
      setPmProgress(0);
      setPmUploading(false);
      showToast("Errore upload PM: " + (err.response?.data?.detail || err.message), 'error');
    }
  };

  const loadPerformance = async (siteName, dateFrom = null, dateTo = null) => {
    if (!siteName) return;
    setPerfLoading(true);
    setPerfData(null);
    setPerfError(null);
    try {
      let query = '';
      const params = [];
      if (dateFrom) params.push(`date_from=${dateFrom}`);
      if (dateTo) params.push(`date_to=${dateTo}`);
      if (params.length > 0) {
        query = `?${params.join('&')}`;
      }
      const url = `${API}/api/performance/${encodeURIComponent(siteName)}${query}`;
      const res = await axios.get(url);
      setPerfData(res.data);
    } catch (err) {
      setPerfError(err.response?.data?.detail || err.message);
    } finally {
      setPerfLoading(false);
    }
  };

  useEffect(() => { if (appState === 'kb') loadKbStats(); }, [appState]);

  useEffect(() => {
    if (activeTab === 'predictive') {
      loadPredictiveReport();
    }
  }, [activeTab]);

  // Reset performance quando cambia il sito selezionato
  useEffect(() => {
    setPerfData(null);
    setPerfError(null);
    setCompareTab('alarms');
    setSelectedPerfDateFrom(''); // Reset alla visualizzazione complessiva
    setSelectedPerfDateTo('');
  }, [selectedSiteA]);



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
      showToast('Errore salvataggio preferenze: ' + e.message, 'error');
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
      showToast('Errore: ' + e.message, 'error');
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
      showToast('Errore: ' + e.message, 'error');
    }
  };

  // ── Filtering & Sorting ───────────────────────────────────────────────────────
  const sortedAndFilteredAlarms = useMemo(() => {
    if (!results) return [];
    
    // 1. Filtering
    const filtered = results.alarms.filter(a => {
      const matchAction   = !filters.action   || String(a.Action || '').toLowerCase().includes(filters.action.toLowerCase());
      const matchMe       = !filters.me       || String(a.ME || '').toLowerCase().includes(filters.me.toLowerCase());
      const matchMacroarea = !filters.macroarea || String(a.Macroarea || '').toLowerCase().includes(filters.macroarea.toLowerCase());
      const matchTopology = !filters.topology || String(a.Topology_Role || '').toLowerCase().includes(filters.topology.toLowerCase());
      const matchAlarm    = !filters.alarm    || String(a['Alarm Code Name'] || '').toLowerCase().includes(filters.alarm.toLowerCase());
      const matchSeverity = !filters.severity || String(a['Alarm Severity'] || '').toLowerCase().includes(filters.severity.toLowerCase());
      return matchAction && matchMe && matchMacroarea && matchTopology && matchAlarm && matchSeverity;
    });

    // 2. Sorting (A-Z / Z-A)
    if (!sortOrder) return filtered;

    return [...filtered].sort((a, b) => {
      let valA = '';
      let valB = '';
      switch (sortOrder) {
        case 'me-asc':
        case 'me-desc':
          valA = a.ME || '';
          valB = b.ME || '';
          break;
        case 'alarm-asc':
        case 'alarm-desc':
          valA = a['Alarm Code Name'] || '';
          valB = b['Alarm Code Name'] || '';
          break;
        case 'time-asc':
        case 'time-desc':
          valA = a['Occurrence Time'] || '';
          valB = b['Occurrence Time'] || '';
          break;
        default:
          return 0;
      }

      if (valA < valB) return sortOrder.endsWith('-asc') ? -1 : 1;
      if (valA > valB) return sortOrder.endsWith('-asc') ? 1 : -1;
      return 0;
    });
  }, [results, filters, sortOrder]);

  const displayAlarms = showAll ? sortedAndFilteredAlarms : sortedAndFilteredAlarms.slice(0, 200);

  // ── Site A/B pairing ────────────────────────────────────────────────────────
  const selectedSiteInfo = useMemo(() => {
    if (!selectedSiteA || !results) return null;
    const rec = results.alarms.find(a => a.ME === selectedSiteA);
    return rec ? { 
      ip: rec['ME IP'], 
      role: rec.Topology_Role,
      linkName: rec.Link_Name,
      macroarea: rec.Macroarea
    } : null;
  }, [selectedSiteA, results]);

  const siteAAlarms = useMemo(() => {
    if (!selectedSiteA || !results) return [];
    return results.alarms.filter(a => a.ME === selectedSiteA);
  }, [selectedSiteA, results]);

  const siteBAlarms = useMemo(() => {
    if (!selectedSiteInfo || !results) return [];
    const ip = selectedSiteInfo.ip;
    const linkName = selectedSiteInfo.linkName;
    if (linkName && linkName !== 'N/A' && !linkName.startsWith('Link Fallback Subnet')) {
      return results.alarms.filter(a => a.ME !== selectedSiteA && a.Link_Name === linkName);
    }
    return results.alarms.filter(a => a.ME !== selectedSiteA && isSameSubnet28(a['ME IP'], ip));
  }, [selectedSiteA, selectedSiteInfo, results]);

  const siteBName = useMemo(() => siteBAlarms.length ? siteBAlarms[0].ME : null, [siteBAlarms]);

  const clearCompare = () => { setSelectedSiteA(null); setCompareMode(false); };

  // removed fetchNeHistory since unused

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
              <button className={`tab-btn ${activeTab === 'predictive' ? 'active' : ''}`} onClick={() => { setActiveTab('predictive'); loadPredictiveReport(); }}>
                <ShieldAlert size={15} style={{ color: '#ef4444' }} /> AI Predictive (PdM)
              </button>
              <button className={`tab-btn ${activeTab === 'kb' ? 'active' : ''}`} onClick={() => { setActiveTab('kb'); loadKbStats(); }}>
                <BookOpen size={15} /> Knowledge Base
              </button>
            </div>
          )}
          {/* Badge stato DB Performance MW e Alarmi */}
          <div style={{ display: 'flex', gap: '0.8rem', flexWrap: 'wrap' }}>
            <div className="pm-status-badge" title="Database Alarmi (FM)">
              <AlertTriangle size={13} />
              {alarmsStatus?.available
                ? <span style={{ color: '#f59e0b' }}>FM DB: {alarmsStatus.total_rows?.toLocaleString()} righe{alarmsStatus.date_from ? ` · ${alarmsStatus.date_from}→${alarmsStatus.date_to}` : ''}</span>
                : <span style={{ color: '#888' }}>FM non caricato</span>}
            </div>
            <div className="pm-status-badge" title="Database Performance Management ZTE">
              <Database size={13} />
              {pmStatus?.available
                ? <span style={{ color: '#10b981' }}>PM DB: {pmStatus.total_rows?.toLocaleString()} righe{pmStatus.date_from ? ` · ${pmStatus.date_from}→${pmStatus.date_to}` : ''}</span>
                : <span style={{ color: '#888' }}>PM non caricato</span>}
            </div>
            {kbStats?.available && kbStats.last_rebuild_at && (
              <div className="pm-status-badge" title="Stato KB Allarmi">
                <BookOpen size={13} style={{ color: 'var(--accent-color)' }} />
                <span style={{ color: 'var(--accent-color)' }}>
                  KB Rebuild: {new Date(kbStats.last_rebuild_at).toLocaleDateString('it-IT')}
                </span>
              </div>
            )}
          </div>
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
        // UPLOAD VIEW — fragment obbligatorio per due elementi nella ternaria
        <>
          {/* Card principale Allarmi — funziona SEMPRE, indipendente dal PM */}
          <div className="glass-card upload-area"
               onDragOver={e => e.preventDefault()}
               onDrop={e => { e.preventDefault(); if (e.dataTransfer.files.length > 0) setFiles(Array.from(e.dataTransfer.files)); }}>
            <UploadCloud className="upload-icon" />
            <h2>Carica l'estrazione giornaliera degli allarmi</h2>
            <p style={{ color: 'var(--text-secondary)', marginTop: '0.5rem' }}>
              {files.length > 0 ? `📎 ${files.map(f => f.name).join(', ')}` : 'Trascina qui uno o più file Excel (.xlsx) oppure clicca per sfogliare'}
            </p>
            <input type="file" ref={fileInputRef} onChange={e => { if (e.target.files.length > 0) setFiles(Array.from(e.target.files)); }}
                   style={{ display: 'none' }} accept=".xlsx,.xls" multiple />
            <button className="upload-btn" onClick={() => fileInputRef.current.click()}>Seleziona File</button>
            {files.length > 0 && !loading && (
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

          {/* Card Performance MW — OPZIONALE, non blocca il flusso allarmi */}
          <div className="glass-card pm-upload-card">
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.8rem', marginBottom: '0.8rem' }}>
              <BarChart2 size={22} style={{ color: '#6366f1' }} />
              <div style={{ flex: 1 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                  <h3 style={{ margin: 0, fontSize: '1rem' }}>Performance MW — ZTE</h3>
                  <span style={{ fontSize: '0.7rem', background: 'rgba(99,102,241,0.2)', color: '#a5b4fc', padding: '0.15rem 0.5rem', borderRadius: '9999px', fontWeight: 600 }}>
                    OPZIONALE
                  </span>
                </div>
                <p style={{ margin: '0.2rem 0 0', color: 'var(--text-secondary)', fontSize: '0.82rem' }}>
                  {pmStatus?.available
                    ? `✅ DB attivo · ${pmStatus.total_rows?.toLocaleString()} righe · ${pmStatus.date_from} → ${pmStatus.date_to} · ${pmStatus.sites?.length} siti`
                    : 'Carica il file Excel PM ZTE per abilitare il tab "Performance MW" nella vista confronto siti.'}
                </p>
              </div>
            </div>
            <div style={{ display: 'flex', gap: '0.8rem', alignItems: 'center', flexWrap: 'wrap' }}>
              <input type="file" ref={pmFileInputRef}
                onChange={e => { if (e.target.files.length > 0) setPmFiles(Array.from(e.target.files)); }}
                style={{ display: 'none' }} accept=".xlsx,.xls" multiple />
              <button className="upload-btn"
                style={{ background: 'rgba(99,102,241,0.2)', border: '1px solid rgba(99,102,241,0.4)', fontSize: '0.82rem', padding: '0.4rem 1rem', marginTop: 0 }}
                onClick={() => pmFileInputRef.current.click()}>
                <Database size={13} style={{ marginRight: '0.4rem' }} />
                {pmFiles.length > 0 ? `📎 ${pmFiles.length} file selezionati` : 'Seleziona file PM (.xlsx)'}
              </button>
              {pmFiles.length > 0 && !pmUploading && (
                <button className="upload-btn"
                  style={{ background: '#6366f1', fontSize: '0.82rem', padding: '0.4rem 1rem', marginTop: 0 }}
                  onClick={uploadPmFile}>
                  <Zap size={13} style={{ marginRight: '0.3rem' }} /> Carica nel DB PM
                </button>
              )}
            </div>
            {pmUploading && (
              <div className="progress-container" style={{ marginTop: '1.2rem', border: '1px solid rgba(99,102,241,0.2)' }}>
                <div className="progress-bar" style={{ width: `${pmProgress}%`, background: 'linear-gradient(90deg, #6366f1, #818cf8)' }} />
                <div className="progress-text" style={{ color: '#a5b4fc' }}>In corso di elaborazione ed ingestion... {pmProgress}%</div>
              </div>
            )}
          </div>
        </>

      ) : compareMode && selectedSiteA ? (
        // COMPARE VIEW — con tab Allarmi / Performance MW
        <div>
          <div className="compare-header">
            <h2 className="compare-title">
              <ArrowLeftRight size={22} style={{ color: 'var(--accent-color)' }} />
              Confronto Link Radio — {selectedSiteA}
            </h2>
            <div style={{ display: 'flex', gap: '0.8rem', alignItems: 'center' }}>
              {/* Tab bar Allarmi / Performance */}
              <div className="compare-tab-bar">
                <button
                  className={`compare-tab-btn ${compareTab === 'alarms' ? 'active' : ''}`}
                  onClick={() => setCompareTab('alarms')}>
                  <Activity size={14} /> Allarmi
                </button>
                <button
                  className={`compare-tab-btn ${compareTab === 'performance' ? 'active' : ''}`}
                  onClick={() => {
                    setCompareTab('performance');
                    if (!perfData && !perfLoading) loadPerformance(selectedSiteA, selectedPerfDateFrom, selectedPerfDateTo);
                  }}>
                  <BarChart2 size={14} /> Performance MW
                  {perfData?.available && (
                    <span className={`outcome-dot outcome-${perfData.outcome?.toLowerCase()}`} />
                  )}
                </button>
              </div>
              <button className="upload-btn" onClick={clearCompare} style={{ background: 'rgba(255,255,255,0.1)', display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.85rem', padding: '0.4rem 0.9rem' }}>
                <X size={14} /> Chiudi
              </button>
            </div>
          </div>

          {compareTab === 'alarms' ? (
            <div className="compare-grid">
              <div className="glass-card compare-panel">
                <div className="compare-panel-header site-a">
                  <span className="site-badge">SITO SELEZIONATO ({selectedSiteInfo?.role || 'A'})</span>
                  <strong>{selectedSiteA}</strong>
                  <small>{selectedSiteInfo?.ip}</small>
                  {selectedSiteInfo?.linkName && (
                    <div style={{ marginTop: '0.4rem', fontSize: '0.8rem', opacity: 0.9, borderTop: '1px dashed rgba(255,255,255,0.15)', paddingTop: '0.4rem' }}>
                      <strong>Link:</strong> {selectedSiteInfo.linkName}
                      {selectedSiteInfo.macroarea && <span style={{ marginLeft: '0.8rem', background: 'rgba(255,255,255,0.15)', padding: '0.1rem 0.4rem', borderRadius: '4px', color: '#60a5fa' }}>📍 {selectedSiteInfo.macroarea}</span>}
                    </div>
                  )}
                </div>
                <SiteAlarmTable alarms={siteAAlarms} />
              </div>
              <div className="glass-card compare-panel">
                <div className="compare-panel-header site-b">
                  <span className="site-badge">SITO CONNESSO ({siteBAlarms[0]?.Topology_Role || 'B'})</span>
                  <strong>{siteBName || '—'}</strong>
                  <small>{siteBAlarms[0]?.['ME IP'] || ''}</small>
                  {siteBAlarms[0]?.Link_Name && (
                    <div style={{ marginTop: '0.4rem', fontSize: '0.8rem', opacity: 0.9, borderTop: '1px dashed rgba(255,255,255,0.15)', paddingTop: '0.4rem' }}>
                      <strong>Link:</strong> {siteBAlarms[0].Link_Name}
                      {siteBAlarms[0].Macroarea && <span style={{ marginLeft: '0.8rem', background: 'rgba(255,255,255,0.15)', padding: '0.1rem 0.4rem', borderRadius: '4px', color: '#60a5fa' }}>📍 {siteBAlarms[0].Macroarea}</span>}
                    </div>
                  )}
                </div>
                {siteBAlarms.length > 0
                  ? <SiteAlarmTable alarms={siteBAlarms} />
                  : <p style={{ padding: '2rem', color: 'var(--text-secondary)', textAlign: 'center' }}>Nessun allarme trovato per l'altro capo del link.</p>}
              </div>
            </div>
          ) : (
            <PerformanceView
              siteName={selectedSiteA}
              data={perfData}
              loading={perfLoading}
              error={perfError}
              pmAvailable={pmStatus?.available}
              pmStatus={pmStatus}
              selectedDateFrom={selectedPerfDateFrom}
              selectedDateTo={selectedPerfDateTo}
              onDateChange={(dateFrom, dateTo) => {
                setSelectedPerfDateFrom(dateFrom || '');
                setSelectedPerfDateTo(dateTo || '');
                loadPerformance(selectedSiteA, dateFrom, dateTo);
              }}
              onRetry={() => loadPerformance(selectedSiteA, selectedPerfDateFrom, selectedPerfDateTo)}
            />
          )}
        </div>

      ) : activeTab === 'kb' ? (
        // KB VIEW
        <KBView stats={kbStats} onRefresh={loadKbStats} />

      ) : activeTab === 'predictive' ? (
        // PREDICTIVE VIEW
        <PredictiveView
          data={predictiveData}
          loading={predictiveLoading}
          error={predictiveError}
          onRefresh={loadPredictiveReport}
        />

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
              <span style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>{sortedAndFilteredAlarms.length} risultati</span>
            </div>
            <div className="filters-row">
              <FilterInput icon={<Search size={14}/>} placeholder="Azione..." value={filters.action} onChange={v => setFilters(f => ({ ...f, action: v }))} />
              <FilterInput icon={<Search size={14}/>} placeholder="Sito (ME)..." value={filters.me} onChange={v => setFilters(f => ({ ...f, me: v }))} />
              <FilterInput icon={<Search size={14}/>} placeholder="Macroarea..." value={filters.macroarea} onChange={v => setFilters(f => ({ ...f, macroarea: v }))} />
              <FilterInput icon={<Search size={14}/>} placeholder="Topologia..." value={filters.topology} onChange={v => setFilters(f => ({ ...f, topology: v }))} />
              <FilterInput icon={<Search size={14}/>} placeholder="Allarme..." value={filters.alarm} onChange={v => setFilters(f => ({ ...f, alarm: v }))} />
              <FilterInput icon={<Search size={14}/>} placeholder="Severità..." value={filters.severity} onChange={v => setFilters(f => ({ ...f, severity: v }))} />
              
              {/* Filtro Ordinamento A-Z / Z-A */}
              <div className="filter-input-wrapper" style={{ minWidth: '160px' }}>
                <ArrowUpDown size={14} style={{ color: 'var(--text-secondary)' }} />
                <select
                  value={sortOrder}
                  onChange={e => setSortOrder(e.target.value)}
                  style={{
                    background: 'none',
                    border: 'none',
                    color: 'var(--text-primary)',
                    fontSize: '0.82rem',
                    cursor: 'pointer',
                    outline: 'none',
                    width: '100%'
                  }}
                >
                  <option value="" style={{ background: 'var(--bg-color)' }}>Ordina per...</option>
                  <option value="me-asc" style={{ background: 'var(--bg-color)' }}>Sito (A-Z)</option>
                  <option value="me-desc" style={{ background: 'var(--bg-color)' }}>Sito (Z-A)</option>
                  <option value="alarm-asc" style={{ background: 'var(--bg-color)' }}>Allarme (A-Z)</option>
                  <option value="alarm-desc" style={{ background: 'var(--bg-color)' }}>Allarme (Z-A)</option>
                  <option value="time-desc" style={{ background: 'var(--bg-color)' }}>Data (Più recente)</option>
                  <option value="time-asc" style={{ background: 'var(--bg-color)' }}>Data (Meno recente)</option>
                </select>
              </div>

              {([...Object.values(filters), sortOrder]).some(v => v) && (
                <button className="feedback-btn" onClick={() => { setFilters({ action:'', me:'', topology:'', alarm:'', severity:'', macroarea:'' }); setSortOrder(''); }}>
                  <X size={14}/> Reset
                </button>
              )}
            </div>

            <table className="data-table">
              <thead>
                <tr>
                  <th>Azione Agente</th>
                  <th>Sito (ME)</th>
                  <th>Link Radio / Area</th>
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
                      {alarm.Topology_Role === 'Local (Site A)' || alarm.Topology_Role === 'Remote (Site B)' || alarm.Topology_Role.startsWith('Node') ? (
                        <button className="site-link" title="Clicca per confrontare con il sito connesso"
                          onClick={() => { setSelectedSiteA(alarm.ME); setCompareMode(true); }}>
                          {alarm.ME}
                          <ArrowLeftRight size={12} style={{ marginLeft: '0.4rem', opacity: 0.6 }} />
                        </button>
                      ) : <span>{alarm.ME}</span>}
                    </td>
                    <td>
                      <div style={{ fontSize: '0.82rem', fontWeight: 500 }}>{alarm.Link_Name || 'N/A'}</div>
                      {alarm.Macroarea && alarm.Macroarea !== 'Sconosciuta' && (
                        <span style={{
                          display: 'inline-block',
                          fontSize: '0.72rem',
                          background: 'rgba(59, 130, 246, 0.15)',
                          color: '#60a5fa',
                          padding: '0.1rem 0.4rem',
                          borderRadius: '4px',
                          marginTop: '0.25rem',
                          fontWeight: 600
                        }}>
                          📍 {alarm.Macroarea}
                        </span>
                      )}
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
            {!showAll && sortedAndFilteredAlarms.length > 200 && (
              <div style={{ textAlign: 'center', marginTop: '1rem' }}>
                <p style={{ color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>
                  Mostrando 200 di {sortedAndFilteredAlarms.length} risultati
                </p>
                <button className="feedback-btn" onClick={() => setShowAll(true)}>Mostra tutti i risultati</button>
              </div>
            )}
            {showAll && sortedAndFilteredAlarms.length > 200 && (
              <div style={{ textAlign: 'center', marginTop: '1rem' }}>
                <p style={{ color: 'var(--text-secondary)' }}>Tutti i {sortedAndFilteredAlarms.length} risultati mostrati.</p>
              </div>
            )}
          </div>

          <div style={{ marginTop: '2rem', textAlign: 'center' }}>
            <button className="upload-btn" onClick={async () => { 
              await axios.delete(`${API}/api/last-session`).catch(() => {});
              setResults(null); 
              setNewAlarms([]); 
              setFiles([]);
              setPmFiles([]);
              setShowNewAlarms(false); 
              setFilters({ action:'', me:'', topology:'', alarm:'', severity:'', macroarea:'' }); 
              setSortOrder('');
              setAppState('upload'); 
            }}>
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

      {/* ── Toast Notifications ── */}
      <div style={{
        position: 'fixed',
        bottom: '20px',
        right: '20px',
        zIndex: 9999,
        display: 'flex',
        flexDirection: 'column',
        gap: '10px',
        maxWidth: '350px'
      }}>
        {toasts.map(t => (
          <div key={t.id} style={{
            background: t.type === 'error' ? '#ef4444' : (t.type === 'success' ? '#10b981' : '#3b82f6'),
            color: '#fff',
            padding: '12px 18px',
            borderRadius: '8px',
            boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
            fontSize: '0.85rem',
            fontWeight: 500,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '10px'
          }}>
            <span>{t.message}</span>
            <button onClick={() => setToasts(prev => prev.filter(x => x.id !== t.id))} style={{
              background: 'none',
              border: 'none',
              color: '#fff',
              cursor: 'pointer',
              fontWeight: 'bold',
              padding: 0
            }}><X size={14} /></button>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
//  Wizard Prima Apertura
// ─────────────────────────────────────────────────────────────────────────────
function WizardView({ alarms, setAlarms, onSubmit, onSkip }) {
  const [step, setStep]     = useState(0);   // 0=intro, 1=lista, 2=confirm
  const [saving, setSaving] = useState(false);
  const [filter, setFilter] = useState('');
  const [sortOrder, setSortOrder] = useState('score-desc'); // 'score-desc' | 'alpha-asc' | 'alpha-desc' | 'occ-desc'

  const setAction = (alarmName, action) => {
    setAlarms(prev => prev.map(a => a.alarm_code_name === alarmName ? { ...a, selected_action: action } : a));
  };

  const handleSubmit = async () => {
    setSaving(true);
    await onSubmit();
  };

  const processedAlarms = useMemo(() => {
    const filtered = alarms.filter(a =>
      !filter || a.alarm_code_name?.toLowerCase().includes(filter.toLowerCase())
    );
    return [...filtered].sort((a, b) => {
      if (sortOrder === 'alpha-asc') return (a.alarm_code_name || '').localeCompare(b.alarm_code_name || '');
      if (sortOrder === 'alpha-desc') return (b.alarm_code_name || '').localeCompare(a.alarm_code_name || '');
      if (sortOrder === 'occ-desc') return (b.total_occurrences || 0) - (a.total_occurrences || 0);
      return (b.filterability_score || 0) - (a.filterability_score || 0);
    });
  }, [alarms, filter, sortOrder]);

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
              
              {/* Filtro e ordinamento */}
              <div style={{ display: 'flex', gap: '0.8rem', margin: '1rem 0', flexWrap: 'wrap' }}>
                <div className="filter-input-wrapper" style={{ flex: 1, minWidth: '200px' }}>
                  <Search size={14} />
                  <input
                    className="filter-input"
                    placeholder="Cerca allarme..."
                    value={filter}
                    onChange={e => setFilter(e.target.value)}
                  />
                  {filter && <button className="filter-clear" onClick={() => setFilter('')}><X size={12}/></button>}
                </div>
                <div className="filter-input-wrapper" style={{ minWidth: '180px' }}>
                  <ArrowUpDown size={14} style={{ color: 'var(--text-secondary)' }} />
                  <select
                    value={sortOrder}
                    onChange={e => setSortOrder(e.target.value)}
                    style={{
                      background: 'none',
                      border: 'none',
                      color: 'var(--text-primary)',
                      fontSize: '0.82rem',
                      cursor: 'pointer',
                      outline: 'none',
                      width: '100%'
                    }}
                  >
                    <option value="score-desc" style={{ background: 'var(--bg-color)' }}>Ordina: Score</option>
                    <option value="alpha-asc" style={{ background: 'var(--bg-color)' }}>Ordina: A-Z</option>
                    <option value="alpha-desc" style={{ background: 'var(--bg-color)' }}>Ordina: Z-A</option>
                    <option value="occ-desc" style={{ background: 'var(--bg-color)' }}>Ordina: Occorrenze</option>
                  </select>
                </div>
              </div>

              <div className="action-legend">
                {actions.map(a => (
                  <span key={a.key} style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', fontSize: '0.8rem' }}>
                    {a.icon} {a.label} — {a.desc}
                  </span>
                ))}
              </div>
            </div>

            <div className="wizard-alarms-list">
              {processedAlarms.map((alarm) => (
                <div key={alarm.alarm_code_name} className="wizard-alarm-row">
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
                        onClick={() => setAction(alarm.alarm_code_name, a.key)}
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
  const [alarmFilter, setAlarmFilter] = useState('');
  const [alarmSort, setAlarmSort] = useState('score-desc'); // 'score-desc' | 'alpha-asc' | 'alpha-desc' | 'occ-desc'
  const [neFilter, setNeFilter] = useState('');
  const [neSort, setNeSort] = useState('risk-desc'); // 'risk-desc' | 'alpha-asc' | 'alpha-desc' | 'occ-desc'

  const filteredTopAlarms = useMemo(() => {
    const list = stats?.top_structural_alarms || [];
    const filtered = list.filter(a => 
      !alarmFilter || a.name?.toLowerCase().includes(alarmFilter.toLowerCase())
    );
    return [...filtered].sort((a, b) => {
      if (alarmSort === 'alpha-asc') return (a.name || '').localeCompare(b.name || '');
      if (alarmSort === 'alpha-desc') return (b.name || '').localeCompare(a.name || '');
      if (alarmSort === 'occ-desc') return (b.occurrences || 0) - (a.occurrences || 0);
      return (b.score || 0) - (a.score || 0);
    });
  }, [stats?.top_structural_alarms, alarmFilter, alarmSort]);

  const filteredTopNe = useMemo(() => {
    const list = stats?.top_risk_ne || [];
    const filtered = list.filter(ne => 
      !neFilter || ne.name?.toLowerCase().includes(neFilter.toLowerCase())
    );
    return [...filtered].sort((a, b) => {
      if (neSort === 'alpha-asc') return (a.name || '').localeCompare(b.name || '');
      if (neSort === 'alpha-desc') return (b.name || '').localeCompare(a.name || '');
      if (neSort === 'occ-desc') return (b.total_alarms || 0) - (a.total_alarms || 0);
      return (b.risk_score || 0) - (a.risk_score || 0);
    });
  }, [stats?.top_risk_ne, neFilter, neSort]);

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

      {/* Controllo Rebuild Completo */}
      <div className="glass-card" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '1rem 1.5rem', marginBottom: '1.5rem', border: '1px solid rgba(139, 92, 246, 0.3)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.8rem' }}>
          <RefreshCw size={18} style={{ color: 'var(--accent-color)' }} className={stats.last_rebuild_status === 'RUNNING' ? 'spin-icon' : ''} />
          <div>
            <h4 style={{ margin: 0, fontSize: '0.9rem' }}>Allineamento & Rebuild KB Storica</h4>
            <p style={{ margin: '0.2rem 0 0', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
              Stato Ultimo Rebuild: {' '}
              <strong style={{ color: stats.last_rebuild_status === 'SUCCESS' ? '#10b981' : '#f59e0b' }}>
                {stats.last_rebuild_status || 'SUCCESS'}
              </strong>
              {stats.last_rebuild_at && ` · completato il ${new Date(stats.last_rebuild_at).toLocaleString('it-IT')}`}
            </p>
          </div>
        </div>
        <button 
          className="upload-btn" 
          style={{ background: 'var(--accent-color)', fontSize: '0.82rem', padding: '0.4rem 1rem', marginTop: 0 }}
          onClick={async () => {
            try {
              await axios.post(`${API}/api/kb/rebuild`);
              showToast("Rebuild completo avviato in background. L'operazione potrebbe richiedere alcuni secondi. Ricarica le statistiche per aggiornare lo stato.", 'success');
              onRefresh();
            } catch (err) {
              showToast("Errore nell'avvio del rebuild: " + err.message, 'error');
            }
          }}
        >
          Avvia Rebuild Completo
        </button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem', marginTop: '0' }}>
        {/* Top allarmi strutturali */}
        <div className="glass-card data-table-container">
          <div className="table-header-row" style={{ flexWrap: 'wrap', gap: '0.8rem' }}>
            <div>
              <h3>🔵 Allarmi Strutturali (Filtrabili)</h3>
              <span style={{ color: 'var(--text-secondary)', fontSize: '0.8rem' }}>Score ≥ {Math.round((stats.filterability_threshold || 0.85) * 100)}%</span>
            </div>
            <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', alignItems: 'center' }}>
              <div className="filter-input-wrapper" style={{ padding: '0.25rem 0.5rem', minWidth: '120px' }}>
                <Search size={12} />
                <input
                  className="filter-input"
                  placeholder="Cerca allarme..."
                  value={alarmFilter}
                  onChange={e => setAlarmFilter(e.target.value)}
                  style={{ fontSize: '0.75rem' }}
                />
                {alarmFilter && <button className="filter-clear" onClick={() => setAlarmFilter('')}><X size={10}/></button>}
              </div>
              <div className="filter-input-wrapper" style={{ padding: '0.25rem 0.5rem', minWidth: '130px' }}>
                <ArrowUpDown size={12} />
                <select
                  value={alarmSort}
                  onChange={e => setAlarmSort(e.target.value)}
                  style={{
                    background: 'none',
                    border: 'none',
                    color: 'var(--text-primary)',
                    fontSize: '0.75rem',
                    cursor: 'pointer',
                    outline: 'none',
                    width: '100%'
                  }}
                >
                  <option value="score-desc" style={{ background: 'var(--bg-color)' }}>Ordina: Score</option>
                  <option value="alpha-asc" style={{ background: 'var(--bg-color)' }}>Ordina: A-Z</option>
                  <option value="alpha-desc" style={{ background: 'var(--bg-color)' }}>Ordina: Z-A</option>
                  <option value="occ-desc" style={{ background: 'var(--bg-color)' }}>Ordina: Occorrenze</option>
                </select>
              </div>
            </div>
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
              {filteredTopAlarms.map((a, i) => (
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
          <div className="table-header-row" style={{ flexWrap: 'wrap', gap: '0.8rem' }}>
            <div>
              <h3>🔴 NE ad Alto Rischio (Filtrabili)</h3>
              <span style={{ color: 'var(--text-secondary)', fontSize: '0.8rem' }}>Ultimi {stats.history_days} giorni</span>
            </div>
            <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', alignItems: 'center' }}>
              <div className="filter-input-wrapper" style={{ padding: '0.25rem 0.5rem', minWidth: '120px' }}>
                <Search size={12} />
                <input
                  className="filter-input"
                  placeholder="Cerca NE..."
                  value={neFilter}
                  onChange={e => setNeFilter(e.target.value)}
                  style={{ fontSize: '0.75rem' }}
                />
                {neFilter && <button className="filter-clear" onClick={() => setNeFilter('')}><X size={10}/></button>}
              </div>
              <div className="filter-input-wrapper" style={{ padding: '0.25rem 0.5rem', minWidth: '130px' }}>
                <ArrowUpDown size={12} />
                <select
                  value={neSort}
                  onChange={e => setNeSort(e.target.value)}
                  style={{
                    background: 'none',
                    border: 'none',
                    color: 'var(--text-primary)',
                    fontSize: '0.75rem',
                    cursor: 'pointer',
                    outline: 'none',
                    width: '100%'
                  }}
                >
                  <option value="risk-desc" style={{ background: 'var(--bg-color)' }}>Ordina: Rischio</option>
                  <option value="alpha-asc" style={{ background: 'var(--bg-color)' }}>Ordina: A-Z</option>
                  <option value="alpha-desc" style={{ background: 'var(--bg-color)' }}>Ordina: Z-A</option>
                  <option value="occ-desc" style={{ background: 'var(--bg-color)' }}>Ordina: Allarmi</option>
                </select>
              </div>
            </div>
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
              {filteredTopNe.map((ne, i) => (
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
//  AI Predictive View
// ─────────────────────────────────────────────────────────────────────────────
function PredictiveView({ data, loading, error, onRefresh }) {
  const [searchTerm, setSearchTerm] = useState('');
  
  if (loading) return (
    <div className="glass-card" style={{ textAlign: 'center', padding: '3rem' }}>
      <RefreshCw size={32} className="spin-icon" style={{ color: 'var(--accent-color)', marginBottom: '1rem' }} />
      <p>Analisi predittiva in corso con il PdM Engine...</p>
    </div>
  );

  if (error) return (
    <div className="glass-card" style={{ textAlign: 'center', padding: '3rem', border: '1px solid rgba(239, 68, 68, 0.3)' }}>
      <AlertTriangle size={40} style={{ color: '#ef4444', marginBottom: '1rem' }} />
      <h3>Errore durante il calcolo predittivo</h3>
      <p style={{ color: 'var(--text-secondary)' }}>{error}</p>
      <button className="upload-btn" onClick={onRefresh} style={{ background: 'var(--accent-color)', marginTop: '1rem' }}>Riprova</button>
    </div>
  );

  if (!data || !data.predictions || data.predictions.length === 0) return (
    <div className="glass-card" style={{ textAlign: 'center', padding: '3rem' }}>
      <Info size={40} style={{ color: '#6366f1', marginBottom: '1rem' }} />
      <h3>Nessuna predizione disponibile</h3>
      <p style={{ color: 'var(--text-secondary)' }}>
        Carica un file di allarmi (FM) nella dashboard per calcolare le predizioni in tempo reale.
      </p>
      <button className="upload-btn" onClick={onRefresh} style={{ background: 'var(--accent-color)', marginTop: '1rem' }}>Calcola Ora</button>
    </div>
  );

  const predictions = data?.predictions || [];
  const filteredPredictions = predictions.filter(p => 
    p && (
      !searchTerm || 
      String(p.Alarm_Name || '').toLowerCase().includes(searchTerm.toLowerCase()) || 
      String(p.Risk_Level || '').toLowerCase().includes(searchTerm.toLowerCase())
    )
  );
  
  const urgentCount = predictions.filter(p => p && (p.Risk_Level === 'CRITICAL' || p.Risk_Level === 'HIGH')).length;
  
  const getRiskColor = (level) => {
    switch (level) {
      case 'CRITICAL': return '#ef4444';
      case 'HIGH': return '#f59e0b';
      case 'MEDIUM': return '#3b82f6';
      default: return '#10b981';
    }
  };

  return (
    <div>
      {/* KPI Cards */}
      <div className="dashboard-grid">
        <div className="glass-card kpi-card">
          <Activity className="upload-icon" style={{ color: 'var(--text-secondary)' }} />
          <div className="kpi-value">{predictions.length}</div>
          <div className="kpi-label">Pattern Valutati</div>
        </div>
        <div className="glass-card kpi-card" style={{ borderTop: `4px solid ${urgentCount > 0 ? '#ef4444' : '#10b981'}` }}>
          <AlertCircle className="upload-icon" style={{ color: urgentCount > 0 ? '#ef4444' : '#10b981' }} />
          <div className="kpi-value" style={{ color: urgentCount > 0 ? '#ef4444' : '#10b981' }}>{urgentCount}</div>
          <div className="kpi-label">Rischi Elevati (Critical/High)</div>
        </div>
        <div className="glass-card kpi-card">
          <Award className="upload-icon" style={{ color: '#8b5cf6' }} />
          <div className="kpi-value" style={{ color: '#8b5cf6' }}>
            {predictions.length > 0 
              ? (predictions.reduce((acc, curr) => acc + (parseFloat(curr?.Risk_Score) || 0), 0) / predictions.length * 100).toFixed(0)
              : 0}%
          </div>
          <div className="kpi-label">Risk Score Medio</div>
        </div>
        <div className="glass-card kpi-card">
          <Clock className="upload-icon" style={{ color: '#f59e0b' }} />
          <div className="kpi-value" style={{ color: '#f59e0b' }}>
            {predictions.some(p => p && String(p.Predicted_Outcome || '').includes('<12h')) ? '<12 ore' : '<24 ore'}
          </div>
          <div className="kpi-label">TTF Minimo Stimato</div>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1.8fr 1.2fr', gap: '1.5rem', marginTop: '1.5rem' }}>
        {/* Tabella dei rischi predetti */}
        <div className="glass-card data-table-container">
          <div className="table-header-row" style={{ flexWrap: 'wrap', gap: '0.8rem' }}>
            <div>
              <h3>🔮 Analisi dei Rischi e TTF (Time-to-Failure)</h3>
              <span style={{ color: 'var(--text-secondary)', fontSize: '0.82rem' }}>
                Allineato in tempo reale con l'estrazione allarmi (m1, m2, m3)
              </span>
            </div>
            <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
              <div className="filter-input-wrapper" style={{ padding: '0.25rem 0.5rem', minWidth: '160px' }}>
                <Search size={12} />
                <input
                  className="filter-input"
                  placeholder="Cerca pattern..."
                  value={searchTerm}
                  onChange={e => setSearchTerm(e.target.value)}
                  style={{ fontSize: '0.75rem' }}
                />
                {searchTerm && <button className="filter-clear" onClick={() => setSearchTerm('')}><X size={10}/></button>}
              </div>
              <button className="row-action-btn" onClick={onRefresh} title="Ricalcola Predizioni" style={{ height: '30px', width: '30px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <RefreshCw size={14} />
              </button>
            </div>
          </div>
          <table className="data-table">
            <thead>
              <tr>
                <th>Alarm Pattern</th>
                <th>Risk Level</th>
                <th>Score</th>
                <th>Siti / Apparati Impattati</th>
                <th>Predicted Failure Outcome</th>
              </tr>
            </thead>
            <tbody>
              {filteredPredictions.map((p, idx) => {
                if (!p) return null;
                const scorePercent = Math.round((parseFloat(p.Risk_Score) || 0) * 100);
                return (
                  <tr key={idx}>
                    <td style={{ fontSize: '0.78rem', fontWeight: 500, maxWidth: '280px', wordBreak: 'break-word' }}>
                      {p.Alarm_Name}
                    </td>
                    <td>
                      <span 
                        className={`flag-badge`} 
                        style={{ 
                          backgroundColor: `${getRiskColor(p.Risk_Level)}15`, 
                          color: getRiskColor(p.Risk_Level),
                          border: `1px solid ${getRiskColor(p.Risk_Level)}30` 
                        }}
                      >
                        {p.Risk_Level}
                      </span>
                    </td>
                    <td>
                      <div className="score-bar-wrap">
                        <div 
                          className="score-bar" 
                          style={{ 
                            width: `${scorePercent}%`,
                            backgroundColor: getRiskColor(p.Risk_Level)
                          }} 
                        />
                        <span style={{ fontWeight: 'bold', fontSize: '0.8rem' }}>{scorePercent}%</span>
                      </div>
                    </td>
                    <td style={{ fontSize: '0.76rem', color: 'var(--text-secondary)', maxWidth: '200px', wordBreak: 'break-word' }}>
                      {p.Impacted_Devices || '—'}
                    </td>
                    <td style={{ fontSize: '0.75rem', color: '#ff6b6b', fontWeight: 600 }}>
                      {p.Predicted_Outcome}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {/* Breakdown Metodologia & Report Testuale */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          {/* Methodology Breakdown */}
          <div className="glass-card" style={{ padding: '1.5rem' }}>
            <h3 style={{ margin: '0 0 1rem 0', color: 'var(--accent-color)', fontSize: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <BookOpen size={18} /> Metodologia di Calcolo Predittivo (m1, m2, m3)
            </h3>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', lineHeight: 1.5, margin: '0 0 1rem 0' }}>
              La formula predittiva calcola il <strong>Risk Score</strong> ponderando la firma temporale di ciascun allarme secondo tre features fondamentali:
            </p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.8rem', fontSize: '0.82rem' }}>
              <div style={{ background: 'rgba(255,255,255,0.02)', padding: '0.6rem 0.8rem', borderRadius: '8px', borderLeft: '3px solid var(--accent-color)', borderTop: '1px solid rgba(255,255,255,0.02)' }}>
                <strong>m1 (Presence):</strong> 1.0 se l'allarme è attivo nella finestra di monitoraggio.
              </div>
              <div style={{ background: 'rgba(255,255,255,0.02)', padding: '0.6rem 0.8rem', borderRadius: '8px', borderLeft: '3px solid #10b981', borderTop: '1px solid rgba(255,255,255,0.02)' }}>
                <strong>m2 (Duration Ratio):</strong> Rapporto di presenza nella finestra a 15 minuti. Valori vicini a 1.0 indicano persistenza e potenziale guasto fisico.
              </div>
              <div style={{ background: 'rgba(255,255,255,0.02)', padding: '0.6rem 0.8rem', borderRadius: '8px', borderLeft: '3px solid #f59e0b', borderTop: '1px solid rgba(255,255,255,0.02)' }}>
                <strong>m3 (Frequency/Flapping):</strong> Numero di ripetizioni dell'allarme. Elevata frequenza indica instabilità del mezzo trasmissivo.
              </div>
            </div>
          </div>

          {/* Markdown Report Preview */}
          <div className="glass-card" style={{ padding: '1.5rem', flex: 1, maxHeight: '420px', overflowY: 'auto', display: 'flex', flexDirection: 'column' }}>
            <h3 style={{ margin: '0 0 0.8rem 0', fontSize: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <ShieldAlert size={18} style={{ color: '#ef4444' }} /> Report Generato per i Tecnici
            </h3>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.8rem', margin: '0 0 1rem 0' }}>
              Questo report in formato Markdown viene salvato in <code>PREDICTION_REPORT.md</code> per essere allegato alle commesse di manutenzione.
            </p>
            <pre style={{ 
              background: 'rgba(0,0,0,0.3)', 
              padding: '1rem', 
              borderRadius: '8px', 
              fontFamily: 'monospace', 
              fontSize: '0.72rem', 
              color: '#a5b4fc', 
              whiteSpace: 'pre-wrap',
              border: '1px solid rgba(255,255,255,0.05)',
              margin: 0,
              flex: 1
            }}>
              {data.markdown}
            </pre>
          </div>
        </div>
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
  const [searchTerm, setSearchTerm] = useState('');
  const [sortOrder, setSortOrder] = useState('time-desc'); // 'time-desc' | 'time-asc' | 'alpha-asc' | 'alpha-desc'

  const processedAlarms = useMemo(() => {
    // 1. Filter
    const filtered = alarms.filter(a => 
      !searchTerm || 
      String(a['Alarm Code Name'] || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
      String(a.Action || '').toLowerCase().includes(searchTerm.toLowerCase())
    );

    // 2. Sort
    return [...filtered].sort((a, b) => {
      let valA = '';
      let valB = '';
      switch (sortOrder) {
        case 'alpha-asc':
        case 'alpha-desc':
          valA = a['Alarm Code Name'] || '';
          valB = b['Alarm Code Name'] || '';
          break;
        case 'time-asc':
        case 'time-desc':
          valA = a['Occurrence Time'] || '';
          valB = b['Occurrence Time'] || '';
          break;
        default:
          return 0;
      }
      if (valA < valB) return sortOrder.endsWith('-asc') ? -1 : 1;
      if (valA > valB) return sortOrder.endsWith('-asc') ? 1 : -1;
      return 0;
    });
  }, [alarms, searchTerm, sortOrder]);

  return (
    <div>
      <div style={{ display: 'flex', gap: '0.5rem', padding: '0.6rem 0.8rem', borderBottom: '1px solid var(--border-color)', background: 'rgba(255,255,255,0.01)', flexWrap: 'wrap' }}>
        <div className="filter-input-wrapper" style={{ padding: '0.2rem 0.5rem', minWidth: '130px', flex: 1 }}>
          <Search size={12} />
          <input
            className="filter-input"
            placeholder="Cerca allarme..."
            value={searchTerm}
            onChange={e => setSearchTerm(e.target.value)}
            style={{ fontSize: '0.75rem' }}
          />
          {searchTerm && <button className="filter-clear" onClick={() => setSearchTerm('')}><X size={10}/></button>}
        </div>
        <div className="filter-input-wrapper" style={{ padding: '0.2rem 0.5rem', minWidth: '120px' }}>
          <ArrowUpDown size={12} />
          <select
            value={sortOrder}
            onChange={e => setSortOrder(e.target.value)}
            style={{
              background: 'none',
              border: 'none',
              color: 'var(--text-primary)',
              fontSize: '0.75rem',
              cursor: 'pointer',
              outline: 'none',
              width: '100%'
            }}
          >
            <option value="time-desc" style={{ background: 'var(--bg-color)' }}>Recenti</option>
            <option value="time-asc" style={{ background: 'var(--bg-color)' }}>Meno recenti</option>
            <option value="alpha-asc" style={{ background: 'var(--bg-color)' }}>Allarme A-Z</option>
            <option value="alpha-desc" style={{ background: 'var(--bg-color)' }}>Allarme Z-A</option>
          </select>
        </div>
      </div>
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
            {processedAlarms.slice(0, 50).map((alarm, idx) => (
              <tr key={idx}>
                <td><span className={`badge badge-${alarm.Action}`}>{alarm.Action}</span></td>
                <td>{alarm['Alarm Code Name']}</td>
                <td>{alarm['Alarm Severity']}</td>
                <td>{alarm['Occurrence Time']}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {processedAlarms.length > 50 && (
          <p style={{ padding: '0.75rem', color: 'var(--text-secondary)', fontSize: '0.85rem', textAlign: 'center' }}>
            +{processedAlarms.length - 50} altri allarmi...
          </p>
        )}
        {processedAlarms.length === 0 && (
          <p style={{ padding: '2rem', color: 'var(--text-secondary)', textAlign: 'center', fontSize: '0.85rem' }}>
            Nessun allarme corrispondente al filtro.
          </p>
        )}
      </div>
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
  const [searchTerm, setSearchTerm] = useState('');
  const [sortOrder, setSortOrder] = useState('time-desc'); // 'time-desc' | 'time-asc' | 'me-asc' | 'me-desc' | 'alarm-asc' | 'alarm-desc'

  const alarms = useMemo(() => {
    const list = category === 'CHRONIC'
      ? results.alarms.filter(a => a.Is_Chronic)
      : results.alarms.filter(a => a.Action === category);

    // 1. Filter
    const filtered = list.filter(a => 
      !searchTerm || 
      String(a.ME || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
      String(a['Alarm Code Name'] || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
      String(a.Action || '').toLowerCase().includes(searchTerm.toLowerCase())
    );

    // 2. Sort
    return [...filtered].sort((a, b) => {
      let valA = '';
      let valB = '';
      switch (sortOrder) {
        case 'me-asc':
        case 'me-desc':
          valA = a.ME || '';
          valB = b.ME || '';
          break;
        case 'alarm-asc':
        case 'alarm-desc':
          valA = a['Alarm Code Name'] || '';
          valB = b['Alarm Code Name'] || '';
          break;
        case 'time-asc':
        case 'time-desc':
          valA = a['Occurrence Time'] || '';
          valB = b['Occurrence Time'] || '';
          break;
        default:
          return 0;
      }
      if (valA < valB) return sortOrder.endsWith('-asc') ? -1 : 1;
      if (valA > valB) return sortOrder.endsWith('-asc') ? 1 : -1;
      return 0;
    });
  }, [category, results, searchTerm, sortOrder]);

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" style={{ maxWidth: '1200px' }} onClick={e => e.stopPropagation()}>
        <div className="modal-header" style={{ flexWrap: 'wrap', gap: '1rem' }}>
          <h2>Allarmi Filtrati: {category} ({alarms.length})</h2>
          
          <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', flexWrap: 'wrap', marginLeft: 'auto', marginRight: '2rem' }}>
            <div className="filter-input-wrapper" style={{ padding: '0.25rem 0.5rem', minWidth: '150px' }}>
              <Search size={12} />
              <input
                className="filter-input"
                placeholder="Cerca sito o allarme..."
                value={searchTerm}
                onChange={e => setSearchTerm(e.target.value)}
                style={{ fontSize: '0.75rem' }}
              />
              {searchTerm && <button className="filter-clear" onClick={() => setSearchTerm('')}><X size={10}/></button>}
            </div>
            <div className="filter-input-wrapper" style={{ padding: '0.25rem 0.5rem', minWidth: '150px' }}>
              <ArrowUpDown size={12} />
              <select
                value={sortOrder}
                onChange={e => setSortOrder(e.target.value)}
                style={{
                  background: 'none',
                  border: 'none',
                  color: 'var(--text-primary)',
                  fontSize: '0.75rem',
                  cursor: 'pointer',
                  outline: 'none',
                  width: '100%'
                }}
              >
                <option value="time-desc" style={{ background: 'var(--bg-color)' }}>Data (Più recente)</option>
                <option value="time-asc" style={{ background: 'var(--bg-color)' }}>Data (Meno recente)</option>
                <option value="me-asc" style={{ background: 'var(--bg-color)' }}>Sito (A-Z)</option>
                <option value="me-desc" style={{ background: 'var(--bg-color)' }}>Sito (Z-A)</option>
                <option value="alarm-asc" style={{ background: 'var(--bg-color)' }}>Allarme (A-Z)</option>
                <option value="alarm-desc" style={{ background: 'var(--bg-color)' }}>Allarme (Z-A)</option>
              </select>
            </div>
          </div>

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

// ─────────────────────────────────────────────────────────────────────────────
//  PerformanceView — Tab analisi performance MW per un sito
// ─────────────────────────────────────────────────────────────────────────────
function PerformanceView({ siteName, data, loading, error, pmAvailable, pmStatus, selectedDateFrom, selectedDateTo, onDateChange, onRetry }) {
  const [zoomedChart, setZoomedChart] = useState(null);

  useEffect(() => {
    if (zoomedChart) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = 'unset';
    }
    return () => {
      document.body.style.overflow = 'unset';
    };
  }, [zoomedChart]);

  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        setZoomedChart(null);
      }
    };
    if (zoomedChart) {
      window.addEventListener('keydown', handleKeyDown);
    }
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [zoomedChart]);

  const [scale, setScale] = useState(1);
  const [position, setPosition] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const [isExpanded, setIsExpanded] = useState(false);

  useEffect(() => {
    setScale(1);
    setPosition({ x: 0, y: 0 });
    setIsDragging(false);
    setIsExpanded(false);
  }, [zoomedChart]);

  const handleMouseDown = (e) => {
    if (scale === 1) return;
    e.preventDefault();
    setIsDragging(true);
    setDragStart({ x: e.clientX - position.x, y: e.clientY - position.y });
  };

  const handleMouseMove = (e) => {
    if (!isDragging) return;
    setPosition({
      x: e.clientX - dragStart.x,
      y: e.clientY - dragStart.y
    });
  };

  const handleMouseUp = () => {
    setIsDragging(false);
  };

  const handleWheel = (e) => {
    if (!zoomedChart) return;
    e.preventDefault();
    const zoomFactor = 0.15;
    const newScale = Math.max(1, Math.min(scale + (e.deltaY < 0 ? zoomFactor : -zoomFactor), 4));
    setScale(newScale);
    if (newScale === 1) {
      setPosition({ x: 0, y: 0 });
    }
  };

  const handleDoubleClick = () => {
    if (scale > 1) {
      setScale(1);
      setPosition({ x: 0, y: 0 });
    } else {
      setScale(2.5);
      setPosition({ x: 0, y: 0 });
    }
  };

  const CHART_DESCRIPTIONS = {
    rsl_trend: {
      title: 'RSL — Livello Segnale Ricevuto',
      significato: 'Misura la potenza del segnale radio ricevuto in decibel-milliwatt (dBm). Rappresenta la forza fisica del collegamento tra il sito locale e quello remoto.',
      soglie: 'Valori nominali ottimali: tra -30 dBm e -55 dBm. Valori inferiori a -60 dBm o -65 dBm indicano una forte attenuazione del segnale.',
      troubleshooting: [
        'Calo speculare su entrambi i lati del link: Fenomeno meteo transitorio come forte pioggia (rain fading) o neve.',
        'Calo unilaterale o persistente nel tempo: Possibile disallineamento meccanico delle parabole, presenza di ostacoli fisici permanenti (es. nuovi edifici o vegetazione cresciuta), o infiltrazioni d\'acqua nei connettori.',
        'RSL eccessivamente alto (es. > -20 dBm): Rischio di saturazione del ricevitore. Valutare l\'inserimento di un attenuatore o la riduzione della potenza di trasmissione (ATPC).'
      ],
      correlazioni: 'Un calo di RSL deve essere correlato con l\'MSE. Se RSL cala e MSE degrada di conseguenza, siamo di fronte a una classica dissolvenza atmosferica.'
    },
    xpi_trend: {
      title: 'XPI — Cross-Polarization Interference',
      significato: 'Nei sistemi XPIC (Cross-Polarization Interference Cancellation) che riutilizzano la stessa frequenza su polarizzazioni verticali e orizzontali, misura la capacità di isolare i due canali ortogonali.',
      soglie: 'Valori nominali ottimali: > 25 dB. Valori inferiori a 20 dB introducono forti interferenze co-canale compromettendo la qualità di trasmissione.',
      troubleshooting: [
        'Calo improvviso o oscillazioni cicliche: Possibile torsione/rotazione dell\'antenna per forte vento o allentamento dei bulloni di fissaggio.',
        'Attenuazione correlata alla pioggia: Durante eventi meteo l\'XPI si riduce fisiologicamente. Se la riduzione avviene in assenza di pioggia, verificare la planarità del percorso (riflessioni da multipath causate da specchi d\'acqua o terreno riflettente).',
        'Verificare se i moduli XPIC su entrambi i modem sono attivi e correttamente calibrati.'
      ],
      correlazioni: 'Un calo di XPI senza una corrispondente diminuzione di RSL è indice quasi certo di un problema meccanico sull\'asse di polarizzazione dell\'antenna o di multipath riflettivo.'
    },
    mse_trend: {
      title: 'MSE — Mean Squared Error',
      significato: 'Rappresenta l\'errore quadratico medio della costellazione di modulazione. Misura la pulizia intrinseca del segnale demodulato (la qualità digitale del segnale).',
      soglie: 'Valori nominali ottimali: inferiori a -30 dB (es. -35 dB). Valori prossimi allo zero (superiori a -22 dB) causano errori sui bit e downshift.',
      troubleshooting: [
        'MSE degradato (es. -20 dB) con RSL ottimo: Indica la presenza di forti interferenze esterne (co-canale o canali adiacenti), rumore di fase, disadattamento di impedenza sui cavi, o guasto hardware interno ai moduli RF/Modem.',
        'MSE degradato coincidente con calo di RSL: Comportamento normale in caso di fading (attenuazione meteo). Il rumore termico prevale al ridursi del segnale utile.',
        'Verificare l\'integrità dei connettori e dei cavi coassiali/fibra tra IDU e ODU.'
      ],
      correlazioni: 'Un MSE degradato è il principale responsabile degli Errored Seconds (ES). L\'analisi combinata permette di confermare la natura elettrica o elettromagnetica del guasto.'
    },
    mod_downshift_trend: {
      title: 'Downshift Modulazione (Sub-Max Mod)',
      significato: 'Monitora la durata (in secondi) in cui l\'algoritmo di Modulazione Adattativa riduce lo schema di modulazione (es. da 4096QAM a QPSK) per preservare la stabilità del link a scapito della banda passante.',
      soglie: 'Condizioni ottimali: 0 secondi (il link opera stabilmente al massimo livello di modulazione configurato).',
      troubleshooting: [
        'Presenza costante di downshift: Il link non riesce a sostenere la capacità di picco nominale. Se avviene a RSL nominale, sospettare un degrado dell\'hardware RF o un\'interferenza costante.',
        'Downshift limitato a fasce orarie specifiche: Possibili fenomeni di multipath termico (inversioni termiche all\'alba o al tramonto) o interferenze esterne periodiche.',
        'Verificare che le soglie di transizione di modulazione sull\'apparato siano configurate correttamente e non vi sia un "ping-pong" continuo.'
      ],
      correlazioni: 'Fisiologicamente associato a un calo di RSL e a un peggioramento di MSE. Se avviene senza calo di RSL, indica un degrado qualitativo isolato.'
    },
    comparison: {
      title: 'Comparazione ES / MSE / RSL / Downshift',
      significato: 'Dashboard integrata a quattro pannelli che correla l\'andamento temporale di tutte le metriche principali in una singola vista coordinata.',
      soglie: 'Fornisce una visione olistica del comportamento del link nelle 24 ore.',
      troubleshooting: [
        'Correlazione Temporale per Diagnosi Meteo: Se RSL scende, MSE peggiora, la modulazione effettua il downshift e compaiono Errored Seconds (ES) nello stesso istante, si tratta di rain fading al 100%.',
        'Correlazione Temporale per Diagnosi Guasto Hardware: Se l\'RSL rimane piatto e stabile, ma l\'MSE ha improvvisi picchi negativi associati a ES elevati, c\'è un guasto hardware intermittente (connettori allentati, infiltrazioni, sbalzi di tensione).',
        'Correlazione per Interferenza: RSL normale, ma XPI e MSE che crollano contemporaneamente a causa di un segnale estraneo sulla stessa frequenza.'
      ],
      correlazioni: 'È lo strumento definitivo per discriminare le cause meteorologiche da quelle hardware o da disturbi di frequenza.'
    }
  };

  const OUTCOME_CONFIG = {
    SUPERATO:        { color: '#10b981', bg: 'rgba(16,185,129,0.15)', icon: '✅', label: 'Link stabile' },
    FALLIMENTO:      { color: '#ef4444', bg: 'rgba(239,68,68,0.15)',  icon: '🔴', label: 'DEGRADO CRITICO' },
    PREOCCUPAZIONE:  { color: '#f59e0b', bg: 'rgba(245,158,11,0.15)',icon: '⚠️',  label: 'PREOCCUPAZIONE QUALITATIVA' },
  };

  // ── PM non caricato (ritorno anticipato solo se il database PM non è presente) ────
  if (!pmAvailable) return (
    <div className="glass-card" style={{ textAlign: 'center', padding: '3rem', margin: '1rem 0' }}>
      <Database size={48} style={{ color: '#6366f1', opacity: 0.5, marginBottom: '1rem' }} />
      <h3>Database PM non disponibile</h3>
      <p style={{ color: 'var(--text-secondary)', marginTop: '0.5rem' }}>
        Carica prima un file Excel <strong>Performance Management ZTE</strong> dalla schermata di upload.
      </p>
    </div>
  );

  const outcome = data?.outcome || 'SUPERATO';
  const cfg     = OUTCOME_CONFIG[outcome] || OUTCOME_CONFIG.SUPERATO;

  const renderStatsTable = (stats, label) => (
    <div>
      <h4 style={{ marginBottom: '0.6rem', color: 'var(--accent-color)', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
        <Activity size={16} /> {label}
      </h4>
      <table className="data-table" style={{ fontSize: '0.8rem' }}>
        <thead>
          <tr>
            <th>Modem</th>
            <th>ES (s)</th>
            <th>Min RSL</th>
            <th>Min MSE</th>
            <th>Min XPI</th>
            <th>Downshift (s)</th>
          </tr>
        </thead>
        <tbody>
          {(stats || []).map((s, i) => (
            <tr key={i}>
              <td style={{ fontFamily: 'monospace', fontSize: '0.75rem' }}>{s.Modem}</td>
              <td style={{ color: s.Total_ES > 0 ? '#ef4444' : '#10b981', fontWeight: 'bold' }}>
                {s.Total_ES?.toFixed(0) ?? '—'}
              </td>
              <td style={{ color: s.Min_RSL !== null && s.Min_RSL < -65 ? '#f59e0b' : 'inherit' }}>
                {s.Min_RSL !== null ? `${s.Min_RSL?.toFixed(1)} dBm` : '—'}
              </td>
              <td>{s.Min_MSE !== null ? `${s.Min_MSE?.toFixed(1)} dB` : '—'}</td>
              <td style={{ color: s.Min_XPI !== null && s.Min_XPI < 25 ? '#f59e0b' : 'inherit' }}>
                {s.Min_XPI !== null ? `${s.Min_XPI?.toFixed(1)} dB` : '—'}
              </td>
              <td style={{ color: s.Tot_Downshifts > 0 ? '#f59e0b' : 'inherit' }}>
                {s.Tot_Downshifts?.toFixed(0) ?? '—'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );

  const renderCharts = (charts, label) => {
    const keys = Object.keys(charts || {});
    if (!keys.length) return null;
    const CHART_LABELS = {
      rsl_trend:           'RSL — Livello Segnale Ricevuto',
      xpi_trend:           'XPI — Cross-Polarization Interference',
      mse_trend:           'MSE — Mean Squared Error',
      mod_downshift_trend: 'Downshift Modulazione (Sub-Max Mod)',
      comparison:          'Comparazione ES / MSE / RSL / Downshift',
    };
    return (
      <div>
        <h4 style={{ marginBottom: '0.8rem', color: 'var(--text-secondary)', fontSize: '0.9rem' }}>{label}</h4>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))', gap: '1rem' }}>
          {keys.map(k => (
            <div
              key={k}
              className="glass-card zoomable-chart-card"
              style={{ padding: '0.6rem', background: 'rgba(255,255,255,0.03)' }}
              onClick={() => setZoomedChart({
                key: k,
                title: CHART_LABELS[k] || k,
                imgData: charts[k],
                site: label
              })}
            >
              <p style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginBottom: '0.4rem' }}>
                {CHART_LABELS[k] || k}
              </p>
              <div style={{ position: 'relative', overflow: 'hidden', borderRadius: '6px' }}>
                <img
                  src={`data:image/png;base64,${charts[k]}`}
                  alt={CHART_LABELS[k] || k}
                  style={{ width: '100%', display: 'block', borderRadius: '6px' }}
                />
                <div className="zoomable-chart-overlay">
                  <span>🔍 Clicca per ingrandire</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  };

  const today = new Date().toISOString().split('T')[0];
  const maxDate = pmStatus?.date_to || today;
  const minDate = pmStatus?.date_from || '2000-01-01';

  const handleToggleMode = (mode) => {
    if (mode === 'history') {
      onDateChange('', '');
    } else {
      onDateChange(pmStatus?.date_from || '2000-01-01', pmStatus?.date_to || today);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>

      {/* ── PM Control Bar (Sempre Visibile) ─────────────────────────────────── */}
      <div className="pm-control-bar" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '1rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.8rem', flexWrap: 'wrap' }}>
          <span style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-secondary)' }}>Filtro Temporale PM:</span>
          <div className="compare-tab-bar">
            <button
              className={`compare-tab-btn ${!(selectedDateFrom || selectedDateTo) ? 'active' : ''}`}
              onClick={() => handleToggleMode('history')}
            >
              Tutto lo storico
            </button>
            <button
              className={`compare-tab-btn ${selectedDateFrom || selectedDateTo ? 'active' : ''}`}
              onClick={() => handleToggleMode('range')}
            >
              Filtra Date
            </button>
          </div>
        </div>

        {(selectedDateFrom || selectedDateTo) && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.8rem', flexWrap: 'wrap' }}>
            <div className="pm-datepicker-wrapper" style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Da:</span>
              <input
                type="date"
                className="pm-datepicker"
                value={selectedDateFrom}
                min={minDate}
                max={selectedDateTo || maxDate}
                onChange={(e) => onDateChange(e.target.value, selectedDateTo)}
              />
            </div>
            <div className="pm-datepicker-wrapper" style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>A:</span>
              <input
                type="date"
                className="pm-datepicker"
                value={selectedDateTo}
                min={selectedDateFrom || minDate}
                max={maxDate}
                onChange={(e) => onDateChange(selectedDateFrom, e.target.value)}
              />
            </div>
          </div>
        )}
      </div>

      {loading ? (
        <div style={{ textAlign: 'center', padding: '4rem', color: 'var(--text-secondary)' }}>
          <RefreshCw size={40} className="spin-icon" style={{ color: '#6366f1', marginBottom: '1rem' }} />
          <p>Analisi performance in corso per <strong>{siteName}</strong>...</p>
          <p style={{ fontSize: '0.85rem', marginTop: '0.4rem' }}>Elaborazione RSL, MSE, XPI, ES e downshift</p>
        </div>
      ) : error ? (
        <div className="glass-card" style={{ textAlign: 'center', padding: '3rem', margin: '1rem 0', borderTop: '3px solid #ef4444' }}>
          <AlertTriangle size={40} style={{ color: '#ef4444', marginBottom: '1rem' }} />
          <h3>Errore nell'analisi</h3>
          <p style={{ color: 'var(--text-secondary)', marginTop: '0.4rem' }}>{error}</p>
          <button className="upload-btn" style={{ marginTop: '1rem' }} onClick={onRetry}>
            <RefreshCw size={14} style={{ marginRight: '0.4rem' }} /> Riprova
          </button>
        </div>
      ) : (!data || !data.available) ? (
        <div className="glass-card" style={{ textAlign: 'center', padding: '3rem', margin: '1rem 0' }}>
          <TrendingUp size={48} style={{ color: '#6366f1', opacity: 0.4, marginBottom: '1rem' }} />
          <h3>Nessun dato PM per questo sito</h3>
          <p style={{ color: 'var(--text-secondary)', marginTop: '0.5rem' }}>
            {data?.message || `Il sito "${siteName}" non ha record nel database PM.`}
          </p>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', marginTop: '0.4rem' }}>
            Assicurati che il nome del sito nel file PM corrisponda al nome NE nel sistema allarmi.
          </p>
        </div>
      ) : (
        <>


      {/* ── Badge esito stato link ────────────────────────────────────────────── */}
      <div className="glass-card" style={{ background: cfg.bg, borderLeft: `4px solid ${cfg.color}`, padding: '1.2rem 1.5rem' }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: '1rem' }}>
          <div style={{ fontSize: '2rem', lineHeight: 1 }}>{cfg.icon}</div>
          <div style={{ flex: 1 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.8rem', marginBottom: '0.5rem', flexWrap: 'wrap' }}>
              <span style={{ fontWeight: 700, fontSize: '1.05rem', color: cfg.color }}>{cfg.label}</span>
              <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                {data.local_site} ↔ {data.remote_site} · {data.arch}
              </span>
            </div>
            {(data.conclusion || []).map((line, i) => (
              <p key={i} style={{
                margin: '0.2rem 0',
                fontSize: i === 0 ? '0.95rem' : '0.85rem',
                fontWeight: i === 0 ? 600 : 400,
                color: i === 0 ? 'var(--text-primary)' : 'var(--text-secondary)',
              }}>
                {line}
              </p>
            ))}
          </div>
        </div>
      </div>

      {/* ── Correlazione Meteo Ambientale ──────────────────────────────────── */}
      {data.weather_correlation && (
        <div className="glass-card" style={{ padding: '1.2rem 1.5rem', border: '1px solid rgba(14, 165, 233, 0.3)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '1rem' }}>
            <CloudRain size={20} style={{ color: '#0ea5e9' }} />
            <h3 style={{ margin: 0, fontSize: '1.05rem', color: '#0ea5e9' }}>Correlazione Meteo Ambientale</h3>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginLeft: 'auto' }}>
              📍 {data.weather_correlation.location.name} ({data.weather_correlation.location.region})
            </span>
          </div>
          
          <p style={{ margin: '0 0 1rem 0', fontSize: '0.9rem', color: 'var(--text-primary)', fontWeight: 500 }}>
            {data.weather_correlation.summary_text}
          </p>

          {data.weather_correlation.events && data.weather_correlation.events.length > 0 && (
            <div style={{ background: 'rgba(255,255,255,0.03)', borderRadius: '8px', padding: '0.8rem', border: '1px solid var(--border-color)' }}>
              <h4 style={{ margin: '0 0 0.8rem 0', fontSize: '0.8rem', color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                Finestre di Degrado RSL Analizzate
              </h4>
              <div style={{ display: 'grid', gap: '0.5rem' }}>
                {data.weather_correlation.events.map((ev, i) => (
                  <div key={i} style={{ 
                    display: 'flex', alignItems: 'center', justifyContent: 'space-between', 
                    padding: '0.5rem', background: 'rgba(0,0,0,0.2)', borderRadius: '6px',
                    borderLeft: ev.is_adverse ? '3px solid #f59e0b' : '3px solid #374151'
                  }}>
                    <div>
                      <span style={{ fontSize: '0.8rem', fontWeight: 600, fontFamily: 'monospace' }}>
                        {new Date(ev.window_start).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})} 
                        {' → '} 
                        {new Date(ev.window_end).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}
                      </span>
                      <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginLeft: '0.5rem' }}>
                        RSL: {ev.min_rsl} dBm · ES: {ev.es_count}
                      </span>
                    </div>
                    <div style={{ display: 'flex', gap: '0.8rem', fontSize: '0.75rem', color: ev.is_adverse ? '#fcd34d' : 'var(--text-secondary)' }}>
                      <span title="Meteo">☁️ {ev.weather_label}</span>
                      <span title="Precipitazioni">🌧️ {ev.precipitation} mm</span>
                      <span title="Vento">💨 {ev.windspeed} km/h</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── Statistiche modem ──────────────────────────────────────────────── */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem' }}>
        <div className="glass-card" style={{ padding: '1.2rem' }}>
          {renderStatsTable(data.stats_local, `📍 Sito Locale — ${data.local_site}`)}
        </div>
        <div className="glass-card" style={{ padding: '1.2rem' }}>
          {renderStatsTable(data.stats_remote, `📡 Sito Remoto — ${data.remote_site}`)}
        </div>
      </div>

      {/* ── Grafici sito locale ─────────────────────────────────────────────── */}
      {data.charts?.local && Object.keys(data.charts.local).length > 0 && (
        <div className="glass-card" style={{ padding: '1.2rem' }}>
          {renderCharts(data.charts.local, `📍 Grafici Sito Locale — ${data.local_site}`)}
        </div>
      )}

      {/* ── Grafici sito remoto ─────────────────────────────────────────────── */}
      {data.charts?.remote && Object.keys(data.charts.remote).length > 0 && (
        <div className="glass-card" style={{ padding: '1.2rem' }}>
          {renderCharts(data.charts.remote, `📡 Grafici Sito Remoto — ${data.remote_site}`)}
        </div>
      )}

    </>
  )}


      {/* ── Modal Ingrandimento Grafico ────────────────────────────────────────── */}
      {zoomedChart && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            backgroundColor: 'rgba(15, 23, 42, 0.8)',
            backdropFilter: 'blur(8px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 9999,
            padding: '1.5rem',
            animation: 'fadeIn 0.2s ease-out'
          }}
          onClick={() => setZoomedChart(null)}
        >
          <div
            className="glass-card"
            style={{
              width: '95%',
              maxWidth: '1200px',
              maxHeight: '90vh',
              backgroundColor: 'rgba(30, 41, 59, 0.75)',
              border: '1px solid rgba(255, 255, 255, 0.08)',
              borderRadius: '16px',
              boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.5)',
              display: 'flex',
              flexDirection: 'column',
              overflow: 'hidden',
              animation: 'slideUp 0.3s cubic-bezier(0.16, 1, 0.3, 1)'
            }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal Header */}
            <div
              style={{
                padding: '1.2rem 1.5rem',
                borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                backgroundColor: 'rgba(15, 23, 42, 0.3)'
              }}
            >
              <div>
                <h3 style={{ margin: 0, fontSize: '1.2rem', fontWeight: 700, color: 'var(--text-primary)' }}>
                  {zoomedChart.title}
                </h3>
                <p style={{ margin: '0.2rem 0 0 0', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                  {zoomedChart.site}
                </p>
              </div>
              <button
                style={{
                  background: 'rgba(255, 255, 255, 0.05)',
                  border: 'none',
                  borderRadius: '50%',
                  width: '36px',
                  height: '36px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: 'var(--text-primary)',
                  cursor: 'pointer',
                  transition: 'background-color 0.2s',
                }}
                onClick={() => setZoomedChart(null)}
                onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'rgba(239, 68, 68, 0.2)'}
                onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'rgba(255, 255, 255, 0.05)'}
              >
                <X size={18} />
              </button>
            </div>

            {/* Modal Body */}
            <div
              className="zoom-modal-grid"
              style={{
                flex: 1,
                overflowY: 'auto',
                padding: '1.5rem',
                display: 'grid',
                gridTemplateColumns: isExpanded ? '1fr' : '1.7fr 1.3fr',
                gap: '2rem'
              }}
            >
              {/* Left Column: Image with Pan and Zoom */}
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  background: 'rgba(0, 0, 0, 0.25)',
                  borderRadius: '12px',
                  padding: '0.5rem',
                  position: 'relative',
                  overflow: 'hidden',
                  minHeight: isExpanded ? '60vh' : '400px',
                  maxHeight: '75vh',
                  userSelect: 'none',
                  border: '1px solid rgba(255, 255, 255, 0.05)',
                  cursor: scale > 1 ? (isDragging ? 'grabbing' : 'grab') : 'zoom-in'
                }}
                onMouseDown={handleMouseDown}
                onMouseMove={handleMouseMove}
                onMouseUp={handleMouseUp}
                onMouseLeave={handleMouseUp}
                onWheel={handleWheel}
                onDoubleClick={handleDoubleClick}
              >
                <img
                  src={`data:image/png;base64,${zoomedChart.imgData}`}
                  alt={zoomedChart.title}
                  style={{
                    maxWidth: '100%',
                    maxHeight: '100%',
                    height: 'auto',
                    objectFit: 'contain',
                    borderRadius: '8px',
                    boxShadow: '0 8px 16px rgba(0,0,0,0.3)',
                    transform: `translate(${position.x}px, ${position.y}px) scale(${scale})`,
                    transformOrigin: 'center center',
                    transition: isDragging ? 'none' : 'transform 0.15s ease-out',
                    pointerEvents: 'none'
                  }}
                />

                {/* Floating zoom and expand controls */}
                <div
                  style={{
                    position: 'absolute',
                    bottom: '1rem',
                    right: '1rem',
                    display: 'flex',
                    gap: '0.4rem',
                    backgroundColor: 'rgba(15, 23, 42, 0.85)',
                    backdropFilter: 'blur(8px)',
                    padding: '0.4rem',
                    borderRadius: '8px',
                    border: '1px solid rgba(255, 255, 255, 0.15)',
                    boxShadow: '0 4px 12px rgba(0,0,0,0.5)',
                    zIndex: 100,
                  }}
                  onClick={(e) => e.stopPropagation()}
                >
                  <button
                    title="Aumenta Zoom (+)"
                    style={{
                      background: 'none',
                      border: 'none',
                      color: 'var(--text-primary)',
                      cursor: 'pointer',
                      width: '32px',
                      height: '32px',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      borderRadius: '6px',
                      transition: 'background-color 0.2s',
                    }}
                    onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'rgba(255,255,255,0.1)'}
                    onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
                    onClick={() => setScale(prev => Math.min(prev + 0.5, 4))}
                  >
                    <ZoomIn size={18} />
                  </button>
                  <button
                    title="Riduci Zoom (-)"
                    style={{
                      background: 'none',
                      border: 'none',
                      color: 'var(--text-primary)',
                      cursor: 'pointer',
                      width: '32px',
                      height: '32px',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      borderRadius: '6px',
                      transition: 'background-color 0.2s',
                    }}
                    onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'rgba(255,255,255,0.1)'}
                    onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
                    onClick={() => {
                      setScale(prev => {
                        const newScale = Math.max(prev - 0.5, 1);
                        if (newScale === 1) setPosition({ x: 0, y: 0 });
                        return newScale;
                      });
                    }}
                  >
                    <ZoomOut size={18} />
                  </button>
                  <button
                    title="Ripristina Zoom (1x)"
                    style={{
                      background: 'none',
                      border: 'none',
                      color: 'var(--text-primary)',
                      cursor: 'pointer',
                      width: '32px',
                      height: '32px',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      borderRadius: '6px',
                      transition: 'background-color 0.2s',
                    }}
                    onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'rgba(255,255,255,0.1)'}
                    onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
                    onClick={() => {
                      setScale(1);
                      setPosition({ x: 0, y: 0 });
                    }}
                  >
                    <RefreshCw size={14} />
                  </button>
                  <div style={{ width: '1px', backgroundColor: 'rgba(255,255,255,0.15)', margin: '0.2rem 0.1rem' }} />
                  <button
                    title={isExpanded ? "Comprimi Vista" : "Espandi Vista Grafico"}
                    style={{
                      background: 'none',
                      border: 'none',
                      color: 'var(--text-primary)',
                      cursor: 'pointer',
                      width: '32px',
                      height: '32px',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      borderRadius: '6px',
                      transition: 'background-color 0.2s',
                    }}
                    onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'rgba(255,255,255,0.1)'}
                    onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
                    onClick={() => setIsExpanded(!isExpanded)}
                  >
                    {isExpanded ? <Minimize2 size={18} /> : <Maximize2 size={18} />}
                  </button>
                </div>
              </div>

              {/* Right Column: Explanations & Notes */}
              {!isExpanded && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '1.2rem', color: 'var(--text-primary)', fontSize: '0.85rem', lineHeight: 1.5 }}>
                  {(() => {
                    const desc = CHART_DESCRIPTIONS[zoomedChart.key] || {};
                    return (
                      <>
                        {/* Significato Metrico */}
                        <div style={{ background: 'rgba(255,255,255,0.02)', borderRadius: '8px', padding: '1rem', border: '1px solid rgba(255,255,255,0.04)' }}>
                          <h4 style={{ margin: '0 0 0.5rem 0', color: 'var(--accent-color)', fontSize: '0.9rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                            <BookOpen size={16} /> Significato Metrico
                          </h4>
                          <p style={{ margin: 0, color: 'var(--text-secondary)' }}>
                            {desc.significato || 'Nessuna spiegazione disponibile.'}
                          </p>
                        </div>

                        {/* Soglie & Valori di Riferimento */}
                        <div style={{ background: 'rgba(255,255,255,0.02)', borderRadius: '8px', padding: '1rem', border: '1px solid rgba(255,255,255,0.04)' }}>
                          <h4 style={{ margin: '0 0 0.5rem 0', color: '#10b981', fontSize: '0.9rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                            <CheckCircle size={16} /> Valori di Riferimento
                          </h4>
                          <p style={{ margin: 0, color: 'var(--text-secondary)' }}>
                            {desc.soglie || 'Nessuna soglia definita.'}
                          </p>
                        </div>

                        {/* Linee Guida Troubleshooting */}
                        <div style={{ background: 'rgba(239, 68, 68, 0.03)', borderRadius: '8px', padding: '1rem', border: '1px solid rgba(239, 68, 68, 0.15)' }}>
                          <h4 style={{ margin: '0 0 0.6rem 0', color: '#ef4444', fontSize: '0.9rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                            <ShieldAlert size={16} /> Troubleshooting & Diagnostica
                          </h4>
                          <ul style={{ margin: 0, paddingLeft: '1.2rem', color: 'var(--text-secondary)', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                            {(desc.troubleshooting || []).map((step, idx) => (
                              <li key={idx}>{step}</li>
                            ))}
                          </ul>
                        </div>

                        {/* Correlazioni chiave */}
                        <div style={{ background: 'rgba(99,102,241,0.03)', borderRadius: '8px', padding: '1rem', border: '1px solid rgba(99,102,241,0.15)' }}>
                          <h4 style={{ margin: '0 0 0.5rem 0', color: '#818cf8', fontSize: '0.9rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                            <Zap size={16} /> Correlazioni Chiave
                          </h4>
                          <p style={{ margin: 0, color: 'var(--text-secondary)' }}>
                            {desc.correlazioni || 'Nessuna correlazione chiave definita.'}
                          </p>
                        </div>
                      </>
                    );
                  })()}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
