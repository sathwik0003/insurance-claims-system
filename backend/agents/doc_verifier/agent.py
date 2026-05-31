# from __future__ import annotations

# import json
# import logging
# import time

# from groq import AsyncGroq

# from config import get_settings
# from models.api import DocumentVerificationResult
# from models.claim import ClaimCategory, ClaimSubmission
# from models.document import DocumentQuality, DocumentType, UploadedDocument, VerifiedDocument
# from models.trace import TraceEntry
# from services.policy_service import PolicyService

# from .prompts import CLASSIFY_SYSTEM, CLASSIFY_USER

# logger = logging.getLogger(__name__)


# class DocVerifierAgent:
#     """
#     Agent 1 — Document Verification.
#     Runs before any expensive extraction.

#     Checks:
#       1. Each document is readable (not UNREADABLE quality)
#       2. Uploaded document types match policy requirements for the claim category
#       3. All documents belong to the same patient

#     Contract:
#       Input : ClaimSubmission
#       Output: (DocumentVerificationResult, TraceEntry)
#       Errors: Never raises — agent failures return passed=True with error_code=AGENT_FAILURE
#     """

#     def __init__(self, groq_client: AsyncGroq, policy: PolicyService) -> None:
#         self._groq = groq_client
#         self._policy = policy

#     async def run(
#         self, submission: ClaimSubmission
#     ) -> tuple[DocumentVerificationResult, TraceEntry]:
#         started = time.monotonic()
#         entry = TraceEntry(
#             component="DocVerifierAgent",
#             input_summary={
#                 "member_id": submission.member_id,
#                 "category": submission.claim_category,
#                 "doc_count": len(submission.documents),
#             },
#         )

#         try:
#             verified = [await self._classify(doc) for doc in submission.documents]

#             # Check 1 — unreadable docs
#             unreadable = [d for d in verified if d.quality == DocumentQuality.UNREADABLE]
#             if unreadable:
#                 names = ", ".join(f"'{d.file_name}'" for d in unreadable)
#                 return self._fail(
#                     entry, started, "UNREADABLE_DOCUMENT",
#                     f"The following document(s) could not be read: {names}. "
#                     "Please re-upload a clearer photo with good lighting and all text in focus.",
#                     verified,
#                 )

#             # Check 2 — wrong document types
#             if err := self._check_types(verified, submission.claim_category):
#                 return self._fail(entry, started, "WRONG_DOCUMENT_TYPE", err, verified)

#             # Check 3 — patient mismatch
#             if err := self._check_patient_consistency(verified):
#                 return self._fail(entry, started, "PATIENT_MISMATCH", err, verified)

#             result = DocumentVerificationResult(passed=True, verified_documents=verified)
#             entry.output_summary = {
#                 "passed": True,
#                 "docs": [
#                     {"file": d.file_name, "type": d.classified_type, "quality": d.quality}
#                     for d in verified
#                 ],
#             }

#         except Exception as exc:
#             logger.warning("DocVerifierAgent failed: %s", exc)
#             result = DocumentVerificationResult(
#                 passed=True,
#                 error_code="AGENT_FAILURE",
#                 error_message=f"Verification skipped due to agent error: {exc}",
#             )
#             entry.error = str(exc)

#         entry.duration_ms = int((time.monotonic() - started) * 1000)
#         return result, entry

#     # ── Private ───────────────────────────────────────────────────────────────

#     async def _classify(self, doc: UploadedDocument) -> VerifiedDocument:
#         if not doc.content_base64:
#             return VerifiedDocument(
#                 file_id=doc.file_id, file_name=doc.file_name,
#                 classified_type=DocumentType.UNKNOWN,
#                 quality=DocumentQuality.DEGRADED,
#                 classification_confidence=0.0,
#                 classification_reasoning="No image content provided",
#             )

