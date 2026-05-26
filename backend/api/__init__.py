# api/__init__.py
from api.alarms import router as alarms_router
from api.performance import router as performance_router
from api.kb import router as kb_router
from api.predictive import router as predictive_router
from api.session import router as session_router
from api.audit import router as audit_router
