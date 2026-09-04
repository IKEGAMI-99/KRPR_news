-- Kirapara News article reactions
-- Public clients can read aggregate counts, but raw browser identifiers are not readable.

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

create table if not exists public.article_reaction_counts (
  article_id text not null,
  reaction_key text not null,
  emoji text not null,
  label text not null default '',
  count bigint not null default 0 check (count >= 0),
  primary key (article_id, reaction_key)
);

create index if not exists article_reactions_article_id_idx
  on public.article_reactions (article_id);

create index if not exists article_reactions_client_id_idx
  on public.article_reactions (client_id);

alter table public.article_reactions enable row level security;
alter table public.article_reaction_counts enable row level security;

-- Raw rows intentionally have no SELECT policy/grant. This keeps client UUIDs private.
drop policy if exists "article reactions are readable" on public.article_reactions;
drop policy if exists "clients can read own article reactions" on public.article_reactions;
drop policy if exists "clients can insert own article reactions" on public.article_reactions;
drop policy if exists "clients can delete own article reactions" on public.article_reactions;

create policy "clients can insert article reactions"
on public.article_reactions
for insert
to anon, authenticated
with check (client_id is not null);

create policy "clients can delete article reactions"
on public.article_reactions
for delete
to anon, authenticated
using (true);

drop policy if exists "reaction counts are public" on public.article_reaction_counts;
create policy "reaction counts are public"
on public.article_reaction_counts
for select
to anon, authenticated
using (true);

revoke all on public.article_reactions from anon, authenticated;
revoke all on public.article_reaction_counts from anon, authenticated;
grant insert, delete on public.article_reactions to anon, authenticated;
grant select on public.article_reaction_counts to anon, authenticated;

create or replace function public.kirapara_sync_reaction_count()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  if tg_op = 'INSERT' then
    insert into public.article_reaction_counts(article_id, reaction_key, emoji, label, count)
    values (new.article_id, new.reaction_key, new.emoji, new.label, 1)
    on conflict (article_id, reaction_key)
    do update set
      emoji = excluded.emoji,
      label = excluded.label,
      count = public.article_reaction_counts.count + 1;
    return new;
  end if;

  if tg_op = 'DELETE' then
    update public.article_reaction_counts
    set count = greatest(0, count - 1)
    where article_id = old.article_id and reaction_key = old.reaction_key;

    delete from public.article_reaction_counts
    where article_id = old.article_id
      and reaction_key = old.reaction_key
      and count <= 0;
    return old;
  end if;

  return null;
end;
$$;

revoke all on function public.kirapara_sync_reaction_count() from public, anon, authenticated;

drop trigger if exists kirapara_article_reaction_count_insert on public.article_reactions;
create trigger kirapara_article_reaction_count_insert
after insert on public.article_reactions
for each row execute function public.kirapara_sync_reaction_count();

drop trigger if exists kirapara_article_reaction_count_delete on public.article_reactions;
create trigger kirapara_article_reaction_count_delete
after delete on public.article_reactions
for each row execute function public.kirapara_sync_reaction_count();

-- Backfill/reconcile counts when this SQL is applied to an existing table.
insert into public.article_reaction_counts(article_id, reaction_key, emoji, label, count)
select article_id, reaction_key, max(emoji), max(label), count(*)::bigint
from public.article_reactions
group by article_id, reaction_key
on conflict (article_id, reaction_key)
do update set
  emoji = excluded.emoji,
  label = excluded.label,
  count = excluded.count;

comment on table public.article_reactions is
  'Discord-style Kirapara News reactions. Raw rows are write-only for public browser clients.';
comment on table public.article_reaction_counts is
  'Public aggregate reaction counts for Kirapara News articles.';
