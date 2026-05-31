# # from __future__ import annotations

# # import json
# # import logging
# # import time
# # from datetime import date

# # from groq import AsyncGroq

# # from config import get_settings
# # from models.document import DocumentQuality, LineItem, ParsedDocument, VerifiedDocument
# # from models.trace import TraceEntry

# # from .prompts import EXTRACT_SYSTEM

# # logger = logging.getLogger(__name__)


# # class DocParserAgent:
# #     """
# #     Agent 2 — Document Parsing.
# #     Calls Groq Vision on each verified document and returns structured ParsedDocument objects.

# #     Contract:
# #       Input : list[VerifiedDocument], base64 map, mime map
# #       Output: (list[ParsedDocument], TraceEntry)
# #       Errors: Per-document failures are isolated — the list always has one entry per input.
# #     """

# #     def __init__(self, groq_client: AsyncGroq) -> None:
# #         self._groq = groq_client

# #     async def run(
# #         self,
# #         verified_docs: list[VerifiedDocument],
# #         b64_map: dict[str, str],
# #         mime_map: dict[str, str],
# #     ) -> tuple[list[ParsedDocument], TraceEntry]:
# #         started = time.monotonic()
# #         entry = TraceEntry(
# #             component="DocParserAgent",
# #             input_summary={"doc_count": len(verified_docs)},
# #         )

# #         parsed: list[ParsedDocument] = []
# #         errors: list[str] = []

# #         for vdoc in verified_docs:
# #             if vdoc.quality == DocumentQuality.UNREADABLE:
# #                 parsed.append(ParsedDocument(
# #                     file_id=vdoc.file_id, document_type=vdoc.classified_type,
# #                     quality=vdoc.quality, extraction_notes="Skipped — UNREADABLE",
# #                 ))
# #                 continue
# #             try:
# #                 pdoc = await self._extract(
# #                     vdoc, b64_map.get(vdoc.file_id), mime_map.get(vdoc.file_id, "image/jpeg")
# #                 )
# #                 parsed.append(pdoc)
# #             except Exception as exc:
# #                 errors.append(f"{vdoc.file_name}: {exc}")
# #                 logger.warning("DocParserAgent extraction failed for %s: %s", vdoc.file_id, exc)
# #                 parsed.append(ParsedDocument(
# #                     file_id=vdoc.file_id, document_type=vdoc.classified_type,
# #                     quality=DocumentQuality.DEGRADED,
# #                     extraction_notes=f"Extraction failed: {exc}",
# #                 ))

# #         avg_conf = round(sum(p.overall_confidence for p in parsed) / max(len(parsed), 1), 3)
# #         entry.output_summary = {"parsed": len(parsed), "avg_confidence": avg_conf, "errors": errors}
# #         if errors:
# #             entry.error = "; ".join(errors)
# #         entry.duration_ms = int((time.monotonic() - started) * 1000)
# #         return parsed, entry

# #     async def _extract(
# #         self, vdoc: VerifiedDocument, b64: str | None, mime: str
# #     ) -> ParsedDocument:
# #         if not b64:
# #             return ParsedDocument(
# #                 file_id=vdoc.file_id, document_type=vdoc.classified_type,
# #                 quality=vdoc.quality, extraction_notes="No image content",
# #             )

# #         resp = await self._groq.chat.completions.create(
# #             model=get_settings().groq_vision_model,
# #             messages=[
# #                 {"role": "system", "content": EXTRACT_SYSTEM},
# #                 {
# #                     "role": "user",
# #                     "content": [
# #                         {"type": "image_url", "image_url": {
# #                             "url": f"data:{mime};base64,{b64}"
# #                         }},
# #                         {"type": "text", "text": (
# #                             f"Document type: {vdoc.classified_type.value.replace('_', ' ').title()}. "
# #                             "Extract all available information."
# #                         )},
# #                     ],
# #                 },
# #             ],
# #             max_tokens=1000,
# #             temperature=0,
# #         )

# #         data = self._parse_json(resp.choices[0].message.content)

# #         doc_date: date | None = None
# #         if raw_date := data.get("document_date"):
# #             try:
# #                 doc_date = date.fromisoformat(raw_date)
# #             except (ValueError, TypeError):
# #                 pass

