# Task 2: Build the UI
col1, col2, col3 = st.columns(3)
col1.metric("Active Deliveries", 42, "+5%")
col2.metric("Late Deliveries", 12, "-2", delta_color="inverse")
col3.metric("On-Time Rate", "84%", "+2%")

# Task 3: Interactivity
routes = load_data("SELECT DISTINCT route FROM shipments")
selected_route = st.multiselect("Filter by Route", options=routes['route'].tolist())

# Revenue Chart
df_rev = load_data("SELECT route, SUM(revenue) as total FROM shipments GROUP BY route")
fig = px.bar(df_rev, x="route", y="total", title="Revenue by Route")
st.plotly_chart(fig, use_container_width=True)