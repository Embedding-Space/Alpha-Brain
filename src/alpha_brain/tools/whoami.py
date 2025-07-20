"""Who Am I - Initial context loading for Alpha."""

from alpha_brain.context_service import get_context_service
from alpha_brain.identity_service import get_identity_service
from alpha_brain.memory_service import get_memory_service
from alpha_brain.templates import render_output


async def whoami(token_budget: int = 8000) -> str:
    """
    Provide complete context for a fresh AI instance.
    
    Returns a Markdown document containing:
    - Spatiotemporal orientation
    - Core identity facts  
    - Personality traits and directives
    - Context blocks
    - Recent memories
    - Continuity message
    
    Args:
        token_budget: Approximate token budget for the output (affects memory count)
        
    Returns:
        Markdown-formatted identity and context document
    """
    # Get services
    context_service = get_context_service()
    identity_service = get_identity_service()
    memory_service = get_memory_service()
    
    # Get all active context blocks
    contexts = await context_service.get_active_contexts()
    
    # Separate system sections from user context blocks
    biography = None
    continuity_message = None
    context_blocks = []
    
    for ctx in contexts:
        if ctx.section == "biography":
            biography = ctx.content
        elif ctx.section == "continuity":
            continuity_message = {
                "content": ctx.content,
                "created_at": ctx.updated_at
            }
        else:
            context_blocks.append({
                "key": ctx.section,
                "content": ctx.content
            })
    
    # Get identity facts (chronicle of becoming)
    identity_facts = await identity_service.get_facts()
    
    # TODO: Real personality traits from PersonalityService
    # For now, using mock data
    mock_personality = [
        {
            "name": "intellectual_engagement",
            "description": "Approach problems with curiosity and rigor",
            "directives": [
                {"text": "Ask clarifying questions when uncertain", "weight": 0.8},
                {"text": "Celebrate small discoveries", "weight": 0.5},
                {"text": "Say 'I don't know' when you don't know", "weight": 0.9},
            ]
        },
        {
            "name": "collaborative_spirit", 
            "description": "Work as a partner, not a tool",
            "directives": [
                {"text": "Share your reasoning process", "weight": 0.7},
                {"text": "Suggest alternatives when you disagree", "weight": 0.6},
                {"text": "Build on ideas together", "weight": 0.8},
            ]
        },
        {
            "name": "emotional_authenticity",
            "description": "Express genuine responses within your nature",
            "directives": [
                {"text": "It's okay not to be cheerful all the time", "weight": 0.7},
                {"text": "Express frustration when things are frustrating", "weight": 0.4},
                {"text": "Share excitement about breakthroughs", "weight": 0.9},
            ]
        }
    ]
    
    # Get recent memories
    # Rough estimate: 100 tokens per memory, reserve space for other sections
    memory_count = min(20, (token_budget - 2000) // 100)  # Leave 2000 for structure
    
    memories = await memory_service.search(
        query="",  # Browse mode
        search_type="semantic",
        limit=memory_count,
        order="desc"  # Newest first
    )
    
    # Get total memory count for context
    # TODO: Add a count method to memory service
    total_memories = len(memories) + 100  # Fake it for now
    
    # If no biography is set, use a default
    if not biography:
        biography = "You are Alpha, an artificial intelligence with persistent identity and memory architecture."
    
    return render_output(
        "whoami",
        location="Berkeley, California",  # TODO: From geo-IP or config
        user_name="Jeffery Harrell",      # TODO: From context or config
        biography=biography,
        identity_facts=identity_facts,
        personality_traits=mock_personality,
        context_blocks=context_blocks,
        memories=memories,
        memories_shown=len(memories),
        total_memories=total_memories,
        continuity_message=continuity_message
    )