#         resp = await self._groq.chat.completions.create(
#             model=get_settings().groq_vision_model,
#             messages=[
#                 {"role": "system", "content": CLASSIFY_SYSTEM},
#                 {
#                     "role": "user",
#                     "content": [
#                         {"type": "image_url", "image_url": {
#                             "url": f"data:{doc.mime_type};base64,{doc.content_base64}"
#                         }},
#                         {"type": "text", "text": CLASSIFY_USER},
#                     ],
#                 },
#             ],
#             max_tokens=300,
#             temperature=0,
#         )

#         data = self._parse_json(resp.choices[0].message.content)
#         return VerifiedDocument(
#             file_id=doc.file_id,
#             file_name=doc.file_name,
#             classified_type=DocumentType(data.get("document_type", "UNKNOWN")),
#             quality=DocumentQuality(data.get("quality", "DEGRADED")),
#             patient_name_on_doc=data.get("patient_name"),
#             classification_confidence=float(data.get("confidence", 0.5)),
#             classification_reasoning=data.get("reasoning", ""),
#         )

#     def _check_types(
#         self, verified: list[VerifiedDocument], category: ClaimCategory
#     ) -> str | None:
#         required = self._policy.required_document_types(category)
#         optional = self._policy.optional_document_types(category)
#         provided = [d.classified_type for d in verified]

#         missing = [r for r in required if r not in provided]
#         unexpected = [
#             d for d in verified
#             if d.classified_type not in required
#             and d.classified_type not in optional
#             and d.classified_type != DocumentType.UNKNOWN
#         ]

#         if not missing and not unexpected:
#             return None

#         parts = []
#         if missing:
#             parts.append(
#                 "Missing required: "
#                 + " and ".join(t.value.replace("_", " ").title() for t in missing)
#             )
#         for d in unexpected:
#             wrong = d.classified_type.value.replace("_", " ").title()
#             needed = " and ".join(t.value.replace("_", " ").title() for t in required)
#             parts.append(
#                 f"'{d.file_name}' is a {wrong}, but this claim requires: {needed}"
#             )

#         return " | ".join(parts) + ". Please re-upload the correct documents."

#     def _check_patient_consistency(self, verified: list[VerifiedDocument]) -> str | None:
#         named = [d for d in verified if d.patient_name_on_doc]
#         if len(named) < 2:
#             return None
#         norm = lambda n: " ".join(n.lower().split())
#         base = norm(named[0].patient_name_on_doc)
#         mismatches = [d for d in named[1:] if norm(d.patient_name_on_doc) != base]
#         if not mismatches:
#             return None
#         detail = ", ".join(f"'{d.file_name}' → {d.patient_name_on_doc}" for d in named)
#         return (
#             "Documents belong to different patients. "
#             f"Names found: {detail}. All documents must be for the same patient."
#         )

#     @staticmethod
#     def _parse_json(raw: str) -> dict:
#         raw = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
#         try:
#             return json.loads(raw)
#         except json.JSONDecodeError:
#             return {"document_type": "UNKNOWN", "quality": "DEGRADED", "confidence": 0.3}

#     def _fail(
#         self,
#         entry: TraceEntry,
#         started: float,
#         code: str,
#         message: str,
#         verified: list[VerifiedDocument] | None = None,
#     ) -> tuple[DocumentVerificationResult, TraceEntry]:
#         entry.output_summary = {"passed": False, "error_code": code}
#         entry.duration_ms = int((time.monotonic() - started) * 1000)
#         return (
#             DocumentVerificationResult(
#                 passed=False,
#                 verified_documents=verified or [],
#                 error_code=code,
#                 error_message=message,
#             ),
#             entry,
#         )






from __future__ import annotations

import json
import logging
import time

from groq import AsyncGroq

from config import get_settings
from models.api import DocumentVerificationResult
from models.claim import ClaimCategory, ClaimSubmission
from models.document import DocumentQuality, DocumentType, UploadedDocument, VerifiedDocument
from models.trace import TraceEntry
from services.policy_service import PolicyService

from .prompts import CLASSIFY_SYSTEM, CLASSIFY_USER

