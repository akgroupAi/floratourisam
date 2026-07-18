-- Seed 6 hospitals + 6 doctors from Flora Medical Tourism PDF profiles.
-- Password for all doctors: Doctor@123456
-- Safe to re-run: skips rows when email/slug already exists.
--
-- Usage (production Postgres):
--   psql "$DATABASE_URL" -f scripts/seed_doctors_from_pdfs.sql
-- or paste into any Postgres client.

BEGIN;

-- Fixed IDs so related rows stay linked
-- Hospitals
--   h1 Skin N Smile Klinic
--   h2 Cheers Multi Speciality Hospital
--   h3 Fusion Kidney Institute
--   h4 OrthoSport Hospital
--   h5 Firozji Physiotherapist Clinic
--   h6 Nova IVF Wings Women's Hospital

-- Users / Doctors
--   u1/d1 Dr. Shadab R. Doi
--   u2/d2 Dr. Shiraz Ahmed Munshi
--   u3/d3 Dr. Manish Dhawan
--   u4/d4 Dr. Pranjel Pipara
--   u5/d5 Dr. Farhanahmed F. Pirzada
--   u6/d6 Dr. Jayesh Amin

-- bcrypt hash of: Doctor@123456
-- (same hash reused; bcrypt still verifies correctly)

-- ========== HOSPITALS ==========
INSERT INTO hospitals (
  id, name, slug, description, email, phone, website,
  address_line1, city, state, country, postal_code,
  total_reviews, is_active, is_verified, is_featured,
  total_doctors, total_patients_served, is_deleted
)
VALUES
(
  '13dbc8a7-beb7-4b48-b14a-1b9ce4de40a6',
  'Skin N Smile Klinic',
  'skin-n-smile-klinic',
  'Dermatology and dental clinic specializing in skin, hair transplant, and aesthetic procedures.',
  'drdoisns@gmail.com',
  '+919104044040',
  'https://www.skinnsmileklinic.com',
  'Shree Parshva Orion, 305/6/7, beside Adani Gas Station, Paldi Cross Roads',
  'Ahmedabad', 'Gujarat', 'India', NULL,
  0, TRUE, FALSE, FALSE, 0, 0, FALSE
),
(
  '0fb9356f-4599-432f-91b0-5b51543723e4',
  'Cheers Multi Speciality Hospital',
  'cheers-multi-speciality-hospital',
  'Multi-speciality hospital offering orthopedics, spine surgery, neurosurgery, gynecology, fertility & IVF, general surgery, urology, and respiratory medicine.',
  'Info.amd@cheershospitals.com',
  '+919998818148',
  'https://www.cheershospitals.com',
  'Swapneel-5, Near Commerce Six Roads, Navrangpura',
  'Ahmedabad', 'Gujarat', 'India', '380009',
  0, TRUE, FALSE, FALSE, 0, 0, FALSE
),
(
  '5dfa70f5-8c37-47d1-996a-6556bf7bb997',
  'Fusion Kidney Institute',
  'fusion-kidney-institute',
  'Specialized kidney institute focused on urology, renal transplantation, and minimally invasive urological surgeries.',
  'info@fusionkidney.com',
  NULL,
  NULL,
  'Fusion Kidney Institute, Ahmedabad',
  'Ahmedabad', 'Gujarat', 'India', NULL,
  0, TRUE, FALSE, FALSE, 0, 0, FALSE
),
(
  'a9810fbc-685c-4760-97da-a5c9482c6127',
  'OrthoSport Hospital',
  'orthosport-hospital',
  'Orthopaedic hospital specializing in joint replacement, sports injuries, and arthroscopy.',
  'contact@verddaan.com',
  '9090080505',
  NULL,
  'Opp Prahladnagar Fire Station, near YMCA Club',
  'Ahmedabad', 'Gujarat', 'India', NULL,
  0, TRUE, FALSE, FALSE, 0, 0, FALSE
),
(
  '297378ff-6005-4575-b053-7200fe2526e0',
  'Firozji Physiotherapist Clinic',
  'firozji-physiotherapist-clinic',
  'Physiotherapy clinic offering neuro, orthopaedic, post-surgery, pregnancy, and weight-loss physiotherapy care.',
  'DRFARHAN_PIRZADA@YAHOO.COM',
  '9974305501',
  NULL,
  'L1, L2 Al-Burooj Commercial, Opp. Seventh Heaven, Makarba',
  'Ahmedabad', 'Gujarat', 'India', '380055',
  0, TRUE, FALSE, FALSE, 0, 0, FALSE
),
(
  '567af8af-9d60-4904-aeca-45a9b95d54bf',
  'Nova IVF Wings Women''s Hospital',
  'nova-ivf-wings-womens-hospital',
  'Women''s hospital and IVF centre offering fertility treatments including IVF, ICSI, PGT, and related reproductive procedures.',
  'pushpak.jhaveri@novaivffertility.com',
  '+917600848484',
  'https://www.novaivffertility.com/ivf-centre/ahmedabad/fertility-clinic-bodakdev',
  '17, Sunrise Park, Himalaya Mall to Vastrapur Lake Road, Bodakdev',
  'Ahmedabad', 'Gujarat', 'India', '380054',
  0, TRUE, FALSE, FALSE, 0, 0, FALSE
)
ON CONFLICT (slug) DO NOTHING;


