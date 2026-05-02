import logging
from sqlalchemy import event

# Configure logging to show the disaster in the console
logging.basicConfig()
logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)

def start_query_counter(engine):
    count = 0
    @event.listens_for(engine.sync_engine, "before_cursor_execute")
    def receive_before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        nonlocal count
        count += 1
        print(f"--- [QUERY {count}] ---")
    return lambda: count