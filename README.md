# HR Resume Shortlisting Agent - Streamlit Edition

AI-powered candidate evaluation dashboard.
LLM: Google Gemini 1.5 Flash | UI: Streamlit | DB: SQLite | Tunnel: localtunnel (no account needed)

## File Structure

```
hr_agent/
├── streamlit_app.py        <- Main Streamlit dashboard
├── config.py               
├── database.py             <- SQLAlchemy ORM - 4 tables
├── schemas.py              <- Pydantic v2 validation schemas
├── file_parser.py          <- PDF/DOCX extraction + PII masking
├── llm_service.py          <- Gemini API calls + structured prompts
├── evaluation_service.py   <- Orchestration pipeline
├── requirements.txt
└── HR_Agent_Streamlit_Colab.ipynb
```


### Step 1 - Run notebook cells in order

Cell 1  -> Install packages + localtunnel
Cell 2  -> Verify GEMINI_API_KEY secret
Cell 3  -> Upload hr_streamlit.zip
Cell 3b -> Verify files
Cell 4  -> Launch app, prints URL + password
Cell 5  -> Stop server
Cell 6  -> View logs
Cell 7  -> Download database

### Step 2 - Open the app

Cell 4 prints something like:
  URL      : https://xxxx.loca.lt
  Password : 34.xxx.xxx.xxx

1. Open the URL
2. Click "Click to Continue" on the yellow localtunnel screen
3. Enter the Password shown above
4. App loads

## Quickstart - Local

```bash
pip install -r requirements.txt
cp .env.example .env
# Edit .env and set GEMINI_API_KEY=your_key
streamlit run streamlit_app.py
```

## Secret Variable Name

| Name            | Where to get                                |
|-----------------|---------------------------------------------|
| GEMINI_API_KEY  | https://aistudio.google.com/app/apikey (free)|

Key resolution order in config.py:
1. Colab Secrets  (userdata.get)
2. os.environ     (subprocess injection in Cell 4)
3. .env file      (local use)

## Scoring Rubric

| Dimension                | Weight |
|--------------------------|--------|
| Skills Match             | 30%    |
| Experience Relevance     | 25%    |
| Project / Portfolio      | 20%    |
| Education & Certs        | 15%    |
| Communication Quality    | 10%    |

Weighted total out of 100:
- >= 75  -> Strong Hire
- 50-74  -> Consider
- < 50   -> Do Not Hire

## Security Controls

| Threat                  | Control                                                    |
|-------------------------|------------------------------------------------------------|
| Prompt injection        | Resume text wrapped as PASSIVE DATA in every LLM call      |
| API key exposure        | Loaded from Secrets/env only, never written to disk        |
| PII in database         | Email + phone masked before any DB write                   |
| Malicious uploads       | Extension whitelist (PDF/DOCX), size limit enforced        |
| LLM bad output          | Pydantic validation, retry once, conservative fallback     |
| Demographic bias        | System prompt ignores name, gender, age, location, uni     |
| Override abuse          | Reason required, every override timestamped in DB          |

## Database Tables

| Table             | Stores                                                  |
|-------------------|---------------------------------------------------------|
| job_descriptions  | Title, raw text, parsed structured fields               |
| candidates        | Name, filename, parsed resume JSON                      |
| evaluations       | Scores, justifications, weighted total, raw LLM response|
| overrides         | HR override history with reason and timestamp           |

## .env example (local use only)

GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-1.5-flash
DATABASE_URL=sqlite:///./hr_agent.db
MAX_FILE_SIZE_MB=10
DEBUG=false
