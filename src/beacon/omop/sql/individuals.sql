
-- name: sql_get_individuals
-- Get individuals
SELECT person_id
FROM omop.person
LIMIT :limit
OFFSET :offset

-- name: cohort_individuals
-- Get individuals
SELECT subject_id as person_id
FROM omop.cohort
where cohort_definition_id = :cohort_id
LIMIT :limit
OFFSET :offset

-- name: count_cohort_individuals$
-- Get individuals count
SELECT count(*)
FROM omop.cohort
where cohort_definition_id = :cohort_id

-- name: count_individuals$
-- Get individuals count
SELECT count(*)
FROM omop.person

-- name: sql_get_individual_id^
-- Get individual by id
SELECT DISTINCT person_id
FROM omop.person
WHERE person_id = :person_id

-- name: sql_get_person
-- Get gender and race by id
SELECT gender_concept_id, race_concept_id
FROM omop.person
WHERE person_id = :person_id

-- name: sql_get_condition
-- Get condition properties by id

SELECT condition_concept_id,
    CASE
        WHEN birth_datetime IS NOT NULL THEN extract(Year from age(condition_start_date, birth_datetime)) 
        ELSE extract(Year from condition_start_date) - year_of_birth
	END AS condition_ageOfOnset
FROM omop.person as p,
    omop.condition_occurrence as c
WHERE p.person_id = :person_id and p.person_id = c.person_id;

-- name: sql_get_dataset
-- Get dataset by person id

SELECT dataset_id
FROM candig.person_in_dataset as p
WHERE p.person_id = :person_id;

-- name: sql_get_procedure
-- Get procedure properties by id
SELECT procedure_concept_id,
    CASE
        WHEN birth_datetime IS NOT NULL THEN extract(Year from age(procedure_date, birth_datetime)) 
        ELSE extract(Year from procedure_date) - year_of_birth
	END AS procedure_ageOfOnset,
    to_char(procedure_date, 'YYYY-MM-DD')
FROM omop.person as p,
    omop.procedure_occurrence as c
WHERE p.person_id = :person_id and p.person_id=c.person_id

-- name: sql_get_measure
-- Get measure properties by id
Select measurement_concept_id,
    CASE
        WHEN birth_datetime IS NOT NULL THEN extract(Year from age(measurement_date, birth_datetime)) 
        ELSE extract(Year from measurement_date) - year_of_birth
	END AS measurement_ageOfOnset,
    to_char(measurement_date, 'YYYY-MM-DD'),
    unit_concept_id,
    value_source_value
FROM omop.person as p,
    omop.measurement c
WHERE p.person_id = :person_id and p.person_id=c.person_id

-- name: sql_get_exposure
-- Get exposure properties by id
Select observation_concept_id,
    CASE
        WHEN birth_datetime IS NOT NULL THEN extract(Year from age(observation_date, birth_datetime)) 
        ELSE extract(Year from observation_date) - year_of_birth
	END AS observation_ageOfOnset,
    to_char(observation_date, 'YYYY-MM-DD'),
    unit_concept_id
FROM omop.person as p,
    omop.observation c
WHERE p.person_id = :person_id and p.person_id=c.person_id

-- name: sql_get_exposure_period^
-- Get exposure duration by id
SELECT 
    concat(
        'P', 
        extract(years from age(observation_period_end_date, observation_period_start_date)), 
        'Y', 
        extract(months from age(observation_period_end_date, observation_period_start_date)), 
        'M', 
        extract(days from age(observation_period_end_date, observation_period_start_date)), 
        'D'
    ) as duration
FROM omop.observation_period c
WHERE c.person_id = :person_id

-- name: sql_get_treatment
-- Get treatment properties by id

SELECT drug_concept_id,
    CASE
        WHEN birth_datetime IS NOT NULL THEN extract(Year from age(drug_exposure_start_date, birth_datetime)) 
        ELSE extract(Year from drug_exposure_start_date) - year_of_birth
	END AS drug_exposure_ageOfOnset
FROM omop.person as p,
    omop.drug_exposure as c
WHERE p.person_id = :person_id and p.person_id = c.person_id;


-- name: sql_get_descendants
-- Get descendants from concept_id
SELECT descendant_concept_id
FROM omop.concept_ancestor 
WHERE ancestor_concept_id = :concept_id

-- name: sql_get_concept_domain
-- Get OMOP concept_id and domain of the concept
SELECT concept_id, domain_id
FROM omop.concept
WHERE vocabulary_id = :vocabulary_id and concept_code = :concept_code

-- name: sql_get_ontology^
-- Get ontology 
SELECT concept_name as label,
    vocabulary_id || ':' || concept_code as id
FROM omop.concept 
WHERE concept_id = :concept_id

-- name: sql_filtering_terms_race_gender
-- Get all the race and gender filtering terms for individual
select distinct CONCAT(vocabulary_id,':',concept_code) as uri, c.concept_name
from omop.concept as c
join omop.person as p on p.race_concept_id=c.concept_id or p.gender_concept_id=c.concept_id

-- name: sql_filtering_terms_condition
-- Get all the condition_occurrence filtering terms for individual
select distinct CONCAT(vocabulary_id,':',concept_code) as uri, c.concept_name
from omop.concept as c
join omop.condition_occurrence as con on con.condition_concept_id=c.concept_id

-- name: sql_filtering_terms_measurement
-- Get all the measurement filtering terms for individual
select distinct CONCAT(vocabulary_id,':',concept_code) as uri, c.concept_name
from omop.concept as c
join omop.measurement as con on con.measurement_concept_id=c.concept_id

-- name: sql_filtering_terms_procedure
-- Get all the procedure_occurrence filtering terms for individual
select distinct CONCAT(vocabulary_id,':',concept_code) as uri, c.concept_name
from omop.concept as c
join omop.procedure_occurrence as con on con.procedure_concept_id=c.concept_id

-- name: sql_filtering_terms_observation
-- Get all the observation filtering terms for individual
select distinct CONCAT(vocabulary_id,':',concept_code) as uri, c.concept_name
from omop.concept as c
join omop.observation as con on con.observation_concept_id=c.concept_id

-- name: sql_filtering_terms_drug_exposure
-- Get all the drug exposure filtering terms for individual
select distinct CONCAT(vocabulary_id,':',concept_code) as uri, c.concept_name
from omop.concept as c
join omop.drug_exposure as con on con.drug_concept_id=c.concept_id

