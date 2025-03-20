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

# Function to calculate date ranges
def get_date_range(period):
    """Return start and end dates for the selected period."""
    today = datetime.now(pytz.timezone("US/Eastern"))
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
    else:
        raise ValueError("Invalid period selected")
    
    return start_of_period.isoformat(), end_of_period.isoformat()

# Function to connect to Salesforce and execute SOQL query
def connect_to_salesforce_and_run_query(start_date, end_date):
    """Connect to Salesforce and execute SOQL query for opportunities."""
    try:
        # Connect to Salesforce using environment variables
        sf = Salesforce(
            username=os.getenv("SF_USERNAME_PRO"),
            password=os.getenv("SF_PASSWORD_PRO"),
            security_token=os.getenv("SF_SECURITY_TOKEN_PRO"),
        )
        st.success("Salesforce connection successful!")

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
        df = pd.DataFrame(records)
        
        # Convert CreatedDate to datetime and adjust to Florida time
        df['CreatedDate'] = pd.to_datetime(df['CreatedDate']).dt.tz_convert("US/Eastern")
        
        # Return the dataframe and query used
        return df, soql_query
        
    except Exception as e:
        st.error(f"Error while querying Salesforce: {str(e)}")
        return None, None


# Streamlit UI - Dashboard Layout
st.title("📊 New Quote Requests Dashboard")

# Session state for persistent variables
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.df = None
    st.session_state.query = None
    st.session_state.total_count = 0
    st.session_state.selected_period = "Week"

# Sidebar for period selection and authentication
st.sidebar.header("Dashboard Options")

# Period selection
selected_period = st.sidebar.selectbox(
    "Select Period",
    options=["Week", "Month", "Quarter"],
    index=["Week", "Month", "Quarter"].index(st.session_state.selected_period)
)

# Authenticate only once
if not st.session_state.authenticated:
    if st.sidebar.button("Authenticate & Run Query"):
        # Calculate date range for the selected period
        start_date, end_date = get_date_range(selected_period)
        # Try connecting to Salesforce (authentication check)
        df, query = connect_to_salesforce_and_run_query(start_date, end_date)
        if df is not None:
            st.session_state.authenticated = True
            st.session_state.df = df
            st.session_state.query = query
            st.session_state.total_count = len(df)
            st.session_state.selected_period = selected_period
            st.sidebar.success("Authentication successful. You can now view the data.")
else:
    # Re-run query if period changes
    if selected_period != st.session_state.selected_period:
        start_date, end_date = get_date_range(selected_period)
        df, query = connect_to_salesforce_and_run_query(start_date, end_date)
        if df is not None:
            st.session_state.df = df
            st.session_state.query = query
            st.session_state.total_count = len(df)
            st.session_state.selected_period = selected_period

# Main content area
if st.session_state.authenticated:
    # Display the total number of opportunities
    st.subheader("Opportunities Summary")
    st.metric("Total Opportunities (New)", st.session_state.total_count)

    # Display SOQL query used
    st.subheader("SOQL Query")
    st.code(st.session_state.query)

    # Visualization Section
    st.subheader("Visualizations")
    
    # Chart Type Selection in Sidebar
    chart_type = st.sidebar.selectbox(
        "Select Chart Type", 
        options=["Bar Chart", "Pie Chart", "Scatter Plot", "Line Chart", "Histogram", "Box Plot"]
    )

    # Display the appropriate chart based on user selection
    if chart_type == "Bar Chart":
        opportunities_by_type = st.session_state.df.groupby(['New_Business_or_Renewal__c', st.session_state.df['CreatedDate'].dt.date]).size().reset_index(name='Opportunities')
        fig1 = px.bar(opportunities_by_type, x='CreatedDate', y='Opportunities', color='New_Business_or_Renewal__c', title="Opportunities by Type Per Day")
        st.plotly_chart(fig1)

    elif chart_type == "Pie Chart":
        fig2 = px.pie(st.session_state.df, names='New_Business_or_Renewal__c', title="Opportunity Type Distribution")
        st.plotly_chart(fig2)

    elif chart_type == "Scatter Plot":
        if 'RecordIndex' not in st.session_state.df.columns:
            st.session_state.df['RecordIndex'] = range(1, len(st.session_state.df) + 1)
        
        fig3 = px.scatter(
            st.session_state.df,
            x='CreatedDate',
            y='RecordIndex',  # Use RecordIndex for y-axis
            color='New_Business_or_Renewal__c',
            title="Opportunities by Type Over Time",
            labels={'RecordIndex': 'Opportunity Index'}
        )
        st.plotly_chart(fig3)


    elif chart_type == "Line Chart":
        opportunities_by_type = st.session_state.df.groupby(['New_Business_or_Renewal__c', st.session_state.df['CreatedDate'].dt.date]).size().reset_index(name='Opportunities')
        fig4 = px.line(opportunities_by_type, x='CreatedDate', y='Opportunities', color='New_Business_or_Renewal__c', title="Opportunities by Type Over Time (Line Chart)")
        st.plotly_chart(fig4)

    elif chart_type == "Histogram":
        fig5 = px.histogram(st.session_state.df, x='CreatedDate', color='New_Business_or_Renewal__c', title="Distribution of Opportunities by Type and Creation Date")
        st.plotly_chart(fig5)

    elif chart_type == "Box Plot":
        fig6 = px.box(st.session_state.df, x='New_Business_or_Renewal__c', y='CreatedDate', title="Opportunities by Type (Box Plot)")
        st.plotly_chart(fig6)

else:
    st.warning("Authenticate first to view data and charts.")
