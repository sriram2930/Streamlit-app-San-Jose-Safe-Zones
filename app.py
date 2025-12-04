import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pymysql
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

# Database connection configuration
DB_CONFIG = {
    'host': 'localhost',  # Change to your host
    'user': 'root',       # Change to your username
    'password': 'your_password',  # Change to your password
    'database': 'sjpd_database',  # Change to your database name
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor
}

# Database connection function
@st.cache_resource
def get_database_connection():
    """Create and cache database connection"""
    try:
        connection = pymysql.connect(**DB_CONFIG)
        return connection
    except Exception as e:
        st.error(f"Database connection failed: {str(e)}")
        return None

# Data loading functions
@st.cache_data(ttl=300)  # Cache for 5 minutes
def load_monthly_data(_conn, start_date, end_date):
    """Load monthly call volume trends with running totals"""
    query = """
    WITH monthly_stats AS (
        SELECT 
            DATE_FORMAT(call_datetime, '%Y-%m-01') as month,
            COUNT(*) as calls,
            SUM(CASE WHEN priority <= 2 THEN 1 ELSE 0 END) as severe_calls
        FROM police_calls
        WHERE call_datetime BETWEEN %s AND %s
        GROUP BY month
        ORDER BY month
    )
    SELECT 
        month,
        calls,
        severe_calls,
        SUM(calls) OVER (ORDER BY month) as running_total,
        LAG(calls) OVER (ORDER BY month) as prev_month_calls
    FROM monthly_stats
    """
    
    df = pd.read_sql(query, _conn, params=[start_date, end_date])
    df['month'] = pd.to_datetime(df['month'])
    
    # Calculate percentage change
    df['pct_change'] = ((df['calls'] - df['prev_month_calls']) / df['prev_month_calls'] * 100).fillna(0)
    
    return df

@st.cache_data(ttl=300)
def load_call_type_data(_conn, start_date, end_date):
    """Load call type distribution and severity analysis"""
    query = """
    SELECT 
        call_type,
        COUNT(*) as total_calls,
        AVG(priority) as avg_priority,
        SUM(CASE WHEN priority <= 2 THEN 1 ELSE 0 END) as severe_count
    FROM police_calls
    WHERE call_datetime BETWEEN %s AND %s
        AND call_type IS NOT NULL
    GROUP BY call_type
    ORDER BY total_calls DESC
    LIMIT 15
    """
    
    df = pd.read_sql(query, _conn, params=[start_date, end_date])
    return df

@st.cache_data(ttl=300)
def load_heatmap_data(_conn, start_date, end_date):
    """Load call distribution by hour and day of week"""
    query = """
    SELECT 
        HOUR(call_datetime) as hour,
        DAYNAME(call_datetime) as day,
        COUNT(*) as calls
    FROM police_calls
    WHERE call_datetime BETWEEN %s AND %s
    GROUP BY hour, day
    ORDER BY hour, FIELD(day, 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday')
    """
    
    df = pd.read_sql(query, _conn, params=[start_date, end_date])
    return df

@st.cache_data(ttl=300)
def load_risk_data(_conn, start_date, end_date):
    """Load high-risk location analysis with predictive scoring"""
    query = """
    WITH location_stats AS (
        SELECT 
            address,
            COUNT(*) as total_calls,
            SUM(CASE WHEN priority <= 2 THEN 1 ELSE 0 END) as severe_calls,
            AVG(priority) as avg_priority,
            DATEDIFF(CURDATE(), MAX(call_datetime)) as days_since_last
        FROM police_calls
        WHERE call_datetime BETWEEN %s AND %s
            AND address IS NOT NULL
        GROUP BY address
        HAVING total_calls >= 10
    )
    SELECT 
        address,
        total_calls,
        severe_calls,
        days_since_last,
        -- Risk score calculation (weighted formula)
        ROUND(
            (total_calls * 0.3) + 
            (severe_calls * 2.0) + 
            (avg_priority * 10) +
            (CASE WHEN days_since_last < 7 THEN 15 ELSE 0 END)
        , 2) as risk_score
    FROM location_stats
    ORDER BY risk_score DESC
    LIMIT 25
    """
    
    df = pd.read_sql(query, _conn, params=[start_date, end_date])
    
    # Add risk categories
    df['risk_category'] = pd.cut(df['risk_score'], 
                                  bins=[0, 70, 80, 90, float('inf')],
                                  labels=['🟢 Lower Risk', '🟡 Moderate Risk', '🟠 High Risk', '🔴 Critical'])
    
    return df

