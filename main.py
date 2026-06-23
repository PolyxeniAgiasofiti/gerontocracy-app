from src.extract import get_all_indicators, get_eurostat_demographics_dataset
from src.load import save_dataframe, create_tables
from src.quality_checks import run_quality_checks

create_tables()

# Old MVP indicators table
df = get_all_indicators()
save_dataframe(df, "indicators")

# New structured Eurostat dataset table
eurostat_df = get_eurostat_demographics_dataset()
save_dataframe(eurostat_df, "eurostat_demographics")

quality_df = run_quality_checks()

print("Indicators table:")
print(df)

print("\nEurostat demographics dataset:")
print(eurostat_df)

print("\nQuality checks:")
print(quality_df)

print("\nData pipeline completed successfully.")