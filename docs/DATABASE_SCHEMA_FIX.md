# Database Schema Fix

## Problem

The Django models in `src/trading/models.py` don't match the existing database schema created by `sql/init.sql`. This causes database errors when trying to access the trading dashboard.

## Schema Mismatches

### Positions Table
**Database has:**
- `position_type` (VARCHAR) - values: 'LONG', 'SHORT'
- `opened_at` (TIMESTAMPTZ)
- No `status` column initially (we added it)

**Django model expected:**
- `side` → mapped to `position_type` via `db_column`
- `entry_time` → mapped to `opened_at` via property
- `status` → added to database

✅ **FIXED**: Updated Position model with `db_column` mappings and added `status` column

### Trades Table
**Database has:**
- `time` (TIMESTAMPTZ) - trade execution time  
- `trade_type` (VARCHAR) - BUY/SELL
- `position_side` (VARCHAR) - LONG/SHORT/BOTH
- `price` (DECIMAL)
- `fee` (DECIMAL)
- `realized_pnl` (DECIMAL)
- `strategy_name` (VARCHAR)
- No `entry_time`, `exit_time`, `pnl`, `status` columns

**Django model expected:**
- `entry_time` → should map to `time`
- `side` → should map to `trade_type` or `position_side`
- `pnl` → should map to `realized_pnl`
- `fees` → should map to `fee`
- `status`, `exit_time`, `exit_price` → missing in database

### Other Missing Tables
- `strategies` table doesn't exist (only `strategy_parameters` exists)
- `signals` table may not exist
- `backtest_results` table may not exist

## Solution Applied

### 1. Set all models to `managed = False`
This prevents Django from trying to create/modify tables during migrations.

### 2. Updated Position Model
```python
class Position(models.Model):
    # Map Django field names to existing database columns
    side = models.CharField(max_length=10, db_column='position_type')
    
    # Use actual database column names
    opened_at = models.DateTimeField(default=timezone.now)
    
    # Add property for backward compatibility
    @property
    def entry_time(self):
        return self.opened_at
    
    class Meta:
        db_table = 'positions'
        managed = False
```

### 3. Added missing `status` column to positions table
```sql
ALTER TABLE positions ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'open';
```

### 4. Fixed admin.py
Changed references from `entry_time` to `opened_at` in PositionAdmin.

## Next Steps Required

### Update Trade Model
The Trade model needs to be updated to match the actual `trades` table schema:

```python
class Trade(models.Model):
    # Database columns
    time = models.DateTimeField()  # Not entry_time
    trade_type = models.CharField(max_length=10)  # BUY/SELL
    position_side = models.CharField(max_length=10, null=True)  # LONG/SHORT/BOTH
    price = models.DecimalField(max_digits=20, decimal_places=8)
    fee = models.DecimalField(max_digits=20, decimal_places=8, null=True)
    realized_pnl = models.DecimalField(max_digits=20, decimal_places=8, null=True)
    
    # Add properties for compatibility
    @property
    def entry_time(self):
        return self.time
    
    @property
    def pnl(self):
        return self.realized_pnl
    
    @property
    def fees(self):
        return self.fee
    
    class Meta:
        db_table = 'trades'
        managed = False
```

### Create Missing Tables
If strategies, signals, and backtest_results are needed, they should be added to `sql/init.sql` or created manually.

## Status

✅ Position model - FIXED
✅ Database credentials - FIXED  
✅ Web container - RUNNING
⚠️ Trade model - NEEDS UPDATE
⚠️ Missing tables - NEEDS REVIEW

## Testing

After fixing the Trade model, test with:
```bash
curl http://localhost:8000/trading/
```

Should return 200 instead of 500.
