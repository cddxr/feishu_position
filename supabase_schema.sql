create table if not exists public.amazon_keyword_rank (
  id bigint generated always as identity primary key,
  asin text not null,
  account_name text,
  zipcode text not null,
  keyword text not null,
  rank int,
  captured_at timestamptz not null,
  captured_date date not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create unique index if not exists uq_amazon_keyword_rank_key
on public.amazon_keyword_rank (asin, keyword, zipcode, captured_date);
