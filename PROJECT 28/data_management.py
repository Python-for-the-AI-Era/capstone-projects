# Task 4: CSV Export
late_df = load_data("SELECT * FROM shipments WHERE status = 'late'")

csv = late_df.to_csv(index=False).encode('utf-8')
st.download_button(
    label="Download Late Deliveries Report",
    data=csv,
    file_name='late_deliveries.csv',
    mime='text/csv',
)

# Task 5: Auto-Refresh Logic
if st.button('Manual Refresh'):
    st.cache_data.clear()