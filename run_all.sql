:ON ERROR EXIT

PRINT '01/09 - Creating raw schema';
:r ./schema/01_create_tables.sql

PRINT '02/09 - Loading patients and doctors';
:r ./data/02_insert_patients_doctors.sql

PRINT '03/09 - Loading reference dimensions';
:r ./data/03_insert_reference_dimensions.sql

PRINT '04/09 - Generating 50,000 synthetic visits';
:r ./data/04_generate_visits.sql

PRINT '05/09 - Cleaning and consolidating data';
:r ./cleaning/05_data_cleaning.sql

PRINT '06/09 - Creating analytical indexes';
:r ./schema/06_create_indexes.sql

PRINT '07/09 - Running data-quality checks';
:r ./validation/08_data_quality_checks.sql

PRINT '08/09 - Running business analysis';
:r ./analysis/07_business_analysis.sql

PRINT '09/09 - Benchmarking the indexes';
:r ./analysis/09_index_performance.sql
