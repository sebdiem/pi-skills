---
name: leboncoin
description: "Allows to search leboncoin for interesting stuff"
---

# Leboncoin skill

This skill allows you to search the French classifieds site [Leboncoin.fr](https://www.leboncoin.fr), fetch item details, and extract the best items for the user.

## Instructions

Whenever you are tasked with searching for an item on Leboncoin, strictly follow this procedure:

### 1. Retrieve Listing URLs
Run the `leboncoin_search.py` script to fetch listing URLs using a Leboncoin search URL. You must construct the search URL based on what the user wants (e.g. `https://www.leboncoin.fr/recherche?text=macbook+pro`).

To execute properly (as these use python inline dependencies), use `uv run`:
```bash
# E.g., target the skill directory absolute path
uv run /Users/seb/.pi/agent/skills/leboncoin/scripts/leboncoin_search.py "<SEARCH_URL>" --pages <PAGE_COUNT>
```

**⚠️ CRITICAL: Page Count Guidelines**

Leboncoin sorts results by date (newest first). Great deals from 2-4 weeks ago are often pushed to later pages. To avoid missing gems:

| Scenario | Minimum Pages | Reason |
|----------|---------------|--------|
| Urgent purchase (need it now) | 5 pages | Focus on recent listings |
| Standard search | **10 pages** | Catch older good deals |
| Rare/specific item | 15-20 pages | Fewer listings, need broader coverage |

**Default: Always fetch at least 10 pages** unless the user explicitly wants only recent listings.

### 2. Fetch Item Details

Extract the actual content (price, specs, description length/quality, condition) of the selected items using leboncoin_item.py. You can batch several URLs (8-10 at a time) to speed up things:

```bash
  uv run /Users/seb/.pi/agent/skills/leboncoin/scripts/leboncoin_item.py "<ITEM_URL1>" "<ITEM_URL2>" ...
```

**⚠️ CRITICAL: Explore ALL fetched URLs**

Do NOT stop after finding "good enough" options. You must:
1. Fetch details for ALL URLs retrieved in step 1 (or at least 80%)
2. Only then evaluate and rank them
3. If you stop early, explicitly tell the user how many listings you explored vs total available

### 3. Report Coverage to User

Before presenting results, always report:
```
📊 Coverage: Explored X out of Y total listings (Z%)
```

This allows the user to judge if the search was exhaustive enough.

### 4. Provide the Best Answer to your Master

After analyzing ALL fetched details:
- Be as exhaustive as possible: explore all fetched listings before concluding
- Use your world knowledge to evaluate which items offer the best value for your master (considering original MSRP, current market standards, condition, etc.).
- Filter out out-of-budget, suspicious, severely damaged, or poorly described listings.
- Present a concise, curated list of the best options. Include the title, price, the direct URL, and a brief reasoning behind why each selection is a stellar choice compared to the rest.

### 5. Alternative Search Strategies

If the initial search yields few results, try:
- Different keywords (e.g., "haltères" → "dumbells", "poids musculation", "disques fonte")
- Broader location (expand radius, include nearby cities)
- Remove location filter entirely, then filter results manually by location

Enjoy finding great deals!
