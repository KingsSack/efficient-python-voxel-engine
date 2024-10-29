import random
from math import floor

from ursina import camera, Sky, Text, Ursina, window, mouse, color

from src.game_player import Player
from src.game_world import WorldController

RENDER_DISTANCE = 2
MAX_WORKERS = 6
SEED = random.randint(0, 2**32 - 1)
CHUNK_SIZE = 16
WORLD_LOWER_LIMIT = -32
WORLD_UPPER_LIMIT = 32


class VoxelGame:
    def __init__(self, render_distance, max_workers, seed, chunk_size, world_lower_limit, world_upper_limit):
        self.app = Ursina()
        window.fullscreen = False
        window.borderless = False
        window.fps_counter.enabled = True

        self.render_distance = render_distance

        self.sky = Sky()
        self.sky.texture = "textures/skybox"

        self.world = WorldController(render_distance, max_workers, seed, chunk_size, world_lower_limit, world_upper_limit)

        self.player = Player(self.world)

        camera.fov = 70

        self.loading_screen = Text(
            text="Loading World, Please Wait...",
            position=(0, 0),
            origin=(0, 0),
            scale=1,
            background=True
        )

        self.last_chunk_position = None

        # try:
        #     self.initialize_game()
        # except Exception as e:
        #     print(f"Failed to initialize game: {e}")
        #     self.cleanup()
        #     raise

    def input(self, key):
        if key == 'left mouse down':
            self.player.on_left_mouse_down()
        elif key == 'right mouse down':
            self.player.on_right_mouse_down()

    def update(self):
        if not self.world.initial_generation_complete:
            try:
                next(self.world.stepped_generation)
            except StopIteration:
                self.loading_complete()
            return

        if not self.player.enabled:
            return

        if self.world.chunks_to_generate:
            try:
                next(self.world.stepped_generation)
            except StopIteration:
                self.world.stepped_generation = self.world.chunk_generator()

        self.player.update()
        self.world.update()
        self.check_chunk_boundary()

    def loading_complete(self):
        print("Initial world generation complete.")
        self.world.stepped_generation = self.world.chunk_generator()
        self.world.initial_generation_complete = True
        self.loading_screen.enabled = False

        self.player.spawnpoint = self.player.calculate_spawn_position()
        print(f"Player spawnpoint set to: {self.player.spawnpoint}")
        self.player.spawn()

    def check_chunk_boundary(self):
        player_pos = self.player.position
        current_chunk_position = (
            floor(player_pos.x / self.world.chunk_size),
            floor(player_pos.y / self.world.chunk_size),
            floor(player_pos.z / self.world.chunk_size)
        )
        if current_chunk_position == self.last_chunk_position:
            return
        self.last_chunk_position = current_chunk_position
        self.chunks_to_generate = self.world.load_chunks(current_chunk_position, self.render_distance)

    def cleanup(self):
        # Cleanup resources
        if hasattr(self, 'world'):
            self.world.executor.shutdown()

    def run(self):
        self.app.run()


if __name__ == '__main__':
    game = VoxelGame(RENDER_DISTANCE, MAX_WORKERS, SEED, CHUNK_SIZE, WORLD_LOWER_LIMIT, WORLD_UPPER_LIMIT)

    def update():
        game.update()

    def input(key):
        game.input(key)

    game.run()
