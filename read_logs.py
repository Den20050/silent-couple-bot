import os

def tail_bytes(file_path, num_bytes=100000):
    try:
        if not os.path.exists(file_path):
            return f"File not found: {file_path}"
        
        file_size = os.path.getsize(file_path)
        if file_size == 0:
            return "File is empty"
            
        with open(file_path, 'rb') as f:
            if file_size > num_bytes:
                f.seek(-num_bytes, os.SEEK_END)
            else:
                f.seek(0)
            
            content = f.read()
            return content.decode('utf-8', errors='replace')
    except Exception as e:
        return f"Error reading file {file_path}: {e}"

if __name__ == "__main__":
    print("--- worker_24h.log TAIL ---")
    print(tail_bytes("worker_24h.log", 50000)) # Last 50KB
    print("\n\n--- webhook_24h.log TAIL ---")
    print(tail_bytes("webhook_24h.log", 50000)) # Last 50KB
