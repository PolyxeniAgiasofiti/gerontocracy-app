import eurostat

df = eurostat.get_data_df("PRC_HPI_A")

countries = [
    "EU27_2020",
    "AT","BE","BG","HR","CY","CZ","DK","EE","FI",
    "FR","DE","EL","HU","IE","IT","LV","LT","LU",
    "MT","NL","PL","PT","RO","SK","SI","ES","SE"
]

filtered = df[
    (df["purchase"] == "TOTAL") &
    (df["unit"] == "RCH_A_AVG") &
    (df["geo\\TIME_PERIOD"].isin(countries))
]

print(filtered[["geo\\TIME_PERIOD", "2025"]])