-- ========== USERS (doctors) ==========
-- Password: Doctor@123456
INSERT INTO users (
  id, email, hashed_password, full_name, phone, role,
  is_active, is_verified, verification_token, is_deleted
)
VALUES
(
  '49d00400-21ad-46aa-84bf-4f0f5bc54c9f',
  'drdoisns@gmail.com',
  '$2b$12$JZ2n1uTh4xMvLtqOX4j4mOLUE.9VzdOXhxCwdl9X3Ss340dx3jtvq',
  'Dr. Shadab R. Doi',
  '+919104044040',
  'doctor',
  TRUE, TRUE, NULL, FALSE
),
(
  'fa94f800-5568-443a-907e-57d4f2d367c0',
  'shiraz.munshi@cheershospitals.com',
  '$2b$12$rYLx5kJUVqs4yLLoCIl2luAZtSu1IEzw4mvHwvlEA4RW.3Eptd5Fi',
  'Dr. Shiraz Ahmed Munshi',
  '+919998818148',
  'doctor',
  TRUE, TRUE, NULL, FALSE
),
(
  'e0bcd720-4c3b-4b2a-87e6-35d0d89466c3',
  'manish.dhawan@fusionkidney.com',
  '$2b$12$dQwxr6ridi/ye0sfOTeLJO.hdddkygyaYfgEtJDICseumkCqobEZa',
  'Dr. Manish Dhawan',
  NULL,
  'doctor',
  TRUE, TRUE, NULL, FALSE
),
(
  '46a1fe95-71e4-4a86-953b-d504cfeaa29e',
  'pranjel.pipara@orthosport.com',
  '$2b$12$1mgBIWlQRFMcH1RX6hZZlezELMB3U0ydvXQMvKBfrvtnQJyNahK3a',
  'Dr. Pranjel Pipara',
  '9090080505',
  'doctor',
  TRUE, TRUE, NULL, FALSE
),
(
  '11089a63-a1bf-41ea-9216-c1bdafbdedb6',
  'DRFARHAN_PIRZADA@YAHOO.COM',
  '$2b$12$o1JiQEIp3t/7NSOclOHPFeQYYGqdxl0RE45z7SvVNqOfB5aFJdi46',
  'Dr. Farhanahmed F. Pirzada',
  '9974305501',
  'doctor',
  TRUE, TRUE, NULL, FALSE
),
(
  '46d7b3ba-882e-4448-9076-30cade7c294d',
  'jayesh.amin@novaivffertility.com',
  '$2b$12$/ESVcgMcs71c095zjErDNe0v/GnX0rbCDZS2x2XMCENAECWd61fe6',
  'Dr. Jayesh Amin',
  '+917600848484',
  'doctor',
  TRUE, TRUE, NULL, FALSE
)
ON CONFLICT (email) DO NOTHING;


