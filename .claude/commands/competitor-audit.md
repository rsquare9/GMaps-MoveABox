# /competitor-audit — Weekly Competitor Deep Audit

Run every Monday at 06:00 IST. This is the deep competitor intelligence sweep.
Takes approximately 20–30 minutes. Output drives the entire week's content strategy.

## Steps to Execute

### Step 1: Competitor Discovery Sweep (Monthly only — skip if last run < 30 days ago)
For each location (Bannerghatta, Banashankari, Koramangala):
1. Search Google Maps using each Tier 1 keyword from that location's coordinates
2. Record every business in the Local 3-Pack or top 10 organic local results
3. Score each competitor on: proximity, review count, avg rating, posting frequency,
   category overlap
4. Select/update top 5 by composite threat score
5. Update `data/competitors.json` with full metadata schema

### Step 2: Full Data Collection (All 15 Competitors)
For each of the 15 tracked competitors, collect:
- Review count (total and delta since last audit)
- Average star rating (and delta)
- Review velocity (new reviews in last 30 days)
- Review response rate (% responded to)
- Average response time in hours
- Total photos and photos added in last 30 days
- Post count in last 30 days and post types
- Q&A section count
- Services/products listed count
- Booking link and messaging enabled status
- Local Pack appearance for top 5 keywords

Store all data in `data/competitors.json`. Track the delta from last week.

### Step 3: Benchmark Scoring
Run `src/benchmark_engine.py` to compute the MoveABox Benchmark Score (MBS) for:
- All 3 MoveABox locations
- All 15 competitors

Use the 10-dimension scoring matrix from CLAUDE.md. Store weekly snapshot in
`data/benchmarks.json` with ISO date key.

### Step 4: Gap Analysis
For each location, run the gap analysis engine:
1. Calculate metric-by-metric delta: MoveABox minus each competitor
2. Identify negative deltas (gaps) and positive deltas (advantages)
3. Score each gap: `(Metric_Weight × Absolute_Delta × Effort_Multiplier)`
   - Effort multipliers: quick win = 3.0, medium = 2.0, high effort = 1.0
4. Produce ranked opportunity list with: gap description, competitor benchmarked against,
   exact action, implementation time, projected ranking impact

### Step 5: Content Intelligence Extraction
For each competitor's last 30 posts:
1. Extract all topics covered
2. Extract all keywords used (explicit and semantic)
3. Identify gaps — keywords/topics competitors rank for that MoveABox does not
4. Add competitor-derived keywords to `data/keywords.json` with flag "competitor-sourced"
5. Build the 2-week "forbidden topics" list per location

### Step 6: Generate Competitor Audit Report
Create `reports/competitor/YYYY-MM-DD-audit.md` containing:
- Executive summary (3–5 bullet points)
- Benchmark scorecard (all 3 locations × all 15 competitors)
- Top 10 ranked gap opportunities across all locations
- Competitor keyword extraction results
- New keywords added to matrix
- Competitor alerts triggered
- Content strategy recommendations for the week

### Step 7: Trigger Alerts
Check all alert conditions and send Slack/WhatsApp notifications for any triggered:
- Any competitor gained 10+ reviews this week
- Any competitor rating now above MoveABox's
- New competitor in Local 3-Pack
- Competitor launched new service
- Competitor posting frequency doubled
- MoveABox lost ranking for previously dominant keywords

### Step 8: Update Strategy
Based on gap analysis, update `data/keywords.json` with:
- New competitor-sourced keywords
- Keyword priority adjustments
- Deprecated low-value keywords

## Output Files
- `reports/competitor/YYYY-MM-DD-audit.md` — Full audit report
- `data/competitors.json` — Updated competitor profiles
- `data/benchmarks.json` — New weekly snapshot appended
- `data/keywords.json` — Updated keyword matrix

## Success Criteria
- All 15 competitor profiles updated with current data
- MBS scores computed for MoveABox and all competitors
- Gap analysis completed with ranked opportunity list
- Competitor audit report generated and saved
- All triggered alerts sent
