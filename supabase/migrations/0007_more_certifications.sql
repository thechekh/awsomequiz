-- Add the remaining 12 AWS certifications + per-user current-cert preference.
-- Idempotent: ON CONFLICT upserts on natural keys, ADD COLUMN IF NOT EXISTS.
--
-- Only CLF-C02 (and eventually DVA-C02) have questions seeded. The picker
-- UI uses `list_certifications_with_questions()` which filters to certs
-- that have at least one active question row, so the metadata rows below
-- don't accidentally show up as "practice now" options until their
-- question bank is loaded.
--
-- Official duration / question_count / pass threshold are from the AWS
-- exam guides as of 2026-05. If AWS changes them, update via an upsert.

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
  ('AIP-P01',  'AWS Certified Generative AI Developer - Professional',   75, 180, 75),
  -- Specialty
  ('ANS-C01',  'AWS Certified Advanced Networking - Specialty',          65, 170, 75),
  ('MLS-C01',  'AWS Certified Machine Learning - Specialty',             65, 180, 75),
  ('SCS-C02',  'AWS Certified Security - Specialty',                     65, 170, 75)
on conflict (code) do update set
  name              = excluded.name,
  question_count    = excluded.question_count,
  duration_minutes  = excluded.duration_minutes,
  pass_threshold_pct = excluded.pass_threshold_pct;

-- Per-user preference: which cert is "current". NULL means "use the app
-- default" (CLF-C02). Stored in profiles rather than a new table so we
-- don't pay the cost of an extra round-trip to look it up.
alter table public.profiles
  add column if not exists current_cert_code text references public.certifications(code) on delete set null;
