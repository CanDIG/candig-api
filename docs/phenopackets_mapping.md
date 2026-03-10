# OMOP 5.4 to Phenopackets v2 Mapping

This document gives a detailed object by object, field by field overview of the approach taken to map the OMOP common data model to produce a valid and comprehensive phenopacket. The mapping is heavily tied to the way we mapped the MOHCCN model to the OMOP model, details and approaches to this are covered in [mohccn-omop-etl](https://github.com/CanDIG/mohccn-omop-etl). This mapping will most likely need to be updated as more diverse data is added into the OMOP database.

## 1. Subject
**Phenopacket Block:** `subject`
**OMOP Source Table:** `person`

### 1.1. id
- **OMOP Source:** `person.person_id`

- **Logic:** Direct copy. Cast the integer ID to a string.

- **SQL Check:**
```sql
SELECT person_id 
FROM omop.person 
WHERE person_id = <your_test_id>;
```
- **Example:** `12345` → `"12345"`

### 1.2. alternate_ids
- **OMOP Source:** `person.person_source_value`

- **Logic:** Wrap the single source string into a list of strings.

**SQL Check:**

```sql
SELECT person_source_value 
FROM omop.person 
WHERE person_id = <your_test_id>;
```
- **Example:** `"UHN-DONOR_99"` → `["UHN-DONOR_99"]`

### 1.3. date_of_birth
- **OMOP Source:** `person.year_of_birth`, `person.month_of_birth`, `person.day_of_birth`

- **Logic:**

  - Combine fields into an ISO8601 string (YYYY-MM-DD).

  - If Year is NULL or 1800, return None.

  - If Month or Day are missing/NULL, default them to 01.

**SQL Check:**
```sql
SELECT year_of_birth, month_of_birth, day_of_birth 
FROM omop.person 
WHERE person_id = <your_test_id>;
```
- **Example:** `1990, NULL, NULL` → `"1990-01-01"`

### 1.4. sex
- **OMOP Source:** `person.gender_concept_id`

- **Logic:** Map OMOP concept ID to Phenopacket Sex Enum:

  - `8507` → `"MALE"`

  - `8532` → `"FEMALE"`

  - `8521` → `"OTHER_SEX"`

  - `Else` → `"UNKNOWN_SEX"`

**SQL Check:**

```sql
SELECT gender_concept_id 
FROM omop.person 
WHERE person_id = <your_test_id>;
```
- **Example:** `8532` → `"FEMALE"`

### 1.5. taxonomy
- **OMOP Source:** N/A (Static)

- **Logic:** Hardcoded value for Homo sapiens.

- **Example:** 

```json
{ "id": "SNOMED:337915000", 
"label": "Homo sapiens (organism)" }
```

### 1.6. gender
- **OMOP Source:** `observation.value_as_concept_id`

- **Logic:**

  - Filter where `observation_concept_id` is `37171290` (Gender identity)

  - Map the resulting `value_as_concept_id` to an Ontology Term (id & label).

**SQL Check:**

```sql
SELECT value_as_concept_id 
FROM omop.observation 
WHERE person_id = <your_test_id> 
  AND observation_concept_id = 37171290;
```

- **Example:** `765761` → `{ "id": "SNOMED:446141000124107", "label": "Identifies as female gender" }`

---

## 1.7. Subject > Vital Status

**Phenopacket Block:** `subject.vital_status`

**OMOP Source Table:** `death`

**Inclusion rule:** Only created if subject has death object in OMOP

### 1.7.1. status
- **OMOP Source:** `death.death_date`

- **Logic:**

  - Check if a row exists in the death table for this person.

  - If death_date is present → `"DECEASED"`

  - Else Do not create `vital_status` object

**SQL Check:**

```sql
SELECT death_date 
FROM omop.death 
WHERE person_id = <your_test_id>;
```
- **Example:** `2023-01-01` → `"DECEASED"`

1.7.2. time_of_death
- **OMOP Source:** `death.death_date`
- **Logic:** Convert the date to a timestamp.

**SQL Check:**

```sql
SELECT death_date 
FROM omop.death 
WHERE person_id = <your_test_id>;
```
- **Example:** `2023-05-20` → { "timestamp": "2023-05-20" }

### 1.7.3. cause_of_death
- **OMOP Source:** `death.cause_concept_id`

- **Logic:** Map the concept ID to an Ontology Term.

**SQL Check:**

```sql
SELECT cause_concept_id 
FROM omop.death 
WHERE person_id = <your_test_id>;
```
- **Example:** `443392` → `{ "id": "SNOMED:363346000", "label": "Malignant neoplastic disease" }`

### 1.7.4. survival_time_in_days
- **OMOP Source:** `death.death_date` AND `condition_occurrence.condition_start_date`

- **Logic:**
  - Start Date (Diagnosis): Find episode where `episode_concept_id` = `32528` (Disease First Occurrence). Join to `condition_occurrence` via `episode_event` (field concept `1147127` `condition_occurrence.condition_occurrence_id`) to get `condition_start_date`.

  - End Date (Death): Get `death_date` from `death` table.

  - Calculation: `death_date` - `disease_first_occurrence_date` (result in days).

**SQL Check:**

```sql
-- Get Death Date
SELECT death_date FROM omop.death WHERE person_id = <your_test_id>;
-- Get First Occurrence Date
SELECT co.condition_start_date
FROM omop.episode e
JOIN omop.episode_event ee ON e.episode_id = ee.episode_id 
  AND ee.episode_event_field_concept_id = 1147127
JOIN omop.condition_occurrence co ON ee.event_id = co.condition_occurrence_id
WHERE e.person_id = <your_test_id> 
  AND e.episode_concept_id = 32528;
```
- **Example:** Death (`2023-01-10`) - Onset (`2023-01-01`) → 9

---

## 2. Biosamples

**Phenopacket Block:** `biosamples` (List)

**OMOP Source Table:** `specimen`

**Overview:** The list is generated by iterating through all records in the specimen table that match the person_id. Each specimen row creates one Biosample object.

### 2.1. id
- **OMOP Source:** `specimen.specimen_source_id`

- **Logic:**

  - **Grouping:** Unique per specimen row.

  - **Transformation:** Direct copy `specimen_source_id`.

**SQL Check:**

```sql
SELECT specimen_source_id 
FROM omop.specimen 
WHERE person_id = <your_test_id>;
```
- **Example:** `"SPECIMEN_0001"` → `"SPECIMEN_0001"`

### 2.2. individual_id
- **OMOP Source:** `specimen.person_id`

- **Logic:**

  - **Grouping:** Same `specimen` row.

  - **Transformation:** Direct copy. Cast to string. Must match the subject.id.

**SQL Check:**

```sql
SELECT person_id 
FROM omop.specimen 
WHERE specimen_id = <your_specimen_id>;
```
- **Example:** `12345` → `"12345"`

### 2.3. sampled_tissue
- **OMOP Source:** `specimen.anatomic_site_concept_id`

- **Logic:**

  - **Grouping:** Specific to each specimen row.

  - **Transformation:** Map the concept ID to an Ontology Term (ID & Label).

**SQL Check:**

```sql
SELECT anatomic_site_concept_id 
FROM omop.specimen 
WHERE specimen_id = <your_specimen_id>;
```

- **Example:** `44497885` → `{ "id": "SNOMED:C57.8", "label": "Overlapping lesion of female genital organs" }`

### 2.4. taxonomy
- **OMOP Source:** N/A (Static)

- **Logic:**

  - **Grouping:** Applied to every specimen object.

  - **Transformation:** Hardcoded value for Homo sapiens.

- **Example:** `{ "id": "SNOMED:337915000", "label": "Homo sapiens (organism)" }`

2.5. time_of_collection
- **OMOP Source:** `specimen.specimen_date`

- **Logic:**

  - **Grouping:** Specific to each specimen row.

  - **Transformation:** Convert the date to an  timestamp object.

**SQL Check:**

```sql
SELECT specimen_date 
FROM omop.specimen 
WHERE specimen_id = <your_specimen_id>;
```
- **Example:** 2023-02-15 → { "iso8601timestamp": "2023-02-15" }

### 2.6. histological_diagnosis
- **OMOP Source:** `observation.value_as_concept_id`

- **Logic:**

  - **Grouping:** Joined to the specific `specimen_id`.

  - **Linkage:** Join `observation` ON `observation_event_id` = `specimen_id` AND `obs_event_field_concept_id` = `1147049` (Specimen).

  - **Filter:** `observation_concept_id` == `36716952` (Morphology).

  - **Transformation:** Map `value_as_concept_id` to Ontology Term.

**SQL Check:**

```sql
SELECT obs.value_as_concept_id
FROM omop.specimen s
JOIN omop.observation obs ON obs.observation_event_id = s.specimen_id
WHERE s.specimen_id = <your_specimen_id>
  AND obs.obs_event_field_concept_id = 1147049
  AND obs.observation_concept_id = 36716952;
```

- **Example:** `44498902` → `{ "id": "ICDO3:9726/3", "label": "Primary cutaneous gamma-delta T-cell lymphoma" }`

### 2.7. tumor_grade
- **OMOP Source:** `observation.value_as_concept_id`

- **Logic:**

  - **Grouping:** Joined to the specific `specimen_id`.

  - **Linkage:** Join observation ON observation_event_id = specimen_id AND obs_event_field_concept_id = 1147049 (specimen.specimen_id).

  - **Filter:** `observation_concept_id` == `4160340` (Histologic grade of neoplasm).

  - **Transformation:** Map `value_as_concept_id` to Ontology Term.

**SQL Check:**

```sql
SELECT obs.value_as_concept_id
FROM omop.specimen s
JOIN omop.observation obs ON obs.observation_event_id = s.specimen_id
WHERE s.specimen_id = <your_specimen_id>
  AND obs.obs_event_field_concept_id = 1147049
  AND obs.observation_concept_id = 4160340;
```
- **Example:** `37164072` → `{ "id": "SNOMED:1228845001", "label": "GX (AJCC)" }`

### 2.8. pathological_tnm_finding
- **OMOP Source:** `measurement.value_as_concept_id`

- **Logic:**

  - **Grouping:** TODO - Currently implementation fetches this list at the Person level and duplicates the same list for every biosample. It does not filter by specimen ID.

  - **Linkage:** Query measurement table where `person_id` matches.

  - **Filter:** `measurement_concept_id` IN `[4293617, 4161174, 4154262]` (pT category, pN category, pM category).

  - **Transformation:** Map `value_as_concept_id` to Ontology Term.

**SQL Check:**

```sql
SELECT value_as_concept_id, measurement_concept_id
FROM omop.measurement
WHERE person_id = <your_test_id>
  AND measurement_concept_id IN (4293617, 4161174, 4154262);
```
- **Example:** `[ { "id": "LOINC:LA3624-9", "label": "T3" }, { "id": "LOINC:LA4517-4", "label": "N2b" }, {"id": "LOINC:LA3624-9", "label": "T3" } ]`

### 2.9. sample_processing
- **OMOP Source:** `observation.value_as_concept_id`

- **Logic:**

  - **Grouping:** Joined to the specific `specimen_id`.

  - **Linkage:** Join observation ON `observation_event_id = specimen_id` AND `obs_event_field_concept_id = 1147049` (`specimen.specimen_id`).

  - **Filter:** `observation_concept_id` == `4154128` (Specimen type).

  - **Transformation:** Map `value_as_concept_id` to Ontology Term.

**SQL Check:**

```sql
SELECT obs.value_as_concept_id
FROM omop.specimen s
JOIN omop.observation obs ON obs.observation_event_id = s.specimen_id
WHERE s.specimen_id = <your_specimen_id>
  AND obs.obs_event_field_concept_id = 1147049
  AND obs.observation_concept_id = 4154128;
```
- **Example:** `40480027` → `{ "id": "SNOMED:441652008", "label": "Formalin-fixed paraffin-embedded tissue specimen" }`

### 2.10. sample_storage
- **OMOP Source:** `observation.value_as_concept_id`

- **Logic:**

  - **Grouping:** Joined to the specific `specimen_id`.

  - **Linkage:** Join observation ON `observation_event_id = specimen_id` AND `obs_event_field_concept_id = 1147049` (specimen.specimen_id).

  - **Filter:** `observation_concept_id == 37169821` (Specimen storage).

  - **Transformation:** Map `value_as_concept_id` to Ontology Term.

**SQL Check:**

```sql
SELECT obs.value_as_concept_id
FROM omop.specimen s
JOIN omop.observation obs ON obs.observation_event_id = s.specimen_id
WHERE s.specimen_id = <your_specimen_id>
  AND obs.obs_event_field_concept_id = 1147049
  AND obs.observation_concept_id = 37169821;
```
- **Example:** `9177` → `{ "id": "SNOMED:74964007", "label": "Other" }`

### 2.11 measurements
Follows same mapping strategy as [Measurements](#5.-Measurements)
  but uses the mapping values in the concept mapping file under biosamples.measurements

---

## 3. Diseases
**Phenopacket Block:** `diseases` (List)
**OMOP Source Table:** `condition_occurrence`
**Overview:** Each `condition_occurrence` creates a `disease` object. Condition occurrences that are linked to a 'Disease First Occurrence' `episode` can be populated with more metadata, whereas other condition occurrences have minimal metadata (comorbidities in mohccn model).

### 3.1. term
- **OMOP Source:** `condition_occurrence.condition_concept_id`

- **Logic:**
  - **Grouping:** Grouped by `episode_id`

  - **Linkage:**

    - Find episode where `episode_concept_id` == `32528` (Disease First Occurrence).

    - Join `episode_event` ON `episode_id` AND `episode_event_field_concept_id` == `1147127 `(`condition_occurrence.condition_occurrence_id`).

    - Join `condition_occurrence` ON `event_id` == `condition_occurrence_id`.

  - **Transformation:** Map `condition_concept_id` to Ontology Term.
    
    - **Linkage:**

      - Find `condition_occurrence` where `condition_occurrence_id` not in  `condition_occurrence_id` already found above
      
      - **Transformation:** Map `condition_concept_id` to Ontology Term.

**SQL Check:**

```sql
SELECT co.condition_concept_id
co.condition_occurrence_id
FROM omop.episode e
JOIN omop.episode_event ee ON e.episode_id = ee.episode_id 
  AND ee.episode_event_field_concept_id = 1147127
JOIN omop.condition_occurrence co ON ee.event_id = co.condition_occurrence_id
WHERE e.person_id = <your_test_id> 
  AND e.episode_concept_id = 32528;
```
- **Example:** `45590880` → `{ "id": "ICD10:C23", "label": "Malignant neoplasm of gallbladder" }`

```sql
SELECT co.condition_concept_id
FROM omop.condition_occurrence co
WHERE co.person_id = <your_test_id> 
  AND co.condition_occurrence_id NOT IN(<condition_occurrence_ids from query above>)
```
- **Example:** `45590880` → `{ "id": "ICD10:C23", "label": "Malignant neoplasm of gallbladder" }`

### 3.2. onset
- **OMOP Source:** `condition_occurrence.condition_start_date`

- **Logic:**

  - **Grouping:** Specific to the linked `condition_occurrence` record.

  - **Transformation:** Convert date to timestamp object.

**SQL Check:**

```sql
SELECT co.condition_start_date
FROM omop.episode e
JOIN omop.episode_event ee ON e.episode_id = ee.episode_id 
  AND ee.episode_event_field_concept_id = 1147127
JOIN omop.condition_occurrence co ON ee.event_id = co.condition_occurrence_id
WHERE e.person_id = <your_test_id> 
  AND e.episode_concept_id = 32528;
```

```sql
SELECT co.condition_start_date
FROM omop.condition_occurrence co 
WHERE e.person_id = <your_test_id> 
  AND co.condition_occurrence_id NOT IN(<condition_occurrence_ids from query above>)
```
- **Example:** `2019-06-01` → `{ "timestamp": "2019-06-01" }`

### 3.3. resolution
- **OMOP Source:** `condition_occurrence.condition_end_date`

- **Logic:**

  - **Grouping:** Specific to the linked `condition_occurrence` record.

  - **Transformation:** Convert date to timestamp object.

**SQL Check:**

```sql
SELECT co.condition_end_date
FROM omop.episode e
JOIN omop.episode_event ee ON e.episode_id = ee.episode_id 
  AND ee.episode_event_field_concept_id = 1147127
JOIN omop.condition_occurrence co ON ee.event_id = co.condition_occurrence_id
WHERE e.person_id = <your_test_id> 
  AND e.episode_concept_id = 32528;
```

```sql
SELECT co.condition_end_date
FROM omop.condition_occurrence co 
WHERE e.person_id = <your_test_id> 
  AND co.condition_occurrence_id NOT IN(<condition_occurrence_ids from query above>)
```

- **Example:** `2020-01-01` → `{ "iso8601timestamp": "2020-01-01" }`

### 3.4. primary_site
- **OMOP Source:** `observation.value_as_concept_id`

- **Logic:**

  - **Grouping:** Group to `condition_occurrence` through `observation_event_id`

  - **Linkage:** Join `observation` table on `person_id`.

  - **Filter:** `observation_concept_id` == `3011717` (Primary site Cancer).

  - **Transformation:** Map `value_as_concept_id` to Ontology Term.

**SQL Check:**

```sql
SELECT value_as_concept_id 
FROM omop.observation o
JOIN condition_occurrence co
ON o.observation_event_id = co.condition_occurrence_id
WHERE person_id = <your_test_id> 
  AND observation_concept_id = 3011717;
```
- **Example:** `44497844` → `{ "id": "ICDO3:C50", "label": "Breast" }`

### 3.5. disease_stage
- **OMOP Source:** `measurement.value_as_concept_id`

- **Logic:**

  - **Grouping:** TODO - Fetched at Person level. All stages found for the person are attached to every disease object.

  - **Linkage:** Query measurement table for `person_id`.

  - **Filter:**

    - `measurement_concept_id` IS descendant of `[37163866, 4130406, 734333]`(American Joint Committee on Cancer allowable value, Stages, INRG finding via concept_ancestor).

    - OR `value_as_concept_id` IN `[4136272, 4114652, ...]` (specific stage concepts).

  - **Transformation:** Map `value_as_concept_id` to Ontology Term.

**SQL Check:**

```sql
SELECT m.value_as_concept_id
FROM omop.measurement m
WHERE m.person_id = <your_test_id>
  AND (
      m.measurement_concept_id IN (
          SELECT descendant_concept_id FROM omop.concept_ancestor 
          WHERE ancestor_concept_id IN (37163866, 4130406, 734333)
      )
      OR m.value_as_concept_id IN (4136272, 4114652, 45876326) -- (truncated list for readability)
  );
```
- **Example:** `[ { "id": "LOINC:LA3668-6", "label": "Stage B" } ]`

### 3.6. clinical_tnm_finding
- **OMOP Source:** `measurement.value_as_concept_id`

- **Logic:**

- **Grouping:** TODO - Fetched at Person level. Attached to every disease object.

  - **Linkage:** Query measurement table for `person_id`.

  - **Filter:** measurement_concept_id IN `[4164336, 4164182, 4164466]` (cT, cN, cM categories).

  - **Transformation:** Map `value_as_concept_id` to Ontology Term.

**SQL Check:**

```sql
SELECT value_as_concept_id 
FROM omop.measurement 
WHERE person_id = <your_test_id> 
  AND measurement_concept_id IN (4164336, 4164182, 4164466);
```
- **Example:** `[ { "id": "LOINC:LA3608-2", "label": "Tis" }, { "id": "LOINC:LA4368-2", "label": "N0" } ]`

### 3.7. laterality
- **OMOP Source:** `measurement.value_as_concept_id`

- **Logic:**

- **Grouping:** Grouped by `condition_occurrence`.

  - **Linkage:** Query measurement table for `person_id`, join to `condition_occurrence` by `measurement_event_id`

  - **Filter:** `measurement_concept_id` == `35918306` (Laterality).

  - **Transformation:** Map `value_as_concept_id` to Ontology Term.

**SQL Check:**

```sql
SELECT m.value_as_concept_id 
FROM omop.condition_occurrence as co
JOIN omop.measurement as m
ON co.condition_occurrence_id = m.measurement_event_id
WHERE person_id = <your_test_id> 
  AND measurement_concept_id = 35918306;
```
- **Example:** `36770232` → `{ "id": "Cancer Modifier:OMOP4999911", "label": "Left" }`

---

## 4. Medical Actions
**Phenopacket Block:** `medical_actions` (List)
**OMOP Source:** Aggregation of `condition_occurrence`, `procedure_occurrence`, `drug_exposure`, and `episode` data.
**Overview:** This section aggregates various parts.

> [!Note] 
> The current logic uses episodes to ensure data from different objects are grouped correctly.

### 4.1. treatment_target
- **OMOP Source:** `condition_occurrence.condition_concept_id`

- **Logic:**

  - **Grouping:** Matches the `condition_occurrence` to its linked treatment `episode`s to match the target to the treatment

  - **Linkage:**

    - Find `episode` where `episode_concept_id` == `32528` (Disease First Occurrence).

    - Join `episode_event` to `condition_occurrence`.

    - Join `condition_occurrence` again to `episode_event` to get the linked treatment `episode`s

  - **Transformation:** Map `condition_concept_id` to Ontology Term and return as dict with episodes as keys.

**SQL Check:**

```sql
SELECT co.condition_concept_id, other_event.episode_id as episode_id
FROM omop.episode e
JOIN omop.episode_event ee ON e.episode_id = ee.episode_id 
  AND ee.episode_event_field_concept_id = 1147127
JOIN omop.condition_occurrence co ON ee.event_id = co.condition_occurrence_id
JOIN omop.episode_event as other_event ON condition_occurrence_id=other_event.event_id
WHERE e.person_id = <your_test_id> 
  AND e.episode_concept_id = 32528;
```
- **Example:** `45590880` → `{46: {"id": "ICD10:C23", "label": "Malignant neoplasm of gallbladder"}, 47: {"id": "ICD10:C23", "label": "Malignant neoplasm of gallbladder"}}`

### 4.2. treatment_intent
- **OMOP Source:** `observation.value_as_concept_id`

- **Logic:**

  - **Grouping:** Linked to the specific Treatment Episode.

  - **Linkage:**

    - Find observation where `observation_concept_id` == `4133895` (Therapeutic).

    - `observation_event_id` is the link to the Episode.

  - **Transformation:** Map `value_as_concept_id` to Ontology Term. Defaults to "No value" if missing. Return as dict with treatment `episode` ids as keys.

**SQL Check:**

```sql
SELECT value_as_concept_id 
FROM omop.observation 
WHERE person_id = <your_test_id> 
  AND observation_concept_id = 4133895;
```
- **Example:** `40491905` → `{46: {"id": "SNOMED:447295008", "label": "Forensic intent" }, 47: "id": "SNOMED:360156006", "label": "Screening intent"}`

### 4.3. response_to_treatment
- **OMOP Source:** `observation.value_as_concept_id`

- **Logic:**

- **Grouping:** Linked to the specific `Treatment` Episode.

  - **Linkage:**

    - Find observation where `observation_concept_id` == `4082405` (Response to treatment).

    - `observation_event_id` is the link to the Episode.

  - **Transformation:** Map `value_as_concept_id` to Ontology Term. Defaults to "No value" if missing. Return as dict with treatment `episode` ids as keys.

**SQL Check:**

```sql
SELECT value_as_concept_id 
FROM omop.observation 
WHERE person_id = <your_test_id> 
  AND observation_concept_id = 4082405;
```
- **Example:** `36310520` → `{46: {"id": "LOINC:LA4566-1", "label": "No Evidence of this Cancer"}, 47: {"id": "LOINC:LA28369-9", "label": "Partial response"}}`

---

### 4.4. Action type: Procedure
**Block:** `medical_actions.procedure`

#### 4.4.1. code
- **OMOP Source:** `procedure_occurrence.procedure_concept_id`

- **Logic:**

  - **Linkage:**

    - Find episode where `episode_concept_id` == `32939` (Cancer Surgery).

    - Join episode_event to `procedure_occurrence` (field concept `1147082`).

  - **Transformation:** 
    - Map `procedure_concept_id` to Ontology Term.
    - If `procedure_concept_id` == `0`, parse `procedure_source_id` to Ontology Term
    - Return as dict with `episode` ids as keys

**SQL Check:**

```sql
SELECT po.procedure_concept_id,
       po.procedure_source_value
FROM omop.episode e
JOIN omop.episode_event ee ON e.episode_id = ee.episode_id 
  AND ee.episode_event_field_concept_id = 1147082
JOIN omop.procedure_occurrence po ON ee.event_id = po.procedure_occurrence_id
WHERE e.person_id = <your_test_id> 
  AND e.episode_concept_id = 32939;
```
- **Example:** `4281521` → `{46: "id": "SNOMED:66398006", "label": "Excision of breast with excision of regional lymph nodes" }}`
- **Example:** `UMLS|C0005558|Biopsy` → `{47: {"id": "UMLS:C0005558", "Biopsy"}}`

#### 4.4.2. body_site
- **OMOP Source:** `observation.value_as_concept_id`

- **Logic:**

  - **Linkage:** Join `observation` ON `observation_event_id` == `episode_id`.

  - **Filter:** `observation_concept_id` == `4181646` (Procedure site) AND `obs_event_field_concept_id` == `798885` (episode.episode_id).

  - **Transformation:** Map `value_as_concept_id` to Ontology Term.

**SQL Check:**

```sql
SELECT obs.value_as_concept_id
FROM omop.episode e
JOIN omop.observation obs ON obs.observation_event_id = e.episode_id
WHERE e.person_id = <your_test_id> 
  AND e.episode_concept_id = 32939
  AND obs.observation_concept_id = 4181646;
```
- **Example:** `0` → `{ "id": "SNOMED:408094002", "label": "No value" }`

#### 4.4.3. performed
- **OMOP Source:** `procedure_occurrence.procedure_date`

- **Logic:** Convert date to timestamp object.

**SQL Check:**

```sql
SELECT po.procedure_date
FROM omop.episode e
JOIN omop.episode_event ee ON e.episode_id = ee.episode_id
JOIN omop.procedure_occurrence po ON ee.event_id = po.procedure_occurrence_id
WHERE e.person_id = <your_test_id> AND e.episode_concept_id = 32939;
```
- **Example:** `2020-02-20` → `{ "timestamp": "2020-02-20" }`

### 4.5. Action Type: Treatment (Drug)
**Block:** `medical_actions.treatment`

#### 4.5.1. agent
- **OMOP Source:** `drug_exposure.drug_concept_id`

- **Logic:**

  - **Linkage:**

    - Find episode where `episode_concept_id` == `32941` (Cancer Drug Treatment).

    - Join `episode_event` to `drug_exposure` (field concept `1147094` `drug_exposure.drug_exposure_id`).

    - Filter `drug_type_concept_id` IN `[32833, 32838]` (EHR order, EHR prescription).
    - 

  - **Transformation:** 
    - Map `drug_concept_id` to Ontology Term 
    - If `drug_type_concept_id` == 0, parse `drug_source_value` using pipe delimited values

**SQL Check:**

```sql
SELECT de.drug_concept_id,
       de.drug_source_value
FROM omop.episode e
JOIN omop.episode_event ee ON e.episode_id = ee.episode_id 
  AND ee.episode_event_field_concept_id = 1147094
JOIN omop.drug_exposure de ON ee.event_id = de.drug_exposure_id
WHERE e.person_id = <your_test_id> AND e.episode_concept_id = 32941;
```
- **Example:** `42426830` → `{ "id": "RxNorm:42426830", "label": "Tamoxifen" }`
- **Example:** `"PubChem|472634117|Ipilimumab"` → `{ "id": "PubChem:472634117", "label": "Ipilimumab" }`

#### 4.5.2. route_of_administration
- **OMOP Source:** `drug_exposure.route_concept_id`

- **Logic:** Map concept to Ontology Term. Defaults to `"Unknown" (SNOMED:261665006)` if missing.

**SQL Check:**

```sql
SELECT route_concept_id 
FROM omop.drug_exposure 
WHERE person_id = <your_test_id>;
```
- **Example:** `NULL` → `{ "id": "SNOMED:261665006", "label": "Unknown" }`

#### 4.5.3. drug_type
- **OMOP Source:** `drug_exposure.drug_type_concept_id`

- **Logic:**
  - If `drug_type_concept_id` == `32838` (EHR prescription) → "PRESCRIPTION"

  - Else → `"UNKNOWN_DRUG_TYPE"`

- **Example:** `32838` → `"PRESCRIPTION"`

#### 4.5.4. cumulative_dose
- **OMOP Source:** `drug_exposure.quantity`

- **Logic:**

  - Only populated if `drug_type_concept_id` IN `[32833]` (EHR order).

  - **Value:** `quantity`.

  - **Unit:** Mapped from `dose_unit_source_value` (e.g., "mg" → Ontology) based on mapping in `src/concept_mappings.json`.

**SQL Check:**

```sql
SELECT quantity, dose_unit_source_value
FROM omop.drug_exposure
WHERE person_id = <your_test_id> AND drug_type_concept_id = 32833;
```
- **Example:** `55.7` `"mg/m2"` → `4223319` →`{ "value": 55.7, "unit": { "id": "SNOMED:404216004", "label": "mg/m2" } }`

### 4.6. Action Type: Radiation Therapy
**Block:** `medical_actions.radiation_therapy`
**Grouping** Radiation therapy fields grouped by linkage to `Treatment regimen (32531)` episode

#### 4.6.1. modality
- **OMOP Source:** `episode.episode_object_concept_id`

- **Logic:**

  - **Linkage:** Find `episode` where `episode_concept_id` == `32940` (Cancer Radiotherapy).

  - **Transformation:** Map `episode_object_concept_id` to Ontology Term.

**SQL Check:**

```sql
SELECT episode_object_concept_id
FROM omop.episode
WHERE person_id = <your_test_id> AND episode_concept_id = 32940;
```
- **Example:** `607996` → `{ "id": "SNOMED:1156506007", "label": "External beam radiation therapy using photons" }`

#### 4.6.2. body_site
- **OMOP Source:** `observation.value_as_concept_id`

- **Logic:**

  - **Linkage:** Join `observation` ON `observation_event_id` == `episode_id`.

  - **Filter:** `observation_concept_id` IN `[4181646]`.

  - **Transformation:** Map `value_as_concept_id` to Ontology Term.

**SQL Check:**

```sql
SELECT obs.value_as_concept_id
FROM omop.episode e
JOIN omop.observation obs ON obs.observation_event_id = e.episode_id
WHERE e.person_id = <your_test_id> AND e.episode_concept_id = 32940;
```
- **Example:** `36717353` → `{ "id": "SNOMED:722738000", "label": "Structure of bone of left femur" }`

#### 4.6.3. dosage
- **OMOP Source:** `measurement.value_as_number`

- **Logic:**

  - **Linkage:** Query `measurement` table for `person_id`.

  - **Filter:** `measurement_concept_id` IN `[40483776]` (Total radiation dose delivered).

  - **Transformation:** Cast to integer.

**SQL Check:**

```sql
SELECT value_as_number
FROM omop.measurement
WHERE person_id = <your_test_id> AND measurement_concept_id = 40483776;
```
- **Example:** `60` → `60`

#### 4.6.4. fractions
- **OMOP Source:** `measurement.value_as_number`

- **Logic:**

  - **Linkage:** Query `measurement` table for `person_id`.

  - **Filter:** `measurement_concept_id` IN `[4037631]` (Number of fractions).

  - **Transformation:** Cast to integer.

**SQL Check:**

```sql
SELECT value_as_number
FROM omop.measurement
WHERE person_id = <your_test_id> AND measurement_concept_id = 4037631;
```
- **Example:** `25` → `25`

## 5. Measurements

**Phenopacket Block:** `measurements` (List)

**OMOP Source Tables:** `measurement`, `observation` & `procedure_occurrence`

**Overview:** This section aggregates various lab results and vital signs. The mapping logic differs depending on whether the source is the `measurement`, `observation` or `procedure_occurrence` table, as defined in the `src/concept_mappings.json` configuration.

### 5.1. assay
- **OMOP Source:**

  - If Source is `observation`: `observation.observation_concept_id` (via filtering_field).

  - If Source is `measurement`: `measurement.measurement_concept_id` (via filtering_field).
  - If Source is `procedure_occurrence`: `procedure_occurrence.modifier_concept_id` or `procedure_occurrence.procedure_concept_id`

- **Logic:**

  - **Grouping:** Each row in the source table creates one `measurement` object.

  - **Filter:** Records are filtered by specific concept IDs (e.g., `[4203711, 43054909...]`) or by ancestor concepts (e.g., descendants of `4326835`).

  - **Transformation:** Map the concept ID to an Ontology Term.

**SQL Check:**

```sql
-- For Observation-based measurements
SELECT observation_concept_id 
FROM omop.observation 
WHERE person_id = <your_test_id> 
  AND observation_concept_id IN (4203711, 43054909, 4151768, 4117444, 3375793);
-- For Measurement-based measurements
SELECT measurement_concept_id 
FROM omop.measurement 
WHERE person_id = <your_test_id> 
  AND measurement_concept_id IN (
    SELECT descendant_concept_id 
    FROM omop.concept_ancestor
    WHERE ancestor_concept_id IN (4326835)
  );
```
- **Example:** `4203711` → `{ "id": "SNOMED:308273005", "label": "Follow-up status" }`
- **Example:** `4272032` → `{ "id": "SNOMED:63476009", "label": "Prostate specific antigen measurement" }`

### 5.2. measurement_value (Quantity)
- **OMOP Source:**

  - If Source is observation: `observation.value_as_number`.

  - If Source is measurement: `measurement.value_as_number`.

- **Logic:**

  - Used if the record has a numerical value.

  - Value: Direct copy of the number.

  - Unit: Mapped from `unit_concept_id`. Defaults to "No value"/Unknown (concept 4129922) if missing.

**SQL Check:**

```sql
SELECT value_as_number, unit_concept_id 
FROM omop.measurement 
WHERE person_id = <your_test_id>;
```
- **Example:** `8.5`, `4122379` → `{ "value": 8.5, "unit": { "id": "SNOMED:258673006", "label": "mm" } }`

### 5.3. measurement_value (Ontology)
- **OMOP Source:**

  - If Source is `observation`: `observation.value_as_concept_id`.
  - If Source is `measurement`: `measurement.value_as_concept_id`.
  - If Source is `procedure_occurrence` one of: `procedure_occurrence.procedure_concept_id`, `procedure_occurrence.modifier_concept_id`.

- **Logic:**

  - Used if the record has a concept value (categorical).

  - **Transformation:** Map `value_as_concept_id` to Ontology Term.

**SQL Check:**

```sql
SELECT value_as_concept_id 
FROM omop.observation 
WHERE person_id = <your_test_id>;
```
- **Example:** `36309453` → ` {"id": "LOINC:LA28369-9", "label": "Partial response"}`

### 5.4. time_observed
- **OMOP Source:**

  - If Source is `observation`: `observation.observation_date`.

  - If Source is `measurement`: `measurement.measurement_date`.

- **Logic:** Convert date to timestamp object.

**SQL Check:**

```sql
SELECT measurement_date 
FROM omop.measurement 
WHERE person_id = <your_test_id>;
```
- **Example:** `2021-11-15` → `{ "timestamp": "2021-11-15" }`

---

## 6. MetaData
**Phenopacket Block:** `metaData`
**Source:** Static Configuration & System Time

### 6.1. created
**Source:** System Time

- **Logic:** Current timestamp in UTC ISO8601 format.

- **Example:** "2023-10-27T10:00:00+00:00"

### 6.2. created_by
**Source:** Static

- **Logic:** Hardcoded string.

- **Example:** "DHDP"

### 6.3. submitted_by
**Source:** Static

- **Logic:** Hardcoded string.

- **Example:** "DHDP"

### 6.4. phenopacket_schema_version
**Source: Static**

- **Logic:** Hardcoded string.

- **Example:** "2.0.0"

### 6.5. resources
**Source:** Static Configuration (get_meta_data function)

- **Logic:** List of ontology definitions used in the phenopacket (SNOMED, ICD10, LOINC, etc.), including version, URL, and namespace prefix.

- **Example:**

```json
"resources": [
            {
                "id": "SNOMED",
                "name": "Systemized Nomenclature of Medicine",
                "namespace_prefix": "SNOMED",
                "url": "https://bioportal.bioontology.org/ontologies/SNOMEDCT",
                "version": "2025-02-01 SNOMED CT International Edition; 2025-03-01 SNOMED CT US Edition; 2025-04-09 SNOMED CT UK Edition",
                "iri_prefix": "http://purl.bioontology.org/ontology/SNOMEDCT/",
            },
            {
                "id": "ICD10",
                "name": "International Statistical Classification of Diseases and Related Health Problems 10th Revision",
                "namespace_prefix": "ICD10",
                "url": "https://bioportal.bioontology.org/ontologies/ICD10",
                "version": "2021 Release",
                "iri_prefix": "http://purl.bioontology.org/ontology/ICD10/",
            },
            {
                "id": "ICD10PCS",
                "name": "International Classification of Diseases, 10th Revision, Procedure Coding System",
                "namespace_prefix": "ICD10PCS",
                "url": "https://bioportal.bioontology.org/ontologies/ICD10PCS",
                "version": "ICD10PCS 2026",
                "iri_prefix": "http://purl.bioontology.org/ontology/ICD10PCS/",
            },
            {
                "id": "ICD9CM",
                "name": "International Classification of Diseases, Ninth Revision, Clinical Modification",
                "namespace_prefix": "ICD9CM",
                "url": "https://bioportal.bioontology.org/ontologies/ICD9CM",
                "version": "ICD9CM v32 master descriptions",
                "iri_prefix": "http://purl.bioontology.org/ontology/ICD9CM/",
            },
            {
                "id": "ICD9Proc",
                "name": "International Classification of Diseases, Ninth Revision, Procedure Codes",
                "namespace_prefix": "Not Applicable",
                "url": "Not Applicable",
                "version": "ICD9CM v32 master descriptions",
                "iri_prefix": "Not Applicable",
            },
            {
                "id": "ICDO3",
                "name": "International Classification of Diseases for Oncology, 3rd Edition",
                "namespace_prefix": "ICDO",
                "url": "http://purl.obolibrary.org/obo/icdo.owl",
                "version": "ICDO3 SEER Site/Histology Released 06/2020",
                "iri_prefix": "http://purl.obolibrary.org/obo/ICDO_",
            },
            {
                "id": "LOINC",
                "name": "Logical Observation Identifiers Names and Codes",
                "namespace_prefix": "LP",
                "url": "https://bioportal.bioontology.org/ontologies/LOINC?p=summary",
                "version": "LOINC 2.80",
                "iri_prefix": "http://purl.bioontology.org/ontology/LNC/LP",
            },
            {
                "id": "NAACCR",
                "name": "North American Association of Central Cancer Registries",
                "namespace_prefix": "NAACCR",
                "url": "https://apps.naaccr.org/data-dictionary/data-dictionary",
                "version": "NAACCR v18",
                "iri_prefix": "https://apps.naaccr.org/data-dictionary/data-dictionary/version=26/data-item-view/item-number=",
            },
            {
                "id": "NCIt",
                "name": "National Cancer Institute Thesaurus",
                "namespace_prefix": "Thesaurus",
                "url": "http://ncicb.nci.nih.gov/xml/owl/EVS/Thesaurus.owl",
                "version": "NCIt 20220509",
                "iri_prefix": "http://ncicb.nci.nih.gov/xml/owl/EVS/Thesaurus.owl#",
            },
            {
                "id": "RxNorm",
                "name": "RxNorm",
                "namespace_prefix": "rxnorm",
                "url": "http://purl.bioontology.org/ontology/RXNORM/",
                "version": "RxNorm 20250602",
                "iri_prefix": "http://purl.bioontology.org/ontology/RXNORM/",
            },
            {
                "id": "UCUM",
                "name": "Unified Code for Units of Measure",
                "namespace_prefix": "Not Applicable",
                "url": "https://ucum.org/ucum",
                "version": "Version 1.8.2",
                "iri_prefix": "Not Applicable",
            },
        ]
```
