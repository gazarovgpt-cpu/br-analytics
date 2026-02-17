"""ETL Pipeline orchestration for Белая Радуга analytics."""

import logging
import sys
from datetime import date, timedelta
from pathlib import Path

import click

from etl.config import DATA_DIR

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


@click.group()
def cli():
    """Белая Радуга ETL Pipeline."""
    pass


@cli.command()
@click.option(
    "--file",
    type=click.Path(exists=True),
    help="Path to Детализация_транзакций Excel file",
)
def transactions(file):
    """Load MIS transactions into DWH."""
    from etl.extractors.transaction_extractor import extract_transactions
    from etl.transformers.transactions import transform_transactions
    from etl.loaders.dwh_loader import (
        get_branch_lookup,
        get_payment_type_lookup,
        load_to_raw,
        load_to_dwh,
        upsert_doctors,
        upsert_services,
    )

    filepath = Path(file) if file else DATA_DIR / "mis" / "transactions.xlsx"
    if not filepath.exists():
        logger.error(f"File not found: {filepath}")
        sys.exit(1)

    logger.info("=== Loading MIS Transactions ===")

    df_raw = extract_transactions(filepath)
    load_to_raw(df_raw.drop(columns=["patient_hash"], errors="ignore"), "mis_transactions", if_exists="replace")

    branch_lookup = get_branch_lookup()
    pt_lookup = get_payment_type_lookup()

    doctor_names = list(df_raw["doctor_name"].dropna().unique())
    doctor_map = upsert_doctors(doctor_names, branch_lookup)

    service_names = list(df_raw["service_items"].dropna().apply(lambda x: str(x).strip()[:200]).unique())
    service_map = upsert_services(service_names)

    df_transformed = transform_transactions(
        df_raw, branch_lookup, pt_lookup, set(doctor_map.keys())
    )

    df_transformed["doctor_id"] = df_transformed["doctor_name"].map(doctor_map)
    df_transformed["service_id"] = df_transformed["service_name"].map(service_map)

    cols_to_load = [
        "transaction_date", "branch_id", "patient_hash", "patient_age",
        "is_child", "payment_type_id", "operation_type", "invoice_branch_id",
        "invoice_amount", "invoice_debt", "service_id", "service_name",
        "visit_date", "doctor_id", "is_primary_visit", "transaction_amount",
    ]

    load_to_dwh(df_transformed[cols_to_load], "fact_transactions", if_exists="replace")
    logger.info("=== MIS Transactions loaded successfully ===")


@cli.command()
@click.option("--file", type=click.Path(exists=True), help="Path to CF Excel file")
def cashflow(file):
    """Load Cash Flow entries from 1C export."""
    from etl.extractors.cf_extractor import extract_cf_entries
    from etl.transformers.cashflow import transform_cf_entries
    from etl.loaders.dwh_loader import get_branch_lookup, load_to_raw

    filepath = Path(file) if file else DATA_DIR / "accounting" / "cf_2024_br.xlsx"
    if not filepath.exists():
        logger.error(f"File not found: {filepath}")
        sys.exit(1)

    logger.info("=== Loading Cash Flow Entries ===")

    df_raw = extract_cf_entries(filepath)
    load_to_raw(df_raw, "cf_entries", if_exists="replace")

    branch_lookup = get_branch_lookup()
    df_transformed = transform_cf_entries(df_raw, branch_lookup)

    logger.info("=== Cash Flow Entries loaded successfully ===")


@cli.command()
@click.option("--file", type=click.Path(exists=True), help="Path to cost structure file")
def costs(file):
    """Load cost structure (unit economics)."""
    from etl.extractors.cost_extractor import extract_cost_structure
    from etl.loaders.dwh_loader import load_to_raw

    filepath = Path(file) if file else DATA_DIR / "accounting" / "cost_structure.xlsx"
    if not filepath.exists():
        logger.error(f"File not found: {filepath}")
        sys.exit(1)

    logger.info("=== Loading Cost Structure ===")
    df = extract_cost_structure(filepath)
    load_to_raw(df, "cost_structure", if_exists="replace")
    logger.info("=== Cost Structure loaded successfully ===")


