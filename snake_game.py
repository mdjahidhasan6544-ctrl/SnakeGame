from __future__ import annotations

import ctypes
import os
import random
import sys
import time
from collections import deque
from dataclasses import dataclass
from typing import Deque

if os.name == "nt":
    import msvcrt
else:
    import select
    import termios
    import tty


UP = (0, -1)
DOWN = (0, 1)
LEFT = (-1, 0)
RIGHT = (1, 0)
OPPOSITE = {UP: DOWN, DOWN: UP, LEFT: RIGHT, RIGHT: LEFT}
KEYBINDS = {
    "w": UP,
    "W": UP,
    "\xe0H": UP,
    "\x00H": UP,
    "s": DOWN,
    "S": DOWN,
    "\xe0P": DOWN,
    "\x00P": DOWN,
    "a": LEFT,
    "A": LEFT,
    "\xe0K": LEFT,
    "\x00K": LEFT,
    "d": RIGHT,
    "D": RIGHT,
    "\xe0M": RIGHT,
    "\x00M": RIGHT,
}


@dataclass
class GameState:
    width: int = 24
    height: int = 16
    tick_rate: float = 0.12

    def __post_init__(self) -> None:
        start_x = self.width // 2
        start_y = self.height // 2
        self.snake: Deque[tuple[int, int]] = deque(
            [(start_x, start_y), (start_x - 1, start_y), (start_x - 2, start_y)]
        )
        self.direction = RIGHT
        self.pending_direction = RIGHT
        self.score = 0
        self.food = self._spawn_food()
        self.game_over = False
        self.win = False

    def _spawn_food(self) -> tuple[int, int]:
        available = [
            (x, y)
            for y in range(self.height)
            for x in range(self.width)
            if (x, y) not in self.snake
        ]
        if not available:
            self.win = True
            return (-1, -1)
        return random.choice(available)

    def change_direction(self, new_direction: tuple[int, int]) -> None:
        if new_direction != OPPOSITE[self.direction]:
            self.pending_direction = new_direction

    def update(self) -> None:
        self.direction = self.pending_direction
        head_x, head_y = self.snake[0]
        dx, dy = self.direction
        new_head = (head_x + dx, head_y + dy)

        hit_wall = not (0 <= new_head[0] < self.width and 0 <= new_head[1] < self.height)
        growing = new_head == self.food
        body_to_check = self.snake if growing else list(self.snake)[:-1]
        hit_self = new_head in body_to_check
        if hit_wall or hit_self:
            self.game_over = True
            return

        self.snake.appendleft(new_head)
        if new_head == self.food:
            self.score += 1
            self.food = self._spawn_food()
        else:
            self.snake.pop()


def enable_ansi_escape_sequences() -> None:
    if os.name != "nt":
        return

    kernel32 = ctypes.windll.kernel32
    handle = kernel32.GetStdHandle(-11)
    mode = ctypes.c_uint32()
    if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
        kernel32.SetConsoleMode(handle, mode.value | 0x0004)


class Keyboard:
    def __enter__(self) -> "Keyboard":
        if os.name != "nt":
            self.fd = sys.stdin.fileno()
            self.old_settings = termios.tcgetattr(self.fd)
            tty.setcbreak(self.fd)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if os.name != "nt":
            termios.tcsetattr(self.fd, termios.TCSADRAIN, self.old_settings)

    def get_key(self) -> str | None:
        if os.name == "nt":
            if not msvcrt.kbhit():
                return None
            first = msvcrt.getwch()
            if first in ("\x00", "\xe0"):
                return first + msvcrt.getwch()
            return first

        ready, _, _ = select.select([sys.stdin], [], [], 0)
        if not ready:
            return None
        first = sys.stdin.read(1)
        if first == "\x1b":
            seq = first
            while True:
                ready, _, _ = select.select([sys.stdin], [], [], 0)
                if not ready:
                    break
                seq += sys.stdin.read(1)
            return {"\x1b[A": "w", "\x1b[B": "s", "\x1b[D": "a", "\x1b[C": "d"}.get(seq, first)
        return first


def clear_screen() -> None:
    print("\033[2J\033[H", end="")


def render(state: GameState) -> None:
    clear_screen()
    print(f"Terminal Snake  |  Score: {state.score}")
    print("Use arrow keys or WASD. Press Q to quit.")
    top_bottom = "+" + "-" * state.width + "+"
    print(top_bottom)
    snake_body = set(state.snake)
    head = state.snake[0]
    for y in range(state.height):
        row = []
        for x in range(state.width):
            point = (x, y)
            if point == head:
                row.append("@")
            elif point == state.food:
                row.append("*")
            elif point in snake_body:
                row.append("O")
            else:
                row.append(" ")
        print("|" + "".join(row) + "|")
    print(top_bottom)

    if state.game_over:
        print("\nGame over! Press R to restart or Q to quit.")
    elif state.win:
        print("\nYou filled the whole board! Press R to play again or Q to quit.")


def play() -> None:
    enable_ansi_escape_sequences()
    print("Launching Terminal Snake...")
    time.sleep(0.5)

    with Keyboard() as keyboard:
        state = GameState()
        last_tick = time.perf_counter()
        render(state)

        while True:
            key = keyboard.get_key()
            if key:
                if key in ("q", "Q"):
                    break
                if key in ("r", "R") and (state.game_over or state.win):
                    state = GameState()
                    last_tick = time.perf_counter()
                    render(state)
                    continue
                direction = KEYBINDS.get(key)
                if direction and not (state.game_over or state.win):
                    state.change_direction(direction)

            now = time.perf_counter()
            if not (state.game_over or state.win) and now - last_tick >= state.tick_rate:
                state.update()
                render(state)
                last_tick = now

            time.sleep(0.01)

    clear_screen()
    print("Thanks for playing Terminal Snake!")


if __name__ == "__main__":
    try:
        play()
    except KeyboardInterrupt:
        clear_screen()
        print("Thanks for playing Terminal Snake!")
