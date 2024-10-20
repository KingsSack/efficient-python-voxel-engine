import random
import threading
from concurrent.futures import ThreadPoolExecutor
from math import floor

import numpy as np
from perlin_noise import PerlinNoise
from ursina import (Entity, Mesh, Text, Ursina, Vec3, color, held_keys,
                    raycast, scene, window)
from ursina.prefabs.first_person_controller import FirstPersonController

CHUNK_SIZE = 16
RENDER_DISTANCE = 2
SEED = 12345
MAX_WORKERS = 4
WORLD_LOWER_LIMIT = -32
WORLD_UPPER_LIMIT = 32
CHUNKS_PER_FRAME = 1


class Chunk:
    def __init__(self, position, world):
        self.position = position
        self.world = world
        self.mesh = None
        self.entity = None
        self.blocks = None
        self.needs_update = True
        self.lock = threading.Lock()

    def generate_terrain(self):
        if self.blocks is not None:
            return
        with self.lock:
            self.blocks = np.zeros((CHUNK_SIZE, CHUNK_SIZE, CHUNK_SIZE), dtype=np.uint8)
            noise = PerlinNoise(octaves=4, seed=SEED)
            for x in range(CHUNK_SIZE):
                for z in range(CHUNK_SIZE):
                    world_x = x + self.position[0] * CHUNK_SIZE
                    world_z = z + self.position[2] * CHUNK_SIZE
                    height = int((noise([world_x / 100, world_z / 100]) + 1) * WORLD_UPPER_LIMIT / 2)
                    for y in range(CHUNK_SIZE):
                        world_y = self.position[1] * CHUNK_SIZE + y
                        if WORLD_LOWER_LIMIT <= world_y < min(height, WORLD_UPPER_LIMIT):
                            self.blocks[x, y, z] = 1
                        else:
                            self.blocks[x, y, z] = 0
            self.needs_update = True

    def generate_mesh(self):
        if not self.needs_update or self.blocks is None:
            return

        with self.lock:
            vertices = []
            triangles = []
            uvs = []
            vertex_count = 0
            for x in range(CHUNK_SIZE):
                for y in range(CHUNK_SIZE):
                    for z in range(CHUNK_SIZE):
                        if self.blocks[x, y, z]:
                            for face in range(6):
                                if self.is_face_visible(x, y, z, face):
                                    verts = self.get_face_vertices(x, y, z, face)
                                    vertices.extend(verts)
                                    tri = self.get_face_triangles(vertex_count)
                                    triangles.extend(tri)
                                    uvs.extend([(0, 0), (1, 0), (1, 1), (0, 1)])
                                    vertex_count += 4
            if not vertices:
                if self.entity:
                    self.entity.disable()
                self.mesh = None
                self.needs_update = False
                return
            self.mesh = Mesh(vertices=vertices, triangles=triangles, uvs=uvs, static=False)
            if not self.entity:
                self.entity = Entity(
                    parent=scene,
                    model=self.mesh,
                    position=Vec3(*self.position) * CHUNK_SIZE,
                    texture='test',
                    color=color.hsv(0, 0, random.uniform(.9, 1.0)),
                    collider='mesh'
                )
            else:
                self.entity.model = self.mesh
                self.entity.enable()

            self.needs_update = False

    def is_face_visible(self, x, y, z, face):
        neighbor_offsets = [
            (0, 0, -1),  # front
            (0, 0, 1),   # back
            (-1, 0, 0),  # left
            (1, 0, 0),   # right
            (0, -1, 0),  # bottom
            (0, 1, 0)    # top
        ]
        dx, dy, dz = neighbor_offsets[face]
        nx, ny, nz = x + dx, y + dy, z + dz

        if 0 <= nx < CHUNK_SIZE and 0 <= ny < CHUNK_SIZE and 0 <= nz < CHUNK_SIZE:
            return not self.blocks[nx, ny, nz]  # If neighbor block is empty, face is visible
        else:
            return True

    @staticmethod
    def get_face_vertices(x, y, z, face):
        v = [
            # bottom left          bottom right         top right            top left
            # 0                    1                    2                    3
            Vec3(x, y, z),       Vec3(x+1, y, z),     Vec3(x+1, y+1, z),   Vec3(x, y+1, z),  # front
            # 4                    5                    6                    7
            Vec3(x, y, z+1),     Vec3(x+1, y, z+1),   Vec3(x+1, y+1, z+1), Vec3(x, y+1, z+1)  # back
        ]
        face_indices = [
            [0, 1, 2, 3],  # front
            [7, 6, 5, 4],  # back
            [3, 7, 4, 0],  # left
            [1, 5, 6, 2],  # right
            [4, 5, 1, 0],  # bottom
            [3, 2, 6, 7]   # top
        ]
        return [v[i] for i in face_indices[face]]

    @staticmethod
    def get_face_triangles(start):
        return [start + 0, start + 1, start + 2, start + 0, start + 2, start + 3]

    def get_block(self, x, y, z):
        if self.blocks is None:
            return 0

        if 0 <= x < CHUNK_SIZE and 0 <= y < CHUNK_SIZE and 0 <= z < CHUNK_SIZE:
            return self.blocks[x, y, z]
        else:
            return 0