@cli.command()
@click.option("--file", type=click.Path(exists=True), help="Path to leads file")
def leads(file):
    """Load lead data."""
    from etl.extractors.cost_extractor import extract_leads
    from etl.loaders.dwh_loader import load_to_raw

    filepath = Path(file) if file else DATA_DIR / "mis" / "leads.xlsx"
    if not filepath.exists():
        logger.error(f"File not found: {filepath}")
        sys.exit(1)

    logger.info("=== Loading Leads ===")
    df_monthly, _ = extract_leads(filepath)
    load_to_raw(df_monthly, "leads_monthly", if_exists="replace")
    logger.info("=== Leads loaded successfully ===")


@cli.command()
def refresh():
    """Refresh all materialized views."""
    from etl.loaders.dwh_loader import refresh_materialized_views

    logger.info("=== Refreshing Materialized Views ===")
    refresh_materialized_views()
    logger.info("=== Done ===")


@cli.command()
@click.pass_context
def full(ctx):
    """Run full ETL pipeline: all sources + refresh views."""
    logger.info("========== FULL ETL PIPELINE ==========")

    sources = {
        "transactions": DATA_DIR / "mis" / "transactions.xlsx",
        "costs": DATA_DIR / "accounting" / "cost_structure.xlsx",
        "leads": DATA_DIR / "mis" / "leads.xlsx",
    }

    for name, path in sources.items():
        if path.exists():
            logger.info(f"Running {name}...")
            ctx.invoke(globals()[name], file=str(path))
        else:
            logger.warning(f"Skipping {name}: {path} not found")

    ctx.invoke(refresh)
    logger.info("========== FULL ETL PIPELINE COMPLETE ==========")


# ── API-based commands ─────────────────────────────────────────


@cli.command("api-test")
def api_test():
    """Test API connection and OAuth 2.0 authentication."""
    from etl.extractors.api_client import ClinicIQClient, AuthError

    logger.info("=== Testing ClinicIQ API Connection ===")
    try:
        client = ClinicIQClient()
        result = client.test_connection()
    except AuthError as e:
        logger.error("Authentication failed: %s", e)
        sys.exit(1)

    if result["success"]:
        logger.info("Connection OK!")
        logger.info("  Token: %s", result.get("token"))
        logger.info("  Branches found: %s", result.get("branches"))
        for name in result.get("branch_names", []):
            logger.info("    - %s", name)
    else:
        logger.error("Connection failed: %s", result.get("error"))
        sys.exit(1)


