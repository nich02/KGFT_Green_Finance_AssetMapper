from pathlib import Path
import io
import pandas as pd
from flask import Flask, render_template, request, redirect, url_for, flash, send_file
from werkzeug.utils import secure_filename
from taxonomy_engine import classify_portfolio

BASE = Path(__file__).resolve().parent
DEFAULT_DATA = BASE / "data" / "synthetic_kenya_loan_portfolio.csv"
UPLOAD_DIR = BASE / "uploads"
ACTIVE_UPLOAD = UPLOAD_DIR / "active_portfolio.csv"
MAX_UPLOAD_BYTES = 10 * 1024 * 1024

EXPECTED_COLUMNS = [
    "loan_id", "origination_date", "borrower_segment", "industry_sector",
    "county", "product_description", "purpose", "collateral_type",
    "currency", "disbursed_amount", "tenor_period"
]

app = Flask(__name__)
app.secret_key = "replace-this-with-an-environment-secret"
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_BYTES

def active_data_path():
    return ACTIVE_UPLOAD if ACTIVE_UPLOAD.exists() else DEFAULT_DATA

def load_raw_data():
    data = pd.read_csv(active_data_path())
    missing = sorted(set(EXPECTED_COLUMNS) - set(data.columns))
    if missing:
        raise ValueError("Missing required columns: " + ", ".join(missing))
    data["disbursed_amount"] = pd.to_numeric(data["disbursed_amount"], errors="coerce")
    if data["loan_id"].isna().any() or data["loan_id"].astype(str).str.strip().eq("").any():
        raise ValueError("Every row must have a loan_id.")
    if data["loan_id"].duplicated().any():
        raise ValueError("loan_id values must be unique.")
    if data["disbursed_amount"].isna().any() or data["disbursed_amount"].lt(0).any():
        raise ValueError("disbursed_amount must contain valid non-negative numbers.")
    return data

def load_screened_data():
    return classify_portfolio(load_raw_data())

def register_group(data, group):
    if group == "green":
        return data[data.screening_category.eq("Potential Green — Validation Required")]
    if group == "review":
        return data[data.screening_category.eq("Manual Assessment")]
    if group == "other":
        return data[data.screening_category.isin([
            "Other / Insufficient evidence", "Excluded / Potential exclusion"
        ])]
    return data

@app.route("/", methods=["GET"])
def index():
    try:
        data = load_screened_data()
    except Exception as exc:
        flash(f"Portfolio could not be loaded: {exc}", "error")
        data = classify_portfolio(pd.DataFrame(columns=EXPECTED_COLUMNS))

    group = request.args.get("group", "all")
    if group not in {"all", "green", "review", "other"}:
        group = "all"
    search = request.args.get("q", "").strip().lower()
    view = register_group(data, group)
    if search and not view.empty:
        mask = view.astype(str).apply(
            lambda col: col.str.lower().str.contains(search, na=False, regex=False)
        ).any(axis=1)
        view = view[mask]

    counts = {
        "all": int(len(data)),
        "green": int(data.screening_category.eq("Potential Green — Validation Required").sum()),
        "review": int(data.screening_category.eq("Manual Assessment").sum()),
        "other": int(data.screening_category.isin([
            "Other / Insufficient evidence", "Excluded / Potential exclusion"
        ]).sum())
    }
    totals = data.groupby("currency").disbursed_amount.sum().to_dict() if not data.empty else {}
    potential = data[data.screening_category.eq(
        "Potential Green — Validation Required"
    )].groupby("currency").disbursed_amount.sum().to_dict() if not data.empty else {}
    pending = counts["green"] + counts["review"]
    chart = {"potential": counts["green"], "review": counts["review"], "other": counts["other"]}
    rows = view.head(10).copy()
    if "origination_date" in rows:
        rows["origination_date"] = rows["origination_date"].astype(str)
    records = rows.fillna("").to_dict(orient="records")
    uploaded_name = "Uploaded portfolio" if ACTIVE_UPLOAD.exists() else "Synthetic demonstration portfolio"
    return render_template(
        "index.html", rows=records, view_total=len(view), total=len(data), pending=pending,
        totals=totals, potential=potential, chart=chart, group=group,
        q=search, counts=counts, uploaded_name=uploaded_name
    )

@app.route("/upload", methods=["POST"])
def upload_portfolio():
    file = request.files.get("portfolio")
    if not file or not file.filename:
        flash("Choose a CSV file before uploading.", "error")
        return redirect(url_for("index"))
    if Path(secure_filename(file.filename)).suffix.lower() != ".csv":
        flash("Only CSV files are accepted.", "error")
        return redirect(url_for("index"))
    try:
        raw = pd.read_csv(file)
        missing = sorted(set(EXPECTED_COLUMNS) - set(raw.columns))
        if missing:
            raise ValueError("Missing required columns: " + ", ".join(missing))
        raw["disbursed_amount"] = pd.to_numeric(raw["disbursed_amount"], errors="coerce")
        if raw["loan_id"].isna().any() or raw["loan_id"].astype(str).str.strip().eq("").any():
            raise ValueError("Every row must have a loan_id.")
        if raw["loan_id"].duplicated().any():
            raise ValueError("loan_id values must be unique.")
        if raw["disbursed_amount"].isna().any() or raw["disbursed_amount"].lt(0).any():
            raise ValueError("disbursed_amount must contain valid non-negative numbers.")
        # Run the mapping engine before activating the upload.
        classify_portfolio(raw)
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        raw.to_csv(ACTIVE_UPLOAD, index=False)
        flash(f"Portfolio uploaded and screened successfully ({len(raw):,} assets).", "success")
    except Exception as exc:
        flash(f"Upload rejected: {exc}", "error")
    return redirect(url_for("index"))

@app.route("/export", methods=["GET"])
def export_portfolio():
    data = load_screened_data()
    output = io.BytesIO()
    sheets = [
        ("All assets", data),
        ("Green identified", register_group(data, "green")),
        ("Manual assessment", register_group(data, "review")),
        ("Not green", register_group(data, "other")),
    ]
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for sheet_name, sheet_data in sheets:
            sheet_data.to_excel(writer, sheet_name=sheet_name, index=False)
    output.seek(0)
    return send_file(
        output,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name="green_asset_mapping_register.xlsx",
    )

@app.route("/reset", methods=["POST"])
def reset_portfolio():
    if ACTIVE_UPLOAD.exists():
        ACTIVE_UPLOAD.unlink()
        flash("Returned to the bundled synthetic demonstration portfolio.", "success")
    return redirect(url_for("index"))

@app.route("/about")
def about():
    return render_template("about.html")

@app.errorhandler(413)
def too_large(_error):
    flash("The uploaded CSV is larger than the 10 MB limit.", "error")
    return redirect(url_for("index"))

if __name__ == "__main__":
    # Local development only. Set debug=False outside development.
    app.run(host="127.0.0.1", port=5000, debug=False)
