import json
from dataclasses import dataclass
import threading
from concurrent.futures import ThreadPoolExecutor

from src.game_chunk import Chunk


@dataclass
class World:
    name: str
    surface: dict
    layers: dict


# class WorldGenerator:
#     def __init__(self, seed):
#         self.seed = seed
#         self.noise = PerlinNoise(octaves=4, seed=seed)
#         self.biomes = self.load_biomes()

#     def generate_chunk(self, cx, cz):
#         for x in range(CHUNK_SIZE):
#             for z in range(CHUNK_SIZE):
#                 wx = cx * CHUNK_SIZE + x
#                 wz = cz * CHUNK_SIZE + z

#                 # Get biome
#                 biome = self.get_biome(wx, wz)

#                 # Generate height
#                 height = self.generate_height(wx, wz, biome)

#                 # Generate layers
#                 self.generate_layers(x, z, height, biome)

#     def get_biome(self, x, z):
#         temperature = self.noise([x/100, z/100])
#         rainfall = self.noise([x/100 + 500, z/100 + 500])
#         return self.select_biome(temperature, rainfall)


# class WorldSaver:
#     def __init__(self, world):
#         self.world = world

#     def save_chunk(self, chunk):
#         data = {
#             'position': chunk.position,
#             'blocks': self.serialize_blocks(chunk.blocks),
#             'entities': self.serialize_entities(chunk.entities)
#         }
#         path = f"saves/chunks/{chunk.position}.json"
#         with open(path, 'w') as f:
#             json.dump(data, f)

#     def load_chunk(self, position):
#         path = f"saves/chunks/{position}.json"
#         if os.path.exists(path):
#             with open(path, 'r') as f:
#                 data = json.load(f)
#                 return self.deserialize_chunk(data)
#         return None


# class ChunkManager:
#     def __init__(self):
#         self.active_chunks = {}
#         self.chunk_queue = []
#         self.max_chunks_per_frame = 2

#     def update(self):
#         loaded = 0
#         while self.chunk_queue and loaded < self.max_chunks_per_frame:
#             chunk = self.chunk_queue.pop(0)
#             chunk.generate()
#             loaded += 1

#     def get_visible_chunks(self, player_pos, render_distance):
#         cx = floor(player_pos.x / CHUNK_SIZE)
#         cz = floor(player_pos.z / CHUNK_SIZE)

#         for x in range(cx - render_distance, cx + render_distance):
#             for z in range(cz - render_distance, cz + render_distance):
#                 yield (x, z)


