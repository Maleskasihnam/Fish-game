from math import *
from pygame import *
from random import *
from collections import deque

init()
font.init()
IMAGES = {
    "obs1.png": transform.scale(image.load("obs1.png"), (75, 100)),
    "obs2.png": transform.scale(image.load("obs2.png"), (125, 125)),
    "obs3.png": transform.scale(image.load("obs3.png"), (30, 80)),
    "turtle.png": transform.scale(image.load("turtle.png"), (50, 50)),
    "heart.png": transform.scale(image.load("heart.png"), (50,50)),
    "broken heart.png": transform.scale(image.load("broken heart.png"), (50,50)),
    "shield.png": transform.scale(image.load("shield.png"), (70,70)),
    "bomb.png": transform.scale(image.load("bomb.png"), (60,60)),
    "bomb_gone.png": transform.scale(image.load("bomb_gone.png"), (60,60)),
    "bubble.png": transform.scale(image.load("bubble.png"),(50,50)),
    "decor_turtle.png": transform.scale(image.load("decor_turtle.png"),(250,250)),
    "fish_left.png": transform.scale(image.load("fish_left.png"),(50,20)),
    "fish_right.png": transform.scale(image.load("fish_right.png"),(50,20)),
    "button.png": transform.scale(image.load("button.png"),(100,300)),
    "wall.png": transform.scale(image.load("line.png"),(50,5))
}

font_title = font.SysFont("Roboto", 216)
font_explanation = font.SysFont("Roboto",144)
font_subtitle = font.SysFont("Roboto",108)
font_system = font.SysFont("Roboto", 72)
font_subtitle_2 = font.SysFont("Roboto",36)
font_small = font.SysFont("Roboto",24)

win_width = 900
win_height = 700
window = display.set_mode((win_width, win_height))

# --- Rewritten BossManager that supports both maze and memoria boss types ---
class BossManager:
    def __init__(self, player, screen_size):
        self.player = player
        self.screen_size = screen_size
        self.current = None
        self.kind = None
        self.active = False

    def start(self, kind=None, difficulty="medium", iterations=3, maze_kwargs=None):
        """
        kind: 'maze' or 'memoria' (if None, pick randomly)
        difficulty: passed to MemoriaBossFight.start
        iterations: number of memoria iterations to survive
        maze_kwargs: optional dict forwarded to MazeBoss constructor if using maze
        """
        if kind is None:
            kind = choice(['memoria'])
        self.kind = kind
        self.active = True

        if kind == "memoria":  # memoria
            self.current = MemoriaBossFight(self.player, win_size=self.screen_size)
            self.current.start(difficulty=difficulty, iterations=iterations)

    def update(self, events):
        """Call each frame. Returns None while bossfight is ongoing. Returns True (win) or False (lose) when finished."""
        if not self.active or self.current is None:
            return None

        # MemoriaBossFight: update returns None while running, or True/False when finished
        if isinstance(self.current, MemoriaBossFight):
            res = self.current.update(events)
            if res is not None:
                # finished
                self._cleanup()
                return res
            return None

        # unknown type -> consider finished
        else:
            self._cleanup()
            return False

    def draw(self, surface):
        if not self.active or self.current is None:
            return
        # Delegate to current boss's draw
        self.current.draw(surface)

    def _cleanup(self):
        # restore player speed (safety)
        if hasattr(self.player, "base_speed"):
            self.player.speed = self.player.base_speed
        # clear current
        self.current = None
        self.active = False

    def stop(self):
        if self.current is not None:
            try:
                self.current.stop()
            except Exception:
                pass
        self._cleanup()

# --- Memoria / Net implementation using obs2.png as the net (fast obstacle) ---
class Net(sprite.Sprite):
    """Net implemented using your 'obs2.png' asset. Flies down a column (axis='col')
    or left across a row (axis='row') at very high speed."""
    def __init__(self, axis, index, cols, rows, win_w, win_h, speed_px_per_frame):
        super().__init__()
        # Use obs2 image as the net sprite
        self.image = IMAGES["obs2.png"].copy()
        self.rect = self.image.get_rect()
        self.axis = axis
        self.index = index
        self.cols = cols
        self.rows = rows
        self.win_w = win_w
        self.win_h = win_h
        self.speed = speed_px_per_frame

        col_w = win_w / cols
        row_h = win_h / rows

        if axis == "col":
            # Spawn above screen, centered in column
            cx = int(index * col_w + col_w / 2)
            self.rect.centerx = cx
            self.rect.bottom = -6
            self.vx = 0
            self.vy = self.speed
        else:
            # axis == "row" -> spawn right of screen, centered in row
            ry = int(index * row_h + row_h / 2)
            self.rect.centery = ry
            self.rect.left = win_w + 6
            self.vx = -self.speed
            self.vy = 0

    def update(self):
        self.rect.x += int(self.vx)
        self.rect.y += int(self.vy)
        # Remove when out of bounds
        if self.rect.top > self.win_h + 50 or self.rect.right < -50:
            self.kill()


