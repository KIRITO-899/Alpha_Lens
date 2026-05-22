import os
import glob

def find_dbs():
    for root, dirs, files in os.walk('.'):
        for file in files:
            if file.endswith('.db'):
                path = os.path.join(root, file)
                print(f"Found DB: {path} (size: {os.path.getsize(path)} bytes)")

if __name__ == '__main__':
    find_dbs()
