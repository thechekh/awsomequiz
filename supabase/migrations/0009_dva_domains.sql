-- Seed DVA-C02 domains. CLF-C02's four domains live in supabase/seed.sql;
-- this migration adds DVA-C02's four domains directly (out-of-band from seed.sql
-- because seed.sql only runs on `supabase db reset`).
--
-- Weights are the official AWS exam-guide percentages.

with cert as (
  select id from public.certifications where code = 'DVA-C02'
)
insert into public.domains (certification_id, code, name, weight, display_order)
select cert.id, v.code, v.name, v.weight, v.display_order
from cert, (values
  ('dev-with-aws-services',         'Development with AWS Services',     32, 1),
  ('security',                      'Security',                          26, 2),
  ('deployment',                    'Deployment',                        24, 3),
  ('troubleshoot-optimization',     'Troubleshooting and Optimization',  18, 4)
) as v(code, name, weight, display_order)
on conflict (certification_id, code) do update set
  name          = excluded.name,
  weight        = excluded.weight,
  display_order = excluded.display_order;