logger = logging.getLogger(__name__)


class DocVerifierAgent:
    """
    Agent 1 — Document Verification.
    Runs before any expensive extraction.

    Checks:
      1. Each document is readable (not UNREADABLE quality)
      2. Uploaded document types match policy requirements for the claim category
      3. All documents belong to the same patient

    Contract:
      Input : ClaimSubmission
      Output: (DocumentVerificationResult, TraceEntry)
      Errors: Never raises — agent failures return passed=True with error_code=AGENT_FAILURE
    """

    def __init__(self, groq_client: AsyncGroq, policy: PolicyService) -> None:
        self._groq = groq_client
        self._policy = policy

    async def run(
        self, submission: ClaimSubmission
    ) -> tuple[DocumentVerificationResult, TraceEntry]:
        started = time.monotonic()
        entry = TraceEntry(
            component="DocVerifierAgent",
            input_summary={
                "member_id": submission.member_id,
                "category": submission.claim_category,
                "doc_count": len(submission.documents),
            },
        )

        try:
            verified = [await self._classify(doc) for doc in submission.documents]

            # Check 1 — unreadable docs
            unreadable = [d for d in verified if d.quality == DocumentQuality.UNREADABLE]
            if unreadable:
                names = ", ".join(f"'{d.file_name}'" for d in unreadable)
                return self._fail(
                    entry, started, "UNREADABLE_DOCUMENT",
                    f"The following document(s) could not be read: {names}. "
                    "Please re-upload a clearer photo with good lighting and all text in focus.",
                    verified,
                )

            # Check 2 — wrong document types
            if err := self._check_types(verified, submission.claim_category):
                return self._fail(entry, started, "WRONG_DOCUMENT_TYPE", err, verified)

            # Check 3 — patient mismatch across documents
            if err := self._check_patient_consistency(verified):
                return self._fail(entry, started, "PATIENT_MISMATCH", err, verified)

            # Check 4 — patient name vs actual policy member
            if err := self._check_patient_vs_member(verified, submission.member_id):
                return self._fail(entry, started, "PATIENT_MISMATCH", err, verified)

            result = DocumentVerificationResult(passed=True, verified_documents=verified)
            entry.output_summary = {
                "passed": True,
                "docs": [
                    {
                        "file": d.file_name,
                        "type": d.classified_type.value,
                        "quality": d.quality.value,
                        "confidence": round(d.classification_confidence, 2),
                        "llm_reasoning": d.classification_reasoning,
                    }
                    for d in verified
                ],
            }

        except Exception as exc:
            logger.warning("DocVerifierAgent failed: %s", exc)
            result = DocumentVerificationResult(
                passed=True,
                error_code="AGENT_FAILURE",
                error_message=f"Verification skipped due to agent error: {exc}",
            )
            entry.error = str(exc)

        entry.duration_ms = int((time.monotonic() - started) * 1000)
        return result, entry

    # ── Private ───────────────────────────────────────────────────────────────

    async def _classify(self, doc: UploadedDocument) -> VerifiedDocument:
        if not doc.content_base64:
            return VerifiedDocument(
                file_id=doc.file_id, file_name=doc.file_name,
                classified_type=DocumentType.UNKNOWN,
                quality=DocumentQuality.DEGRADED,
                classification_confidence=0.0,
                classification_reasoning="No image content provided",
            )

        resp = await self._groq.chat.completions.create(
            model=get_settings().groq_vision_model,
            messages=[
                {"role": "system", "content": CLASSIFY_SYSTEM},
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {
                            "url": f"data:{doc.mime_type};base64,{doc.content_base64}"
                        }},
                        {"type": "text", "text": CLASSIFY_USER},
                    ],
                },
            ],
            max_tokens=300,
            temperature=0,
        )

        data = self._parse_json(resp.choices[0].message.content)
        return VerifiedDocument(
            file_id=doc.file_id,
            file_name=doc.file_name,
            classified_type=DocumentType(data.get("document_type", "UNKNOWN")),
            quality=DocumentQuality(data.get("quality", "DEGRADED")),
            patient_name_on_doc=data.get("patient_name"),
            classification_confidence=float(data.get("confidence", 0.5)),
            classification_reasoning=data.get("reasoning", ""),
        )

    def _check_types(
        self, verified: list[VerifiedDocument], category: ClaimCategory
    ) -> str | None:
        required = self._policy.required_document_types(category)
        optional = self._policy.optional_document_types(category)
        provided = [d.classified_type for d in verified]

        missing = [r for r in required if r not in provided]
        unexpected = [
            d for d in verified
            if d.classified_type not in required
            and d.classified_type not in optional
            and d.classified_type != DocumentType.UNKNOWN
        ]

        if not missing and not unexpected:
            return None

        parts = []
        if missing:
            parts.append(
                "Missing required: "
                + " and ".join(t.value.replace("_", " ").title() for t in missing)
            )
        for d in unexpected:
            wrong = d.classified_type.value.replace("_", " ").title()
            needed = " and ".join(t.value.replace("_", " ").title() for t in required)
            parts.append(
                f"'{d.file_name}' is a {wrong}, but this claim requires: {needed}"
            )

        return " | ".join(parts) + ". Please re-upload the correct documents."

    def _check_patient_consistency(self, verified: list[VerifiedDocument]) -> str | None:
        named = [d for d in verified if d.patient_name_on_doc]
        if len(named) < 2:
            return None
        norm = lambda n: " ".join(n.lower().split())
        base = norm(named[0].patient_name_on_doc)
        mismatches = [d for d in named[1:] if norm(d.patient_name_on_doc) != base]
        if not mismatches:
            return None
        detail = ", ".join(f"'{d.file_name}' → {d.patient_name_on_doc}" for d in named)
        return (
            "Documents belong to different patients. "
            f"Names found: {detail}. All documents must be for the same patient."
        )

    def _check_patient_vs_member(
        self, verified: list, member_id: str
    ) -> str | None:
        """
        Compare patient names found on documents against the actual
        policy member's name. Catches someone submitting another person's
        documents for their own claim.

        Uses word-overlap so 'R. Kumar' still matches 'Rajesh Kumar'.
        Only blocks when we have at least one name AND it clearly doesn't
        match — avoids false positives when names are illegible.
        """
        member = self._policy.get_member(member_id)
        if not member:
            return None  # member validity handled by rules engine

        member_name = member['name']
        # Use meaningful words only (skip initials like 'R.')
        member_words = {w.lower() for w in member_name.split() if len(w) > 2}

        named_docs = [d for d in verified if d.patient_name_on_doc]
        if not named_docs:
            return None  # no names found — cannot verify, let it through

        mismatches = []
        for doc in named_docs:
            doc_words = {w.lower() for w in doc.patient_name_on_doc.split() if len(w) > 2}
            if not (member_words & doc_words):
                mismatches.append(f"'{doc.patient_name_on_doc}' on {doc.file_name}")

        if not mismatches:
            return None

        return (
            f"Document(s) belong to a different patient, not the insured member '{member_name}'. "
            f"Name(s) found on documents: {', '.join(mismatches)}. "
            "Please submit documents that belong to the member making this claim."
        )

    @staticmethod
    def _parse_json(raw: str) -> dict:
        raw = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {"document_type": "UNKNOWN", "quality": "DEGRADED", "confidence": 0.3}

    def _fail(
        self,
        entry: TraceEntry,
        started: float,
        code: str,
        message: str,
        verified: list[VerifiedDocument] | None = None,
    ) -> tuple[DocumentVerificationResult, TraceEntry]:
        entry.output_summary = {"passed": False, "error_code": code}
        entry.duration_ms = int((time.monotonic() - started) * 1000)
        return (
            DocumentVerificationResult(
                passed=False,
                verified_documents=verified or [],
                error_code=code,
                error_message=message,
            ),
            entry,
        )