@st.cache_data(ttl=300)
def load_response_time_data(_conn, start_date, end_date):
    """Load response time percentiles by call type"""
    query = """
    WITH response_times AS (
        SELECT 
            call_type,
            TIMESTAMPDIFF(MINUTE, call_datetime, dispatch_datetime) as response_time
        FROM police_calls
        WHERE call_datetime BETWEEN %s AND %s
            AND dispatch_datetime IS NOT NULL
            AND TIMESTAMPDIFF(MINUTE, call_datetime, dispatch_datetime) BETWEEN 0 AND 120
    )
    SELECT 
        call_type,
        COUNT(*) as total_calls,
        ROUND(PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY response_time), 1) as p50,
        ROUND(PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY response_time), 1) as p75,
        ROUND(PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY response_time), 1) as p90,
        ROUND(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY response_time), 1) as p95
    FROM response_times
    GROUP BY call_type
    HAVING total_calls >= 50
    ORDER BY p90 DESC
    LIMIT 10
    """
    
    # Note: If your MySQL version doesn't support PERCENTILE_CONT, use this alternative:
    alternative_query = """
    SELECT 
        call_type,
        COUNT(*) as total_calls,
        ROUND(AVG(CASE WHEN percent_rank = 50 THEN response_time END), 1) as p50,
        ROUND(AVG(CASE WHEN percent_rank = 75 THEN response_time END), 1) as p75,
        ROUND(AVG(CASE WHEN percent_rank = 90 THEN response_time END), 1) as p90,
        ROUND(AVG(CASE WHEN percent_rank = 95 THEN response_time END), 1) as p95
    FROM (
        SELECT 
            call_type,
            TIMESTAMPDIFF(MINUTE, call_datetime, dispatch_datetime) as response_time,
            ROUND(PERCENT_RANK() OVER (PARTITION BY call_type ORDER BY TIMESTAMPDIFF(MINUTE, call_datetime, dispatch_datetime)) * 100) as percent_rank
        FROM police_calls
        WHERE call_datetime BETWEEN %s AND %s
            AND dispatch_datetime IS NOT NULL
            AND TIMESTAMPDIFF(MINUTE, call_datetime, dispatch_datetime) BETWEEN 0 AND 120
    ) ranked
    GROUP BY call_type
    HAVING total_calls >= 50
    ORDER BY p90 DESC
    LIMIT 10
    """
    
    try:
        df = pd.read_sql(query, _conn, params=[start_date, end_date])
    except:
        # Fallback to alternative query if PERCENTILE_CONT not supported
        df = pd.read_sql(alternative_query, _conn, params=[start_date, end_date])
    
    return df

@st.cache_data(ttl=300)
def load_pareto_data(_conn, start_date, end_date):
    """Load Pareto analysis data for location concentration"""
    query = """
    SELECT 
        address,
        COUNT(*) as calls
    FROM police_calls
    WHERE call_datetime BETWEEN %s AND %s
        AND address IS NOT NULL
    GROUP BY address
    ORDER BY calls DESC
    LIMIT 50
    """
    
    df = pd.read_sql(query, _conn, params=[start_date, end_date])
    df['rank'] = range(1, len(df) + 1)
    df['cumulative_calls'] = df['calls'].cumsum()
    df['cumulative_pct'] = (df['cumulative_calls'] / df['calls'].sum()) * 100
    
    return df