# #         return ParsedDocument(
# #             file_id=vdoc.file_id,
# #             document_type=vdoc.classified_type,
# #             quality=vdoc.quality,
# #             patient_name=data.get("patient_name"),
# #             doctor_name=data.get("doctor_name"),
# #             doctor_registration=data.get("doctor_registration"),
# #             hospital_name=data.get("hospital_name"),
# #             document_date=doc_date,
# #             diagnosis=data.get("diagnosis"),
# #             treatment=data.get("treatment"),
# #             medicines=data.get("medicines") or [],
# #             tests_ordered=data.get("tests_ordered") or [],
# #             line_items=[
# #                 LineItem(
# #                     description=item.get("description", "Unknown"),
# #                     amount=float(item.get("amount", 0)),
# #                 )
# #                 for item in (data.get("line_items") or [])
# #             ],
# #             total_amount=data.get("total_amount"),
# #             gst_amount=float(data.get("gst_amount") or 0),
# #             field_confidences=data.get("field_confidences") or {},
# #             extraction_notes=data.get("extraction_notes") or "",
# #         )

# #     @staticmethod
# #     def _parse_json(raw: str) -> dict:
# #         raw = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
# #         try:
# #             return json.loads(raw)
# #         except json.JSONDecodeError:
# #             return {"extraction_notes": f"JSON parse failed. Snippet: {raw[:100]}"}




# from __future__ import annotations

# import json
# import logging
# import time
# from datetime import date

# from groq import AsyncGroq

# from config import get_settings
# from models.document import DocumentQuality, LineItem, ParsedDocument, VerifiedDocument
# from models.trace import TraceEntry

# from .prompts import EXTRACT_SYSTEM

# logger = logging.getLogger(__name__)


# class DocParserAgent:
#     """
#     Agent 2 — Document Parsing.
#     Calls Groq Vision on each verified document and returns structured ParsedDocument objects.

#     Contract:
#       Input : list[VerifiedDocument], base64 map, mime map
#       Output: (list[ParsedDocument], TraceEntry)
#       Errors: Per-document failures are isolated — the list always has one entry per input.
#     """

#     def __init__(self, groq_client: AsyncGroq) -> None:
#         self._groq = groq_client

#     async def run(
#         self,
#         verified_docs: list[VerifiedDocument],
#         b64_map: dict[str, str],
#         mime_map: dict[str, str],
#     ) -> tuple[list[ParsedDocument], TraceEntry]:
#         started = time.monotonic()
#         entry = TraceEntry(
#             component="DocParserAgent",
#             input_summary={"doc_count": len(verified_docs)},
#         )

#         parsed: list[ParsedDocument] = []
#         errors: list[str] = []

#         for vdoc in verified_docs:
#             if vdoc.quality == DocumentQuality.UNREADABLE:
#                 parsed.append(ParsedDocument(
#                     file_id=vdoc.file_id, document_type=vdoc.classified_type,
#                     quality=vdoc.quality, extraction_notes="Skipped — UNREADABLE",
#                 ))
#                 continue
#             try:
#                 pdoc = await self._extract(
#                     vdoc, b64_map.get(vdoc.file_id), mime_map.get(vdoc.file_id, "image/jpeg")
#                 )
#                 parsed.append(pdoc)
#             except Exception as exc:
#                 errors.append(f"{vdoc.file_name}: {exc}")
#                 logger.warning("DocParserAgent extraction failed for %s: %s", vdoc.file_id, exc)
#                 parsed.append(ParsedDocument(
#                     file_id=vdoc.file_id, document_type=vdoc.classified_type,
#                     quality=DocumentQuality.DEGRADED,
#                     extraction_notes=f"Extraction failed: {exc}",
#                 ))

#         avg_conf = round(sum(p.overall_confidence for p in parsed) / max(len(parsed), 1), 3)
#         entry.output_summary = {
#             "parsed": len(parsed),
#             "avg_confidence": avg_conf,
#             "errors": errors,
#             "extractions": [
#                 {
#                     "file": p.file_id,
#                     "patient": p.patient_name,
#                     "diagnosis": p.diagnosis,
#                     "doctor": p.doctor_name,
#                     "hospital": p.hospital_name,
#                     "total_amount": p.total_amount,
#                     "field_confidences": p.field_confidences,
#                     "llm_notes": p.extraction_notes,
#                 }
#                 for p in parsed
#             ],
#         }
#         if errors:
#             entry.error = "; ".join(errors)
#         entry.duration_ms = int((time.monotonic() - started) * 1000)
#         return parsed, entry

