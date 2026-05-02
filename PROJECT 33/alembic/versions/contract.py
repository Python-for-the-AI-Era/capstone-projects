def upgrade():
    # Phase 3: Finalize the constraint. 
    # Because we backfilled, this check is nearly instantaneous.
    op.alter_column('sensor_readings', 'energy_source_id',
               existing_type=sa.Integer(),
               nullable=False)