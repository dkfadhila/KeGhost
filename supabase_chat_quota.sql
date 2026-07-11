-- KeGhost CapyAi chat quota — run once in Supabase SQL Editor
-- Tracks daily chat usage per username (reset handled by WIB date key from app).

create table if not exists public.chat_usage (
  username   text not null,
  day        text not null,               -- 'YYYY-MM-DD' in WIB
  count      int  not null default 0,
  updated_at timestamptz not null default now(),
  primary key (username, day)
);

alter table public.chat_usage enable row level security;
-- No public policies: only the service key (backend) touches this table.

-- Atomic upsert-increment. SECURITY DEFINER so the service role can call it via RPC.
create or replace function public.bump_chat_usage(p_username text, p_day text)
returns int
language plpgsql
security definer
as $$
declare
  new_count int;
begin
  insert into public.chat_usage (username, day, count, updated_at)
  values (p_username, p_day, 1, now())
  on conflict (username, day)
  do update set count = public.chat_usage.count + 1, updated_at = now()
  returning count into new_count;
  return new_count;
end;
$$;
