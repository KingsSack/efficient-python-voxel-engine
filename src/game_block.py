import json
from dataclasses import dataclass

@dataclass
class Block:
    name: str
    uvs: dict

    def get_texture(self):
        return "textures/blocks/" + self.name

    def get_face(self, name):
        return self.uvs[name]

# class BlockManager:
#     def __init__(self):
#         self.block_registry = {}
#         self.load_block_definitions()

#     def load_block_definitions(self):
#         try:
#             with open("data/blocks/blocks.json", "r") as f:
#                 blocks = json.load(f)
#                 for block_data in blocks:
#                     self.register_block(Block(**block_data))

#     def register_block(self, block):
#         self.block_registry[block.name] = block

#     def get_block(self, name):
#         return self.block_registry.get(name)
