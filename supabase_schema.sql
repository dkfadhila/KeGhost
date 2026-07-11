-- KeGhost shared scan history — run once in Supabase SQL Editor
create table if not exists public.scans (
  id          bigint generated always as identity primary key,
  username    text not null,
  overall     text not null default 'warning',
  search_vis  int  default 0,
  reply_rate  int  default 0,
  quote_rate  int  default 0,
  engagement  int  default 0,
  layers      jsonb default '[]'::jsonb,
  profile     jsonb default '{}'::jsonb,
  avatar_url  text default '',
  created_at  timestamptz not null default now()
);

create index if not exists scans_created_idx  on public.scans (created_at desc);
create index if not exists scans_username_idx on public.scans (lower(username));

-- Shared history: anyone can read. Writes go through the backend service key (bypasses RLS).
alter table public.scans enable row level security;

drop policy if exists "public read scans" on public.scans;
create policy "public read scans" on public.scans
  for select using (true);
