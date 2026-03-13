# /review-respond — Review Monitoring & Response

Run on-demand or automatically 4 times per day (08:00, 12:00, 17:00, 21:00 IST).
Monitors all 3 GBP locations for new reviews and generates appropriate responses.

## Steps to Execute

### Step 1: Fetch New Reviews
- Call `src/review_manager.py fetch_new_reviews()` for all 3 locations
- Compare against `data/review_history.json` to identify unprocessed reviews
- Sort by: 1-2 star reviews first (priority), then 3-4 star, then 5-star

### Step 2: Review Triage
For each new review, classify and flag:
- **5-star** → Auto-generate response, queue for immediate publish
- **3-4 star** → Generate response, flag for human review before publish
- **1-2 star** → Generate response, flag URGENT for human review + manager escalation
- **Suspicious review** (no photo, generic text, sudden spike) → Flag for dispute process

### Step 3: Generate Responses

#### For 5-Star Reviews:
Generate a response that:
- Thanks the reviewer by name
- References the specific service used (if mentioned in review)
- Naturally embeds one Tier 1 keyword for that location
- Mentions the location name and/or a neighborhood
- Cross-sells another MoveABox service
- Is 40–80 words
- Tone: warm, grateful, specific
- Passes brand voice check

#### For 3–4 Star Reviews:
Generate a response that:
- Thanks warmly, acknowledges the specific feedback given
- Mentions a concrete improvement or resolution step
- Provides direct contact: phone number + manager name
- Is 60–120 words
- Tone: constructive, accountable, solution-focused

#### For 1–2 Star Reviews:
Generate a response that:
- Expresses genuine concern and apologizes sincerely
- Never argues, deflects, or makes excuses
- Offers offline resolution with named manager and contact details
- Is 80–150 words
- Tone: empathetic, professional, ownership-taking
- Also: create internal escalation alert in Slack `#escalations`

### Step 4: Spam/Suspicious Review Detection
Flag a review as suspicious if:
- Reviewer has 0 prior reviews and no profile photo
- Review text is extremely generic (< 10 words, no specifics)
- Multiple reviews arrive from unrelated accounts within 24 hours
- Review is dramatically inconsistent with the service experience described
- Business name is mentioned incorrectly (competitor review bombing indicator)

For flagged reviews: log to `data/review_history.json` with status "dispute_flagged"
and send alert to `#gbp-alerts` Slack channel.

### Step 5: Review Velocity Campaign (Weekly — Fridays only)
Generate 1 WhatsApp-friendly review request message per location:
- Short (< 100 words), emoji-friendly, conversational
- Includes direct Google review link for that location
- Rotates template every 2 weeks (use `data/review_history.json` to track which template was last used)
- Save to `output/review_responses/review-request-YYYY-MM-DD-[location].txt`

### Step 6: Update Review Metrics
After processing all reviews, calculate:
- New review count per location
- Average rating update
- Response rate (% of all reviews that have responses)
- Review velocity (reviews in last 30 days)
- Sentiment trend (positive/neutral/negative keyword extraction)

Update `data/review_history.json` with all responses and metrics.

### Step 7: Benchmark Comparison
Compare current review metrics against top competitor per location:
- If competitor review velocity > MoveABox velocity: flag for escalation
- Calculate monthly review target: `(Top_Competitor_Count - MoveABox_Count) / 12 + 5`
- If MoveABox is on track: log "on track" in report
- If behind: generate "review velocity alert" for manager

### Step 8: Alert if Thresholds Breached
Trigger immediate Slack + WhatsApp alert if:
- Any location drops below 4.3 star average
- Review velocity drops > 30% week-over-week
- Any 1-star review mentions: "lost items", "damage", "fraud", "cheating", "police"

## Output Files
- `output/review_responses/YYYY-MM-DD-[location]-responses.json` — Queued responses
- `data/review_history.json` — Updated with new reviews and responses
- `reports/daily/YYYY-MM-DD.md` — Append review summary section

## Success Criteria
- All new reviews have generated responses (queued or published)
- 1–2 star reviews escalated to manager
- Suspicious reviews flagged for dispute
- Review metrics updated in data files
- Alerts sent for threshold breaches
