import math
import random
from array import array

import pygame
from game.beat import Note, LANES, LANE_KEYS, LANE_LABELS, LANE_COLORS

WIDTH, HEIGHT = 480, 640
FPS = 60
BPM = 120
HIT_Y = HEIGHT - 80
HIT_WINDOW = 30
BG = (15, 10, 25)
LANE_W = WIDTH // LANES


def create_hit_sound(frequency, duration_ms=90, volume=0.35):
    sample_rate = 22050
    total_samples = int(sample_rate * duration_ms / 1000)
    samples = array('h')

    for i in range(total_samples):
        t = i / sample_rate
        fade = max(0.0, 1.0 - (i / total_samples) * 1.2)
        value = int(volume * fade * 32767 * math.sin(2 * math.pi * frequency * t))
        samples.append(value)

    sound = pygame.mixer.Sound(buffer=samples.tobytes())
    sound.set_volume(0.6)
    return sound


class GameEngine:
    def __init__(self):
        pygame.init()
        pygame.mixer.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Rhythm Tap")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("monospace", 26, bold=True)
        self.big_font = pygame.font.SysFont("monospace", 44, bold=True)
        self.hit_sounds = {
            "PERFECT": create_hit_sound(880),
            "GREAT": create_hit_sound(660),
            "OK": create_hit_sound(440),
        }
        self.reset()

    def reset(self):
        self.notes = []
        self.score = 0
        self.combo = 0
        self.max_combo = 0
        self.misses = 0
        self.perfect = 0
        self.great = 0
        self.ok = 0
        self.speed = 5
        self.frame = 0
        self.feedback = []  # (text, color, ttl, x, y)
        self.game_over = False
        self.held_lanes = set()
        self.bpm = BPM
        self.beat_interval_ms = 60000 / self.bpm
        self.song_start_time = pygame.time.get_ticks()
        self.next_spawn_time = self.song_start_time + self.beat_interval_ms

    def spawn_note(self):
        lane = random.randint(0, LANES - 1)
        is_hold = random.random() < 0.20
        self.notes.append(Note(lane, y=-30, speed=self.speed, is_hold=is_hold))

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT: return False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_r:
                    self.reset()
                elif not self.game_over:
                    for i, key in enumerate(LANE_KEYS):
                        if event.key == key:
                            self.held_lanes.add(i)
                            self.process_tap(i)
            elif event.type == pygame.KEYUP:
                for i, key in enumerate(LANE_KEYS):
                    if event.key == key:
                        self.held_lanes.discard(i)
        return True

    def process_tap(self, lane):
        # Find closest note in this lane near hit zone
        best = None
        best_dist = 9999
        for note in self.notes:
            if note.lane == lane and not note.hit and not note.missed:
                note_center = note.y + (note.get_rect(lane * LANE_W + LANE_W // 2).height // 2)
                dist = abs(note_center - HIT_Y)
                if dist < best_dist:
                    best_dist = dist
                    best = note
        lane_x = lane * LANE_W + LANE_W // 2

        if not best:
            self.combo = 0
            self.feedback.append(["MISS", (220,60,60), 40, lane_x, HIT_Y - 30])
            return

        if best.is_hold:
            if best_dist <= HIT_WINDOW and best.hold_start_time is None:
                best.hold_start_time = pygame.time.get_ticks()
                self.feedback.append(["HOLD", (150, 220, 255), 20, lane_x, HIT_Y - 30])
            else:
                self.combo = 0
                self.feedback.append(["MISS", (220,60,60), 40, lane_x, HIT_Y - 30])
            return

        if best_dist <= HIT_WINDOW:
            best.hit = True
            if best_dist < 8:
                grade, pts = "PERFECT", 300
                col = (255, 220, 0)
                self.perfect += 1
            elif best_dist < 18:
                grade, pts = "GREAT", 200
                col = (100, 220, 100)
                self.great += 1
            else:
                grade, pts = "OK", 100
                col = (180, 180, 255)
                self.ok += 1
            self.combo += 1
            self.max_combo = max(self.max_combo, self.combo)
            self.score += pts * max(1, self.combo // 5)
            self.feedback.append([grade, col, 40, lane_x, HIT_Y - 30])
            self.hit_sounds[grade].play()
        else:
            self.combo = 0
            self.feedback.append(["MISS", (220,60,60), 40, lane_x, HIT_Y - 30])

    def update(self):
        if self.game_over: return
        self.frame += 1

        now = pygame.time.get_ticks()
        while now >= self.next_spawn_time:
            self.spawn_note()
            self.next_spawn_time += self.beat_interval_ms

        for note in self.notes:
            note.update()

            if note.is_hold and not note.hit and not note.missed:
                if note.hold_start_time is not None:
                    if note.lane not in self.held_lanes:
                        note.missed = True
                        self.misses += 1
                        self.combo = 0
                        self.feedback.append(["MISS", (220,60,60), 40, note.lane * LANE_W + LANE_W // 2, HIT_Y - 30])
                    elif now - note.hold_start_time >= note.hold_duration_ms:
                        note.hit = True
                        self.perfect += 1
                        self.combo += 1
                        self.max_combo = max(self.max_combo, self.combo)
                        self.score += 400 * max(1, self.combo // 5)
                        self.feedback.append(["HOLD!", (120,220,255), 40, note.lane * LANE_W + LANE_W // 2, HIT_Y - 30])
                elif note.y > HIT_Y + HIT_WINDOW + Note.HEIGHT:
                    note.missed = True
                    self.misses += 1
                    self.combo = 0

            elif not note.hit and not note.missed and note.y > HIT_Y + HIT_WINDOW + Note.HEIGHT:
                note.missed = True
                self.misses += 1
                self.combo = 0

        self.notes = [n for n in self.notes if not (n.hit or n.missed and n.y > HEIGHT + 10)]
        self.feedback = [[t,c,ttl-1,x,y] for t,c,ttl,x,y in self.feedback if ttl > 1]

        if self.misses >= 15:
            self.game_over = True

    def draw(self):
        self.screen.fill(BG)
        # Lane dividers
        for i in range(LANES + 1):
            pygame.draw.line(self.screen, (40,40,60), (i*LANE_W,0), (i*LANE_W,HEIGHT), 1)

        # Hit line
        pygame.draw.line(self.screen, (80,80,100), (0,HIT_Y), (WIDTH,HIT_Y), 2)
        for i in range(LANES):
            lx = i*LANE_W + LANE_W//2
            pygame.draw.rect(self.screen, LANE_COLORS[i],
                pygame.Rect(lx - Note.WIDTH//2, HIT_Y - 12, Note.WIDTH, 24), border_radius=6)
            lbl = self.font.render(LANE_LABELS[i], True, (20,20,20))
            self.screen.blit(lbl, (lx - lbl.get_width()//2, HIT_Y - 10))

        # Notes
        for note in self.notes:
            if note.hit: continue
            lx = note.lane * LANE_W + LANE_W // 2
            rect = note.get_rect(lx)
            if note.is_hold:
                outline = pygame.Rect(rect.x - 3, rect.y - 3, rect.width + 6, rect.height + 6)
                pygame.draw.rect(self.screen, (255, 255, 255), outline, border_radius=10, width=2)
                pygame.draw.rect(self.screen, (18, 18, 28), rect, border_radius=10)
                pygame.draw.rect(self.screen, LANE_COLORS[note.lane], rect.inflate(-8, -8), border_radius=8)
                pygame.draw.rect(self.screen, (255, 255, 255), (rect.x + 10, rect.y + rect.height - 10, rect.width - 20, 6), border_radius=3)
                if note.hold_start_time is not None and not note.hit:
                    hold_pct = min(1.0, max(0.0, (pygame.time.get_ticks() - note.hold_start_time) / note.hold_duration_ms))
                    fill_w = max(4, int((rect.width - 20) * hold_pct))
                    pygame.draw.rect(self.screen, (120, 220, 255), (rect.x + 10, rect.y + rect.height - 10, fill_w, 6), border_radius=3)
                hold_label = self.font.render("HOLD", True, (255,255,255))
                self.screen.blit(hold_label, (rect.centerx - hold_label.get_width() // 2, rect.y - 22))
            else:
                pygame.draw.rect(self.screen, LANE_COLORS[note.lane], rect, border_radius=5)

        # Feedback
        for text, color, ttl, x, y in self.feedback:
            surf = self.font.render(text, True, color)
            alpha = min(255, ttl * 7)
            surf.set_alpha(alpha)
            self.screen.blit(surf, (x - surf.get_width()//2, y))

        # HUD
        sc = self.font.render(f"Score: {self.score}", True, (220,220,220))
        co = self.font.render(f"Combo: {self.combo}x", True, (255,220,80))
        mi = self.font.render(f"Misses: {self.misses}/15", True, (220,100,100))
        bp = self.font.render(f"BPM: {self.bpm}", True, (180,200,255))
        self.screen.blit(sc, (10, 10))
        self.screen.blit(co, (10, 40))
        self.screen.blit(mi, (WIDTH - 170, 10))
        self.screen.blit(bp, (WIDTH - 120, 40))

        if self.game_over:
            ov = pygame.Surface((WIDTH,HEIGHT), pygame.SRCALPHA)
            ov.fill((0,0,0,180))
            self.screen.blit(ov,(0,0))

            total_notes = max(1, self.perfect + self.great + self.ok + self.misses)
            accuracy = round((self.perfect * 1.0 + self.great * 0.75 + self.ok * 0.5) / total_notes * 100, 1)

            msg = self.big_font.render("GAME OVER", True, (220,60,60))
            sc_msg = self.font.render(f"Final Score: {self.score}  Max Combo: {self.max_combo}x", True, (200,200,200))
            summary_title = self.font.render("Summary", True, (255,255,255))
            summary_x = WIDTH // 2 - 90
            summary_y = HEIGHT // 2 - 45
            summary_lines = [
                ("PERFECT", self.perfect, (255,220,0)),
                ("GREAT", self.great, (100,220,100)),
                ("OK", self.ok, (180,180,255)),
                ("MISS", self.misses, (220,100,100)),
                ("Accuracy", f"{accuracy}%", (255,255,255)),
            ]

            self.screen.blit(msg, (WIDTH//2-msg.get_width()//2, HEIGHT//2-150))
            self.screen.blit(sc_msg, (WIDTH//2-sc_msg.get_width()//2, HEIGHT//2-110))
            self.screen.blit(summary_title, (WIDTH//2-summary_title.get_width()//2, summary_y - 20))

            for idx, (label, value, color) in enumerate(summary_lines):
                label_surf = self.font.render(f"{label}:", True, (220,220,220))
                value_surf = self.font.render(str(value), True, color)
                y = summary_y + idx * 28
                self.screen.blit(label_surf, (summary_x, y))
                self.screen.blit(value_surf, (summary_x + 110, y))

            restart = self.font.render("Press R to Restart", True, (160,160,160))
            self.screen.blit(restart, (WIDTH//2-restart.get_width()//2, HEIGHT//2+120))
        pygame.display.flip()

    def run(self):
        running = True
        while running:
            running = self.handle_events()
            self.update()
            self.draw()
            self.clock.tick(FPS)
        pygame.quit()
