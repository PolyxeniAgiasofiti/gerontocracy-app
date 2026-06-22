import eurostat

dataset_code = "YTH_DEMO_030"
df = eurostat.get_data_df(dataset_code)

filtered = df[
    (df["sex"] == "T") &
    (df["geo\\TIME_PERIOD"].isin(["EL", "EU27_2020"]))
]

print(filtered[["geo\\TIME_PERIOD", "2024", "2025"]])