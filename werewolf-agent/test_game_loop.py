import asyncio
from unittest.mock import MagicMock, patch
from werewolf.game_manager import GameManager
from werewolf.models import PlayerProfile
async def test_game_loop():
    players = [
        PlayerProfile(id="p1", role_private="werewolf", alignment="wolves"),
        PlayerProfile(id="p2", role_private="villager", alignment="town"),
        PlayerProfile(id="p3", role_private="villager", alignment="town"),
        PlayerProfile(id="p4", role_private="detective", alignment="town"),
        PlayerProfile(id="p5", role_private="doctor", alignment="town"),
    ]
    
    config = {"max_words_day_talk": 100}
    
    # Mock httpx to return dummy responses
    with patch("httpx.AsyncClient") as mock_client:
        mock_post = MagicMock()
        mock_post.status_code = 200
        
        async def side_effect(*args, **kwargs):
            url = args[0] if args else kwargs.get("url")
            if "night_action" in url:
                return MagicMock(status_code=200, json=lambda: {"kill_vote": "p2", "inspect": "p1", "protect": "p2", "sleep": True})
            elif "discussion" in url:
                return MagicMock(status_code=200, json=lambda: {"talk": "I am innocent"})
            elif "vote" in url:
                return MagicMock(status_code=200, json=lambda: {"vote": "p1", "reason": "sus"})
            return MagicMock(status_code=404)

        mock_post.side_effect = side_effect
        mock_client.return_value.__aenter__.return_value.post = mock_post
        
        manager = GameManager(players, config)
        
        # We need to patch the _query_agent methods because they instantiate httpx.AsyncClient internally
        # Alternatively, we can just run it and let it fail/fallback if we didn't mock correctly, 
        # but mocking the internal calls is safer.
        
        # Actually, since I'm using `async with httpx.AsyncClient()`, patching the class should work.
        # However, `side_effect` needs to be async if it's an async method? 
        # No, `post` is awaitable.
        
        # Let's simplify and patch the _query_agent methods directly to avoid async mocking complexity
        with patch.object(manager, '_query_agent_night_action', side_effect=mock_night_action), \
             patch.object(manager, '_query_agent_discussion', return_value="I am innocent"), \
             patch.object(manager, '_query_agent_vote', side_effect=mock_vote):
             
            record = await manager.run_game()
            
            assert record is not None
            assert len(record.phases) > 0
            print("Game finished successfully")
            print("Winner:", record.final_result.winning_side)

async def mock_night_action(pid, prompt):
    role = prompt.role
    if role == "werewolf":
        return {"kill_vote": "p2"}
    elif role == "detective":
        return {"inspect": "p1"}
    elif role == "doctor":
        return {"protect": "p2"}
    return {"sleep": True}

async def mock_vote(pid, prompt):
    from werewolf.models import VoteResponse
    # Vote for the first available option that isn't self
    options = prompt.options
    target = next((o for o in options if o != pid), options[0])
    return VoteResponse(vote=target, one_sentence_reason="sus")

if __name__ == "__main__":
    asyncio.run(test_game_loop())
