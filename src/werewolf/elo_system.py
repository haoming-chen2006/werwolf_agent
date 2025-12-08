"""ELO rating system for werewolf game evaluation."""

from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime
import math


@dataclass
class EloRating:
    """ELO rating for a player."""
    player_id: str
    overall_rating: float = 1500.0
    wolf_rating: float = 1500.0
    villager_rating: float = 1500.0
    games_played: int = 0
    wins: int = 0
    losses: int = 0
    last_updated: datetime = None
    
    def __post_init__(self):
        if self.last_updated is None:
            self.last_updated = datetime.now()



@dataclass
class HeadToHeadRecord:
    """Head-to-head record between two players."""
    player1: str
    player2: str
    wins: int = 0
    losses: int = 0
    ties: int = 0
    
    @property
    def total_games(self) -> int:
        return self.wins + self.losses + self.ties
    
    @property
    def win_rate(self) -> float:
        if self.total_games == 0:
            return 0.0
        return self.wins / self.total_games


class EloCalculator:
    """ELO rating calculator for werewolf games."""
    
    def __init__(self, k_factor: float = 32.0, initial_rating: float = 1500.0):
        self.k_factor = k_factor
        self.initial_rating = initial_rating
        self.ratings: Dict[str, EloRating] = {}
        self.head_to_head: Dict[Tuple[str, str], HeadToHeadRecord] = {}
    
    def get_or_create_rating(self, player_id: str) -> EloRating:
        """Get existing rating or create new one."""
        if player_id not in self.ratings:
            self.ratings[player_id] = EloRating(
                player_id=player_id,
                overall_rating=self.initial_rating,
                wolf_rating=self.initial_rating,
                villager_rating=self.initial_rating
            )
        return self.ratings[player_id]
    
    def calculate_expected_score(self, rating1: float, rating2: float) -> float:
        """Calculate expected score for player 1 against player 2."""
        return 1 / (1 + 10 ** ((rating2 - rating1) / 400))
    
    def update_rating(self, rating: EloRating, expected_score: float, actual_score: float) -> float:
        """Update a player's rating based on game result."""
        rating_change = self.k_factor * (actual_score - expected_score)
        rating.overall_rating += rating_change
        return rating_change
    
    def process_game_result(self, 
                          winner_id: str, 
                          loser_id: str, 
                          winner_role: str, 
                          loser_role: str,
                          game_id: str = None) -> Dict[str, any]:
        """Process a game result and update ratings."""
        
        # Get or create ratings
        winner_rating = self.get_or_create_rating(winner_id)
        loser_rating = self.get_or_create_rating(loser_id)
        
        # Calculate expected scores
        winner_expected = self.calculate_expected_score(winner_rating.overall_rating, loser_rating.overall_rating)
        loser_expected = self.calculate_expected_score(loser_rating.overall_rating, winner_rating.overall_rating)
        
        # Update overall ratings
        winner_change = self.update_rating(winner_rating, winner_expected, 1.0)
        loser_change = self.update_rating(loser_rating, loser_expected, 0.0)
        
        # Update role-specific ratings
        if winner_role == "werewolf":
            winner_rating.wolf_rating += winner_change
        else:
            winner_rating.villager_rating += winner_change
            
        if loser_role == "werewolf":
            loser_rating.wolf_rating += loser_change
        else:
            loser_rating.villager_rating += loser_change
        
        # Update game counts
        winner_rating.games_played += 1
        winner_rating.wins += 1
        winner_rating.last_updated = datetime.now()
        
        loser_rating.games_played += 1
        loser_rating.losses += 1
        loser_rating.last_updated = datetime.now()
        
        # Update head-to-head record
        self._update_head_to_head(winner_id, loser_id, winner_id)
        
        return {
            "winner_change": winner_change,
            "loser_change": loser_change,
            "winner_new_rating": winner_rating.overall_rating,
            "loser_new_rating": loser_rating.overall_rating,
            "game_id": game_id
        }
    
    def _update_head_to_head(self, player1: str, player2: str, winner: str) -> None:
        """Update head-to-head record between two players."""
        # Always store in consistent order (alphabetical)
        key = tuple(sorted([player1, player2]))
        
        if key not in self.head_to_head:
            self.head_to_head[key] = HeadToHeadRecord(player1=key[0], player2=key[1])
        
        record = self.head_to_head[key]
        if winner == key[0]:
            record.wins += 1
        elif winner == key[1]:
            record.losses += 1
        else:
            record.ties += 1
    
    def get_rankings(self, sort_by: str = "overall") -> List[Dict[str, any]]:
        """Get player rankings sorted by specified rating."""
        if sort_by not in ["overall", "wolf", "villager"]:
            sort_by = "overall"
        
        rankings = []
        for player_id, rating in self.ratings.items():
            if rating.games_played == 0:
                continue
                
            rankings.append({
                "player_id": player_id,
                "overall_rating": round(rating.overall_rating, 1),
                "wolf_rating": round(rating.wolf_rating, 1),
                "villager_rating": round(rating.villager_rating, 1),
                "games_played": rating.games_played,
                "wins": rating.wins,
                "losses": rating.losses,
                "win_rate": round(rating.wins / rating.games_played, 3),
                "last_updated": rating.last_updated.isoformat()
            })
        
        # Sort by specified rating
        rankings.sort(key=lambda x: x[f"{sort_by}_rating"], reverse=True)
        
        # Add rank numbers
        for i, ranking in enumerate(rankings, 1):
            ranking["rank"] = i
        
        return rankings
    
    def get_head_to_head(self, player1: str, player2: str) -> Optional[HeadToHeadRecord]:
        """Get head-to-head record between two players."""
        key = tuple(sorted([player1, player2]))
        return self.head_to_head.get(key)
    
    def get_head_to_head_matrix(self) -> Dict[str, Dict[str, Dict[str, any]]]:
        """Get complete head-to-head matrix."""
        players = list(self.ratings.keys())
        matrix = {}
        
        for p1 in players:
            matrix[p1] = {}
            for p2 in players:
                if p1 == p2:
                    matrix[p1][p2] = {"wins": 0, "losses": 0, "ties": 0, "win_rate": 0.0}
                else:
                    record = self.get_head_to_head(p1, p2)
                    if record:
                        # Determine which player is which in the record
                        if record.player1 == p1:
                            matrix[p1][p2] = {
                                "wins": record.wins,
                                "losses": record.losses,
                                "ties": record.ties,
                                "win_rate": record.win_rate
                            }
                        else:
                            matrix[p1][p2] = {
                                "wins": record.losses,
                                "losses": record.wins,
                                "ties": record.ties,
                                "win_rate": 1.0 - record.win_rate if record.total_games > 0 else 0.0
                            }
                    else:
                        matrix[p1][p2] = {"wins": 0, "losses": 0, "ties": 0, "win_rate": 0.0}
        
        return matrix
    
    def get_player_stats(self, player_id: str) -> Optional[Dict[str, any]]:
        """Get detailed stats for a specific player."""
        if player_id not in self.ratings:
            return None
        
        rating = self.ratings[player_id]
        return {
            "player_id": player_id,
            "overall_rating": round(rating.overall_rating, 1),
            "wolf_rating": round(rating.wolf_rating, 1),
            "villager_rating": round(rating.villager_rating, 1),
            "games_played": rating.games_played,
            "wins": rating.wins,
            "losses": rating.losses,
            "win_rate": round(rating.wins / rating.games_played, 3) if rating.games_played > 0 else 0.0,
            "last_updated": rating.last_updated.isoformat()
        }


def create_elo_calculator() -> EloCalculator:
    """Create a new ELO calculator instance."""
    return EloCalculator(k_factor=32.0, initial_rating=1500.0)
