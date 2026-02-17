"""Extract cost structure (unit economics) from Excel."""

import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)


def extract_cost_structure(filepath: Path) -> pd.DataFrame:
    """
    Extract unit economics per procedure.

    Expected file: 2024_11_13_отчет_по_себестоимости_запрос_на_отдельные_позиции.xlsx
    Sheet: "отчет"
    Columns: Код позиции | Название позиции | ПРАЙС | материалы | % |
             ФОТ врача | ФОТ ассистента | налоги | ИТОГО | руб (margin) | % (margin)
    """
    logger.info(f"Reading cost structure from {filepath}")

    df = pd.read_excel(filepath, sheet_name="отчет", engine="openpyxl", header=2)
    logger.info(f"Read {len(df)} rows, columns: {list(df.columns)}")

    rename_map = {
        "Код позиции": "service_code",
        "Название позиции": "service_name",
        "ПРАЙС": "price",
        "материалы": "material_cost",
        "ФОТ врача": "doctor_pay",
        "ФОТ ассистента": "assistant_pay",
        "налоги": "taxes",
        "ИТОГО": "total_cost",
    }

    available = {k: v for k, v in rename_map.items() if k in df.columns}
    df = df.rename(columns=available)

    for col in ["price", "material_cost", "doctor_pay", "assistant_pay", "taxes", "total_cost"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["service_name", "price"])
    df = df[df["price"] > 0]

    if "material_cost" in df.columns and "price" in df.columns:
        df["material_pct"] = df["material_cost"] / df["price"]

    if "total_cost" in df.columns and "price" in df.columns:
        df["margin_rub"] = df["price"] - df["total_cost"]
        df["margin_pct"] = df["margin_rub"] / df["price"]

    logger.info(f"Extracted {len(df)} cost structure records")
    return df


def extract_leads(filepath: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Extract lead data.

    Expected file: 5_Лиды.xlsx
    Sheet "Лиды общие": monthly primary/secondary counts
    Sheet "Источники первичных лидов": weekly source breakdown
    """
    logger.info(f"Reading leads from {filepath}")

    df_monthly = pd.read_excel(filepath, sheet_name="Лиды общие", engine="openpyxl")
    df_sources = pd.read_excel(
        filepath, sheet_name="Источники первичных лидов", engine="openpyxl"
    )

    months = [
        "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
        "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь",
    ]

    records = []
    for _, row in df_monthly.iterrows():
        lead_type = row.get("Клиенты")
        if pd.isna(lead_type) or lead_type not in ("Первичные", "Вторичные", "Итого"):
            continue
        if lead_type == "Итого":
            continue
        for i, m in enumerate(months, 1):
            val = row.get(m)
            if pd.notna(val):
                records.append({
                    "year": 2025,
                    "month": i,
                    "lead_type": lead_type,
                    "count": int(val),
                })

    leads_df = pd.DataFrame(records)
    logger.info(f"Extracted {len(leads_df)} monthly lead records")

    return leads_df, df_sources