-- ========== DOCTOR PROFILES ==========
INSERT INTO doctors (
  id, user_id, hospital_id, title, primary_specialty, years_of_experience,
  qualifications, education, certifications, bio, languages_spoken,
  consultation_fee, consultation_duration_minutes,
  video_consultation_enabled, chat_consultation_enabled, in_person_enabled,
  address_line1, city, state, country, postal_code,
  total_reviews, total_consultations, is_verified, verification_date, is_deleted
)
SELECT * FROM (VALUES
(
  '075bfb5a-c706-4150-9b1e-b554759948d9'::uuid,
  '49d00400-21ad-46aa-84bf-4f0f5bc54c9f'::uuid,
  '13dbc8a7-beb7-4b48-b14a-1b9ce4de40a6'::uuid,
  'Dr.',
  'Dermatologist & Hair Transplant Surgeon',
  9,
  ARRAY['MBBS','MD DVL','FIAL','Fellow Hair Transplant']::varchar[],
  '[{"degree":"MBBS","college":"VNSGU","year":2016,"location":"Surat, India"},{"degree":"MD DVL","college":"Gujarat University","year":2020,"location":"Ahmedabad, India"},{"degree":"FIAL","college":"ASI","year":2021,"location":"Melbourne, Australia"}]'::jsonb,
  '[{"name":"Fellowship in Aesthetic & Laser Medicine","location":"Australia"},{"name":"Fellowship in Hair Transplantation","location":"Istanbul, Turkey"}]'::jsonb,
  'Dr. Shadab Doi is a Consultant Dermatologist, Dermatosurgeon, Hair Transplant Surgeon, and Aesthetic Physician with over 9 years of clinical experience.',
  ARRAY['English','Hindi','Gujarati']::varchar[],
  700::float8,
  30,
  TRUE, TRUE, TRUE,
  'Shree Parshva Orion, 305/6/7, beside Adani Gas Station, Paldi Cross Roads',
  'Ahmedabad', 'Gujarat', 'India', NULL::varchar,
  0, 0, TRUE, NOW(), FALSE
),
(
  'c8557e70-02ad-4bea-8135-c152cd354edb'::uuid,
  'fa94f800-5568-443a-907e-57d4f2d367c0'::uuid,
  '0fb9356f-4599-432f-91b0-5b51543723e4'::uuid,
  'Dr.',
  'Endoscopic Spine Surgery & Pain Management',
  16,
  ARRAY['MBBS','D.Ortho','DNB','FIPP (USA)']::varchar[],
  '[{"degree":"MBBS","college":"BJMC Ahmedabad","year":2003,"location":"India"},{"degree":"DNB – Anesthesia","college":"National Board","year":2008,"location":"India"},{"degree":"Diploma – Orthopedics","college":"CPS Maharashtra","year":2018,"location":"India"},{"degree":"FIPP","year":2008,"location":"USA"}]'::jsonb,
  '[{"name":"FIPP - Fellow of Interventional Pain Practice","location":"World Institute of Pain, USA"},{"name":"Fellow Selective Endoscopic Discectomy","location":"DISC, Phoenix-Arizona, USA"}]'::jsonb,
  'Pioneer of Interventional Pain and Spine Endoscopy in India and East Africa. Offers pain management, endoscopic spine surgery, and regenerative therapy.',
  ARRAY['English','Hindi','Gujarati','Arabic','Swahili']::varchar[],
  2000::float8,
  30,
  TRUE, TRUE, TRUE,
  'Swapneel-5, Near Commerce Six Roads, Navrangpura',
  'Ahmedabad', 'Gujarat', 'India', '380009'::varchar,
  0, 0, TRUE, NOW(), FALSE
),
(
  '535a9d21-6108-43ba-b2a1-777367e8d774'::uuid,
  'e0bcd720-4c3b-4b2a-87e6-35d0d89466c3'::uuid,
  '5dfa70f5-8c37-47d1-996a-6556bf7bb997'::uuid,
  'Dr.',
  'Urology & Kidney Transplant',
  10,
  ARRAY['MBBS','MS','DNB']::varchar[],
  '[{"degree":"MBBS","college":"Medical College"},{"degree":"MS (General Surgery)","college":"Medical College"},{"degree":"DNB (Urology)","college":"National Board of Examinations"}]'::jsonb,
  '[{"name":"DNB Urology"},{"name":"Renal Transplant Surgery"}]'::jsonb,
  'Urologist and Kidney Transplant Surgeon and Director at Fusion Kidney Institute, Ahmedabad.',
  ARRAY['English','Hindi','Gujarati']::varchar[],
  NULL::float8,
  30,
  TRUE, TRUE, TRUE,
  NULL::varchar,
  'Ahmedabad', 'Gujarat', 'India', NULL::varchar,
  0, 0, TRUE, NOW(), FALSE
),
(
  '31ea3451-15aa-403f-b076-15ed12fa4894'::uuid,
  '46a1fe95-71e4-4a86-953b-d504cfeaa29e'::uuid,
  'a9810fbc-685c-4760-97da-a5c9482c6127'::uuid,
  'Dr.',
  'Joint Replacement & Sports Injuries',
  18,
  ARRAY['MBBS','MS Ortho']::varchar[],
  '[{"degree":"MBBS","college":"KMC Mangalore","year":"2002-2008","location":"India"},{"degree":"MS Ortho","college":"MS Ramaiah Medical College","year":"2008-2011","location":"Bangalore, India"}]'::jsonb,
  '[{"name":"ISAKOS Fellow"},{"name":"Fellowship in Joint Replacement and Sports Injury","location":"Vienna"}]'::jsonb,
  'Expertise in shoulder and knee surgery including joint replacement and sports injury/arthroscopy. 16,000+ procedures.',
  ARRAY['English','Hindi','Gujarati','Arabic']::varchar[],
  NULL::float8,
  30,
  TRUE, TRUE, TRUE,
  'Opp Prahladnagar Fire Station, near YMCA Club',
  'Ahmedabad', 'Gujarat', 'India', NULL::varchar,
  0, 0, TRUE, NOW(), FALSE
),
(
  '89ca28eb-a16e-4135-a73f-1685a8614722'::uuid,
  '11089a63-a1bf-41ea-9216-c1bdafbdedb6'::uuid,
  '297378ff-6005-4575-b053-7200fe2526e0'::uuid,
  'Dr.',
  'Physiotherapist',
  25,
  ARRAY['B.PT']::varchar[],
  '[{"degree":"Bachelor in Physiotherapy","college":"Rajiv Gandhi College","year":1996,"location":"Mangalore, India"}]'::jsonb,
  '[{"name":"B.PT"},{"name":"IAP"},{"name":"USA PT License (LARA)"}]'::jsonb,
  'Practicing since 2001. Treats orthopaedic, neuro, post-surgery, and pregnancy-related physiotherapy cases.',
  ARRAY['English','Hindi','Gujarati']::varchar[],
  NULL::float8,
  30,
  TRUE, FALSE, TRUE,
  'L1, L2 Al-Burooj Commercial, Opp. Seventh Heaven, Makarba',
  'Ahmedabad', 'Gujarat', 'India', '380055'::varchar,
  0, 0, TRUE, NOW(), FALSE
),
(
  '74117973-582d-4638-adbb-09d18cb07353'::uuid,
  '46d7b3ba-882e-4448-9076-30cade7c294d'::uuid,
  '567af8af-9d60-4904-aeca-45a9b95d54bf'::uuid,
  'Dr.',
  'In Vitro Fertilization',
  25,
  ARRAY['MBBS','MD (Gynaecology)']::varchar[],
  '[{"degree":"MBBS","college":"Saurashtra University","year":2000,"location":"India"},{"degree":"MD (Obstetrics & Gynaecology)","college":"Saurashtra University","year":2003,"location":"India"}]'::jsonb,
  '[{"name":"Fellowship for IVF & Embryology","location":"LARS Johnson, Sweden"}]'::jsonb,
  'Senior Consultant with more than 25 years of experience and 30,000+ IVF pregnancies. Successfully treated 10,000+ patients with PGT-A.',
  ARRAY['English','Hindi','Gujarati']::varchar[],
  2000::float8,
  30,
  TRUE, TRUE, TRUE,
  '17, Sunrise Park, Himalaya Mall to Vastrapur Lake Road, Bodakdev',
  'Ahmedabad', 'Gujarat', 'India', '380054'::varchar,
  0, 0, TRUE, NOW(), FALSE
)
) AS v(
  id, user_id, hospital_id, title, primary_specialty, years_of_experience,
  qualifications, education, certifications, bio, languages_spoken,
  consultation_fee, consultation_duration_minutes,
  video_consultation_enabled, chat_consultation_enabled, in_person_enabled,
  address_line1, city, state, country, postal_code,
  total_reviews, total_consultations, is_verified, verification_date, is_deleted
)
WHERE EXISTS (SELECT 1 FROM users u WHERE u.id = v.user_id)
  AND NOT EXISTS (SELECT 1 FROM doctors d WHERE d.user_id = v.user_id);


