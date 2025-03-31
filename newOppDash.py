import streamlit as st
from simple_salesforce import Salesforce
import os
from dotenv import load_dotenv
import plotly.express as px
import pandas as pd
import pytz
from datetime import datetime, timedelta

# Load environment variables from .env file
load_dotenv()

# Set page configuration with icon
st.set_page_config(
    page_title="New Quote Requests Dashboard",
    page_icon="📊",
    layout="wide",  # Use a wide layout for the app
)

# Function to get current time in Eastern timezone
def get_eastern_time_now():
    return datetime.now(pytz.timezone('US/Eastern'))

# Function to convert UTC datetime to Eastern Time
def convert_to_eastern(dt):
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        dt = dt.replace(tzinfo=pytz.UTC)
    return dt.astimezone(pytz.timezone('US/Eastern'))

# Function to get date range for filters in ISO format
def get_date_range_iso(days=1095):
    eastern_now = get_eastern_time_now()
    end_date = eastern_now
    start_date = eastern_now - timedelta(days=days)
    return start_date.date().isoformat(), end_date.date().isoformat()

# Function to calculate date ranges
def get_date_range(period):
    """Return start and end dates for the selected period."""
    today = get_eastern_time_now()
    
    if period == "Week":
        start_of_period = (today - timedelta(days=today.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_period = start_of_period + timedelta(days=6, hours=23, minutes=59, seconds=59)
    elif period == "Month":
        start_of_period = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end_of_period = (start_of_period + timedelta(days=31)).replace(day=1) - timedelta(seconds=1)
    elif period == "Quarter":
        quarter = (today.month - 1) // 3 + 1
        start_of_period = datetime(today.year, 3 * quarter - 2, 1, tzinfo=today.tzinfo)
        if quarter < 4:
            end_of_period = datetime(today.year, 3 * quarter + 1, 1, tzinfo=today.tzinfo) - timedelta(seconds=1)
        else:
            end_of_period = datetime(today.year, 12, 31, 23, 59, 59, tzinfo=today.tzinfo)
    elif period == "7":
        end_of_period = today
        start_of_period = today - timedelta(days=7)
    elif period == "30":
        end_of_period = today
        start_of_period = today - timedelta(days=30)
    elif period == "90":
        end_of_period = today
        start_of_period = today - timedelta(days=90)
    elif period == "1095":  # ~3 years
        end_of_period = today
        start_of_period = today - timedelta(days=1095)
    else:
        if isinstance(period, tuple) and len(period) == 2:  # Custom date range
            start_date, end_date = period
            start_of_period = datetime.combine(start_date, datetime.min.time()).replace(tzinfo=today.tzinfo)
            end_of_period = datetime.combine(end_date, datetime.max.time()).replace(tzinfo=today.tzinfo)
        else:
            raise ValueError("Invalid period selected")
    
    return start_of_period.isoformat(), end_of_period.isoformat(), start_of_period, end_of_period

# Function to connect to Salesforce and execute SOQL query
def connect_to_salesforce_and_run_query(start_date=None, end_date=None):
    """Connect to Salesforce and execute SOQL query for opportunities."""
    try:
        # Connect to Salesforce using environment variables
        sf = Salesforce(
            username=os.getenv("SF_USERNAME_PRO"),
            password=os.getenv("SF_PASSWORD_PRO"),
            security_token=os.getenv("SF_SECURITY_TOKEN_PRO"),
        )
        st.success("Salesforce connection successful!")

        # If no dates provided, use default 1095 days
        if start_date is None or end_date is None:
            start_date, end_date = get_date_range_iso()

        # Define the SOQL query
        soql_query = f"""
            SELECT CreatedDate, New_Business_or_Renewal__c, Name, Id
            FROM Opportunity
            WHERE CreatedDate >= {start_date} AND CreatedDate <= {end_date}
            AND New_Business_or_Renewal__c IN ('Personal Lines - New Business', 'Commercial Lines - New Business')
        """
        
        # Execute the SOQL query
        query_results = sf.query_all(soql_query)
        
        # Extract and prepare data for visualization
        records = query_results['records']
        if not records:
            return pd.DataFrame(), soql_query
            
        df = pd.DataFrame(records)
        
        # Convert CreatedDate to datetime and adjust to Florida time
        df['CreatedDate'] = pd.to_datetime(df['CreatedDate']).dt.tz_convert("US/Eastern")
        # Add Eastern Time version of CreatedDate for filtering
        df['CreatedDateET'] = df['CreatedDate']
        
        # Return the dataframe and query used
        return df, soql_query
        
    except Exception as e:
        st.error(f"Error while querying Salesforce: {str(e)}")
        return pd.DataFrame(), None


# Streamlit UI - Dashboard Layout
st.title("📊 New Quote Requests Dashboard")

# Session state for persistent variables
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.df = pd.DataFrame()
    st.session_state.query = None
    st.session_state.total_count = 0
    st.session_state.selected_period = "Week"
    st.session_state.period_start = None
    st.session_state.period_end = None
    st.session_state.date_filter = "90"  # Default to 90 days

# Sidebar for period selection and authentication
st.sidebar.header("Dashboard Options")

# Date Range Options
date_filter_options = {
    "Week": "Current Week",
    "Month": "Current Month", 
    "Quarter": "Current Quarter",
    "7": "Last 7 Days",
    "30": "Last 30 Days",
    "90": "Last 90 Days",
    "1095": "Last 3 Years",
    "custom": "Custom Range"
}

# Period selection
selected_period = st.sidebar.selectbox(
    "Select Period",
    options=list(date_filter_options.keys()),
    format_func=lambda x: date_filter_options[x],
    index=list(date_filter_options.keys()).index(st.session_state.selected_period 
                                                if st.session_state.selected_period in date_filter_options 
                                                else "Week")
)

# Custom date range if custom is selected
custom_start_date = None
custom_end_date = None
if selected_period == "custom":
    col1, col2 = st.sidebar.columns(2)
    with col1:
        custom_start_date = st.date_input("Start Date", value=datetime.now() - timedelta(days=90))
    with col2:
        custom_end_date = st.date_input("End Date", value=datetime.now())
    
    if custom_start_date > custom_end_date:
        st.sidebar.error("Start date must be before end date")

# Authenticate only once
if not st.session_state.authenticated:
    if st.sidebar.button("Authenticate & Run Query"):
        # Calculate date range for the selected period
        if selected_period == "custom":
            # Use custom date range
            if custom_start_date and custom_end_date and custom_start_date <= custom_end_date:
                period_tuple = (custom_start_date, custom_end_date)
                start_date, end_date, period_start, period_end = get_date_range(period_tuple)
            else:
                st.sidebar.error("Invalid date range")
                start_date, end_date, period_start, period_end = get_date_range("90")  # Default to 90 days
        else:
            start_date, end_date, period_start, period_end = get_date_range(selected_period)
        
        # Try connecting to Salesforce (authentication check)
        df, query = connect_to_salesforce_and_run_query(start_date, end_date)
        if not df.empty:
            st.session_state.authenticated = True
            st.session_state.df = df
            st.session_state.query = query
            st.session_state.total_count = len(df)
            st.session_state.selected_period = selected_period
            st.session_state.period_start = period_start
            st.session_state.period_end = period_end
            st.sidebar.success("Authentication successful. You can now view the data.")
        else:
            st.error("No data found.")
else:
    st.sidebar.success("Already authenticated. You can view and interact with the data.")
    
    # Re-run query if period changes or custom dates change
    if selected_period != st.session_state.selected_period or selected_period == "custom":
        if st.sidebar.button("Update Query"):
            if selected_period == "custom":
                # Use custom date range
                if custom_start_date and custom_end_date and custom_start_date <= custom_end_date:
                    period_tuple = (custom_start_date, custom_end_date)
                    start_date, end_date, period_start, period_end = get_date_range(period_tuple)
                else:
                    st.sidebar.error("Invalid date range")
                    start_date, end_date, period_start, period_end = get_date_range(st.session_state.selected_period)
            else:
                start_date, end_date, period_start, period_end = get_date_range(selected_period)
            
            df, query = connect_to_salesforce_and_run_query(start_date, end_date)
            if not df.empty:
                st.session_state.df = df
                st.session_state.query = query
                st.session_state.total_count = len(df)
                st.session_state.selected_period = selected_period
                st.session_state.period_start = period_start
                st.session_state.period_end = period_end
            else:
                st.error("No data found.")

# Main content area
if st.session_state.authenticated:
    # Display reporting period information
    if st.session_state.period_start and st.session_state.period_end:
        st.subheader("Reporting Period")
        if st.session_state.selected_period == "Month":
            period_display = f"{st.session_state.period_start.strftime('%B %Y')}"
        elif st.session_state.selected_period == "Week":
            period_display = f"Week of {st.session_state.period_start.strftime('%B %d, %Y')} to {st.session_state.period_end.strftime('%B %d, %Y')}"
        elif st.session_state.selected_period == "Quarter":
            quarter_num = (st.session_state.period_start.month - 1) // 3 + 1
            period_display = f"Q{quarter_num} {st.session_state.period_start.year}"
        elif st.session_state.selected_period == "custom":
            period_display = f"{st.session_state.period_start.strftime('%B %d, %Y')} to {st.session_state.period_end.strftime('%B %d, %Y')}"
        else:  # Numerical periods (7, 30, 90, 1095 days)
            period_display = f"{date_filter_options[st.session_state.selected_period]}: {st.session_state.period_start.strftime('%B %d, %Y')} to {st.session_state.period_end.strftime('%B %d, %Y')}"
        
        st.info(f"**Reporting Period: {period_display}**", icon="📅")
    
    # Display the total number of opportunities
    st.subheader("Opportunities Summary")
    st.metric("Total Opportunities (New)", st.session_state.total_count)

    # Visualization Section
    st.subheader("Visualizations")
    
    # Chart Type Selection in Sidebar
    chart_type = st.sidebar.selectbox(
        "Select Chart Type", 
        options=["Bar Chart", "Pie Chart", "Scatter Plot", "Line Chart", "Histogram", "Box Plot"]
    )

    # Use filtered dataframe for visualizations
    filtered_df = st.session_state.df

    # Display the appropriate chart based on user selection
    if chart_type == "Bar Chart":
        opportunities_by_type = filtered_df.groupby(['New_Business_or_Renewal__c', filtered_df['CreatedDate'].dt.date]).size().reset_index(name='Opportunities')
        fig1 = px.bar(opportunities_by_type, x='CreatedDate', y='Opportunities', color='New_Business_or_Renewal__c', title="Opportunities by Type Per Day")
        st.plotly_chart(fig1)

    elif chart_type == "Pie Chart":
        fig2 = px.pie(filtered_df, names='New_Business_or_Renewal__c', title="Opportunity Type Distribution")
        st.plotly_chart(fig2)

    elif chart_type == "Scatter Plot":
        if 'RecordIndex' not in filtered_df.columns:
            filtered_df['RecordIndex'] = range(1, len(filtered_df) + 1)
        
        fig3 = px.scatter(
            filtered_df,
            x='CreatedDate',
            y='RecordIndex',  # Use RecordIndex for y-axis
            color='New_Business_or_Renewal__c',
            title="Opportunities by Type Over Time",
            labels={'RecordIndex': 'Opportunity Index'}
        )
        st.plotly_chart(fig3)

    elif chart_type == "Line Chart":
        opportunities_by_type = filtered_df.groupby(['New_Business_or_Renewal__c', filtered_df['CreatedDate'].dt.date]).size().reset_index(name='Opportunities')
        fig4 = px.line(opportunities_by_type, x='CreatedDate', y='Opportunities', color='New_Business_or_Renewal__c', title="Opportunities by Type Over Time (Line Chart)")
        st.plotly_chart(fig4)

    elif chart_type == "Histogram":
        fig5 = px.histogram(filtered_df, x='CreatedDate', color='New_Business_or_Renewal__c', title="Distribution of Opportunities by Type and Creation Date")
        st.plotly_chart(fig5)

    elif chart_type == "Box Plot":
        fig6 = px.box(filtered_df, x='New_Business_or_Renewal__c', y='CreatedDate', title="Opportunities by Type (Box Plot)")
        st.plotly_chart(fig6)

    # Display SOQL query used (moved below visualizations)
    with st.expander("View SOQL Query", expanded=False):
        st.code(st.session_state.query)

else:
    st.warning("Authenticate first to view data and charts.")
