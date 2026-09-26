"""Head office of a report's company, as a card tag: [short label, full text] from the page's "HQ:" line.

The label is "US-based" for any US address, else "<country>-based"; a line that cannot be reduced to one
country gives no tag rather than a wrong one. Used by tools/card_tags.py.
"""
import html
import re

# Full names only, so a street or city word ("West Wen Yi Road", "New Delhi", "Prince Edward Island") never
# reads as a state; multi-word names are matched whole, longest first.
US_STATES = [
    'Alabama', 'Alaska', 'Arizona', 'Arkansas', 'California', 'Colorado', 'Connecticut', 'Delaware', 'Florida',
    'Georgia', 'Hawaii', 'Idaho', 'Illinois', 'Indiana', 'Iowa', 'Kansas', 'Kentucky', 'Louisiana', 'Maine',
    'Maryland', 'Massachusetts', 'Michigan', 'Minnesota', 'Mississippi', 'Missouri', 'Montana', 'Nebraska',
    'Nevada', 'New Hampshire', 'New Jersey', 'New Mexico', 'New York', 'North Carolina', 'North Dakota', 'Ohio',
    'Oklahoma', 'Oregon', 'Pennsylvania', 'Rhode Island', 'South Carolina', 'South Dakota', 'Tennessee', 'Texas',
    'Utah', 'Vermont', 'Virginia', 'Washington', 'West Virginia', 'Wisconsin', 'Wyoming',
]
STATE_RE = re.compile(r'\b(' + '|'.join(re.escape(s) for s in sorted(US_STATES, key=len, reverse=True))
                      + r'|D\.?C\.?|USA|U\.S\.A?\.?|United States)\b')
US_ABBR = re.compile(r',\s*(A[KLRZ]|C[AOT]|D[CE]|FL|GA|HI|I[ADLN]|K[SY]|LA|M[ADEINOST]|N[CDEHJMVY]|O[HKR]|PA|RI|S[CD]|T[NX]|UT|V[AT]|W[AIVY])\b')
COUNTRY = {'united kingdom': 'UK', 'england': 'UK', 'uk': 'UK', 'the netherlands': 'Netherlands',
           'republic of ireland': 'Ireland', 'people\'s republic of china': 'China', 'south korea': 'South Korea',
           'korea': 'South Korea', 'taiwan (roc)': 'Taiwan',
           # Canadian provinces and a city that appear as the last part of a head-office line
           'ontario': 'Canada', 'alberta': 'Canada', 'quebec': 'Canada', 'québec': 'Canada',
           'british columbia': 'Canada', 'nova scotia': 'Canada', 'n.s.': 'Canada', 'toronto': 'Canada',
           'manitoba': 'Canada', 'saskatchewan': 'Canada', 'new brunswick': 'Canada',
           'prince edward island': 'Canada', 'newfoundland and labrador': 'Canada'}
HQ_FALLBACK = {  # reports with no "HQ:" line (from Wikipedia's constituent list or the report text)
    'hd': 'Atlanta, Georgia', 'unh': 'Minnetonka, Minnesota',
}


def hq_of(slug: str, text: str) -> list[str] | None:
    """[short label, full head-office text] from the page's "HQ:" line, or None when it cannot be reduced to one."""
    m = re.search(r'HQ:?\s*</span>\s*([^<]{3,160})|HQ:\s*([^<]{3,160})', text)
    full = html.unescape((m.group(1) or m.group(2)).strip()) if m else HQ_FALLBACK.get(slug)
    if not full:
        return None
    full = re.sub(r'\s+', ' ', full).strip(' ·;')
    # classify on the stated head office only, not on notes in brackets ("(executive offices in Columbus, Ohio)")
    main = re.split(r'\s*[·;]', re.sub(r'\([^)]*\)', '', full))[0].strip(' ,')
    if ',' not in main:             # "Mayfield Village (300 N. Commons Blvd., Mayfield, OH 44143)": the place is in the brackets
        main = full
    if STATE_RE.search(main) or US_ABBR.search(main) or re.search(r'\b[A-Z]{2} \d{5}\b', main):
        return ['US-based', full]
    parts = [p.strip() for p in main.split(',') if p.strip()]
    country = parts[-1] if parts else main
    country = COUNTRY.get(country.lower(), country)
    if len(country) > 18:           # free text we can't reduce to a country: show no tag rather than a wrong one
        return None
    return [f'{country}-based', full]