-- Resolve hospital IDs by slug in case ON CONFLICT skipped inserts with different IDs
-- and re-link doctors if hospitals already existed with other UUIDs.
UPDATE doctors d
SET hospital_id = h.id
FROM hospitals h, users u
WHERE d.user_id = u.id
  AND (
    (u.email = 'drdoisns@gmail.com' AND h.slug = 'skin-n-smile-klinic') OR
    (u.email = 'shiraz.munshi@cheershospitals.com' AND h.slug = 'cheers-multi-speciality-hospital') OR
    (u.email = 'manish.dhawan@fusionkidney.com' AND h.slug = 'fusion-kidney-institute') OR
    (u.email = 'pranjel.pipara@orthosport.com' AND h.slug = 'orthosport-hospital') OR
    (u.email = 'DRFARHAN_PIRZADA@YAHOO.COM' AND h.slug = 'firozji-physiotherapist-clinic') OR
    (u.email = 'jayesh.amin@novaivffertility.com' AND h.slug = 'nova-ivf-wings-womens-hospital')
  );


-- ========== SPECIALIZATIONS ==========
INSERT INTO doctor_specializations (
  id, doctor_id, specialization, is_primary, is_deleted
)
SELECT gen_random_uuid(), d.id, s.specialization, s.is_primary, FALSE
FROM doctors d
JOIN users u ON u.id = d.user_id
JOIN (VALUES
  ('drdoisns@gmail.com', 'Dermatology', TRUE),
  ('drdoisns@gmail.com', 'Hair Transplant', FALSE),
  ('drdoisns@gmail.com', 'Aesthetic Dermatology', FALSE),
  ('shiraz.munshi@cheershospitals.com', 'Pain Management', TRUE),
  ('shiraz.munshi@cheershospitals.com', 'Endoscopic Spine Surgery', FALSE),
  ('shiraz.munshi@cheershospitals.com', 'Regenerative Therapy', FALSE),
  ('manish.dhawan@fusionkidney.com', 'Kidney Transplant', TRUE),
  ('manish.dhawan@fusionkidney.com', 'Minimally Invasive Urology', FALSE),
  ('manish.dhawan@fusionkidney.com', 'Renal Surgery', FALSE),
  ('manish.dhawan@fusionkidney.com', 'Endourology', FALSE),
  ('pranjel.pipara@orthosport.com', 'Joint Replacement', TRUE),
  ('pranjel.pipara@orthosport.com', 'Sports Injury & Arthroscopy', FALSE),
  ('pranjel.pipara@orthosport.com', 'Orthopaedics', FALSE),
  ('DRFARHAN_PIRZADA@YAHOO.COM', 'Physiotherapy', TRUE),
  ('DRFARHAN_PIRZADA@YAHOO.COM', 'Neuro Physiotherapy', FALSE),
  ('DRFARHAN_PIRZADA@YAHOO.COM', 'Orthopaedic Physiotherapy', FALSE),
  ('DRFARHAN_PIRZADA@YAHOO.COM', 'Post Surgery Rehabilitation', FALSE),
  ('jayesh.amin@novaivffertility.com', 'In Vitro Fertilization', TRUE),
  ('jayesh.amin@novaivffertility.com', 'Reproductive Endocrinology', FALSE)
) AS s(email, specialization, is_primary)
  ON u.email = s.email
