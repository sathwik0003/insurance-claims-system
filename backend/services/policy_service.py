from __future__ import annotations

import json
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path

from models.claim import ClaimCategory
from models.document import DocumentType


class PolicyService:
    def __init__(self, policy_path: Path) -> None:
        with open(policy_path) as f:
            self._data: dict = json.load(f)
        self._members: dict[str, dict] = {
            m["member_id"]: m for m in self._data["members"]
        }

    # ── Member ────────────────────────────────────────────────────────────────

    def get_member(self, member_id: str) -> dict | None:
        return self._members.get(member_id)

    def member_exists(self, member_id: str) -> bool:
        return member_id in self._members

    def get_join_date(self, member_id: str) -> date | None:
        m = self.get_member(member_id)
        return date.fromisoformat(m["join_date"]) if m else None

    def all_members(self) -> list[dict]:
        return list(self._members.values())

    # ── Waiting periods ───────────────────────────────────────────────────────

    def initial_waiting_period_days(self) -> int:
        return self._data["waiting_periods"]["initial_waiting_period_days"]

    def condition_waiting_period_days(self, diagnosis: str) -> int | None:
        diag = diagnosis.lower()
        wp = self._data["waiting_periods"]["specific_conditions"]
        keyword_map: dict[str, list[str]] = {
            "diabetes":          ["diabetes", "t2dm", "type 2 diabetes", "dm"],
            "hypertension":      ["hypertension", "htn", "high blood pressure"],
            "thyroid_disorders": ["thyroid", "hypothyroidism", "hyperthyroidism"],
            "joint_replacement": ["joint replacement", "knee replacement", "hip replacement"],
            "maternity":         ["maternity", "pregnancy", "antenatal"],
            "mental_health":     ["depression", "anxiety", "mental health", "psychiatric"],
            "obesity_treatment": ["obesity", "morbid obesity", "bariatric", "weight loss"],
            "hernia":            ["hernia"],
            "cataract":          ["cataract"],
        }
        for key, keywords in keyword_map.items():
            if any(kw in diag for kw in keywords):
                return wp.get(key)
        return None

    def is_within_waiting_period(
        self,
        member_id: str,
        treatment_date: date,
        diagnosis: str | None = None,
    ) -> tuple[bool, str]:
        """Returns (is_blocked, reason_message)."""
        join_date = self.get_join_date(member_id)
        if not join_date:
            return False, ""

        initial_days = self.initial_waiting_period_days()
        eligible_from = join_date + timedelta(days=initial_days)
        if treatment_date < eligible_from:
            return True, (
                f"Treatment date {treatment_date} is within the {initial_days}-day "
                f"initial waiting period. Eligible from {eligible_from}."
            )

        if diagnosis:
            cond_days = self.condition_waiting_period_days(diagnosis)
            if cond_days:
                cond_eligible = join_date + timedelta(days=cond_days)
                if treatment_date < cond_eligible:
                    return True, (
                        f"Diagnosis '{diagnosis}' has a {cond_days}-day waiting period. "
                        f"Eligible from {cond_eligible}."
                    )
        return False, ""

    # ── Coverage & limits ─────────────────────────────────────────────────────

    def _category_cfg(self, category: ClaimCategory) -> dict | None:
        key = (
            "alternative_medicine"
            if category == ClaimCategory.ALTERNATIVE_MEDICINE
            else category.value.lower()
        )
        return self._data["opd_categories"].get(key)

    def get_sub_limit(self, category: ClaimCategory) -> float:
        cfg = self._category_cfg(category)
        return float(cfg["sub_limit"]) if cfg else 0.0

    def get_copay_percent(self, category: ClaimCategory) -> float:
        cfg = self._category_cfg(category)
        return float(cfg.get("copay_percent", 0)) if cfg else 0.0

    def get_network_discount_percent(self, category: ClaimCategory) -> float:
        cfg = self._category_cfg(category)
        return float(cfg.get("network_discount_percent", 0)) if cfg else 0.0

    def per_claim_limit(self) -> float:
        return float(self._data["coverage"]["per_claim_limit"])

    def annual_opd_limit(self) -> float:
        return float(self._data["coverage"]["annual_opd_limit"])

    # ── Exclusions ────────────────────────────────────────────────────────────

    def is_excluded_condition(self, diagnosis: str) -> tuple[bool, str]:
        d = diagnosis.lower()
        for exc in self._data["exclusions"]["conditions"]:
            # Only match on words >= 6 chars to avoid false matches on
            # short words like "or", "and", "war" appearing in unrelated diagnoses
            key_words = [
                w.strip(".,()-/")
                for w in exc.lower().split()
                if len(w.strip(".,()-/")) >= 6
            ]
            if key_words and any(w in d for w in key_words):
                return True, exc
        return False, ""

    def is_excluded_dental_procedure(self, description: str) -> tuple[bool, str]:
        desc = description.lower()
        cfg = self._data["opd_categories"]["dental"]
        for exc in cfg.get("excluded_procedures", []):
            # Match primary phrase (before parenthesis) as a whole substring
            primary = exc.split("(")[0].strip().lower()
            if primary in desc:
                return True, exc
        return False, ""

    def is_excluded_vision_item(self, description: str) -> tuple[bool, str]:
        desc = description.lower()
        for exc in self._data["exclusions"].get("vision_exclusions", []):
            primary = exc.split("(")[0].strip().lower()
            if primary in desc:
                return True, exc
        return False, ""

    # ── Pre-authorization ─────────────────────────────────────────────────────

    def requires_pre_auth(
        self,
        category: ClaimCategory,
        tests: list[str],
        amount: float,
    ) -> tuple[bool, str]:
        if category != ClaimCategory.DIAGNOSTIC:
            return False, ""
        cfg = self._category_cfg(category)
        if not cfg:
            return False, ""
        threshold = cfg.get("pre_auth_threshold", float("inf"))
        high_value: list[str] = cfg.get("high_value_tests_requiring_pre_auth", [])
        for test in tests:
            for hv in high_value:
                if hv.lower() in test.lower() and amount > threshold:
                    return True, (
                        f"{hv} above ₹{threshold:,.0f} requires pre-authorization. "
                        "Obtain pre-auth from your insurer before the procedure."
                    )
        return False, ""

    # ── Network hospitals ─────────────────────────────────────────────────────

    def is_network_hospital(self, hospital_name: str | None) -> bool:
        if not hospital_name:
            return False
        h = hospital_name.lower()
        return any(
            net.lower() in h or h in net.lower()
            for net in self._data["network_hospitals"]
        )

    # ── Document requirements ─────────────────────────────────────────────────

    def required_document_types(self, category: ClaimCategory) -> list[DocumentType]:
        reqs = self._data["document_requirements"].get(category.value, {})
        return [DocumentType(t) for t in reqs.get("required", [])]

    def optional_document_types(self, category: ClaimCategory) -> list[DocumentType]:
        reqs = self._data["document_requirements"].get(category.value, {})
        return [DocumentType(t) for t in reqs.get("optional", [])]

    # ── Submission rules ──────────────────────────────────────────────────────

    def submission_deadline_days(self) -> int:
        return self._data["submission_rules"]["deadline_days_from_treatment"]

    def minimum_claim_amount(self) -> float:
        return float(self._data["submission_rules"]["minimum_claim_amount"])

    # ── Fraud thresholds ──────────────────────────────────────────────────────

    def fraud_thresholds(self) -> dict:
        return self._data["fraud_thresholds"]


@lru_cache(maxsize=1)
def get_policy_service() -> PolicyService:
    from config import get_settings
    return PolicyService(get_settings().policy_data_path)