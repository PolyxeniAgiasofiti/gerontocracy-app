from src.extract import get_all_indicators
from src.load import save_dataframe, create_tables
from src.quality_checks import run_quality_checks

create_tables()

df = get_all_indicators()
save_dataframe(df, "indicators")

quality_df = run_quality_checks()

print(df)
print("\nQuality checks:")
print(quality_df)
print("\nData pipeline completed successfully.")