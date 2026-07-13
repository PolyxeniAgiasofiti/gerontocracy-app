from src.extract import (
    get_all_indicators,
    get_eurostat_demographics_dataset,
    get_housing_market_dataset,
    get_social_protection_dataset,
    get_social_protection_shares_dataset,
    get_median_age_eu_countries_dataset,
    get_leaving_home_eu_countries_dataset,
    get_youth_housing_overburden_eu_countries_dataset,
    get_property_price_growth_eu_countries_dataset,
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


social_shares_df = get_social_protection_shares_dataset()
save_dataframe(
    social_shares_df,
    "social_protection_shares"
)


median_age_df = get_median_age_eu_countries_dataset()
save_dataframe(
    median_age_df,
    "median_age_eu_countries"
)


leaving_home_df = get_leaving_home_eu_countries_dataset()
save_dataframe(
    leaving_home_df,
    "leaving_home_eu_countries"
)


youth_housing_df = get_youth_housing_overburden_eu_countries_dataset()
save_dataframe(
    youth_housing_df,
    "youth_housing_eu_countries"
)


property_price_df = get_property_price_growth_eu_countries_dataset()
save_dataframe(
    property_price_df,
    "property_price_growth_eu_countries"
)


quality_df = run_quality_checks()


print("Indicators table:")
print(df)

print("\nEurostat demographics dataset:")
print(eurostat_df)

print("\nHousing market dataset:")
print(housing_df)

print("\nSocial protection dataset:")
print(social_df)

print("\nSocial protection shares dataset:")
print(social_shares_df)

print("\nMedian age EU countries dataset:")
print(median_age_df)

print("\nLeaving parental home EU countries dataset:")
print(leaving_home_df)

print("\nYouth housing overburden EU countries dataset:")
print(youth_housing_df)

print("\nProperty price growth EU countries dataset:")
print(property_price_df)

print("\nQuality checks:")
print(quality_df)

print("\nData pipeline completed successfully.")