WHERE NOT EXISTS (
  SELECT 1 FROM doctor_specializations ds
  WHERE ds.doctor_id = d.id
    AND ds.specialization = s.specialization
    AND ds.is_deleted = FALSE
);


-- ========== AVAILABILITY (Mon-Sat) ==========
INSERT INTO doctor_availability (
  id, doctor_id, day_of_week, start_time, end_time,
  is_available, slot_duration_minutes, max_appointments, is_deleted
)
SELECT gen_random_uuid(), d.id, g.day_of_week, a.start_time::time, a.end_time::time,
       TRUE, 30, 8, FALSE
FROM doctors d
JOIN users u ON u.id = d.user_id
JOIN (VALUES
  ('drdoisns@gmail.com', '10:30:00', '18:30:00'),
  ('shiraz.munshi@cheershospitals.com', '12:00:00', '20:00:00'),
  ('manish.dhawan@fusionkidney.com', '09:00:00', '17:00:00'),
  ('pranjel.pipara@orthosport.com', '09:00:00', '17:00:00'),
  ('DRFARHAN_PIRZADA@YAHOO.COM', '10:00:00', '22:00:00'),
  ('jayesh.amin@novaivffertility.com', '10:00:00', '18:00:00')
) AS a(email, start_time, end_time)
  ON u.email = a.email
