# Backend Development

This backend uses Python and FastAPI.

## Setup

1. Open a terminal in `c:\AI trining\backend`
2. Create a virtual environment:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\activate
   ```
3. Install dependencies:
   ```powershell
   pip install -r requirements.txt
   ```
4. Copy the environment template:
   ```powershell
   copy .env.example .env
   ```
5. Fill in the values in `.env`.
   - Set `GEMINI_API_KEY` to your Gemini API key or `LITELLM_API_KEY` to use the LiteLLM proxy.

## Run

1. Activate the virtual environment:
   ```powershell
   .\.venv\Scripts\activate
   ```
2. Start the app:
   ```powershell
   .\start.ps1
   ```

## Notes

- This project loads `backend/.env` using `backend/app/config.py`.
- Do not store API keys or secrets directly in source files.
