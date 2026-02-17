"""Transform Cash Flow data from 1C: map branches, legal entities, expense types."""

import logging

import pandas as pd

from etl.config import CF_BRANCH_MAP, LEGAL_ENTITY_MAP

logger = logging.getLogger(__name__)


def transform_cf_entries(df: pd.DataFrame, branch_lookup: dict) -> pd.DataFrame:
    """
    Transform raw CF entries into DWH-ready format.

    Maps branch_uu (Подразделение_УУ) to branch_id.
    """
    logger.info(f"Transforming {len(df)} CF entries")

    result = df.copy()

    def map_branch(branch_uu):
        if pd.isna(branch_uu):
            return None
        name = str(branch_uu).strip()
        code = CF_BRANCH_MAP.get(name)
        if code and code in branch_lookup:
            return branch_lookup[code]
        return None

    result["branch_id"] = result["branch_uu"].apply(map_branch)

    unmapped = result["branch_id"].isna().sum()
    if unmapped > 0:
        logger.warning(f"{unmapped} CF entries with unmapped branch")

    return result


def transform_cf_monthly(df: pd.DataFrame) -> pd.DataFrame:
    """
    Transform monthly CF SVOD data.

    Maps legal_entity short name to legal_entity_id.
    Parses year_month string to date.
    """
    if df.empty:
        return df

    logger.info(f"Transforming {len(df)} CF monthly records")

    result = df.copy()

    result["legal_entity_id"] = result["legal_entity"].map(LEGAL_ENTITY_MAP)

    def parse_year_month(ym_str):
        """Parse '2025-1' or '2025-01' to date."""
        try:
            parts = str(ym_str).split("-")
            year = int(parts[0])
            month = int(parts[1])
            return pd.Timestamp(year=year, month=month, day=1)
        except (ValueError, IndexError):
            return None

    result["year_month"] = result["year_month_str"].apply(parse_year_month)
    result = result.dropna(subset=["year_month", "legal_entity_id"])

    logger.info(f"Transformed {len(result)} CF monthly records")
    return result
