# Green Asset Mapping — KGFT-informed portfolio screening

## Run the Flask dashboard
```bash
python -m pip install -r requirements.txt
python app.py
```
Open http://127.0.0.1:5000

Run these commands from the `KGFT_AssetMapper` directory. The bundled
demonstration portfolio is at `data/synthetic_kenya_loan_portfolio.csv`.
To run the smoke tests, use `python -m unittest discover -s tests` from this directory.

## Test on GitHub Pages
The repository root `index.html` hosts the browser-only dashboard from
`dashboard_preview.html`. On GitHub Pages, choose a CSV from your computer;
screening happens locally in your browser, and the selected dataset is not
uploaded or saved by the site. The static dashboard exports an Excel workbook
with `All assets`, `Green identified`, `Manual assessment`, and `Not green`
sheets. The Flask server is not run by GitHub Pages.
The expected Pages URL is
https://nich02.github.io/KGFT_Green_Finance_AssetMapper/ after deployment succeeds.

## Upload and export
- Upload a CSV using the dashboard's **Upload portfolio** control.
- The CSV must contain: `loan_id`, `origination_date`, `borrower_segment`, `industry_sector`, `county`, `product_description`, `purpose`, `collateral_type`, `currency`, `disbursed_amount`, `tenor_period`.
- The app validates the required schema, unique loan IDs and non-negative numeric disbursements before activating the file.
- **Export workbook** downloads an Excel workbook with `All assets`, `Green identified`, `Manual assessment`, and `Not green` sheets. Each sheet includes taxonomy theme, rule score, matched evidence and rationale.
- Use **Restore demonstration portfolio** to return to the bundled synthetic data.

## Run the converted Python script
```bash
python GreenAssetMapping.py --input data/synthetic_kenya_loan_portfolio.csv --output-dir outputs
```
The script creates an auditable mapping register and currency-separated portfolio summaries.

## Classification tabs
- Green identified: `Potential Green — Validation Required`
- Manual assessment: `Manual Assessment`
- Not green: `Other / Insufficient evidence` plus `Excluded / Potential exclusion`

The counts update from the currently loaded portfolio. The register preview shows the first 10 matching assets.

## Important
This is a preliminary KGFT-informed keyword screening prototype, not a taxonomy certification tool. A final alignment decision requires evidence against the relevant activity eligibility, technical screening criteria, DNSH and minimum social safeguards. Financial amounts are not added across currencies.

The Flask demo stores one active upload in `uploads/active_portfolio.csv`; it is intended for local demonstration, not concurrent multi-user production deployment. For production, use authenticated user-specific storage and a database.
