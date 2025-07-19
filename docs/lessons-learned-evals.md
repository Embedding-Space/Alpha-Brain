# Lessons Learned: Entity Extraction Evaluations

## Key Insights

### Models Read JSON and Write Prose
- Small models (like Llama 3.2) struggle to output valid JSON consistently
- Switching from JSON to Markdown format improved F1 scores from 0.131 to ~0.70 (400% improvement!)
- Models are much better at reading comprehension than structured data generation

### The Interview Approach Wins
- Sequential questions ("Who is mentioned?") work better than batch extraction
- Single GPU = single inference anyway, so no performance penalty
- Treating the helper model like "Lil Brudder" who answers simple questions is more reliable
- Reading comprehension > complex prompting

### Real Data vs Synthetic Data
- Synthetic data gave us 90%+ F1 scores
- Real STM data dropped to 81% best F1
- Small F1 differences = massive quality differences in practice

### PydanticAI Evaluation Framework
- `Dataset` → `Case` → `Evaluator` pattern is clean and effective
- Built-in metrics (precision, recall, F1) are valuable
- Directory-based prompt testing worked well
- The pydantic-evals package is powerful for future prompt engineering

### Temperature Matters
- Setting temperature=0 is crucial for consistent extraction
- Deterministic output makes debugging much easier

### What Didn't Work
- Complex system prompts with detailed instructions
- Trying to extract everything in one shot
- JSON output format with small models
- Backward compatibility (just added cruft)

## Future Approach

When we need evaluations again:
1. Create a dedicated workspace for prompt engineering
2. Use PydanticAI's evaluation framework
3. Test on real data, not just synthetic
4. Remember: simple questions > complex prompts
5. Markdown output > JSON for small models

## The Bottom Line

Extra data is truly "extra" - the system functions on embeddings alone. Any metadata we extract is a bonus, not a requirement. This makes the system robust and graceful in its degradation.