"""Cifrado de los datos privados (bonos y fondo NL) del dashboard.

Esquema híbrido para que los cortes automáticos NO necesiten el PIN:
- data/llave.json: llave pública RSA-OAEP (para cifrar) + llave privada cifrada con AES-GCM
  usando PBKDF2-SHA256(PIN). Solo el navegador, con el PIN, abre la llave privada.
- Cada bloque cifrado: {"k": llave AES envuelta con RSA-OAEP, "iv": ..., "ct": AES-GCM(json)} en base64.

Uso:
  python3 -I scripts/cripto.py init <PIN>            # llave nueva (lo cifrado antes ya no se podrá abrir)
  python3 -I scripts/cripto.py cambiar <PIN> <NUEVO> # cambia el PIN sin tocar los datos
  python3 -I scripts/cripto.py probar <PIN>          # abre latest.json y bonos_detalle.json para verificar
"""
import base64, json, os, sys, subprocess

try:
    from cryptography.hazmat.primitives.asymmetric import rsa, padding
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
except ImportError:  # contenedor nuevo sin la librería
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "--break-system-packages", "cryptography"], check=True)
    from cryptography.hazmat.primitives.asymmetric import rsa, padding
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LLAVE = os.path.join(ROOT, "data", "llave.json")
ITER = 600000
b64 = lambda b: base64.b64encode(b).decode()
ub64 = base64.b64decode
OAEP = padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None)


def _kdf(pin, salt):
    return PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=ITER).derive(str(pin).encode())


def _pin_ok(pin):
    if not (str(pin).isdigit() and 4 <= len(str(pin)) <= 8):
        sys.exit("El PIN debe ser numérico (4 a 8 dígitos)")


def _guardar_priv(priv_der, pin, pub_der):
    salt, iv = os.urandom(16), os.urandom(12)
    ct = AESGCM(_kdf(pin, salt)).encrypt(iv, priv_der, None)
    json.dump({"v": 1, "iter": ITER, "salt": b64(salt), "iv": b64(iv), "priv": b64(ct), "pub": b64(pub_der)},
              open(LLAVE, "w"), indent=1)


def _abrir_priv(pin):
    L = json.load(open(LLAVE))
    der = AESGCM(PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=ub64(L["salt"]), iterations=L["iter"]).derive(str(pin).encode())
                 ).decrypt(ub64(L["iv"]), ub64(L["priv"]), None)
    return serialization.load_der_private_key(der, password=None)


def cifrar(obj):
    if not os.path.exists(LLAVE):
        sys.exit("Falta data/llave.json: corre  python3 -I scripts/cripto.py init <PIN>")
    pub = serialization.load_der_public_key(ub64(json.load(open(LLAVE))["pub"]))
    k, iv = AESGCM.generate_key(256), os.urandom(12)
    ct = AESGCM(k).encrypt(iv, json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode(), None)
    return {"k": b64(pub.encrypt(k, OAEP)), "iv": b64(iv), "ct": b64(ct)}


def descifrar(blob, priv):
    k = priv.decrypt(ub64(blob["k"]), OAEP)
    return json.loads(AESGCM(k).decrypt(ub64(blob["iv"]), ub64(blob["ct"]), None))


def es_cifrado(x):
    return isinstance(x, dict) and set(x) == {"k", "iv", "ct"}


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "init":
        _pin_ok(sys.argv[2])
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        priv = key.private_bytes(serialization.Encoding.DER, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
        pub = key.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
        _guardar_priv(priv, sys.argv[2], pub)
        print("Llave nueva en", LLAVE)
    elif cmd == "cambiar":
        _pin_ok(sys.argv[3])
        key = _abrir_priv(sys.argv[2])
        priv = key.private_bytes(serialization.Encoding.DER, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
        _guardar_priv(priv, sys.argv[3], ub64(json.load(open(LLAVE))["pub"]))
        print("PIN cambiado")
    elif cmd == "probar":
        key = _abrir_priv(sys.argv[2])
        lt = json.load(open(os.path.join(ROOT, "data", "latest.json")))
        p = descifrar(lt["privado"], key)
        print("latest: bonos", len(p.get("bonos", [])), "fondo", len(p.get("fondo", [])))
        bd = json.load(open(os.path.join(ROOT, "data", "bonos_detalle.json")))
        print("bonos_detalle:", len([descifrar(v, key) for v in bd.values()]), "meses")
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
