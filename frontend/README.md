# Frontend Development

This frontend uses React, TypeScript, Vite, and Tailwind CSS.

## Setup

1. Open a terminal in `c:\AI trining\frontend`
2. Install dependencies:
   ```powershell
   npm install
   ```

## Run

1. Start the frontend:
   ```powershell
   .\start.ps1
   ```

2. Open the URL printed by Vite (usually `http://localhost:5173`).

## Notes

- The Vite config proxies `/api` requests to `http://localhost:8000`.
- No frontend secrets are stored in code.
- If `npm install` fails, make sure Node.js 18+ is installed and available on PATH.
