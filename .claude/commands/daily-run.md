# /daily-run — MoveABox Daily Pipeline

Execute the full daily pipeline for all three MoveABox locations. Run this every morning
at 07:00 IST. Follow all steps in sequence as defined in CLAUDE.md.

## Steps to Execute

### Step 1: Fetch GBP Insights
- Call `src/gbp_api.py` to pull views, searches, customer actions for all 3 locations
- Store results in `data/benchmarks.json` (append today's snapshot)
- Flag any metric that dropped > 20% week-over-week

### Step 2: Review Management
- Call `src/review_manager.py` to fetch all new reviews across 3 locations
- Generate responses using the protocol in CLAUDE.md (5-star / 3-4 star / 1-2 star rules)
- Auto-queue 5-star responses; flag 1-4 star for human review
- Update `data/review_history.json`

### Step 3: Competitor Pulse Check
- Run a lightweight check on the top 5 competitors per location
- Check for: new reviews (delta), new posts, rating changes
- Trigger alerts if any competitor alert conditions are met (see CLAUDE.md)
- Store deltas in `data/competitors.json`

### Step 4: Determine Today's Post Type
- Check the day of week and the seasonal calendar
- Override with seasonal content if within 14 days of a seasonal window
- Read `data/post_history.json` to confirm post type hasn't been used in 7 days

### Step 5: Content Differentiation Check
- For each location, read the last 10 posts from each of the top 5 competitors
- Note all topics covered in the last 14 days
- Build a "forbidden topics" list for today's posts

### Step 6: Generate 3 Posts (1 Per Location)
For each location, generate a post that:
- Matches today's post type from the rotation schedule
- Contains at least ONE Tier 1 keyword naturally embedded
- References the specific location AND at least one neighborhood/landmark
- Is 150–300 words (800–1200 characters)
- Includes clear CTA with phone/website
- Uses max 3 emojis, no hashtags
- Avoids all "forbidden topics" from competitor posts
- Is < 20% similar to any post in `data/post_history.json` from last 90 days
- Includes Maps link if this is every 3rd post (check post_history count)

Output each post using the schema defined in CLAUDE.md (Section 6.3).

### Step 7: Quality Gate
- Score each post on 5 dimensions (0–10 each): Keyword Relevance, Location Specificity,
  Uniqueness, CTA Clarity, Tone & Voice
- If total < 35: Regenerate the post (max 3 attempts)
- If total 35–39: Save to `output/posts/` with flag `requires_human_review: true`
- If total 40+: Save to `output/posts/` with flag `auto_publish: true`

### Step 8: Generate Image Prompts
- For each approved post, generate a detailed image prompt
- Include: scene description, Bangalore context, professional movers, brand colors
- Save image prompts to `output/images/YYYY-MM-DD-[location].txt`

### Step 9: Queue Posts
- Schedule posts for optimal publish time: 10:00–11:00 AM IST
- Stagger by 15 minutes between locations
- Record in `data/post_history.json`

### Step 10: Daily Digest
- Compile summary of: posts generated, reviews responded to, competitor alerts,
  any anomalies detected
- Send to Slack channel `#gbp-daily` and WhatsApp group
- Save digest to `reports/daily/YYYY-MM-DD.md`

### Step 11: Log Everything
- Update all JSON files in `data/`
- Log pipeline run to `logs/daily.log`
- Record timestamp, posts generated, reviews processed, alerts triggered

## Success Criteria
- 3 posts generated and queued (or flagged for review)
- All new reviews have queued responses
- Daily digest sent
- No errors in data/ file updates
