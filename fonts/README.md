Place Unicode TTF fonts here for guaranteed Cyrillic PDF rendering.

Supported filenames (priority order):
1. DejaVuSans.ttf
2. NotoSans-Regular.ttf

If these files are missing, the system falls back to Windows fonts:
- C:/Windows/Fonts/DejaVuSans.ttf
- C:/Windows/Fonts/arial.ttf
- C:/Windows/Fonts/calibri.ttf

Tip:
- For consistent production output across servers, provide DejaVuSans.ttf in this folder.
- Ensure your deployment image includes Playwright Chromium if REPORT_PDF_ENGINE=playwright.
