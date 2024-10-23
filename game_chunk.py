import json
import random
import threading

import numpy as np
from perlin_noise import PerlinNoise
from ursina import Entity, Mesh, Vec3, scene

from game_block import Block


class Chunk:
    def __init__(self, seed, position, world, size, lower_limit, upper_limit):
        self.seed = seed
        self.position = position
        self.world = world
        self.size = size
        self.lower_limit = lower_limit
        self.upper_limit = upper_limit
        self.mesh = None
        self.entity = None
        self.blocks = None
        self.needs_update = True
        self.lock = threading.Lock()

    def generate_terrain(self):
        if self.blocks is not None:
            return

        with self.lock:
            self.blocks = np.empty((self.size, self.size, self.size), dtype=object)
            noise = PerlinNoise(octaves=4, seed=self.seed)
            layers = self.world.layers
            for x in range(self.size):
                for z in range(self.size):
                    world_x = x + self.position[0] * self.size
                    world_z = z + self.position[2] * self.size
                    height = int((noise([world_x / 100, world_z / 100]) + 1) * self.upper_limit / 2)
                    for y in range(self.size):
                        world_y = self.position[1] * self.size + y
                        if self.lower_limit <= world_y < min(height, self.upper_limit):
                            random_percentage = random.random()
                            if world_y == height - 1:
                                for block, chance in self.world.surface.items():
                                    if random_percentage < chance:
                                        self.blocks[x, y, z] = self._load_block(block)
                                        break
                            else:
                                for layer_name, layer in layers.items():
                                    next_layer_start = min(
                                        (next_layer["start"] for next_layer_name, next_layer in layers.items() if next_layer["start"] > layer["start"]),
                                        default=float('inf')
                                    )
                                    if layer["start"] <= world_y < next_layer_start:
                                        for block, chance in layer["blocks"].items():
                                            if random_percentage < chance:
                                                self.blocks[x, y, z] = self._load_block(block)
                                                break
                        else:
                            self.blocks[x, y, z] = None
            self.needs_update = True

    def generate_mesh(self):
        if not self.needs_update or self.blocks is None:
            return

        with self.lock:
            vertices = []
            triangles = []
            uvs = []
            vertex_count = 0
            for x in range(self.size):
                for y in range(self.size):
                    for z in range(self.size):
                        block = self.blocks[x, y, z]
                        if not block:
                            continue

                        for face in range(6):
                            if self.is_face_visible(x, y, z, face):
                                verts = self.get_face_vertices(x, y, z, face)
                                vertices.extend(verts)
                                tri = self.get_face_triangles(vertex_count)
                                triangles.extend(tri)
                                face_name = ['side', 'side', 'side', 'side', 'bottom', 'top'][face]
                                face_uv = block.get_face(face_name)
                                uvs.extend([(face_uv[0], face_uv[1]), (face_uv[2], face_uv[1]),
                                            (face_uv[2], face_uv[3]), (face_uv[0], face_uv[3])])
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
                    position=Vec3(*self.position) * self.size,
                    texture='atlas.png',  # Use your texture atlas image
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

        if 0 <= nx < self.size and 0 <= ny < self.size and 0 <= nz < self.size:
            return self.blocks[nx, ny, nz] == None  # If neighbor block is air, face is visible
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
            [5, 4, 7, 6],  # back
            [4, 0, 3, 7],  # left
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
            return None

        # if 0 <= x < self.size and 0 <= y < self.size and 0 <= z < self.size:
        #     return self.blocks[x, y, z]
        # else:
        #     return None

        return self.blocks[x, y, z]

    def _load_block(self, name):
        data = None
        try:
            with open(f"data/blocks/{name}.json", "r", encoding="utf-8") as file:
                data = json.load(file)
        except FileNotFoundError:
            print(f"File '{name}.json' does not exist.")
            return None
        except json.JSONDecodeError:
            print(f"File '{name}.json' is not a valid JSON.")
            return None

        try:
            return Block(**data)
        except TypeError:
            print("Block data is not formatted correctly.")
            return None
