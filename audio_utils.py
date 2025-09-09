import pyaudio

def find_audio_device_index(device_name_part: str, device_type: str = "input") -> int:
    """
    Найти индекс аудиоустройства по части имени
    device_type: "input" для микрофонов, "output" для динамиков
    """
    p = pyaudio.PyAudio()
    
    try:
        for i in range(p.get_device_count()):
            try:
                device_info = p.get_device_info_by_index(i)
                device_name = device_info.get('name', '').lower()
                
                if device_type == "input" and device_info.get('maxInputChannels', 0) == 0:
                    continue
                elif device_type == "output" and device_info.get('maxOutputChannels', 0) == 0:
                    continue
                
                if device_name_part.lower() in device_name:
                    print(f"Найдено {device_type} устройство: {device_info['name']} (индекс: {i})")
                    return i
                    
            except Exception as e:
                continue
                
        print(f"Устройство '{device_name_part}' не найдено")
        return None
        
    finally:
        p.terminate()

def list_audio_devices():
    """Показать все доступные аудиоустройства"""
    p = pyaudio.PyAudio()
    
    print("=== ДОСТУПНЫЕ АУДИОУСТРОЙСТВА ===")
    try:
        for i in range(p.get_device_count()):
            try:
                device_info = p.get_device_info_by_index(i)
                max_inputs = device_info.get('maxInputChannels', 0)
                max_outputs = device_info.get('maxOutputChannels', 0)
                
                device_type = []
                if max_inputs > 0:
                    device_type.append("INPUT")
                if max_outputs > 0:
                    device_type.append("OUTPUT")
                
                print(f"[{i}] {device_info['name']} ({', '.join(device_type)})")
                
            except Exception as e:
                print(f"[{i}] Ошибка получения информации: {e}")
                
    finally:
        p.terminate()