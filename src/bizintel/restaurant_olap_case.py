"""restaurant_olap_case.py - custom project.

An example of OLAP reporting for a restaurant business.

OLAP stands for Online Analytical Processing.
OLAP techniques help examine restaurant business
measures across different dimensions and levels of detail.

Author: Ralph Massaquoi
Date: 2026-08

Process:
- Connect to the DuckDB data warehouse.
- Create restaurant reporting tables.
- Create a restaurant reporting view.
- Export a reporting-ready restaurant dataset.
- Slice restaurant sales by location.
- Dice restaurant sales by menu dimensions.
- Roll up restaurant sales by time.
- Drill down from summaries to detailed orders.
- Visualize restaurant OLAP results.

Data Source:
- artifacts/smart_sales.duckdb

Output:
- data/reporting/restaurant_reporting.csv

Terminal command to run this file from the root project folder:

uv run python -m bizintel.restaurant_olap_case
"""

# === Section 1. Import dependencies and set up constants ===

# === IMPORTS ===

from pathlib import Path
from typing import Final

from datafun_toolkit.logger import log_path
import duckdb
import matplotlib.pyplot as plt
import pandas as pd

from bizintel.utils_logger import LOG, log_header
from bizintel.utils_viz import plot_bar, plot_line

# === DECLARE CONSTANTS ===

# Path to the DuckDB data warehouse.
DW_FILE: Final[Path] = Path("artifacts/smart_sales.duckdb")

# Folder for reporting-ready data.
DATA_REPORTING: Final[Path] = Path("data/reporting")

# Reporting-ready CSV file used by Power BI or Spark.
REPORTING_FILE: Final[Path] = DATA_REPORTING / "restaurant_reporting.csv"

# A slice selects one value from one dimension.
# Change this value in your copied file to investigate another region.
SLICE_REGION: Final[str] = "Downtown"

# A dice selects values from two or more dimensions.
# Change these values in your copied file to investigate another data subset.

DICE_REGIONS: Final[tuple[str, ...]] = ("Downtown", "Uptown")
DICE_CATEGORIES: Final[tuple[str, ...]] = ("Food", "Beverage")


# === Section 2. Define Reusable Functions ===

# === Section 2.1 DEFINE A VERIFY WAREHOUSE FUNCTION ===


def verify_warehouse(conn: duckdb.DuckDBPyConnection) -> None:
    """Verify that the required warehouse tables exist.

    WHY: Connecting to a missing DuckDB file creates a new empty database.
    We verify the file and required tables before running reporting queries
    so students receive a useful message instead of a confusing SQL error.

    Args:
        conn: Open DuckDB connection.

    Returns:
        None

    Raises:
        RuntimeError: If a required warehouse table is missing.
    """
    LOG.info("Verifying required warehouse tables")

    # SHOW TABLES returns one tuple for every table in the database.
    table_rows = conn.execute("SHOW TABLES").fetchall()

    # The first value in each tuple is the table name.
    existing_tables: set[str] = {str(row[0]) for row in table_rows}

    # These tables were created and populated in Module 4.
    required_tables: set[str] = {
        "dim_customers",
        "dim_products",
        "fact_sales",
    }

    # Set subtraction finds any required tables that are not present.
    missing_tables: set[str] = required_tables - existing_tables

    if missing_tables:
        missing_text = ", ".join(sorted(missing_tables))
        raise RuntimeError(
            "The data warehouse is missing required tables: "
            f"{missing_text}. Create and populate the Module 4 warehouse first."
        )

    LOG.info("  PASS: All required warehouse tables are available")


# === Section 2.2 DEFINE A CREATE TABLE FUNCTION ===


