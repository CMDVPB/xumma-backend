def format_site(site):
    if not site:
        return None

    parts = [
        site.address_site,
        site.city_site,
        site.zip_code_site,
        getattr(site.country_code_site, "code", None),  # safe country access
    ]

    return ", ".join(p for p in parts if p)
