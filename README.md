# feishu_position

## Pipeline
GitHub Actions schedule -> Python scrape -> Supabase upsert -> POST to Feishu workflow webhook -> Feishu loop -> Feishu sheet/base

## Setup
1. Run SQL in Supabase: `supabase_schema.sql`
2. Create repository secrets:
   - `SUPABASE_URL`
   - `SUPABASE_SERVICE_ROLE_KEY`
   - `SUPABASE_TABLE` (default `amazon_keyword_rank`)
   - `SUPABASE_ON_CONFLICT` (default `asin,keyword,zipcode,captured_date`)
   - `FEISHU_WEBHOOK_URL`
   - `TIMEZONE` (example `Asia/Shanghai`)
3. Adjust `ASIN_KEYWORDS_MAP` in `src/run_pipeline.py`
4. Manual run in GitHub Actions or wait for schedule

## Local run
```bash
pip install -r requirements.txt
cp .env.example .env
python src/run_pipeline.py
```

## Feishu workflow suggestion
1. Trigger node: webhook
2. Add loop node over `rows`
3. In loop body, add "write to multi-dimensional table" or "write to sheet"
4. Map fields: asin, keyword, zipcode, rank, captured_at
