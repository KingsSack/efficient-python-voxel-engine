import json
from dataclasses import dataclass

@dataclass
class Block:
    texture: str
    uvs: dict

    def get_face(self, name):
        return self.uvs[name]
