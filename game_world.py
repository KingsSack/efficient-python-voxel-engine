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
                self.loaded_chunks.add(chunk_key)
        return self.chunks.get(chunk_key)

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