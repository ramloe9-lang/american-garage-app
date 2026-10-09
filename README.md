# Dynamic Menu & Margin Guard — Backend

## Puesta en marcha
1. Crea una Service Account en Google Cloud, habilita *Google Sheets API* y comparte la hoja (solo lectura) con el correo de la cuenta.
2. `cp .env.example .env` y completa los valores.
3. `pip install -r requirements.txt && uvicorn app.main:app --reload`
4. Docs interactivas: http://localhost:8000/docs

## Docker
`docker build -t margin-guard . && docker run --env-file .env -v $PWD/secrets:/secrets:ro -p 8000:8000 margin-guard`

## Endpoints
- `GET /api/v1/menu[?categoria=...]` — menú ordenado por `prioridad_score`.
- `GET /api/v1/dashboard` — KPIs (header `X-API-Key` si se configuró `DASHBOARD_API_KEY`).
- `GET /health`