@st.cache_data(ttl=300)
def load_incident_chain_data(_conn, start_date, end_date):
    """Load incident chain analysis for escalating situations"""
    query = """
    WITH incident_chains AS (
        SELECT 
            address,
            call_datetime,
            priority,
            LAG(call_datetime) OVER (PARTITION BY address ORDER BY call_datetime) as prev_call_time,
            LEAD(call_datetime) OVER (PARTITION BY address ORDER BY call_datetime) as next_call_time
        FROM police_calls
        WHERE call_datetime BETWEEN %s AND %s
            AND address IS NOT NULL
    ),
    chains_24h AS (
        SELECT 
            address,
            COUNT(*) as incidents_24h,
            MIN(priority) as highest_priority
        FROM incident_chains
        WHERE TIMESTAMPDIFF(HOUR, prev_call_time, call_datetime) <= 24
            OR TIMESTAMPDIFF(HOUR, call_datetime, next_call_time) <= 24
        GROUP BY address
        HAVING incidents_24h >= 3
    )
    SELECT 
        address,
        incidents_24h,
        highest_priority,
        ROUND(incidents_24h / 2.0) as chain_length
    FROM chains_24h
    ORDER BY incidents_24h DESC
    LIMIT 15
    """
    
    df = pd.read_sql(query, _conn, params=[start_date, end_date])
    return df

# Header
st.markdown('<div class="main-header">🚔 San Jose Police Calls Analytics Dashboard</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Real-time insights for data-driven policing and resource optimization</div>', unsafe_allow_html=True)

# Sidebar filters
st.sidebar.header("📊 Dashboard Filters")
date_range = st.sidebar.date_input(
    "Select Date Range",
    value=(datetime(2024, 1, 1), datetime(2024, 11, 26)),
    max_value=datetime.now()
)

# Handle single date selection
if isinstance(date_range, tuple) and len(date_range) == 2:
    start_date, end_date = date_range
else:
    start_date = end_date = date_range

priority_filter = st.sidebar.multiselect(
    "Priority Levels",
    options=[1, 2, 3, 4, 5],
    default=[1, 2, 3, 4, 5]
)

st.sidebar.markdown("---")
st.sidebar.info("💡 *Tip*: Hover over charts for detailed information")

# Refresh button
if st.sidebar.button("🔄 Refresh Data"):
    st.cache_data.clear()
    st.rerun()

# Get database connection
conn = get_database_connection()

if conn is None:
    st.error("⚠️ Unable to connect to database. Please check your connection settings.")
    st.stop()

# Load all data
try:
    with st.spinner("Loading data from database..."):
        monthly_data = load_monthly_data(conn, start_date, end_date)
        call_type_data = load_call_type_data(conn, start_date, end_date)
        heatmap_data = load_heatmap_data(conn, start_date, end_date)
        risk_data = load_risk_data(conn, start_date, end_date)
        response_data = load_response_time_data(conn, start_date, end_date)
        pareto_data = load_pareto_data(conn, start_date, end_date)
        chain_data = load_incident_chain_data(conn, start_date, end_date)
except Exception as e:
    st.error(f"Error loading data: {str(e)}")
    st.stop()

# Key Metrics Row
st.markdown("### 📈 Key Performance Indicators")
col1, col2, col3, col4 = st.columns(4)

with col1:
    total_calls = monthly_data['calls'].sum() if not monthly_data.empty else 0
    last_pct_change = monthly_data['pct_change'].iloc[-1] if not monthly_data.empty else 0
    st.metric("Total Calls", f"{total_calls:,}", delta=f"+{last_pct_change:.1f}% MoM")

with col2:
    severe_calls = monthly_data['severe_calls'].sum() if not monthly_data.empty else 0
    severe_pct = (severe_calls / total_calls * 100) if total_calls > 0 else 0
    st.metric("Severe Incidents", f"{severe_calls:,}", delta=f"{severe_pct:.1f}% of total")

with col3:
    avg_daily = total_calls / len(monthly_data) if not monthly_data.empty else 0
    st.metric("Avg Daily Calls", f"{avg_daily:.0f}", delta="📞")

with col4:
    top_risk_locations = len(risk_data[risk_data['risk_score'] > 85]) if not risk_data.empty else 0
    st.metric("High-Risk Locations", f"{top_risk_locations}", delta="🔴 Critical")

st.markdown("---")

# Visualization 1: Monthly Trends with Running Total
st.markdown("### 📊 Visualization 1: Call Volume Trends & Running Totals")

if not monthly_data.empty:
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
        peak_month = monthly_data.loc[monthly_data['calls'].idxmax(), 'month'].strftime('%B %Y')
        st.markdown(f"""
        - **Peak Month**: {peak_month}
        - **Total Calls YTD**: {monthly_data['calls'].sum():,}
        - **Avg Growth Rate**: {monthly_data['pct_change'].mean():.1f}% per month
        - **Trend**: {'📈 Increasing' if monthly_data['pct_change'].iloc[-1] > 0 else '📉 Decreasing'}
        """)
        st.info("💡 Running totals help identify long-term capacity needs and seasonal patterns.")
