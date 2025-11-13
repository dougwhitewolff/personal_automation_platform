# User Guide: Personal Automation Platform

## Quick Start

The platform automatically processes your Limitless Pendant transcripts and Discord messages to track your health, fitness, and nutrition data.

## How to Use

### Logging Data (Limitless Pendant)

Simply say **"Log that"** (or "track that", "log this") after describing what you did:

**Examples:**
- "I had a smoothie with protein powder and banana. Log that."
- "Just finished a 30-minute Peloton ride. Log that."
- "Drank 16 ounces of water. Log that."

The system will:
1. Detect "Log that" in your transcript
2. Automatically route to the right module (nutrition, workout, etc.)
3. Extract and store the data
4. Send a confirmation to Discord

### Asking Questions (Discord)

Ask questions naturally in Discord:

**Nutrition Questions:**
- "How much protein did I eat today?"
- "What did I have for breakfast?"
- "Show me my macros"

**Workout Questions:**
- "What workouts did I do this week?"
- "How many calories did I burn today?"

**General Questions:**
- "How do I track my macros?" (gets helpful guidance)
- "What's my daily summary?" (shows today's stats)

### Getting Summaries

Ask for summaries in natural language:

**In Discord:**
- "Show me my summary"
- "What did I do yesterday?"
- "Give me a summary for last week"
- "Show stats for 2024-01-15"

**In Limitless Transcripts:**
- "Show me my summary for today"
- "What did I do yesterday?"

The summary includes:
- Nutrition totals (calories, protein, carbs, fat)
- Workouts completed
- Sleep hours
- Bowel movements
- Water intake

## What Gets Tracked

### Nutrition Module
- Food items and meals
- Macros (calories, protein, carbs, fat, fiber)
- Hydration (water intake)
- Sleep (hours, quality, score)
- Health markers (weight, bowel movements)
- Supplements

### Workout Module
- Exercise type and duration
- Calories burned
- Peloton stats (strive score, output, heart rate)
- Training intensity

## Tips

1. **Be specific**: "I had a chicken breast with rice" is better than "I had lunch"
2. **Include amounts**: "16 ounces of water" is better than "some water"
3. **Use "Log that"**: Always end with "Log that" to trigger logging
4. **Ask naturally**: Questions work in Discord without special commands

## Commands

### Discord Commands
- `!summary [date]` - Get summary for a specific date (e.g., `!summary 2024-01-15`)
- `!help` - Show this guide

### Natural Language (No Commands Needed)
- "Log that" - Log the previous statement
- "Show me my summary" - Get today's summary
- "What did I do yesterday?" - Get yesterday's summary

## Out of Scope

The agent will politely refuse questions about:
- Weather
- News
- Politics
- General knowledge (unless related to health/fitness)
- Coding/software development

It focuses on personal automation: nutrition, fitness, health tracking, and productivity.

## Troubleshooting

**"No matching modules found"**
- Make sure you said "Log that" at the end
- Be more specific about what you did
- Check that the content is related to nutrition or workouts

**Summary not showing**
- Try: "Show me my summary for today"
- Or use the `!summary` command in Discord

**Data not being logged**
- Verify "Log that" was detected (check Discord notifications)
- Check that the module correctly identified your content
- Review the error message in Discord

## Need Help?

Check the Discord channel for error messages and confirmations. The system will notify you when:
- Data is successfully logged
- An error occurs
- No matching module is found