#     async def _extract(
#         self, vdoc: VerifiedDocument, b64: str | None, mime: str
#     ) -> ParsedDocument:
#         if not b64:
#             return ParsedDocument(
#                 file_id=vdoc.file_id, document_type=vdoc.classified_type,
#                 quality=vdoc.quality, extraction_notes="No image content",
#             )

#         resp = await self._groq.chat.completions.create(
#             model=get_settings().groq_vision_model,
#             messages=[
#                 {"role": "system", "content": EXTRACT_SYSTEM},
#                 {
#                     "role": "user",
#                     "content": [
#                         {"type": "image_url", "image_url": {
#                             "url": f"data:{mime};base64,{b64}"
#                         }},
#                         {"type": "text", "text": (
#                             f"Document type: {vdoc.classified_type.value.replace('_', ' ').title()}. "
#                             "Extract all available information."
#                         )},
#                     ],
#                 },
#             ],
#             max_tokens=1000,
#             temperature=0,
#         )

#         data = self._parse_json(resp.choices[0].message.content)

#         doc_date: date | None = None
#         if raw_date := data.get("document_date"):
#             try:
#                 doc_date = date.fromisoformat(raw_date)
#             except (ValueError, TypeError):
#                 pass

#         return ParsedDocument(
#             file_id=vdoc.file_id,
#             document_type=vdoc.classified_type,
#             quality=vdoc.quality,
#             patient_name=data.get("patient_name"),
#             doctor_name=data.get("doctor_name"),
#             doctor_registration=data.get("doctor_registration"),
#             hospital_name=data.get("hospital_name"),
#             document_date=doc_date,
#             diagnosis=data.get("diagnosis"),
#             treatment=data.get("treatment"),
#             medicines=data.get("medicines") or [],
#             tests_ordered=data.get("tests_ordered") or [],
#             line_items=[
#                 LineItem(
#                     description=item.get("description", "Unknown"),
#                     amount=float(item.get("amount", 0)),
#                 )
#                 for item in (data.get("line_items") or [])
#             ],
#             total_amount=data.get("total_amount"),
#             gst_amount=float(data.get("gst_amount") or 0),
#             field_confidences=data.get("field_confidences") or {},
#             extraction_notes=data.get("extraction_notes") or "",
#         )

#     @staticmethod
#     def _parse_json(raw: str) -> dict:
#         raw = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
#         try:
#             return json.loads(raw)
#         except json.JSONDecodeError:
#             return {"extraction_notes": f"JSON parse failed. Snippet: {raw[:100]}"}


from __future__ import annotations

import json
import logging
import time
from datetime import date

from groq import AsyncGroq

from config import get_settings
from models.document import DocumentQuality, LineItem, ParsedDocument, VerifiedDocument
from models.trace import TraceEntry

from .prompts import EXTRACT_SYSTEM

logger = logging.getLogger(__name__)


