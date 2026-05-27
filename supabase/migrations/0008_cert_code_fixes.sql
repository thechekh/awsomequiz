-- Cert-code corrections to match the official AWS naming as of 2026-05.
-- Migration 0007 used the wrong code for two certs and included one that
-- AWS doesn't ship (MLS-C01 ML Specialty is being retired in favour of the
-- MLA-C01 Associate / SageMaker focus). This migration:
--   1. Renames AIP-P01  -> AIP-C01 (Generative AI Developer - Professional)
--   2. Renames SCS-C02  -> SCS-C03 (Security - Specialty)
--   3. Deletes the MLS-C01 row entirely.
--
-- Safe to run on the existing prod database because none of these three
-- rows have any questions, exam_sessions, or profile references (verified
-- before authoring this migration). The deletes/updates would otherwise
-- be blocked by foreign keys.

update public.certifications set code = 'AIP-C01' where code = 'AIP-P01';
update public.certifications set code = 'SCS-C03' where code = 'SCS-C02';
delete from public.certifications where code = 'MLS-C01';
