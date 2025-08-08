# Import Required Libraries
import time  # Used to delay requests and avoid rate-limiting
import streamlit as st  # Streamlit for web UI
import plotly.express as px  # For interactive plots
from pytrends.request import TrendReq  # For accessing Google Trends data
import pandas as pd  # For working with data
import pycountry  # For country name to code conversion

# Set Title
st.set_page_config(
    page_title="Google Trends Explorer",
    page_icon="🌍",
    layout="wide"
)
# Helper Function - Country Code
def get_country_code(user_input):
    """Convert a country name or code to ISO Alpha-2 format."""
    if not user_input:
        return ""
    user_input = user_input.strip()

    # If already a valid 2-letter code
    if len(user_input) == 2 and user_input.isalpha():
        return user_input.upper()

    # Try matching full country name
    try:
        country = pycountry.countries.lookup(user_input)
        return country.alpha_2
    except LookupError:
        return ""  # Invalid input

# Google Trends App Class
class GoogleTrendsExplorer:
    def __init__(self):
        """Initialize the Google Trends connection and default settings."""
        self.pytrends = TrendReq(hl='en-US', tz=360, retries=2, backoff_factor=0.3)
        self.keywords = []  # List of keywords from user
        self.timeframe = "today 1-m"  # Default time frame
        self.geo = ""  # Country/region code

    def set_user_input(self):
        """Collect keywords, timeframe, and optional country/region from user."""
        # Keyword input
        keyword_str = st.text_input("Enter keywords (comma separated):", value="")
        if keyword_str:
            self.keywords = [k.strip() for k in keyword_str.split(",") if k.strip()]

        # Timeframe selection
        self.timeframe = st.selectbox(
            "Select timeframe:",
            options=[
                "now 1-H", "now 4-H", "now 1-d", "today 1-m",
                "today 3-m", "today 12-m", "today 5-y", "all"
            ],
            index=3
        )

        # Country or region input
        country_input = st.text_input(
            "Enter country code or full country name (leave empty for worldwide):",
            value=""
        ).strip()

        # Convert to ISO Alpha-2 code
        self.geo = get_country_code(country_input)

    def fetch_trend_data(self):
        """Fetch and display Google Trends data based on user input."""
        if st.button("Analyze") and self.keywords:
            try:
                # Build API request
                self.pytrends.build_payload(self.keywords, timeframe=self.timeframe, geo=self.geo)
                time.sleep(2)  # Prevent hitting rate limits

                # Fetch interest over time
                interest_df = self.pytrends.interest_over_time()

                if interest_df.empty:
                    st.error("❌ No trend data found for these keywords.")
                    return

                # 📈 Plot Interest Over Time (Interactive)
                self.plot_interest_over_time(interest_df)

                # Export CSV
                csv = interest_df.reset_index().to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Download Interest Over Time as CSV",
                    data=csv,
                    file_name='interest_over_time.csv',
                    mime='text/csv'
                )

                # Sidebar Filters for Regional Data
                st.sidebar.subheader("📊 Regional Data Filters")
                top_n = st.sidebar.slider("Select Top N Regions", min_value=5, max_value=50, value=10, step=1)
                min_interest = st.sidebar.slider("Minimum Interest Level", min_value=0, max_value=100, value=0, step=1)

                # Fetch Interest by Region
                region_df = self.get_interest_by_region()

                if region_df is not None and not region_df.empty:
                    combined_filtered_df = pd.DataFrame()

                    for keyword in self.keywords:
                        if keyword in region_df.columns:
                            # Apply filters
                            filtered_region_df = region_df[region_df[keyword] >= min_interest]
                            filtered_region_df = filtered_region_df.sort_values(by=keyword, ascending=False).head(top_n)

                            if not filtered_region_df.empty:
                                filtered_region_df = filtered_region_df.rename(columns={keyword: f"{keyword}_interest"})

                                if combined_filtered_df.empty:
                                    combined_filtered_df = filtered_region_df
                                else:
                                    combined_filtered_df = pd.concat([combined_filtered_df, filtered_region_df], axis=1)

                                # 🌍 Plot Top Regions (Interactive)
                                self.plot_top_regions(filtered_region_df, keyword)
                            else:
                                st.warning(f"No regions meet the filter criteria for '{keyword}'.")
                        else:
                            st.warning(f"No regional interest data available for '{keyword}'.")

                    # Export CSV
                    if not combined_filtered_df.empty:
                        combined_csv = combined_filtered_df.reset_index().to_csv(index=False).encode('utf-8')
                        st.download_button(
                            label="📥 Download Combined Regional Interest as CSV",
                            data=combined_csv,
                            file_name="combined_regional_interest.csv",
                            mime="text/csv"
                        )
                else:
                    st.warning("No regional data found for the selected keyword(s).")

                # Related Searches Section
                self.display_related_queries()

            except Exception as e:
                st.error(f"Something went wrong: {e}")

    def get_interest_by_region(self):
        """Retrieve Google Trends interest by region."""
        region_df = self.pytrends.interest_by_region()
        if not region_df.empty:
            return region_df
        return pd.DataFrame()

    # Interactive Plot for Interest Over Time
    def plot_interest_over_time(self, df):
        if df.empty:
            st.warning("No data available for the selected keywords/timeframe.")
            return

        fig = px.line(
            df,
            x=df.index,
            y=df.columns[:-1],  # Exclude 'isPartial'
            title="Interest Over Time",
            labels={"value": "Interest", "index": "Date"},
            markers=True
        )
        fig.update_traces(mode="lines+markers", hovertemplate="%{y}")
        st.plotly_chart(fig, use_container_width=True)

    #Interactive Plot for Top Regions
    def plot_top_regions(self, df, keyword):
        if df.empty:
            st.warning("No regional data available.")
            return

        fig = px.bar(
            df,
            x=df.index,
            y=f"{keyword}_interest",
            title=f"Top Regions for '{keyword}'",
            labels={"value": "Interest", "index": "Region"}
        )
        fig.update_traces(hovertemplate="%{x}: %{y}")
        st.plotly_chart(fig, use_container_width=True)

    def display_related_queries(self):
        """Displays top related search queries for the first keyword."""
        st.subheader("🔗 Top Related Queries")
        try:
            time.sleep(3)
            related = self.pytrends.related_queries()
            top = related.get(self.keywords[0], {}).get("top", None)

            if top is not None and not top.empty:
                st.dataframe(top.head(10))
            else:
                st.info("No related queries found.")
        except Exception as e:
            st.warning(f"Unable to fetch related queries: {e}")


# Main Program Execution
if __name__ == "__main__":
    app = GoogleTrendsExplorer()
    app.set_user_input()
    app.fetch_trend_data()