class DocParserAgent:
    """
    Agent 2 — Document Parsing.
    Calls Groq Vision on each verified document and returns structured ParsedDocument objects.

    Contract:
      Input : list[VerifiedDocument], base64 map, mime map
      Output: (list[ParsedDocument], TraceEntry)
      Errors: Per-document failures are isolated — the list always has one entry per input.
    """

    def __init__(self, groq_client: AsyncGroq) -> None:
        self._groq = groq_client

    async def run(
        self,
        verified_docs: list[VerifiedDocument],
        b64_map: dict[str, str],
        mime_map: dict[str, str],
    ) -> tuple[list[ParsedDocument], TraceEntry]:
        started = time.monotonic()
        entry = TraceEntry(
            component="DocParserAgent",
            input_summary={"doc_count": len(verified_docs)},
        )

        parsed: list[ParsedDocument] = []
        errors: list[str] = []

        for vdoc in verified_docs:
            if vdoc.quality == DocumentQuality.UNREADABLE:
                parsed.append(ParsedDocument(
                    file_id=vdoc.file_id, document_type=vdoc.classified_type,
                    quality=vdoc.quality, extraction_notes="Skipped — UNREADABLE",
                ))
                continue
            try:
                pdoc = await self._extract(
                    vdoc, b64_map.get(vdoc.file_id), mime_map.get(vdoc.file_id, "image/jpeg")
                )
                parsed.append(pdoc)
            except Exception as exc:
                errors.append(f"{vdoc.file_name}: {exc}")
                logger.warning("DocParserAgent extraction failed for %s: %s", vdoc.file_id, exc)
                parsed.append(ParsedDocument(
                    file_id=vdoc.file_id, document_type=vdoc.classified_type,
                    quality=DocumentQuality.DEGRADED,
                    extraction_notes=f"Extraction failed: {exc}",
                ))

        avg_conf = round(sum(p.overall_confidence for p in parsed) / max(len(parsed), 1), 3)
        entry.output_summary = {
            "parsed": len(parsed),
            "avg_confidence": avg_conf,
            "errors": errors,
            "extractions": [
                {
                    "file": p.file_id,
                    "patient": p.patient_name,
                    "diagnosis": p.diagnosis,
                    "doctor": p.doctor_name,
                    "hospital": p.hospital_name,
                    "total_amount": p.total_amount,
                    "field_confidences": p.field_confidences,
                    "llm_notes": p.extraction_notes,
                }
                for p in parsed
            ],
        }
        if errors:
            entry.error = "; ".join(errors)
        entry.duration_ms = int((time.monotonic() - started) * 1000)
        return parsed, entry

    async def _extract(
        self, vdoc: VerifiedDocument, b64: str | None, mime: str
    ) -> ParsedDocument:
        if not b64:
            return ParsedDocument(
                file_id=vdoc.file_id, document_type=vdoc.classified_type,
                quality=vdoc.quality, extraction_notes="No image content",
            )

        resp = await self._groq.chat.completions.create(
            model=get_settings().groq_vision_model,
            messages=[
                {"role": "system", "content": EXTRACT_SYSTEM},
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {
                            "url": f"data:{mime};base64,{b64}"
                        }},
                        {"type": "text", "text": (
                            f"Document type: {vdoc.classified_type.value.replace('_', ' ').title()}. "
                            "Extract all available information."
                        )},
                    ],
                },
            ],
            max_tokens=1000,
            temperature=0,
        )

        data = self._parse_json(resp.choices[0].message.content)

        doc_date: date | None = None
        if raw_date := data.get("document_date"):
            try:
                doc_date = date.fromisoformat(raw_date)
            except (ValueError, TypeError):
                pass

        return ParsedDocument(
            file_id=vdoc.file_id,
            document_type=vdoc.classified_type,
            quality=vdoc.quality,
            patient_name=data.get("patient_name"),
            doctor_name=data.get("doctor_name"),
            doctor_registration=data.get("doctor_registration"),
            hospital_name=data.get("hospital_name"),
            document_date=doc_date,
            diagnosis=data.get("diagnosis"),
            treatment=data.get("treatment"),
            medicines=data.get("medicines") or [],
            tests_ordered=data.get("tests_ordered") or [],
            line_items=[
                LineItem(
                    description=item.get("description", "Unknown"),
                    amount=float(item.get("amount", 0)),
                )
                for item in (data.get("line_items") or [])
            ],
            total_amount=data.get("total_amount"),
            gst_amount=float(data.get("gst_amount") or 0),
            field_confidences=data.get("field_confidences") or {},
            extraction_notes=data.get("extraction_notes") or "",
            authenticity_genuine=data.get("authenticity", {}).get("looks_genuine", True),
            authenticity_suspicion=data.get("authenticity", {}).get("suspicion_level", "none"),
            authenticity_flags=data.get("authenticity", {}).get("flags") or [],
            authenticity_notes=data.get("authenticity", {}).get("notes") or "",
        )

    @staticmethod
    def _parse_json(raw: str) -> dict:
        raw = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {"extraction_notes": f"JSON parse failed. Snippet: {raw[:100]}"}