WITH new_datasets AS (
    INSERT INTO candig.dataset (source_value, info) VALUES
        ('DATASET_001', '{"description": "Example dataset 1"}'),
        ('DATASET_002', '{"description": "Example dataset 2"}')
    RETURNING id, source_value
),
new_persons AS (
    INSERT INTO omop.person (
        gender_concept_id, year_of_birth, month_of_birth, 
        day_of_birth, birth_datetime, race_concept_id, ethnicity_concept_id,
        location_id, provider_id, care_site_id, person_source_value,
        gender_source_value, gender_source_concept_id, race_source_value,
        race_source_concept_id, ethnicity_source_value, ethnicity_source_concept_id
    )
    SELECT 8507, 1980+i, 6, 15, (1980+i || '-06-15 00:00:00')::timestamp,
           8527, 38003563,
           NULL, NULL, NULL,
           'DONOR_' || lpad(i::text,4,'0'),
           'M', 8507, 'ASIAN', 8527, 'NOT HISPANIC', 38003563
    FROM generate_series(1,9) s(i)
    RETURNING person_id, person_source_value
)
INSERT INTO candig.person_in_dataset (dataset_id, person_id)
SELECT d1.id, p.person_id
FROM new_persons p
JOIN new_datasets d1 ON d1.source_value = 'DATASET_001'
WHERE p.person_source_value IN ('DONOR_0001','DONOR_0002','DONOR_0003','DONOR_0004','DONOR_0005')
UNION ALL
SELECT d2.id, p.person_id
FROM new_persons p
JOIN new_datasets d2 ON d2.source_value = 'DATASET_002'
WHERE p.person_source_value IN ('DONOR_0006','DONOR_0007','DONOR_0008','DONOR_0009');