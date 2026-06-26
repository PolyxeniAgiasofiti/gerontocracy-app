from src.extract import (
    get_all_indicators,
    get_eurostat_demographics_dataset,
    get_housing_market_dataset,
    get_social_protection_dataset
)
from src.load import save_dataframe, create_tables
from src.quality_checks import run_quality_checks

create_tables()

df = get_all_indicators()
save_dataframe(df, "indicators")

eurostat_df = get_eurostat_demographics_dataset()
save_dataframe(eurostat_df, "eurostat_demographics")

housing_df = get_housing_market_dataset()
save_dataframe(housing_df, "housing_market")

social_df = get_social_protection_dataset()
save_dataframe(social_df, "social_protection")

quality_df = run_quality_checks()

print("Indicators table:")
print(df)

print("\nEurostat demographics dataset:")
print(eurostat_df)

print("\nHousing market dataset:")
print(housing_df)

print("\nSocial protection dataset:")
print(social_df)

print("\nQuality checks:")
print(quality_df)

print("\nData pipeline completed successfully.")