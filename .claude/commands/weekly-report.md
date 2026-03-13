# /weekly-report — Weekly Performance Report

Run every Friday at 18:00 IST. Generates a comprehensive performance report covering
all 3 locations with full competitor benchmark comparison and next-week strategy.

## Steps to Execute

### Step 1: Aggregate Weekly Data
Pull data from all sources for the past 7 days:
- GBP Insights API: views, searches, customer actions per location
- Review metrics: new reviews, rating changes, response rate, sentiment
- Post performance: views, clicks, CTR per post type
- Competitor benchmark data from `data/benchmarks.json`
- Keyword ranking data (if rank tracker is configured)

### Step 2: Compute Weekly KPIs (Per Location)

| Metric              | Current Week | Prior Week | Delta |
|---------------------|-------------|------------|-------|
| GBP Views (total)   | —           | —          | —     |
| Search Views        | —           | —          | —     |
| Maps Views          | —           | —          | —     |
| Calls               | —           | —          | —     |
| Direction Requests  | —           | —          | —     |
| Website Clicks      | —           | —          | —     |
| New Reviews         | —           | —          | —     |
| Average Rating      | —           | —          | —     |
| Review Response Rate| —           | —          | —     |
| Posts Published     | —           | —          | —     |
| Best Performing Post| —           | —          | —     |
| MBS Score           | —           | —          | —     |

### Step 3: Generate Benchmark Scorecard
Create the full 3-location × 5-competitor scorecard:

For each location, produce a table:

| Business        | MBS   | Reviews | Rating | Posts/mo | Photos | Trend |
|-----------------|-------|---------|--------|----------|--------|-------|
| ⭐ MoveABox     | —/100 | —       | —      | —        | —      | —     |
| Competitor 1    | —/100 | —       | —      | —        | —      | —     |
| Competitor 2    | —/100 | —       | —      | —        | —      | —     |
| Competitor 3    | —/100 | —       | —      | —        | —      | —     |
| Competitor 4    | —/100 | —       | —      | —        | —      | —     |
| Competitor 5    | —/100 | —       | —      | —        | —      | —     |

Include trend arrows: ↑ (improving), → (stable), ↓ (declining)
Include "time to overtake" estimate for each competitor MoveABox is behind.

### Step 4: Gap Analysis Summary
Pull the top 5 gap opportunities per location from the latest competitor audit.
Rank by Opportunity Score (see CLAUDE.md Section 3.4).
Format as actionable items with owner, timeline, and projected impact.

### Step 5: Post Performance Analysis
For each of the 7 posts published this week per location:
- Views, clicks, CTR
- Keyword coverage (which Tier 1 keywords were covered)
- Best performer and worst performer
- Recommendations for next week's content based on performance data

Identify: which post types performed best, which days had highest engagement,
which locations had highest CTR.

### Step 6: Review Sentiment Analysis
- Keyword extraction from all reviews received this week
- Positive themes (services praised, team members mentioned)
- Negative themes (complaints, areas for improvement)
- Trending topics compared to 4 weeks ago
- Competitor review sentiment comparison (if data available)

### Step 7: Keyword Ranking Update
For each location, report on ranking positions for top 10 Tier 1 keywords:
- Current position in Local Pack
- Change from prior week
- Keywords where MoveABox entered/exited top 3
- Keywords where competitors gained/lost position
- New keyword opportunities discovered this week

### Step 8: Generate Next-Week Content Calendar
Based on: post performance data, seasonal calendar, competitor intelligence,
keyword gaps, and upcoming events — generate a 7-day content calendar for each location.

Format:
```
[Location] — Week of [Date]
Mon: [Post type] — [Topic] — [Target keyword]
Tue: [Post type] — [Topic] — [Target keyword]
...
```

### Step 9: Strategic Recommendations
Generate 5–7 prioritized strategic actions for next week:
1. Content adjustments based on this week's performance
2. Review velocity campaign actions
3. Profile optimization tasks (Q&A, photos, completeness gaps)
4. Competitor response strategies
5. Citation/SEO opportunities
6. Any urgent alerts that need attention

### Step 10: Compile and Send Report
Create report at `reports/weekly/YYYY-MM-DD-weekly.md` with all sections above.
Send summary digest (top 5 insights + scorecard) to Slack `#gbp-weekly` and WhatsApp.

### Step 11: Monthly Strategy Memo (First Friday of Each Month)
If this is the first Friday of the month, also generate:
- Narrative 500–800 word memo: what worked, what didn't, strategic pivots
- Seasonal calendar opportunities for next 30 days
- Competitor moves to counter
- Content calendar adjustments
- Projected MBS scores for next month
- Save to `reports/weekly/YYYY-MM-monthly-[month].md`

## Output Files
- `reports/weekly/YYYY-MM-DD-weekly.md` — Full weekly report
- `reports/weekly/YYYY-MM-monthly-[month].md` — Monthly memo (first Friday)
- Updated `data/benchmarks.json` — Benchmark snapshot

## Success Criteria
- KPI table completed for all 3 locations with WoW deltas
- Full competitor benchmark scorecard generated
- Gap analysis summary with top 5 opportunities per location
- Post performance analysis completed
- Next-week content calendar generated
- Report saved and digest sent to Slack/WhatsApp