class World:
    def __init__(self):
        self.chunks = {}
        self.chunk_lock = threading.Lock()
        self.executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)
        self.loaded_chunks = set()

    def get_chunk(self, x, y, z):
        chunk_key = (x, y, z)
        if chunk_key not in self.loaded_chunks:
            with self.chunk_lock:
                if chunk_key not in self.chunks:
                    chunk = Chunk((x, y, z), self)
                    self.chunks[chunk_key] = chunk
                self.loaded_chunks.add(chunk_key)
        return self.chunks.get(chunk_key)

    # def _generate_chunk_async(self, chunk):
    #     chunk.generate_terrain()
    #     chunk.generate_mesh()

    def generate_terrain_async(self, chunk):
        terrain_future = self.executor.submit(chunk.generate_terrain)
        terrain_future.result()  # Wait for terrain generation to complete
        yield terrain_future

    def generate_mesh_async(self, chunk):
        mesh_future = self.executor.submit(chunk.generate_mesh)
        mesh_future.result()  # Wait for mesh generation to complete
        yield mesh_future

    def unload_distant_chunks(self, current_chunks):
        chunks_to_unload = self.loaded_chunks - current_chunks
        with self.chunk_lock:
            for chunk_pos in chunks_to_unload:
                chunk = self.chunks.pop(chunk_pos, None)
                if chunk and chunk.entity:
                    chunk.entity.disable()
            self.loaded_chunks = current_chunks

    def get_block(self, x, y, z):
        chunk_x = x // CHUNK_SIZE
        chunk_y = y // CHUNK_SIZE
        chunk_z = z // CHUNK_SIZE
        chunk = self.get_chunk(chunk_x, chunk_y, chunk_z)
        if chunk:
            local_x = x % CHUNK_SIZE
            local_y = y % CHUNK_SIZE
            local_z = z % CHUNK_SIZE
            return chunk.get_block(local_x, local_y, local_z)
        return 0

    def set_block(self, x, y, z, block_type):
        chunk_x = x // CHUNK_SIZE
        chunk_y = y // CHUNK_SIZE
        chunk_z = z // CHUNK_SIZE
        chunk = self.get_chunk(chunk_x, chunk_y, chunk_z)
        if chunk:
            local_x = x % CHUNK_SIZE
            local_y = y % CHUNK_SIZE
            local_z = z % CHUNK_SIZE
            with chunk.lock:
                chunk.blocks[local_x, local_y, local_z] = block_type
                chunk.needs_update = True

            self._update_neighbor_chunks(chunk_x, chunk_y, chunk_z)

    def _update_neighbor_chunks(self, chunk_x, chunk_y, chunk_z):
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                for dz in [-1, 0, 1]:
                    if dx != 0 or dy != 0 or dz != 0:
                        neighbor_chunk = self.get_chunk(chunk_x + dx, chunk_y + dy, chunk_z + dz)
                        if neighbor_chunk:
                            neighbor_chunk.needs_update = True


class VoxelGame:
    def __init__(self, render_distance):
        self.app = Ursina()
        window.fullscreen = False
        window.borderless = False
        window.fps_counter.enabled = True

        self.render_distance = render_distance

        self.world = World()

        self.player = FirstPersonController(enabled=False)
        self.player_spawnpoint = Vec3(0, 0, 0)

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
                spawn_y = y + 4
                break
        self.player_spawnpoint = Vec3(spawn_x, spawn_y, spawn_z)
        print(f"Spawnpoint set to: ({self.player_spawnpoint})")

    def respawn_player(self):
        self.player.position = self.player_spawnpoint
        print(f"Player respawned at: {self.player.position}")

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
            block_pos = hit_info.entity.position + hit_info.normal * (0.5 if block_type == 1 else -0.5)
            x, y, z = int(block_pos.x), int(block_pos.y), int(block_pos.z)
            self.world.set_block(x, y, z, block_type)

    def update(self):
        if not self.initial_generation_complete:
            try:
                next(self.stepped_generation)
            except StopIteration:
                print("Initial world generation complete.")
                self.stepped_generation = self.chunk_generator()
                self.loading_screen.enabled = False
                self.initial_generation_complete = True
                self.spawn_player()
            return

        if not self.player.enabled:
            return

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

        for chunk_pos in required_chunks:
            chunk = self.world.get_chunk(*chunk_pos)
            if chunk:
                yield from self.world.generate_terrain_async(chunk)
                yield from self.world.generate_mesh_async(chunk)

    def chunk_generator(self):
        for chunk in self.chunks_to_generate:
            if chunk:
                yield from self.world.generate_terrain_async(chunk)
                yield from self.world.generate_mesh_async(chunk)

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

        current_chunks = set()
        for dx in range(-self.render_distance, self.render_distance + 1):
            for dz in range(-self.render_distance, self.render_distance + 1):
                for dy in range(WORLD_LOWER_LIMIT // CHUNK_SIZE, WORLD_UPPER_LIMIT // CHUNK_SIZE + 1):
                    chunk_x = current_chunk_position[0] + dx
                    chunk_z = current_chunk_position[2] + dz
                    chunk_pos = (chunk_x, dy, chunk_z)
                    current_chunks.add(chunk_pos)
                    chunk = self.world.get_chunk(*chunk_pos)
                    self.chunks_to_generate.append(chunk)

        self.world.unload_distant_chunks(current_chunks)

    def run(self):
        self.app.run()


if __name__ == '__main__':
    game = VoxelGame(RENDER_DISTANCE)

    def update():
        game.update()

    game.run()