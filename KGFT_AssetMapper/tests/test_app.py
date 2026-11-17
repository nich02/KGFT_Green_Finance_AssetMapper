import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

import app
from taxonomy_engine import classify_portfolio


class AppTests(unittest.TestCase):
    def test_empty_portfolio_retains_screening_columns(self):
        result = classify_portfolio(pd.DataFrame(columns=app.EXPECTED_COLUMNS))
        self.assertIn("screening_category", result.columns)
        self.assertTrue(result.empty)

    def test_dashboard_and_about_render(self):
        client = app.app.test_client()
        dashboard = client.get("/")
        self.assertEqual(dashboard.status_code, 200)
        self.assertIn(b"Executive overview", dashboard.data)
        self.assertIn(b"Portfolio screening distribution", dashboard.data)
        dashboard_html = dashboard.data.decode()
        self.assertLess(
            dashboard_html.index("＋ Choose portfolio"),
            dashboard_html.index(">Screen</button>"),
        )
        self.assertLess(
            dashboard_html.index(">Screen</button>"),
            dashboard_html.index("Export workbook"),
        )
        self.assertEqual(client.get("/about").status_code, 200)

    def test_export_contains_four_screening_sheets(self):
        source = pd.DataFrame([
            {
                "loan_id": "GREEN-001", "product_description": "photovoltaic solar panels",
                "purpose": "solar installation",
            },
            {
                "loan_id": "REVIEW-001", "product_description": "heat pump",
                "purpose": "equipment financing",
            },
            {
                "loan_id": "OTHER-001", "product_description": "general retail",
                "purpose": "working capital",
            },
            {
                "loan_id": "EXCLUDED-001", "product_description": "diesel generator",
                "purpose": "backup power",
            },
        ])
        screened = classify_portfolio(source)
        with patch.object(app, "load_screened_data", return_value=screened):
            response = app.app.test_client().get("/export")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.mimetype,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        workbook = pd.ExcelFile(io.BytesIO(response.data))
        self.assertEqual(
            workbook.sheet_names,
            ["All assets", "Green identified", "Manual assessment", "Not green"],
        )
        self.assertEqual(len(pd.read_excel(workbook, "All assets")), 4)
        self.assertEqual(len(pd.read_excel(workbook, "Green identified")), 1)
        self.assertEqual(len(pd.read_excel(workbook, "Manual assessment")), 1)
        not_green = pd.read_excel(workbook, "Not green")
        self.assertEqual(len(not_green), 2)
        self.assertEqual(set(not_green["loan_id"]), {"OTHER-001", "EXCLUDED-001"})

    def test_search_treats_regex_metacharacters_as_literals(self):
        response = app.app.test_client().get("/?q=%5B")
        self.assertEqual(response.status_code, 200)

    def test_dashboard_renders_when_default_data_is_missing(self):
        with tempfile.TemporaryDirectory() as directory:
            missing_data = Path(directory) / "missing.csv"
            with patch.object(app, "DEFAULT_DATA", missing_data), patch.object(
                app, "ACTIVE_UPLOAD", Path(directory) / "missing-upload.csv"
            ):
                response = app.app.test_client().get("/")
            self.assertEqual(response.status_code, 200)

    def test_upload_validates_and_activates_csv(self):
        csv_content = (
            "loan_id,origination_date,borrower_segment,industry_sector,county,"
            "product_description,purpose,collateral_type,currency,disbursed_amount,tenor_period\n"
            "TEST-001,2025-01-01,SME,Energy,Nairobi,solar panels,solar installation,"
            "Equipment,KES,1000,12 months\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            temp_dir = Path(directory)
            active_upload = temp_dir / "active.csv"
            with patch.object(app, "ACTIVE_UPLOAD", active_upload), patch.object(
                app, "UPLOAD_DIR", temp_dir
            ):
                response = app.app.test_client().post(
                    "/upload",
                    data={"portfolio": (io.BytesIO(csv_content.encode()), "portfolio.csv")},
                    content_type="multipart/form-data",
                    follow_redirects=True,
                )
            self.assertEqual(response.status_code, 200)
            self.assertTrue(active_upload.exists())
