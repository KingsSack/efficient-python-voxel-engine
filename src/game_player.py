import time
from math import floor

from ursina import Vec3, Entity, color, raycast, held_keys
from ursina.prefabs.first_person_controller import FirstPersonController


class BlockHighlight(Entity):
    def __init__(self):
        super().__init__(
            model='cube',
            color=color.rgba(1, 1, 1, 0.2),
            scale=1.001
        )
        self.visible = False


class BlockInteraction:
    def __init__(self, world):
        self.world = world
        self.reach_distance = 5
        self.highlight = BlockHighlight()
        self.placing = False

    def ray_cast(self, position, direction):
        hit_info = raycast(position, direction, distance=self.reach_distance)

        if hit_info.hit and hit_info.entity != self.highlight:
            point = hit_info.world_point
            normal = hit_info.normal

            if point and normal:
                if self.placing:
                    # For placing, add the normal to get adjacent block position
                    point = Vec3(
                        point.x + normal.x,
                        point.y + normal.y,
                        point.z + normal.z
                    )

                # Round down to get block coordinates
                x = floor(point.x)
                y = floor(point.y)
                z = floor(point.z)
                return (x, y, z), point

        return None, None

    def update_highlight(self, position, direction):
        block_pos, _ = self.ray_cast(position, direction)
        if block_pos:
            x, y, z = block_pos
            self.highlight.visible = True
            self.highlight.position = Vec3(x + 0.5, y + 0.5, z + 0.5)
        else:
            self.highlight.visible = False

    def place_block(self, position, direction, block_type):
        self.placing = True
        block_pos, _ = self.ray_cast(position, direction)
        if block_pos:
            x, y, z = block_pos
            # Check distance from player
            distance = (Vec3(x, y, z) - position).length()
            if distance <= self.reach_distance:
                player_pos = position
                if (abs(x - player_pos.x) > 0.5 or
                    abs(y - player_pos.y) > 1.0 or
                    abs(z - player_pos.z) > 0.5):
                    if self.world.lower_limit <= y <= self.world.upper_limit:
                        self.world.set_block(x, y, z, block_type)
        self.placing = False

    def break_block(self, position, direction):
        self.placing = False
        block_pos, _ = self.ray_cast(position, direction)
        if block_pos:
            x, y, z = block_pos
            distance = (Vec3(x, y, z) - position).length()
            if distance <= self.reach_distance:
                self.world.set_block(x, y, z, "air")


class Player(FirstPersonController):
    def __init__(self, world):
        super().__init__(enabled=False)
        self.spawnpoint = Vec3(0, 0, 0)

        self.block_interaction = BlockInteraction(world)

        self.world = world

        # self.gravity = 18
        # self.jump_height = 1.5
        self.walking_speed = 6
        self.running_speed = 12

    def calculate_spawn_position(self) -> Vec3:
        spawn_x, spawn_z = 0, 0
        spawn_y = self.world.upper_limit
        for y in range(self.world.upper_limit, self.world.lower_limit - 1, -1):
            if self.world.get_block(spawn_x, y, spawn_z) != 0:
                spawn_y = y + 2
                break
        return Vec3(spawn_x, spawn_y, spawn_z)

    def respawn(self):
        self.position = self.spawnpoint
        print(f"Player respawned at: {self.position}")

    def spawn(self):
        self.respawn()
        self.enable()

    def on_left_mouse_down(self):
        if self.enabled:
            self.block_interaction.break_block(self.position, self.forward)

    def on_right_mouse_down(self):
        if self.enabled:
            self.block_interaction.place_block(self.position, self.forward, "stone")

    def sprint_handler(self):
        # Handle running
        if held_keys.get('left control'):
            self.speed = self.running_speed
        else:
            self.speed = self.walking_speed

    def update(self):
        super().update()
        self.block_interaction.update_highlight(self.position, self.forward)
        self.sprint_handler()
