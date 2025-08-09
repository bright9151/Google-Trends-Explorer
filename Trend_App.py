# IMPORTS
import time  # To add delays for rate limiting and pauses
import streamlit as st  # Streamlit for web app UI components
import plotly.express as px  # Plotly Express for interactive charts
from pytrends.request import TrendReq  # Pytrends to fetch Google Trends data
import pandas as pd  # Pandas for data manipulation
import pycountry  # To map country names to country codes
from PIL import Image  # To load and display images
import os  # For file and path operations

# PAGE CONFIGURATION
st.set_page_config(
    page_title="Google Trends Explorer",  # Title shown on browser tab
    page_icon="Trends.png",  # Favicon icon for the app
    layout="wide"  # Use wide layout for more horizontal space
)

# SESSION STATE FOR SIDEBAR
if "show_custom_sidebar" not in st.session_state:  # Check if sidebar visibility flag is not set
    st.session_state.show_custom_sidebar = True  # Default sidebar to visible

# HEADER AREA
header_cols = st.columns([0.5, 9, 0.7])  # Create 3 columns for header with custom width ratios

with header_cols[0]:
    if st.button("☰", key="hamburger"):  # Hamburger menu button to toggle sidebar
        st.session_state.show_custom_sidebar = not st.session_state.show_custom_sidebar  # Toggle sidebar visibility flag

with header_cols[1]:
    logo_path = os.path.join("assets", "logo.png")  # Define logo image path
    if os.path.exists(logo_path):  # Check if logo file exists
        logo_img = Image.open(logo_path)  # Open logo image file
        st.image(logo_img, width=40, use_column_width=False)  # Display logo image with fixed width
        # Display app title with inline HTML styling for vertical alignment
        st.markdown("### <span style='vertical-align:middle'>Google Trends Explorer</span>", unsafe_allow_html=True)
    else:
        st.markdown("## 🌍 Google Trends Explorer")  # Fallback title if logo is missing

