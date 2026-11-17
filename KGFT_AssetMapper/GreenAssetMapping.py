#!/usr/bin/env python
"""
GreenAssetMapping.py
Standalone conversion of Notebook 01 — KGFT-informed Green Asset Mapping.

Usage:
    python GreenAssetMapping.py --input data/synthetic_kenya_loan_portfolio.csv
    python GreenAssetMapping.py --input my_portfolio.csv --output-dir outputs

The keyword mapping is a preliminary screening tool, not KGFT certification.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import pandas as pd
from taxonomy_engine import classify_portfolio

EXPECTED_COLUMNS = [
    "loan_id", "origination_date", "borrower_segment", "industry_sector",
    "county", "product_description", "purpose", "collateral_type",
    "currency", "disbursed_amount", "tenor_period"
]

def validate_portfolio(data: pd.DataFrame) -> pd.DataFrame:
    missing = sorted(set(EXPECTED_COLUMNS) - set(data.columns))
    if missing:
        raise ValueError(f"Missing required columns: {missing}")
    if data["loan_id"].isna().any() or data["loan_id"].astype(str).str.strip().eq("").any():
        raise ValueError("loan_id must be populated for every record.")
    if data["loan_id"].duplicated().any():
        raise ValueError("loan_id must be unique.")
    data = data.copy()
    data["disbursed_amount"] = pd.to_numeric(data["disbursed_amount"], errors="coerce")
    if data["disbursed_amount"].isna().any() or data["disbursed_amount"].lt(0).any():
        raise ValueError("disbursed_amount must contain valid non-negative numbers.")
    return data

def run_mapping(input_path: Path, output_dir: Path) -> pd.DataFrame:
    print("=" * 72)
    print("GREEN ASSET MAPPING | KGFT-INFORMED PORTFOLIO SCREENING")
    print("=" * 72)
    raw = pd.read_csv(input_path)
    print(f"\n[1/6] Loaded {len(raw):,} rows and {len(raw.columns)} columns.")
    raw = validate_portfolio(raw)
    print("[2/6] Schema and data-quality checks passed.")
    quality = pd.DataFrame({
        "missing_values": raw.isna().sum(),
        "missing_pct": (raw.isna().mean() * 100).round(2),
        "unique_values": raw.nunique()
    })
    print("\nData quality summary:")
    print(quality.to_string())

    print("\n[3/6] Portfolio composition:")
    print("\nBorrower segment:\n", raw["borrower_segment"].value_counts().to_string())
    print("\nIndustry sector:\n", raw["industry_sector"].value_counts().to_string())
    print("\n[4/6] Applying exclusion-first taxonomy keyword screening...")
    screened = classify_portfolio(raw)
    print("\nScreening distribution:")
    print(screened["screening_category"].value_counts(dropna=False).to_string())

    screened["validation_status"] = "Not yet validated"
    screened["kgft_alignment_status"] = "Not assessed"
    screened["reviewer_notes"] = ""
    screened["screening_method_version"] = "KGFT-informed-rules-v1.0"

    print("\n[5/6] Portfolio exposure by currency (currencies are not combined):")
    exposure = (screened.groupby(["currency", "screening_category"], dropna=False)
                .agg(loan_count=("loan_id", "count"),
                     disbursed_amount=("disbursed_amount", "sum"))
                .reset_index())
    print(exposure.to_string(index=False))

    print("\n[6/6] Exporting audit register and portfolio summaries...")
    output_dir.mkdir(parents=True, exist_ok=True)
    screened.to_csv(output_dir / "green_asset_mapping_register.csv", index=False)
    exposure.to_csv(output_dir / "portfolio_exposure_by_currency.csv", index=False)
    segment_view = (screened.groupby(["borrower_segment", "screening_category"])
                    .agg(loan_count=("loan_id", "count"),
                         disbursed_amount=("disbursed_amount", "sum")).reset_index())
    county_view = (screened.groupby(["county", "screening_category"])
                   .agg(loan_count=("loan_id", "count"),
                        disbursed_amount=("disbursed_amount", "sum")).reset_index())
    segment_view.to_csv(output_dir / "mapping_by_borrower_segment.csv", index=False)
    county_view.to_csv(output_dir / "mapping_by_county.csv", index=False)

    print(f"\nCompleted. Outputs saved to: {output_dir.resolve()}")
    print("Reminder: a rule-based result is preliminary and is not evidence of KGFT alignment.")
    return screened

def main():
    parser = argparse.ArgumentParser(description="Run KGFT-informed Green Asset Mapping.")
    parser.add_argument("--input", type=Path, default=Path("data/synthetic_kenya_loan_portfolio.csv"),
                        help="Input portfolio CSV.")
    parser.add_argument("--output-dir", type=Path, default=Path("outputs"),
                        help="Directory for CSV output files.")
    args = parser.parse_args()
    run_mapping(args.input, args.output_dir)

if __name__ == "__main__":
    main()
