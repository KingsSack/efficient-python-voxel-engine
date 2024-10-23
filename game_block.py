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