class MemoriaBossFight:
    """
    Memoria-style attack using obs2 nets.
    Rules:
     - Grid: 9 columns x 7 rows (window divided)
     - Rays from top/right: yellow = safe (player MUST stand in lit col/row),
       red = forbidden (player must avoid lit col/row)
     - Grace time (telegraph) 2s for player to move
     - Nets (obs2) spawn in unsafe columns/rows and fly extremely fast
    """
    def __init__(self, player, win_size=(900,700)):
        self.player = player
        self.win_w, self.win_h = win_size
        self.cols = 9
        self.rows = 7

        self.active = False
        self.iterations = 1
        self.iter_done = 0
        self.difficulty = "medium"

        # timings (ms)
        self.telegraph_ms = 2000
        self.attack_ms = 1200
        self.cooldown_range = (900, 1500)

        self._phase = "idle"
        self._phase_start = 0

        # ray info
        self.top_rays = []
        self.right_rays = []
        self.top_type = None
        self.right_type = None
        self.ray_objs = []

        # nets group (using obs2)
        self.nets = sprite.Group()

        # difficulty-tunable params
        self.net_speed_range = (34, 56)
        self.player_speed_mult = 1.0

        self.result = None

    def start(self, difficulty="medium", iterations=3):
        self.difficulty = difficulty
        self.iterations = max(1, iterations)
        self.iter_done = 0
        self.active = True
        self.result = None
        self._choose_difficulty_settings()
        # save player's base speed so we can restore later
        if not hasattr(self.player, "base_speed"):
            self.player.base_speed = getattr(self.player, "speed", 2)
        self._start_new_iteration()

    def _choose_difficulty_settings(self):
        if self.difficulty == "easy":
            self.side_options = {"top": True, "right": False}
            self.allowed_types = {"top": ["yellow"], "right": []}
            self.net_speed_range = (18, 26)
            self.player_speed_mult = 1.0
            self.cooldown_range = (1200, 1700)
        elif self.difficulty == "medium":
            self.side_options = {"top": True, "right": False}
            self.allowed_types = {"top": ["yellow", "red"], "right": []}
            self.net_speed_range = (26, 40)
            self.player_speed_mult = 1.1
            self.cooldown_range = (900, 1400)
        else:  # hard
            self.side_options = {"top": True, "right": True}
            self.allowed_types = {"top": ["yellow", "red"], "right": ["yellow", "red"]}
            self.net_speed_range = (34, 56)
            self.player_speed_mult = 1.2
            self.cooldown_range = (700, 1100)

    def _start_new_iteration(self):
        # pick rays
        self.ray_objs = []
        self.top_rays = []
        self.right_rays = []
        self.top_type = None
        self.right_type = None

        if self.side_options.get("top"):
            max_top = min(3, self.cols)
            count = randint(1, max_top)
            self.top_rays = sample(range(self.cols), count)
            self.top_type = choice(self.allowed_types["top"])
            for idx in self.top_rays:
                color = (255,220,60) if self.top_type == "yellow" else (255,60,60)
                self.ray_objs.append(Ray("top", idx, self.cols, self.rows, self.win_w, self.win_h, color))

        if self.side_options.get("right"):
            max_right = min(4, self.rows)
            count = randint(1, max_right)
            self.right_rays = sample(range(self.rows), count)
            self.right_type = choice(self.allowed_types["right"])
            for idx in self.right_rays:
                color = (255,220,60) if self.right_type == "yellow" else (255,60,60)
                self.ray_objs.append(Ray("right", idx, self.cols, self.rows, self.win_w, self.win_h, color))

        # phase: telegraph
        self._phase = "telegraph"
        self._phase_start = time.get_ticks()
        self.nets.empty()

        # boost player speed temporarily
        self.player.speed = getattr(self.player, "base_speed", self.player.speed) * self.player_speed_mult

    def _spawn_nets_for_iteration(self):
        # determine safe/unsafe columns & rows according to ray logic
        safe_cols = set()
        safe_rows = set()

        # top rays
        if self.top_rays:
            if self.top_type == "yellow":
                safe_cols.update(self.top_rays)
            else:  # red on top -> forbidden -> safe is complement
                safe_cols = set(range(self.cols)) - set(self.top_rays)

        # right rays
        if self.right_rays:
            if self.right_type == "yellow":
                safe_rows.update(self.right_rays)
            else:
                safe_rows = set(range(self.rows)) - set(self.right_rays)

        # compute columns/rows where nets spawn: any column NOT in safe_cols spawns col-nets;
        # any row NOT in safe_rows spawns row-nets.
        cols_to_spawn = [c for c in range(self.cols) if c not in safe_cols]
        rows_to_spawn = [r for r in range(self.rows) if r not in safe_rows]

        # spawn Net objects using obs2 image (fast)
        for c in cols_to_spawn:
            speed = randint(self.net_speed_range[0], self.net_speed_range[1])
            net = Net(axis="col", index=c, cols=self.cols, rows=self.rows,
                      win_w=self.win_w, win_h=self.win_h, speed_px_per_frame=speed)
            self.nets.add(net)

        for r in rows_to_spawn:
            speed = randint(self.net_speed_range[0], self.net_speed_range[1])
            net = Net(axis="row", index=r, cols=self.cols, rows=self.rows,
                      win_w=self.win_w, win_h=self.win_h, speed_px_per_frame=speed)
            self.nets.add(net)

    def _player_in_safe_spot(self):
        px, py = self.player.rect.center
        col_w = self.win_w / self.cols
        row_h = self.win_h / self.rows
        player_col = int(px // col_w)
        player_row = int(py // row_h)

        has_yellow = (self.top_type == "yellow") or (self.right_type == "yellow")
        if has_yellow:
            in_yellow_col = (player_col in self.top_rays) if self.top_rays and self.top_type == "yellow" else False
            in_yellow_row = (player_row in self.right_rays) if self.right_rays and self.right_type == "yellow" else False
            return (in_yellow_col or in_yellow_row)

        # No yellow -> apply red semantics (forbidden)
        if (self.top_type == "red" and (player_col in self.top_rays)) or (self.right_type == "red" and (player_row in self.right_rays)):
            return False
        return True

    def update(self, events):
        """Call from your main loop each frame. Returns None while ongoing; returns True/False when finished."""
        if not self.active:
            return None

        now = time.get_ticks()

        if self._phase == "telegraph":
            # show rays during telegraph; after telegraph_ms, ensure player is in safe spot
            if now - self._phase_start >= self.telegraph_ms:
                if not self._player_in_safe_spot():
                    # fail immediately
                    self.active = False
                    self.result = False
                    # restore player speed
                    self.player.speed = getattr(self.player, "base_speed", self.player.speed)
                    return self.result

                # spawn nets and move to attack phase
                self._spawn_nets_for_iteration()
                self._phase = "attack"
                self._phase_start = now
            else:
                return None

        elif self._phase == "attack":
            self.nets.update()
            # check collision: if any net collides with player's hitbox -> fail
            for net in self.nets:
                if self.player.hitbox.colliderect(net.rect):
                    self.active = False
                    self.result = False
                    # restore player speed
                    self.player.speed = getattr(self.player, "base_speed", self.player.speed)
                    return self.result

            # if nets cleared (they flew past) or attack window elapsed, move to cooldown
            if not self.nets or (now - self._phase_start >= self.attack_ms):
                self._phase = "cooldown"
                self._phase_start = now
            return None

        elif self._phase == "cooldown":
            if now - self._phase_start >= randint(self.cooldown_range[0], self.cooldown_range[1]):
                self.iter_done += 1
                if self.iter_done >= self.iterations:
                    self.active = False
                    self.result = True
                    # restore player speed
                    self.player.speed = getattr(self.player, "base_speed", self.player.speed)
                    return self.result
                else:
                    # new iteration
                    self._start_new_iteration()
                    return None
            return None

        return None

    def draw(self, surface):
        if not self.active:
            return
        # draw rays while telegraph/attack phases
        if self._phase in ("telegraph", "attack"):
            for r in self.ray_objs:
                r.draw(surface)
        # draw nets
        if self.nets:
            self.nets.draw(surface)

    def stop(self):
        self.active = False
        self.result = False
        self.nets.empty()
        # restore player speed
        self.player.speed = getattr(self.player, "base_speed", self.player.speed)

class VFXManager:
    def __init__(self):
        self.effects = []

    def add(self, effect):
        self.effects.append(effect)

    def update(self):
        for e in self.effects[:]:
            e.update()
            if not e.alive:
                self.effects.remove(e)

    def draw(self, surface):
        for e in self.effects:
            e.draw(surface)

GREEN  = ( 80, 220, 160)
YELLOW = (255, 230,  80)
ORANGE = (255, 165,  60)

class Ray:
    def __init__(self, side, index, total_cols, total_rows, win_w, win_h):
        self.side = side      # "top" or "right"
        self.index = index
        self.win_w = win_w
        self.win_h = win_h

        self.total_cols = total_cols
        self.total_rows = total_rows

        self._build_rects()

    def _build_rects(self):
        if self.side == "top":
            col_w = self.win_w / self.total_cols
            x = int(self.index * col_w)

            beam_w = int(col_w)
            beam_h = self.win_h

            self.base_rect = Rect(x, 0, beam_w, beam_h)

        else:  # right
            row_h = self.win_h / self.total_rows
            y = int(self.index * row_h)

            beam_w = self.win_w
            beam_h = int(row_h)

            self.base_rect = Rect(0, y, beam_w, beam_h)

        # Layer shrink values (centered)
        self.layers = [
            (GREEN,  0,  70),
            (YELLOW, 8,  90),
            (ORANGE, 16, 120),
        ]

    def draw(self, surf):
        overlay = Surface((self.win_w, self.win_h), SRCALPHA)

        for color, inset, alpha in self.layers:
            if self.side == "top":
                rect = Rect(
                    self.base_rect.x + inset,
                    self.base_rect.y,
                    self.base_rect.w - inset * 2,
                    self.base_rect.h
                )
            else:  # right
                rect = Rect(
                    self.base_rect.x,
                    self.base_rect.y + inset,
                    self.base_rect.w,
                    self.base_rect.h - inset * 2
                )

            layer = Surface((rect.w, rect.h), SRCALPHA)
            layer.fill((*color, alpha))
            overlay.blit(layer, rect.topleft)

        surf.blit(overlay, (0, 0))

class VFX:
    def __init__(self):
        self.alive = True

    def update(self):
        pass

    def draw(self, surface):
        pass

class Button:
    def __init__(self, image_name, center, label, font, action=None,text_offset=(-10,0)):
        # base image
        img = IMAGES[image_name]
        img = transform.rotate(img, -90)   # rotate bottle sideways
        self.image = img
        self.rect = self.image.get_rect(center=center)

        self.text_offset = text_offset
        # text inside button
        self.text = Text(font, self.rect.center)
        self.text.show_instant(label)

        self.action = action
        self.hovered = False

        # visual tweaks
        self.base_alpha = 180
        self.hover_alpha = 255
        self.image.set_alpha(self.base_alpha)

    def update(self, events):
        mouse_pos = mouse.get_pos()
        self.hovered = self.rect.collidepoint(mouse_pos)

        # hover effect
        self.image.set_alpha(self.hover_alpha if self.hovered else self.base_alpha)
        if self.hovered:
            self.rect.y += int(sin(time.get_ticks() * 0.004) * 0.5)
        # click detection
        for e in events:
            if e.type == MOUSEBUTTONUP and e.button == 1:
                if self.hovered and self.action:
                    self.action()

    def draw(self, surface):
        surface.blit(self.image, self.rect)

        # re-center text every frame (safe if image pulses later)
        self.text.pos = (self.rect.centerx + self.text_offset[0],self.rect.centery + self.text_offset[1])
        self.text.draw(surface)

class BackgroundChar:
    def __init__(self, image, pos):
        self.image = image
        self.rect = self.image.get_rect(center=pos)

    def update(self):
        pass  # subclasses decide movement

    def draw(self, surface):
        surface.blit(self.image, self.rect)

class BackgroundFish(BackgroundChar):
    def __init__(self):
        self.direction = choice(["left", "right"])

        image = IMAGES[
            "fish_left.png" if self.direction == "left" else "fish_right.png"
        ]

        x = win_width + 100 if self.direction == "left" else -100
        y = randint(300, win_height - 150)

        super().__init__(image, (x, y))

        self.speed = randint(1, 3)

    def update(self):
        if self.direction == "left":
            self.rect.x -= self.speed
            if self.rect.right < 0:
                self.__init__()
        else:
            self.rect.x += self.speed
            if self.rect.left > win_width:
                self.__init__()

class Bubble(BackgroundChar):
    def __init__(self, x):
        image = IMAGES["bubble.png"]

        scale = randint(20, 50)
        image = transform.scale(image, (scale, scale))
        image.set_alpha(randint(120, 200))

        y = win_height + randint(0, 100)
        jitter = randint(-20,20)
        super().__init__(image, (x + jitter, y))

        self.speed = randint(1, 3)
        self.drift = uniform(-0.7, 0.7)

    def update(self):
        self.rect.y -= self.speed
        self.rect.x += int(sin(time.get_ticks() * 0.002) * 0.5)
        self.rect.x += self.drift

    def is_dead(self):
        return self.rect.centery <= 300

from collections import deque

class BubbleColumn:
    def __init__(self):
        self.x = randint(100, win_width - 100)
        self.spawn_time = time.get_ticks()
        self.duration = randint(1500, 3000)

        self.last_spawn = 0
        self.spawn_delay = randint(120, 250)

        self.bubbles = deque()   # 🔑 CHANGED: deque instead of list

    def update(self):
        now = time.get_ticks()

        # spawn bubbles ONE BY ONE
        if now - self.spawn_time < self.duration:
            if now - self.last_spawn >= self.spawn_delay:
                self.bubbles.append(Bubble(self.x))
                self.last_spawn = now
                self.spawn_delay = randint(120, 250)  # keep randomness

        # update bubbles
        for _ in range(len(self.bubbles)):
            b = self.bubbles.popleft()
            b.update()
            if not b.is_dead():
                self.bubbles.append(b)

    def draw(self, surface):
        for b in self.bubbles:
            b.draw(surface)

    def is_finished(self):
        return (
            time.get_ticks() - self.spawn_time > self.duration
            and not self.bubbles
        )

class Transition:
    def __init__(self, size):
        self.w, self.h = size
        self.alpha = 0
        self.phase = "idle"
        self.start_time = 0
        self.duration = 800
        self.mid_callback = None
        self.called = False

    def start(self, mid_callback=None):
        self.phase = "out"
        self.alpha = 0
        self.start_time = time.get_ticks()
        self.mid_callback = mid_callback
        self.called = False

    def update(self):
        if self.phase == "idle":
            return

        t = (time.get_ticks() - self.start_time) / self.duration

        if self.phase == "out":
            self.alpha = min(255, int(255 * t))
            if t >= 1:
                if self.mid_callback and not self.called:
                    self.mid_callback()
                    self.called = True
                self.phase = "in"
                self.start_time = time.get_ticks()

        elif self.phase == "in":
            self.alpha = max(0, 255 - int(255 * t))
            if t >= 1:
                self.phase = "idle"

    def draw(self, surface):
        if self.alpha <= 0:
            return
        overlay = Surface((self.w, self.h), SRCALPHA)
        overlay.fill((0, 0, 0, self.alpha))
        surface.blit(overlay, (0, 0))

class Text:
    """
    Unified text object:
    - typing mode (choose_dialogue + update_typing)
    - instant mode (show_instant)
    - fade mode (show_fade: fade_in -> hold -> fade_out)
    Use update() and draw(surface) each frame.
    """
    def __init__(self, text_font, pos, typing_speed=40):
        self.font = text_font
        self.pos = pos
        self.typing_speed = typing_speed

        # typing-related
        self.dialogues = []
        self.full_text = ""
        self.current_text = ""
        self.char_index = 0
        self.last_update = 0

        # visual style
        self.color = (255, 255, 255)
        self.alpha = 255

        # state
        self.mode = "idle"   # "idle", "typing", "instant", "fade"
        self.active = False
        self.instant = False

        # fade-specific
        self._fade_start = 0
        self._fade_in = 600
        self._hold = 1000
        self._fade_out = 600
        self._phase = None   # "fading_in","holding","fading_out"
        self._fade_surf = None

    # ---------- existing typing API ----------
    def choose_dialogue(self, dialogue_list):
        self.dialogues = dialogue_list
        self.full_text = choice(self.dialogues)
        self.current_text = ""
        self.char_index = 0
        self.last_update = time.get_ticks()
        self.active = True
        self.instant = False
        self.mode = "typing"

    def update_typing(self):
        if not self.active or self.instant or self.mode != "typing":
            return

        now = time.get_ticks()
        delay = 1000 // max(1, self.typing_speed)

        if self.char_index < len(self.full_text):
            if now - self.last_update >= delay:
                self.current_text += self.full_text[self.char_index]
                self.char_index += 1
                self.last_update = now

    def show_instant(self, text):
        self.full_text = text
        self.current_text = text
        self.active = True
        self.instant = True
        self.mode = "instant"
        # pre-render surf for consistent draw
        if self.font is not None:
            self._fade_surf = self.font.render(self.current_text, True, self.color).convert_alpha()
            self._fade_surf.set_alpha(self.alpha)

    # ---------- new fade API ----------
    def show_fade(self, text, color=None, fade_in=600, hold=1000, fade_out=600):
        """Show a single pre-rendered text with fade-in → hold → fade-out.
        Use this for ending text. While fading, update() and draw() should be called each frame.
        """
        self.full_text = text
        self.current_text = text
        self.char_index = len(text)
        self.last_update = time.get_ticks()
        if color is not None:
            self.color = color
        self._fade_in = fade_in
        self._hold = hold
        self._fade_out = fade_out

        # pre-render surface once for fade drawing
        if self.font is not None:
            self._fade_surf = self.font.render(self.full_text, True, self.color).convert_alpha()
        else:
            self._fade_surf = None

        self.active = True
        self.instant = False
        self.mode = "fade"
        self._phase = "fading_in"
        self._fade_start = time.get_ticks()
        self.alpha = 0

    def set_style(self, color=None, alpha=None):
        if color is not None:
            self.color = color
            # if we have a cached surf and are in fade, re-render
            if self.mode == "fade" and self.font is not None:
                self._fade_surf = self.font.render(self.full_text, True, self.color).convert_alpha()
        if alpha is not None:
            self.alpha = alpha

    # ---------- lifecycle ----------
    def update(self):
        # typing mode
        if self.mode == "typing":
            self.update_typing()
            return

        # fade mode
        if self.mode == "fade" and self.active:
            now = time.get_ticks()
            if self._phase == "fading_in":
                t = (now - self._fade_start) / max(1, self._fade_in)
                if t >= 1:
                    self.alpha = 255
                    self._phase = "holding"
                    self._fade_start = now
                else:
                    self.alpha = int(255 * t)
            elif self._phase == "holding":
                if now - self._fade_start >= self._hold:
                    self._phase = "fading_out"
                    self._fade_start = now
            elif self._phase == "fading_out":
                t = (now - self._fade_start) / max(1, self._fade_out)
                if t >= 1:
                    self.alpha = 0
                    self.active = False
                    self.mode = "idle"
                else:
                    self.alpha = int(255 * (1 - t))

    def draw(self, surface):
        # nothing to draw if no current text (typing draws progressively)
        if self.mode == "typing":
            if not self.current_text:
                return
            text_surf = self.font.render(self.current_text, True, self.color).convert_alpha()
            text_surf.set_alpha(self.alpha)
            rect = text_surf.get_rect(center=self.pos)
            surface.blit(text_surf, rect)
            return

        if self.mode == "instant":
            if not self.current_text:
                return
            # if we have cached surf use it
            s = self._fade_surf if self._fade_surf is not None else self.font.render(self.current_text, True, self.color).convert_alpha()
            s.set_alpha(self.alpha)
            rect = s.get_rect(center=self.pos)
            surface.blit(s, rect)
            return

        if self.mode == "fade":
            if not self.active:
                return
            if self._fade_surf is None:
                # fallback render
                s = self.font.render(self.full_text, True, self.color).convert_alpha()
            else:
                s = self._fade_surf.copy()
            s.set_alpha(max(0, min(255, self.alpha)))
            rect = s.get_rect(center=self.pos)
            surface.blit(s, rect)

    def is_active(self):
        """Return True if text is currently active (typing, instant or fading)."""
        return self.active or self.mode in ("typing", "instant")

class SubtitleBar:
    def __init__(self, width, height=70):
        self.width = width
        self.height = height

        self.bg = Surface((width, height), SRCALPHA)
        self.bg.fill((0, 0, 0, 150))  # you’ll customize

        self.text = Text(font_subtitle_2, (width // 2, win_height - height // 2))

        self.active = False
        self.start = 0
        self.duration = 1800

    def trigger(self, message):
        self.text.show_instant(message)
        self.active = True
        self.start = time.get_ticks()

    def update(self):
        if not self.active:
            return

        if time.get_ticks() - self.start > self.duration:
            self.active = False

    def draw(self, surface):
        if not self.active:
            return

        y = win_height - self.height
        surface.blit(self.bg, (0, y))
        self.text.draw(surface)

class FloatingText:
    def __init__(self, font):
        self.font = font
        self.text = ""
        self.timer = 0
        self.duration = 3000
        self.active = False

    def show(self, text):
        self.text = text
        self.timer = time.get_ticks()
        self.active = True

    def draw(self, surface):
        if not self.active:
            return

        if time.get_ticks() - self.timer > self.duration:
            self.active = False
            return

        img = self.font.render(self.text, True, (255, 80, 80))
        rect = img.get_rect(center=(surface.get_width()//2, 580))
        surface.blit(img, rect)

class HUD:
    def __init__(self):
        self.hearts = sprite.Group()
        self.bombs = sprite.Group()

    def update_lives(self, lives, max_lives):
        self.hearts.empty()
        for i in range(max_lives):
            img = "heart.png" if i < lives else "broken heart.png"
            self.hearts.add(HUDSprite(img, 20 + i * 55, 20))

    def update_bombs(self, bombs, max_bombs):
        self.bombs.empty()
        for i in range(max_bombs):
            img = "bomb.png" if i < bombs else "bomb_gone.png"
            self.bombs.add(HUDSprite(img, 825 - i * 55, 10))

    def draw(self, surface):
        self.hearts.draw(surface)
        self.bombs.draw(surface)

class HUDSprite(sprite.Sprite):
    def __init__(self, image_name, x, y):
        super().__init__()
        self.image = IMAGES[image_name]
        self.rect = self.image.get_rect(topleft=(x, y))

    def draw(self, surface):
        surface.blit(self.image, self.rect)

class ScreenFlash(VFX):
    def __init__(self, color, duration=150):
        super().__init__()
        self.color = color
        self.start = time.get_ticks()
        self.duration = duration

    def update(self):
        if time.get_ticks() - self.start > self.duration:
            self.alive = False

    def draw(self, surface):
        t = (time.get_ticks() - self.start) / self.duration
        alpha = int(180 * (1 - t))
        overlay = Surface(surface.get_size(), SRCALPHA)
        overlay.fill((*self.color, max(0, alpha)))
        surface.blit(overlay, (0, 0))

class ShockwaveRing(VFX):
    def __init__(self, center, lives):
        super().__init__()
        self.center = center
        self.radius = 0
        self.max_radius = 360
        self.speed = 18
        self.thickness = 10
        self.alpha = 180

        self.color = {
            3: (0, 255, 0),
            2: (255, 255, 0),
            1: (255, 60, 60),
            0: (255, 0, 0)
        }.get(lives, (255, 255, 255))

    def update(self):
        self.radius += self.speed
        self.alpha -= 4

        if self.radius > self.max_radius or self.alpha <= 0:
            self.alive = False

    def draw(self, surface):
        ring = Surface(surface.get_size(), SRCALPHA)
        draw.circle(
            ring,
            (*self.color, max(0, self.alpha)),
            self.center,
            int(self.radius),
            self.thickness
        )
        surface.blit(ring, (0, 0))

class ScreenShake(VFX):
    def __init__(self, intensity=8, duration=250):
        super().__init__()
        self.intensity = intensity
        self.start = time.get_ticks()
        self.duration = duration
        self.offset = Vector2()

    def update(self):
        t = time.get_ticks() - self.start
        if t > self.duration:
            self.offset = Vector2()
            self.alive = False
            return

        decay = 1 - t / self.duration
        self.offset.x = randint(-1, 1) * self.intensity * decay
        self.offset.y = randint(-1, 1) * self.intensity * decay

class Shield(sprite.Sprite):
    def __init__(self, player):
        super().__init__()
        self.player = player
        self.image = IMAGES["shield.png"]
        self.rect = self.image.get_rect(center=player.rect.center)

    def update(self):
        self.rect.center = self.player.rect.center
        alpha = 150 + int(105 * sin(time.get_ticks() * 0.01))
        self.image.set_alpha(alpha)

class GameSprite(sprite.Sprite):
    def __init__(self, player_image, x_co, y_co, player_speed, width, height):
        super().__init__()
        self.image = IMAGES[player_image]
        self.speed = player_speed
        self.rect = self.image.get_rect()
        self.rect.x = x_co
        self.rect.y = y_co

    def reset(self):
        window.blit(self.image, (self.rect.x, self.rect.y))

class Player(GameSprite):
    def __init__(self, *args, lives=3,bombs=3):
        super().__init__(*args)

        self.max_lives = lives
        self.lives = lives
        self.invulnerability = False
        self.inv_timer = 0
        self.inv_dur = 3000
        self.max_bombs = bombs
        self.bombs = bombs
        self.bomb_radius = 300
        self.last_bomb = -9999
        self.bomb_cd = 3000
        self.blink = False
        self.blink_timer = 0

        hitbox_w = self.rect.width * 0.1
        hitbox_h = self.rect.height * 0.1

        self.hitbox = Rect(0, 0, hitbox_w, hitbox_h)
        self.update_hitbox()

    def use_bomb(self, bullets,forced=False):
        if not forced:
            if self.bombs <= 0:
                cooldown_text.show("NO BOMBS LEFT")
                return
            now = time.get_ticks()
            if now - self.last_bomb < self.bomb_cd:
                cooldown_text.show("BOMB ON COOLDOWN")
                return
            self.last_bomb = now
            self.bombs -= 1
            vfx.add(ScreenFlash((237, 70, 14)))
        vfx.add(ShockwaveRing(self.rect.center,self.lives))
        vfx.add(ScreenShake(intensity=12))
        px, py = self.rect.center

        for o in bullets:
            ox, oy = o.rect.center
            if hypot(ox - px, oy - py) <= self.bomb_radius:
                o.kill()

        self.invulnerability = True
        self.inv_timer = time.get_ticks()
        self.inv_dur = 1000

    def update_hitbox(self):
        self.hitbox.center = self.rect.center

    def upd(self):
        keys = key.get_pressed()

        if self.invulnerability:
            if time.get_ticks() - self.inv_timer >= self.inv_dur:
                self.invulnerability = False
            if self.invulnerability == False:
                self.inv_dur = 3000

        if self.blink:
            if (time.get_ticks() - self.blink_timer) > self.inv_dur:
                self.blink = False

        if keys[K_LSHIFT] or keys[K_RSHIFT]:
            current_speed = self.speed / 2
        else:
            current_speed = self.speed

        if (keys[K_w] or keys[K_UP]) and self.rect.y > 50:
            self.rect.y -= current_speed
        if (keys[K_s] or keys[K_DOWN]) and self.rect.y < 650:
            self.rect.y += current_speed
        if (keys[K_a] or keys[K_LEFT]) and self.rect.x > 50:
            self.rect.x -= current_speed
        if (keys[K_d] or keys[K_RIGHT]) and self.rect.x < 800:
            self.rect.x += current_speed

        self.update_hitbox()

    def take_damage(self,bullets):
        if self.invulnerability:
            return

        damaged_text = choice(damaged_text_list)
        self.blink = True
        self.blink_timer = time.get_ticks()

        self.use_bomb(bullets,forced=True)

        self.lives -= 1
        if self.lives != 0:
            subtitle_bar.trigger(damaged_text)

        if self.lives <= 1:
            self.inv_dur = 5000
            vfx.add(ScreenFlash((255, 0, 0), 180))
            vfx.add(ScreenShake(intensity=3, duration=400))
        if self.lives == 2:
            vfx.add(ScreenFlash((255, 255, 0), 180))
            vfx.add(ScreenShake(intensity=6, duration=120))
        self.invulnerability = True
        self.inv_timer = time.get_ticks()

    def draw(self, surface):
        if not self.blink or time.get_ticks() % 200 < 100:
            surface.blit(self.image, self.rect)

class Obstacle(GameSprite):
    def __init__(self, player_image, speed, width, height):
        origin = randint(1, 3)

        if origin == 1:  # FROM TOP
            angle = randint(30, 150)
            x = randint(0, win_width - width)
            y = -height

        elif origin == 2:  # FROM RIGHT
            angle = randint(150, 180)
            x = win_width - 10
            y = randint(0, win_height - height)

        else:  # FROM LEFT
            angle = randint(0, 30)
            x = -width
            y = randint(0, win_height - height)

        rad = radians(angle)
        super().__init__(player_image, x, y, speed, width, height)

        self.rotation = choice([0, 90, -90, 180])

        if self.rotation != 0:
            self.image = transform.rotate(self.image, self.rotation)
            self.rect = self.image.get_rect(center=self.rect.center)

        self.fx = float(self.rect.x)
        self.fy = float(self.rect.y)

        self.vx = speed * cos(rad)
        self.vy = speed * sin(rad)

        hitbox_w = self.rect.width * 0.9
        hitbox_h = self.rect.height * 0.9
        self.hitbox = Rect(0, 0, hitbox_w, hitbox_h)
        self.update_hitbox()

    def update_hitbox(self):
        self.hitbox.center = self.rect.center

    def update(self):
        self.fx += self.vx
        self.fy += self.vy

        self.rect.x = int(self.fx)
        self.rect.y = int(self.fy)

        self.update_hitbox()

        if (self.rect.top > win_height or self.rect.right < 0
            or self.rect.left > win_width or self.rect.bottom < 0):
            self.kill()

background = transform.scale(image.load("bg.jpg"), (win_width, win_height))
menu_bg = transform.scale(image.load("menu_bg.png"),(win_width,win_height))
bullets = sprite.Group()
turtle = Player("turtle.png", 450, 200, 2, 50, 50)
shield = Shield(turtle)
SPAWN_INTERVAL = 1000  # 1 second
GAME_DURATION = 60000  # 60 seconds
game = True
clock = time.Clock()
FPS = 60
spawn_timer = 0
spawn_delay = 30
spawn_queue = deque()
timer_text = Text(font_subtitle, (450, 40))
countdown_text = Text(font_title, (win_width // 2, win_height // 2))
warning_text = Text(font_subtitle,(win_width // 2, win_height // 2))
cooldown_text = FloatingText(font_system)
extra_end_text = Text(font_small, (win_width // 2, win_height // 2 + 100))
vfx = VFXManager()
hud = HUD()
HUD_HEIGHT = 100
end_text = Text(font_title, (win_width//2, win_height//2))
title_top = Text(font_title, (win_width // 2, win_height // 2 - 140))
title_bottom = Text(font_title, (win_width // 2, win_height // 2 - 20))
diff_top = Text(font_title, (win_width // 2, win_height // 2 - 270))
diff_bottom = Text(font_title, (win_width // 2, win_height // 2 - 150))
title_top.set_style((46,139,87),255)
title_bottom.set_style((5,16,148),255)
diff_top.set_style((10,17,114),255)
diff_bottom.set_style((5,16,148),255)
prompt_text = Text(font_subtitle_2, (win_width//2, win_height//2 + 100))
bubble_columns = []
last_column = 0

STATE_MENU = "menu"
STATE_PLAYING = "playing"
STATE_ENDING  = "ending"
STATE_STOPPED = "stopped"
STATE_DIFFICULTY = "difficulty"
STATE_BOSS = "boss"
DIFFICULTIES = {
    "easy": {
        "spawn_interval": 1400,
        "obstacle_speed_mult": 0.9,
        "lives": 4,
        "bombs": 4,
        "duration": 50000
    },
    "medium": {
        "spawn_interval": 1000,
        "obstacle_speed_mult": 1.0,
        "lives": 3,
        "bombs": 3,
        "duration": 60000
    },
    "hard": {
        "spawn_interval": 700,
        "obstacle_speed_mult": 1.1,
        "lives": 3,
        "bombs": 2,
        "duration": 70000
    }
}
current_difficulty = "medium"
def select_difficulty(diff):
    global current_difficulty
    current_difficulty = diff
    transition.start(mid_callback=enter_game)

easy_btn = Button(
    "button.png",
    center=(win_width//2, win_height//2 - 20),
    label="EASY",
    font=font_system,
    action=lambda: select_difficulty("easy"),
    text_offset=(-20, 0)
)

medium_btn = Button(
    "button.png",
    center=(win_width//2, win_height//2 + 80),
    label="MEDIUM",
    font=font_system,
    action=lambda: select_difficulty("medium"),
    text_offset=(-20, 0)
)

hard_btn = Button(
    "button.png",
    center=(win_width//2, win_height//2 + 180),
    label="HARD",
    font=font_system,
    action=lambda: select_difficulty("hard"),
    text_offset=(-20, 0)
)

subtitle_bar = SubtitleBar(win_width,height=70)

game_state = STATE_MENU
stop_fade_alpha = 0
stop_fade_speed = 2   # lower = slower fade
stop_fade_done = False

quit_text = Text(font_system,(win_width // 2, win_height // 2 + 160))

hud_bar = Surface((win_width, HUD_HEIGHT), SRCALPHA)
hud_bar.fill((10, 40, 60, 160))
transition = Transition((win_width, win_height))
draw.line(hud_bar,(100, 200, 220, 180),(0, HUD_HEIGHT - 2),(win_width, HUD_HEIGHT - 2),2)
end_headline = Surface((win_width, 235), SRCALPHA)
end_headline.fill((0, 0, 0, 100))
draw.line(end_headline, (100, 200, 220, 180), (0, 262), (win_width, 262), 2)
draw.line(end_headline, (100, 200, 220, 180), (0, 493), (win_width, 493), 2)
boss_manager = BossManager(
    player=turtle,
    screen_size=(win_width, win_height)
)

def start_game():
    transition.start(mid_callback=enter_difficulty)

def enter_difficulty():
    global game_state
    game_state = STATE_DIFFICULTY

def back():
    global game_state
    game_state = STATE_MENU

def back_to_menu():
    transition.start(mid_callback=back)

def enter_game():
    global warning_triggered, game_state, START_TIME, last_spawn_time, spawn_queue, bullets, current_vignette, warning_triggered, SPAWN_INTERVAL, GAME_DURATION

    warning_triggered = False
    game_state = STATE_PLAYING

    # reset timers
    START_TIME = time.get_ticks()
    last_spawn_time = START_TIME

    # clear obstacles/bullets & spawn queue
    bullets.empty()
    spawn_queue = deque()

    # reset player properties
    turtle.rect.x, turtle.rect.y = 450, 200  # your original spawn
    turtle.update_hitbox()
    turtle.lives = turtle.max_lives
    turtle.bombs = turtle.max_bombs
    turtle.invulnerability = False
    turtle.inv_timer = 0
    turtle.blink = False
    turtle.blink_timer = 0

    # clear visual effects
    vfx.effects = []

    # reset HUD/vignette/warnings
    hud.update_lives(turtle.lives, turtle.max_lives)
    hud.update_bombs(turtle.bombs, turtle.max_bombs)
    current_vignette = vignettes[turtle.lives]
    warning_triggered = False

    spec = DIFFICULTIES[current_difficulty]

    SPAWN_INTERVAL = spec["spawn_interval"]
    GAME_DURATION = spec["duration"]

    turtle.max_lives = spec["lives"]
    turtle.lives = spec["lives"]
    turtle.max_bombs = spec["bombs"]
    turtle.bombs = spec["bombs"]


def quit_game():
    global game
    game = False

start_button = Button(image_name="button.png",center=(win_width // 2, win_height // 2 + 100),label="START",font=font_system,action=start_game,text_offset=(-20,0))
quit_button = Button(image_name="button.png",center=(win_width // 2, win_height // 2 + 200),label="QUIT",font=font_system,action=quit_game,text_offset=(-20,0))
back_btn = Button("button.png",center=(win_width//2, win_height//2 + 280), label="BACK",font=font_system,action=back_to_menu,text_offset=(-20,0))
def create_vignette(width, height, R, G, B, strength):
    vignette = Surface((width, height), SRCALPHA)
    cx, cy = width // 2, height // 2
    max_dist = sqrt(cx*cx + cy*cy)

    inner_radius = max_dist * 0.55  # 🔑 NO vignette in center

    for y in range(height):
        for x in range(width):
            dx = x - cx
            dy = y - cy
            dist = sqrt(dx*dx + dy*dy)

            if dist < inner_radius:
                alpha = 0
            else:
                t = (dist - inner_radius) / (max_dist - inner_radius)
                alpha = int(strength * (t ** 2))  # 🔑 curve
                alpha = min(alpha,255)

            vignette.set_at((x, y), (R, G, B, alpha))

    return vignette

def draw_timer_arc(surface, center, radius, color, thickness=6, alpha=200):
    arc_surf = Surface((radius * 2, radius * 2), SRCALPHA)
    rect = arc_surf.get_rect(center=(radius, radius))

    draw.arc(arc_surf,(*color, alpha),rect,pi,          2 * pi,      thickness)
    surface.blit(arc_surf, (center[0] - radius, center[1] - radius))

def draw_timer_progress(surface, center, radius, color, progress, thickness=6):
    arc_surf = Surface((radius * 2, radius * 2), SRCALPHA)
    rect = arc_surf.get_rect(center=(radius, radius))

    start = pi
    end = pi + pi * progress  # 0 → empty, 1 → full

    draw.arc(arc_surf,(*color, 220),rect,start,end,thickness)

    surface.blit(arc_surf, (center[0] - radius, center[1] - radius))

vignettes = {
    3: create_vignette(win_width, win_height, 0, 255, 0, 60),
    2: create_vignette(win_width, win_height, 255, 255, 0, 100),
    1: create_vignette(win_width, win_height, 255, 0, 0, 150),
    0: create_vignette(win_width, win_height, 0, 0, 0, 220),
}

menu_fish = [BackgroundFish() for _ in range(12)]

warning_text_list = ["Lock In!!!", "Last Life!", "Dodge or Die..."]
won_text_list = ["I think I've recruited the person for this job...","Project Leader has been complaining, he won't be after this surely..",
                 "Keep up the good work mate, we got like a billion more to save. It's divided by 10.000 members I guess..."]
lost_text_list = ["I REALLY need to ramp up the required skill ceiling for such candidates man...","Hadn't I trained you well???",
                  "Here's a tip, turtles like neither plastic nor nets","Tough jobs will be compensated by satisfying results, don't give up mate!"]
damaged_text_list = ["Oi! Can't you see that's something you need to avoid!","Get a glasses man, obviously you can't see clearly..","Why did you let the turtle eat that?","Seriously? Your CV says you're good at this kind of stuff."]

current_vignette = vignettes[turtle.lives]
warning_start = 0

window.blit(background, (0,0))
START_TIME = time.get_ticks()
last_spawn_time = START_TIME
display.update()

while game:
    shake_offset = Vector2()
    events = event.get()
    for e in events:
        if e.type == QUIT:
            quit_game()
        if game_state == STATE_STOPPED and e.type == KEYDOWN:
            game_state = STATE_MENU
        if e.type == KEYDOWN and game_state == STATE_PLAYING:
            if e.key == K_x:
                turtle.use_bomb(bullets)

    for e in vfx.effects:
        if isinstance(e, ScreenShake):
            shake_offset += e.offset

    window.blit(background, shake_offset)

    # ---- UPDATE & DRAW ----
    if game_state == STATE_PLAYING:
        warning_triggered = False
        current_time = time.get_ticks()
        window.blit(hud_bar, (0, 0))
        if current_time - START_TIME < GAME_DURATION:
            if current_time - last_spawn_time >= SPAWN_INTERVAL:
                last_spawn_time = current_time

                spawn_queue += [("obs1.png", 0.9, 75, 100)] * 1
                spawn_queue += [("obs2.png", 0.9, 125, 125)] * 2
                spawn_queue += [("obs3.png", 0.9, 30, 80)] * 2

            if spawn_queue:
                img, speed, w, h = spawn_queue.popleft()
                speed *= DIFFICULTIES[current_difficulty]["obstacle_speed_mult"]
                bullets.add(Obstacle(img, speed, w, h))
        if current_time - START_TIME >= GAME_DURATION:
            game_state = STATE_BOSS
            boss_manager.start(
                kind="memoria",
                difficulty=current_difficulty,  # "easy" | "medium" | "hard"
                iterations=10  # scale later if needed
            )
        turtle.upd()
        turtle.update_hitbox()
        bullets.update()
        subtitle_bar.update()
        for o in bullets:
            if turtle.hitbox.colliderect(o.hitbox):
                turtle.take_damage(bullets)
                hud.update_lives(turtle.lives, turtle.max_lives)
                hud.update_bombs(turtle.bombs, turtle.max_bombs)
                current_vignette = vignettes[turtle.lives]
                if turtle.lives <= 0 and game_state == STATE_PLAYING:
                    game_state = STATE_ENDING
                    end_text.show_fade("You Lose...", color=(255, 60, 60), fade_in=2000, hold=5000, fade_out=1000)
                    extra_end_text.choose_dialogue(lost_text_list)
                    extra_end_text.set_style((255,255,0),255)

        draw_timer_arc(window, center=(win_width // 2, 0), radius=90, color=(100, 220, 255), thickness=5)

        time_left = max(0, (GAME_DURATION - (current_time - START_TIME)) // 1000)
        if time_left > 10:
            if time_left > 30:
                timer_text.set_style((0, 255, 0), 255)
                timer_text.show_instant(f"{time_left}")
                timer_text.draw(window)
            else:
                timer_text.set_style((255, 255, 0), 255)
                timer_text.show_instant(f"{time_left}")
                timer_text.draw(window)
        else:
            countdown_text.set_style((255, 0, 0), 100)
            countdown_text.show_instant(f"{time_left}")
            countdown_text.draw(window)
            overlay = Surface((win_width, win_height), SRCALPHA)
            overlay.fill((0, 0, 0, 50))
            window.blit(overlay, (0, 0))

        progress = time_left / (GAME_DURATION // 1000)
        base_radius = 90
        pulse = int(2 * sin(time.get_ticks() * 0.01))
        draw_timer_progress(window, (win_width // 2, 0), base_radius + pulse,(0, 255, 0) if time_left > 30 else (255, 255, 0), progress)

    for o in bullets:
        window.blit(o.image, o.rect.move(shake_offset))
    turtle.draw(window)
    if turtle.invulnerability:
        shield.update()
        window.blit(shield.image, shield.rect)
    if turtle.lives == 1:
        if not warning_triggered:
            warning_start = time.get_ticks()
            warning_text.choose_dialogue(warning_text_list)
            warning_triggered = True

        if time.get_ticks() - warning_start < 5000:
            warning_headline = Surface((win_width,150),SRCALPHA)
            warning_headline.fill((0,0,0,100))
            window.blit(warning_headline,(0,275))
            warning_text.set_style((255, 0, 0), 255)
            warning_text.update()
            warning_text.draw(window)

    if game_state == STATE_ENDING:
        window.blit(hud_bar, (0, 0))
        overlay = Surface((win_width, win_height), SRCALPHA)
        overlay.fill((0, 0, 0, 40))
        window.blit(overlay, (0, 0))
        window.blit(end_headline, (0, 260))
        end_text.update()
        end_text.draw(window)
        if end_text._phase == "holding":
            extra_end_text.update()
            extra_end_text.draw(window)
        # once fade is done
        if not end_text.is_active():
            game_state = STATE_STOPPED

    cooldown_text.draw(window)
    hud.draw(window)
    hud.update_lives(turtle.lives, turtle.max_lives)
    hud.update_bombs(turtle.bombs, turtle.max_bombs)
    subtitle_bar.draw(window)
    window.blit(current_vignette, (0, 0))
    vfx.update()
    vfx.draw(window)
    if game_state == STATE_STOPPED:
        # fade background to black
        if stop_fade_alpha < 255:
            stop_fade_alpha = min(255, stop_fade_alpha + stop_fade_speed)
        else:
            stop_fade_done = True

        fade_overlay = Surface((win_width, win_height), SRCALPHA)
        fade_overlay.fill((0, 0, 0, stop_fade_alpha))
        window.blit(fade_overlay, (0, 0))

        # once fully dark, show quit text
        if stop_fade_done:
            quit_text.show_instant("[Press any key to quit]")
            quit_text.set_style((200, 200, 200), alpha=min(255,stop_fade_alpha))
            quit_text.draw(window)

    if game_state == STATE_MENU:
        window.blit(menu_bg, (0, 0))
        for fish in menu_fish:
            fish.update()
            fish.draw(window)
        now = time.get_ticks()

        # occasionally spawn a column
        if now - last_column > randint(3000, 6000):
            bubble_columns.append(BubbleColumn())
            last_column = now

        for col in bubble_columns[:]:
            col.update()
            col.draw(window)
            if col.is_finished():
                bubble_columns.remove(col)

        window.blit(vignettes[2],(0,0))
        window.blit(IMAGES["decor_turtle.png"],(win_width // 2 + 100, win_height // 2 + 100))

        title_top.show_instant("TURTLE")
        title_bottom.show_instant("PROTOCOL")
        title_top.draw(window)
        title_bottom.draw(window)

        start_button.update(events)
        start_button.draw(window)
        quit_button.update(events)
        quit_button.draw(window)

    if game_state == STATE_DIFFICULTY:
        window.blit(menu_bg, (0, 0))

        diff_top.show_instant("SELECT")
        diff_bottom.show_instant("DIFFICULTY")
        diff_top.draw(window)
        diff_bottom.draw(window)

        easy_btn.update(events)
        medium_btn.update(events)
        hard_btn.update(events)
        back_btn.update(events)

        easy_btn.draw(window)
        medium_btn.draw(window)
        hard_btn.draw(window)
        back_btn.draw(window)

    if game_state == STATE_BOSS:
        boss_result = boss_manager.update(event.get())

        if boss_result is not None:
            # Boss finished
            if boss_result:
                end_text.show_fade("You Win!", color=(120, 255, 120))
            else:
                end_text.show_fade("You Lose...", color=(255, 60, 60))

            game_state = STATE_ENDING

        boss_manager.draw(window)

    transition.update()
    transition.draw(window)
    display.update()
    clock.tick(FPS)
