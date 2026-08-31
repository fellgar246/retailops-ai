"""Supplier-document intake, local storage and deterministic validation."""

from retailops_api.documents.process import process_document
from retailops_api.documents.s3 import S3DocumentStorage
from retailops_api.documents.storage import DocumentStorage, LocalDocumentStorage
from retailops_api.documents.textract import TextractDocumentAnalyzer
from retailops_api.documents.types import Finding, ProcessResult, RuleConfig, SupplierSheetRow
from retailops_api.domain.models.document import (
    DocumentStatus,
    DocumentType,
    FindingSeverity,
)

__all__ = [
    "DocumentStatus",
    "DocumentStorage",
    "DocumentType",
    "Finding",
    "FindingSeverity",
    "LocalDocumentStorage",
    "ProcessResult",
    "RuleConfig",
    "S3DocumentStorage",
    "SupplierSheetRow",
    "TextractDocumentAnalyzer",
    "process_document",
]
