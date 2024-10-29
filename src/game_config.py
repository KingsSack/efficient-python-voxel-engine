from dataclasses import dataclass


@dataclass
class GameConfig:
    render_distance: int = 2
    max_workers: int = 6
    seed: int = 0
    chunk_size: int = 16
    world_lower_limit: int = -32
    world_upper_limit: int = 32
