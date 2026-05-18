#!/usr/bin/env python3
import fcntl
import os
import signal
import struct
import time

I2C_SLAVE = 0x0703
I2C_BUS = os.environ.get("FT6336_I2C", "/dev/i2c-3")
I2C_ADDR = int(os.environ.get("FT6336_ADDR", "0x38"), 0)
SCREEN_W = int(os.environ.get("FT6336_SCREEN_W", "480"))
SCREEN_H = int(os.environ.get("FT6336_SCREEN_H", "320"))
RAW_W = int(os.environ.get("FT6336_RAW_W", "320"))
RAW_H = int(os.environ.get("FT6336_RAW_H", "480"))
MAP = os.environ.get("FT6336_MAP", "rot90")

EV_SYN = 0x00
EV_KEY = 0x01
EV_ABS = 0x03
SYN_REPORT = 0
BTN_TOUCH = 0x14A
ABS_X = 0x00
ABS_Y = 0x01
ABS_PRESSURE = 0x18
BUS_I2C = 0x18

UI_SET_EVBIT = 0x40045564
UI_SET_KEYBIT = 0x40045565
UI_SET_ABSBIT = 0x40045567
UI_DEV_CREATE = 0x5501
UI_DEV_DESTROY = 0x5502

running = True


def stop(_signum, _frame):
    global running
    running = False


signal.signal(signal.SIGTERM, stop)
signal.signal(signal.SIGINT, stop)


def clamp(value, lo, hi):
    return max(lo, min(hi, value))


def map_point(rx, ry):
    if MAP == "rot270":
        x = RAW_H - 1 - ry
        y = rx
    elif MAP == "none":
        x = rx * (SCREEN_W - 1) // max(1, RAW_W - 1)
        y = ry * (SCREEN_H - 1) // max(1, RAW_H - 1)
    elif MAP == "flipxy":
        x = ry
        y = rx
    else:
        x = ry
        y = RAW_W - 1 - rx
    return clamp(x, 0, SCREEN_W - 1), clamp(y, 0, SCREEN_H - 1)


def emit(fd, etype, code, value):
    now = time.time()
    sec = int(now)
    usec = int((now - sec) * 1000000)
    os.write(fd, struct.pack("llHHI", sec, usec, etype, code, value))


def create_uinput():
    fd = os.open("/dev/uinput", os.O_WRONLY | os.O_NONBLOCK)
    for ev in (EV_KEY, EV_ABS):
        fcntl.ioctl(fd, UI_SET_EVBIT, ev)
    fcntl.ioctl(fd, UI_SET_KEYBIT, BTN_TOUCH)
    for abs_code in (ABS_X, ABS_Y, ABS_PRESSURE):
        fcntl.ioctl(fd, UI_SET_ABSBIT, abs_code)

    name = b"SJAgent FT6336U Touch"
    absmax = [0] * 64
    absmin = [0] * 64
    absfuzz = [0] * 64
    absflat = [0] * 64
    absmax[ABS_X] = SCREEN_W - 1
    absmax[ABS_Y] = SCREEN_H - 1
    absmax[ABS_PRESSURE] = 255
    uidev = struct.pack("80sHHHHi", name, BUS_I2C, 0x534A, 0x6336, 1, 0)
    uidev += struct.pack("64i", *absmax)
    uidev += struct.pack("64i", *absmin)
    uidev += struct.pack("64i", *absfuzz)
    uidev += struct.pack("64i", *absflat)
    os.write(fd, uidev)
    fcntl.ioctl(fd, UI_DEV_CREATE)
    time.sleep(0.3)
    return fd


def open_i2c():
    fd = os.open(I2C_BUS, os.O_RDWR)
    fcntl.ioctl(fd, I2C_SLAVE, I2C_ADDR)
    return fd


def read_touch(fd):
    os.write(fd, bytes([0x02]))
    data = os.read(fd, 14)
    if len(data) < 5:
        return None
    points = data[0] & 0x0F
    if points == 0:
        return None
    rx = ((data[1] & 0x0F) << 8) | data[2]
    ry = ((data[3] & 0x0F) << 8) | data[4]
    return rx, ry


def main():
    i2c = open_i2c()
    uinp = create_uinput()
    pressed = False
    last_log = 0
    print(f"FT6336 touch bridge started bus={I2C_BUS} addr=0x{I2C_ADDR:02x} map={MAP}", flush=True)
    try:
        while running:
            pt = read_touch(i2c)
            if pt:
                rx, ry = pt
                x, y = map_point(rx, ry)
                emit(uinp, EV_KEY, BTN_TOUCH, 1)
                emit(uinp, EV_ABS, ABS_X, x)
                emit(uinp, EV_ABS, ABS_Y, y)
                emit(uinp, EV_ABS, ABS_PRESSURE, 180)
                emit(uinp, EV_SYN, SYN_REPORT, 0)
                pressed = True
                now = time.time()
                if now - last_log > 0.5:
                    print(f"TOUCH raw=({rx},{ry}) mapped=({x},{y})", flush=True)
                    last_log = now
            elif pressed:
                emit(uinp, EV_KEY, BTN_TOUCH, 0)
                emit(uinp, EV_ABS, ABS_PRESSURE, 0)
                emit(uinp, EV_SYN, SYN_REPORT, 0)
                pressed = False
            time.sleep(0.015)
    finally:
        try:
            fcntl.ioctl(uinp, UI_DEV_DESTROY)
        except Exception:
            pass
        os.close(uinp)
        os.close(i2c)


if __name__ == "__main__":
    main()