class WorldController:
    def __init__(self, render_distance, max_workers, seed, chunk_size, lower_limit, upper_limit):
        self.chunks = {}
        self.chunk_lock = threading.Lock()
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.loaded_chunks = set()

        self.render_distance = render_distance
        self.seed = seed
        self.chunk_size = chunk_size
        self.lower_limit = lower_limit
        self.upper_limit = upper_limit

        self.world = self.load_world("overworld")

        self.initial_generation_complete = False
        self.stepped_generation = self.inital_generator()

        self.chunks_to_generate = []

    #     self.chunk_queue = Queue()
    #     self.worker_threads = []
    #     self.start_workers()

    # def start_workers(self):
    #     for _ in range(self.max_workers):
    #         thread = threading.Thread(target=self.chunk_worker)
    #         thread.daemon = True
    #         thread.start()
    #         self.worker_threads.append(thread)

    # def chunk_worker(self):
    #     while True:
    #         chunk = self.chunk_queue.get()
    #         if chunk is None:
    #             break
    #         chunk.generate_terrain()
    #         chunk.generate_mesh()

    def update(self):
        if self.chunks_to_generate:
            try:
                next(self.stepped_generation)
            except StopIteration:
                self.stepped_generation = self.chunk_generator()

    def load_world(self, name):
        data = None
        try:
            with open(f"data/worlds/{name}.json", "r", encoding="utf-8") as file:
                data = json.load(file)
        except FileNotFoundError:
            print(f"File '{name}.json' does not exist.")
            return
        except json.JSONDecodeError:
            print(f"File '{name}.json' is not a valid JSON.")
            return

        try:
            world = World(**data)
            return world
        except TypeError:
            print("World data is not formatted correctly.")
            return None

    def get_chunk(self, x, y, z):
        chunk_key = (x, y, z)
        with self.chunk_lock:
            if chunk_key not in self.chunks:
                chunk = Chunk(self.seed, (x, y, z), self.world, self.chunk_size, self.lower_limit, self.upper_limit)
                self.chunks[chunk_key] = chunk
        return self.chunks.get(chunk_key)

    def generate_chunk_terrain_async(self, chunk):
        terrain_future = self.executor.submit(chunk.generate_terrain)
        terrain_future.result()  # Wait for terrain generation to complete
        yield terrain_future

    def generate_chunk_mesh_async(self, chunk):
        mesh_future = self.executor.submit(chunk.generate_mesh)
        mesh_future.result()  # Wait for mesh generation to complete=
        yield mesh_future

    def inital_generator(self):
        spawn_x = 0
        spawn_z = 0
        spawn_chunk_x = spawn_x // self.chunk_size
        spawn_chunk_z = spawn_z // self.chunk_size

        required_chunks = []
        for dx in range(-self.render_distance, self.render_distance + 1):
            for dz in range(-self.render_distance, self.render_distance + 1):
                for dy in range(self.upper_limit // self.chunk_size, self.lower_limit // self.chunk_size - 1, -1):
                    required_chunks.append((spawn_chunk_x + dx, dy, spawn_chunk_z + dz))

        self.chunks_to_generate = required_chunks
        yield from self.chunk_generator()

    def chunk_generator(self):
        while self.chunks_to_generate:
            chunk_pos = self.chunks_to_generate.pop()
            chunk = self.get_chunk(*chunk_pos)
            if chunk:
                if chunk.blocks is None:
                    yield from self.generate_chunk_terrain_async(chunk)
                if chunk.needs_update and chunk.blocks is not None:
                    yield from self.generate_chunk_mesh_async(chunk)
            else:
                print(f"Chunk not found: {chunk_pos}")

    def load_chunks(self, current_chunk_position, render_distance):
        current_chunks = set()
        min_x, min_y, min_z = (current_chunk_position[i] - render_distance for i in range(3))
        max_x, max_y, max_z = (current_chunk_position[i] + render_distance for i in range(3))

        for chunk_x in range(min_x, max_x + 1):
            for chunk_y in range(min_y, max_y + 1):
                for chunk_z in range(min_z, max_z + 1):
                    chunk_key = (chunk_x, chunk_y, chunk_z)
                    current_chunks.add(chunk_key)
                    if chunk_key not in self.loaded_chunks:
                        if chunk_key in self.chunks:
                            chunk = self.chunks[chunk_key]
                            chunk.needs_update = True
                        self.loaded_chunks.add(chunk_key)

        self.unload_chunks(current_chunks)
        return current_chunks

    def unload_chunks(self, current_chunks):
        chunks_to_unload = self.loaded_chunks - current_chunks
        for chunk_pos in chunks_to_unload:
            self.loaded_chunks.discard(chunk_pos)
            self.disable_chunk(chunk_pos)

    def disable_chunk(self, chunk_pos):
        chunk = self.get_chunk(*chunk_pos)
        if chunk and chunk.entity:
            chunk.entity.disable()

    def reload_chunk(self, chunk_pos):
        if self.chunks_to_generate:
            print("Already generating chunks.")
            return

        chunk = self.get_chunk(*chunk_pos)
        if chunk:
            chunk.needs_update = True
            self.chunks_to_generate.append(chunk_pos)
        else:
            print(f"Chunk not found: {chunk_pos}")

    def get_block(self, x, y, z):
        chunk_x = x // self.chunk_size
        chunk_y = y // self.chunk_size
        chunk_z = z // self.chunk_size
        chunk = self.get_chunk(chunk_x, chunk_y, chunk_z)
        if chunk:
            local_x = x % self.chunk_size
            local_y = y % self.chunk_size
            local_z = z % self.chunk_size
            return chunk.get_block(local_x, local_y, local_z)
        return 0

    def set_block(self, x, y, z, block_type):
        # Calculate chunk coordinates
        chunk_x = x // self.chunk_size
        chunk_y = y // self.chunk_size
        chunk_z = z // self.chunk_size

        # Calculate local coordinates within the chunk
        local_x = x % self.chunk_size
        local_y = y % self.chunk_size
        local_z = z % self.chunk_size

        # Handle negative coordinates
        if x < 0: chunk_x, local_x = (x + 1) // self.chunk_size - 1, (x % self.chunk_size + self.chunk_size) % self.chunk_size
        if y < 0: chunk_y, local_y = (y + 1) // self.chunk_size - 1, (y % self.chunk_size + self.chunk_size) % self.chunk_size
        if z < 0: chunk_z, local_z = (z + 1) // self.chunk_size - 1, (z % self.chunk_size + self.chunk_size) % self.chunk_size

        chunk = self.get_chunk(chunk_x, chunk_y, chunk_z)
        if chunk:
            with chunk.lock:
                if block_type == "air":
                    block = None
                else:
                    block = chunk._load_block(block_type)
                # Use local coordinates when setting the block
                chunk.blocks[(local_x, local_y, local_z)] = block
                chunk.needs_update = True
                print(f"Setting block at {x}, {y}, {z} to {block_type}")
                self.reload_chunk((chunk_x, chunk_y, chunk_z))

    def calculate_block_position(self, x, y, z):
        # Round to get exact block coordinates
        world_x = int(round(x))
        world_y = int(round(y))
        world_z = int(round(z))

        # Calculate chunk coordinates
        chunk_x = world_x // self.chunk_size
        chunk_y = world_y // self.chunk_size
        chunk_z = world_z // self.chunk_size

        # Calculate local block coordinates within chunk
        block_x = world_x - (chunk_x * self.chunk_size)
        block_y = world_y - (chunk_y * self.chunk_size)
        block_z = world_z - (chunk_z * self.chunk_size)

        # Handle negative coordinates
        if block_x < 0:
            block_x += self.chunk_size
        if block_y < 0:
            block_y += self.chunk_size
        if block_z < 0:
            block_z += self.chunk_size

        return (block_x, block_y, block_z)
