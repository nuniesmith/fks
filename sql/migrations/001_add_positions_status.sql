-- Migration: Add status column to positions table
-- Date: 2025-10-16
-- Description: Adds missing 'status' column to positions table to track position lifecycle

-- Add status column to positions table
ALTER TABLE positions 
ADD COLUMN IF NOT EXISTS status VARCHAR(20) 
CHECK (status IN ('open', 'closed', 'liquidated')) 
DEFAULT 'open';

-- Create index for faster status queries
CREATE INDEX IF NOT EXISTS idx_positions_status ON positions(status);

-- Backfill existing positions with 'open' status (if any exist)
UPDATE positions SET status = 'open' WHERE status IS NULL;

-- Add comment to document the column
COMMENT ON COLUMN positions.status IS 'Position lifecycle status: open, closed, or liquidated';
