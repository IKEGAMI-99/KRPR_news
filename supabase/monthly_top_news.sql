-- Monthly Kirapara News reaction totals, grouped by Asia/Tokyo month.

create table if not exists public.article_reaction_monthly_counts (
  month_key date not null,
  article_id text not null,
  stamp_count bigint not null default 0 check (stamp_count >= 0),
  primary key (month_key, article_id)
);

alter table public.article_reaction_monthly_counts enable row level security;
revoke all on public.article_reaction_monthly_counts from anon, authenticated;
grant select on public.article_reaction_monthly_counts to anon, authenticated;

drop policy if exists "monthly reaction counts are public" on public.article_reaction_monthly_counts;
create policy "monthly reaction counts are public"
on public.article_reaction_monthly_counts
for select
to anon, authenticated
using (true);

create or replace function private.sync_article_reaction_count()
returns trigger
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  v_month date;
begin
  if tg_op = 'INSERT' then
    v_month := date_trunc('month', new.created_at at time zone 'Asia/Tokyo')::date;

    insert into public.article_reaction_counts(article_id, reaction_key, emoji, label, count)
    values (new.article_id, new.reaction_key, new.emoji, new.label, 1)
    on conflict (article_id, reaction_key)
    do update set
      emoji = excluded.emoji,
      label = excluded.label,
      count = public.article_reaction_counts.count + 1;

    insert into public.article_reaction_monthly_counts(month_key, article_id, stamp_count)
    values (v_month, new.article_id, 1)
    on conflict (month_key, article_id)
    do update set stamp_count = public.article_reaction_monthly_counts.stamp_count + 1;

    return new;
  elsif tg_op = 'DELETE' then
    v_month := date_trunc('month', old.created_at at time zone 'Asia/Tokyo')::date;

    update public.article_reaction_counts
    set count = greatest(0, count - 1)
    where article_id = old.article_id and reaction_key = old.reaction_key;
    delete from public.article_reaction_counts
    where article_id = old.article_id and reaction_key = old.reaction_key and count = 0;

    update public.article_reaction_monthly_counts
    set stamp_count = greatest(0, stamp_count - 1)
    where month_key = v_month and article_id = old.article_id;
    delete from public.article_reaction_monthly_counts
    where month_key = v_month and article_id = old.article_id and stamp_count = 0;

    return old;
  end if;
  return null;
end;
$$;

revoke all on function private.sync_article_reaction_count() from public, anon, authenticated;

insert into public.article_reaction_monthly_counts(month_key, article_id, stamp_count)
select
  date_trunc('month', created_at at time zone 'Asia/Tokyo')::date,
  article_id,
  count(*)::bigint
from public.article_reactions
group by 1, 2
on conflict (month_key, article_id)
do update set stamp_count = excluded.stamp_count;

comment on table public.article_reaction_monthly_counts is
  'Monthly total reaction counts per Kirapara News article, grouped by Asia/Tokyo month.';
