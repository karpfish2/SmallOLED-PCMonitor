#!/usr/bin/env python3
"""
PC Stats Monitor для Arch Linux (Ryzen + NVIDIA)
"""

import psutil
import socket
import time
import json
import subprocess
from datetime import datetime
import os
import glob

ESP32_IP = "192.168.0.19"
UDP_PORT = 4210
BROADCAST_INTERVAL = 3

sensor_paths = {
    "cpu_temp": None,
    "fan": None,
    "gpu_temp": None
}

def detect_hwmon_sensors():
    print("Сканирование сенсоров...")

    base = "/sys/class/hwmon/"

    try:
        for dev in os.listdir(base):
            path = os.path.join(base, dev)
            name_file = os.path.join(path, "name")

            if not os.path.isfile(name_file):
                continue

            with open(name_file, "r") as f:
                name = f.read().strip()

            print(f"Найден: {name} ({dev})")

            # Ryzen CPU температура (k10temp, zenpower)
            if name in ["k10temp", "zenpower"]:
                # Пробуем Tdie или Tctl
                for temp_label in ["temp1_input", "temp2_input"]:
                    temp_file = os.path.join(path, temp_label)
                    if os.path.isfile(temp_file):
                        sensor_paths["cpu_temp"] = temp_file
                        print(f"✓ CPU temp: {temp_file}")
                        break

            # Вентиляторы (обычно в it87, nct6775 и т.д.)
            if not sensor_paths["fan"]:
                fan_files = glob.glob(os.path.join(path, "fan*_input"))
                if fan_files:
                    sensor_paths["fan"] = fan_files[0]
                    print(f"✓ Fan: {fan_files[0]}")

    except Exception as e:
        print(f"Ошибка: {e}")

def read_number(path):
    try:
        with open(path, "r") as f:
            return int(f.read().strip())
    except:
        return None

def get_gpu_temp():
    """NVIDIA RTX 3080 Ti"""
    try:
        output = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader,nounits"],
            stderr=subprocess.DEVNULL,
            timeout=2
        )
        return int(output.decode().strip())
    except:
        return None

def get_sensor_values():
    cpu_temp = None
    fan = None
    gpu_temp = None

    if sensor_paths["cpu_temp"]:
        t = read_number(sensor_paths["cpu_temp"])
        cpu_temp = t // 1000 if t else None

    if sensor_paths["fan"]:
        fan = read_number(sensor_paths["fan"])

    gpu_temp = get_gpu_temp()

    return fan, cpu_temp, gpu_temp

def get_system_stats():
    fan_speed, cpu_temp, gpu_temp = get_sensor_values()

    stats = {
        'timestamp': datetime.now().strftime('%H:%M'),
        'cpu_percent': round(psutil.cpu_percent(interval=0), 1),
        'ram_percent': round(psutil.virtual_memory().percent, 1),
        'ram_used_gb': round(psutil.virtual_memory().used / (1024**3), 1),
        'ram_total_gb': round(psutil.virtual_memory().total / (1024**3), 1),
        'disk_percent': round(psutil.disk_usage('/').percent, 1),
        'cpu_temp': cpu_temp,
        'gpu_temp': gpu_temp,
        'fan_speed': fan_speed,
        'status': 'online'
    }

    return stats

def send_stats(sock, stats):
    try:
        msg = json.dumps(stats).encode()
        sock.sendto(msg, (ESP32_IP, UDP_PORT))
        print(f"[{stats['timestamp']}] CPU {stats['cpu_percent']}% ({stats['cpu_temp']}°C) | "
              f"GPU {stats['gpu_temp']}°C | RAM {stats['ram_percent']}% | Fan {stats['fan_speed']}")
    except Exception as e:
        print(f"Ошибка отправки: {e}")

def main():
    print("=" * 60)
    print("PC Stats Monitor - Arch Linux (Ryzen + NVIDIA)")
    print("=" * 60)

    detect_hwmon_sensors()

    print("-" * 60)
    print("Мониторинг запущен... (CTRL+C для остановки)")
    print("-" * 60)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    psutil.cpu_percent(interval=1)

    try:
        while True:
            stats = get_system_stats()
            send_stats(sock, stats)
            time.sleep(BROADCAST_INTERVAL)
    except KeyboardInterrupt:
        print("\nОстановлено.")
    finally:
        sock.close()

if __name__ == "__main__":
    main()
