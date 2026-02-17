"""Load transformed data into DWH PostgreSQL."""

import logging
from typing import Optional

import pandas as pd
from sqlalchemy import create_engine, text

from etl.config import DWH_URL

logger = logging.getLogger(__name__)

_engine = None


def get_engine():
    """Get or create SQLAlchemy engine."""
    global _engine
    if _engine is None:
        _engine = create_engine(DWH_URL, pool_pre_ping=True)
    return _engine


def load_to_raw(df: pd.DataFrame, table_name: str, if_exists: str = "append") -> int:
    """
    Load DataFrame into raw schema table.

    Args:
        df: Data to load
        table_name: Table name (without schema prefix)
        if_exists: 'append' or 'replace'

    Returns:
        Number of rows loaded
    """
    engine = get_engine()
    logger.info(f"Loading {len(df)} rows into raw.{table_name}")
    df.to_sql(table_name, engine, schema="raw", if_exists=if_exists, index=False)
    logger.info(f"Loaded {len(df)} rows into raw.{table_name}")
    return len(df)


def load_to_dwh(df: pd.DataFrame, table_name: str, if_exists: str = "append") -> int:
    """Load DataFrame into dwh schema table."""
    engine = get_engine()
    logger.info(f"Loading {len(df)} rows into dwh.{table_name}")
    df.to_sql(table_name, engine, schema="dwh", if_exists=if_exists, index=False)
    logger.info(f"Loaded {len(df)} rows into dwh.{table_name}")
    return len(df)


def upsert_doctors(doctor_names: list[str], branch_lookup: dict) -> dict:
    """
    Insert new doctors into dim_doctor, return full name->id mapping.
    """
    engine = get_engine()

    with engine.begin() as conn:
        existing = pd.read_sql("SELECT doctor_id, full_name FROM dwh.dim_doctor", conn)
        existing_map = dict(zip(existing["full_name"], existing["doctor_id"]))

        new_names = [n for n in doctor_names if n and n not in existing_map]
        if new_names:
            logger.info(f"Inserting {len(new_names)} new doctors")
            for name in new_names:
                result = conn.execute(
                    text(
                        "INSERT INTO dwh.dim_doctor (full_name) VALUES (:name) "
                        "ON CONFLICT (full_name) DO NOTHING RETURNING doctor_id"
                    ),
                    {"name": name},
                )
                row = result.fetchone()
                if row:
                    existing_map[name] = row[0]

        if new_names:
            refreshed = pd.read_sql(
                "SELECT doctor_id, full_name FROM dwh.dim_doctor", conn
            )
            existing_map = dict(zip(refreshed["full_name"], refreshed["doctor_id"]))

    return existing_map


def upsert_services(service_names: list[str]) -> dict:
    """Insert new services into dim_service, return name->id mapping."""
    engine = get_engine()

    with engine.begin() as conn:
        existing = pd.read_sql("SELECT service_id, name FROM dwh.dim_service", conn)
        existing_map = dict(zip(existing["name"], existing["service_id"]))

        new_names = [n for n in service_names if n and n not in existing_map]
        if new_names:
            logger.info(f"Inserting {len(new_names)} new services")
            from etl.config import classify_service

            for name in new_names:
                category = classify_service(name)
                conn.execute(
                    text(
                        "INSERT INTO dwh.dim_service (name, category) VALUES (:name, :cat) "
                        "ON CONFLICT (name) DO NOTHING"
                    ),
                    {"name": name[:200], "cat": category},
                )

            refreshed = pd.read_sql(
                "SELECT service_id, name FROM dwh.dim_service", conn
            )
            existing_map = dict(zip(refreshed["name"], refreshed["service_id"]))

    return existing_map


def get_branch_lookup() -> dict:
    """Get code -> branch_id mapping from dim_branch."""
    engine = get_engine()
    with engine.connect() as conn:
        df = pd.read_sql("SELECT branch_id, code FROM dwh.dim_branch", conn)
    return dict(zip(df["code"], df["branch_id"]))


def get_payment_type_lookup() -> dict:
    """Get name -> payment_type_id mapping."""
    engine = get_engine()
    with engine.connect() as conn:
        df = pd.read_sql(
            "SELECT payment_type_id, name FROM dwh.dim_payment_type", conn
        )
    return dict(zip(df["name"], df["payment_type_id"]))


def refresh_materialized_views():
    """Refresh all materialized views in marts schema."""
    engine = get_engine()
    views = ["monthly_pnl", "doctor_kpi", "branch_comparison", "service_economics"]
    with engine.begin() as conn:
        for view in views:
            try:
                conn.execute(text(f"REFRESH MATERIALIZED VIEW marts.{view}"))
                logger.info(f"Refreshed marts.{view}")
            except Exception as e:
                logger.warning(f"Could not refresh marts.{view}: {e}")
