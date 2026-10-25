from __future__ import annotations

import unittest

from backend.certifications import certification, public_certifications
from backend.schemas import BatchQuizRequest


class CertificationCatalogTests(unittest.TestCase):
    def test_exposes_the_supported_microsoft_certification_paths(self) -> None:
        catalog = public_certifications()

        self.assertEqual(
            [item["code"] for item in catalog],
            [
                "AI-901",
                "AI-103",
                "AI-200",
                "AI-300",
                "AI-500",
                "AB-100",
                "DP-600",
                "DP-700",
            ],
        )
        for item in catalog:
            self.assertEqual(
                item["study_guide_url"].rsplit("/", maxsplit=1)[-1],
                item["code"].lower(),
            )
            self.assertTrue(item["domains"])

    def test_ai_500_uses_its_official_multi_agent_scope(self) -> None:
        selected = certification("ai-500")

        self.assertEqual(
            selected.title,
            "Designing and Implementing Multi-Agent AI Solutions",
        )
        self.assertIn("Architect multi-agent solutions", selected.domains)

    def test_new_paths_use_their_official_scope(self) -> None:
        self.assertIn(
            "Plan AI-powered business solutions",
            certification("ab-100").domains,
        )
        self.assertIn("Prepare data", certification("dp-600").domains)
        self.assertIn(
            "Ingest and transform data",
            certification("dp-700").domains,
        )

    def test_batch_requests_accept_supported_code_families(self) -> None:
        for code in ("AB-100", "DP-600", "DP-700"):
            with self.subTest(code=code):
                request = BatchQuizRequest(certification_code=code)
                self.assertEqual(request.certification_code, code)


if __name__ == "__main__":
    unittest.main()
