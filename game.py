import random
from math import floor

from ursina import camera, Sky, Text, Ursina, Vec3, held_keys, raycast, window, mouse
from ursina.prefabs.first_person_controller import FirstPersonController

from game_world import World

RENDER_DISTANCE = 2
MAX_WORKERS = 6
SEED = random.randint(0, 2**32 - 1)
CHUNK_SIZE = 16
WORLD_LOWER_LIMIT = -32
WORLD_UPPER_LIMIT = 32


class VoxelGame:
    def __init__(self, render_distance, max_workers, seed, chunk_size, lower_limit, upper_limit):
        self.app = Ursina()
        window.fullscreen = False
        window.borderless = False
        window.fps_counter.enabled = True

        self.render_distance = render_distance

        self.sky = Sky()
        self.sky.texture = "textures/sky"

        self.world = World(max_workers, seed, chunk_size, lower_limit, upper_limit)

        self.player = FirstPersonController(enabled=False)
        # self.player.cursor.model =
        self.player_spawnpoint = Vec3(0, 0, 0)

        camera.fov = 70

        self.loading_screen = Text(
            text="Loading World, Please Wait...",
            position=(0, 0),
            origin=(0, 0),
            scale=1,
            background=True
        )

        self.initial_generation_complete = False
        self.stepped_generation = self.inital_generator()

        self.last_chunk_position = None
        self.chunks_to_generate = []

    def calculate_spawn_position(self):
        spawn_x, spawn_z = 0, 0
        spawn_y = WORLD_UPPER_LIMIT
        for y in range(WORLD_UPPER_LIMIT, WORLD_LOWER_LIMIT - 1, -1):
            if self.world.get_block(spawn_x, y, spawn_z) != 0:
                spawn_y = y + 2
                break
        self.player_spawnpoint = Vec3(spawn_x, spawn_y, spawn_z)

    def respawn_player(self):
        self.player.position = self.player_spawnpoint
        print(f"Player position set to: {self.player.position}")

    def spawn_player(self):
        self.calculate_spawn_position()
        self.respawn_player()
        self.player.enable()

    def input(self, key):
        if key == 'left mouse down':
            self.on_left_mouse_down()
        elif key == 'right mouse down':
            self.on_right_mouse_down()

    def on_left_mouse_down(self):
        if self.player.enabled:
            self.modify_block(1)

    def on_right_mouse_down(self):
        if self.player.enabled:
            self.modify_block(0)

    def modify_block(self, block_type):
        hit_info = raycast(self.player.position, self.player.forward, distance=5)
        if hit_info.hit:
            if not hit_info.entity:
                return
            block_pos = hit_info.entity.position + hit_info.normal * (0.5 if block_type == 1 else -0.5)
            x, y, z = int(block_pos.x), int(block_pos.y), int(block_pos.z)
            self.world.set_block(x, y, z, block_type)

    def update(self):
        if not self.initial_generation_complete:
            try:
                next(self.stepped_generation)
            except StopIteration:
                print("Initial world generation complete.")
                self.last_chunk_position = (0, 0, 0)
                self.stepped_generation = self.chunk_generator()
                self.loading_screen.enabled = False
                self.initial_generation_complete = True
                self.spawn_player()
            return

        if not self.player.enabled:
            return

        if self.chunks_to_generate:
            try:
                next(self.stepped_generation)
            except StopIteration:
                self.stepped_generation = self.chunk_generator()

        self.check_chunk_boundary()

        if self.player.position.y < WORLD_LOWER_LIMIT - 10:
            self.respawn_player()

        if held_keys['left mouse']:
            self.on_left_mouse_down()
        if held_keys['right mouse']:
            self.on_right_mouse_down()

    def inital_generator(self):
        spawn_x = 0
        spawn_z = 0
        spawn_chunk_x = spawn_x // CHUNK_SIZE
        spawn_chunk_z = spawn_z // CHUNK_SIZE

        required_chunks = []
        for dx in range(-self.render_distance, self.render_distance + 1):
            for dz in range(-self.render_distance, self.render_distance + 1):
                for dy in range(WORLD_UPPER_LIMIT // CHUNK_SIZE, WORLD_LOWER_LIMIT // CHUNK_SIZE - 1, -1):
                    required_chunks.append((spawn_chunk_x + dx, dy, spawn_chunk_z + dz))

        self.chunks_to_generate = required_chunks
        yield from self.chunk_generator()

    def chunk_generator(self):
        while self.chunks_to_generate:
            chunk_pos = self.chunks_to_generate.pop()
            chunk = self.world.get_chunk(*chunk_pos)
            if chunk:
                if chunk.blocks is None:
                    yield from self.world.generate_chunk_terrain_async(chunk)
                if chunk.needs_update and chunk.blocks is not None:
                    yield from self.world.generate_chunk_mesh_async(chunk)
            else:
                print(f"Chunk not found: {chunk_pos}")

    def check_chunk_boundary(self):
        player_pos = self.player.position
        current_chunk_position = (
            floor(player_pos.x / CHUNK_SIZE),
            floor(player_pos.y / CHUNK_SIZE),
            floor(player_pos.z / CHUNK_SIZE)
        )
        if current_chunk_position == self.last_chunk_position:
            return
        self.last_chunk_position = current_chunk_position
        self.chunks_to_generate = self.world.load_chunks(current_chunk_position, self.render_distance)

    def run(self):
        self.app.run()


if __name__ == '__main__':
    game = VoxelGame(RENDER_DISTANCE, MAX_WORKERS, SEED, CHUNK_SIZE, WORLD_LOWER_LIMIT, WORLD_UPPER_LIMIT)

    def update():
        game.update()

    game.run()
