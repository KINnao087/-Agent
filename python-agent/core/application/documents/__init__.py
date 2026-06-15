"""文档处理相关的应用服务。"""

from .linearize_service import LinearizeDocumentsResult, linearize_documents
from .parse_service import ParseDocumentsResult, parse_documents_to_structured_json

__all__ = [
    "LinearizeDocumentsResult",
    "ParseDocumentsResult",
    "linearize_documents",
    "parse_documents_to_structured_json",
]
