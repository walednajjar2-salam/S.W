"""OpenAPI 3.0 spec for Launch Quality ERP (Phase 10)."""
from __future__ import annotations

from typing import Any, Dict, List


def build_openapi_spec(base_url: str, version: str) -> Dict[str, Any]:
    base = base_url.rstrip("/")
    paths: Dict[str, Any] = {}
    tag_groups: List[Dict[str, str]] = [
        {"name": "Auth", "description": "تسجيل الدخول والجلسة"},
        {"name": "Core", "description": "عقارات، عملاء، عقود، فواتير"},
        {"name": "Finance", "description": "محاسبة وبنك"},
        {"name": "Operations", "description": "صيانة، تنبيهات، اعتمادات"},
        {"name": "Intelligence", "description": "Walid والذكاء التشغيلي"},
        {"name": "Enterprise", "description": "فروع، تدقيق، نسخ احتياطي"},
    ]

    def post(path: str, summary: str, tag: str, body_example: dict | None = None):
        paths[path] = {
            "post": {
                "tags": [tag],
                "summary": summary,
                "security": [{"bearerAuth": []}],
                "requestBody": {
                    "content": {"application/json": {"schema": {"type": "object"}, "example": body_example or {}}}
                },
                "responses": {"200": {"description": "OK"}},
            }
        }

    def get(path: str, summary: str, tag: str):
        paths[path] = {
            "get": {
                "tags": [tag],
                "summary": summary,
                "security": [{"bearerAuth": []}],
                "responses": {"200": {"description": "OK"}},
            }
        }

    post("/api/login", "تسجيل الدخول", "Auth", {"username": "admin", "password": "***"})
    get("/api/me", "المستخدم الحالي", "Auth")
    get("/api/bootstrap", "تحميل البيانات الكاملة", "Core")
    get("/api/dashboard", "لوحة التحكم", "Core")
    get("/api/properties", "قائمة العقارات", "Core")
    post("/api/clients", "إضافة عميل", "Core", {"name": "Client name"})
    post("/api/contracts", "إنشاء عقد", "Core", {"property_id": "P-1", "client_id": "C-1", "rent_amount": 500})
    post("/api/invoice_from_contract", "فاتورة من عقد", "Core", {"contract_id": "CT-1"})
    post("/api/pay_invoice", "تحصيل فاتورة", "Core", {"invoice_id": "INV-1", "amount": 100})
    get("/api/financial_statements", "القوائم المالية", "Finance")
    get("/api/bank_reconciliation_preview", "معاينة تسوية البنك", "Finance")
    get("/api/alert_center", "مركز التنبيهات", "Operations")
    get("/api/operational_intel", "ذكاء Walid", "Intelligence")
    post("/api/ai/ask", "سؤال Walid", "Intelligence", {"question": "من لم يدفع؟"})
    get("/api/branches", "الفروع", "Enterprise")
    get("/api/audit_feed", "سجل التدقيق", "Enterprise")
    get("/api/backup/status", "حالة النسخ الاحتياطي", "Enterprise")
    get("/api/health", "صحة النظام", "Enterprise")

    return {
        "openapi": "3.0.3",
        "info": {
            "title": "Launch Quality ERP API",
            "version": version,
            "description": "REST API · Launch Quality LLC · Real Estate & Hospitality ERP",
        },
        "servers": [{"url": base}],
        "tags": tag_groups,
        "components": {
            "securitySchemes": {
                "bearerAuth": {
                    "type": "http",
                    "scheme": "bearer",
                    "description": "Bearer token from POST /api/login",
                }
            }
        },
        "paths": paths,
    }
