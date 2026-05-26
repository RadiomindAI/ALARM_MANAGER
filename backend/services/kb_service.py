# services/kb_service.py
import logging
from datetime import datetime
from config.settings import settings
from repositories.json_repo import load_json, save_json
from core.audit import log_feedback

# Import reload_kb
try:
    from core.classifier import reload_kb
except ImportError:
    def reload_kb(): pass

logger = logging.getLogger(__name__)

class KBService:
    def __init__(self):
        self._alarm_kb_path = settings.alarm_kb_path
        self._operator_kb_path = settings.operator_kb_path

    def _default_operator_kb(self) -> dict:
        return {
            "wizard_completed": False,
            "wizard_completed_at": None,
            "operator_rules": {},
            "new_alarm_history": [],
        }

    def get_structural_alarms_for_wizard(self) -> list:
        kb = load_json(self._alarm_kb_path, {})
        alarm_profiles = kb.get('alarm_profiles', {})
        threshold = kb.get('filterability_threshold', 0.85)
        operator_kb = load_json(self._operator_kb_path, self._default_operator_kb())
        already_set = set(operator_kb.get('operator_rules', {}).keys())

        structural = [
            {
                'alarm_code_name':   name,
                'filterability_score': p.get('filterability_score', 0),
                'total_occurrences': p.get('total_occurrences', 0),
                'affected_me_count': p.get('affected_me_count', 0),
                'main_severity':     p.get('main_severity', ''),
                'suggested_action':  p.get('suggested_action', 'TOLERABLE'),
                'suggested_reason':  p.get('suggested_reason', ''),
                'already_classified': name in already_set,
            }
            for name, p in alarm_profiles.items()
            if p.get('filterability_score', 0) >= threshold
        ]
        structural.sort(key=lambda x: x['filterability_score'], reverse=True)
        return structural[:settings.base_dir.parent.joinpath("backend/config/thresholds.yml").exists() and 50 or 50]

    def get_first_launch_status(self) -> dict:
        operator_kb = load_json(self._operator_kb_path, self._default_operator_kb())
        kb_available = self._alarm_kb_path.exists()
        structural_alarms = []
        if kb_available and not operator_kb.get('wizard_completed', False):
            structural_alarms = self.get_structural_alarms_for_wizard()

        return {
            "wizard_completed": operator_kb.get('wizard_completed', False),
            "kb_available":     kb_available,
            "structural_alarms": structural_alarms,
        }

    def init_operator_rules(self, rules: list) -> int:
        operator_kb = load_json(self._operator_kb_path, self._default_operator_kb())
        for rule in rules:
            operator_kb['operator_rules'][rule.alarm_code_name] = {
                'operator_action': rule.operator_action,
                'note':            rule.note or '',
                'set_at':          datetime.now().isoformat(),
            }
        operator_kb['wizard_completed'] = True
        operator_kb['wizard_completed_at'] = datetime.now().isoformat()
        save_json(self._operator_kb_path, operator_kb)
        
        reload_kb()
        log_feedback(event_type="wizard_completed", rules_count=len(rules))
        return len(rules)

    def get_operator_kb(self) -> dict:
        return load_json(self._operator_kb_path, self._default_operator_kb())

    def update_operator_rule(self, alarm_code_name: str, operator_action: str, note: str, new_alarm_entry: dict = None) -> dict:
        operator_kb = load_json(self._operator_kb_path, self._default_operator_kb())
        operator_kb['operator_rules'][alarm_code_name] = {
            'operator_action': operator_action,
            'note':            note or '',
            'set_at':          datetime.now().isoformat(),
        }

        if new_alarm_entry:
            history = operator_kb.get('new_alarm_history', [])
            entry = {
                'alarm_code_name':  alarm_code_name,
                'first_seen':       datetime.now().isoformat(),
                'operator_action':  operator_action,
                'solution_applied': new_alarm_entry.get('solution_applied', ''),
                'resolved':         new_alarm_entry.get('resolved', False),
                'note':             note or '',
            }
            history.append(entry)
            operator_kb['new_alarm_history'] = history

        save_json(self._operator_kb_path, operator_kb)
        reload_kb()
        
        log_feedback(
            event_type="new_alarm_classified" if new_alarm_entry else "alarm_reclassified",
            alarm_code_name=alarm_code_name,
            operator_action=operator_action,
            note=note or ''
        )
        return {"status": "ok", "alarm": alarm_code_name, "action": operator_action}

    def get_kb_stats(self) -> dict:
        kb = load_json(self._alarm_kb_path, {})
        if not kb:
            return {"available": False, "message": "KB non ancora generata."}

        alarm_profiles = kb.get('alarm_profiles', {})
        me_profiles = kb.get('me_profiles', {})
        threshold = kb.get('filterability_threshold', 0.85)

        structural = [(n, p) for n, p in alarm_profiles.items() if p.get('is_structural')]
        top_structural = sorted(structural, key=lambda x: x[1].get('filterability_score', 0), reverse=True)[:20]
        top_risk_me = sorted(me_profiles.items(), key=lambda x: x[1].get('risk_score', 0), reverse=True)[:20]

        operator_kb = load_json(self._operator_kb_path, self._default_operator_kb())

        return {
            "available":             True,
            "generated_at":          kb.get('generated_at'),
            "last_rebuild_at":       kb.get('last_rebuild_at'),
            "last_rebuild_status":   kb.get('last_rebuild_status', 'SUCCESS'),
            "last_updated":          kb.get('last_updated'),
            "history_days":          kb.get('history_days', 0),
            "date_from":             kb.get('date_from'),
            "date_to":               kb.get('date_to'),
            "total_events":          kb.get('total_events', 0),
            "unique_mes":            kb.get('unique_mes', 0),
            "unique_alarm_types":    kb.get('unique_alarm_types', 0),
            "structural_alarm_count": kb.get('structural_alarm_count', 0),
            "filterability_threshold": threshold,
            "top_structural_alarms": [
                {
                    "name":               n,
                    "score":              p.get('filterability_score', 0),
                    "occurrences":        p.get('total_occurrences', 0),
                    "affected_me":        p.get('affected_me_count', 0),
                    "severity":           p.get('main_severity', ''),
                    "operator_classified": n in operator_kb.get('operator_rules', {}),
                }
                for n, p in top_structural
            ],
            "top_risk_ne": [
                {
                    "name":          n,
                    "risk_score":    p.get('risk_score', 0),
                    "total_alarms":  p.get('total_alarms_20d', 0),
                    "chronic_count": p.get('chronic_alarm_count', 0),
                    "top_alarm":     p.get('top_alarm', ''),
                }
                for n, p in top_risk_me
            ],
            "wizard_completed": operator_kb.get('wizard_completed', False),
            "operator_rules_count": len(operator_kb.get('operator_rules', {})),
        }

# Istanza singleton
kb_service = KBService()
