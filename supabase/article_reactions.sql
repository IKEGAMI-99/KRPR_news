-- Kirapara News article reactions
-- Safe for public clients only when Row Level Security stays enabled.

create extension if not exists pgcrypto;

create table if not exists public.article_reactions (
  id uuid primary key default gen_random_uuid(),
  article_id text not null check (char_length(article_id) between 1 and 512),
  reaction_key text not null check (char_length(reaction_key) between 1 and 128),
  emoji text not null check (char_length(emoji) between 1 and 32),
  label text not null default '' check (char_length(label) <= 32),
  client_id uuid not null,
  created_at timestamptz not null default now(),
  unique (article_id, reaction_key, client_id)
);

create index if not exists article_reactions_article_id_idx
  on public.article_reactions (article_id);

create index if not exists article_reactions_client_id_idx
  on public.article_reactions (client_id);

alter table public.article_reactions enable row level security;

create or replace function public.kirapara_request_client_id()
returns uuid
language sql
stable
as $$
  select nullif(
    coalesce(current_setting('request.headers', true), '{}')::jsonb ->> 'x-client-id',
    ''
  )::uuid;
$$;

revoke all on function public.kirapara_request_client_id() from public;
grant execute on function public.kirapara_request_client_id() to anon, authenticated;

drop policy if exists "article reactions are readable" on public.article_reactions;
create policy "article reactions are readable"
on public.article_reactions
for select
to anon, authenticated
using (true);

drop policy if exists "clients can insert own article reactions" on public.article_reactions;
create policy "clients can insert own article reactions"
on public.article_reactions
for insert
to anon, authenticated
with check (client_id = public.kirapara_request_client_id());

drop policy if exists "clients can delete own article reactions" on public.article_reactions;
create policy "clients can delete own article reactions"
on public.article_reactions
for delete
to anon, authenticated
using (client_id = public.kirapara_request_client_id());

grant select, insert, delete on public.article_reactions to anon, authenticated;

create or replace view public.article_reaction_counts
with (security_invoker = true)
as
select
  article_id,
  reaction_key,
  emoji,
  label,
  count(*)::bigint as count
from public.article_reactions
group by article_id, reaction_key, emoji, label;

grant select on public.article_reaction_counts to anon, authenticated;

comment on table public.article_reactions is
  'Discord-style reactions for Kirapara News articles. One reaction key per browser client and article.';
