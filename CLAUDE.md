# Alpha Lens — Notes for Claude

## Git push target

Always push to the `harthik` remote (`github.com/harthik200620/Alpha_Lens.git`), NOT `origin` (KIRITO-899). The `main` branch is already configured to track `harthik/main`, so a plain `git push` will go to the right place — do not pass `origin` explicitly.

## Running the app locally

- Backend (Flask): `C:/Project rohan/Alpha_Lens/.alpha-venv/Scripts/python.exe backend/app.py` — serves on port 5000
- Flask is configured with `static_folder='../frontend', static_url_path='/'`, so `/stocks.js`, `/index.html` etc. resolve to files in `frontend/`
- Frontend is a single `frontend/index.html` (no build step) plus `frontend/stocks.js` (NSE/BSE ticker list, ~2150 entries)
