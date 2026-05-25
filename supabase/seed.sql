-- Seed the CLF-C02 certification and its four official domains.
-- Idempotent: ON CONFLICT upserts on natural keys, so re-running just refreshes.
-- Weights are the official AWS exam-guide percentages for CLF-C02.

insert into public.certifications (code, name, question_count, duration_minutes, pass_threshold_pct)
values ('CLF-C02', 'AWS Certified Cloud Practitioner', 65, 90, 70)
on conflict (code) do update set
  name              = excluded.name,
  question_count    = excluded.question_count,
  duration_minutes  = excluded.duration_minutes,
  pass_threshold_pct = excluded.pass_threshold_pct;

with cert as (
  select id from public.certifications where code = 'CLF-C02'
)
insert into public.domains (certification_id, code, name, weight, display_order)
select cert.id, v.code, v.name, v.weight, v.display_order
from cert, (values
  ('cloud-concepts',            'Cloud Concepts',                24, 1),
  ('security-and-compliance',   'Security and Compliance',       30, 2),
  ('cloud-technology-services', 'Cloud Technology and Services', 34, 3),
  ('billing-pricing-support',   'Billing, Pricing, and Support', 12, 4)
) as v(code, name, weight, display_order)
on conflict (certification_id, code) do update set
  name          = excluded.name,
  weight        = excluded.weight,
  display_order = excluded.display_order;