@cli.command("api-sync")
@click.option(
    "--date-from",
    type=str,
    default=None,
    help="Start date (YYYY-MM-DD). Default: 30 days ago",
)
@click.option(
    "--date-to",
    type=str,
    default=None,
    help="End date (YYYY-MM-DD). Default: today",
)
@click.option(
    "--incremental/--full",
    default=True,
    help="Incremental (modified_since) or full reload",
)
@click.option(
    "--endpoints",
    type=str,
    default="all",
    help="Comma-separated list: branches,doctors,services,transactions,appointments,invoices,patient_stats",
)
def api_sync(date_from, date_to, incremental, endpoints):
    """Sync data from ClinicIQ API into DWH."""
    from etl.extractors.api_extractor import (
        extract_branches,
        extract_doctors,
        extract_services,
        extract_transactions,
        extract_appointments,
        extract_invoices,
        extract_patient_stats,
    )
    from etl.loaders.dwh_loader import load_to_raw

    today = date.today()
    if not date_from:
        date_from = (today - timedelta(days=30)).isoformat()
    if not date_to:
        date_to = today.isoformat()

    if endpoints == "all":
        endpoint_list = [
            "branches", "doctors", "services",
            "transactions", "appointments", "invoices", "patient_stats",
        ]
    else:
        endpoint_list = [e.strip() for e in endpoints.split(",")]

    logger.info("========== API SYNC ==========")
    logger.info("Period: %s to %s", date_from, date_to)
    logger.info("Mode: %s", "incremental" if incremental else "full")
    logger.info("Endpoints: %s", ", ".join(endpoint_list))

    results = {}

    # 1. Reference data (no date range needed)
    if "branches" in endpoint_list:
        try:
            df = extract_branches()
            if not df.empty:
                load_to_raw(df, "api_branches", if_exists="replace")
            results["branches"] = len(df)
        except Exception as e:
            logger.error("Failed to sync branches: %s", e)
            results["branches"] = f"ERROR: {e}"

    if "doctors" in endpoint_list:
        try:
            df = extract_doctors(incremental=incremental)
            if not df.empty:
                mode = "append" if incremental else "replace"
                load_to_raw(df, "api_doctors", if_exists=mode)
            results["doctors"] = len(df)
        except Exception as e:
            logger.error("Failed to sync doctors: %s", e)
            results["doctors"] = f"ERROR: {e}"

    if "services" in endpoint_list:
        try:
            df = extract_services(incremental=incremental)
            if not df.empty:
                mode = "append" if incremental else "replace"
                load_to_raw(df, "api_services", if_exists=mode)
            results["services"] = len(df)
        except Exception as e:
            logger.error("Failed to sync services: %s", e)
            results["services"] = f"ERROR: {e}"

    # 2. Transactional data (date range required)
    if "transactions" in endpoint_list:
        try:
            df = extract_transactions(
                date_from, date_to, incremental=incremental
            )
            if not df.empty:
                mode = "append" if incremental else "replace"
                load_to_raw(df, "api_transactions", if_exists=mode)
            results["transactions"] = len(df)
        except Exception as e:
            logger.error("Failed to sync transactions: %s", e)
            results["transactions"] = f"ERROR: {e}"

    if "appointments" in endpoint_list:
        try:
            df = extract_appointments(
                date_from, date_to, incremental=incremental
            )
            if not df.empty:
                mode = "append" if incremental else "replace"
                load_to_raw(df, "api_appointments", if_exists=mode)
            results["appointments"] = len(df)
        except Exception as e:
            logger.error("Failed to sync appointments: %s", e)
            results["appointments"] = f"ERROR: {e}"

    if "invoices" in endpoint_list:
        try:
            df = extract_invoices(
                date_from, date_to, incremental=incremental
            )
            if not df.empty:
                mode = "append" if incremental else "replace"
                load_to_raw(df, "api_invoices", if_exists=mode)
            results["invoices"] = len(df)
        except Exception as e:
            logger.error("Failed to sync invoices: %s", e)
            results["invoices"] = f"ERROR: {e}"

    if "patient_stats" in endpoint_list:
        try:
            df = extract_patient_stats(date_from, date_to)
            if not df.empty:
                load_to_raw(df, "api_patient_stats", if_exists="replace")
            results["patient_stats"] = len(df)
        except Exception as e:
            logger.error("Failed to sync patient stats: %s", e)
            results["patient_stats"] = f"ERROR: {e}"

    # Summary
    logger.info("========== SYNC RESULTS ==========")
    for endpoint, count in results.items():
        status = f"{count} rows" if isinstance(count, int) else count
        logger.info("  %-18s %s", endpoint, status)
    logger.info("==================================")


@cli.command("api-sync-daily")
def api_sync_daily():
    """Quick daily incremental sync (yesterday's changes)."""
    from click.testing import CliRunner

    today = date.today()
    yesterday = today - timedelta(days=1)

    runner = CliRunner()
    result = runner.invoke(
        api_sync,
        [
            "--date-from", yesterday.isoformat(),
            "--date-to", today.isoformat(),
            "--incremental",
            "--endpoints", "transactions,appointments,invoices",
        ],
    )
    if result.exit_code != 0:
        logger.error("Daily sync failed")
        sys.exit(1)


if __name__ == "__main__":
    cli()
