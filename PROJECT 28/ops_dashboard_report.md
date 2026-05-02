# Haul247 Self-Service Dashboard: Deployment Specs

## 1. User Guide
- **Login:** Access is restricted via the team passcode.
- **Filters:** Use the sidebar to filter by date or driver.
- **Exports:** Click the 'Download' button to get a CSV of filtered data for Excel reporting.

## 2. Technical Architecture
- **Engine:** Streamlit + SQLAlchemy.
- **Caching:** Data is cached for 5 minutes. If you need the absolute latest data, click 'Manual Refresh'.
- **Mobile-Responsive:** The dashboard layout automatically adjusts for viewing on phones (for field ops).

## 3. Key Metrics Tracked
- **Late Deliveries:** Calculated as `expected_arrival_time < current_time` for items not yet delivered.
- **Revenue by Route:** Visualized to help optimize fuel and driver allocation.

## 4. Scalability (Stretch Goal)
The dashboard uses **Connection Pooling** to ensure that multiple simultaneous users don't overwhelm the PostgreSQL instance.