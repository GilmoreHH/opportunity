import streamlit as st
from simple_salesforce import Salesforce
import os
from dotenv import load_dotenv
import plotly.express as px
import pandas as pd

# Load environment variables from .env file
load_dotenv()

# Function to connect to Salesforce and execute SOQL query
def connect_to_salesforce_and_run_query(name_filter=None, id_filter=None):
    """Connect to Salesforce and execute SOQL query for opportunities."""
    try:
        # Connect to Salesforce using environment variables
        sf = Salesforce(
            username=os.getenv("SF_USERNAME_PRO"),
            password=os.getenv("SF_PASSWORD_PRO"),
            security_token=os.getenv("SF_SECURITY_TOKEN_PRO"),
        )
        st.success("Salesforce connection successful!")

        # Define the SOQL query with optional filters for Name and Id
        soql_query = """
            SELECT CreatedDate, StageName, Name, Id 
            FROM Opportunity
            WHERE CreatedDate = LAST_N_DAYS:7 
            AND StageName = 'New'
        """
        
        # Apply name filter if provided
        if name_filter:
            soql_query += f" AND Name LIKE '%{name_filter}%'"
        
        # Apply Id filter if provided
        if id_filter:
            soql_query += f" AND Id = '{id_filter}'"
        
        # Execute the SOQL query
        query_results = sf.query_all(soql_query)
        
        # Extract and prepare data for visualization
        records = query_results['records']
        df = pd.DataFrame(records)
        
        # Convert CreatedDate to datetime for better plotting
        df['CreatedDate'] = pd.to_datetime(df['CreatedDate'])
        
        # Return the dataframe, query used, and filter details
        return df, soql_query, name_filter, id_filter
        
    except Exception as e:
        st.error(f"Error while querying Salesforce: {str(e)}")
        return None, None, None, None


# Streamlit UI - Dashboard Layout
st.title("Salesforce Opportunity Query Dashboard")

# Session state for persistent variables
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.df = None
    st.session_state.query = None
    st.session_state.name_filter = None
    st.session_state.id_filter = None
    st.session_state.total_count = 0

# Sidebar for filters and authentication
st.sidebar.header("Authentication & Filter Options")

# Authenticate only once
if not st.session_state.authenticated:
    if st.sidebar.button("Authenticate & Run Query"):
        # Try connecting to Salesforce (authentication check)
        df, query, name_filter, id_filter = connect_to_salesforce_and_run_query()
        if df is not None:
            st.session_state.authenticated = True
            st.session_state.df = df
            st.session_state.query = query
            st.session_state.name_filter = name_filter
            st.session_state.id_filter = id_filter
            st.session_state.total_count = len(df)
            st.sidebar.success("Authentication successful. You can now view and filter the data.")
else:
    st.sidebar.success("Already authenticated. You can view and interact with the data.")

# Main content area
if st.session_state.authenticated:
    # Display the total number of opportunities
    st.subheader("Opportunities Summary")
    st.metric("Total Opportunities (New)", st.session_state.total_count)

    # Display SOQL query used
    st.subheader("SOQL Query")
    st.code(st.session_state.query)

    # Display filters applied in the query
    st.subheader("Filters Applied")
    st.write(f"Name Filter: {st.session_state.name_filter if st.session_state.name_filter else 'None'}")
    st.write(f"Id Filter: {st.session_state.id_filter if st.session_state.id_filter else 'None'}")

    # Sidebar Filter Options for Opportunity Name and ID
    st.sidebar.header("Apply Filters")
    name_filter_input = st.sidebar.text_input("Opportunity Name", value=st.session_state.name_filter if st.session_state.name_filter else "")
    id_filter_input = st.sidebar.text_input("Opportunity ID", value=st.session_state.id_filter if st.session_state.id_filter else "")

    # Update data with the selected filters
    if name_filter_input or id_filter_input:
        df, query, name_filter_input, id_filter_input = connect_to_salesforce_and_run_query(
            name_filter=name_filter_input, id_filter=id_filter_input
        )
        if df is not None:
            st.session_state.df = df
            st.session_state.query = query
            st.session_state.name_filter = name_filter_input
            st.session_state.id_filter = id_filter_input
            st.session_state.total_count = len(df)

    # Visualization Section
    st.subheader("Visualizations")
    
    # Chart Type Selection in Sidebar
    chart_type = st.sidebar.selectbox(
        "Select Chart Type", 
        options=["Bar Chart", "Pie Chart", "Scatter Plot", "Line Chart", "Histogram", "Box Plot"]
    )

    # Display the appropriate chart based on user selection
    if chart_type == "Bar Chart":
        opportunities_per_day = st.session_state.df.groupby(st.session_state.df['CreatedDate'].dt.date).size().reset_index(name='Opportunities')
        fig1 = px.bar(opportunities_per_day, x='CreatedDate', y='Opportunities', title="Opportunities Created Per Day")
        st.plotly_chart(fig1)

    elif chart_type == "Pie Chart":
        fig2 = px.pie(st.session_state.df, names='StageName', title="Opportunity Stage Distribution")
        st.plotly_chart(fig2)

    elif chart_type == "Scatter Plot":
        st.session_state.df['OpportunityId'] = st.session_state.df['Id']  # Using Opportunity ID for scatter plot
        fig3 = px.scatter(st.session_state.df, x='CreatedDate', y='OpportunityId', title="Opportunities Created Over Time")
        st.plotly_chart(fig3)

    elif chart_type == "Line Chart":
        opportunities_per_day = st.session_state.df.groupby(st.session_state.df['CreatedDate'].dt.date).size().reset_index(name='Opportunities')
        fig4 = px.line(opportunities_per_day, x='CreatedDate', y='Opportunities', title="Opportunities Created Over Time (Line Chart)")
        st.plotly_chart(fig4)

    elif chart_type == "Histogram":
        fig5 = px.histogram(st.session_state.df, x='CreatedDate', title="Distribution of Opportunities by Creation Date")
        st.plotly_chart(fig5)

    elif chart_type == "Box Plot":
        fig6 = px.box(st.session_state.df, x='StageName', y='CreatedDate', title="Opportunities by Stage (Box Plot)")
        st.plotly_chart(fig6)

else:
    st.warning("Authenticate first to view data and charts.")
