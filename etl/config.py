"""Configuration for ETL pipeline."""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Project root
PROJECT_ROOT = Path(__file__).parent.parent

# Data directory
DATA_DIR = Path(os.getenv("DATA_DIR", PROJECT_ROOT / "data"))

# ClinicIQ REST API (OAuth 2.0)
CLINICIQ_API = {
    "base_url": os.getenv("CLINICIQ_BASE_URL", "https://i.cliniciq.ru"),
    "token_url": os.getenv("CLINICIQ_TOKEN_URL", "https://i.cliniciq.ru/oauth/token"),
    "client_id": os.getenv("CLINICIQ_CLIENT_ID", ""),
    "client_secret": os.getenv("CLINICIQ_CLIENT_SECRET", ""),
    "scope": os.getenv("CLINICIQ_SCOPE", "read"),
    "api_prefix": "/api/v1",
    "page_size": 1000,
    "rate_limit_per_minute": 90,  # ниже лимита 100 для запаса
    "request_timeout": 30,
    "max_retries": 3,
}

# Sync state file (stores last_sync timestamps per endpoint)
SYNC_STATE_FILE = PROJECT_ROOT / ".sync_state.json"

# DWH PostgreSQL connection
DWH_CONFIG = {
    "host": os.getenv("DWH_HOST", "localhost"),
    "port": int(os.getenv("DWH_PORT", "5433")),
    "database": os.getenv("DWH_DB", "br_analytics"),
    "user": os.getenv("DWH_USER", "br_admin"),
    "password": os.getenv("DWH_PASSWORD", "br_analytics_2025"),
}

DWH_URL = (
    f"postgresql://{DWH_CONFIG['user']}:{DWH_CONFIG['password']}"
    f"@{DWH_CONFIG['host']}:{DWH_CONFIG['port']}/{DWH_CONFIG['database']}"
)

# MIS ClinicIQ PostgreSQL (read-only)
MIS_CONFIG = {
    "host": os.getenv("MIS_HOST", ""),
    "port": int(os.getenv("MIS_PORT", "5432")),
    "database": os.getenv("MIS_DB", ""),
    "user": os.getenv("MIS_USER", ""),
    "password": os.getenv("MIS_PASSWORD", ""),
}

# Branch name mappings (MIS name -> canonical code)
MIS_BRANCH_MAP = {
    "(Таганская)": "taganskaya",
    "(Бауманская)": "baumanskaya",
    "(Динамо)": "dinamo",
    "(Зиларт)": "zilart",
    "(Рублевка)": "rublevka",
    "(Хамовники)": "khamovniki",
    "Таганская": "taganskaya",
    "Бауманская": "baumanskaya",
    "Динамо": "dinamo",
    "Зиларт": "zilart",
    "Рублевка": "rublevka",
    "Хамовники": "khamovniki",
}

# CF branch name mappings (1C name -> canonical code)
CF_BRANCH_MAP = {
    "Таганка": "taganskaya",
    "ТАГАНКА": "taganskaya",
    "Бауманская": "baumanskaya",
    "БАУМАНКА": "baumanskaya",
    "Динамо": "dinamo",
    "ДИНАМО": "dinamo",
    "Зиларт": "zilart",
    "ЗИЛАРТ": "zilart",
    "Рублевка": "rublevka",
    "РУБЛЕВКА": "rublevka",
    "Рублёвка": "rublevka",
    "Хамовники": "khamovniki",
    "ХАМОВНИКИ": "khamovniki",
}

# Legal entity short name -> id mapping
LEGAL_ENTITY_MAP = {
    "БР": 1,
    "БР-1": 2,
    "БРЦ": 3,
    "ИП": 4,
}

# Service category classification rules
SERVICE_CATEGORIES = {
    "гигиен": "Гигиена",
    "седаци": "Седация",
    "имплант": "Хирургия",
    "удален": "Хирургия",
    "хирург": "Хирургия",
    "коронк": "Ортопедия",
    "вкладк": "Ортопедия",
    "винир": "Ортопедия",
    "протез": "Ортопедия",
    "брекет": "Ортодонтия",
    "элайнер": "Ортодонтия",
    "ортодонт": "Ортодонтия",
    "пломб": "Терапия",
    "эндодонт": "Терапия",
    "канал": "Терапия",
    "пульпит": "Терапия",
    "кариес": "Терапия",
    "консульт": "Консультация",
    "осмотр": "Консультация",
    "рентген": "Диагностика",
    "КТ": "Диагностика",
    "снимок": "Диагностика",
}


def classify_service(service_name: str) -> str:
    """Classify service into a category based on name patterns."""
    if not service_name:
        return "Прочее"
    name_lower = service_name.lower()
    for pattern, category in SERVICE_CATEGORIES.items():
        if pattern.lower() in name_lower:
            return category
    return "Прочее"
