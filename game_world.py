from game_chunk import Chunk
from concurrent.futures import ThreadPoolExecutor
import threading


class World:
    def __init__(self, max_workers, seed, chunk_size, lower_limit, upper_limit):
        self.chunks = {}
        self.chunk_lock = threading.Lock()
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.loaded_chunks = set()
        
        self.seed = seed
        self.chunk_size = chunk_size
        self.lower_limit = lower_limit
        self.upper_limit = upper_limit

    def get_chunk(self, x, y, z):
        chunk_key = (x, y, z)
        if chunk_key not in self.loaded_chunks:
            with self.chunk_lock:
                if chunk_key not in self.chunks:
                    chunk = Chunk(self.seed, (x, y, z), self, self.chunk_size, self.lower_limit, self.upper_limit)
                    self.chunks[chunk_key] = chunk
        return self.chunks.get(chunk_key)

    def generate_chunk_async(self, chunk):
        terrain_future = self.executor.submit(chunk.generate_terrain)
        terrain_future.result()  # Wait for terrain generation to complete
        yield terrain_future
        
        mesh_future = self.executor.submit(chunk.generate_mesh)
        mesh_future.result()  # Wait for mesh generation to complete
        yield mesh_future
    
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
        chunk_x = x // self.chunk_size
        chunk_y = y // self.chunk_size
        chunk_z = z // self.chunk_size
        chunk = self.get_chunk(chunk_x, chunk_y, chunk_z)
        if chunk:
            local_x = x % self.chunk_size
            local_y = y % self.chunk_size
            local_z = z % self.chunk_size
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