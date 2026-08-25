import os

from dotenv import load_dotenv


load_dotenv()


class Settings:
    def __init__(self) -> None:
        self.bot_token = os.getenv("BOT_TOKEN", "")
        self.openai_api_key = os.getenv("OPENAI_API_KEY", "")
        self.openai_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.openai_transcribe_model = os.getenv("OPENAI_TRANSCRIBE_MODEL", "whisper-1")
        self.career_assessment_timeout_seconds = max(
            5.0,
            float(os.getenv("CAREER_ASSESSMENT_TIMEOUT_SECONDS", "40")),
        )
        self.report_output_dir = os.getenv("REPORT_OUTPUT_DIR", "reports")
        public_domain = os.getenv("RAILWAY_PUBLIC_DOMAIN", "").strip()
        default_report_url = f"https://{public_domain}/reports" if public_domain else "http://localhost:8000/reports"
        self.report_base_url = os.getenv("REPORT_BASE_URL", default_report_url).strip()
        self.report_pdf_engine = os.getenv("REPORT_PDF_ENGINE", "auto")
        self.report_pdf_font_path = os.getenv("REPORT_PDF_FONT_PATH", "").strip()
        self.google_sheets_webhook_url = os.getenv("GOOGLE_SHEETS_WEBHOOK_URL", "").strip()
        self.analytics_registry_path = os.getenv("ANALYTICS_REGISTRY_PATH", "reports/user_registry.json").strip()
        self.analytics_events_log_path = os.getenv("ANALYTICS_EVENTS_LOG_PATH", "reports/behavior_events.jsonl").strip()
        self.analytics_excel_log_path = os.getenv("ANALYTICS_EXCEL_LOG_PATH", "reports/analytics_events.csv").strip()
        self.specialist_telegram_url = os.getenv("SPECIALIST_TELEGRAM_URL", "").strip()
        self.specialist_notify_chat_id = os.getenv("SPECIALIST_NOTIFY_CHAT_ID", "").strip()
        self.support_group_telegram_url = os.getenv("SUPPORT_GROUP_TELEGRAM_URL", "").strip()
        self.hybrid_support_url = os.getenv("HYBRID_SUPPORT_URL", "").strip()
        self.app_db_path = os.getenv("APP_DB_PATH", "reports/app_data.sqlite3").strip()
        self.environment = os.getenv("ENVIRONMENT", "development").strip().lower()
        self.report_api_enabled = os.getenv("ENABLE_REPORT_API", "").strip().lower() in {"1", "true", "yes"}
        self.legacy_career_report_enabled = os.getenv("LEGACY_CAREER_REPORT_ENABLED", "false").strip().lower() in {
            "1",
            "true",
            "yes",
        }

    def validate(self) -> None:
        missing = []
        if not self.bot_token:
            missing.append("BOT_TOKEN")
        if not self.openai_api_key:
            missing.append("OPENAI_API_KEY")
        if missing:
            joined = ", ".join(missing)
            raise ValueError(f"Missing required environment variables: {joined}")


settings = Settings()
