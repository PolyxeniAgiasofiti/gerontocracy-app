"""
Prompt-driven starter discovery for the Gerontocracy Data Observatory.

This first version searches a curated catalogue of verified official data
repositories. It does not yet perform open-web AI discovery. That will be
added as a separate agent stage after the registry and audit trail are stable.
"""


GERONTOCRACY_REPOSITORY_CATALOG = [
    {
        "provider": "Eurostat",
        "repository_name": "Population and Demography",
        "url": "https://ec.europa.eu/eurostat/web/population-demography",
        "description": (
            "EU population structure, demographic indicators, population "
            "ageing, population stock and projections."
        ),
        "dimension": "Demography",
        "geography": "EU + Member States",
        "data_format": "Data portal / API",
        "refresh_frequency": "Monthly check",
        "keywords": [
            "gerontocracy", "age", "ageing", "aging", "population",
            "demography", "demographic", "elderly", "older", "old age",
            "dependency ratio", "life expectancy",
        ],
    },
    {
        "provider": "Eurostat",
        "repository_name": "Housing Database",
        "url": "https://ec.europa.eu/eurostat/web/housing/database",
        "description": (
            "EU housing statistics covering housing costs, affordability, "
            "living conditions and housing-market indicators."
        ),
        "dimension": "Housing",
        "geography": "EU + Member States",
        "data_format": "Data portal / API",
        "refresh_frequency": "Monthly check",
        "keywords": [
            "gerontocracy", "housing", "home", "property", "rent",
            "affordability", "leaving home", "overburden", "house price",
        ],
    },
    {
        "provider": "Eurostat",
        "repository_name": "Social Protection / ESSPROS",
        "url": "https://ec.europa.eu/eurostat/en/web/social-protection/database",
        "description": (
            "EU social-protection expenditure by function, including old age, "
            "housing, unemployment, family and social exclusion."
        ),
        "dimension": "Social Protection",
        "geography": "EU + Member States",
        "data_format": "Data portal / API",
        "refresh_frequency": "Monthly check",
        "keywords": [
            "gerontocracy", "social protection", "pension", "benefit",
            "old age", "welfare", "housing benefit", "family benefit",
        ],
    },
    {
        "provider": "Bank of Greece",
        "repository_name": "Real Estate Market",
        "url": "https://www.bankofgreece.gr/en/statistics/real-estate-market",
        "description": (
            "Official Greek residential and commercial property-price indices "
            "and related real-estate statistics."
        ),
        "dimension": "Housing & Assets",
        "geography": "Greece",
        "data_format": "Open data / Web",
        "refresh_frequency": "Quarterly check",
        "keywords": [
            "gerontocracy", "housing", "property", "house price",
            "real estate", "asset", "wealth", "home ownership",
        ],
    },
    {
        "provider": "ELSTAT",
        "repository_name": "ESSPROS Social Protection Expenditure",
        "url": "https://www.statistics.gr/en/statistics/-/publication/SHE24/-",
        "description": (
            "Greek ESSPROS social-protection expenditure time series, "
            "including old-age and housing functions."
        ),
        "dimension": "Social Protection",
        "geography": "Greece",
        "data_format": "Time series / Spreadsheets",
        "refresh_frequency": "Annual check",
        "keywords": [
            "gerontocracy", "social protection", "pension", "benefit",
            "old age", "welfare", "housing benefit", "greece",
        ],
    },
    {
        "provider": "OECD",
        "repository_name": "Income and Wealth Distribution Databases",
        "url": "https://www.oecd.org/en/data/datasets/income-and-wealth-distribution-database.html",
        "description": (
            "Cross-country income, poverty and household wealth distribution "
            "data, including age-group indicators in the income database."
        ),
        "dimension": "Wealth & Intergenerational Opportunity",
        "geography": "OECD countries including Greece",
        "data_format": "Data Explorer / SDMX API",
        "refresh_frequency": "Quarterly check",
        "keywords": [
            "gerontocracy", "wealth", "income", "inequality", "poverty",
            "asset", "intergenerational", "young", "older", "age group",
        ],
    },
    {
        "provider": "European Parliament",
        "repository_name": "MEPs Open Data",
        "url": "https://data.europarl.europa.eu/en/datasets/members-of-the-european-parliament-meps-parliamentary-term10/0030",
        "description": (
            "Open data on Members of the European Parliament, including "
            "birth dates and country of representation for age analysis."
        ),
        "dimension": "Political Power",
        "geography": "European Union",
        "data_format": "CSV / RDF / Open Data",
        "refresh_frequency": "Monthly check",
        "keywords": [
            "gerontocracy", "political", "politics", "parliament",
            "representation", "power", "mep", "leader", "decision making",
        ],
    },
    {
        "provider": "Eurostat",
        "repository_name": "Employment and Labour Force by Age",
        "url": "https://ec.europa.eu/eurostat/databrowser/view/lfsi_emp_a/default/table",
        "description": (
            "Annual employment and labour-force statistics by age for EU "
            "countries, supporting labour-market and retirement analysis."
        ),
        "dimension": "Labour & Positions",
        "geography": "EU + Member States",
        "data_format": "Data Browser / API",
        "refresh_frequency": "Monthly check",
        "keywords": [
            "gerontocracy", "labour", "labor", "employment", "work",
            "job", "retirement", "worker", "age", "seniority",
        ],
    },
]


def discover_gerontocracy_repositories(prompt):
    """
    Return relevant verified repositories from the starter catalogue.

    The prompt controls which gerontocracy dimensions are returned. A broad
    prompt containing 'gerontocracy' returns the complete starter catalogue.
    """

    prompt_text = (prompt or "").strip().lower()

    if not prompt_text:
        return []

    broad_topic = "gerontocracy" in prompt_text
    results = []

    for item in GERONTOCRACY_REPOSITORY_CATALOG:
        matches = sum(
            1
            for keyword in item["keywords"]
            if keyword in prompt_text
        )

        if broad_topic or matches > 0:
            candidate = {
                key: value
                for key, value in item.items()
                if key != "keywords"
            }

            if broad_topic:
                score = 85 + min(matches * 2, 10)
            else:
                score = 70 + min(matches * 5, 25)

            candidate["relevance_score"] = min(score, 100)
            results.append(candidate)

    results.sort(
        key=lambda item: (
            -item["relevance_score"],
            item["provider"],
            item["repository_name"],
        )
    )

    return results
