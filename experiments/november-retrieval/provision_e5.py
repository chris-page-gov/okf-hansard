"""Download only public model data, verify against pinned Hugging Face object IDs."""
from hashlib import sha1, sha256
from pathlib import Path
import sys
from urllib.request import urlopen
REV = "ffb93f3bd4047442299a41ebb6fa998a38507c52"
# The weights use the LFS SHA-256 digest. Other files use a Git blob object ID.
def read_checksums():
    manifest = Path(__file__).with_name("e5-checksums.txt")
    entries = {}
    for line in manifest.read_text(encoding="ascii").splitlines():
        digest, name = line.split()
        entries[name] = digest
    return entries

PINS = read_checksums()

def checksum(name,data):
    return sha256(data).hexdigest() if name=="model.safetensors" else sha1(b"blob "+str(len(data)).encode()+b"\0"+data).hexdigest()
def verify(folder):
    for name, expected in PINS.items():
        if checksum(name,(folder/name).read_bytes())!=expected:
            raise ValueError("Model pin mismatch: "+name)
if __name__=="__main__":
    folder=Path(sys.argv[1])
    for name, expected in PINS.items():
        path=folder/name
        if path.exists():
            continue
        with urlopen(f"https://huggingface.co/intfloat/e5-small-v2/resolve/{REV}/{name}",timeout=120) as response:
            data=response.read(134_000_000)
        if checksum(name,data)!=expected:
            raise ValueError(name)
        with path.open('xb') as f: f.write(data)
    verify(folder)
