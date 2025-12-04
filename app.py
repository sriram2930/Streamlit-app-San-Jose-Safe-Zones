import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
from datetime import datetime, timedelta
# Page configuration
st.set_page_config(
    page_title="San Jose Police Calls Analytics",
    page_icon="🚔",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for professional styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        font-size: 1.2rem;
        color: #666;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-container {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #1f77b4;
    }
    .stMetric {
        background-color: white;
        padding: 1rem;
        border-radius: 0.5rem;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
</style>
""", unsafe_allow_html=True)

# Header
st.markdown('<div class="main-header">🚔 San Jose Police Calls Analytics Dashboard</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Real-time insights for data-driven policing and resource optimization</div>', unsafe_allow_html=True)

# Generate sample data (replace with actual database queries)
@st.cache_data
def generate_sample_data():
    np.random.seed(42)
    dates = pd.date_range(start='2024-01-01', end='2024-11-26', freq='D')
    
    # Monthly trends data
    monthly_data = pd.DataFrame({
        'month': pd.date_range(start='2024-01', end='2024-11', freq='MS'),
        'calls': np.random.randint(2000, 4000, 11),
        'severe_calls': np.random.randint(200, 600, 11)
    })
    monthly_data['running_total'] = monthly_data['calls'].cumsum()
    monthly_data['pct_change'] = monthly_data['calls'].pct_change() * 100
    
    # Call types data
    call_types = ['DISTURBANCE', 'TRAFFIC STOP', 'THEFT', 'ASSAULT', 'BURGLARY', 
                  'WELFARE CHECK', 'SUSPICIOUS PERSON', 'VANDALISM', 'DOMESTIC', 'ALARM']
    call_type_data = pd.DataFrame({
        'call_type': call_types,
        'total_calls': np.random.randint(500, 3000, len(call_types)),
        'avg_priority': np.random.uniform(2.5, 4.5, len(call_types)),
        'severe_count': np.random.randint(50, 500, len(call_types))
    })
    call_type_data = call_type_data.sort_values('total_calls', ascending=False)
    
    # Heat map data (hour x day)
    hours = list(range(24))
    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    heatmap_data = pd.DataFrame({
        'hour': np.repeat(hours, len(days)),
        'day': days * len(hours),
        'calls': np.random.randint(20, 200, len(hours) * len(days))
    })
    
    # Risk locations data
    streets = ['Main St', 'Oak Ave', 'Park Blvd', 'Market St', 'First St',
               'Second St', 'Third St', 'Santa Clara St', 'San Carlos St', 'San Fernando St',
               'Almaden Blvd', 'The Alameda', 'Stevens Creek', 'Winchester Blvd', 'Bascom Ave']
    suffixes = ['', 'N', 'S', 'E', 'W']
    addresses = [f'{np.random.randint(100, 9999)} {street} {suffix}' 
                 for street in streets
                 for suffix in suffixes]
    
    # Ensure we have enough addresses
    num_risk_locations = min(25, len(addresses))
    risk_data = pd.DataFrame({
        'address': np.random.choice(addresses, num_risk_locations, replace=False),
        'risk_score': np.random.uniform(60, 95, num_risk_locations),
        'total_calls': np.random.randint(50, 300, num_risk_locations),
        'severe_calls': np.random.randint(10, 80, num_risk_locations),
        'days_since_last': np.random.randint(0, 14, num_risk_locations)
    })
    risk_data = risk_data.sort_values('risk_score', ascending=False)
    risk_data['risk_category'] = pd.cut(risk_data['risk_score'], 
                                        bins=[0, 70, 80, 90, 100],
                                        labels=['🟢 Lower Risk', '🟡 Moderate Risk', '🟠 High Risk', '🔴 Critical'])
    
    # Response time percentiles
    response_data = pd.DataFrame({
        'call_type': call_types[:8],
        'p50': np.random.randint(5, 15, 8),
        'p75': np.random.randint(10, 25, 8),
        'p90': np.random.randint(15, 40, 8),
        'p95': np.random.randint(20, 60, 8),
        'total_calls': np.random.randint(100, 1000, 8)
    })
    
    # Pareto data
    pareto_data = pd.DataFrame({
        'rank': list(range(1, 51)),
        'address': [f'Location #{i}' for i in range(1, 51)],
        'calls': np.sort(np.random.randint(50, 500, 50))[::-1],
    })
    pareto_data['cumulative_calls'] = pareto_data['calls'].cumsum()
    pareto_data['cumulative_pct'] = (pareto_data['cumulative_calls'] / pareto_data['calls'].sum()) * 100
    
    return monthly_data, call_type_data, heatmap_data, risk_data, response_data, pareto_data

monthly_data, call_type_data, heatmap_data, risk_data, response_data, pareto_data = generate_sample_data()

# Sidebar filters
st.sidebar.header("📊 Dashboard Filters")
date_range = st.sidebar.date_input(
    "Select Date Range",
    value=(datetime(2024, 1, 1), datetime(2024, 11, 26)),
    max_value=datetime(2024, 11, 26)
)
priority_filter = st.sidebar.multiselect(
    "Priority Levels",
    options=[1, 2, 3, 4, 5],
    default=[1, 2, 3, 4, 5]
)
st.sidebar.markdown("---")
st.sidebar.info("💡 *Tip*: Hover over charts for detailed information")

# Key Metrics Row
st.markdown("### 📈 Key Performance Indicators")
col1, col2, col3, col4 = st.columns(4)

with col1:
    total_calls = monthly_data['calls'].sum()
    st.metric("Total Calls", f"{total_calls:,}", delta=f"+{monthly_data['pct_change'].iloc[-1]:.1f}% MoM")

with col2:
    severe_calls = monthly_data['severe_calls'].sum()
    severe_pct = (severe_calls / total_calls) * 100
    st.metric("Severe Incidents", f"{severe_calls:,}", delta=f"{severe_pct:.1f}% of total")

with col3:
    avg_daily = total_calls / len(monthly_data)
    st.metric("Avg Daily Calls", f"{avg_daily:.0f}", delta="📞")

with col4:
    top_risk_locations = len(risk_data[risk_data['risk_score'] > 85])
    st.metric("High-Risk Locations", f"{top_risk_locations}", delta="🔴 Critical")

st.markdown("---")

# Visualization 1: Monthly Trends with Running Total
st.markdown("### 📊 Visualization 1: Call Volume Trends & Running Totals")
col1, col2 = st.columns([2, 1])

with col1:
    fig1 = make_subplots(specs=[[{"secondary_y": True}]])
    
    fig1.add_trace(
        go.Bar(x=monthly_data['month'], y=monthly_data['calls'], 
               name='Monthly Calls', marker_color='lightblue'),
        secondary_y=False
    )
    
    fig1.add_trace(
        go.Scatter(x=monthly_data['month'], y=monthly_data['running_total'],
                   name='Running Total', mode='lines+markers',
                   line=dict(color='darkblue', width=3)),
        secondary_y=True
    )
    
    fig1.update_layout(
        title='Monthly Call Volume with Cumulative Trend',
        hovermode='x unified',
        height=400
    )
    fig1.update_xaxes(title_text="Month")
    fig1.update_yaxes(title_text="Monthly Calls", secondary_y=False)
    fig1.update_yaxes(title_text="Running Total", secondary_y=True)
    
    st.plotly_chart(fig1, use_container_width=True)

with col2:
    st.markdown("#### 📌 Key Insights")
    st.markdown(f"""
    - *Peak Month*: {monthly_data.loc[monthly_data['calls'].idxmax(), 'month'].strftime('%B %Y')}
    - *Total Calls YTD*: {monthly_data['calls'].sum():,}
    - *Avg Growth Rate*: {monthly_data['pct_change'].mean():.1f}% per month
    - *Trend*: {'📈 Increasing' if monthly_data['pct_change'].iloc[-1] > 0 else '📉 Decreasing'}
    """)
    st.info("💡 Running totals help identify long-term capacity needs and seasonal patterns.")

st.markdown("---")

# Visualization 2: Call Type Distribution
st.markdown("### 📊 Visualization 2: Call Type Analysis & Priority Distribution")

fig2 = make_subplots(
    rows=1, cols=2,
    subplot_titles=('Top Call Types by Volume', 'Severe Incidents by Type'),
    specs=[[{"type": "bar"}, {"type": "pie"}]]
)

fig2.add_trace(
    go.Bar(x=call_type_data['total_calls'], y=call_type_data['call_type'],
           orientation='h', marker_color='steelblue',
           text=call_type_data['total_calls'], textposition='auto'),
    row=1, col=1
)

fig2.add_trace(
    go.Pie(labels=call_type_data['call_type'][:5], 
           values=call_type_data['severe_count'][:5],
           hole=0.4, marker_colors=px.colors.sequential.RdBu),
    row=1, col=2
)

fig2.update_layout(height=450, showlegend=True)
fig2.update_xaxes(title_text="Total Calls", row=1, col=1)
st.plotly_chart(fig2, use_container_width=True)

st.markdown("---")

# Visualization 3: Heat Map - Hour x Day Analysis
st.markdown("### 📊 Visualization 3: Call Volume Heat Map (Hour × Day)")

heatmap_pivot = heatmap_data.pivot(index='hour', columns='day', values='calls')
day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
heatmap_pivot = heatmap_pivot[day_order]

fig3 = go.Figure(data=go.Heatmap(
    z=heatmap_pivot.values,
    x=heatmap_pivot.columns,
    y=heatmap_pivot.index,
    colorscale='YlOrRd',
    text=heatmap_pivot.values,
    texttemplate='%{text}',
    textfont={"size": 10},
    colorbar=dict(title="Calls")
))

fig3.update_layout(
    title='Call Distribution by Hour and Day of Week',
    xaxis_title='Day of Week',
    yaxis_title='Hour of Day',
    height=500
)

st.plotly_chart(fig3, use_container_width=True)

col1, col2 = st.columns(2)
with col1:
    st.success("✅ *Peak Hours*: 10 PM - 2 AM on weekends show highest activity")
with col2:
    st.info("💡 *Low Activity*: Tuesday/Wednesday 2 AM - 6 AM ideal for maintenance")

st.markdown("---")

# Visualization 4: High-Risk Location Map
st.markdown("### 📊 Visualization 4: Predictive Risk Analysis - Top 25 Locations")

col1, col2 = st.columns([3, 1])

with col1:
    fig4 = go.Figure()
    
    colors = {'🔴 Critical': 'red', '🟠 High Risk': 'orange', 
              '🟡 Moderate Risk': 'yellow', '🟢 Lower Risk': 'green'}
    
    for category in risk_data['risk_category'].unique():
        data = risk_data[risk_data['risk_category'] == category]
        fig4.add_trace(go.Scatter(
            x=data.index,
            y=data['risk_score'],
            mode='markers',
            name=category,
            marker=dict(
                size=data['total_calls'] / 5,
                color=colors.get(category, 'blue'),
                line=dict(width=2, color='white')
            ),
            text=data['address'],
            hovertemplate='<b>%{text}</b><br>Risk Score: %{y:.1f}<br>Total Calls: ' +
                         data['total_calls'].astype(str) + '<extra></extra>'
        ))
    
    fig4.update_layout(
        title='Risk Score Distribution (Size = Call Volume)',
        xaxis_title='Location Rank',
        yaxis_title='Risk Score',
        height=400,
        hovermode='closest'
    )
    
    st.plotly_chart(fig4, use_container_width=True)

with col2:
    st.markdown("#### 🎯 Top 5 Risk Locations")
    for idx, row in risk_data.head(5).iterrows():
        st.markdown(f"""
        *{row['address']}*  
        Risk: {row['risk_score']:.1f} {row['risk_category']}  
        Calls: {row['total_calls']} | Severe: {row['severe_calls']}
        """)
        st.markdown("---")

st.markdown("---")

# Visualization 5: Response Time Percentiles
st.markdown("### 📊 Visualization 5: Response Time Analysis (Percentiles by Call Type)")

fig5 = go.Figure()

fig5.add_trace(go.Box(
    x=response_data['call_type'],
    q1=response_data['p50'],
    median=response_data['p75'],
    q3=response_data['p90'],
    lowerfence=response_data['p50'] * 0.5,
    upperfence=response_data['p95'],
    name='Response Time Distribution',
    marker_color='indianred'
))

fig5.add_hline(y=10, line_dash="dash", line_color="red", 
               annotation_text="SLA Target (10 min)")

fig5.update_layout(
    title='Response Time Percentiles by Call Type (P50, P75, P90, P95)',
    xaxis_title='Call Type',
    yaxis_title='Response Time (minutes)',
    height=450
)

st.plotly_chart(fig5, use_container_width=True)

st.warning("⚠ Call types exceeding the 10-minute SLA target (red line) need process improvement")

st.markdown("---")

# Visualization 6: Pareto Analysis
st.markdown("### 📊 Visualization 6: Pareto Analysis - Location Concentration")

fig6 = make_subplots(specs=[[{"secondary_y": True}]])

fig6.add_trace(
    go.Bar(x=pareto_data['rank'][:30], y=pareto_data['calls'][:30],
           name='Calls per Location', marker_color='skyblue'),
    secondary_y=False
)

fig6.add_trace(
    go.Scatter(x=pareto_data['rank'][:30], y=pareto_data['cumulative_pct'][:30],
               name='Cumulative %', mode='lines+markers',
               line=dict(color='red', width=3),
               marker=dict(size=8)),
    secondary_y=True
)

fig6.add_hline(y=80, line_dash="dash", line_color="green",
               annotation_text="80% Threshold", secondary_y=True)

fig6.update_layout(
    title='80/20 Rule: Do Top 20% of Locations Generate 80% of Calls?',
    hovermode='x unified',
    height=450
)
fig6.update_xaxes(title_text="Location Rank")
fig6.update_yaxes(title_text="Number of Calls", secondary_y=False)
fig6.update_yaxes(title_text="Cumulative Percentage", secondary_y=True)

st.plotly_chart(fig6, use_container_width=True)

# Calculate 80/20 metrics
locations_for_80pct = pareto_data[pareto_data['cumulative_pct'] <= 80].shape[0]
pct_locations_for_80pct = (locations_for_80pct / len(pareto_data)) * 100

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Locations for 80% of Calls", f"{locations_for_80pct}", 
              delta=f"{pct_locations_for_80pct:.1f}% of total locations")
with col2:
    st.metric("Pareto Efficiency", f"{100 - pct_locations_for_80pct:.1f}%",
              delta="Focus area reduction")
with col3:
    st.success("✅ Validates 80/20 rule - focus on top locations for maximum impact")

st.markdown("---")

# Visualization 7: Incident Chain Analysis
st.markdown("### 📊 Visualization 7: Incident Chains - Escalating Situations")

# Generate sample incident chain data
chain_data = pd.DataFrame({
    'address': risk_data['address'][:10],
    'incidents_24h': np.random.randint(3, 8, 10),
    'chain_length': np.random.randint(2, 5, 10),
    'highest_priority': np.random.randint(1, 3, 10)
})

fig7 = go.Figure()

fig7.add_trace(go.Scatter(
    x=chain_data['incidents_24h'],
    y=chain_data['chain_length'],
    mode='markers+text',
    marker=dict(
        size=chain_data['highest_priority'] * 20,
        color=chain_data['highest_priority'],
        colorscale='Reds',
        showscale=True,
        colorbar=dict(title="Priority"),
        line=dict(width=2, color='white')
    ),
    text=chain_data['address'].str[:15] + '...',
    textposition='top center',
    hovertemplate='<b>%{text}</b><br>24h Incidents: %{x}<br>Chain Length: %{y}<extra></extra>'
))

fig7.update_layout(
    title='Incident Chains: Locations with Cascading Problems (24-hour windows)',
    xaxis_title='Incidents in 24 Hours',
    yaxis_title='Chain Length (sequential incidents)',
    height=450
)

st.plotly_chart(fig7, use_container_width=True)

st.error("🚨 *Action Required*: Locations with 5+ incidents in 24 hours need immediate intervention")

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666; padding: 2rem;'>
    <p><strong>San Jose Police Department - Analytics Dashboard</strong></p>
    <p>Data-driven insights for proactive policing and community safety</p>
    <p style='font-size: 0.8rem;'>Last Updated: November 26, 2024 | Refresh rate: Real-time</p>
</div>
""", unsafe_allow_html=True)