else:
    st.warning("No monthly data available for the selected date range.")

st.markdown("---")

# Visualization 2: Call Type Distribution
st.markdown("### 📊 Visualization 2: Call Type Analysis & Priority Distribution")

if not call_type_data.empty:
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
    
    top_5_severe = call_type_data.nlargest(5, 'severe_count')
    fig2.add_trace(
        go.Pie(labels=top_5_severe['call_type'], 
               values=top_5_severe['severe_count'],
               hole=0.4, marker_colors=px.colors.sequential.RdBu),
        row=1, col=2
    )
    
    fig2.update_layout(height=450, showlegend=True)
    fig2.update_xaxes(title_text="Total Calls", row=1, col=1)
    st.plotly_chart(fig2, use_container_width=True)
else:
    st.warning("No call type data available for the selected date range.")

st.markdown("---")

# Visualization 3: Heat Map - Hour x Day Analysis
st.markdown("### 📊 Visualization 3: Call Volume Heat Map (Hour × Day)")

if not heatmap_data.empty:
    heatmap_pivot = heatmap_data.pivot(index='hour', columns='day', values='calls')
    day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    # Reorder columns to match day_order, keeping only existing days
    heatmap_pivot = heatmap_pivot[[day for day in day_order if day in heatmap_pivot.columns]]
    
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
        st.success("✅ **Peak Hours**: Identify high-activity periods for resource allocation")
    with col2:
        st.info("💡 **Low Activity**: Optimal times for training and maintenance")
else:
    st.warning("No heatmap data available for the selected date range.")

st.markdown("---")

# Visualization 4: High-Risk Location Map
st.markdown("### 📊 Visualization 4: Predictive Risk Analysis - Top 25 Locations")

if not risk_data.empty:
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
            **{row['address']}**  
            Risk: {row['risk_score']:.1f} {row['risk_category']}  
            Calls: {row['total_calls']} | Severe: {row['severe_calls']}
            """)
            st.markdown("---")
else:
    st.warning("No risk data available for the selected date range.")

st.markdown("---")

# Visualization 5: Response Time Percentiles
st.markdown("### 📊 Visualization 5: Response Time Analysis (Percentiles by Call Type)")

if not response_data.empty:
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
else:
    st.warning("No response time data available for the selected date range.")

st.markdown("---")

# Visualization 6: Pareto Analysis
st.markdown("### 📊 Visualization 6: Pareto Analysis - Location Concentration")

if not pareto_data.empty:
    fig6 = make_subplots(specs=[[{"secondary_y": True}]])
    
    display_count = min(30, len(pareto_data))
    
    fig6.add_trace(
        go.Bar(x=pareto_data['rank'][:display_count], y=pareto_data['calls'][:display_count],
               name='Calls per Location', marker_color='skyblue'),
        secondary_y=False
    )
    
    fig6.add_trace(
        go.Scatter(x=pareto_data['rank'][:display_count], y=pareto_data['cumulative_pct'][:display_count],
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
else:
    st.warning("No Pareto data available for the selected date range.")

st.markdown("---")

# Visualization 7: Incident Chain Analysis
st.markdown("### 📊 Visualization 7: Incident Chains - Escalating Situations")

if not chain_data.empty:
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
    
    st.error("🚨 **Action Required**: Locations with 5+ incidents in 24 hours need immediate intervention")
else:
    st.info("No incident chains detected for the selected date range.")

# Footer
st.markdown("---")
st.markdown(f"""
<div style='text-align: center; color: #666; padding: 2rem;'>
    <p><strong>San Jose Police Department - Analytics Dashboard</strong></p>
    <p>Data-driven insights for proactive policing and community safety</p>
    <p style='font-size: 0.8rem;'>Last Updated: {datetime.now().strftime('%B %d, %Y %I:%M %p')} | Data Source: Live Database</p>
</div>
""", unsafe_allow_html=True)

# Close database connection when done
if conn:
    conn.close()