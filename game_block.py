class BlockFace:
    def __init__(self, texture, color=(255, 255, 255), uv=(0, 0, 1, 1)):
        self.texture = texture
        self.color = color
        self.uv = uv  # UV coordinates

class Block:
    def __init__(self, texture, color=(255, 255, 255), faces=None, uvs=None):
        self.texture = texture
        if faces is None:
            self.faces = {
                "top": BlockFace(texture, color, uvs["top"] if uvs else (0, 0, 1, 1)),
                "bottom": BlockFace(texture, color, uvs["bottom"] if uvs else (0, 0, 1, 1)),
                "side": BlockFace(texture, color, uvs["side"] if uvs else (0, 0, 1, 1))
            }
        else:
            self.faces = faces

    def get_face(self, face):
        return self.faces.get(face)

class Dirt(Block):
    def __init__(self):
        uvs = {"top": (0, 0, 1/4, 1), "bottom": (0, 0, 1/4, 1), "side": (0, 0, 1/4, 1)}
        super().__init__("textures/blocks/dirt", uvs=uvs)

class Grass(Block):
    def __init__(self):
        uvs = {
            "top": (1/2, 0, 3/4, 1),
            "bottom": (0, 0, 1/4, 1),
            "side": (1/4, 0, 1/2, 1)
        }
        super().__init__("textures/blocks/glass_block_side", faces={
            "top": BlockFace("textures/blocks/grass_block_top", (0, 255, 0), uv=uvs["top"]),
            "bottom": BlockFace("textures/blocks/dirt", uv=uvs["bottom"]),
            "side": BlockFace("textures/blocks/glass_block_side", uv=uvs["side"])
        })

class Stone(Block):
    def __init__(self):
        uvs = {"top": (3/4, 0, 1, 1), "bottom": (3/4, 0, 1, 1), "side": (3/4, 0, 1, 1)}
        super().__init__("textures/blocks/stone", uvs=uvs)