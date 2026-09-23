# Hand-picked card tags brief: ♥ what you know them for · ♠ big themes · ★ key people

Approved pilot (Oki, 23 Sep 2026): the 12 demo cards. See `hand_tags_pilot.json` in the run's scratchpad, or the `hw` / `th` / `pp` keys in `data/card_tags.json`.

Source for each company: its extract `cardline_src/<slug>.txt` (the report's hero + sections 01–03). No web, no outside knowledge.

## Families
Labels are **broad**: one or two words, shared across many companies. The tooltip carries the company-specific detail.

1. **♥ What you know them for:** exactly ONE label for what the company makes or sells, in words a newcomer uses. Pick from this list; propose `NEW:<label>` only if nothing fits:
   Chips, Chip equipment, Software, Cloud, Cybersecurity, Computers, Phones, Networking, Cars, Trucks, Auto parts, Beverages, Alcohol, Food, Household products, Beauty, Restaurants, Retail, Groceries, Clothing, Shoes, Luxury, Banking, Insurance, Payments, Exchanges, Asset management, Brokerage, Credit cards, Defense, Aerospace, Medicines, Biotech, Medical devices, Lab equipment, Health insurance, Hospitals, Pharmacy, Oil & gas, Pipelines, Electricity, Water, Real estate, Data centers, Telecom, Media, Social media, Streaming, Video games, Advertising, Travel, Hotels, Cruises, Casinos, Airlines, Railroads, Trucking, Shipping & delivery, Machinery, Construction, Building products, Industrial parts, Chemicals, Mining, Gold, Steel, Fertilizer, Packaging, Homebuilding, Tobacco, Consulting, Staffing & HR, Waste, Rentals, Data & ratings.
2. **♠ Big themes:** 0–2 broad trends the company is exposed to, and only when the extract treats the trend as central to this company, not a passing mention:
   AI, Robotics, EVs, Clean energy, Nuclear, Data centers, Cloud, Cybersecurity, Gov't spending, Aging population, Weight-loss drugs, Reshoring, Crypto, Space, Wildfire risk, Interest rates, Consumer spending, Housing, Tariffs, China, Oil prices, Streaming wars, Patent cliff.
3. **★ Key people:** 0–1, only if the extract states it with a date:
   - `Founder-CEO`: a founder still runs it.
   - `Long-serving CEO`: CEO for 15+ years at the report date.
   - `New CEO`: in the job under 2 years at the report date. Also return the start date as YYYY-MM so the tag can expire.
   - `Famous owner`: a well-known investor holds a large stake.
   - The person's surname, when the person IS the story (e.g. Musk).

## Tooltips
- 1–2 sentences each.
- Plain English for a smart reader who doesn't follow markets; no jargon, no defining everyday words.
- Company-specific facts from the extract only.
- No buy/sell language.
- No "this year", "now" or "recently". Durable phrasing.

## Return
One JSON object per slug, one per line (JSON Lines), exactly:
`{"slug":"nvda","hw":[["Chips","..."]],"th":[["AI","..."]],"pp":[["Founder-CEO","..."]],"since":null}`
Use `"th":[]` and `"pp":[]` when none apply. `since` is YYYY-MM for New CEO, otherwise null.

## Checker
For every tag, verify:
1. The label is from the list (or a justified NEW).
2. The theme is central in the extract.
3. The person tag has its date in the extract.
4. The tooltip's facts are in the extract, and it is plain and durable.

Fix or drop anything failing. Return the same JSON Lines, adding `"chk":"PASS"` or `"chk":"FIXED: reason"`.
