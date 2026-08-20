from __future__ import annotations

from hakim_legal_schema.ingestion import IngestionReport, IngestionStatus


def test_ingestion_report_for_successful_tck_run() -> None:
    report = IngestionReport(
        source="mevzuat",
        document_id="law:5237",
        status=IngestionStatus.SUCCESS,
        articles_found=345,
        warnings=[],
        content_changed=True,
    )
    assert report.status == IngestionStatus.SUCCESS
    assert report.articles_found == 345
    assert report.content_changed is True
