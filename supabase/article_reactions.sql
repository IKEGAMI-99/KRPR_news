-- Kirapara News article reactions
-- Public clients can read aggregate counts. Browser UUIDs stay hidden.

create extension if not exists pgcrypto;
create schema if not exists private;
revoke all on schema private from public, anon, authenticated;

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

create index if not exists article_reactions_article_id_idx on public.article_reactions (article_id);
create index if not exists article_reactions_client_id_idx on public.article_reactions (client_id);

alter table public.article_reactions enable row level security;
alter table public.article_reaction_counts enable row level security;

revoke all on public.article_reactions from anon, authenticated;
grant select (article_id, reaction_key, emoji, label, created_at) on public.article_reactions to anon, authenticated;
grant insert (article_id, reaction_key, emoji, label, client_id) on public.article_reactions to anon, authenticated;
grant delete on public.article_reactions to anon, authenticated;

revoke all on public.article_reaction_counts from anon, authenticated;
grant select on public.article_reaction_counts to anon, authenticated;

drop policy if exists "public can read reaction rows without client ids" on public.article_reactions;
create policy "public can read reaction rows without client ids"
on public.article_reactions for select to anon, authenticated using (true);

drop policy if exists "browser can insert only its own reaction" on public.article_reactions;
create policy "browser can insert only its own reaction"
on public.article_reactions for insert to anon, authenticated
with check (
  client_id = (select nullif(current_setting('request.headers', true)::jsonb ->> 'x-client-id', '')::uuid)
);

drop policy if exists "browser can delete only its own reaction" on public.article_reactions;
create policy "browser can delete only its own reaction"
on public.article_reactions for delete to anon, authenticated
using (
  client_id = (select nullif(current_setting('request.headers', true)::jsonb ->> 'x-client-id', '')::uuid)
);

drop policy if exists "reaction counts are public" on public.article_reaction_counts;
create policy "reaction counts are public"
on public.article_reaction_counts for select to anon, authenticated using (true);

create or replace function private.sync_article_reaction_count()
returns trigger
language plpgsql
security definer
set search_path = public, pg_temp
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
  elsif tg_op = 'DELETE' then
    update public.article_reaction_counts
    set count = greatest(0, count - 1)
    where article_id = old.article_id and reaction_key = old.reaction_key;
    delete from public.article_reaction_counts
    where article_id = old.article_id and reaction_key = old.reaction_key and count = 0;
    return old;
  end if;
  return null;
end;
$$;

revoke all on function private.sync_article_reaction_count() from public, anon, authenticated;

drop trigger if exists sync_article_reaction_count_insert on public.article_reactions;
create trigger sync_article_reaction_count_insert
after insert on public.article_reactions
for each row execute function private.sync_article_reaction_count();

drop trigger if exists sync_article_reaction_count_delete on public.article_reactions;
create trigger sync_article_reaction_count_delete
after delete on public.article_reactions
for each row execute function private.sync_article_reaction_count();

create or replace function public.kirapara_set_article_reaction(
  p_article_id text,
  p_reaction_key text,
  p_emoji text,
  p_label text,
  p_client_id uuid,
  p_selected boolean
)
returns void
language plpgsql
security invoker
set search_path = public, pg_temp
as $$
begin
  if p_article_id is null or char_length(p_article_id) not between 1 and 512 then raise exception 'invalid article id'; end if;
  if p_reaction_key is null or char_length(p_reaction_key) not between 1 and 128 then raise exception 'invalid reaction key'; end if;
  if p_emoji is null or char_length(p_emoji) not between 1 and 32 then raise exception 'invalid emoji'; end if;
  if p_label is null or char_length(p_label) > 32 then raise exception 'invalid label'; end if;
  if p_client_id is null then raise exception 'invalid client id'; end if;

  perform set_config('request.headers', jsonb_build_object('x-client-id', p_client_id::text)::text, true);

  if p_selected then
    begin
      insert into public.article_reactions(article_id, reaction_key, emoji, label, client_id)
      values (p_article_id, p_reaction_key, p_emoji, p_label, p_client_id);
    exception when unique_violation then null;
    end;
  else
    delete from public.article_reactions
    where article_id = p_article_id and reaction_key = p_reaction_key;
  end if;
end;
$$;

revoke all on function public.kirapara_set_article_reaction(text,text,text,text,uuid,boolean) from public;
grant execute on function public.kirapara_set_article_reaction(text,text,text,text,uuid,boolean) to anon, authenticated;

insert into public.article_reaction_counts(article_id,reaction_key,emoji,label,count)
select article_id,reaction_key,max(emoji),max(label),count(*)::bigint
from public.article_reactions
group by article_id,reaction_key
on conflict (article_id,reaction_key)
do update set emoji=excluded.emoji,label=excluded.label,count=excluded.count;
