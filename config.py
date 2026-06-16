import os

from dotenv import load_dotenv


load_dotenv()


class Settings:
    def __init__(self) -> None:
        self.bot_token = os.getenv("BOT_TOKEN", "")
        self.openai_api_key = os.getenv("OPENAI_API_KEY", "")
        self.openai_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.openai_transcribe_model = os.getenv("OPENAI_TRANSCRIBE_MODEL", "whisper-1")
        self.report_output_dir = os.getenv("REPORT_OUTPUT_DIR", "reports")
        self.report_base_url = os.getenv("REPORT_BASE_URL", "http://localhost:8000/reports")
        self.report_pdf_engine = os.getenv("REPORT_PDF_ENGINE", "auto")
        self.report_pdf_font_path = os.getenv("REPORT_PDF_FONT_PATH", "").strip()

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
