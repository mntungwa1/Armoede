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
- Submit once a database or Gmail delivery is configured. Repeated submissions of the same response ID do not create duplicates or overwrite the first submission.

The facilitator dashboard is password protected, shows submitted responses only, and offers question maps, role/session filters, SOP fit ratings, CSV exports and full JSON backups. It is locked when no administrator password is configured.

## Smartphones

On narrow screens, the answer boxes appear above the map. All navigation buttons are large, and there is one question per screen. Tap the map, then use **Attach selected place to this answer**; tapping alone does not save a pin. Scroll below the map to see attached places and navigation. Before closing or refreshing, select **Prepare draft download**, then **Download my draft**. Preparation captures the latest input before generating the file. To continue later, use **Continue from a saved draft** on the welcome screen, select the downloaded JSON file and click **Restore draft**. The app shows how many questions and locations were restored and opens the saved question. Older drafts without saved navigation metadata open the first question containing input. Empty or invalid drafts are explicitly reported.

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
4. Configure Secrets with a strong `ADMIN_PASSWORD` (or `ADMIN_PASSWORD_SHA256`), plus `EMAIL_ADDRESS` and `EMAIL_PASSWORD` for Gmail notifications. For a persistent dashboard, also configure an external PostgreSQL `DATABASE_URL`. Leave `REQUIRE_DURABLE_STORAGE = true`.
5. Optionally configure a separate `SURVEY_PASSWORD` (or its hash) and share it through the organiser's chosen channel.
6. Deploy and open the generated Streamlit URL on a desktop and smartphone. Submit a test response, restart the app, and verify the response remains available in the facilitator dashboard. Remove test records using your database administration process if needed.

**Without either an external database or Gmail credentials, the default app allows draft completion and downloads but disables submission.** Gmail credentials allow email collection without PostgreSQL. In that mode, emails are the retained record and dashboard copies use temporary local storage: they may disappear after a Cloud restart or redeployment. Configure PostgreSQL to retain the dashboard as well as the emailed answers. SQLite alone is for laptop workshops or hosting with an explicitly persistent disk.

The database account needs access to a dedicated database/schema and permission to create and insert/select from `armoede_survey_responses`. Email tracking also uses `armoede_email_notifications`; the database account needs create, insert, select and update permissions for this table. The app does not publish database credentials to participant browsers. Restrict the database account to the required permissions, retain backups, and use TLS as required by your database provider. Set the connection string only in Secrets or an environment variable. Do not paste credentials into chat or commit them to GitHub.

The PostgreSQL path is implemented but was not integration-tested against a live server because no database connection was supplied. Complete the live submission-and-restart check before using it for engagement.

## Access and privacy

No participant names, identity numbers, email addresses or medical details are requested. Text can nevertheless include personal information; the survey asks people to avoid entering it, and exact pins remain linked to answers in restricted dashboard exports. The organiser should explain who can see submissions, where they are stored and how long they will be retained before collection. Consent records do not replace the organiser's privacy notice.

The optional survey password limits entry; the facilitator password protects submitted responses within the app. There is no participant account management, per-person identity verification or Internet-wide abuse prevention. The basic session-level login throttle is not a replacement for a managed authentication service. Use Streamlit app sharing restrictions or managed hosting controls if access requirements are stronger.

All mapped locations are participant proposals, not verified safe assembly points, hazards or statutory boundary determinations. The KMZ has no mapped roads, hotspots or shelter locations; these are added through stakeholder input. The map validates against the supplied polygon only. Road One and New Stands are mentioned in the questions and storm scenario but are not pre-positioned, because their coordinates were not supplied.

## Project files

- `app.py`: participant flow, map interactions and protected dashboard.
- `survey_core.py`: schema, boundary checks, draft validation and exports.
- `map_view.py`: Armoede boundary and participant markers.
- `storage.py`: parameterised SQLite/PostgreSQL response storage and email delivery status.
- `notifications.py`: Gmail sending with full answers, locations, CSV and GeoJSON attachments.
- `data/questions.json`: the 12 questions, probes and SOP references.
- `data/armoede_boundary.geojson`: supplied community polygon.
- `.streamlit/config.toml`: colours, readable text and upload limit.
- `.streamlit/secrets.example.toml`: configuration example containing no active credentials.
- `tests/test_survey.py`: map, navigation, storage, consent and export checks.
- `tests/test_restore.py`: restore flow, draft confirmation, stale widget replacement and download preparation.

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

## Gmail notifications and facilitator dashboard

Add the following to Streamlit Secrets, using your own passwords privately:

```toml
SURVEY_PASSWORD = "your participant password"
ADMIN_PASSWORD = "your facilitator password"
EMAIL_ADDRESS = "dingaanm@gmail.com"
EMAIL_PASSWORD = "your Google App Password"
REQUIRE_DURABLE_STORAGE = true
```

Keep an existing DATABASE_URL if configured. The Google App Password is separate from the survey and facilitator passwords and your normal Google password. It needs 2-Step Verification on the sending Google account. Spaces in Google's displayed app password are removed before SMTP authentication. No credentials are included in this repository.

Each submitted response is emailed to **dingaanm@gmail.com** with all 12 question headings and answers, suggested changes, location coordinates and map links, SOP ratings, priorities and closing comments. CSV and GeoJSON exports are attached. The facilitator dashboard remains available, with email statuses and a button to send pending or failed notifications. Responses submitted before Gmail was configured can be sent from that button if they still exist in the database.

Repeated submit clicks do not normally resend a sent notification. Delivery is marked sent when Gmail accepts the message, which does not prove inbox delivery. If a send times out after transmission may have begun, its status is uncertain and automatic retries stop. The organiser checks Gmail before using the explicit manual retry, which can create a duplicate. If Gmail fails before sending, answers remain available locally or in PostgreSQL and a safe retry is offered.

When Gmail is the only configured destination, download a backup if sending fails: temporary Cloud records are not a durable outbox. Configure PostgreSQL for durable pending messages and dashboard records. The app does not run a background retry worker; the facilitator retries pending notifications while the dashboard is open. Gmail SMTP access must be allowed by the hosting environment.

After saving Secrets and deploying the update, submit a short test answer through the survey, check Inbox and Spam, and verify the response and email status in the facilitator dashboard. Real Gmail sending has not been tested by the developer because credentials stay private in the deployed app; automated tests simulate SMTP success, authentication failures, ambiguous delivery, duplicate clicks and email-only submission.

Google guidance: https://support.google.com/mail/answer/185833

## Questionnaire entries

The first tab is **Questionnaire entries**, with radio choices for **Traditional Council** and **Wardens and General Stakeholders**. Questions and prompts come from the supplied ACDT discussion guides: each has 21 main questions, six hazard scenarios, three closing questions and an optional facilitator action table. General stakeholders use the Wardens guide from their own role and experience; the original wording is retained.

The two choices keep separate drafts during a session. Download a questionnaire draft before closing or refreshing and restore it in the first tab to continue. The original map-based stakeholder survey remains on the second tab. Document previews and Word downloads follow it.

Questionnaire submissions use the same storage, consent, password gate and Gmail notification settings as the map survey. The facilitator dashboard's **Questionnaire to review** selector separates map survey responses, Traditional Council entries and Wardens/general stakeholder entries; CSV and JSON exports include all questionnaire answers and action records. Hosted local storage may be temporary unless DATABASE_URL is configured. No participant answers or credentials are stored in the repository.