with header_cols[2]:
    # Display right-aligned navigation links using HTML inside markdown
    st.markdown(
        """
        <div style="text-align: right;">
            <a href='#'>About</a> &nbsp;|&nbsp;
            <a href='#'>Docs</a> &nbsp;|&nbsp;
            <a href='#'>Contact</a>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.write("---")  # Horizontal rule separator

# HELPER FUNCTION: COUNTRY CODE
def get_country_code(user_input):
    if not user_input:  # Return empty string if no input
        return ""
    user_input = user_input.strip()  # Trim whitespace
    if len(user_input) == 2 and user_input.isalpha():  # If 2-letter alpha code, assume it's country code
        return user_input.upper()  # Return uppercase country code
    try:
        country = pycountry.countries.lookup(user_input)  # Lookup country by name or code using pycountry
        return country.alpha_2  # Return 2-letter ISO country code
    except Exception:  # If lookup fails, return empty string
        return ""

# MAIN CLASS: GoogleTrendsExplorer
class GoogleTrendsExplorer:
    def __init__(self):
        # Initialize Pytrends request object with locale, timezone, retry config, and backoff factor
        self.pytrends = TrendReq(hl='en-US', tz=360, retries=2, backoff_factor=0.3)
        self.keywords = []  # List to store user keywords
        self.timeframe = "today 1-m"  # Default timeframe
        self.geo = ""  # Default geographic filter (empty = worldwide)

    def set_user_input(self, sidebar_col=None):
        # Use provided container (sidebar) or main Streamlit context
        target = sidebar_col if sidebar_col is not None else st
        # Text input for comma-separated keywords, strip whitespace
        keyword_str = target.text_input("Enter keywords (comma separated):", value="").strip()
        if keyword_str:  # If input not empty
            # Split keywords by comma and strip each keyword
            self.keywords = [k.strip() for k in keyword_str.split(",") if k.strip()]

        # Dropdown selectbox for timeframe options with default index 3 ("today 1-m")
        self.timeframe = target.selectbox(
            "Select timeframe:",
            options=[
                "now 1-H", "now 4-H", "now 1-d", "today 1-m",
                "today 3-m", "today 12-m", "today 5-y", "all"
            ],
            index=3
        )

        # Text input for country code or full country name, default empty (worldwide)
        country_input = target.text_input(
            "Enter country code or full country name (leave empty for worldwide):",
            value=""
        ).strip()
        self.geo = get_country_code(country_input)  # Convert input to 2-letter country code or empty string

    def fetch_interest_over_time_df(self):
        if not self.keywords:  # Return empty DataFrame if no keywords provided
            return pd.DataFrame()
        # Build the Pytrends payload with current keywords, timeframe, and geo filter
        self.pytrends.build_payload(self.keywords, timeframe=self.timeframe, geo=self.geo)
        df = self.pytrends.interest_over_time()  # Fetch interest over time data as DataFrame
        if "isPartial" in df.columns:  # Remove 'isPartial' column if it exists (indicates incomplete data)
            df = df.drop(columns=["isPartial"])
        return df  # Return cleaned DataFrame

    def get_interest_by_region(self):
        if not self.keywords:  # Return empty DataFrame if no keywords
            return pd.DataFrame()
        # Build payload again for interest by region query
        self.pytrends.build_payload(self.keywords, timeframe=self.timeframe, geo=self.geo)
        df = self.pytrends.interest_by_region()  # Fetch interest by region data as DataFrame
        return df

    def show_interest_map(self, df_region):
        if df_region.empty:  # Return None if DataFrame is empty (no data)
            return None

        df_region = df_region.reset_index()  # Reset index to make region names a column
        if len(df_region.columns) > 2:  # If more than two columns (multiple keywords)
            first_keyword_col = df_region.columns[1]  # Take second column as first keyword interest
            # Keep only region names and first keyword interest columns
            df_region = df_region[['geoName', first_keyword_col]]
            df_region.columns = ['Country', 'Interest']  # Rename columns to standardized names
        else:
            df_region.columns = ['Country', 'Interest']  # Rename columns if only two present

        # Create a choropleth map figure showing interest by country
        fig = px.choropleth(
            df_region,
            locations="Country",  # Use country names for location
            locationmode="country names",  # Interpret locations as country names
            color="Interest",  # Color intensity based on interest value
            hover_name="Country",  # Tooltip shows country name
            color_continuous_scale=px.colors.sequential.Blues,  # Blue color scale
            title="Interest by Country"  # Map title
        )
        return fig  # Return the Plotly figure

    def plot_interest_over_time(self, df):
        if df.empty:  # Return None if DataFrame empty
            return None
        # Create a line plot for interest over time with markers
        fig = px.line(
            df,
            x=df.index,  # X-axis is the DataFrame index (date/time)
            y=df.columns,  # Y-axis is all keyword columns
            title="Interest Over Time",  # Chart title
            labels={"value": "Interest", "index": "Date"},  # Axis labels
            markers=True  # Show markers on data points
        )
        # Update trace to show lines + markers and customize hover text
        fig.update_traces(mode="lines+markers", hovertemplate="Date: %{x}<br>Interest: %{y}")
        return fig  # Return Plotly figure

    def plot_top_regions(self, df, keyword_colname):
        if df.empty:  # Return None if empty DataFrame
            return None
        # Create a bar chart showing interest by region for one keyword
        fig = px.bar(
            df,
            x=df.index,  # X-axis is region names (index)
            y=keyword_colname,  # Y-axis is interest values for specified keyword column
            title=f"Top Regions for '{keyword_colname.replace('_interest','')}'",  # Chart title with keyword cleaned
            labels={"value": "Interest", "index": "Region"}  # Axis labels
        )
        fig.update_traces(hovertemplate="%{x}: %{y}")  # Customize hover tooltip format
        return fig  # Return Plotly bar chart figure

    def get_related_queries_df(self):
        try:
            time.sleep(1)  # Delay 1 second before fetching related queries to respect rate limits
            related = self.pytrends.related_queries()  # Get related queries dictionary
            if not self.keywords:  # Return None if no keywords set
                return None
            # Get the 'top' related queries DataFrame for the first keyword
            top = related.get(self.keywords[0], {}).get("top", None)
            if top is not None and not top.empty:  # If top related queries exist and not empty
                return top.head(10)  # Return top 10 related queries
        except Exception:  # On any error, return None
            return None

# APP LAYOUT
app = GoogleTrendsExplorer()  # Instantiate the main app class

# If sidebar is visible
if st.session_state.show_custom_sidebar:
    left_col, main_col = st.columns([3, 9])  # Split page into sidebar and main content columns

    with left_col:
        st.header("Filters")  # Sidebar header
        app.set_user_input(sidebar_col=left_col)  # Show keyword, timeframe, and country inputs in sidebar

        st.subheader("Regional Filters")  # Subheader for additional region filters
        top_n = left_col.slider("Top N regions", min_value=5, max_value=50, value=10, step=1)  # Slider to select how many top regions to show
        min_interest = left_col.slider("Minimum interest", min_value=0, max_value=100, value=0, step=1)  # Slider for minimum interest threshold

    with main_col:
        st.header("Results")  # Results section header
        if st.button("Analyze") and app.keywords:  # Analyze button triggers data fetch if keywords exist
            try:
                # Build payload with user inputs
                app.pytrends.build_payload(app.keywords, timeframe=app.timeframe, geo=app.geo)
                time.sleep(1)  # Pause for rate limiting

                interest_df = app.fetch_interest_over_time_df()  # Fetch interest over time data

                if interest_df.empty:
                    st.error("❌ No trend data found for these keywords.")  # Show error if no data
                else:
                    # Create 2x2 grid layout for results
                    row1_col1, row1_col2 = st.columns(2)  # Top row columns
                    row2_col1, row2_col2 = st.columns(2)  # Bottom row columns

                    # Top-left: Interest over time chart
                    with row1_col1:
                        time_fig = app.plot_interest_over_time(interest_df)  # Generate line chart
                        if time_fig:
                            st.plotly_chart(time_fig, use_container_width=True)  # Display chart responsively
                            # Prepare CSV download for interest over time data
                            csv = interest_df.reset_index().to_csv(index=False).encode("utf-8")
                            st.download_button("📥 Download Time Data", data=csv,
                                               file_name="interest_over_time.csv",
                                               mime="text/csv")

                    # Top-right: Interest by region map
                    with row1_col2:
                        region_df = app.get_interest_by_region()  # Fetch interest by region
                        if not region_df.empty:
                            map_fig = app.show_interest_map(region_df)  # Generate choropleth map
                            if map_fig:
                                st.plotly_chart(map_fig, use_container_width=True)  # Show map chart

                    # Bottom-left: Top regions bar chart (for first keyword)
                    with row2_col1:
                        if not region_df.empty and app.keywords:
                            first_keyword = app.keywords[0]  # First keyword to filter on
                            if first_keyword in region_df.columns:
                                # Filter regions above minimum interest and get top N regions
                                fr = region_df[region_df[first_keyword] >= min_interest].sort_values(
                                    by=first_keyword, ascending=False).head(top_n)
                                if not fr.empty:
                                    # Rename column for plotting
                                    fr = fr.rename(columns={first_keyword: f"{first_keyword}_interest"})
                                    bar_fig = app.plot_top_regions(fr, f"{first_keyword}_interest")  # Generate bar chart
                                    if bar_fig:
                                        st.plotly_chart(bar_fig, use_container_width=True)  # Display bar chart

                    # Bottom-right: Related queries table
                    with row2_col2:
                        st.subheader("🔗 Top Related Queries")  # Section title
                        related_df = app.get_related_queries_df()  # Fetch related queries data
                        if related_df is not None:
                            st.dataframe(related_df)  # Show as interactive table
                        else:
                            st.info("No related queries found.")  # Inform user if none found

            except Exception as e:
                st.error(f"Something went wrong: {e}")  # Show error message on failure

# If sidebar is hidden 
else:
    st.header("Results (sidebar hidden)")  # Header when sidebar is hidden
    with st.expander("Show Filters"):  # Expandable filters section
        app.set_user_input(sidebar_col=st)  # Show filters inline in main area
        top_n = st.slider("Top N regions", min_value=5, max_value=50, value=10, step=1)  # Slider for top regions
        min_interest = st.slider("Minimum interest", min_value=0, max_value=100, value=0, step=1)  # Slider for min interest

    if st.button("Analyze") and app.keywords:  # Analyze button with keywords check
        try:
            app.pytrends.build_payload(app.keywords, timeframe=app.timeframe, geo=app.geo)  # Build query
            time.sleep(1)  # Wait to avoid rate limiting

            interest_df = app.fetch_interest_over_time_df()  # Fetch interest over time

            if interest_df.empty:
                st.error("❌ No trend data found for these keywords.")  # Error if empty
            else:
                # 2x2 grid for results
                row1_col1, row1_col2 = st.columns(2)
                row2_col1, row2_col2 = st.columns(2)

                # Top-left: interest over time line chart
                with row1_col1:
                    time_fig = app.plot_interest_over_time(interest_df)
                    if time_fig:
                        st.plotly_chart(time_fig, use_container_width=True)
                        csv = interest_df.reset_index().to_csv(index=False).encode("utf-8")
                        st.download_button("📥 Download Time Data", data=csv,
                                          file_name="interest_over_time.csv",
                                          mime="text/csv")

                # Top-right: interest by region map
                with row1_col2:
                    region_df = app.get_interest_by_region()
                    if not region_df.empty:
                        map_fig = app.show_interest_map(region_df)
                        if map_fig:
                            st.plotly_chart(map_fig, use_container_width=True)

                # Bottom-left: top regions bar chart for first keyword
                with row2_col1:
                    if not region_df.empty and app.keywords:
                        first_keyword = app.keywords[0]
                        if first_keyword in region_df.columns:
                            fr = region_df[region_df[first_keyword] >= min_interest].sort_values(
                                by=first_keyword, ascending=False).head(top_n)
                            if not fr.empty:
                                fr = fr.rename(columns={first_keyword: f"{first_keyword}_interest"})
                                bar_fig = app.plot_top_regions(fr, f"{first_keyword}_interest")
                                if bar_fig:
                                    st.plotly_chart(bar_fig, use_container_width=True)

                # Bottom-right: related queries table
                with row2_col2:
                    st.subheader("🔗 Top Related Queries")
                    related_df = app.get_related_queries_df()
                    if related_df is not None:
                        st.dataframe(related_df)
                    else:
                        st.info("No related queries found.")

        except Exception as e:
            st.error(f"Something went wrong: {e}")  # Show error on exceptions
