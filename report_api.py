from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from config import settings
from utils.reporting import generate_report_payload


class ReportGenerateRequest(BaseModel):
    user_id: str
    digital_human: dict
    career_decision: dict
    market_analysis: list | dict
    action_plan: dict


class ReportGenerateResponse(BaseModel):
    telegram_summary: str
    pdf_url: str


app = FastAPI(title="Career GPS Report API")

reports_dir = Path(settings.report_output_dir)
reports_dir.mkdir(parents=True, exist_ok=True)
app.mount("/reports", StaticFiles(directory=str(reports_dir)), name="reports")


@app.post("/report/generate", response_model=ReportGenerateResponse)
async def report_generate(payload: ReportGenerateRequest) -> ReportGenerateResponse:
    report = {
        "digital_human": payload.digital_human,
        "career_decision": payload.career_decision,
        "market_analysis": payload.market_analysis if isinstance(payload.market_analysis, list) else [],
        "action_plan": payload.action_plan,
        "weekly_plan": [],
        "development_map": {},
    }
    generated = generate_report_payload(
        user_id=payload.user_id,
        report=report,
        base_url=settings.report_base_url,
        output_dir=settings.report_output_dir,
    )
    return ReportGenerateResponse(**generated)
