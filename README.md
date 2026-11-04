# Imtihan Tayyari 📚
Upload a textbook chapter → get practice questions → get answers checked → explanations in English, Urdu or Roman Urdu.

## Run locally
```
pip install -r requirements.txt
mkdir -p .streamlit && cp .streamlit/secrets.toml.example .streamlit/secrets.toml   # then add your real key
streamlit run app.py
```

## Deploy (GitHub + Streamlit Community Cloud)
1. Push these files to a GitHub repo (`.gitignore` keeps your key out).
2. Go to share.streamlit.io → New app → pick the repo, main file `app.py`.
3. Advanced settings → Secrets → paste: `ANTHROPIC_API_KEY = "sk-ant-..."`
4. Deploy.

Get an API key at console.anthropic.com. Set a monthly spend limit there.
