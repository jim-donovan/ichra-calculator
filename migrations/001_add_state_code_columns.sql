-- Migration: Add state_code columns and indexes for query performance
-- Date: 2026-01-08
-- Purpose: Eliminate SUBSTRING() calls on hios_plan_id which prevent index usage
--
-- The SUBSTRING(hios_plan_id, 6, 2) pattern is used extensively throughout the codebase
-- to extract the 2-letter state code from the HIOS Plan ID. Adding a stored generated
-- column allows PostgreSQL to use indexes for these lookups.
--
-- IMPORTANT: Run this migration during a maintenance window. The base_rates table
-- has 13.4M rows and index creation will take several minutes.

-- ============================================================================
-- STEP 1: Add state_code column to the large base_rates table (13.4M rows)
-- ============================================================================

-- Add generated column (STORED means it's physically stored, not computed on read)
ALTER TABLE rbis_insurance_plan_base_rates_20251019202724
ADD COLUMN IF NOT EXISTS state_code varchar(2)
GENERATED ALWAYS AS (SUBSTRING(plan_id, 6, 2)) STORED;

-- Create composite index optimized for the slow query pattern:
-- WHERE state_code = X AND rating_area_numeric = Y AND age = '21' AND rate_effective_date = '2026-01-01'
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_rates_state_area_age_date
ON rbis_insurance_plan_base_rates_20251019202724 (state_code, rating_area_numeric, age, rate_effective_date);

-- Additional index for plan lookups by state
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_rates_state_code
ON rbis_insurance_plan_base_rates_20251019202724 (state_code);


-- ============================================================================
-- STEP 2: Add state_code column to the plan table (18K rows)
-- ============================================================================

ALTER TABLE rbis_insurance_plan_20251019202724
ADD COLUMN IF NOT EXISTS state_code varchar(2)
GENERATED ALWAYS AS (SUBSTRING(hios_plan_id, 6, 2)) STORED;

-- Index for filtering plans by state
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_plans_state_code
ON rbis_insurance_plan_20251019202724 (state_code);

-- Composite index for common query pattern: state + market + metal level
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_plans_state_market_metal
ON rbis_insurance_plan_20251019202724 (state_code, market_coverage, level_of_coverage)
WHERE plan_effective_date = '2026-01-01';


-- ============================================================================
-- VERIFICATION QUERIES (run after migration)
-- ============================================================================

-- Verify columns were added:
-- SELECT state_code, plan_id FROM rbis_insurance_plan_base_rates_20251019202724 LIMIT 5;
-- SELECT state_code, hios_plan_id FROM rbis_insurance_plan_20251019202724 LIMIT 5;

-- Verify indexes exist:
-- SELECT indexname FROM pg_indexes WHERE tablename = 'rbis_insurance_plan_base_rates_20251019202724';
-- SELECT indexname FROM pg_indexes WHERE tablename = 'rbis_insurance_plan_20251019202724';

-- Test query performance (should be <100ms now):
-- EXPLAIN ANALYZE
-- SELECT p.level_of_coverage, COUNT(DISTINCT p.hios_plan_id)
-- FROM rbis_insurance_plan_20251019202724 p
-- JOIN rbis_insurance_plan_base_rates_20251019202724 br
--     ON p.hios_plan_id = br.plan_id
--     AND br.age = '21'
--     AND br.rate_effective_date = '2026-01-01'
-- WHERE p.market_coverage = 'Individual'
--   AND p.plan_effective_date = '2026-01-01'
--   AND p.level_of_coverage IN ('Bronze', 'Expanded Bronze', 'Silver', 'Gold')
--   AND p.state_code = 'WI'
--   AND br.rating_area_numeric = 12
-- GROUP BY p.level_of_coverage;