CROSS JOIN generate_series(0, 5) AS g(day_of_week)
WHERE NOT EXISTS (
  SELECT 1 FROM doctor_availability da
  WHERE da.doctor_id = d.id
    AND da.day_of_week = g.day_of_week
    AND da.is_deleted = FALSE
);


-- Keep hospital doctor counts roughly in sync
UPDATE hospitals h
SET total_doctors = sub.cnt
FROM (
  SELECT hospital_id, COUNT(*) AS cnt
  FROM doctors
  WHERE is_deleted = FALSE AND hospital_id IS NOT NULL
  GROUP BY hospital_id
) sub
WHERE h.id = sub.hospital_id
  AND h.slug IN (
    'skin-n-smile-klinic',
    'cheers-multi-speciality-hospital',
    'fusion-kidney-institute',
    'orthosport-hospital',
    'firozji-physiotherapist-clinic',
    'nova-ivf-wings-womens-hospital'
  );

COMMIT;

-- Verify
SELECT u.full_name, u.email, u.is_verified AS user_verified,
       d.is_verified AS doctor_verified, h.name AS hospital
FROM doctors d
JOIN users u ON u.id = d.user_id
LEFT JOIN hospitals h ON h.id = d.hospital_id
WHERE u.email IN (
  'drdoisns@gmail.com',
  'shiraz.munshi@cheershospitals.com',
  'manish.dhawan@fusionkidney.com',
  'pranjel.pipara@orthosport.com',
  'DRFARHAN_PIRZADA@YAHOO.COM',
  'jayesh.amin@novaivffertility.com'
)
ORDER BY u.full_name;
