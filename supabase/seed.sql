-- Seed all AWS certifications and CLF-C02's four official domains.
-- Idempotent: ON CONFLICT upserts on natural keys, so re-running just refreshes.
-- Production gets these via supabase/migrations/0006_more_certifications.sql;
-- seed.sql runs only on `supabase db reset` (local dev) so it has to mirror
-- the migration's certifications list to keep prod and dev consistent.
--
-- Question banks are loaded separately via scripts/migrate_sqlite_to_supabase.py
-- (or the JSON loader). A cert with no questions still exists as a row but
-- doesn't show up in the picker UI (list_certifications_with_questions filters
-- to certs that have at least one active question).

insert into public.certifications (code, name, question_count, duration_minutes, pass_threshold_pct)
values
  -- Foundational
  ('CLF-C02',  'AWS Certified Cloud Practitioner',                       65, 90,  70),
  ('AIF-C01',  'AWS Certified AI Practitioner',                          65, 90,  70),
  -- Associate
  ('SAA-C03',  'AWS Certified Solutions Architect - Associate',          65, 130, 72),
  ('DVA-C02',  'AWS Certified Developer - Associate',                    65, 130, 72),
  ('SOA-C03',  'AWS Certified CloudOps Engineer - Associate',            65, 130, 72),
  ('DEA-C01',  'AWS Certified Data Engineer - Associate',                65, 130, 72),
  ('MLA-C01',  'AWS Certified Machine Learning Engineer - Associate',    65, 130, 72),
  -- Professional
  ('SAP-C02',  'AWS Certified Solutions Architect - Professional',       75, 180, 75),
  ('DOP-C02',  'AWS Certified DevOps Engineer - Professional',           75, 180, 75),
  ('AIP-C01',  'AWS Certified Generative AI Developer - Professional',   75, 180, 75),
  -- Specialty
  ('ANS-C01',  'AWS Certified Advanced Networking - Specialty',          65, 170, 75),
  ('SCS-C03',  'AWS Certified Security - Specialty',                     65, 170, 75)
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