def create_restaurant_tables(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    """Create restaurant tables for the custom OLAP project."""

    LOG.info("Creating restaurant tables")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS dim_restaurants (
            RestaurantID INTEGER,
            RestaurantName VARCHAR,
            Location VARCHAR,
            RestaurantType VARCHAR
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS dim_menu_items (
            MenuItemID INTEGER,
            MenuName VARCHAR,
            Category VARCHAR,
            Price DOUBLE
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS fact_orders (
            OrderID INTEGER,
            OrderDate DATE,
            RestaurantID INTEGER,
            MenuItemID INTEGER,
            Quantity INTEGER,
            SalesAmount DOUBLE
        )
    """)

    LOG.info("Restaurant tables ready")


# === Section 2.3 DEFINE LOAD RESTAURANT DATA FUNCTION ===


def load_restaurant_data(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    """Load sample restaurant data into DuckDB tables."""

    LOG.info("Loading restaurant sample data")

    conn.execute("""
        INSERT INTO dim_restaurants VALUES
        (1, 'Downtown Bistro', 'Downtown', 'Casual'),
        (2, 'Uptown Grill', 'Uptown', 'Family'),
        (3, 'Lakeside Cafe', 'Lakeside', 'Cafe')
    """)

    conn.execute("""
        INSERT INTO dim_menu_items VALUES
        (101, 'Classic Burger', 'Food', 12.99),
        (102, 'Caesar Salad', 'Food', 9.99),
        (103, 'Coffee', 'Beverage', 3.50),
        (104, 'Fresh Juice', 'Beverage', 5.50)
    """)

    conn.execute("""
        INSERT INTO fact_orders VALUES
        (1001, '2026-01-05', 1, 101, 2, 25.98),
        (1002, '2026-01-06', 1, 103, 5, 17.50),
        (1003, '2026-02-10', 2, 102, 3, 29.97),
        (1004, '2026-02-15', 3, 104, 4, 22.00),
        (1005, '2026-03-01', 2, 101, 6, 77.94)
    """)

    LOG.info("Restaurant data loaded")


# === Section 2.4 DEFINE A CREATE RESTAURANT REPORTING VIEW FUNCTION ===


def create_restaurant_reporting_view(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    """Create a reporting view for restaurant OLAP analysis."""

    LOG.info("Creating restaurant_reporting view")

    sql = """
        CREATE OR REPLACE VIEW restaurant_reporting AS
        SELECT
            o.OrderID,
            o.OrderDate,

            r.RestaurantID,
            r.RestaurantName,
            r.Location,

            m.MenuItemID,
            m.MenuName,
            m.Category,

            o.Quantity,
            o.SalesAmount

        FROM fact_orders o

        JOIN dim_restaurants r
            ON o.RestaurantID = r.RestaurantID

        JOIN dim_menu_items m
            ON o.MenuItemID = m.MenuItemID
    """

    conn.execute(sql)

    LOG.info("restaurant_reporting view created")


# === Section 2.5 DEFINE AN EXPORT RESTAURANT REPORTING DATASET FUNCTION ===


def export_restaurant_reporting_dataset(
    conn: duckdb.DuckDBPyConnection,
) -> pd.DataFrame:
    """Export the restaurant reporting view to CSV.

    WHY: The exported dataset can be used by reporting
    tools such as Power BI or Spark.

    Args:
        conn: Open DuckDB connection.

    Returns:
        Restaurant reporting DataFrame.
    """

    LOG.info("Exporting restaurant reporting dataset")

    DATA_REPORTING.mkdir(
        parents=True,
        exist_ok=True,
    )

    sql = """
        SELECT *
        FROM restaurant_reporting
        ORDER BY OrderDate, OrderID
    """

    df_reporting: pd.DataFrame = conn.execute(sql).df()

    df_reporting.to_csv(
        REPORTING_FILE,
        index=False,
    )

    LOG.info(f"  Exported {df_reporting.shape[0]} restaurant reporting rows")

    log_path(
        LOG,
        "Restaurant reporting data:",
        REPORTING_FILE,
    )

    return df_reporting


# === Section 2.6 DEFINE A SLICE FUNCTION ===


def slice_restaurant_sales_by_region(
    conn: duckdb.DuckDBPyConnection,
    selected_location: str,
) -> pd.DataFrame:
    """Slice restaurant sales by one location.

    WHY: A slice selects one value from one dimension.
    Here, we select one restaurant location and compare
    restaurant sales by menu category.

    Args:
        conn: Open DuckDB connection.
        selected_location: Location to analyze.

    Returns:
        DataFrame with Location, Category, and TotalSales.
    """

    LOG.info(f"OLAP slice: restaurant sales for Location = {selected_location!r}")

    sql = """
        SELECT
            Location,
            Category,
            ROUND(SUM(SalesAmount), 2) AS TotalSales
        FROM restaurant_reporting
        WHERE Location = ?
        GROUP BY Location, Category
        ORDER BY TotalSales DESC
    """

    df_slice: pd.DataFrame = conn.execute(
        sql,
        [selected_location],
    ).df()

    if df_slice.empty:
        raise ValueError(
            f"No restaurant sales found for location {selected_location!r}"
        )

    LOG.info(f"  Categories in slice: {df_slice.shape[0]}")

    return df_slice


# === Section 2.7 DEFINE A DICE FUNCTION ===


def dice_restaurant_sales_by_dimensions(
    conn: duckdb.DuckDBPyConnection,
    selected_location: tuple[str, ...],
    selected_categories: tuple[str, ...],
) -> pd.DataFrame:
    """Dice restaurant sales by selected locations and menu categories.

    WHY: A dice filters across multiple dimensions.
    Here, we compare selected restaurant locations and
    menu categories.

    Args:
        conn: Open DuckDB connection.
        selected_lovations: Locations to include.
        selected_categories: Menu categories to include.

    Returns:
        DataFrame with Location, Category, and TotalSales.
    """

    LOG.info(
        f"OLAP dice: Locations={selected_location}; Categories={selected_categories}"
    )

    sql = """
        SELECT
            Location,
            Category,
            ROUND(SUM(SalesAmount), 2) AS TotalSales
        FROM restaurant_reporting
        WHERE Location IN (?, ?)
          AND Category IN (?, ?)
        GROUP BY Location, Category
        ORDER BY TotalSales DESC
    """

    parameters: list[str] = [
        *selected_location,
        *selected_categories,
    ]

    df_dice: pd.DataFrame = conn.execute(
        sql,
        parameters,
    ).df()

    if df_dice.empty:
        raise ValueError("The selected restaurant dice returned no rows.")

    LOG.info(f" Location- category combinations: {df_dice.shape[0]}")

    return df_dice


# === Section 2.8 DEFINE A ROLL-UP FUNCTION ===


def rollup_restaurant_sales_by_time(
    conn: duckdb.DuckDBPyConnection,
) -> pd.DataFrame:
    """Roll up restaurant sales through the time hierarchy.

    Time hierarchy:
        Month -> Quarter -> Year -> All Years
    """

    LOG.info("OLAP roll-up: Month -> Quarter -> Year -> All Years")

    sql = """
        SELECT
            CASE
                WHEN SalesYear IS NULL THEN 'All Years'
                WHEN SalesQuarter IS NULL THEN 'Year'
                WHEN YearMonth IS NULL THEN 'Quarter'
                ELSE 'Month'
            END AS SummaryLevel,

            SalesYear,
            SalesQuarter,
            YearMonth,

            ROUND(SUM(SalesAmount), 2) AS TotalSales

        FROM
        (
            SELECT
                EXTRACT(YEAR FROM OrderDate)::INTEGER AS SalesYear,

                EXTRACT(QUARTER FROM OrderDate)::INTEGER
                    AS SalesQuarter,

                STRFTIME(OrderDate, '%Y-%m') AS YearMonth,

                SalesAmount

            FROM restaurant_reporting
        )

        GROUP BY ROLLUP
        (
            SalesYear,
            SalesQuarter,
            YearMonth
        )

        ORDER BY
            SalesYear NULLS LAST,
            SalesQuarter NULLS LAST,
            YearMonth NULLS LAST
    """

    df_rollup: pd.DataFrame = conn.execute(sql).df()

    LOG.info(f"  Roll-up rows returned: {df_rollup.shape[0]}")

    return df_rollup


# === Section 2.9 DEFINE A DRILL-DOWN FUNCTION ===


def drilldown_restaurant_sales_by_time(
    conn: duckdb.DuckDBPyConnection,
    selected_year: int,
) -> pd.DataFrame:
    """Drill down restaurant sales from year to month.

    WHY: Drill-down reveals details behind a summary.
    A manager can start with yearly sales and investigate
    quarters and months that contributed to the result.

    Time hierarchy:
        Year -> Quarter -> Month

    Args:
        conn: Open DuckDB connection.
        selected_year: Year to investigate.

    Returns:
        DataFrame containing year, quarter, and month detail.
    """

    LOG.info(f"OLAP drill-down: Year {selected_year} -> Quarter -> Month")

    sql = """
        WITH selected_sales AS (

            SELECT
                EXTRACT(YEAR FROM OrderDate)::INTEGER
                    AS SalesYear,

                EXTRACT(QUARTER FROM OrderDate)::INTEGER
                    AS SalesQuarter,

                STRFTIME(OrderDate, '%Y-%m')
                    AS YearMonth,

                SalesAmount

            FROM restaurant_reporting

            WHERE EXTRACT(YEAR FROM OrderDate)::INTEGER = ?

        )

        SELECT
            1 AS SortLevel,
            'Year' AS DetailLevel,

            CAST(SalesYear AS VARCHAR)
                AS PeriodLabel,

            NULL AS SalesQuarter,
            NULL AS YearMonth,

            ROUND(SUM(SalesAmount), 2)
                AS TotalSales

        FROM selected_sales

        GROUP BY SalesYear


        UNION ALL


        SELECT
            2 AS SortLevel,
            'Quarter' AS DetailLevel,

            CAST(SalesYear AS VARCHAR)
                || '-Q'
                || CAST(SalesQuarter AS VARCHAR)
                AS PeriodLabel,

            SalesQuarter,
            NULL AS YearMonth,

            ROUND(SUM(SalesAmount), 2)
                AS TotalSales

        FROM selected_sales

        GROUP BY SalesYear, SalesQuarter


        UNION ALL


        SELECT
            3 AS SortLevel,
            'Month' AS DetailLevel,

            YearMonth AS PeriodLabel,

            SalesQuarter,
            YearMonth,

            ROUND(SUM(SalesAmount), 2)
                AS TotalSales

        FROM selected_sales

        GROUP BY SalesQuarter, YearMonth


        ORDER BY
            SortLevel,
            SalesQuarter NULLS FIRST,
            YearMonth NULLS FIRST
    """

    df_drilldown: pd.DataFrame = conn.execute(
        sql,
        [selected_year],
    ).df()

    if df_drilldown.empty:
        raise ValueError(f"No restaurant sales found for year {selected_year}")

    LOG.info(f"  Drill-down rows returned: {df_drilldown.shape[0]}")

    return df_drilldown


# === Section 2.10 DEFINE A SUMMARIZE FUNCTION ===


def summarize_restaurant_results(
    df_slice: pd.DataFrame,
    df_dice: pd.DataFrame,
    df_rollup: pd.DataFrame,
    df_drilldown: pd.DataFrame,
    selected_region: str,
    selected_year: int,
) -> None:
    """Summarize restaurant OLAP findings.

    WHY: Creates a short business summary from the
    analytical results.

    Args:
        df_slice: Slice analysis results.
        df_dice: Dice analysis results.
        df_rollup: Roll-up results.
        df_drilldown: Drill-down results.
        selected_region: Region analyzed.
        selected_year: Year analyzed.

    Returns:
        None
    """

    LOG.info("========================")
    LOG.info("RESTAURANT SUMMARY")
    LOG.info("========================")

    # Highest category within selected region.
    top_category: str = str(df_slice.iloc[0]["Category"])

    top_category_sales: float = float(df_slice.iloc[0]["TotalSales"])

    LOG.info(
        f"Slice: In {selected_region}, "
        f"top category is {top_category} "
        f"(${top_category_sales:,.2f})"
    )

    # Strongest location-category combination.
    best_location: str = str(df_dice.iloc[0]["Location"])

    best_category: str = str(df_dice.iloc[0]["Category"])

    best_sales: float = float(df_dice.iloc[0]["TotalSales"])

    LOG.info(
        "Dice: Strongest combination is "
        f"{best_location} / {best_category} "
        f"(${best_sales:,.2f})"
    )

    # Total sales from all years.
    df_total = df_rollup.loc[df_rollup["SummaryLevel"] == "All Years"]

    total_sales: float = float(df_total.iloc[0]["TotalSales"])

    LOG.info(f"Roll-up: Total restaurant sales are ${total_sales:,.2f}")

    # Best month from drill-down.
    df_months = df_drilldown.loc[df_drilldown["DetailLevel"] == "Month"]

    best_month_index = df_months["TotalSales"].idxmax()

    best_month: str = str(
        df_months.loc[
            best_month_index,
            "PeriodLabel",
        ]
    )

    best_month_sales: float = float(
        df_months.loc[
            best_month_index,
            "TotalSales",
        ]
    )

    LOG.info(
        f"Drill-down: Strongest month in {selected_year} "
        f"is {best_month} "
        f"(${best_month_sales:,.2f})"
    )

    LOG.info("========================")
    LOG.info("RESTAURANT ANALYST NOTES:")
    LOG.info("Slice identifies performance in one selected region.")
    LOG.info("Dice compares multiple restaurant dimensions.")
    LOG.info("Roll-up summarizes sales across time levels.")
    LOG.info("Drill-down reveals details behind summary results.")
    LOG.info("========================")


# === MAIN FUNCTION ===
def main() -> None:
    """Main function to run the DuckDB restaurant OLAP reporting logic."""

    log_header(LOG, "BI")

    LOG.info("========================")
    LOG.info("START main()")
    LOG.info("========================")

    log_path(LOG, "Data warehouse:", DW_FILE)
    log_path(LOG, "Reporting data:", REPORTING_FILE)

    # DuckDB creates an empty database when the requested file is missing.
    # Check first so we do not accidentally connect to a new empty warehouse.
    if not DW_FILE.exists():
        raise FileNotFoundError(
            f"Data warehouse not found: {DW_FILE}. "
            "Create and populate the Module 4 warehouse first."
        )

    LOG.info("Connecting to DuckDB data warehouse........")
    conn: duckdb.DuckDBPyConnection = duckdb.connect(str(DW_FILE))

    try:
        LOG.info("CALL a function to verify the warehouse........")
        verify_warehouse(conn)

        LOG.info("CALL a function to create restaurant tables........")
        create_restaurant_tables(conn)

        LOG.info("CALL a function to load restaurant data........")
        load_restaurant_data(conn)

        LOG.info("CALL a function to create the restaurant reporting view........")
        create_restaurant_reporting_view(conn)

        LOG.info("CALL a function to export restaurant reporting data........")
        export_restaurant_reporting_dataset(conn)

        LOG.info("CALL a function to slice restaurant sales by region........")
        df_slice = slice_restaurant_sales_by_region(
            conn,
            SLICE_REGION,
        )

        LOG.info("CALL a function to plot the slice result........")
        plot_bar(
            df=df_slice,
            x="Category",
            y="TotalSales",
            title=f"Sales by Category in {SLICE_REGION}",
            xlabel="Category",
            ylabel="Total Sales ($)",
            palette="Blues_d",
        )

        LOG.info("CALL a function to dice restaurant sales by dimensions........")
        df_dice = dice_restaurant_sales_by_dimensions(
            conn,
            DICE_REGIONS,
            DICE_CATEGORIES,
        )
        # Create one readable label for each location-category combination.
        df_dice_chart = df_dice.copy()

        df_dice_chart["LocationCategory"] = (
            df_dice_chart["Location"] + " / " + df_dice_chart["Category"]
        )

        df_dice_chart["LocationCategory"] = (
            df_dice_chart["Location"] + " / " + df_dice_chart["Category"]
        )

        LOG.info("CALL a function to plot the dice result........")
        plot_bar(
            df=df_dice_chart,
            x="LocationCategory",
            y="TotalSales",
            title="Restaurant Sales for Selected Locations and Categories",
            xlabel="Location / Category",
            ylabel="Total Sales ($)",
            palette="Greens_d",
        )

        LOG.info("CALL a function to roll up restaurant sales by time........")
        df_rollup = rollup_restaurant_sales_by_time(conn)

        df_quarterly = df_rollup.loc[df_rollup["SummaryLevel"] == "Quarter"].copy()

        df_quarterly["YearQuarter"] = (
            df_quarterly["SalesYear"].astype(int).astype(str)
            + "-Q"
            + df_quarterly["SalesQuarter"].astype(int).astype(str)
        )

        LOG.info("CALL a function to plot quarterly roll-up results........")
        plot_line(
            df=df_quarterly,
            x="YearQuarter",
            y="TotalSales",
            title="Quarterly Restaurant Sales Roll-Up",
            xlabel="Quarter",
            ylabel="Total Sales ($)",
        )

        selected_year = 2026

        LOG.info("CALL a function to drill down restaurant sales by time........")
        df_drilldown = drilldown_restaurant_sales_by_time(
            conn,
            selected_year,
        )

        df_monthly = df_drilldown.loc[df_drilldown["DetailLevel"] == "Month"].copy()

        LOG.info("CALL a function to plot monthly drill-down results........")
        plot_line(
            df=df_monthly,
            x="PeriodLabel",
            y="TotalSales",
            title=f"Monthly Restaurant Sales Drill-Down for {selected_year}",
            xlabel="Month",
            ylabel="Total Sales ($)",
        )

        LOG.info("CALL a function to summarize restaurant OLAP findings........")
        summarize_restaurant_results(
            df_slice,
            df_dice,
            df_rollup,
            df_drilldown,
            SLICE_REGION,
            selected_year,
        )

        LOG.info("CALL a function to show charts........")
        plt.show()

    finally:
        # Always close the database connection,
        # even if an error occurs while running a query.
        conn.close()
        LOG.info("Closed DuckDB connection")

    LOG.info("Workflow complete")
    LOG.info("CLOSE chart windows to continue.")
    LOG.info("Terminate this process with CTRL+c as needed.")
    LOG.info("========================")
    LOG.info("Executed successfully!")
    LOG.info("========================")


# === CONDITIONAL EXECUTION GUARD ===

if __name__ == "__main__":
    main()
