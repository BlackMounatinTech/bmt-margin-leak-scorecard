# Margin Leak Scorecard

Free lead-magnet web app for Black Mountain Technologies. Canadian GCs answer 10 questions in 60 seconds and get a personalized margin-leak breakdown powered by Claude Opus 4.7.

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env          # then edit .env and set ANTHROPIC_API_KEY
streamlit run app.py
```

Open http://localhost:8501.

## Deploy to Render

First time:

1. Push this repo to GitHub:
   ```bash
   gh repo create bmt-margin-leak-scorecard --private --source=. --remote=origin --push
   ```
   Or manually: create a new empty repo on github.com, then:
   ```bash
   git remote add origin git@github.com:<your-user>/bmt-margin-leak-scorecard.git
   git branch -M main
   git push -u origin main
   ```

2. In Render dashboard: **New → Web Service → Connect the GitHub repo**. Render will auto-detect `render.yaml` and pick up settings.

3. Before first deploy finishes, open the service's **Environment** tab and set:
   - `ANTHROPIC_API_KEY` = your Anthropic key
   (`ANTHROPIC_MODEL` and `PYTHON_VERSION` are set in `render.yaml` already.)

4. Render builds + deploys. You get a URL like `https://bmt-margin-leak-scorecard.onrender.com`.

Every `git push` to `main` auto-redeploys.

## Files

```
app.py            # Streamlit UI + form + capture + render
scoring.py        # Scoring algorithm + Claude prompt + API call
pdf_generator.py  # fpdf2 PDF (unused; retained for future)
styles/
  theme.css       # BMT v3.0 base theme
  scorecard.css   # Scorecard-specific components
.env.example      # Required env vars template (never commit real .env)
render.yaml       # Render service config
.tmp/
  scorecard_leads.csv  # Lead capture, auto-created on first submit
```

## Lead captures

Every submission appends a row to `.tmp/scorecard_leads.csv` with:

```
timestamp, company_name, email, score, tier, revenue_tier,
active_projects, biggest_pain, all_answers_json
```

On Render the CSV lives inside the running container. For persistence between deploys, add a Render disk mount to `.tmp/` or swap write_lead_row to hit Google Sheets / Airtable / a database.

## Shared design docs

`VOICE_GUIDE.md` and `DESIGN_SYSTEM.md` are NOT in this repo on purpose. They live at `/Users/michaelmackrell/BMT_Shared/` as the single source of truth for all BMT products. Locally they appear as symlinks so agents can reference them. They're gitignored because they're not needed at runtime and duplicating them across repos causes drift.
