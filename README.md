# Armoede Community SOP Survey

A Streamlit stakeholder engagement app for Armoede / Ga-Sekhaolelo. The 12 questions and optional prompts are taken from the Armoede Focus Group Engagement Guide prepared on 13 October 2026. The map uses the supplied Ga-Sekhaolelo KMZ polygon, converted to GeoJSON without changing its vertices.

## What participants can do

- Answer individually or as a facilitated focus group.
- Work through one question at a time, with text boxes for their answer and suggested changes.
- Tap a map inside the Armoede boundary, describe the selected place, and attach it to the current answer.
- Add up to 20 different locations per question, remove pins, or answer without a location.
- Enter decimal coordinates if map tiles do not load.
- Rate the four SOPs, identify three priority changes and capture a differing view.
- Download a draft, restore it later, and export their answers as CSV or locations as GeoJSON.
- Submit once a storage backend is configured. Repeated submissions of the same response ID do not create duplicates or overwrite the first submission.

The facilitator dashboard is password protected, shows submitted responses only, and offers question maps, role/session filters, SOP fit ratings, CSV exports and full JSON backups. It is locked when no administrator password is configured.

## Smartphones

On narrow screens, the answer boxes appear above the map. All navigation buttons are large, and there is one question per screen. Tap the map, then use **Attach selected place to this answer**; tapping alone does not save a pin. Scroll below the map to see attached places and navigation. Download a draft before closing or refreshing the page. To continue later, use **Continue from a saved draft** on the welcome screen and select the downloaded JSON file.

This is an online web app, not an offline installable app. Background map tiles require internet access. Session memory is not a durable draft backup. Test the published deployment on the phones and networks participants will use before the engagement. Do not use browser refresh as navigation.

## Run on a laptop

Use Python 3.12 (tested) and open a terminal in this folder.

```bash
python -m venv .venv
```

On Windows:

```powershell
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .streamlit\secrets.example.toml .streamlit\secrets.toml
```

On macOS or Linux:

```bash
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .streamlit/secrets.example.toml .streamlit/secrets.toml
```

For a local workshop, edit `.streamlit/secrets.toml` to set:

```toml
REQUIRE_DURABLE_STORAGE = false
ADMIN_PASSWORD = "your own strong facilitator password"
```

Then run:

```bash
python -m streamlit run app.py
```

Local submissions are saved under `responses/armoede.sqlite3`. Back up this folder and dashboard exports. Files are ignored by Git to avoid accidentally publishing responses. Smartphone users can join the laptop's app only if they share a suitable network and the laptop's firewall and network allow connections. On a shared network, consider a survey access password and use an appropriately secured hosting setup for personal or sensitive information.

## Deploy on Streamlit Community Cloud

1. Create a GitHub repository for this app.
2. Upload all project files, preserving the `data` and `.streamlit` directories. Do not upload a real `secrets.toml` or the `responses` directory.
3. In Streamlit Community Cloud, create an app using that repository, branch and `app.py` as the main file. Choose Python 3.12.
4. Configure Secrets with a strong `ADMIN_PASSWORD` (or `ADMIN_PASSWORD_SHA256`), and an external PostgreSQL `DATABASE_URL`. Leave `REQUIRE_DURABLE_STORAGE = true`.
5. Optionally configure a separate `SURVEY_PASSWORD` (or its hash) and share it through the organiser's chosen channel.
6. Deploy and open the generated Streamlit URL on a desktop and smartphone. Submit a test response, restart the app, and verify the response remains available in the facilitator dashboard. Remove test records using your database administration process if needed.

**Without a configured external database, the default app allows draft completion and downloads but disables server submission.** This prevents a cloud deployment from silently collecting survey records on ephemeral local storage. SQLite is for local workshops or hosting with an explicitly persistent disk; do not enable it on Community Cloud for real collection.

The database account needs access to a dedicated database/schema and permission to create and insert/select from `armoede_survey_responses`. This is the only table used by this app. The app does not publish database credentials to participant browsers. Restrict the database account to the required permissions, retain backups, and use TLS as required by your database provider. Set the connection string only in Secrets or an environment variable. Do not paste credentials into chat or commit them to GitHub.

The PostgreSQL path is implemented but was not integration-tested against a live server because no database connection was supplied. Complete the live submission-and-restart check before using it for engagement.

## Access and privacy

No participant names, identity numbers, email addresses or medical details are requested. Text can nevertheless include personal information; the survey asks people to avoid entering it, and exact pins remain linked to answers in restricted dashboard exports. The organiser should explain who can see submissions, where they are stored and how long they will be retained before collection. Consent records do not replace the organiser's privacy notice.

The optional survey password limits entry; the facilitator password protects submitted responses within the app. There is no participant account management, per-person identity verification or Internet-wide abuse prevention. The basic session-level login throttle is not a replacement for a managed authentication service. Use Streamlit app sharing restrictions or managed hosting controls if access requirements are stronger.

All mapped locations are participant proposals, not verified safe assembly points, hazards or statutory boundary determinations. The KMZ has no mapped roads, hotspots or shelter locations; these are added through stakeholder input. The map validates against the supplied polygon only. Road One and New Stands are mentioned in the questions and storm scenario but are not pre-positioned, because their coordinates were not supplied.

## Project files

- `app.py`: participant flow, map interactions and protected dashboard.
- `survey_core.py`: schema, boundary checks, draft validation and exports.
- `map_view.py`: Armoede boundary and participant markers.
- `storage.py`: parameterised SQLite/PostgreSQL storage.
- `data/questions.json`: the 12 questions, probes and SOP references.
- `data/armoede_boundary.geojson`: supplied community polygon.
- `.streamlit/config.toml`: colours, readable text and upload limit.
- `.streamlit/secrets.example.toml`: configuration example containing no active credentials.
- `tests/test_survey.py`: map, navigation, storage, consent and export checks.

The field names and SOP references make CSV outputs usable as evidence for the SOP comment and response matrix. They do not automatically disposition comments or approve revisions.

## Tests and verification

```bash
python -m pip install pytest
python -m pytest tests -q
```

Verification covers boundary acceptance/rejection, pin deduplication and question association, draft restore, longitude/latitude order in GeoJSON, consent and minimum-input validation, safe spreadsheet exports, database deduplication, navigation retaining answers, attaching a selected location, submission, dashboard lock and cloud submission gating. Streamlit AppTest supplies simulated map component returns; actual touch interaction and map tile delivery still require browser/device checking after deployment.

Reference documentation:

- https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app
- https://docs.streamlit.io/develop/api-reference/caching-and-state/st.session_state
- https://docs.streamlit.io/develop/concepts/app-testing
- https://github.com/randyzwitch/streamlit-folium

The reference KZN survey was visible at its password screen, with Survey and Admin Dashboard navigation. Its protected questionnaire was not inspected, and no source code was copied.
