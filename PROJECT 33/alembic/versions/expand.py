def upgrade():
    # Phase 1: Add the column as NULLABLE. No lock on existing data.
    op.add_column('sensor_readings', 
        sa.Column('energy_source_id', sa.Integer(), nullable=True)
    )